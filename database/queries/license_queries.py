from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from database.client import get_db
from database.models.license import LicenseModel
from database.queries.guild_queries import update_guild_config


async def create_license(
    plan_tier: str,
    razorpay_order_id: str,
    guild_id: str | None = None,
    payment_id: str | None = None,
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    license_key = str(uuid.uuid4())
    license_record = LicenseModel(
        license_key=license_key,
        plan_tier=plan_tier,
        guild_id=guild_id,
        activated_at=datetime.now(UTC) if guild_id else None,
        expires_at=expires_at,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=payment_id,
    ).to_document()
    await get_db()["licenses"].insert_one(license_record)
    return license_record


async def activate_license(license_key: str, guild_id: str, payment_id: str | None = None) -> dict[str, Any] | None:
    collection = get_db()["licenses"]
    now = datetime.now(UTC)
    await collection.update_one(
        {"license_key": license_key, "is_active": True},
        {"$set": {"guild_id": guild_id, "activated_at": now, "razorpay_payment_id": payment_id}},
    )
    license_doc = await collection.find_one({"license_key": license_key, "is_active": True})
    if license_doc:
        await update_guild_config(
            guild_id,
            {
                "plan_tier": license_doc["plan_tier"],
                "license_key": license_key,
            },
        )
    return license_doc


async def get_guild_license(guild_id: str) -> dict[str, Any] | None:
    return await get_db()["licenses"].find_one({"guild_id": guild_id, "is_active": True})


async def check_license_valid(guild_id: str) -> tuple[bool, str]:
    license_doc = await get_guild_license(guild_id)
    if not license_doc:
        return False, "free"
    expires_at = license_doc.get("expires_at")
    if expires_at and expires_at < datetime.now(UTC):
        await deactivate_license(guild_id)
        return False, "free"
    return True, str(license_doc["plan_tier"])


async def deactivate_license(guild_id: str) -> int:
    result = await get_db()["licenses"].update_many({"guild_id": guild_id}, {"$set": {"is_active": False}})
    await update_guild_config(guild_id, {"plan_tier": "free", "license_key": None})
    return result.modified_count
