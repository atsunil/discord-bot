from __future__ import annotations

from bot.agents.base_agent import AgentResult
from bot.agents.coder import CoderAgent
from bot.agents.researcher import ResearcherAgent
from bot.ai_engine import AIContext, AIEngine


class AgentOrchestrator:
    def __init__(self, engine: AIEngine) -> None:
        self.researcher = ResearcherAgent(engine)
        self.coder = CoderAgent(engine)

    async def run(self, prompt: str, context: AIContext) -> AgentResult:
        research = await self.researcher.run(prompt, context)
        code = await self.coder.run(f"Use this research when helpful:\n{research.output}\n\nTask:\n{prompt}", context)
        return AgentResult(output=code.output)
