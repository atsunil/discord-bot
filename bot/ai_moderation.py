from __future__ import annotations

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands
from transformers import pipeline

from database.client import get_db
from database.queries.guild_queries import get_guild_config, update_guild_config
from shared.config import TOXICITY_MODEL_FALLBACKS

EXPLICIT_KEYWORDS = {"nsfw", "porn", "nude", "sex", "explicit"}


class AIModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.collection = get_db()["ai_mod_events"]
        self.executor = ThreadPoolExecutor(max_workers=1)
        self._classifier = None
        self._cache: dict[str, tuple[datetime, float]] = {}

    aimod = app_commands.Group(name="aimod", description="Manage AI moderation settings.")

    @aimod.command(name="enable", description="Enable AI moderation in this server.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def enable_aimod(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        if config.get("plan_tier") not in {"pro", "premium"}:
            await interaction.response.send_message("AI moderation is available on Pro and Premium plans.", ephemeral=True)
            return
        await update_guild_config(str(interaction.guild.id), {"ai_moderation_enabled": True})
        await interaction.response.send_message("AI moderation enabled.", ephemeral=True)

    @aimod.command(name="disable", description="Disable AI moderation in this server.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def disable_aimod(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await update_guild_config(str(interaction.guild.id), {"ai_moderation_enabled": False})
        await interaction.response.send_message("AI moderation disabled.", ephemeral=True)

    @aimod.command(name="threshold", description="Set the toxicity threshold for auto moderation.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def threshold_aimod(self, interaction: discord.Interaction, value: app_commands.Range[float, 0.0, 1.0]) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await update_guild_config(str(interaction.guild.id), {"ai_moderation_threshold": float(value)})
        await interaction.response.send_message(f"AI moderation threshold set to `{value:.2f}`.", ephemeral=True)

    @aimod.command(name="whitelist", description="Exempt a role from AI moderation.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def whitelist_aimod(self, interaction: discord.Interaction, role: discord.Role) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        whitelist = set(config.get("ai_moderation_whitelist_roles", []))
        whitelist.add(str(role.id))
        await update_guild_config(str(interaction.guild.id), {"ai_moderation_whitelist_roles": sorted(whitelist)})
        await interaction.response.send_message(f"{role.mention} is now exempt from AI moderation.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None or not message.content.strip():
            return
        config = await get_guild_config(str(message.guild.id), message.guild.name)
        if not config.get("ai_moderation_enabled"):
            return
        if any(str(role.id) in config.get("ai_moderation_whitelist_roles", []) for role in getattr(message.author, "roles", [])):
            return
        score = await self._score_message(message.content)
        keyword_flag = any(keyword in message.content.lower() for keyword in EXPLICIT_KEYWORDS)
        threshold = float(config.get("ai_moderation_threshold", 0.85))
        if score < threshold and not keyword_flag:
            return

        await message.delete()
        try:
            await message.author.send("Your message was removed for violating community guidelines.")
        except discord.Forbidden:
            pass

        await self.collection.insert_one(
            {
                "guild_id": str(message.guild.id),
                "user_id": str(message.author.id),
                "content": message.content[:2000],
                "toxicity_score": score,
                "created_at": datetime.now(UTC),
            }
        )

        mod_log = discord.utils.get(message.guild.text_channels, name="mod-log")
        if mod_log is not None:
            embed = discord.Embed(title="AI Moderation", color=discord.Color.red())
            embed.description = message.content[:1900]
            embed.add_field(name="User", value=message.author.mention)
            embed.add_field(name="Score", value=f"{score:.2f}")
            await mod_log.send(embed=embed)

        count = await self.collection.count_documents(
            {
                "guild_id": str(message.guild.id),
                "user_id": str(message.author.id),
                "created_at": {"$gte": datetime.now(UTC) - timedelta(hours=24)},
            }
        )
        if count >= 3 and isinstance(message.author, discord.Member):
            await message.author.timeout(discord.utils.utcnow() + timedelta(hours=1), reason="AI moderation repeat violations")

    async def _score_message(self, content: str) -> float:
        normalized = content.strip().lower()
        if len(normalized) <= 200:
            cached = self._cache.get(normalized)
            if cached and cached[0] > datetime.now(UTC):
                return cached[1]
        classifier = await self._get_classifier()
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(self.executor, functools.partial(classifier, content))
        score = 0.0
        for row in results:
            label = row.get("label", "").lower()
            if "toxic" in label:
                score = max(score, float(row.get("score", 0.0)))
        if len(normalized) <= 200:
            self._cache[normalized] = (datetime.now(UTC) + timedelta(minutes=10), score)
        return score

    async def _get_classifier(self):
        if self._classifier is not None:
            return self._classifier
        loop = asyncio.get_running_loop()
        for model_name in TOXICITY_MODEL_FALLBACKS:
            try:
                self._classifier = await loop.run_in_executor(
                    self.executor,
                    functools.partial(pipeline, "text-classification", model=model_name),
                )
                return self._classifier
            except Exception:
                continue
        raise RuntimeError("Could not load a toxicity model for AI moderation.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AIModerationCog(bot))
