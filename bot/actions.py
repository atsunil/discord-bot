from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

import discord

from bot.security import PermissionDeniedError, can_use_tool, check_hierarchy, sanitize_content

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ActionResult:
    success: bool
    message: str
    data: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def execute_tool(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    bot: discord.Client,
    guild: discord.Guild,
    channel: discord.abc.Messageable | discord.abc.GuildChannel | None,
    caller: discord.Member,
    guild_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    guild_config = guild_config or {}
    try:
        can_use_tool(caller, tool_name)
        result = await _dispatch(tool_name, tool_args, bot=bot, guild=guild, channel=channel, caller=caller, guild_config=guild_config)
    except PermissionDeniedError as exc:
        logger.warning("Permission denied for %s by %s in %s: %s", tool_name, caller.id, guild.id, exc)
        result = ActionResult(False, str(exc))
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        logger.exception("Failed to execute tool %s in guild %s", tool_name, guild.id)
        result = ActionResult(False, f"Something went wrong while running `{tool_name}`: {exc}")

    logger.info(
        "Action executed action_name=%s caller_id=%s guild_id=%s success=%s",
        tool_name,
        caller.id,
        guild.id,
        result.success,
    )
    return result.to_dict()


async def _dispatch(
    tool_name: str,
    tool_args: dict[str, Any],
    *,
    bot: discord.Client,
    guild: discord.Guild,
    channel: discord.abc.Messageable | discord.abc.GuildChannel | None,
    caller: discord.Member,
    guild_config: dict[str, Any],
) -> ActionResult:
    if tool_name == "kick_member":
        member = _require_member(guild, tool_args)
        check_hierarchy(caller, member)
        await guild.kick(member, reason=tool_args.get("reason"))
        return ActionResult(True, f"Kicked {member.mention}.")

    if tool_name == "ban_member":
        member = _require_member(guild, tool_args)
        check_hierarchy(caller, member)
        await guild.ban(member, reason=tool_args.get("reason"))
        return ActionResult(True, f"Banned {member.mention}.")

    if tool_name == "unban_member":
        user = _require_user(bot, tool_args)
        await guild.unban(user, reason=tool_args.get("reason"))
        return ActionResult(True, f"Unbanned {user}.")

    if tool_name == "timeout_member":
        member = _require_member(guild, tool_args)
        check_hierarchy(caller, member)
        minutes = int(tool_args.get("duration_minutes", 60))
        until = discord.utils.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=tool_args.get("reason"))
        return ActionResult(True, f"Timed out {member.mention} for {minutes} minutes.")

    if tool_name == "assign_role":
        member = _require_member(guild, tool_args)
        role = _require_role(guild, tool_args)
        check_hierarchy(caller, member)
        await member.add_roles(role, reason=tool_args.get("reason"))
        return ActionResult(True, f"Assigned {role.mention} to {member.mention}.")

    if tool_name == "remove_role":
        member = _require_member(guild, tool_args)
        role = _require_role(guild, tool_args)
        check_hierarchy(caller, member)
        await member.remove_roles(role, reason=tool_args.get("reason"))
        return ActionResult(True, f"Removed {role.mention} from {member.mention}.")

    if tool_name == "create_channel":
        name = str(tool_args["name"]).strip().replace("#", "").replace(" ", "-")
        kind = str(tool_args.get("channel_type", "text")).lower()
        if kind == "voice":
            new_channel = await guild.create_voice_channel(name=name)
        else:
            new_channel = await guild.create_text_channel(name=name, topic=tool_args.get("topic"))
        return ActionResult(True, f"Created {new_channel.mention if hasattr(new_channel, 'mention') else new_channel.name}.", {"channel_id": str(new_channel.id)})

    if tool_name == "send_announcement":
        target_channel = _resolve_channel(guild, tool_args) or channel
        if target_channel is None:
            raise RuntimeError("No channel available for the announcement.")
        content = sanitize_content(str(tool_args["content"]), caller)
        await target_channel.send(content)
        return ActionResult(True, "Announcement sent.")

    if tool_name == "list_members":
        members = [
            {"id": str(member.id), "name": member.display_name, "status": str(member.status)}
            for member in guild.members
            if getattr(member, "status", None) != discord.Status.offline
        ]
        return ActionResult(True, f"Found {len(members)} online members.", members)

    if tool_name == "send_dm":
        member = _require_member(guild, tool_args)
        content = sanitize_content(str(tool_args["content"]), caller)
        await member.send(content)
        return ActionResult(True, f"Sent a DM to {member.display_name}.")

    if tool_name == "purge_messages":
        if channel is None or not hasattr(channel, "purge"):
            raise RuntimeError("This action requires a text channel context.")
        max_purge = int(guild_config.get("max_purge", 100))
        requested = int(tool_args.get("count", 1))
        amount = max(1, min(requested, max_purge))
        deleted = await channel.purge(limit=amount)
        return ActionResult(True, f"Deleted {len(deleted)} messages.", {"deleted": len(deleted)})

    if tool_name == "server_info":
        embed = discord.Embed(title=f"{guild.name} Overview", color=discord.Color.blurple())
        embed.add_field(name="Members", value=str(guild.member_count or len(guild.members)))
        embed.add_field(name="Channels", value=str(len(guild.channels)))
        embed.add_field(name="Roles", value=str(len(guild.roles)))
        embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
        return ActionResult(True, "Server info generated.", embed)

    if tool_name == "set_bot_presence":
        activity_type = str(tool_args.get("activity_type", "watching")).lower()
        text = str(tool_args["status_text"])
        activity = _build_activity(activity_type, text)
        await bot.change_presence(activity=activity)
        return ActionResult(True, "Bot presence updated.")

    raise RuntimeError(f"Unknown or unsupported tool: {tool_name}")


def _build_activity(activity_type: str, text: str) -> discord.BaseActivity:
    activity_map = {
        "playing": discord.Game(name=text),
        "listening": discord.Activity(type=discord.ActivityType.listening, name=text),
        "watching": discord.Activity(type=discord.ActivityType.watching, name=text),
        "competing": discord.Activity(type=discord.ActivityType.competing, name=text),
    }
    return activity_map.get(activity_type, discord.Activity(type=discord.ActivityType.watching, name=text))


def _require_member(guild: discord.Guild, tool_args: dict[str, Any]) -> discord.Member:
    user_id = int(tool_args["user_id"])
    member = guild.get_member(user_id)
    if member is None:
        raise RuntimeError(f"Member {user_id} was not found in this server.")
    return member


def _require_role(guild: discord.Guild, tool_args: dict[str, Any]) -> discord.Role:
    role_id = int(tool_args["role_id"])
    role = guild.get_role(role_id)
    if role is None:
        raise RuntimeError(f"Role {role_id} was not found in this server.")
    return role


def _resolve_channel(guild: discord.Guild, tool_args: dict[str, Any]) -> discord.abc.Messageable | None:
    channel_id = tool_args.get("channel_id")
    if channel_id is None:
        return None
    return guild.get_channel(int(channel_id))


def _require_user(bot: discord.Client, tool_args: dict[str, Any]) -> discord.User:
    user = bot.get_user(int(tool_args["user_id"]))
    if user is None:
        raise RuntimeError(f"User {tool_args['user_id']} is not available in cache.")
    return user
