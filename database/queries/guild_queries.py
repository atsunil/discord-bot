from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from database.client import get_db
from database.models.guild import GuildConfigModel


def build_default_guild_config(guild_id: str, guild_name: str = "Unknown Guild") -> dict[str, Any]:
    return GuildConfigModel(guild_id=guild_id, guild_name=guild_name).to_document()


async def upsert_guild(guild_id: str, guild_name: str) -> dict[str, Any]:
    collection = get_db()["guilds"]
    default_doc = build_default_guild_config(guild_id=guild_id, guild_name=guild_name)
    await collection.update_one(
        {"guild_id": guild_id},
        {
            "$setOnInsert": default_doc,
            "$set": {"guild_name": guild_name, "updated_at": datetime.now(UTC)},
        },
        upsert=True,
    )
    return await collection.find_one({"guild_id": guild_id}) or default_doc


async def get_guild_config(guild_id: str, guild_name: str = "Unknown Guild") -> dict[str, Any]:
    collection = get_db()["guilds"]
    document = await collection.find_one({"guild_id": guild_id})
    if document:
        return document
    return await upsert_guild(guild_id=guild_id, guild_name=guild_name)


async def update_guild_config(guild_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    collection = get_db()["guilds"]
    updates = {**updates, "updated_at": datetime.now(UTC)}
    await collection.update_one({"guild_id": guild_id}, {"$set": updates}, upsert=True)
    document = await collection.find_one({"guild_id": guild_id})
    if document is None:
        raise RuntimeError(f"Failed to update guild config for {guild_id}")
    return document
