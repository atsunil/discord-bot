"""
coder.py — Code Generation Agent
Uses the NVIDIA NIM API to generate, explain, and debug code.
"""

import logging

logger = logging.getLogger(__name__)

from .base_agent import BaseAgent


CODER_SYSTEM_PROMPT = """You are a senior software engineer assistant.
Your job is to help users with code-related tasks:
- Write clean, well-commented code
- Explain code snippets clearly
- Debug and fix errors
- Suggest improvements and best practices

Rules:
- Always use Discord markdown for code blocks (```language)
- Keep explanations concise but thorough
- If the language isn't specified, infer it from context
- Include brief comments in generated code
"""


class CoderAgent(BaseAgent):
    """Agent that generates, explains, and debugs code."""

    def __init__(self):
        super().__init__(
            name="Coder",
            description="Generates, explains, and debugs code",
        )

    async def execute(self, task: str, context: dict = None) -> str:
        """Generate or explain code based on the task."""
        logger.info(f"[Coder] Processing task: {task[:80]}")

        try:
            from ai_engine import client, get_model

            response = client.chat.completions.create(
                model=get_model("default"),
                messages=[
                    {"role": "system", "content": CODER_SYSTEM_PROMPT},
                    {"role": "user", "content": task},
                ],
                temperature=0.3,
                max_tokens=1500,
            )

            result = response.choices[0].message.content or ""
            logger.info(f"[Coder] Generated response ({len(result)} chars)")
            return result

        except Exception as e:
            logger.error(f"[Coder] execute failed: {e}", exc_info=True)
            return f"❌ Code generation failed: {e}"
