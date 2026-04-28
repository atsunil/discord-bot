from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class LicenseModel:
    license_key: str
    plan_tier: str
    razorpay_order_id: str
    guild_id: str | None = None
    activated_at: datetime | None = None
    expires_at: datetime | None = None
    razorpay_payment_id: str | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_document(self) -> dict[str, object]:
        return {
            "license_key": self.license_key,
            "plan_tier": self.plan_tier,
            "guild_id": self.guild_id,
            "activated_at": self.activated_at,
            "expires_at": self.expires_at,
            "razorpay_order_id": self.razorpay_order_id,
            "razorpay_payment_id": self.razorpay_payment_id,
            "is_active": self.is_active,
            "created_at": self.created_at,
        }
