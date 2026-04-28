from __future__ import annotations

import discord
from deep_translator import GoogleTranslator
from discord import app_commands
from discord.ext import commands

from database.client import get_db
from database.queries.guild_queries import get_guild_config, update_guild_config
from shared.config import LANGUAGE_FLAGS, SUPPORTED_LANGUAGE_NAMES


def language_label(code: str) -> str:
    return f"{LANGUAGE_FLAGS.get(code, '🌐')} {SUPPORTED_LANGUAGE_NAMES.get(code, code)}"


class TranslatorCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.collection = get_db()["auto_translate"]
        self.translate_message_menu = app_commands.ContextMenu(
            name="Translate Message",
            callback=self.translate_message_context,
        )

    async def cog_load(self) -> None:
        self.bot.tree.add_command(self.translate_message_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.translate_message_menu.name, type=self.translate_message_menu.type)

    @app_commands.command(name="translate", description="Translate text into another language.")
    async def translate(self, interaction: discord.Interaction, text: str, target_lang: str | None = None) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        target = (target_lang or config.get("default_language", "en")).lower()
        if target not in SUPPORTED_LANGUAGE_NAMES:
            await interaction.response.send_message("Unsupported target language code.", ephemeral=True)
            return
        translated = GoogleTranslator(source="auto", target=target).translate(text)
        embed = discord.Embed(title=f"Translated to {language_label(target)}", description=translated, color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setlanguage", description="Set the default language for this server.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_language(self, interaction: discord.Interaction, lang: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        lang = lang.lower()
        if lang not in SUPPORTED_LANGUAGE_NAMES:
            await interaction.response.send_message("Unsupported language code.", ephemeral=True)
            return
        await update_guild_config(str(interaction.guild.id), {"default_language": lang})
        await interaction.response.send_message(f"Default language set to {language_label(lang)}.", ephemeral=True)

    autotranslate = app_commands.Group(name="autotranslate", description="Manage per-channel auto translation.")

    @autotranslate.command(name="enable", description="Enable auto-translation in this channel.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def autotranslate_enable(self, interaction: discord.Interaction, target_lang: str) -> None:
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message("This command can only be used in a server channel.", ephemeral=True)
            return
        target_lang = target_lang.lower()
        if target_lang not in SUPPORTED_LANGUAGE_NAMES:
            await interaction.response.send_message("Unsupported language code.", ephemeral=True)
            return
        await self.collection.update_one(
            {"guild_id": str(interaction.guild.id), "channel_id": str(interaction.channel.id)},
            {"$set": {"target_lang": target_lang}},
            upsert=True,
        )
        await interaction.response.send_message(
            f"Auto-translation enabled in this channel for {language_label(target_lang)}.",
            ephemeral=True,
        )

    @autotranslate.command(name="disable", description="Disable auto-translation in this channel.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def autotranslate_disable(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message("This command can only be used in a server channel.", ephemeral=True)
            return
        await self.collection.delete_one({"guild_id": str(interaction.guild.id), "channel_id": str(interaction.channel.id)})
        await interaction.response.send_message("Auto-translation disabled in this channel.", ephemeral=True)

    async def translate_message_context(self, interaction: discord.Interaction, message: discord.Message) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This action can only be used in a server.", ephemeral=True)
            return
        config = await get_guild_config(str(interaction.guild.id), interaction.guild.name)
        target = config.get("default_language", "en")
        translated = GoogleTranslator(source="auto", target=target).translate(message.content)
        embed = discord.Embed(title=f"Translated to {language_label(target)}", description=translated, color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        config = await self.collection.find_one({"guild_id": str(message.guild.id), "channel_id": str(message.channel.id)})
        if not config or not message.content.strip():
            return
        translated = GoogleTranslator(source="auto", target=config["target_lang"]).translate(message.content)
        if translated.strip() == message.content.strip():
            return
        embed = discord.Embed(
            title=f"Auto-translation • {language_label(config['target_lang'])}",
            description=translated,
            color=discord.Color.blurple(),
        )
        await message.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TranslatorCog(bot))
