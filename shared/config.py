from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

BOT_NAME = "Moloj"
DEFAULT_PREFIX = "moloj"
DEFAULT_PORT = 8080
DEFAULT_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_IMAGE_URL = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-xl"
DEFAULT_CHAT_MODEL = "nvidia/llama-3.1-nemotron-ultra-253b-v1"
FALLBACK_CHAT_MODEL = "meta/llama-3.1-70b-instruct"
DEFAULT_HISTORY_LIMIT = 20
MAX_HISTORY_PER_CHANNEL = 50
GUILD_CACHE_TTL_SECONDS = 60
LICENSE_CACHE_TTL_SECONDS = 300
AI_RETRY_ATTEMPTS = 3
AI_RETRY_BASE_DELAY_SECONDS = 2
REACTION_ROLE_LIMIT = 20
MUSIC_QUEUE_LIMIT = 50
VOICE_INACTIVITY_TIMEOUT_SECONDS = 180
IMAGE_RATE_LIMIT = 3
IMAGE_RATE_LIMIT_WINDOW_SECONDS = 3600
FREE_TIER_DAILY_MESSAGES = 50

SUPPORTED_LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "ru": "Russian",
    "pt": "Portuguese",
}

LANGUAGE_FLAGS = {
    "en": "🇬🇧",
    "hi": "🇮🇳",
    "ta": "🇮🇳",
    "te": "🇮🇳",
    "ml": "🇮🇳",
    "fr": "🇫🇷",
    "de": "🇩🇪",
    "es": "🇪🇸",
    "ja": "🇯🇵",
    "ko": "🇰🇷",
    "zh": "🇨🇳",
    "ar": "🇸🇦",
    "ru": "🇷🇺",
    "pt": "🇵🇹",
}

NSFW_KEYWORDS = {
    "nsfw",
    "nude",
    "nudity",
    "porn",
    "explicit",
    "sex",
    "fetish",
}

TOXICITY_MODEL_FALLBACKS = (
    "unitary/toxic-bert",
    "martin-ha/toxic-comment-model",
)


def _parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class AppConfig:
    discord_bot_token: str | None = field(default_factory=lambda: os.getenv("DISCORD_BOT_TOKEN"))
    discord_client_id: str | None = field(default_factory=lambda: os.getenv("DISCORD_CLIENT_ID"))
    discord_client_secret: str | None = field(default_factory=lambda: os.getenv("DISCORD_CLIENT_SECRET"))
    nvidia_api_key: str | None = field(default_factory=lambda: os.getenv("NVIDIA_API_KEY"))
    mongo_uri: str | None = field(default_factory=lambda: os.getenv("MONGO_URI"))
    razorpay_key_id: str | None = field(default_factory=lambda: os.getenv("RAZORPAY_KEY_ID"))
    razorpay_key_secret: str | None = field(default_factory=lambda: os.getenv("RAZORPAY_KEY_SECRET"))
    razorpay_webhook_secret: str | None = field(default_factory=lambda: os.getenv("RAZORPAY_WEBHOOK_SECRET"))
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "change-me"))
    dashboard_url: str = field(default_factory=lambda: os.getenv("DASHBOARD_URL", "http://localhost:8000"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", str(DEFAULT_PORT))))
    super_users: list[str] = field(default_factory=lambda: _parse_csv(os.getenv("SUPER_USERS", "")))
    allow_unsafe_tools: bool = field(default_factory=lambda: _bool_env("ALLOW_UNSAFE_TOOLS", False))
    nim_base_url: str = field(default_factory=lambda: os.getenv("NIM_BASE_URL", DEFAULT_NIM_BASE_URL))
    nim_chat_model: str = field(default_factory=lambda: os.getenv("NIM_CHAT_MODEL", DEFAULT_CHAT_MODEL))
    nim_fallback_model: str = field(default_factory=lambda: os.getenv("NIM_FALLBACK_MODEL", FALLBACK_CHAT_MODEL))
    nim_image_url: str = field(default_factory=lambda: os.getenv("NIM_IMAGE_URL", DEFAULT_IMAGE_URL))
    lavalink_uri: str = field(default_factory=lambda: os.getenv("LAVALINK_URI", "https://lavalink.devamop.in"))
    lavalink_password: str = field(default_factory=lambda: os.getenv("LAVALINK_PASSWORD", "devamop.in"))
    health_host: str = field(default_factory=lambda: os.getenv("HEALTH_HOST", "0.0.0.0"))
    log_file: str = field(default_factory=lambda: os.getenv("LOG_FILE", "moloj.log"))

    def require(self, *names: str) -> None:
        missing = [name for name in names if not self.as_mapping().get(name)]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required environment variables: {joined}")

    def dashboard_origin(self) -> str:
        parsed = urlparse(self.dashboard_url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return self.dashboard_url.rstrip("/")

    def as_mapping(self) -> dict[str, Any]:
        return {
            "DISCORD_BOT_TOKEN": self.discord_bot_token,
            "DISCORD_CLIENT_ID": self.discord_client_id,
            "DISCORD_CLIENT_SECRET": self.discord_client_secret,
            "NVIDIA_API_KEY": self.nvidia_api_key,
            "MONGO_URI": self.mongo_uri,
            "RAZORPAY_KEY_ID": self.razorpay_key_id,
            "RAZORPAY_KEY_SECRET": self.razorpay_key_secret,
            "RAZORPAY_WEBHOOK_SECRET": self.razorpay_webhook_secret,
            "SECRET_KEY": self.secret_key,
            "DASHBOARD_URL": self.dashboard_url,
            "PORT": self.port,
            "SUPER_USERS": self.super_users,
            "ALLOW_UNSAFE_TOOLS": self.allow_unsafe_tools,
            "NIM_BASE_URL": self.nim_base_url,
            "NIM_CHAT_MODEL": self.nim_chat_model,
            "NIM_FALLBACK_MODEL": self.nim_fallback_model,
            "NIM_IMAGE_URL": self.nim_image_url,
            "LAVALINK_URI": self.lavalink_uri,
            "LAVALINK_PASSWORD": self.lavalink_password,
            "HEALTH_HOST": self.health_host,
            "LOG_FILE": self.log_file,
        }


settings = AppConfig()
