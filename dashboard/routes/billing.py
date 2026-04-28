from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from dashboard.auth import get_current_user, is_guild_admin
from database.queries.guild_queries import get_guild_config, update_guild_config
from database.queries.license_queries import create_license
from payments.plans import PLANS
from payments.razorpay_client import create_order, verify_payment_signature
from shared.config import settings

router = APIRouter(tags=["billing"])


def _find_user_guild(user: dict[str, Any], guild_id: str) -> dict[str, Any] | None:
    return next((guild for guild in user["guilds"] if guild["id"] == guild_id and is_guild_admin(guild)), None)


@router.get("/dashboard/{guild_id}/billing", response_class=HTMLResponse)
async def billing_page(request: Request, guild_id: str, user: dict[str, Any] = Depends(get_current_user)) -> HTMLResponse:
    guild = _find_user_guild(user, guild_id)
    if guild is None:
        return RedirectResponse("/dashboard", status_code=302)
    config = await get_guild_config(guild_id, guild["name"])
    return request.app.state.templates.TemplateResponse(
        "billing.html",
        {
            "request": request,
            "guild": guild,
            "config": config,
            "plans": PLANS,
            "razorpay_key_id": settings.razorpay_key_id,
            "user": user,
        },
    )


@router.post("/dashboard/{guild_id}/create-order")
async def billing_create_order(guild_id: str, plan_tier: str = Form(...), user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    guild = _find_user_guild(user, guild_id)
    if guild is None:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)
    order = create_order(plan_tier=plan_tier, guild_id=guild_id, owner_id=user["user_id"])
    return JSONResponse({"order": order, "key_id": settings.razorpay_key_id})


@router.post("/dashboard/{guild_id}/verify-payment")
async def billing_verify_payment(
    guild_id: str,
    order_id: str = Form(...),
    payment_id: str = Form(...),
    signature: str = Form(...),
    plan_tier: str = Form(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> RedirectResponse:
    guild = _find_user_guild(user, guild_id)
    if guild is None:
        return RedirectResponse("/dashboard", status_code=302)
    if not verify_payment_signature(order_id, payment_id, signature):
        return RedirectResponse(f"/dashboard/{guild_id}/billing?status=failed", status_code=302)

    license_doc = await create_license(
        plan_tier=plan_tier,
        razorpay_order_id=order_id,
        guild_id=guild_id,
        payment_id=payment_id,
    )
    await update_guild_config(guild_id, {"plan_tier": plan_tier, "license_key": license_doc["license_key"]})
    return RedirectResponse(f"/dashboard/{guild_id}/billing?status=success", status_code=302)
