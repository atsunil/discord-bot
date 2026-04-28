from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from dashboard.auth import get_current_user, is_guild_admin
from database.queries.history_queries import get_history_stats

router = APIRouter(tags=["stats"])


def _find_user_guild(user: dict[str, Any], guild_id: str) -> dict[str, Any] | None:
    return next((guild for guild in user["guilds"] if guild["id"] == guild_id and is_guild_admin(guild)), None)


@router.get("/dashboard/{guild_id}/stats", response_class=HTMLResponse)
async def guild_stats(request: Request, guild_id: str, user: dict[str, Any] = Depends(get_current_user)) -> HTMLResponse:
    guild = _find_user_guild(user, guild_id)
    if guild is None:
        return RedirectResponse("/dashboard", status_code=302)
    stats = await get_history_stats(guild_id)
    return request.app.state.templates.TemplateResponse(
        "stats.html",
        {"request": request, "guild": guild, "stats": stats, "user": user},
    )
