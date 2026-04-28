from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from payments.plans import PLANS
from shared.config import settings

router = APIRouter(tags=["home"])


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    invite_url = (
        f"https://discord.com/oauth2/authorize?client_id={settings.discord_client_id or ''}"
        "&permissions=8&scope=bot%20applications.commands"
    )
    return request.app.state.templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "plans": PLANS,
            "invite_url": invite_url,
            "user": request.session.get("user"),
        },
    )
