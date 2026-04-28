from __future__ import annotations

from bot.agents.base_agent import AgentResult, BaseAgent
from bot.ai_engine import AIContext


class CoderAgent(BaseAgent):
    async def run(self, prompt: str, context: AIContext) -> AgentResult:
        response = await self.engine.generate_response(
            user_message=f"Code task: {prompt}",
            context=context,
            caller_is_superuser=False,
        )
        return AgentResult(output=response.text)
