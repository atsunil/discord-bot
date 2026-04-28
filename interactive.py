"""
interactive.py — Interactive Discord UI Components
Parses AI responses for interactive blocks and renders Discord Buttons, Select Menus, Polls, etc.

Supported block formats (placed at the END of the AI message, on their own line):
  [BUTTONS: Option A | Option B | Option C]
  [CONFIRM: action description]
  [POLL: Question? | Choice 1 | Choice 2 | Choice 3]
  [SELECT: Prompt text | Option A | Option B | ... | Option N]
"""

import re
import logging
import discord
from discord.ui import View, Button, Select
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)

# ─── Regex patterns for interactive blocks ──────────────────────────────────────
BUTTONS_PATTERN  = re.compile(r"\[BUTTONS:\s*(.+?)\]", re.IGNORECASE)
CONFIRM_PATTERN  = re.compile(r"\[CONFIRM:\s*(.+?)\]", re.IGNORECASE)
POLL_PATTERN     = re.compile(r"\[POLL:\s*(.+?)\]", re.IGNORECASE)
SELECT_PATTERN   = re.compile(r"\[SELECT:\s*(.+?)\]", re.IGNORECASE)

# Button style palette — cycle through these for visual variety
BUTTON_STYLES = [
    discord.ButtonStyle.primary,    # Blurple
    discord.ButtonStyle.success,    # Green
    discord.ButtonStyle.secondary,  # Grey
    discord.ButtonStyle.primary,    # Blurple again
    discord.ButtonStyle.success,    # Green again
]

POLL_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

VIEW_TIMEOUT = 180  # 3 minutes


# ─── Callback type ──────────────────────────────────────────────────────────────
# Signature:  async callback(interaction, selected_text, channel_id) -> None
InteractionCallback = Callable[[discord.Interaction, str, str], Awaitable[None]]


# ─── Interactive Button ─────────────────────────────────────────────────────────
class InteractiveButton(Button):
    """A button that sends the user's selection back to the AI."""

    def __init__(
        self,
        label: str,
        style: discord.ButtonStyle,
        callback_fn: InteractionCallback,
        channel_id: str,
        emoji: Optional[str] = None,
    ):
        super().__init__(label=label, style=style, emoji=emoji)
        self._callback_fn = callback_fn
        self._channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        # Disable all buttons in this view after click
        for item in self.view.children:
            item.disabled = True

        # Mark the clicked button
        self.style = discord.ButtonStyle.success
        self.label = f"✓ {self.label}"

        await interaction.response.edit_message(view=self.view)

        # Feed the selection back to the AI
        await self._callback_fn(interaction, self.label.replace("✓ ", ""), self._channel_id)


# ─── Confirm Button ─────────────────────────────────────────────────────────────
class ConfirmButton(Button):
    """Confirm or cancel an action."""

    def __init__(
        self,
        is_confirm: bool,
        action_desc: str,
        callback_fn: InteractionCallback,
        channel_id: str,
    ):
        if is_confirm:
            super().__init__(label="✅ Confirm", style=discord.ButtonStyle.success)
        else:
            super().__init__(label="❌ Cancel", style=discord.ButtonStyle.danger)

        self._is_confirm = is_confirm
        self._action_desc = action_desc
        self._callback_fn = callback_fn
        self._channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        # Disable all buttons
        for item in self.view.children:
            item.disabled = True

        if self._is_confirm:
            self.style = discord.ButtonStyle.success
            self.label = "✅ Confirmed"
        else:
            self.style = discord.ButtonStyle.secondary
            self.label = "❌ Cancelled"

        await interaction.response.edit_message(view=self.view)

        selection = f"Yes, confirm: {self._action_desc}" if self._is_confirm else f"No, cancel: {self._action_desc}"
        await self._callback_fn(interaction, selection, self._channel_id)


# ─── Poll Button ─────────────────────────────────────────────────────────────────
class PollButton(Button):
    """A poll vote button — tracks vote counts."""

    def __init__(
        self,
        label: str,
        emoji: str,
        channel_id: str,
    ):
        super().__init__(label=f"{label} (0)", style=discord.ButtonStyle.secondary, emoji=emoji)
        self._base_label = label
        self._channel_id = channel_id
        self._votes: set[int] = set()  # Track user IDs who voted

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        if user_id in self._votes:
            # Un-vote
            self._votes.discard(user_id)
        else:
            # Remove vote from other options first (single-vote poll)
            for item in self.view.children:
                if isinstance(item, PollButton) and item is not self:
                    item._votes.discard(user_id)
                    item.label = f"{item._base_label} ({len(item._votes)})"
            self._votes.add(user_id)

        self.label = f"{self._base_label} ({len(self._votes)})"

        # Highlight the voted button for this user
        await interaction.response.edit_message(view=self.view)


# ─── Interactive Select Menu ────────────────────────────────────────────────────
class InteractiveSelect(Select):
    """A dropdown select menu for 5+ options."""

    def __init__(
        self,
        placeholder: str,
        options_list: list[str],
        callback_fn: InteractionCallback,
        channel_id: str,
    ):
        options = [
            discord.SelectOption(label=opt.strip(), value=opt.strip())
            for opt in options_list[:25]  # Discord max 25 options
        ]
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)
        self._callback_fn = callback_fn
        self._channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]

        # Disable the select after use
        self.disabled = True
        self.placeholder = f"✓ Selected: {selected}"

        await interaction.response.edit_message(view=self.view)

        # Feed selection back to AI
        await self._callback_fn(interaction, selected, self._channel_id)


# ─── View Builders ──────────────────────────────────────────────────────────────
def build_buttons_view(
    options: list[str],
    callback_fn: InteractionCallback,
    channel_id: str,
) -> View:
    """Create a View with interactive buttons (max 5 per row, max 25 total)."""
    view = View(timeout=VIEW_TIMEOUT)
    for i, opt in enumerate(options[:25]):
        style = BUTTON_STYLES[i % len(BUTTON_STYLES)]
        btn = InteractiveButton(
            label=opt.strip(),
            style=style,
            callback_fn=callback_fn,
            channel_id=channel_id,
        )
        view.add_item(btn)
    return view


def build_confirm_view(
    action_desc: str,
    callback_fn: InteractionCallback,
    channel_id: str,
) -> View:
    """Create a View with Confirm / Cancel buttons."""
    view = View(timeout=VIEW_TIMEOUT)
    view.add_item(ConfirmButton(True, action_desc, callback_fn, channel_id))
    view.add_item(ConfirmButton(False, action_desc, callback_fn, channel_id))
    return view


def build_poll_view(
    question: str,
    choices: list[str],
    channel_id: str,
) -> View:
    """Create a View with poll vote buttons. Polls don't feed back to AI — they just track votes."""
    view = View(timeout=600)  # Polls last 10 minutes
    for i, choice in enumerate(choices[:10]):
        emoji = POLL_EMOJIS[i] if i < len(POLL_EMOJIS) else None
        btn = PollButton(
            label=choice.strip(),
            emoji=emoji,
            channel_id=channel_id,
        )
        view.add_item(btn)
    return view


def build_select_view(
    placeholder: str,
    options: list[str],
    callback_fn: InteractionCallback,
    channel_id: str,
) -> View:
    """Create a View with a dropdown select menu."""
    view = View(timeout=VIEW_TIMEOUT)
    select = InteractiveSelect(
        placeholder=placeholder.strip(),
        options_list=options,
        callback_fn=callback_fn,
        channel_id=channel_id,
    )
    view.add_item(select)
    return view


# ─── Main Parser ────────────────────────────────────────────────────────────────
def parse_interactive_blocks(
    text: str,
    callback_fn: InteractionCallback,
    channel_id: str,
) -> tuple[str, Optional[View]]:
    """
    Parse AI response text for interactive block markers.

    Returns:
        (clean_text, view_or_None)
        - clean_text: the text with interactive block markers removed
        - view_or_None: a discord.ui.View if interactive elements were found, else None
    """
    view = None

    # ── Check for BUTTONS ────────────────────────────────────────────────────
    match = BUTTONS_PATTERN.search(text)
    if match:
        raw = match.group(1)
        options = [o.strip() for o in raw.split("|") if o.strip()]
        if options:
            text = text[:match.start()] + text[match.end():]
            view = build_buttons_view(options, callback_fn, channel_id)
            logger.info(f"Parsed BUTTONS block with {len(options)} options")

    # ── Check for CONFIRM ────────────────────────────────────────────────────
    if not view:
        match = CONFIRM_PATTERN.search(text)
        if match:
            action_desc = match.group(1).strip()
            text = text[:match.start()] + text[match.end():]
            view = build_confirm_view(action_desc, callback_fn, channel_id)
            logger.info(f"Parsed CONFIRM block: {action_desc}")

    # ── Check for POLL ───────────────────────────────────────────────────────
    if not view:
        match = POLL_PATTERN.search(text)
        if match:
            raw = match.group(1)
            parts = [p.strip() for p in raw.split("|") if p.strip()]
            if len(parts) >= 2:
                question = parts[0]
                choices = parts[1:]
                text = text[:match.start()] + text[match.end():]
                view = build_poll_view(question, choices, channel_id)
                logger.info(f"Parsed POLL block: {question} with {len(choices)} choices")

    # ── Check for SELECT ─────────────────────────────────────────────────────
    if not view:
        match = SELECT_PATTERN.search(text)
        if match:
            raw = match.group(1)
            parts = [p.strip() for p in raw.split("|") if p.strip()]
            if len(parts) >= 2:
                placeholder = parts[0]
                options = parts[1:]
                text = text[:match.start()] + text[match.end():]
                view = build_select_view(placeholder, options, callback_fn, channel_id)
                logger.info(f"Parsed SELECT block with {len(options)} options")

    # Clean up extra trailing whitespace/newlines left by removed blocks
    text = text.rstrip()

    return text, view
