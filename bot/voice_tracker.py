from __future__ import annotations

from datetime import UTC, datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from database.client import get_db
from database.queries.guild_queries import get_guild_config


def format_duration(total_seconds: int) -> str:
    hours, remainder = divmod(max(total_seconds, 0), 3600)
    minutes, _ = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


class VoiceTrackerCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.collection = get_db()["voice_logs"]
        self.running_sessions: dict[tuple[int, int], dict[str, object]] = {}

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        key = (member.guild.id, member.id)
        if before.channel is None and after.channel is not None:
            self.running_sessions[key] = {
                "guild_id": str(member.guild.id),
                "user_id": str(member.id),
                "username": member.display_name,
                "channel_id": str(after.channel.id),
                "channel_name": after.channel.name,
                "join_time": datetime.now(UTC),
            }
            return

        if before.channel is not None and after.channel is None:
            await self._close_session(key)
            return

        if before.channel and after.channel and before.channel.id != after.channel.id:
            await self._close_session(key)
            self.running_sessions[key] = {
                "guild_id": str(member.guild.id),
                "user_id": str(member.id),
                "username": member.display_name,
                "channel_id": str(after.channel.id),
                "channel_name": after.channel.name,
                "join_time": datetime.now(UTC),
            }

    @app_commands.command(name="voicestats", description="Show total voice time for a member.")
    async def voice_stats(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        stats = await self._fetch_stats(str(interaction.guild.id), str(user.id))
        embed = discord.Embed(title=f"Voice stats for {user.display_name}", color=discord.Color.blurple())
        embed.add_field(name="This week", value=format_duration(stats["week"]))
        embed.add_field(name="This month", value=format_duration(stats["month"]))
        embed.add_field(name="All time", value=format_duration(stats["all_time"]))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="myvoicetime", description="Show your own voice stats.")
    async def my_voice_time(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        stats = await self._fetch_stats(str(interaction.guild.id), str(interaction.user.id))
        await interaction.response.send_message(
            f"This week: {format_duration(stats['week'])} | "
            f"This month: {format_duration(stats['month'])} | "
            f"All time: {format_duration(stats['all_time'])}"
        )

    @app_commands.command(name="voiceleaderboard", description="Show the top 10 voice-active members in this server.")
    async def voice_leaderboard(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        if config.get("plan_tier") != "premium":
            await interaction.response.send_message("Voice leaderboard is a Premium feature.", ephemeral=True)
            return
        pipeline = [
            {"$match": {"guild_id": str(interaction.guild.id)}},
            {"$group": {"_id": "$user_id", "username": {"$last": "$username"}, "seconds": {"$sum": "$duration_seconds"}}},
            {"$sort": {"seconds": -1}},
            {"$limit": 10},
        ]
        rows = await self.collection.aggregate(pipeline).to_list(length=10)
        if not rows:
            await interaction.response.send_message("No voice activity has been recorded yet.", ephemeral=True)
            return
        description = "\n".join(
            f"**{index}.** {row['username']} — {format_duration(int(row['seconds']))}"
            for index, row in enumerate(rows, start=1)
        )
        embed = discord.Embed(title="Voice Leaderboard", description=description, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)

    async def _close_session(self, key: tuple[int, int]) -> None:
        session = self.running_sessions.pop(key, None)
        if not session:
            return
        leave_time = datetime.now(UTC)
        join_time = session["join_time"]
        duration = int((leave_time - join_time).total_seconds())
        await self.collection.insert_one(
            {
                **session,
                "leave_time": leave_time,
                "duration_seconds": max(duration, 0),
            }
        )

    async def _fetch_stats(self, guild_id: str, user_id: str) -> dict[str, int]:
        now = datetime.now(UTC)
        monday = now - timedelta(
            days=now.weekday(),
            hours=now.hour,
            minutes=now.minute,
            seconds=now.second,
            microseconds=now.microsecond,
        )
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return {
            "week": await self._sum_duration(guild_id, user_id, monday),
            "month": await self._sum_duration(guild_id, user_id, month_start),
            "all_time": await self._sum_duration(guild_id, user_id, None),
        }

    async def _sum_duration(self, guild_id: str, user_id: str, start: datetime | None) -> int:
        query: dict[str, object] = {"guild_id": guild_id, "user_id": user_id}
        if start is not None:
            query["join_time"] = {"$gte": start}
        pipeline = [
            {"$match": query},
            {"$group": {"_id": None, "seconds": {"$sum": "$duration_seconds"}}},
        ]
        rows = await self.collection.aggregate(pipeline).to_list(length=1)
        return int(rows[0]["seconds"]) if rows else 0


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceTrackerCog(bot))
