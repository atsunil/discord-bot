from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Awaitable, Callable

import discord

from database.queries.license_queries import check_license_valid
from shared.config import settings

LicenseLookup = Callable[[str], Awaitable[tuple[bool, str]]]

FEATURE_GATES = {
    "free": {"chat", "custom_commands_basic"},
    "pro": {
        "chat",
        "moderation",
        "role_management",
        "reaction_roles",
        "welcome",
        "voice_tracker",
        "translation",
        "ai_moderation",
        "custom_commands",
    },
    "premium": {
        "chat",
        "moderation",
        "role_management",
        "reaction_roles",
        "welcome",
        "voice_tracker",
        "translation",
        "ai_moderation",
        "custom_commands",
        "music",
        "image_generation",
        "memory",
        "persona",
        "agents",
    },
}


@dataclass(slots=True)
class CachedLicense:
    plan_tier: str
    expires_at: float


class LicenseManager:
    def __init__(self, fetcher: LicenseLookup = check_license_valid, ttl_seconds: int = 300) -> None:
        self.fetcher = fetcher
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, CachedLicense] = {}

    async def get_plan_tier(self, guild_id: str) -> str:
        cached = self._cache.get(guild_id)
        now = time.time()
        if cached and cached.expires_at > now:
            return cached.plan_tier

        valid, plan_tier = await self.fetcher(guild_id)
        resolved = plan_tier if valid else "free"
        self._cache[guild_id] = CachedLicense(plan_tier=resolved, expires_at=now + self.ttl_seconds)
        return resolved

    async def is_feature_allowed(self, guild_id: str, feature_name: str) -> bool:
        plan = await self.get_plan_tier(guild_id)
        if feature_name == "custom_commands":
            return plan in {"pro", "premium"}
        if feature_name == "custom_commands_basic":
            return True
        return feature_name in FEATURE_GATES.get(plan, set())

    def invalidate(self, guild_id: str) -> None:
        self._cache.pop(guild_id, None)

    def clear(self) -> None:
        self._cache.clear()


def build_upgrade_embed(guild_id: str) -> discord.Embed:
    embed = discord.Embed(
        title="⚡ Upgrade to Pro",
        description=(
            "**Free**: AI chat only\n"
            "**Pro**: moderation, role tools, translation, welcome cards, reaction roles\n"
            "**Premium**: everything in Pro plus music, image generation, memory, persona, and agents"
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Billing", value=f"{settings.dashboard_url.rstrip('/')}/dashboard/{guild_id}/billing", inline=False)
    embed.set_footer(text="Upgrade in the dashboard billing page.")
    return embed
