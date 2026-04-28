"""
config.py — Bot Configuration Defaults
Centralized constants and default values for Moloj.
"""

# ─── Bot Identity ──────────────────────────────────────────────────────────────
BOT_NAME = "Moloj"
DEFAULT_PREFIX = "moloj"

# ─── Limits ────────────────────────────────────────────────────────────────────
MAX_HISTORY = 20
DEFAULT_MAX_PURGE = 100
MAX_SPAM_COUNT = 100
MAX_STICKER_COUNT = 100

# ─── Models ────────────────────────────────────────────────────────────────────
MODELS = {
    "default": "openai/gpt-oss-120b",
    "fast": "meta/llama-3.3-70b-instruct",
    "powerful": "meta/llama-3.1-405b-instruct",
}

# ─── Streaming ─────────────────────────────────────────────────────────────────
STREAM_EDIT_INTERVAL = 50  # characters between Discord message edits
STREAM_TEMPERATURE = 0.7
STREAM_MAX_TOKENS = 1024
