"""
bot.py — Discord AI Bot (Main Entry Point)
NVIDIA NIM API + Discord.py
"""

import discord
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from ai_engine import get_ai_response
from actions import execute_action

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("moloj")

PREFIX = "moloj"

# ─── Bot Setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)

# Per-channel conversation history { channel_id: [messages] }
history: dict[str, list] = {}
MAX_HISTORY = 20


# ─── Help Embed ────────────────────────────────────────────────────────────────
def build_help_embed() -> discord.Embed:
    """Build a rich embed panel showing all available commands."""
    embed = discord.Embed(
        title="✨ Moloj — Command Panel",
        description=(
            f"Hey there! I'm **Moloj**, your AI-powered server assistant.\n"
            f"Use the prefix **`{PREFIX}`** or **@mention** me to get started.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=0x5865F2  # Discord blurple
    )

    embed.add_field(
        name="💬  General",
        value=(
            f"**`{PREFIX} <message>`** — Chat with me\n"
            f"**`{PREFIX} help`** — Show this panel\n"
        ),
        inline=False
    )

    embed.add_field(
        name="🔨  Moderation  *(Admin/Mod only)*",
        value=(
            f"**`{PREFIX} kick @user <reason>`**\n"
            f"**`{PREFIX} ban @user <reason>`**\n"
            f"**`{PREFIX} mute @user <duration>`**\n"
        ),
        inline=False
    )

    embed.add_field(
        name="🎭  Roles  *(Admin/Mod only)*",
        value=(
            f"**`{PREFIX} give @user <role>`**\n"
            f"**`{PREFIX} remove role @user <role>`**\n"
        ),
        inline=False
    )

    embed.add_field(
        name="📢  Channels  *(Admin/Mod only)*",
        value=(
            f"**`{PREFIX} create channel <name>`**\n"
            f"**`{PREFIX} announce <#channel> <message>`**\n"
        ),
        inline=False
    )

    embed.add_field(
        name="👥  Utility",
        value=(
            f"**`{PREFIX} list members`** — Show online members\n"
            f"**`{PREFIX} dm @user <message>`** — DM a member\n"
        ),
        inline=False
    )

    embed.set_footer(text=f"Prefix: {PREFIX} • Powered by NVIDIA NIM AI")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


# ─── Helper: Build User Context Header ────────────────────────────────────────
def build_context_header(message: discord.Message) -> str:
    """Inject metadata so AI knows who is talking and what permissions they have."""
    author = message.author
    
    # Check for Super User
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
        role_tag = "Member"  # DM fallback

    channel_name = getattr(message.channel, "name", "DM")
    return f"[User: {author.display_name} | ID: {author.id} | Role: {role_tag} | Channel: #{channel_name}]"


# ─── Events ───────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    logger.info(f"✅ Moloj is online as {bot.user}")
    logger.info(f"   Connected to {len(bot.guilds)} server(s)")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"the server | {PREFIX}"
        )
    )


@bot.event
async def on_member_join(member):
    if member.guild.system_channel:
        try:
            await member.guild.system_channel.send(f"👋 Welcome to the server, {member.mention}! Type `{PREFIX} help` to see what I can do.")
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    # Respond on: @mention, prefix, or DM
    is_dm      = isinstance(message.channel, discord.DMChannel)
    is_mention = bot.user in message.mentions
    is_prefix  = message.content.lower().startswith(PREFIX)

    if not (is_dm or is_mention or is_prefix):
        return

    # Strip trigger prefix from content
    content = message.content
    if is_mention:
        content = content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
    elif is_prefix:
        content = content[len(PREFIX):].strip()

    # Show help panel if empty or "help"
    if not content or content.lower() == "help":
        await message.reply(embed=build_help_embed())
        return

    # Build full message = context header + user message
    header           = build_context_header(message)
    full_user_message = f"{header}\n\n{content}"

    channel_id = str(message.channel.id)
    if channel_id not in history:
        if len(history) >= 100:
            history.pop(next(iter(history)))
        history[channel_id] = []
    else:
        history[channel_id] = history.pop(channel_id)

    history[channel_id].append({"role": "user", "content": full_user_message})

    # Keep last MAX_HISTORY turns
    if len(history[channel_id]) > MAX_HISTORY:
        history[channel_id] = history[channel_id][-MAX_HISTORY:]

    async with message.channel.typing():
        try:
            # ── 1. Ask AI ────────────────────────────────────────────────────
            ai_result = get_ai_response(history[channel_id])
            reply_parts = []

            # ── 2. Run any tool calls ─────────────────────────────────────────
            if ai_result["tool_calls"]:
                guild = message.guild
                for tc in ai_result["tool_calls"]:
                    if guild:
                        result = await execute_action(tc["name"], tc["arguments"], guild)
                    else:
                        result = "❌ Server actions unavailable in DMs."
                    reply_parts.append(result)

                    # Feed result back to history so AI knows what happened
                    history[channel_id].append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result
                    })

            # ── 3. Add text reply ─────────────────────────────────────────────
            if ai_result["text"]:
                reply_parts.append(ai_result["text"])

            final_reply = "\n\n".join(reply_parts) if reply_parts else "✅ Done."

            # ── 4. Send (handle 2000 char Discord limit) ──────────────────────
            if len(final_reply) > 2000:
                chunks = [final_reply[i:i+1990] for i in range(0, len(final_reply), 1990)]
                for i, chunk in enumerate(chunks):
                    await message.reply(chunk) if i == 0 else await message.channel.send(chunk)
            else:
                await message.reply(final_reply)

            history[channel_id].append({"role": "assistant", "content": final_reply})

        except Exception as e:
            logger.error(f"Error during message processing: {e}", exc_info=True)
            await message.reply(f"⚠️ Error: `{str(e)}`")


token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    logger.error("DISCORD_BOT_TOKEN is not set in environment variables.")
    exit(1)
bot.run(token)
