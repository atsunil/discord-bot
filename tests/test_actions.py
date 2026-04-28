from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.actions import execute_tool


@pytest.mark.asyncio
async def test_send_announcement_sanitizes_everyone():
    guild = SimpleNamespace(id=1, members=[], roles=[], channels=[])
    caller = SimpleNamespace(
        id=5,
        guild_permissions=SimpleNamespace(administrator=False, kick_members=False, manage_messages=True),
        top_role=SimpleNamespace(position=2, __le__=lambda self, other: self.position <= other.position),
        guild=SimpleNamespace(owner_id=999),
    )
    channel = SimpleNamespace(send=AsyncMock())
    bot = SimpleNamespace()

    result = await execute_tool(
        tool_name="send_announcement",
        tool_args={"content": "@everyone test"},
        bot=bot,
        guild=guild,
        channel=channel,
        caller=caller,
        guild_config={"max_purge": 50},
    )

    assert result["success"] is True
    channel.send.assert_awaited_once()
    assert "@everyone" not in channel.send.await_args.args[0]


@pytest.mark.asyncio
async def test_purge_clamps_to_guild_limit():
    deleted = [object(), object()]
    channel = SimpleNamespace(purge=AsyncMock(return_value=deleted))
    guild = SimpleNamespace(id=1)
    caller = SimpleNamespace(
        id=6,
        guild_permissions=SimpleNamespace(administrator=False, kick_members=False, manage_messages=True),
        top_role=SimpleNamespace(position=2, __le__=lambda self, other: self.position <= other.position),
        guild=SimpleNamespace(owner_id=999),
    )
    result = await execute_tool(
        tool_name="purge_messages",
        tool_args={"count": 999},
        bot=SimpleNamespace(),
        guild=guild,
        channel=channel,
        caller=caller,
        guild_config={"max_purge": 25},
    )
    assert result["success"] is True
    channel.purge.assert_awaited_once_with(limit=25)
