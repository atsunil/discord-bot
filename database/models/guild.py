from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from shared.config import DEFAULT_PREFIX


@dataclass(slots=True)
class GuildConfigModel:
    guild_id: str
    guild_name: str
    prefix: str = DEFAULT_PREFIX
    allowed_channels: list[str] = field(default_factory=list)
    max_purge: int = 100
    super_user_roles: list[str] = field(default_factory=list)
    plan_tier: str = "free"
    license_key: str | None = None
    dj_role_id: str | None = None
    default_language: str = "en"
    ai_moderation_enabled: bool = False
    ai_moderation_threshold: float = 0.85
    ai_moderation_whitelist_roles: list[str] = field(default_factory=list)
    welcome_config: dict[str, Any] = field(
        default_factory=lambda: {
            "channel_id": None,
            "bg_color": "#1f2937",
            "enabled": False,
            "message_template": "Welcome to {server_name}, {user}!",
        }
    )
    persona: dict[str, Any] = field(
        default_factory=lambda: {
            "bot_name": "Moloj",
            "personality": "Helpful, concise, and professional.",
            "avatar_url": None,
            "language_style": "professional",
            "forbidden_topics": [],
        }
    )
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_document(self) -> dict[str, Any]:
        return {
            "guild_id": self.guild_id,
            "guild_name": self.guild_name,
            "prefix": self.prefix,
            "allowed_channels": self.allowed_channels,
            "max_purge": self.max_purge,
            "super_user_roles": self.super_user_roles,
            "plan_tier": self.plan_tier,
            "license_key": self.license_key,
            "dj_role_id": self.dj_role_id,
            "default_language": self.default_language,
            "ai_moderation_enabled": self.ai_moderation_enabled,
            "ai_moderation_threshold": self.ai_moderation_threshold,
            "ai_moderation_whitelist_roles": self.ai_moderation_whitelist_roles,
            "welcome_config": self.welcome_config,
            "persona": self.persona,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
