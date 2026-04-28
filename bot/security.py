from __future__ import annotations

import os
import re
from enum import IntEnum
from typing import Any

from shared.config import settings

ADMIN_ONLY_TOOLS = {"ban_member", "unban_member", "assign_role", "remove_role", "create_channel"}
MOD_ONLY_TOOLS = {"kick_member", "timeout_member", "purge_messages", "send_announcement"}
UNSAFE_TOOLS = {"spam_user", "send_random_stickers"}


class PermissionDeniedError(RuntimeError):
    """Raised when a guild member cannot perform an action."""


class RoleTier(IntEnum):
    MEMBER = 0
    MOD = 1
    ADMIN = 2


def _member_permissions(member: Any) -> Any:
    return getattr(member, "guild_permissions", None)


def is_super_user(user_id: str | int) -> bool:
    return str(user_id) in settings.super_users


def get_role_tier(member: Any) -> RoleTier:
    permissions = _member_permissions(member)
    if permissions and getattr(permissions, "administrator", False):
        return RoleTier.ADMIN
    if is_super_user(getattr(member, "id", "")):
        return RoleTier.ADMIN
    if permissions and (
        getattr(permissions, "kick_members", False) or getattr(permissions, "manage_messages", False)
    ):
        return RoleTier.MOD
    return RoleTier.MEMBER


def get_role_tag(member: Any) -> str:
    tier = get_role_tier(member)
    return {
        RoleTier.ADMIN: "Admin",
        RoleTier.MOD: "Mod",
        RoleTier.MEMBER: "Member",
    }[tier]


def check_permission(member: Any, required_tier: RoleTier) -> bool:
    actual_tier = get_role_tier(member)
    if actual_tier < required_tier:
        raise PermissionDeniedError(
            f"This action requires {required_tier.name.title()} privileges. Your role tier is {actual_tier.name.title()}."
        )
    return True


def check_hierarchy(actor_member: Any, target_member: Any) -> bool:
    if getattr(actor_member, "id", None) == getattr(target_member, "id", None):
        raise PermissionDeniedError("You cannot use this action on yourself.")

    actor_guild = getattr(actor_member, "guild", None)
    if actor_guild and getattr(actor_guild, "owner_id", None) == getattr(actor_member, "id", None):
        return True

    actor_top_role = getattr(actor_member, "top_role", None)
    target_top_role = getattr(target_member, "top_role", None)
    if actor_top_role is None or target_top_role is None:
        raise PermissionDeniedError("Could not determine role hierarchy for this action.")
    if actor_top_role <= target_top_role:
        raise PermissionDeniedError("You cannot act on a member with an equal or higher role.")
    return True


def can_use_tool(member: Any, tool_name: str) -> bool:
    if tool_name in UNSAFE_TOOLS:
        if not settings.allow_unsafe_tools:
            raise PermissionDeniedError("Unsafe tools are disabled for this bot.")
        if not is_super_user(getattr(member, "id", "")):
            raise PermissionDeniedError("Only super users can access unsafe tools.")
        return True

    if tool_name in ADMIN_ONLY_TOOLS:
        return check_permission(member, RoleTier.ADMIN)
    if tool_name in MOD_ONLY_TOOLS:
        return check_permission(member, RoleTier.MOD)
    return True


def sanitize_content(content: str, member: Any) -> str:
    if get_role_tier(member) >= RoleTier.ADMIN:
        return content
    return re.sub(r"@(everyone|here)", r"[\1]", content, flags=re.IGNORECASE)
