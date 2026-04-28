"""
status.py — /status Slash Command
Provides bot health, uptime, memory usage, and API ping.
"""

import discord
from discord import app_commands
import psutil
import time
import logging

logger = logging.getLogger(__name__)

START_TIME = time.time()
message_count = 0  # Increment this in bot.py on each message


def setup_status(bot):
    """Register the /status slash command."""

    @bot.tree.command(
        name="status", description="Show bot health and stats"
    )
    async def status_slash(interaction: discord.Interaction):
        await interaction.response.defer()

        # ── Uptime ──────────────────────────────────────────────────────
        uptime_secs = int(time.time() - START_TIME)
        hours, rem = divmod(uptime_secs, 3600)
        mins, secs = divmod(rem, 60)
        uptime_str = f"{hours}h {mins}m {secs}s"

        # ── Memory ──────────────────────────────────────────────────────
        process = psutil.Process()
        mem_mb = process.memory_info().rss / 1024 / 1024

        # ── WebSocket latency ───────────────────────────────────────────
        latency_ms = round(bot.latency * 1000, 2)

        # ── NIM API test ping ───────────────────────────────────────────
        nim_status = "✅ Online"
        try:
            from ai_engine import client, get_model

            client.chat.completions.create(
                model=get_model("default"),
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
        except Exception as e:
            nim_status = f"❌ Offline ({e})"
            logger.warning(f"NIM API ping failed: {e}")

        # ── Build embed ─────────────────────────────────────────────────
        embed = discord.Embed(
            title="🤖 Moloj Status",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="⏱️ Uptime", value=uptime_str, inline=True
        )
        embed.add_field(
            name="📡 WS Latency", value=f"{latency_ms}ms", inline=True
        )
        embed.add_field(
            name="🧠 Memory", value=f"{mem_mb:.1f} MB", inline=True
        )
        embed.add_field(
            name="💬 Messages", value=str(message_count), inline=True
        )
        embed.add_field(
            name="🔗 NIM API", value=nim_status, inline=True
        )
        embed.add_field(
            name="🏠 Servers",
            value=str(len(bot.guilds)),
            inline=True,
        )

        await interaction.followup.send(embed=embed)
        logger.info(f"/status requested by {interaction.user}")
