from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import DESCENDING

from database.client import get_db
from database.models.history import HistoryEntryModel
from shared.config import MAX_HISTORY_PER_CHANNEL


async def get_history(guild_id: str, channel_id: str, limit: int = 20) -> list[dict[str, Any]]:
    collection = get_db()["history"]
    cursor = (
        collection.find({"guild_id": guild_id, "channel_id": channel_id})
        .sort("timestamp", DESCENDING)
        .limit(limit)
    )
    documents = await cursor.to_list(length=limit)
    return list(reversed(documents))


async def save_message(
    guild_id: str,
    channel_id: str,
    role: str,
    content: str,
    username: str,
) -> dict[str, Any]:
    collection = get_db()["history"]
    entry = HistoryEntryModel(
        guild_id=guild_id,
        channel_id=channel_id,
        role=role,
        content=content,
        username=username,
    ).to_document()
    result = await collection.insert_one(entry)
    await trim_channel_history(guild_id=guild_id, channel_id=channel_id, keep=MAX_HISTORY_PER_CHANNEL)
    entry["_id"] = result.inserted_id
    return entry


async def trim_channel_history(guild_id: str, channel_id: str, keep: int = MAX_HISTORY_PER_CHANNEL) -> None:
    collection = get_db()["history"]
    cursor = (
        collection.find({"guild_id": guild_id, "channel_id": channel_id}, {"_id": 1})
        .sort("timestamp", DESCENDING)
        .skip(keep)
    )
    stale = await cursor.to_list(length=None)
    if stale:
        await collection.delete_many({"_id": {"$in": [row["_id"] for row in stale]}})


async def clear_history(guild_id: str, channel_id: str) -> int:
    result = await get_db()["history"].delete_many({"guild_id": guild_id, "channel_id": channel_id})
    return result.deleted_count


async def prune_old_history() -> int:
    cutoff = datetime.now(UTC) - timedelta(days=7)
    result = await get_db()["history"].delete_many({"timestamp": {"$lt": cutoff}})
    return result.deleted_count


async def get_history_stats(guild_id: str) -> dict[str, Any]:
    collection = get_db()["history"]
    pipeline = [
        {"$match": {"guild_id": guild_id}},
        {
            "$facet": {
                "message_count": [{"$count": "count"}],
                "top_channels": [
                    {"$group": {"_id": "$channel_id", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 5},
                ],
            }
        },
    ]
    results = await collection.aggregate(pipeline).to_list(length=1)
    if not results:
        return {"message_count": 0, "top_channels": []}
    item = results[0]
    return {
        "message_count": item["message_count"][0]["count"] if item["message_count"] else 0,
        "top_channels": item["top_channels"],
    }
