from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import discord
import wavelink
import yt_dlp
from discord import app_commands
from discord.ext import commands

from database.queries.guild_queries import get_guild_config
from shared.config import MUSIC_QUEUE_LIMIT, VOICE_INACTIVITY_TIMEOUT_SECONDS, settings


@dataclass
class GuildMusicState:
    loop_mode: str = "off"
    idle_task: asyncio.Task | None = None
    requesters: dict[str, int] = field(default_factory=dict)


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.states: dict[int, GuildMusicState] = {}

    async def cog_load(self) -> None:
        try:
            parsed = urlparse(settings.lavalink_uri)
            await wavelink.Pool.connect(
                nodes=[
                    wavelink.Node(
                        identifier="moloj-node",
                        uri=f"{parsed.scheme}://{parsed.netloc}",
                        password=settings.lavalink_password,
                    )
                ],
                client=self.bot,
            )
        except Exception:
            pass

    async def _ensure_premium(self, interaction: discord.Interaction) -> dict | None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return None
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        if config.get("plan_tier") != "premium":
            await interaction.response.send_message("Music is a Premium feature.", ephemeral=True)
            return None
        return config

    async def _ensure_dj_access(self, interaction: discord.Interaction, config: dict) -> bool:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("You need to be in a voice channel to use music controls.", ephemeral=True)
            return False
        if interaction.user.guild_permissions.administrator:
            return True
        dj_role_id = config.get("dj_role_id")
        if dj_role_id:
            if any(role.id == int(dj_role_id) for role in interaction.user.roles):
                return True
            await interaction.response.send_message("Only members with the configured DJ role can use music commands.", ephemeral=True)
            return False
        if interaction.user.voice and interaction.user.voice.channel:
            return True
        await interaction.response.send_message("Join a voice channel first.", ephemeral=True)
        return False

    def _state(self, guild_id: int) -> GuildMusicState:
        return self.states.setdefault(guild_id, GuildMusicState())

    async def _get_player(self, interaction: discord.Interaction) -> wavelink.Player | None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return None
        if not interaction.user.voice or not interaction.user.voice.channel:
            return None
        player = interaction.guild.voice_client
        if not isinstance(player, wavelink.Player):
            player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
        return player

    @app_commands.command(name="play", description="Search YouTube or queue a URL and play it in your voice channel.")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or not await self._ensure_dj_access(interaction, config):
            return
        await interaction.response.defer(thinking=True)
        player = await self._get_player(interaction)
        if player is None:
            await interaction.followup.send("Join a voice channel first.", ephemeral=True)
            return
        state = self._state(interaction.guild.id)
        self._cancel_idle_disconnect(state)

        search_query = await self._resolve_query(query)
        results = await wavelink.Playable.search(search_query)
        if not results:
            await interaction.followup.send("I couldn't find anything for that query.", ephemeral=True)
            return
        track = results[0]
        queue_size = len(player.queue)
        if queue_size >= MUSIC_QUEUE_LIMIT:
            await interaction.followup.send(f"The queue is full. Limit: {MUSIC_QUEUE_LIMIT} songs.", ephemeral=True)
            return
        state.requesters[getattr(track, "identifier", track.title)] = interaction.user.id
        if player.playing or player.paused:
            await player.queue.put_wait(track)
            await interaction.followup.send(f"Queued **{track.title}**.")
        else:
            await player.play(track, volume=50)
            await interaction.followup.send(f"Now playing **{track.title}**.")

    @app_commands.command(name="pause", description="Pause the current track.")
    async def pause(self, interaction: discord.Interaction) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or not await self._ensure_dj_access(interaction, config):
            return
        player = interaction.guild.voice_client if interaction.guild else None
        if not isinstance(player, wavelink.Player) or not player.playing:
            await interaction.response.send_message("Nothing is currently playing.", ephemeral=True)
            return
        await player.pause(True)
        await interaction.response.send_message("Playback paused.")

    @app_commands.command(name="resume", description="Resume the paused track.")
    async def resume(self, interaction: discord.Interaction) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or not await self._ensure_dj_access(interaction, config):
            return
        player = interaction.guild.voice_client if interaction.guild else None
        if not isinstance(player, wavelink.Player):
            await interaction.response.send_message("Nothing is currently connected.", ephemeral=True)
            return
        await player.pause(False)
        await interaction.response.send_message("Playback resumed.")

    @app_commands.command(name="skip", description="Skip to the next track.")
    async def skip(self, interaction: discord.Interaction) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or not await self._ensure_dj_access(interaction, config):
            return
        player = interaction.guild.voice_client if interaction.guild else None
        if not isinstance(player, wavelink.Player) or not player.current:
            await interaction.response.send_message("Nothing is currently playing.", ephemeral=True)
            return
        await player.skip(force=True)
        await interaction.response.send_message("Skipped the current track.")

    @app_commands.command(name="stop", description="Stop playback and disconnect the bot.")
    async def stop(self, interaction: discord.Interaction) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or not await self._ensure_dj_access(interaction, config):
            return
        player = interaction.guild.voice_client if interaction.guild else None
        if not isinstance(player, wavelink.Player):
            await interaction.response.send_message("The bot is not in a voice channel.", ephemeral=True)
            return
        await player.queue.clear()
        await player.disconnect()
        await interaction.response.send_message("Playback stopped and disconnected.")

    @app_commands.command(name="queue", description="Show the current music queue.")
    async def queue(self, interaction: discord.Interaction) -> None:
        player = interaction.guild.voice_client if interaction.guild else None
        if not isinstance(player, wavelink.Player):
            await interaction.response.send_message("There is no active queue.", ephemeral=True)
            return
        tracks = list(player.queue)[:10]
        description = "\n".join(f"**{index}.** {track.title}" for index, track in enumerate(tracks, start=1)) or "Queue is empty."
        embed = discord.Embed(title="Music Queue", description=description, color=discord.Color.blurple())
        if len(player.queue) > 10:
            embed.set_footer(text=f"Showing 10 of {len(player.queue)} queued tracks.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show the current song with progress.")
    async def now_playing(self, interaction: discord.Interaction) -> None:
        player = interaction.guild.voice_client if interaction.guild else None
        if not isinstance(player, wavelink.Player) or not player.current:
            await interaction.response.send_message("Nothing is currently playing.", ephemeral=True)
            return
        track = player.current
        duration = max(getattr(track, "length", 0) // 1000, 1)
        position = max(getattr(player, "position", 0) // 1000, 0)
        progress_bar = self._build_progress_bar(position, duration)
        requester_id = self._state(interaction.guild.id).requesters.get(getattr(track, "identifier", track.title))
        embed = discord.Embed(title="Now Playing", description=f"**{track.title}**\n{progress_bar}", color=discord.Color.blurple())
        embed.add_field(name="Artist", value=getattr(track, "author", "Unknown"), inline=True)
        embed.add_field(name="Duration", value=self._format_seconds(duration), inline=True)
        embed.add_field(name="Requester", value=f"<@{requester_id}>" if requester_id else "Unknown", inline=True)
        artwork = getattr(track, "artwork", None)
        if artwork:
            embed.set_thumbnail(url=artwork)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Set the playback volume.")
    async def volume(self, interaction: discord.Interaction, value: app_commands.Range[int, 1, 100]) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or not await self._ensure_dj_access(interaction, config):
            return
        player = interaction.guild.voice_client if interaction.guild else None
        if not isinstance(player, wavelink.Player):
            await interaction.response.send_message("Nothing is currently connected.", ephemeral=True)
            return
        await player.set_volume(value)
        await interaction.response.send_message(f"Volume set to `{value}`.")

    @app_commands.command(name="shuffle", description="Shuffle the queue.")
    async def shuffle(self, interaction: discord.Interaction) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or not await self._ensure_dj_access(interaction, config):
            return
        player = interaction.guild.voice_client if interaction.guild else None
        if not isinstance(player, wavelink.Player) or len(player.queue) < 2:
            await interaction.response.send_message("Not enough tracks are queued to shuffle.", ephemeral=True)
            return
        player.queue.shuffle()
        await interaction.response.send_message("Queue shuffled.")

    @app_commands.command(name="loop", description="Toggle loop mode (off, track, queue).")
    async def loop(self, interaction: discord.Interaction) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or not await self._ensure_dj_access(interaction, config):
            return
        state = self._state(interaction.guild.id)
        state.loop_mode = {"off": "track", "track": "queue", "queue": "off"}[state.loop_mode]
        await interaction.response.send_message(f"Loop mode set to `{state.loop_mode}`.")

    @app_commands.command(name="remove", description="Remove a song from the queue by position.")
    async def remove(self, interaction: discord.Interaction, position: app_commands.Range[int, 1, 50]) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or not await self._ensure_dj_access(interaction, config):
            return
        player = interaction.guild.voice_client if interaction.guild else None
        if not isinstance(player, wavelink.Player):
            await interaction.response.send_message("There is no active queue.", ephemeral=True)
            return
        tracks = list(player.queue)
        if position > len(tracks):
            await interaction.response.send_message("That queue position does not exist.", ephemeral=True)
            return
        removed = tracks[position - 1]
        del player.queue[position - 1]
        await interaction.response.send_message(f"Removed **{removed.title}** from the queue.")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        player = payload.player
        if player.guild is None:
            return
        state = self._state(player.guild.id)
        finished = payload.track
        if state.loop_mode == "track" and finished is not None:
            await player.play(finished)
            return
        if state.loop_mode == "queue" and finished is not None:
            await player.queue.put_wait(finished)
        if player.queue:
            next_track = await player.queue.get_wait()
            await player.play(next_track)
            return
        self._start_idle_disconnect(player, state)

    async def _resolve_query(self, query: str) -> str:
        if "spotify.com" not in query.lower():
            return query
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as downloader:
            info = downloader.extract_info(query, download=False)
        title = info.get("title") or info.get("entries", [{}])[0].get("title") or query
        return f"ytsearch:{title}"

    def _start_idle_disconnect(self, player: wavelink.Player, state: GuildMusicState) -> None:
        self._cancel_idle_disconnect(state)

        async def disconnect_later() -> None:
            await asyncio.sleep(VOICE_INACTIVITY_TIMEOUT_SECONDS)
            if not player.playing and len(player.queue) == 0:
                await player.disconnect()

        state.idle_task = asyncio.create_task(disconnect_later())

    def _cancel_idle_disconnect(self, state: GuildMusicState) -> None:
        if state.idle_task and not state.idle_task.done():
            state.idle_task.cancel()
        state.idle_task = None

    def _build_progress_bar(self, position: int, duration: int, width: int = 14) -> str:
        filled = min(width, int((position / max(duration, 1)) * width))
        return "[" + "█" * filled + "░" * (width - filled) + f"] {self._format_seconds(position)} / {self._format_seconds(duration)}"

    def _format_seconds(self, value: int) -> str:
        minutes, seconds = divmod(max(value, 0), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot))
