from __future__ import annotations

import base64
import io
import logging
import random
from datetime import UTC, datetime, timedelta
from typing import Any

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from database.client import get_db
from database.queries.guild_queries import get_guild_config
from shared.config import IMAGE_RATE_LIMIT, IMAGE_RATE_LIMIT_WINDOW_SECONDS, NSFW_KEYWORDS, settings

logger = logging.getLogger(__name__)


class ImageGenerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.collection = get_db()["image_usage"]

    @app_commands.command(name="imagine", description="Generate an image from a text prompt.")
    async def imagine(self, interaction: discord.Interaction, prompt: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        if config.get("plan_tier") != "premium":
            await interaction.response.send_message("Image generation is a Premium feature.", ephemeral=True)
            return
        if any(keyword in prompt.lower() for keyword in NSFW_KEYWORDS):
            await interaction.response.send_message("That prompt was blocked by the safety filter.", ephemeral=True)
            return
        allowed, remaining = await self._check_limit(str(interaction.guild.id), str(interaction.user.id))
        if not allowed:
            await interaction.response.send_message("You've used all 3 image generations this hour.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        try:
            seed = random.randint(1, 99999999)
            image_bytes = await self._generate_image(prompt, seed=seed, steps=25)
            await self.collection.insert_one(
                {
                    "guild_id": str(interaction.guild.id),
                    "user_id": str(interaction.user.id),
                    "prompt": prompt,
                    "seed": seed,
                    "created_at": datetime.now(UTC),
                }
            )
            file = discord.File(io.BytesIO(image_bytes), filename="moloj-image.png")
            embed = discord.Embed(description=prompt, color=discord.Color.blurple())
            embed.set_footer(text=f"Model: SDXL via NVIDIA NIM | Seed: {seed} | Steps: 25 | Remaining: {remaining - 1}")
            await interaction.followup.send(embed=embed, file=file)
        except Exception as exc:  # pragma: no cover - network/runtime behavior
            logger.exception("Image generation failed: %s", exc)
            await interaction.followup.send(f"Image generation failed: {exc}", ephemeral=True)

    async def _check_limit(self, guild_id: str, user_id: str) -> tuple[bool, int]:
        cutoff = datetime.now(UTC) - timedelta(seconds=IMAGE_RATE_LIMIT_WINDOW_SECONDS)
        count = await self.collection.count_documents(
            {
                "guild_id": guild_id,
                "user_id": user_id,
                "created_at": {"$gte": cutoff},
            }
        )
        remaining = max(IMAGE_RATE_LIMIT - count, 0)
        return count < IMAGE_RATE_LIMIT, remaining

    async def _generate_image(self, prompt: str, *, seed: int, steps: int) -> bytes:
        if not settings.nvidia_api_key:
            raise RuntimeError("NVIDIA_API_KEY is not configured.")
        payload = {
            "text_prompts": [{"text": prompt}],
            "seed": seed,
            "steps": steps,
        }
        headers = {
            "Authorization": f"Bearer {settings.nvidia_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(settings.nim_image_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return self._decode_image_response(data)

    def _decode_image_response(self, data: dict[str, Any]) -> bytes:
        candidates = [
            data.get("artifacts", [{}])[0].get("base64"),
            data.get("image"),
            data.get("images", [{}])[0].get("base64") if data.get("images") else None,
            data.get("data", [{}])[0].get("b64_json") if data.get("data") else None,
        ]
        for candidate in candidates:
            if candidate:
                return base64.b64decode(candidate)
        raise RuntimeError("Image API response did not include base64 image content.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ImageGenerationCog(bot))
