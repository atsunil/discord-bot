from __future__ import annotations

import io
import logging

import discord
import httpx
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from database.queries.guild_queries import get_guild_config, update_guild_config

logger = logging.getLogger(__name__)

CANVAS_SIZE = (800, 300)
AVATAR_SIZE = 120


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    welcome = app_commands.Group(name="welcome", description="Manage welcome cards.")

    @welcome.command(name="setup", description="Configure the welcome channel and enable welcome cards.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_welcome(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        welcome_config = config.get("welcome_config", {})
        welcome_config.update({"channel_id": str(channel.id), "enabled": True})
        await update_guild_config(str(interaction.guild.id), {"welcome_config": welcome_config})
        await interaction.response.send_message(f"Welcome cards enabled in {channel.mention}.", ephemeral=True)

    @welcome.command(name="test", description="Preview your welcome card.")
    async def test_welcome(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.user is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        file = await self.build_welcome_file(interaction.guild, interaction.user)
        await interaction.followup.send(content="Welcome card preview:", file=file, ephemeral=True)

    @welcome.command(name="disable", description="Disable welcome cards for this server.")
    @app_commands.checks.has_permissions(administrator=True)
    async def disable_welcome(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        welcome_config = config.get("welcome_config", {})
        welcome_config["enabled"] = False
        await update_guild_config(str(interaction.guild.id), {"welcome_config": welcome_config})
        await interaction.response.send_message("Welcome cards disabled.", ephemeral=True)

    @welcome.command(name="color", description="Change the welcome card background color.")
    @app_commands.checks.has_permissions(administrator=True)
    async def color_welcome(self, interaction: discord.Interaction, hex_color: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        if not self._is_valid_hex(hex_color):
            await interaction.response.send_message("Use a valid color like `#1f2937`.", ephemeral=True)
            return
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        welcome_config = config.get("welcome_config", {})
        welcome_config["bg_color"] = hex_color
        await update_guild_config(str(interaction.guild.id), {"welcome_config": welcome_config})
        await interaction.response.send_message(f"Welcome card color updated to `{hex_color}`.", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        config = await get_guild_config(str(member.guild.id), member.guild.name)
        welcome_config = config.get("welcome_config", {})
        if not welcome_config.get("enabled"):
            return
        channel = self._resolve_channel(member.guild, welcome_config)
        if channel is None:
            return
        try:
            file = await self.build_welcome_file(member.guild, member)
            template = welcome_config.get("message_template", "Welcome to {server_name}, {user}!")
            text = template.format(server_name=member.guild.name, user=member.mention)
            await channel.send(content=text, file=file)
        except Exception as exc:  # pragma: no cover - network/image runtime
            logger.exception("Failed to send welcome card in guild %s: %s", member.guild.id, exc)

    async def build_welcome_file(self, guild: discord.Guild, member: discord.abc.User) -> discord.File:
        config = await get_guild_config(str(guild.id), guild.name)
        welcome_config = config.get("welcome_config", {})
        bg_color = welcome_config.get("bg_color", "#1f2937")

        canvas = Image.new("RGBA", CANVAS_SIZE, bg_color)
        draw = ImageDraw.Draw(canvas)
        self._paint_gradient(draw, bg_color)

        avatar = await self._download_image(member.display_avatar.url)
        avatar = avatar.resize((AVATAR_SIZE, AVATAR_SIZE))
        avatar = self._circle_crop(avatar)
        canvas.alpha_composite(avatar, (40, 90))

        if guild.icon:
            watermark = await self._download_image(guild.icon.url)
            watermark = watermark.resize((60, 60))
            watermark.putalpha(90)
            canvas.alpha_composite(watermark, (CANVAS_SIZE[0] - 90, 20))

        font_large = self._load_font(40)
        font_medium = self._load_font(28)
        font_small = self._load_font(20)

        draw.text((200, 85), f"Welcome to {guild.name}!", fill="white", font=font_large)
        draw.text((200, 145), member.display_name, fill="#a5b4fc", font=font_medium)
        draw.text((200, 200), f"Member #{guild.member_count or 0}", fill="#cbd5e1", font=font_small)

        buffer = io.BytesIO()
        canvas.convert("RGB").save(buffer, format="PNG")
        buffer.seek(0)
        return discord.File(buffer, filename="welcome-card.png")

    def _resolve_channel(self, guild: discord.Guild, welcome_config: dict[str, object]) -> discord.TextChannel | None:
        channel_id = welcome_config.get("channel_id")
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if isinstance(channel, discord.TextChannel):
                return channel
        if isinstance(guild.system_channel, discord.TextChannel):
            return guild.system_channel
        return next((channel for channel in guild.text_channels if channel.permissions_for(guild.me).send_messages), None)

    def _paint_gradient(self, draw: ImageDraw.ImageDraw, bg_color: str) -> None:
        base = self._hex_to_rgb(bg_color)
        width, height = CANVAS_SIZE
        for y in range(height):
            ratio = y / max(height - 1, 1)
            color = tuple(min(255, int(channel * (0.8 + 0.25 * ratio))) for channel in base)
            draw.line([(0, y), (width, y)], fill=color)

    async def _download_image(self, url: str) -> Image.Image:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content)).convert("RGBA")

    def _circle_crop(self, image: Image.Image) -> Image.Image:
        mask = Image.new("L", image.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, image.size[0], image.size[1]), fill=255)
        output = Image.new("RGBA", image.size)
        output.paste(image, (0, 0), mask)
        return output

    def _load_font(self, size: int) -> ImageFont.ImageFont:
        try:
            return ImageFont.truetype("arial.ttf", size=size)
        except OSError:
            return ImageFont.load_default()

    def _hex_to_rgb(self, value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))

    def _is_valid_hex(self, value: str) -> bool:
        value = value.lstrip("#")
        return len(value) == 6 and all(character in "0123456789abcdefABCDEF" for character in value)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeCog(bot))
