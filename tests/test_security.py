from __future__ import annotations

import pytest

from bot.security import PermissionDeniedError, can_use_tool, check_hierarchy, get_role_tag, is_super_user
from shared.config import settings


class DummyRole:
    def __init__(self, position: int) -> None:
        self.position = position

    def __le__(self, other: "DummyRole") -> bool:
        return self.position <= other.position


class DummyPermissions:
    def __init__(self, administrator: bool = False, kick_members: bool = False, manage_messages: bool = False) -> None:
        self.administrator = administrator
        self.kick_members = kick_members
        self.manage_messages = manage_messages


class DummyGuild:
    def __init__(self, owner_id: int = 999) -> None:
        self.owner_id = owner_id


class DummyMember:
    def __init__(
        self,
        *,
        user_id: int,
        administrator: bool = False,
        kick_members: bool = False,
        manage_messages: bool = False,
        top_role_position: int = 1,
        owner_id: int = 999,
    ) -> None:
        self.id = user_id
        self.guild_permissions = DummyPermissions(administrator, kick_members, manage_messages)
        self.top_role = DummyRole(top_role_position)
        self.guild = DummyGuild(owner_id)


def test_get_role_tag_admin(monkeypatch):
    monkeypatch.setattr(settings, "super_users", [])
    member = DummyMember(user_id=1, administrator=True)
    assert get_role_tag(member) == "Admin"


def test_get_role_tag_mod():
    member = DummyMember(user_id=2, kick_members=True)
    assert get_role_tag(member) == "Mod"


def test_get_role_tag_member():
    member = DummyMember(user_id=3)
    assert get_role_tag(member) == "Member"


def test_hierarchy_blocks_equal_roles():
    actor = DummyMember(user_id=1, top_role_position=2)
    target = DummyMember(user_id=2, top_role_position=2)
    with pytest.raises(PermissionDeniedError):
        check_hierarchy(actor, target)


def test_can_use_tool_requires_admin():
    member = DummyMember(user_id=4)
    with pytest.raises(PermissionDeniedError):
        can_use_tool(member, "ban_member")


def test_is_super_user(monkeypatch):
    monkeypatch.setattr(settings, "super_users", ["42"])
    assert is_super_user(42) is True
