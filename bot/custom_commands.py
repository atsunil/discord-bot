from __future__ import annotations

import re
from datetime import UTC, datetime

import discord
from discord import app_commands
from discord.ext import commands

from database.client import get_db
from database.queries.guild_queries import get_guild_config

EMBED_PATTERN = re.compile(r'^\[EMBED title="(?P<title>[^"]+)" color="(?P<color>#[0-9a-fA-F]{6})"\]\s*(?P<body>.*)$', re.DOTALL)


class CustomCommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.collection = get_db()["custom_commands"]

    @app_commands.command(name="addcommand", description="Create a custom server command.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_command(self, interaction: discord.Interaction, trigger: str, response: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        max_commands = {"free": 5, "pro": 25, "premium": 50}.get(config.get("plan_tier", "free"), 5)
        current_count = await self.collection.count_documents({"guild_id": str(interaction.guild.id)})
        if current_count >= max_commands:
            await interaction.response.send_message("This server has reached its custom command limit.", ephemeral=True)
            return

        response_type = "embed" if response.startswith("[EMBED") else "text"
        embed_color = "#7c3aed" if response_type == "embed" else "#000000"
        await self.collection.update_one(
            {"guild_id": str(interaction.guild.id), "trigger": trigger},
            {
                "$set": {
                    "response": response,
                    "response_type": response_type,
                    "embed_color": embed_color,
                    "created_by": str(interaction.user.id),
                    "created_at": datetime.now(UTC),
                },
                "$setOnInsert": {"uses": 0},
            },
            upsert=True,
        )
        await interaction.response.send_message(f"Custom command `{trigger}` saved.", ephemeral=True)

    @app_commands.command(name="deletecommand", description="Delete a custom server command.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def delete_command(self, interaction: discord.Interaction, trigger: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        result = await self.collection.delete_one({"guild_id": str(interaction.guild.id), "trigger": trigger})
        if result.deleted_count == 0:
            await interaction.response.send_message("No custom command matched that trigger.", ephemeral=True)
            return
        await interaction.response.send_message(f"Deleted custom command `{trigger}`.", ephemeral=True)

    @app_commands.command(name="listcommands", description="List custom commands for this server.")
    async def list_commands(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        rows = await self.collection.find({"guild_id": str(interaction.guild.id)}).sort("trigger", 1).to_list(length=100)
        if not rows:
            await interaction.response.send_message("No custom commands configured.", ephemeral=True)
            return
        description = "\n".join(f"`{row['trigger']}` • uses: {row.get('uses', 0)}" for row in rows)
        embed = discord.Embed(title="Custom Commands", description=description, color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None or not message.content.strip():
            return
        row = await self.collection.find_one({"guild_id": str(message.guild.id), "trigger": message.content.split()[0]})
        if row is None:
            return
        text = self._render_response(template=row["response"], message=message)
        embed_match = EMBED_PATTERN.match(text)
        if embed_match:
            embed = discord.Embed(
                title=embed_match.group("title"),
                description=embed_match.group("body"),
                color=discord.Color.from_str(embed_match.group("color")),
            )
            await message.channel.send(embed=embed)
        else:
            await message.channel.send(text)
        await self.collection.update_one({"_id": row["_id"]}, {"$inc": {"uses": 1}})

    def _render_response(self, template: str, message: discord.Message) -> str:
        return (
            template.replace("{user}", message.author.mention)
            .replace("{server}", message.guild.name if message.guild else "")
            .replace("{count}", str(message.guild.member_count if message.guild else 0))
            .replace("{channel}", message.channel.name if hasattr(message.channel, "name") else "DM")
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CustomCommandsCog(bot))
