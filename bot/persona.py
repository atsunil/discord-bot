from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from database.queries.guild_queries import get_guild_config, update_guild_config

DEFAULT_PERSONA = {
    "bot_name": "Moloj",
    "personality": "Helpful, concise, and professional.",
    "avatar_url": None,
    "language_style": "professional",
    "forbidden_topics": [],
}


class PersonaCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    persona = app_commands.Group(name="persona", description="Manage the bot persona for this server.")
    persona_set = app_commands.Group(name="set", description="Update part of the server persona.", parent=persona)

    async def _ensure_premium(self, interaction: discord.Interaction) -> dict | None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return None
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        if config.get("plan_tier") != "premium":
            await interaction.response.send_message("Custom persona is a Premium feature.", ephemeral=True)
            return None
        return config

    @persona_set.command(name="name", description="Set the bot name for this server.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_name(self, interaction: discord.Interaction, name: str) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or interaction.guild is None:
            return
        persona = config.get("persona", DEFAULT_PERSONA.copy())
        persona["bot_name"] = name
        await update_guild_config(str(interaction.guild.id), {"persona": persona})
        await interaction.response.send_message(f"Bot persona name set to `{name}`.", ephemeral=True)

    @persona_set.command(name="style", description="Set the language style.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(
        style=[
            app_commands.Choice(name="Formal", value="formal"),
            app_commands.Choice(name="Casual", value="casual"),
            app_commands.Choice(name="Funny", value="funny"),
            app_commands.Choice(name="Professional", value="professional"),
        ]
    )
    async def set_style(self, interaction: discord.Interaction, style: app_commands.Choice[str]) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or interaction.guild is None:
            return
        persona = config.get("persona", DEFAULT_PERSONA.copy())
        persona["language_style"] = style.value
        await update_guild_config(str(interaction.guild.id), {"persona": persona})
        await interaction.response.send_message(f"Persona style set to `{style.value}`.", ephemeral=True)

    @persona_set.command(name="personality", description="Set a custom personality description.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_personality(self, interaction: discord.Interaction, text: str) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or interaction.guild is None:
            return
        persona = config.get("persona", DEFAULT_PERSONA.copy())
        persona["personality"] = text
        await update_guild_config(str(interaction.guild.id), {"persona": persona})
        await interaction.response.send_message("Persona personality updated.", ephemeral=True)

    @persona_set.command(name="forbidden", description="Add a forbidden topic.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_forbidden(self, interaction: discord.Interaction, topic: str) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or interaction.guild is None:
            return
        persona = config.get("persona", DEFAULT_PERSONA.copy())
        topics = set(persona.get("forbidden_topics", []))
        topics.add(topic)
        persona["forbidden_topics"] = sorted(topics)
        await update_guild_config(str(interaction.guild.id), {"persona": persona})
        await interaction.response.send_message(f"Added `{topic}` to forbidden topics.", ephemeral=True)

    @persona.command(name="reset", description="Reset the server persona to the default Moloj personality.")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_persona(self, interaction: discord.Interaction) -> None:
        config = await self._ensure_premium(interaction)
        if config is None or interaction.guild is None:
            return
        await update_guild_config(str(interaction.guild.id), {"persona": DEFAULT_PERSONA.copy()})
        await interaction.response.send_message("Persona reset to default.", ephemeral=True)

    @persona.command(name="preview", description="Preview the current server persona.")
    async def preview_persona(self, interaction: discord.Interaction) -> None:
        config = await self._ensure_premium(interaction)
        if config is None:
            return
        persona = config.get("persona", DEFAULT_PERSONA.copy())
        embed = discord.Embed(title=f"Persona Preview • {persona['bot_name']}", color=discord.Color.blurple())
        embed.add_field(name="Style", value=persona["language_style"])
        embed.add_field(name="Forbidden", value=", ".join(persona["forbidden_topics"]) or "None", inline=False)
        embed.add_field(name="Personality", value=persona["personality"], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PersonaCog(bot))
