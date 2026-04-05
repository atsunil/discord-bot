# 🤖 Moloj — Discord AI Bot

> An intelligent Discord server assistant and moderator powered by **NVIDIA NIM API** with interactive UI components, persistent SQLite history, multi-agent system, and slash commands.

---

## 📖 Overview

**Moloj** is an AI-powered Discord bot that combines natural language conversation with full server management capabilities. It uses the NVIDIA NIM API (GPT-OSS-120B model) for intelligent responses and OpenAI-compatible function calling (tool use) to execute Discord actions like moderation, role management, and announcements — all driven by natural language commands.

---

## 🏗️ Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                       Discord Server                              │
│                                                                   │
│   User Message / @mention / prefix / Slash Command                │
│           │                                                       │
│           ▼                                                       │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐        │
│   │   bot.py      │───▶│ ai_engine.py │───▶│ NVIDIA NIM   │        │
│   │  (Discord     │    │ (System      │    │ API          │        │
│   │   Client +    │    │  Prompt +    │    │ (GPT-OSS-    │        │
│   │   Slash Cmds) │◀───│  Tool Defs + │◀───│  120B)       │        │
│   └──────┬────────┘    │  Streaming)  │    └──────────────┘        │
│          │             └──────────────┘                            │
│          ├──▶ actions.py        (Execute Discord API calls)        │
│          ├──▶ interactive.py    (Buttons, Polls, Selects)          │
│          ├──▶ database.py       (SQLite: history + config)         │
│          ├──▶ slash_commands.py  (/kick /ban /purge /config)       │
│          ├──▶ status.py         (/status health check)             │
│          └──▶ agents/           (Research, Code, Orchestrator)     │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

| File / Directory               | Description                                                        |
|---------------------------------|--------------------------------------------------------------------|
| `bot.py`                        | **Main entry point.** Discord client, event handlers, message routing, SQLite history, per-server config, slash commands, graceful shutdown. |
| `ai_engine.py`                  | NVIDIA NIM API integration. System prompt, tool definitions, AI response parsing (non-streaming with tool calls + streaming for chat). |
| `actions.py`                    | Action executor. Maps AI tool calls to Discord API operations with input sanitization (`@everyone`/`@here` protection). |
| `interactive.py`                | Interactive UI components. Parses `[BUTTONS]`, `[CONFIRM]`, `[POLL]`, `[SELECT]` blocks from AI responses. |
| `database.py`                   | SQLite layer via aiosqlite. Persistent conversation history + per-server configuration. |
| `config.py`                     | Centralized bot configuration defaults (prefix, limits, model names). |
| `slash_commands.py`             | Slash commands: `/kick`, `/ban`, `/purge`, `/config`, `/clear_history`. |
| `status.py`                     | `/status` command — uptime, memory, latency, API health, message count. |
| `agents/`                       | Multi-agent system (Researcher, Coder, Orchestrator). |
| `agents/base_agent.py`          | Abstract base class for all agents. |
| `agents/researcher.py`          | Web research agent (DuckDuckGo + httpx + BeautifulSoup). |
| `agents/coder.py`               | Code generation/explanation agent. |
| `agents/orchestrator.py`        | Routes tasks to the appropriate specialized agent. |
| `main.py`                       | **Legacy bot** (old prefix-based version). Not used. |
| `.env`                          | Environment variables (tokens, API keys). **Not committed.** |
| `.env.example`                  | Template showing required environment variables. |
| `requirements.txt`              | Python dependencies. |
| `Procfile`                      | Deployment config (Heroku/Railway). |
| `Dockerfile`                    | Docker container config with persistent DB volume. |
| `.dockerignore`                 | Files excluded from Docker builds. |
| `.github/workflows/lint.yml`    | GitHub Actions CI — linting with ruff on push/PR. |
| `.gitignore`                    | Git ignore rules. |

---

## ✨ Features

### 💬 AI Chat
- Natural language conversation powered by NVIDIA NIM API
- **Persistent conversation history** via SQLite (survives bot restarts)
- **Streaming responses** — tokens appear progressively in Discord
- Context-aware responses with user metadata (name, role, channel)
- Responds to: configurable prefix (default `moloj`), `@mention`, or DMs

### 🔨 Moderation (Admin/Mod only)
- **Kick** — Remove a member (`/kick` slash command or natural language)
- **Ban / Unban** — Permanently ban or unban members (`/ban`)
- **Timeout / Mute** — Temporarily mute members (1 min to 28 days)
- **Purge** — Bulk delete messages (`/purge`)

### 🎭 Role Management (Admin/Mod only)
- **Assign Role** — Add a role to a member
- **Remove Role** — Remove a role from a member

### 📢 Channel & Communication
- **Create Channel** — Create text or voice channels
- **Send Announcement** — Post to specific channels (with `@everyone`/`@here` sanitization)
- **Send DM** — Direct message any server member
- **Spam User** — Loop messages to a user (Admin only)
- **Send Stickers** — Send random emoji stickers via DM

### ℹ️ Utility
- **List Members** — Show online members with User IDs
- **Server Info** — Display server statistics
- **Help Panel** — Rich embed with all commands

### 🎛️ Interactive UI
- **Buttons** — Choices/options (2–5 options)
- **Confirm/Cancel** — Before destructive actions
- **Polls** — Vote buttons with live count tracking
- **Select Menus** — Dropdown for 6+ options

### ⚡ Slash Commands
| Command            | Description                           | Permission       |
|--------------------|---------------------------------------|------------------|
| `/kick`            | Kick a member                        | Kick Members     |
| `/ban`             | Ban a member                         | Ban Members      |
| `/purge`           | Delete messages                      | Manage Messages  |
| `/config`          | Server bot settings                  | Administrator    |
| `/clear_history`   | Clear AI memory for channel          | Manage Messages  |
| `/status`          | Bot health and stats                 | Everyone         |

### 🗄️ Per-Server Configuration
Each server can customize via `/config`:
- **Prefix** — Change the bot trigger word
- **Allowed Channels** — Restrict bot to specific channels
- **Max Purge** — Limit bulk message deletion

### 🤖 Multi-Agent System
- **Researcher** — Web search via DuckDuckGo + page scraping
- **Coder** — Code generation/explanation/debugging
- **Orchestrator** — Automatic routing to the right agent

### 🔐 Security
- **Input Sanitization** — `@everyone`/`@here` stripped from non-admin messages
- **Role-Based Access** — Admin, Mod, Member tiers
- **Super Users** — Configurable via `SUPER_USERS` env variable

---

## ⚙️ Setup & Configuration

### Prerequisites
- Python 3.10+
- A Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))
- An NVIDIA NIM API Key ([build.nvidia.com](https://build.nvidia.com))

### Installation

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd discord

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env
# Edit .env with your actual tokens
```

### Environment Variables

| Variable            | Description                                | Required |
|---------------------|--------------------------------------------|----------|
| `DISCORD_BOT_TOKEN` | Discord bot token from Developer Portal    | ✅       |
| `NVIDIA_API_KEY`    | NVIDIA NIM API key from build.nvidia.com   | ✅       |
| `SUPER_USERS`       | Comma-separated usernames or IDs           | Optional |
| `DB_PATH`           | SQLite database path (default: `moloj.db`) | Optional |

### Running the Bot

```bash
python bot.py
```

---

## 🐳 Docker Deployment

```bash
# Build
docker build -t moloj-bot .

# Run (with persistent database)
docker run -d \
  --name moloj \
  --env-file .env \
  -v moloj-data:/app/data \
  moloj-bot
```

---

## 🚀 Platform Deployment

### Heroku / Railway
The `Procfile` runs: `worker: python bot.py`

### Required Bot Permissions
**Privileged Intents** (Discord Developer Portal → Bot section):
- ✅ Message Content Intent
- ✅ Server Members Intent

**Bot Permissions**: Send Messages, Manage Messages, Kick Members, Ban Members, Moderate Members, Manage Channels, Manage Roles

---

## 🧩 Dependencies

| Package            | Version  | Purpose                              |
|--------------------|----------|--------------------------------------|
| `discord.py`       | ≥ 2.3.0  | Discord API wrapper                  |
| `openai`           | ≥ 1.30.0 | OpenAI-compatible client for NVIDIA  |
| `python-dotenv`    | ≥ 1.0.0  | Load .env variables                  |
| `aiosqlite`        | ≥ 0.20.0 | Async SQLite for history/config      |
| `duckduckgo-search`| ≥ 6.0.0  | Web search (research agent)          |
| `httpx`            | ≥ 0.27.0 | Async HTTP client (research agent)   |
| `beautifulsoup4`   | ≥ 4.12.0 | HTML parsing (research agent)        |
| `psutil`           | ≥ 5.9.0  | System metrics (/status command)     |
| `ruff`             | ≥ 0.4.0  | Python linter (CI)                   |

---

## 📌 Notes

- Conversation history is **persistent** — stored in SQLite and survives bot restarts.
- Old history (>7 days) is automatically pruned on startup.
- The AI model can be changed in `ai_engine.py` (`MODELS` dict).
- Streaming is available for pure chat; tool-calling flows use non-streaming.
- `main.py` is the **legacy bot** — not used by the current system.
- Logs go to both console and `moloj.log` file.
