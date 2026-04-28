from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from shared.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

DISCORD_API = "https://discord.com/api/v10"
ADMIN_PERMISSION = 0x8


def build_discord_oauth_url() -> str:
    params = {
        "client_id": settings.discord_client_id,
        "redirect_uri": f"{settings.dashboard_url.rstrip('/')}/auth/callback",
        "response_type": "code",
        "scope": "identify guilds",
        "prompt": "consent",
    }
    return f"https://discord.com/oauth2/authorize?{urlencode(params)}"


def is_guild_admin(guild: dict[str, Any]) -> bool:
    permissions = int(guild.get("permissions", 0))
    return (permissions & ADMIN_PERMISSION) == ADMIN_PERMISSION


@router.get("/login")
async def login() -> RedirectResponse:
    return RedirectResponse(build_discord_oauth_url())


@router.get("/callback")
async def callback(request: Request, code: str) -> RedirectResponse:
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_response = await client.post(
            f"{DISCORD_API}/oauth2/token",
            data={
                "client_id": settings.discord_client_id,
                "client_secret": settings.discord_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{settings.dashboard_url.rstrip('/')}/auth/callback",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        access_token = token_data["access_token"]

        headers = {"Authorization": f"Bearer {access_token}"}
        user_response = await client.get(f"{DISCORD_API}/users/@me", headers=headers)
        guilds_response = await client.get(f"{DISCORD_API}/users/@me/guilds", headers=headers)
        user_response.raise_for_status()
        guilds_response.raise_for_status()
        user = user_response.json()
        guilds = guilds_response.json()

    request.session["user"] = {
        "user_id": user["id"],
        "username": user["username"],
        "avatar": user.get("avatar"),
        "guilds": guilds,
    }
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/", status_code=302)


async def get_current_user(request: Request) -> dict[str, Any]:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    return user
