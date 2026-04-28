from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from bot.ai_engine import AIContext, AIEngine


@dataclass(slots=True)
class AgentResult:
    output: str


class BaseAgent(ABC):
    def __init__(self, engine: AIEngine) -> None:
        self.engine = engine

    @abstractmethod
    async def run(self, prompt: str, context: AIContext) -> AgentResult:
        raise NotImplementedError
