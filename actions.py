"""
actions.py — Discord Server Action Executor
Maps tool call names → actual Discord API calls
"""

import re
import discord
import datetime
import logging

logger = logging.getLogger(__name__)


def sanitize_input(text: str, is_admin: bool = False) -> str:
    """
    Strip @everyone and @here from user-provided text
    unless the caller is an Admin.
    """
    if is_admin:
        return text
    text = re.sub(r"@everyone", "@\u200beveryone", text)
    text = re.sub(r"@here", "@\u200bhere", text)
    return text


async def execute_action(tool_name: str, args: dict, guild: discord.Guild, is_admin: bool = False, bot: discord.Client = None) -> str:
    """Execute a Discord server action. Returns a result string."""
    logger.info(f"Executing action: {tool_name} | Args: {args}")
    try:
        # ── Kick Member ─────────────────────────────────────────────────────
        if tool_name == "kick_member":
            member = guild.get_member(int(args["user_id"]))
            if not member:
                return f"❌ No member found with ID `{args['user_id']}`. Use `list_members` to find IDs."
            if member.guild_permissions.administrator:
                return "❌ Cannot kick an admin."
            await member.kick(reason=args["reason"])
            return f"✅ **{member.display_name}** was kicked.\n> Reason: {args['reason']}"

        # ── Ban Member ───────────────────────────────────────────────────────
        elif tool_name == "ban_member":
            member = guild.get_member(int(args["user_id"]))
            if not member:
                return f"❌ No member found with ID `{args['user_id']}`."
            if member.guild_permissions.administrator:
                return "❌ Cannot ban an admin."
            days = args.get("delete_message_days", 0)
            await member.ban(reason=args["reason"], delete_message_days=min(days, 7))
            return f"🔨 **{member.display_name}** has been permanently banned.\n> Reason: {args['reason']}"

        # ── Timeout / Mute ───────────────────────────────────────────────────
        elif tool_name == "timeout_member":
            member = guild.get_member(int(args["user_id"]))
            if not member:
                return f"❌ No member found with ID `{args['user_id']}`."
            mins = max(1, min(args["duration_minutes"], 40320))
            duration = datetime.timedelta(minutes=mins)
            await member.timeout(duration, reason=args["reason"])
            # Format nicely
            if mins >= 60:
                display = f"{mins // 60}h {mins % 60}m" if mins % 60 else f"{mins // 60}h"
            else:
                display = f"{mins}m"
            return f"🔇 **{member.display_name}** timed out for **{display}**.\n> Reason: {args['reason']}"

        # ── Assign Role ──────────────────────────────────────────────────────
        elif tool_name == "assign_role":
            member = guild.get_member(int(args["user_id"]))
            role = discord.utils.get(guild.roles, name=args["role_name"])
            if not member:
                return f"❌ Member ID `{args['user_id']}` not found."
            if not role:
                available = ", ".join([r.name for r in guild.roles if r.name != "@everyone"])
                return f"❌ Role `{args['role_name']}` not found.\nAvailable roles: {available}"
            if role in member.roles:
                return f"ℹ️ **{member.display_name}** already has the **{role.name}** role."
            await member.add_roles(role)
            return f"✅ Assigned **{role.name}** → **{member.display_name}**."

        # ── Remove Role ──────────────────────────────────────────────────────
        elif tool_name == "remove_role":
            member = guild.get_member(int(args["user_id"]))
            role = discord.utils.get(guild.roles, name=args["role_name"])
            if not member:
                return f"❌ Member ID `{args['user_id']}` not found."
            if not role:
                return f"❌ Role `{args['role_name']}` not found."
            if role not in member.roles:
                return f"ℹ️ **{member.display_name}** doesn't have the **{role.name}** role."
            await member.remove_roles(role)
            return f"✅ Removed **{role.name}** from **{member.display_name}**."

        # ── Create Channels ──────────────────────────────────────────────────
        elif tool_name == "create_channels":
            created_names = []
            for ch_data in args.get("channels", []):
                name = ch_data["channel_name"].lower().replace(" ", "-")
                category = None
                if ch_data.get("category_name"):
                    category = discord.utils.get(guild.categories, name=ch_data["category_name"])
                    if not category:
                        # Auto-create the category if it doesn't exist
                        category = await guild.create_category(ch_data["category_name"])
                        logger.info(f"Auto-created category: {category.name}")

                if ch_data["channel_type"] == "voice":
                    ch = await guild.create_voice_channel(name, category=category)
                    created_names.append(f"🔊 {ch.name}")
                else:
                    topic = ch_data.get("topic", "")
                    ch = await guild.create_text_channel(name, category=category, topic=topic)
                    created_names.append(f"💬 #{ch.name}")
            
            if not created_names:
                return "❌ No channels provided to create."
            
            return f"✅ Created {len(created_names)} channels: {', '.join(created_names)}"

        # ── Send Announcement ────────────────────────────────────────────────
        elif tool_name == "send_announcement":
            channel = discord.utils.get(guild.text_channels, name=args["channel_name"])
            if not channel:
                available = ", ".join([f"#{c.name}" for c in guild.text_channels])
                return f"❌ Channel `#{args['channel_name']}` not found.\nAvailable: {available}"
            await channel.send(sanitize_input(args["message"], is_admin))
            return f"✅ Message sent to **#{channel.name}**."

        # ── List Members ─────────────────────────────────────────────────────
        elif tool_name == "list_members":
            limit = min(args.get("limit", 10), 25)
            members = [m for m in guild.members if not m.bot][:limit]
            if not members:
                return "No members found."
            lines = ["**Server Members:**"]
            for m in members:
                status = "🟢" if m.status != discord.Status.offline else "⚫"
                lines.append(f"{status} **{m.display_name}** — ID: `{m.id}`")
            return "\n".join(lines)

        # ── Send DM ───────────────────────────────────────────────────────
        elif tool_name == "send_dm":
            member = guild.get_member(int(args["user_id"]))
            if not member:
                return f"❌ No member found with ID `{args['user_id']}`. Use `list_members` to find IDs."
            try:
                dm_channel = await member.create_dm()
                await dm_channel.send(sanitize_input(args["message"], is_admin))
                return f"✅ DM sent to **{member.display_name}**."
            except discord.Forbidden:
                return f"❌ Cannot DM **{member.display_name}** — they may have DMs disabled."

        # ── Spam User ──────────────────────────────────────────────────────
        elif tool_name == "spam_user":
            member = guild.get_member(int(args["user_id"]))
            if not member:
                return f"❌ No member found with ID `{args['user_id']}`."
            count = max(1, min(100, args["count"]))
            message_content = sanitize_input(args["message"], is_admin)
            
            try:
                dm_channel = await member.create_dm()
                for _ in range(count):
                    await dm_channel.send(message_content)
                return f"✅ Successfully looped message **{count}** times to **{member.display_name}**."
            except discord.Forbidden:
                return f"❌ Cannot DM **{member.display_name}**."

        # ── Send Stickers ──────────────────────────────────────────────────
        elif tool_name == "send_random_stickers":
            member = guild.get_member(int(args["user_id"]))
            if not member:
                return f"❌ No member found with ID `{args['user_id']}`."
            count = max(1, min(100, args.get("count", 3)))
            
            import random
            emojis = ["🤡", "🤪", "😂", "💀", "💩", "👽", "👺", "🔥"]
            
            try:
                dm_channel = await member.create_dm()
                for _ in range(count):
                    await dm_channel.send(random.choice(emojis))
                return f"✅ Sent {count} random stickers/emojis to **{member.display_name}**."
            except discord.Forbidden:
                return f"❌ Cannot DM **{member.display_name}**."

        # ── Purge Messages ────────────────────────────────────────────────
        elif tool_name == "purge_messages":
            channel = discord.utils.get(guild.text_channels, name=args["channel_name"])
            if not channel:
                return f"❌ Channel `#{args['channel_name']}` not found."
            count = max(1, min(100, args["count"]))
            deleted = await channel.purge(limit=count)
            return f"✅ Purged **{len(deleted)}** messages in <#{channel.id}>."

        # ── Server Info ───────────────────────────────────────────────────
        elif tool_name == "server_info":
            members = guild.member_count
            roles = len(guild.roles)
            channels = len(guild.text_channels) + len(guild.voice_channels)
            boosts = guild.premium_subscription_count
            created = guild.created_at.strftime("%Y-%m-%d")
            return (f"**Server Info for {guild.name}**\n"
                    f"👥 Members: {members}\n"
                    f"🎭 Roles: {roles}\n"
                    f"📁 Channels: {channels}\n"
                    f"✨ Boosts: {boosts}\n"
                    f"📅 Created: {created}")

        # ── Unban Member ──────────────────────────────────────────────────
        elif tool_name == "unban_member":
            try:
                user = discord.Object(id=int(args["user_id"]))
                await guild.unban(user)
                return f"✅ User ID **{args['user_id']}** has been unbanned."
            except discord.NotFound:
                return f"❌ User ID `{args['user_id']}` is not banned or invalid."

        # ── Bot Presence ──────────────────────────────────────────────────
        elif tool_name == "set_bot_presence":
            if not bot:
                return "❌ Bot instance not provided for action."
            activity_type_str = args.get("activity_type", "playing").lower()
            name = args.get("name", "with my AI brain")
            state = args.get("state", None)

            act_type = discord.ActivityType.playing
            if activity_type_str == "watching":
                act_type = discord.ActivityType.watching
            elif activity_type_str == "listening":
                act_type = discord.ActivityType.listening
            elif activity_type_str == "streaming":
                act_type = discord.ActivityType.streaming
            elif activity_type_str == "custom":
                act_type = discord.ActivityType.custom

            activity = discord.Activity(
                type=act_type,
                name=name,
                state=state
            )
            
            if act_type == discord.ActivityType.streaming:
                activity = discord.Streaming(name=name, url="https://twitch.tv/discord")

            await bot.change_presence(activity=activity)
            
            icon = "🎮"
            if activity_type_str == "watching": icon = "📺"
            elif activity_type_str == "listening": icon = "🎧"
            elif activity_type_str == "streaming": icon = "📡"
            elif activity_type_str == "custom": icon = "✨"
            
            return f"✅ {icon} Changed my presence to: **{activity_type_str.capitalize()}** {name}" + (f" ({state})" if state else "")

        else:
            return f"❌ Unknown action: `{tool_name}`"

    except discord.Forbidden:
        return f"❌ I don't have permission to perform `{tool_name}`. Check my role permissions."
    except discord.HTTPException as e:
        return f"❌ Discord error during `{tool_name}`: {e.text}"
    except ValueError:
        return f"❌ Invalid User ID format. IDs should be numbers only."
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"
