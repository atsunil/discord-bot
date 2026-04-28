from __future__ import annotations

import logging
from datetime import timedelta

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel

from shared.config import settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        if not settings.mongo_uri:
            raise RuntimeError("MONGO_URI is required to use MongoDB features.")
        _client = AsyncIOMotorClient(settings.mongo_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        _db = get_client().get_default_database() or get_client()["moloj"]
    return _db


async def init_indexes() -> None:
    db = get_db()

    await db["guilds"].create_indexes(
        [IndexModel([("guild_id", ASCENDING)], unique=True, name="guild_id_unique")]
    )
    await db["history"].create_indexes(
        [
            IndexModel(
                [("guild_id", ASCENDING), ("channel_id", ASCENDING), ("timestamp", DESCENDING)],
                name="guild_channel_timestamp",
            ),
            IndexModel(
                [("timestamp", ASCENDING)],
                expireAfterSeconds=int(timedelta(days=7).total_seconds()),
                name="history_ttl",
            ),
        ]
    )
    await db["licenses"].create_indexes(
        [
            IndexModel([("license_key", ASCENDING)], unique=True, name="license_key_unique"),
            IndexModel([("guild_id", ASCENDING)], name="license_guild_lookup"),
        ]
    )
    await db["reaction_roles"].create_indexes(
        [
            IndexModel(
                [("guild_id", ASCENDING), ("message_id", ASCENDING), ("emoji", ASCENDING)],
                unique=True,
                name="reaction_role_unique",
            )
        ]
    )
    await db["voice_logs"].create_indexes(
        [
            IndexModel([("guild_id", ASCENDING), ("user_id", ASCENDING), ("join_time", DESCENDING)]),
            IndexModel([("leave_time", DESCENDING)]),
        ]
    )
    await db["user_memory"].create_indexes(
        [
            IndexModel([("guild_id", ASCENDING), ("user_id", ASCENDING), ("key", ASCENDING)], unique=True),
            IndexModel([("updated_at", DESCENDING)]),
        ]
    )
    await db["image_usage"].create_indexes([IndexModel([("guild_id", ASCENDING), ("user_id", ASCENDING), ("created_at", DESCENDING)])])
    await db["auto_translate"].create_indexes([IndexModel([("guild_id", ASCENDING), ("channel_id", ASCENDING)], unique=True)])
    await db["custom_commands"].create_indexes(
        [IndexModel([("guild_id", ASCENDING), ("trigger", ASCENDING)], unique=True, name="custom_command_unique")]
    )
    await db["ai_mod_events"].create_indexes([IndexModel([("guild_id", ASCENDING), ("user_id", ASCENDING), ("created_at", DESCENDING)])])
    logger.info("MongoDB indexes initialized.")


async def close_mongo() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None
