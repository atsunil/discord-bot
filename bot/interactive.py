from __future__ import annotations

import re
from collections import defaultdict
from typing import Awaitable, Callable

import discord

ChoiceCallback = Callable[[discord.Interaction, str], Awaitable[None]]

MARKER_PATTERN = re.compile(r"\[(BUTTONS|CONFIRM|POLL|SELECT):\s*(.*?)\]", re.IGNORECASE | re.DOTALL)


class CompositeInteractiveView(discord.ui.View):
    def __init__(self, callback: ChoiceCallback, timeout: float = 120) -> None:
        super().__init__(timeout=timeout)
        self.callback = callback
        self.poll_votes: dict[str, int] = defaultdict(int)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True


class ChoiceButton(discord.ui.Button["CompositeInteractiveView"]):
    def __init__(self, label: str, callback_value: str, style: discord.ButtonStyle = discord.ButtonStyle.secondary) -> None:
        super().__init__(label=label, style=style)
        self.callback_value = callback_value

    async def callback(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        assert self.view is not None
        await interaction.response.defer(ephemeral=False, thinking=False)
        await self.view.callback(interaction, self.callback_value)


class ConfirmButton(ChoiceButton):
    def __init__(self, label: str, callback_value: str, approve: bool) -> None:
        super().__init__(
            label=label,
            callback_value=callback_value,
            style=discord.ButtonStyle.success if approve else discord.ButtonStyle.danger,
        )
        self.approve = approve

    async def callback(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        assert self.view is not None
        if not self.approve:
            await interaction.response.send_message("Action cancelled.", ephemeral=True)
            self.view.stop()
            return
        await interaction.response.defer(ephemeral=False, thinking=False)
        await self.view.callback(interaction, self.callback_value)


class PollButton(discord.ui.Button["CompositeInteractiveView"]):
    def __init__(self, option: str) -> None:
        super().__init__(label=f"{option} (0 votes)", style=discord.ButtonStyle.primary)
        self.option = option

    async def callback(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        assert self.view is not None
        self.view.poll_votes[self.option] += 1
        self.label = f"{self.option} ({self.view.poll_votes[self.option]} votes)"
        await interaction.response.edit_message(view=self.view)
        await self.view.callback(interaction, self.option)


class ChoiceSelect(discord.ui.Select["CompositeInteractiveView"]):
    def __init__(self, placeholder: str, options: list[str]) -> None:
        super().__init__(
            placeholder=placeholder[:150],
            options=[discord.SelectOption(label=option[:100], value=option) for option in options],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        assert self.view is not None
        await interaction.response.defer(ephemeral=False, thinking=False)
        await self.view.callback(interaction, self.values[0])


def parse_interactive_response(
    text: str,
    callback: ChoiceCallback,
) -> tuple[str, discord.ui.View | None]:
    matches = list(MARKER_PATTERN.finditer(text))
    if not matches:
        return text, None

    view = CompositeInteractiveView(callback=callback)
    for match in matches:
        marker_type = match.group(1).upper()
        payload = match.group(2).strip()
        _add_components(view, marker_type, payload)

    cleaned = MARKER_PATTERN.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, view if view.children else None


def _add_components(view: CompositeInteractiveView, marker_type: str, payload: str) -> None:
    if marker_type == "BUTTONS":
        for option in _split_payload(payload):
            view.add_item(ChoiceButton(label=option, callback_value=option))
        return

    if marker_type == "CONFIRM":
        description = payload.strip()
        view.add_item(ConfirmButton(label="Yes, do it", callback_value=description, approve=True))
        view.add_item(ConfirmButton(label="Cancel", callback_value="cancel", approve=False))
        return

    if marker_type == "POLL":
        parts = _split_payload(payload)
        options = parts[1:] if len(parts) > 1 else parts
        for option in options:
            view.add_item(PollButton(option=option))
        return

    if marker_type == "SELECT":
        parts = _split_payload(payload)
        if not parts:
            return
        placeholder = parts[0]
        options = parts[1:] if len(parts) > 1 else ["Select"]
        view.add_item(ChoiceSelect(placeholder=placeholder, options=options))


def _split_payload(payload: str) -> list[str]:
    return [item.strip() for item in payload.split("|") if item.strip()]
