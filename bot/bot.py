from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Awaitable, Callable

import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aiohttp import web
import discord
from discord.ext import commands

from bot.actions import execute_tool
from bot.ai_engine import AIContext, AIEngine
from bot.interactive import parse_interactive_response
from bot.license import LicenseManager, build_upgrade_embed
from bot.security import get_role_tag, is_super_user
from database.client import close_mongo, init_indexes
from database.queries.guild_queries import get_guild_config, upsert_guild
from database.queries.history_queries import get_history, save_message
from shared.config import GUILD_CACHE_TTL_SECONDS, settings

logger = logging.getLogger("moloj")

EXTENSIONS = [
    "bot.slash_commands",
    "bot.reaction_roles",
    "bot.music",
    "bot.welcome",
    "bot.voice_tracker",
    "bot.memory",
    "bot.image_gen",
    "bot.translator",
    "bot.ai_moderation",
    "bot.persona",
    "bot.custom_commands",
]

ACTION_FEATURE_MAP = {
    "kick_member": "moderation",
    "ban_member": "moderation",
    "unban_member": "moderation",
    "timeout_member": "moderation",
    "purge_messages": "moderation",
    "send_announcement": "moderation",
    "assign_role": "role_management",
    "remove_role": "role_management",
    "create_channel": "role_management",
    "send_dm": "moderation",
    "set_bot_presence": "moderation",
    "server_info": "chat",
    "list_members": "chat",
}


def setup_logging() -> None:
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(settings.log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(console)
    logger.addHandler(file_handler)
    logging.getLogger("discord").setLevel(logging.INFO)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


@dataclass(slots=True)
class CachedGuildConfig:
    value: dict[str, Any]
    expires_at: float


class MolojBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None)
        self.guild_cache: dict[str, CachedGuildConfig] = {}
        self.license_manager = LicenseManager()
        self.ai_engine = AIEngine()
        self.health_runner: web.AppRunner | None = None
        self.synced_once = False

    async def setup_hook(self) -> None:
        await init_indexes()
        for extension in EXTENSIONS:
            try:
                await self.load_extension(extension)
                logger.info("Loaded extension %s", extension)
            except Exception:  # pragma: no cover - extension runtime behavior
                logger.exception("Failed to load extension %s", extension)
        await self.start_health_server()

    async def close(self) -> None:
        if self.health_runner is not None:
            await self.health_runner.cleanup()
            self.health_runner = None
        await close_mongo()
        await super().close()

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "unknown")
        if not self.synced_once:
            try:
                await self.tree.sync()
                self.synced_once = True
                logger.info("Slash commands synced.")
            except Exception:
                logger.exception("Failed to sync application commands.")

    async def on_disconnect(self) -> None:
        logger.warning("Discord gateway disconnected.")

    async def on_guild_join(self, guild: discord.Guild) -> None:
        await upsert_guild(str(guild.id), guild.name)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        if message.guild is not None:
            await upsert_guild(str(message.guild.id), message.guild.name)
            config = await self.get_cached_guild_config(message.guild.id, message.guild.name)
            allowed_channels = config.get("allowed_channels", [])
            if allowed_channels and str(message.channel.id) not in allowed_channels:
                return
        else:
            config = {"prefix": "moloj", "plan_tier": "premium"}

        prompt = self.extract_prompt(message, config)
        if prompt is None:
            return

        if not prompt.strip():
            await message.channel.send("Say something after the trigger so I know how to help.")
            return

        await self.respond_to_prompt(message=message, prompt=prompt.strip(), config=config)

    async def respond_to_prompt(self, *, message: discord.Message, prompt: str, config: dict[str, Any]) -> None:
        guild = message.guild
        guild_id = str(guild.id) if guild else "dm"
        plan_tier = await self.license_manager.get_plan_tier(guild_id) if guild else "premium"
        history = await get_history(guild_id, str(message.channel.id), limit=20)

        memories = {}
        memory_cog = self.get_cog("MemoryCog")
        if guild and plan_tier in {"pro", "premium"} and memory_cog is not None:
            memories = await memory_cog.get_user_memories(str(guild.id), str(message.author.id))

        persona = config.get("persona") if guild and plan_tier == "premium" else None
        context = AIContext(
            username=message.author.display_name,
            user_id=str(message.author.id),
            role_tag=get_role_tag(message.author) if isinstance(message.author, discord.Member) else "Member",
            channel_name=message.channel.name if hasattr(message.channel, "name") else "DM",
            guild_name=guild.name if guild else "Direct Messages",
            plan_tier=plan_tier,
            history=[{"role": row.get("role", "user"), "content": row.get("content", "")} for row in history],
            persona=persona,
            memories=memories,
        )

        if guild:
            await save_message(str(guild.id), str(message.channel.id), "user", prompt, message.author.display_name)

        async with message.channel.typing():
            response = await self.ai_engine.generate_response(
                user_message=prompt,
                context=context,
                caller_is_superuser=is_super_user(message.author.id),
            )

        if response.tool_calls:
            await self.handle_tool_calls(message=message, tool_calls=response.tool_calls, config=config)
            if guild and memory_cog is not None and plan_tier in {"pro", "premium"}:
                await memory_cog.extract_and_store(str(guild.id), str(message.author.id), prompt)
            return

        cleaned_text, view = parse_interactive_response(
            response.text or "I couldn't think of a reply just now.",
            callback=self._build_interaction_callback(message, config),
        )
        sent = await message.channel.send(cleaned_text, view=view)

        if guild:
            await save_message(str(guild.id), str(message.channel.id), "assistant", cleaned_text, self.user.display_name if self.user else "Moloj")
            if memory_cog is not None and plan_tier in {"pro", "premium"}:
                await memory_cog.extract_and_store(str(guild.id), str(message.author.id), prompt)

    async def handle_tool_calls(self, *, message: discord.Message, tool_calls: list[Any], config: dict[str, Any]) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            await message.channel.send("Server tools are only available inside a guild.")
            return

        for tool_call in tool_calls:
            feature = ACTION_FEATURE_MAP.get(tool_call.name, "moderation")
            if not await self.license_manager.is_feature_allowed(str(message.guild.id), feature):
                await message.channel.send(embed=build_upgrade_embed(str(message.guild.id)))
                return

            result = await execute_tool(
                tool_name=tool_call.name,
                tool_args=tool_call.arguments,
                bot=self,
                guild=message.guild,
                channel=message.channel,
                caller=message.author,
                guild_config=config,
            )
            data = result.get("data")
            if isinstance(data, discord.Embed):
                await message.channel.send(embed=data)
            else:
                await message.channel.send(result["message"])
            await save_message(
                str(message.guild.id),
                str(message.channel.id),
                "assistant",
                result["message"],
                self.user.display_name if self.user else "Moloj",
            )

    async def get_cached_guild_config(self, guild_id: int, guild_name: str) -> dict[str, Any]:
        key = str(guild_id)
        cached = self.guild_cache.get(key)
        now = time.time()
        if cached and cached.expires_at > now:
            return cached.value
        config = await get_guild_config(key, guild_name)
        self.guild_cache[key] = CachedGuildConfig(value=config, expires_at=now + GUILD_CACHE_TTL_SECONDS)
        return config

    def extract_prompt(self, message: discord.Message, config: dict[str, Any]) -> str | None:
        if message.guild is None:
            return message.content

        prefix = str(config.get("prefix", "moloj")).strip()
        mention_patterns = [rf"^<@!?{self.user.id}>\s*" if self.user else ""]
        content = message.content.strip()

        if prefix and content.lower().startswith(prefix.lower()):
            return content[len(prefix):].strip()

        if self.user and self.user.mentioned_in(message):
            for pattern in mention_patterns:
                cleaned = re.sub(pattern, "", content, count=1).strip()
                if cleaned != content:
                    return cleaned

        return None

    def _build_interaction_callback(
        self,
        message: discord.Message,
        config: dict[str, Any],
    ) -> Callable[[discord.Interaction, str], Awaitable[None]]:
        async def callback(interaction: discord.Interaction, choice: str) -> None:
            if not interaction.channel:
                return
            synthetic_message = message
            prompt = choice
            response_target = interaction.followup.send
            guild = interaction.guild
            guild_id = str(guild.id) if guild else "dm"
            plan_tier = await self.license_manager.get_plan_tier(guild_id) if guild else "premium"
            history = await get_history(guild_id, str(interaction.channel.id), limit=20)
            memories = {}
            memory_cog = self.get_cog("MemoryCog")
            if guild and plan_tier in {"pro", "premium"} and memory_cog is not None:
                memories = await memory_cog.get_user_memories(str(guild.id), str(interaction.user.id))

            context = AIContext(
                username=interaction.user.display_name if isinstance(interaction.user, discord.Member) else interaction.user.name,
                user_id=str(interaction.user.id),
                role_tag=get_role_tag(interaction.user) if isinstance(interaction.user, discord.Member) else "Member",
                channel_name=interaction.channel.name if hasattr(interaction.channel, "name") else "DM",
                guild_name=guild.name if guild else "Direct Messages",
                plan_tier=plan_tier,
                history=[{"role": row.get("role", "user"), "content": row.get("content", "")} for row in history],
                persona=config.get("persona") if plan_tier == "premium" else None,
                memories=memories,
            )
            response = await self.ai_engine.generate_response(
                user_message=prompt,
                context=context,
                caller_is_superuser=is_super_user(interaction.user.id),
            )
            if response.tool_calls and guild and isinstance(interaction.user, discord.Member):
                for tool_call in response.tool_calls:
                    result = await execute_tool(
                        tool_name=tool_call.name,
                        tool_args=tool_call.arguments,
                        bot=self,
                        guild=guild,
                        channel=interaction.channel,
                        caller=interaction.user,
                        guild_config=config,
                    )
                    if isinstance(result.get("data"), discord.Embed):
                        await response_target(embed=result["data"])
                    else:
                        await response_target(result["message"])
                return

            cleaned, view = parse_interactive_response(response.text, self._build_interaction_callback(message, config))
            await response_target(cleaned, view=view)

        return callback

    async def start_health_server(self) -> None:
        app = web.Application()
        app.router.add_get("/health", self.healthcheck)
        self.health_runner = web.AppRunner(app)
        await self.health_runner.setup()
        site = web.TCPSite(self.health_runner, settings.health_host, settings.port)
        await site.start()
        logger.info("Health check server listening on %s:%s", settings.health_host, settings.port)

    async def healthcheck(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "bot_user": str(self.user) if self.user else None})


async def run_bot_forever() -> None:
    setup_logging()
    settings.require("DISCORD_BOT_TOKEN", "NVIDIA_API_KEY", "MONGO_URI")
    backoff = 2
    while True:
        bot = MolojBot()
        try:
            await bot.start(settings.discord_bot_token)
            return
        except KeyboardInterrupt:
            await bot.close()
            return
        except Exception:  # pragma: no cover - gateway/network behavior
            logger.exception("Bot crashed. Restarting in %s seconds.", backoff)
            try:
                await bot.close()
            except Exception:
                pass
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


def main() -> None:
    asyncio.run(run_bot_forever())


if __name__ == "__main__":
    main()
