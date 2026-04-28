# Moloj

Moloj is a sellable Discord bot stack built around `discord.py`, NVIDIA NIM, MongoDB Atlas, FastAPI, and Razorpay. This repository includes:

- A Discord bot with natural-language moderation, slash commands, welcome cards, reaction roles, voice tracking, translation, custom commands, image generation, and premium persona/memory hooks
- A FastAPI + Jinja2 dashboard with Discord OAuth2 login, guild configuration, usage stats, and billing pages
- Razorpay order helpers and webhook handling for plan activation
- MongoDB-backed guild configuration, message history, licensing, and feature data

## Stack

- Python 3.11
- `discord.py` 2.x
- NVIDIA NIM via the OpenAI-compatible Python client
- MongoDB Atlas + Motor
- FastAPI + Jinja2
- Razorpay
- Render deployment

## Quick start

1. Create a Python 3.11 virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in your Discord, NVIDIA, MongoDB, and Razorpay credentials.
4. Start the dashboard:

   ```bash
   uvicorn dashboard.main:app --reload
   ```

5. Start the bot:

   ```bash
   python bot/bot.py
   ```

## Layout

- [`bot`](./bot): Discord runtime, cogs, AI engine, permissions, and tool execution
- [`dashboard`](./dashboard): FastAPI dashboard, OAuth, billing, templates, and static assets
- [`database`](./database): MongoDB client, models, and queries
- [`payments`](./payments): Razorpay plan and webhook helpers
- [`shared`](./shared): environment parsing and shared constants
- [`tests`](./tests): starter pytest coverage for core logic

## Notes

- The bot expects MongoDB indexes to be created on startup.
- Premium-only features are plan-gated through the license manager and guild config.
- The dashboard billing page includes both Razorpay order creation and a manual verification form for first-pass setup.
- Render deployment settings are included in [`render.yaml`](./render.yaml).
