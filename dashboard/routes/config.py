from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from dashboard.auth import get_current_user, is_guild_admin
from database.queries.guild_queries import get_guild_config, update_guild_config, upsert_guild

router = APIRouter(tags=["config"])


def _find_user_guild(user: dict[str, Any], guild_id: str) -> dict[str, Any] | None:
    return next((guild for guild in user["guilds"] if guild["id"] == guild_id and is_guild_admin(guild)), None)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_index(request: Request, user: dict[str, Any] = Depends(get_current_user)) -> HTMLResponse:
    admin_guilds = [guild for guild in user["guilds"] if is_guild_admin(guild)]
    configs = []
    for guild in admin_guilds:
        config = await upsert_guild(guild["id"], guild["name"])
        configs.append({"guild": guild, "config": config})
    return request.app.state.templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "items": configs, "user": user},
    )


@router.get("/dashboard/{guild_id}/config", response_class=HTMLResponse)
async def guild_config_page(request: Request, guild_id: str, user: dict[str, Any] = Depends(get_current_user)) -> HTMLResponse:
    guild = _find_user_guild(user, guild_id)
    if guild is None:
        return RedirectResponse("/dashboard", status_code=302)
    config = await get_guild_config(guild_id, guild["name"])
    return request.app.state.templates.TemplateResponse(
        "guild_config.html",
        {"request": request, "guild": guild, "config": config, "user": user},
    )


@router.post("/dashboard/{guild_id}/config")
async def guild_config_save(
    request: Request,
    guild_id: str,
    prefix: str = Form(...),
    allowed_channels: str = Form(""),
    max_purge: int = Form(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> RedirectResponse:
    guild = _find_user_guild(user, guild_id)
    if guild is None:
        return RedirectResponse("/dashboard", status_code=302)
    await update_guild_config(
        guild_id,
        {
            "prefix": prefix.strip(),
            "allowed_channels": [value.strip() for value in allowed_channels.split(",") if value.strip()],
            "max_purge": int(max_purge),
        },
    )
    return RedirectResponse(f"/dashboard/{guild_id}/config", status_code=302)
