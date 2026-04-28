from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from dashboard import auth
from dashboard.routes import billing, config, home, stats
from payments import webhook
from shared.config import settings

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Moloj Dashboard")
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.dashboard_origin()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.state.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.include_router(auth.router)
app.include_router(home.router)
app.include_router(config.router)
app.include_router(stats.router)
app.include_router(billing.router)
app.include_router(webhook.router)
