from __future__ import annotations

import logging
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

from database.client import get_db
from shared.config import REACTION_ROLE_LIMIT

logger = logging.getLogger(__name__)


class ReactionRolesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.collection = get_db()["reaction_roles"]

    reactionrole = app_commands.Group(name="reactionrole", description="Manage reaction role messages.")

    @reactionrole.command(name="setup", description="Create a reaction-role message from emoji-to-role mappings.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_reaction_role(self, interaction: discord.Interaction, mappings: str, title: str = "Choose your roles") -> None:
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message("This command can only be used in a server channel.", ephemeral=True)
            return

        parsed = self._parse_mappings(interaction.guild, mappings)
        if not parsed:
            await interaction.response.send_message(
                "No valid mappings found. Use a format like `✅=@Member, 🎮=@Gamer`.",
                ephemeral=True,
            )
            return
        if len(parsed) > REACTION_ROLE_LIMIT:
            await interaction.response.send_message(
                f"You can only attach up to {REACTION_ROLE_LIMIT} mappings to one message.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(title=title, color=discord.Color.blurple())
        embed.description = "\n".join(f"{emoji} → {role.mention}" for emoji, role in parsed)
        await interaction.response.send_message("Creating reaction role message...", ephemeral=True)
        message = await interaction.channel.send(embed=embed)

        documents = []
        for emoji, role in parsed:
            await message.add_reaction(emoji)
            documents.append(
                {
                    "guild_id": str(interaction.guild.id),
                    "channel_id": str(interaction.channel.id),
                    "message_id": str(message.id),
                    "emoji": emoji,
                    "role_id": str(role.id),
                }
            )
        if documents:
            await self.collection.insert_many(documents)
        await interaction.followup.send(f"Reaction roles are live on [this message]({message.jump_url}).", ephemeral=True)

    @reactionrole.command(name="list", description="List active reaction-role messages in this server.")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_reaction_roles(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        cursor = self.collection.find({"guild_id": str(interaction.guild.id)})
        records = await cursor.to_list(length=None)
        if not records:
            await interaction.response.send_message("No reaction-role messages are configured here yet.", ephemeral=True)
            return

        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for record in records:
            grouped[record["message_id"]].append(record)

        lines = []
        for message_id, items in grouped.items():
            channel_id = items[0]["channel_id"]
            summary = ", ".join(f"{item['emoji']}→<@&{item['role_id']}>" for item in items)
            lines.append(f"[Message {message_id}](https://discord.com/channels/{interaction.guild.id}/{channel_id}/{message_id}) — {summary}")

        embed = discord.Embed(title="Reaction Roles", description="\n".join(lines[:20]), color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @reactionrole.command(name="delete", description="Delete a reaction-role setup by message ID.")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete_reaction_role(self, interaction: discord.Interaction, message_id: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        result = await self.collection.delete_many({"guild_id": str(interaction.guild.id), "message_id": message_id})
        if result.deleted_count == 0:
            await interaction.response.send_message("No reaction-role mapping matched that message ID.", ephemeral=True)
            return
        await interaction.response.send_message(f"Removed {result.deleted_count} stored mappings for message `{message_id}`.", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.guild_id is None or self.bot.user is None or payload.user_id == self.bot.user.id:
            return
        await self._handle_reaction_change(payload=payload, add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.guild_id is None:
            return
        await self._handle_reaction_change(payload=payload, add=False)

    async def _handle_reaction_change(self, *, payload: discord.RawReactionActionEvent, add: bool) -> None:
        record = await self.collection.find_one(
            {
                "guild_id": str(payload.guild_id),
                "message_id": str(payload.message_id),
                "emoji": str(payload.emoji),
            }
        )
        if not record:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        member = guild.get_member(payload.user_id)
        role = guild.get_role(int(record["role_id"]))
        if member is None:
            return
        if role is None:
            logger.warning("Reaction role %s missing in guild %s", record["role_id"], guild.id)
            return
        if add:
            await member.add_roles(role, reason="Reaction role assignment")
        else:
            await member.remove_roles(role, reason="Reaction role removal")

    def _parse_mappings(self, guild: discord.Guild, raw: str) -> list[tuple[str, discord.Role]]:
        pairs: list[tuple[str, discord.Role]] = []
        for item in raw.split(","):
            if "=" not in item:
                continue
            emoji, role_text = item.split("=", 1)
            emoji = emoji.strip()
            role = self._resolve_role(guild, role_text.strip())
            if emoji and role:
                pairs.append((emoji, role))
        return pairs

    def _resolve_role(self, guild: discord.Guild, raw: str) -> discord.Role | None:
        mention_id = "".join(ch for ch in raw if ch.isdigit())
        if mention_id:
            role = guild.get_role(int(mention_id))
            if role:
                return role
        return discord.utils.get(guild.roles, name=raw.removeprefix("@"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReactionRolesCog(bot))
