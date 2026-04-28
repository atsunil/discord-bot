from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class HistoryEntryModel:
    guild_id: str
    channel_id: str
    role: str
    content: str
    username: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_document(self) -> dict[str, object]:
        return {
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "role": self.role,
            "content": self.content,
            "username": self.username,
            "timestamp": self.timestamp,
        }
