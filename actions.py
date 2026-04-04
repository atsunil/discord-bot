"""
actions.py — Discord Server Action Executor
Maps tool call names → actual Discord API calls
"""

import discord
import datetime


async def execute_action(tool_name: str, args: dict, guild: discord.Guild) -> str:
    """Execute a Discord server action. Returns a result string."""
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

        # ── Create Channel ───────────────────────────────────────────────────
        elif tool_name == "create_channel":
            name = args["channel_name"].lower().replace(" ", "-")
            category = None
            if args.get("category_name"):
                category = discord.utils.get(guild.categories, name=args["category_name"])
                if not category:
                    return f"❌ Category `{args['category_name']}` not found."

            if args["channel_type"] == "voice":
                ch = await guild.create_voice_channel(name, category=category)
                return f"✅ Voice channel **{ch.name}** created."
            else:
                topic = args.get("topic", "")
                ch = await guild.create_text_channel(name, category=category, topic=topic)
                return f"✅ Text channel **#{ch.name}** created."

        # ── Send Announcement ────────────────────────────────────────────────
        elif tool_name == "send_announcement":
            channel = discord.utils.get(guild.text_channels, name=args["channel_name"])
            if not channel:
                available = ", ".join([f"#{c.name}" for c in guild.text_channels])
                return f"❌ Channel `#{args['channel_name']}` not found.\nAvailable: {available}"
            await channel.send(args["message"])
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
                await dm_channel.send(args["message"])
                return f"✅ DM sent to **{member.display_name}**."
            except discord.Forbidden:
                return f"❌ Cannot DM **{member.display_name}** — they may have DMs disabled."

        # ── Spam User ──────────────────────────────────────────────────────
        elif tool_name == "spam_user":
            member = guild.get_member(int(args["user_id"]))
            if not member:
                return f"❌ No member found with ID `{args['user_id']}`."
            count = max(1, min(100, args["count"]))
            message_content = args["message"]
            
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
