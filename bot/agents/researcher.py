from __future__ import annotations

from bot.agents.base_agent import AgentResult, BaseAgent
from bot.ai_engine import AIContext


class ResearcherAgent(BaseAgent):
    async def run(self, prompt: str, context: AIContext) -> AgentResult:
        response = await self.engine.generate_response(user_message=f"Research task: {prompt}", context=context)
        return AgentResult(output=response.text)
