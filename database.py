"""
database.py — Supabase (PostgreSQL) Database Layer
Handles: conversation history persistence, per-server configuration
"""

import os
import logging
import asyncio
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Initialize Supabase client
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


async def init_db():
    if not supabase:
        logger.warning(
            "SUPABASE_URL or SUPABASE_KEY missing in .env! "
            "Database features (history, config) will be disabled."
        )
        return
    logger.info("Supabase client initialized via REST API.")


async def save_message(channel_id, guild_id, role, content):
    if not supabase:
        return
    def _run():
        try:
            supabase.table("conversation_history").insert({
                "channel_id": str(channel_id),
                "guild_id": str(guild_id),
                "role": role,
                "content": content
            }).execute()
        except Exception as e:
            logger.error(f"Supabase insert failed: {e}")
    await asyncio.to_thread(_run)


async def get_history(channel_id: str, limit: int = 20):
    if not supabase:
        return []
    def _run():
        try:
            response = supabase.table("conversation_history") \
                .select("role, content") \
                .eq("channel_id", str(channel_id)) \
                .order("timestamp", desc=True) \
                .limit(limit) \
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Supabase select failed: {e}")
            return []
    
    rows = await asyncio.to_thread(_run)
    # Reverse so oldest is first (ASC order)
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


async def clear_history(channel_id: str):
    if not supabase:
        return
    def _run():
        try:
            supabase.table("conversation_history").delete().eq("channel_id", str(channel_id)).execute()
        except Exception as e:
            logger.error(f"Supabase clear_history failed: {e}")
    await asyncio.to_thread(_run)
    logger.info(f"Cleared history for channel {channel_id}")


async def get_server_config(guild_id: str) -> dict:
    defaults = {
        "guild_id": str(guild_id),
        "prefix": "moloj",
        "allowed_channels": "",
        "max_purge": 100,
        "super_user_roles": ""
    }
    if not supabase:
        return defaults
        
    def _run():
        try:
            response = supabase.table("server_config").select("*").eq("guild_id", str(guild_id)).execute()
            if response.data:
                return response.data[0]
            # Insert defaults if no existing config is found
            supabase.table("server_config").upsert(defaults).execute()
            return defaults
        except Exception as e:
            logger.error(f"Supabase get_server_config failed: {e}")
            return defaults
            
    return await asyncio.to_thread(_run)


async def update_server_config(guild_id: str, **kwargs):
    if not supabase or not kwargs:
        return
    def _run():
        try:
            supabase.table("server_config").update(kwargs).eq("guild_id", str(guild_id)).execute()
        except Exception as e:
            logger.error(f"Supabase update_server_config failed: {e}")
    await asyncio.to_thread(_run)
    logger.info(f"Updated config for guild {guild_id}: {kwargs}")


async def prune_old_history(days: int = 7):
    if not supabase:
        return
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    def _run():
        try:
            supabase.table("conversation_history").delete().lt("timestamp", cutoff).execute()
        except Exception as e:
            logger.error(f"Supabase prune_old_history failed: {e}")
    await asyncio.to_thread(_run)
    logger.info(f"Pruned conversation history older than {days} days")
