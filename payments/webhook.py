from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from database.queries.guild_queries import update_guild_config
from database.queries.license_queries import create_license
from shared.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])


def _verify_webhook_signature(body: bytes, signature: str | None) -> bool:
    if not settings.razorpay_webhook_secret or not signature:
        return False
    digest = hmac.new(
        settings.razorpay_webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, signature)


async def _send_confirmation_dm(user_id: str, content: str) -> None:
    if not settings.discord_bot_token:
        return
    headers = {
        "Authorization": f"Bot {settings.discord_bot_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        channel_response = await client.post("https://discord.com/api/v10/users/@me/channels", headers=headers, json={"recipient_id": user_id})
        channel_response.raise_for_status()
        channel_id = channel_response.json()["id"]
        await client.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers=headers,
            json={"content": content},
        )


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None),
) -> dict[str, Any]:
    body = await request.body()
    if not _verify_webhook_signature(body, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    event = await request.json()
    event_name = event.get("event")
    payment = (((event.get("payload") or {}).get("payment") or {}).get("entity") or {})
    notes = payment.get("notes") or {}
    guild_id = notes.get("guild_id")
    plan_tier = notes.get("plan_tier")
    owner_id = notes.get("owner_id")

    if event_name == "payment.captured" and guild_id and plan_tier:
        license_doc = await create_license(
            plan_tier=plan_tier,
            razorpay_order_id=payment.get("order_id", "unknown"),
            guild_id=guild_id,
            payment_id=payment.get("id"),
        )
        await update_guild_config(
            guild_id,
            {
                "plan_tier": plan_tier,
                "license_key": license_doc["license_key"],
            },
        )
        if owner_id:
            try:
                await _send_confirmation_dm(
                    owner_id,
                    f"Your Moloj {plan_tier.title()} payment was received and activated for guild `{guild_id}`.",
                )
            except Exception as exc:  # pragma: no cover - external network behavior
                logger.warning("Failed to send payment confirmation DM: %s", exc)
        return {"status": "ok", "activated": True}

    if event_name == "payment.failed":
        logger.warning("Payment failed payload=%s", payment)
        return {"status": "ok", "activated": False}

    return {"status": "ignored"}
