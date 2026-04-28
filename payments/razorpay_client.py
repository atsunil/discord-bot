from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import razorpay

from payments.plans import PLANS
from shared.config import settings

logger = logging.getLogger(__name__)


def get_razorpay_client() -> razorpay.Client:
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise RuntimeError("Razorpay credentials are not configured.")
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def create_order(plan_tier: str, guild_id: str, owner_id: str | None = None) -> dict[str, Any]:
    if plan_tier not in PLANS:
        raise ValueError(f"Unknown plan: {plan_tier}")
    payload = {
        "amount": PLANS[plan_tier]["price_inr"],
        "currency": "INR",
        "payment_capture": 1,
        "notes": {
            "guild_id": guild_id,
            "plan_tier": plan_tier,
        },
    }
    if owner_id:
        payload["notes"]["owner_id"] = owner_id
    order = get_razorpay_client().order.create(data=payload)
    logger.info("Created Razorpay order %s for guild %s plan %s", order.get("id"), guild_id, plan_tier)
    return order


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    if not settings.razorpay_key_secret:
        raise RuntimeError("RAZORPAY_KEY_SECRET is required for payment verification.")
    body = f"{order_id}|{payment_id}".encode("utf-8")
    digest = hmac.new(settings.razorpay_key_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)
