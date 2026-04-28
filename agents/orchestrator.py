"""
orchestrator.py — Task Orchestrator Agent
Routes user requests to the appropriate specialized agent.
"""

import logging

logger = logging.getLogger(__name__)

from .base_agent import BaseAgent
from .researcher import ResearcherAgent
from .coder import CoderAgent


# Keywords that trigger specific agents
RESEARCH_KEYWORDS = [
    "search", "find", "lookup", "look up", "google", "research",
    "what is", "who is", "when did", "where is", "how does",
    "latest", "news", "article",
]

CODE_KEYWORDS = [
    "code", "program", "function", "script", "debug", "fix",
    "write a", "generate", "implement", "python", "javascript",
    "java", "html", "css", "sql", "algorithm", "snippet",
    "explain this code", "what does this code",
]


class OrchestratorAgent(BaseAgent):
    """Routes tasks to the appropriate specialized agent."""

    def __init__(self):
        super().__init__(
            name="Orchestrator",
            description="Routes tasks to specialized agents",
        )
        self.researcher = ResearcherAgent()
        self.coder = CoderAgent()
        logger.info("[Orchestrator] Sub-agents loaded")

    async def execute(self, task: str, context: dict = None) -> str:
        """Determine the best agent for the task and delegate."""
        agent = self._classify(task)
        logger.info(f"[Orchestrator] Routing to: {agent.name}")
        return await agent.run(task, context)

    def _classify(self, task: str) -> BaseAgent:
        """Simple keyword-based classification."""
        task_lower = task.lower()

        # Check for code keywords first (more specific)
        for kw in CODE_KEYWORDS:
            if kw in task_lower:
                logger.info(f"[Orchestrator] Matched code keyword: {kw!r}")
                return self.coder

        # Check for research keywords
        for kw in RESEARCH_KEYWORDS:
            if kw in task_lower:
                logger.info(f"[Orchestrator] Matched research keyword: {kw!r}")
                return self.researcher

        # Default to researcher for general queries
        logger.info("[Orchestrator] No keyword match, defaulting to Researcher")
        return self.researcher

    async def run_research(self, query: str, context: dict = None) -> str:
        """Convenience method to directly run research."""
        return await self.researcher.run(query, context)

    async def run_code(self, task: str, context: dict = None) -> str:
        """Convenience method to directly run code generation."""
        return await self.coder.run(task, context)
