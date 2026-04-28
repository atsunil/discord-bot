from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from database.queries.guild_queries import get_guild_config, update_guild_config


class CoreSlashCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    config_group = app_commands.Group(name="config", description="Manage bot configuration for this server.")

    @app_commands.command(name="ping", description="Check whether Moloj is awake.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = round((self.bot.latency or 0) * 1000)
        await interaction.response.send_message(f"Pong. Latency: {latency_ms}ms")

    @config_group.command(name="show", description="Show the current configuration for this server.")
    async def config_show(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        embed = discord.Embed(title=f"{interaction.guild.name} config", color=discord.Color.blurple())
        embed.add_field(name="Prefix", value=config.get("prefix", "moloj"))
        embed.add_field(name="Max purge", value=str(config.get("max_purge", 100)))
        embed.add_field(name="Plan", value=config.get("plan_tier", "free").title())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @config_group.command(name="prefix", description="Update the natural-language trigger prefix.")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_prefix(self, interaction: discord.Interaction, prefix: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await update_guild_config(str(interaction.guild.id), {"prefix": prefix.strip()})
        await interaction.response.send_message(f"Prefix updated to `{prefix.strip()}`.", ephemeral=True)

    @config_group.command(name="maxpurge", description="Update the maximum bulk-delete limit.")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_maxpurge(self, interaction: discord.Interaction, value: app_commands.Range[int, 1, 500]) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await update_guild_config(str(interaction.guild.id), {"max_purge": int(value)})
        await interaction.response.send_message(f"Max purge updated to `{value}`.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    cog = CoreSlashCommands(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.config_group)
