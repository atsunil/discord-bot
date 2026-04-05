"""
base_agent.py — Abstract Base Agent
All Moloj agents inherit from this class.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all Moloj agents."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        logger.info(f"[{self.name}] Agent initialized")

    @abstractmethod
    async def execute(self, task: str, context: dict = None) -> str:
        """
        Execute a task and return the result as a string.

        Args:
            task: The task description / user query.
            context: Optional dict with extra context (guild, channel, author, etc.)

        Returns:
            The agent's response string.
        """
        ...

    async def run(self, task: str, context: dict = None) -> str:
        """
        Public entry point — wraps execute() with logging and error handling.
        """
        logger.info(f"[{self.name}] Starting task: {task[:100]}")
        try:
            result = await self.execute(task, context or {})
            logger.info(
                f"[{self.name}] Task completed "
                f"({len(result)} chars)"
            )
            return result
        except Exception as e:
            logger.error(
                f"[{self.name}] execute failed: {e}", exc_info=True
            )
            return f"❌ Agent `{self.name}` encountered an error: {e}"

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name!r}>"
