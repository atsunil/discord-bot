from __future__ import annotations

import json
import logging
from collections import OrderedDict
from datetime import UTC, datetime

import discord
from discord import app_commands
from discord.ext import commands
from openai import AsyncOpenAI

from database.client import get_db
from database.queries.guild_queries import get_guild_config
from shared.config import settings

logger = logging.getLogger(__name__)


class MemoryCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.collection = get_db()["user_memory"]
        self.client = AsyncOpenAI(api_key=settings.nvidia_api_key, base_url=settings.nim_base_url) if settings.nvidia_api_key else None

    @app_commands.command(name="mymemory", description="Show what the bot remembers about you.")
    async def my_memory(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        memories = await self.get_user_memories(str(interaction.guild.id), str(interaction.user.id))
        if not memories:
            await interaction.response.send_message("I do not have any saved memories for you here yet.", ephemeral=True)
            return
        lines = [f"**{key}**: {value}" for key, value in memories.items()]
        embed = discord.Embed(title="Your saved memory", description="\n".join(lines), color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="forgetme", description="Delete all memory entries for you in this server.")
    async def forget_me(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        result = await self.collection.delete_many({"guild_id": str(interaction.guild.id), "user_id": str(interaction.user.id)})
        await interaction.response.send_message(f"Deleted {result.deleted_count} saved memories.", ephemeral=True)

    @app_commands.command(name="remember", description="Manually store a personal fact for yourself.")
    async def remember(self, interaction: discord.Interaction, key: str, value: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        if config.get("plan_tier") not in {"pro", "premium"}:
            await interaction.response.send_message("Saved memory is available on Pro and Premium plans.", ephemeral=True)
            return
        await self.store_memory(str(interaction.guild.id), str(interaction.user.id), key, value)
        await interaction.response.send_message(f"I'll remember `{key} = {value}` for this server.", ephemeral=True)

    async def get_user_memories(self, guild_id: str, user_id: str) -> dict[str, str]:
        cursor = self.collection.find({"guild_id": guild_id, "user_id": user_id}).sort("updated_at", 1)
        rows = await cursor.to_list(length=20)
        return OrderedDict((row["key"], row["value"]) for row in rows)

    async def store_memory(self, guild_id: str, user_id: str, key: str, value: str) -> None:
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"guild_id": guild_id, "user_id": user_id, "key": key},
            {"$set": {"value": value, "updated_at": now}},
            upsert=True,
        )
        await self._trim_memories(guild_id, user_id, max_items=20)

    async def extract_and_store(self, guild_id: str, user_id: str, user_message: str) -> dict[str, str]:
        if self.client is None:
            return {}
        prompt = (
            "Extract any personal facts mentioned by the user. "
            "Return strict JSON as an object of key/value pairs, or {} if nothing is worth storing. "
            "Only include facts with high confidence."
        )
        try:
            completion = await self.client.chat.completions.create(
                model=settings.nim_fallback_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_message},
                ],
                stream=False,
            )
            content = completion.choices[0].message.content or "{}"
            data = json.loads(content)
            if not isinstance(data, dict):
                return {}
            stored: dict[str, str] = {}
            for key, value in data.items():
                if isinstance(key, str) and isinstance(value, str):
                    await self.store_memory(guild_id, user_id, key, value)
                    stored[key] = value
            return stored
        except Exception as exc:  # pragma: no cover - external API behavior
            logger.warning("Memory extraction failed: %s", exc)
            return {}

    async def _trim_memories(self, guild_id: str, user_id: str, max_items: int) -> None:
        cursor = self.collection.find({"guild_id": guild_id, "user_id": user_id}, {"_id": 1}).sort("updated_at", 1)
        rows = await cursor.to_list(length=None)
        overflow = max(len(rows) - max_items, 0)
        if overflow > 0:
            await self.collection.delete_many({"_id": {"$in": [row["_id"] for row in rows[:overflow]]}})


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemoryCog(bot))
