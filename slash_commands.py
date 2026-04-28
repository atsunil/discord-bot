"""
slash_commands.py — Discord Slash Commands
Registers /kick, /ban, /purge, /config using app_commands.
"""

import discord
from discord import app_commands
import logging

logger = logging.getLogger(__name__)


def setup_slash_commands(bot):
    """Call this in bot.py to register all slash commands."""

    @bot.tree.command(name="kick", description="Kick a member from the server")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_slash(
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        await interaction.response.defer()
        try:
            await member.kick(reason=reason)
            await interaction.followup.send(
                f"✅ Kicked {member.mention} | Reason: {reason}"
            )
            logger.info(f"Kicked {member} | By: {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to kick this member."
            )
            logger.warning(f"Kick forbidden for {member}")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed: {e}")
            logger.error(f"Kick failed: {e}", exc_info=True)

    @bot.tree.command(name="ban", description="Ban a member from the server")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban_slash(
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        await interaction.response.defer()
        try:
            await member.ban(reason=reason)
            await interaction.followup.send(
                f"✅ Banned {member.mention} | Reason: {reason}"
            )
            logger.info(f"Banned {member} | By: {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to ban this member."
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Failed: {e}")
            logger.error(f"Ban failed: {e}", exc_info=True)

    @bot.tree.command(
        name="purge", description="Delete messages in this channel"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge_slash(
        interaction: discord.Interaction,
        amount: int,
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=amount)
            await interaction.followup.send(
                f"✅ Deleted {len(deleted)} messages", ephemeral=True
            )
            logger.info(
                f"Purged {len(deleted)} msgs in #{interaction.channel} "
                f"| By: {interaction.user}"
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Failed: {e}", ephemeral=True)
            logger.error(f"Purge failed: {e}", exc_info=True)

    @bot.tree.command(
        name="config",
        description="Configure bot settings for this server",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def config_slash(
        interaction: discord.Interaction,
        prefix: str = None,
        max_purge: int = None,
        allowed_channel: discord.TextChannel = None,
    ):
        from database import update_server_config, get_server_config

        await interaction.response.defer(ephemeral=True)
        updates = {}
        if prefix:
            updates["prefix"] = prefix
        if max_purge:
            updates["max_purge"] = max_purge
        if allowed_channel:
            config = await get_server_config(str(interaction.guild.id))
            existing = config.get("allowed_channels", "")
            ids = [c for c in existing.split(",") if c.strip()]
            ids.append(str(allowed_channel.id))
            updates["allowed_channels"] = ",".join(ids)

        if updates:
            await update_server_config(
                str(interaction.guild.id), **updates
            )
            await interaction.followup.send(
                f"✅ Config updated: {updates}", ephemeral=True
            )
            logger.info(
                f"Config updated for guild {interaction.guild.id}: {updates}"
            )
        else:
            await interaction.followup.send(
                "No changes provided.", ephemeral=True
            )

    @bot.tree.command(
        name="clear_history",
        description="Clear AI conversation history for this channel",
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear_history_slash(interaction: discord.Interaction):
        from database import clear_history

        await interaction.response.defer(ephemeral=True)
        await clear_history(str(interaction.channel.id))
        await interaction.followup.send(
            "✅ Conversation history cleared for this channel.",
            ephemeral=True,
        )
        logger.info(
            f"History cleared for #{interaction.channel} "
            f"| By: {interaction.user}"
        )

    # ─── Global error handler for slash commands ───────────────────────────
    @bot.tree.error
    async def on_app_command_error(interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            if interaction.response.is_done():
                await interaction.followup.send(
                    "❌ You don't have permission for that.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ You don't have permission for that.", ephemeral=True
                )
        else:
            logger.error(f"Slash command error: {error}", exc_info=True)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        f"❌ Error: {error}", ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"❌ Error: {error}", ephemeral=True
                    )
            except Exception:
                pass
