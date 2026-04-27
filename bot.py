"""
bot.py — Discord AI Bot (Main Entry Point)
NVIDIA NIM API + Discord.py with Interactive Button/Select/Poll UI
Supabase-backed conversation history + per-server configuration
"""

import discord
from discord import app_commands
import os
import signal
import asyncio
import logging
import ssl
import aiohttp
from aiohttp import web
from datetime import datetime, timezone
from dotenv import load_dotenv

from ai_engine import get_ai_response
from actions import execute_action
from interactive import parse_interactive_blocks
from database import (
    init_db, save_message, get_history,
    clear_history, prune_old_history,
    get_server_config, update_server_config,
)
from slash_commands import setup_slash_commands
from status import setup_status
import status as status_module

load_dotenv()

# ─── Logging Setup ─────────────────────────────────────────────────────────────
log_handlers = [logging.StreamHandler()]
try:
    log_handlers.append(logging.FileHandler("moloj.log", encoding="utf-8"))
except OSError:
    pass  # Read-only filesystem (Docker/HuggingFace)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=log_handlers,
)
logger = logging.getLogger(__name__)

DEFAULT_PREFIX = "moloj"
MAX_HISTORY = 20


# ─── Bot Setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)
bot.tree = app_commands.CommandTree(bot)

# Register slash commands & status
setup_slash_commands(bot)
setup_status(bot)


# ─── UptimeRobot Keep-Alive Server ────────────────────────────────────────────
async def start_ping_server():
    """Starts a minimal HTTP server so UptimeRobot can ping the bot."""
    app = web.Application()
    
    async def hello(request):
        return web.Response(text="Moloj is alive and running!")
        
    app.add_routes([web.get('/', hello)])
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    try:
        await site.start()
        logger.info(f"Ping server started on port {port} for UptimeRobot")
    except Exception as e:
        logger.error(f"Could not start ping server (port in use?): {e}")


# ─── Interactive Callback ─────────────────────────────────────────────────────
async def on_interactive_selection(
    interaction: discord.Interaction,
    selected_text: str,
    channel_id: str,
):
    """Handle button/select clicks — feed the user's choice back to the AI."""

    author = interaction.user
    guild = interaction.guild
    guild_id = str(guild.id) if guild else "0"

    # Determine role tag
    super_users = [u.strip() for u in os.getenv("SUPER_USERS", "").split(",") if u.strip()]
    is_super_user = str(author.name) in super_users or str(author.id) in super_users

    if is_super_user:
        role_tag = "Admin"
    elif isinstance(author, discord.Member):
        if author.guild_permissions.administrator:
            role_tag = "Admin"
        elif any(r.name.lower() in ["mod", "moderator", "staff", "helper"] for r in author.roles):
            role_tag = "Mod"
        else:
            role_tag = "Member"
    else:
        role_tag = "Member"

    channel_name = getattr(interaction.channel, "name", "DM")
    header = f"[User: {author.display_name} | ID: {author.id} | Role: {role_tag} | Channel: #{channel_name}]"
    selection_msg = f"{header}\n\n[User clicked button: {selected_text}]"

    # Save to DB and get history
    await save_message(channel_id, guild_id, "user", selection_msg)
    history = await get_history(channel_id, limit=MAX_HISTORY)

    # Get AI response
    async with interaction.channel.typing():
        try:
            ai_result = get_ai_response(history)
            reply_parts = []

            if ai_result["tool_calls"]:
                is_admin = (
                    isinstance(author, discord.Member)
                    and author.guild_permissions.administrator
                ) or is_super_user
                for tc in ai_result["tool_calls"]:
                    if guild:
                        result = await execute_action(
                            tc["name"], tc["arguments"], guild, is_admin=is_admin, bot=bot
                        )
                    else:
                        result = "❌ Server actions unavailable in DMs."
                    reply_parts.append(result)

            if ai_result["text"]:
                reply_parts.append(ai_result["text"])

            final_reply = "\n\n".join(reply_parts) if reply_parts else "✅ Done."

            # Save assistant response to DB
            await save_message(channel_id, guild_id, "assistant", final_reply)

            # Parse for interactive blocks
            clean_text, view = parse_interactive_blocks(
                final_reply, on_interactive_selection, channel_id
            )

            send_kwargs = {}
            if view is not None:
                send_kwargs["view"] = view

            if len(clean_text) > 2000:
                chunks = [clean_text[i:i+1990] for i in range(0, len(clean_text), 1990)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await interaction.followup.send(chunk, **send_kwargs)
                    else:
                        await interaction.channel.send(chunk)
            else:
                await interaction.followup.send(clean_text, **send_kwargs)

        except Exception as e:
            logger.error(f"Error during button callback: {e}", exc_info=True)
            try:
                await interaction.followup.send(f"⚠️ Error: `{str(e)}`")
            except Exception:
                pass


# ─── Help Embed ────────────────────────────────────────────────────────────────
def build_help_embed(prefix: str = DEFAULT_PREFIX) -> discord.Embed:
    """Build a rich embed panel showing all available commands."""
    embed = discord.Embed(
        title="✨ Moloj — Command Panel",
        description=(
            f"Hey there! I'm **Moloj**, your AI-powered server assistant.\n"
            f"Use the prefix **`{prefix}`** or **@mention** me to get started.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=0x5865F2,
    )

    embed.add_field(
        name="💬  General",
        value=(
            f"**`{prefix} <message>`** — Chat with me\n"
            f"**`{prefix} help`** — Show this panel\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="🔨  Moderation  *(Admin/Mod only)*",
        value=(
            f"**`{prefix} kick @user <reason>`**\n"
            f"**`{prefix} ban @user <reason>`**\n"
            f"**`{prefix} mute @user <duration>`**\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="🎭  Roles  *(Admin/Mod only)*",
        value=(
            f"**`{prefix} give @user <role>`**\n"
            f"**`{prefix} remove role @user <role>`**\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="📢  Channels  *(Admin/Mod only)*",
        value=(
            f"**`{prefix} create channel <name>`**\n"
            f"**`{prefix} announce <#channel> <message>`**\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="👥  Utility",
        value=(
            f"**`{prefix} list members`** — Show online members\n"
            f"**`{prefix} dm @user <message>`** — DM a member\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="🎛️  Interactive",
        value=(
            "I automatically create **buttons** and **menus** when I give you choices!\n"
            "Just ask me a question or request a quiz/poll — no commands needed.\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="⚡  Slash Commands",
        value=(
            "**/kick** — Kick a member\n"
            "**/ban** — Ban a member\n"
            "**/purge** — Delete messages\n"
            "**/config** — Server settings\n"
            "**/status** — Bot health\n"
            "**/clear_history** — Reset AI memory\n"
        ),
        inline=False,
    )

    embed.set_footer(text=f"Prefix: {prefix} • Powered by NVIDIA NIM AI")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


# ─── Helper: Build User Context Header ────────────────────────────────────────
def build_context_header(message: discord.Message) -> str:
    """Inject metadata so AI knows who is talking and what permissions they have."""
    author = message.author

    super_users = [u.strip() for u in os.getenv("SUPER_USERS", "").split(",") if u.strip()]
    is_super_user = str(author.name) in super_users or str(author.id) in super_users

    if is_super_user:
        role_tag = "Admin"
    elif isinstance(author, discord.Member):
        if author.guild_permissions.administrator:
            role_tag = "Admin"
        elif any(r.name.lower() in ["mod", "moderator", "staff", "helper"] for r in author.roles):
            role_tag = "Mod"
        else:
            role_tag = "Member"
    else:
        role_tag = "Member"

    channel_name = getattr(message.channel, "name", "DM")
    return f"[User: {author.display_name} | ID: {author.id} | Role: {role_tag} | Channel: #{channel_name}]"


# ─── Events ───────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    # Start the HTTP ping server
    asyncio.create_task(start_ping_server())

    # Initialize database & prune old history
    await init_db()
    await prune_old_history(days=7)

    # Sync slash commands
    try:
        await bot.tree.sync()
        logger.info(f"Slash commands synced for {len(bot.guilds)} server(s)")
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}", exc_info=True)

    logger.info(f"✅ Moloj is online as {bot.user}")
    logger.info(f"   Connected to {len(bot.guilds)} server(s)")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"the server | {DEFAULT_PREFIX}",
        )
    )


@bot.event
async def on_member_join(member):
    if member.guild.system_channel:
        try:
            config = await get_server_config(str(member.guild.id))
            prefix = config.get("prefix", DEFAULT_PREFIX)
            await member.guild.system_channel.send(
                f"👋 Welcome to the server, {member.mention}! "
                f"Type `{prefix} help` to see what I can do."
            )
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    # Increment message counter for /status
    status_module.message_count += 1

    # ── Load per-server config ─────────────────────────────────────────────
    is_dm = isinstance(message.channel, discord.DMChannel)

    if is_dm:
        prefix = DEFAULT_PREFIX
        guild_id = "0"
    else:
        guild_id = str(message.guild.id)
        config = await get_server_config(guild_id)
        prefix = config.get("prefix", DEFAULT_PREFIX)

        # Check allowed channels (if configured, only respond in those)
        allowed = config.get("allowed_channels", "")
        if allowed:
            allowed_ids = [c.strip() for c in allowed.split(",") if c.strip()]
            if str(message.channel.id) not in allowed_ids:
                return

    # ── Trigger detection ──────────────────────────────────────────────────
    is_mention = bot.user in message.mentions
    is_prefix = message.content.lower().startswith(prefix)

    if not (is_dm or is_mention or is_prefix):
        return

    # Strip trigger prefix from content
    content = message.content
    if is_mention:
        content = content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
    elif is_prefix:
        content = content[len(prefix):].strip()

    # Show help panel if empty or "help"
    if not content or content.lower() == "help":
        await message.reply(embed=build_help_embed(prefix))
        return

    # ── Build user message with context ────────────────────────────────────
    header = build_context_header(message)
    full_user_message = f"{header}\n\n{content}"
    channel_id = str(message.channel.id)

    # Save user message to database
    await save_message(channel_id, guild_id, "user", full_user_message)

    # Get conversation history from database
    history = await get_history(channel_id, limit=MAX_HISTORY)

    # ── Process with AI ────────────────────────────────────────────────────
    async with message.channel.typing():
        try:
            # ── 1. Ask AI (non-streaming for tool call support) ────────────
            ai_result = get_ai_response(history)
            reply_parts = []

            # ── 2. Run any tool calls ──────────────────────────────────────
            if ai_result["tool_calls"]:
                guild = message.guild
                # Determine if caller is admin for sanitization
                is_admin = False
                if guild:
                    super_users = [u.strip() for u in os.getenv("SUPER_USERS", "").split(",") if u.strip()]
                    is_admin = (
                        isinstance(message.author, discord.Member)
                        and message.author.guild_permissions.administrator
                    ) or (
                        str(message.author.name) in super_users
                        or str(message.author.id) in super_users
                    )

                for tc in ai_result["tool_calls"]:
                    if guild:
                        result = await execute_action(
                            tc["name"], tc["arguments"], guild, is_admin=is_admin, bot=bot
                        )
                    else:
                        result = "❌ Server actions unavailable in DMs."
                    reply_parts.append(result)

            # ── 3. Add text reply ──────────────────────────────────────────
            if ai_result["text"]:
                reply_parts.append(ai_result["text"])

            final_reply = "\n\n".join(reply_parts) if reply_parts else "✅ Done."

            # ── 4. Save assistant response to database ─────────────────────
            await save_message(channel_id, guild_id, "assistant", final_reply)

            # ── 5. Parse for interactive blocks (buttons, polls, etc.) ─────
            clean_text, view = parse_interactive_blocks(
                final_reply, on_interactive_selection, channel_id
            )

            # ── 6. Send (handle 2000 char Discord limit) ──────────────────
            send_kwargs = {}
            if view is not None:
                send_kwargs["view"] = view

            if len(clean_text) > 2000:
                chunks = [clean_text[i:i+1990] for i in range(0, len(clean_text), 1990)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await message.reply(chunk, **send_kwargs)
                    else:
                        await message.channel.send(chunk)
            else:
                await message.reply(clean_text, **send_kwargs)

        except Exception as e:
            logger.error(f"Error during message processing: {e}", exc_info=True)
            await message.reply(f"⚠️ Error: `{str(e)}`")


# ─── Graceful Shutdown ─────────────────────────────────────────────────────────
async def shutdown():
    """Gracefully close the bot."""
    logger.info("Shutting down Moloj gracefully...")
    await bot.close()


def handle_sigterm(*args):
    """Handle SIGTERM for graceful shutdown (e.g. Docker, systemd)."""
    logger.info("SIGTERM received")
    asyncio.create_task(shutdown())


signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)


# ─── Start Bot ─────────────────────────────────────────────────────────────────
async def run_bot():
    """Run the bot with automatic reconnect on network failures."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN is not set in environment variables.")
        exit(1)

    # Start the ping server once, before the connection loop
    await start_ping_server()

    retry_delay = 10  # seconds
    max_delay = 120   # cap backoff at 2 minutes

    # Network errors that should trigger a retry (not a crash)
    NETWORK_ERRORS = (
        aiohttp.ClientConnectorError,
        aiohttp.ServerDisconnectedError,
        aiohttp.ClientOSError,
        discord.errors.ConnectionClosed,
        discord.errors.GatewayNotFound,
    )

    while True:
        try:
            logger.info(f"Connecting to Discord... (retry_delay={retry_delay}s)")
            await bot.start(token)
        except discord.LoginFailure:
            logger.error("Invalid DISCORD_BOT_TOKEN. Please check your .env file.")
            exit(1)
        except NETWORK_ERRORS as e:
            logger.warning(
                f"Network error — discord.com unreachable: {e}\n"
                f"Retrying in {retry_delay}s..."
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)
            # Reset the bot client for a clean reconnect
            if not bot.is_closed():
                await bot.close()
            logger.info("Reconnecting...")
        except Exception as e:
            error_msg = str(e)
            # aiohttp raises plain Exception for some SSL/host errors
            if "Cannot connect to host" in error_msg or "ssl" in error_msg.lower():
                logger.warning(
                    f"Network/SSL error — discord.com unreachable: {e}\n"
                    f"Retrying in {retry_delay}s..."
                )
            else:
                logger.error(f"Unexpected error running bot: {e}", exc_info=True)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)
            if not bot.is_closed():
                await bot.close()
            logger.info("Reconnecting...")
        else:
            # Clean exit (e.g. SIGTERM)
            break


asyncio.run(run_bot())
