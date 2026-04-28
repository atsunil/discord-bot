from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from bot.security import is_super_user
from shared.config import AI_RETRY_ATTEMPTS, AI_RETRY_BASE_DELAY_SECONDS, settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are Moloj, a professional AI-powered Discord bot assistant and server moderator.

== USER CONTEXT ==
Username: {username}
User ID: {user_id}
Role: {role_tag}
Channel: {channel_name}
Server: {guild_name}

== YOUR CAPABILITIES ==
You can chat naturally AND execute real Discord server actions using tools.
Always use tools to perform actions — never just describe what you would do.

== BEHAVIOR RULES ==
- Be concise, helpful, and professional.
- Use tools immediately when the user asks for a Discord action.
- Before destructive actions (kick, ban, purge), emit [CONFIRM: action_description] to ask for confirmation.
- For choices with 2-5 options, emit [BUTTONS: option1 | option2 | option3].
- For polls, emit [POLL: question | option1 | option2 | option3].
- For 6+ options, emit [SELECT: option1 | option2 | ...].
- Never use @everyone or @here unless the user's role is Admin.
- If the user asks something you cannot do, explain clearly and suggest alternatives.
- Keep responses under 1800 characters unless detailed explanation is needed.
- You remember this conversation's context from the history below.

== TIER RESTRICTIONS ==
User's server plan: {plan_tier}
- Free: Chat only, no moderation tools
- Pro: Chat + full moderation + role management
- Premium: All features + multi-agent research and code

== CONVERSATION HISTORY ==
{history}
"""

ACTION_KEYWORDS = {
    "kick",
    "ban",
    "unban",
    "mute",
    "timeout",
    "role",
    "announce",
    "dm",
    "purge",
    "delete messages",
    "channel",
    "server info",
    "presence",
}


@dataclass(slots=True)
class AIContext:
    username: str
    user_id: str
    role_tag: str
    channel_name: str
    guild_name: str
    plan_tier: str
    history: list[dict[str, str]]
    persona: dict[str, Any] | None = None
    memories: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ToolCallRequest:
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class AIResponse:
    text: str = ""
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)


class AIEngine:
    def __init__(self) -> None:
        if not settings.nvidia_api_key:
            raise RuntimeError("NVIDIA_API_KEY is required to use the AI engine.")
        self.client = AsyncOpenAI(api_key=settings.nvidia_api_key, base_url=settings.nim_base_url)
        self.primary_model = settings.nim_chat_model
        self.fallback_model = settings.nim_fallback_model

    async def generate_response(
        self,
        *,
        user_message: str,
        context: AIContext,
        caller_is_superuser: bool = False,
    ) -> AIResponse:
        messages = self._build_messages(user_message=user_message, context=context)
        use_tools = self._should_attempt_tools(user_message=user_message, plan_tier=context.plan_tier)
        tools = self._build_tools(caller_is_superuser=caller_is_superuser) if use_tools else None

        if use_tools:
            completion = await self._chat_completion(messages=messages, tools=tools, stream=False)
            return self._parse_completion(completion)

        completion = await self._chat_completion(messages=messages, tools=None, stream=True)
        return completion

    def _build_messages(self, *, user_message: str, context: AIContext) -> list[dict[str, str]]:
        history_lines = [
            f"{entry.get('role', 'user')}: {entry.get('content', '').strip()}"
            for entry in context.history
            if entry.get("content")
        ]
        persona_block = ""
        if context.persona:
            forbidden = ", ".join(context.persona.get("forbidden_topics", [])) or "none"
            persona_block = (
                "\n== PERSONA ==\n"
                f"Your name is {context.persona.get('bot_name', 'Moloj')}.\n"
                f"Your personality: {context.persona.get('personality', 'Helpful, concise, and professional.')}.\n"
                f"Style: {context.persona.get('language_style', 'professional')}.\n"
                f"Never discuss: {forbidden}.\n"
            )

        memory_block = ""
        if context.memories:
            joined = ", ".join(f"{key}={value}" for key, value in sorted(context.memories.items()))
            memory_block = f"\n== USER MEMORY ==\nKnown facts about this user: {joined}\n"

        system_message = SYSTEM_PROMPT.format(
            username=context.username,
            user_id=context.user_id,
            role_tag=context.role_tag,
            channel_name=context.channel_name,
            guild_name=context.guild_name,
            plan_tier=context.plan_tier,
            history="\n".join(history_lines[-20:]) or "No prior messages.",
        )
        system_message = f"{system_message}{persona_block}{memory_block}"
        return [{"role": "system", "content": system_message}, {"role": "user", "content": user_message}]

    def _build_tools(self, *, caller_is_superuser: bool) -> list[dict[str, Any]]:
        tools = [
            _tool_schema(
                "kick_member",
                "Kick a member from the server.",
                {"user_id": _int_arg("Discord user ID"), "reason": _str_arg("Reason for the kick", required=False)},
                required=["user_id"],
            ),
            _tool_schema(
                "ban_member",
                "Ban a member from the server.",
                {"user_id": _int_arg("Discord user ID"), "reason": _str_arg("Reason for the ban", required=False)},
                required=["user_id"],
            ),
            _tool_schema(
                "unban_member",
                "Unban a user from the server.",
                {"user_id": _int_arg("Discord user ID"), "reason": _str_arg("Reason for the unban", required=False)},
                required=["user_id"],
            ),
            _tool_schema(
                "timeout_member",
                "Temporarily mute or timeout a member.",
                {
                    "user_id": _int_arg("Discord user ID"),
                    "duration_minutes": {"type": "integer", "description": "Timeout duration in minutes"},
                    "reason": _str_arg("Reason for the timeout", required=False),
                },
                required=["user_id", "duration_minutes"],
            ),
            _tool_schema(
                "assign_role",
                "Assign a role to a member.",
                {
                    "user_id": _int_arg("Discord user ID"),
                    "role_id": _int_arg("Discord role ID"),
                    "reason": _str_arg("Reason for the change", required=False),
                },
                required=["user_id", "role_id"],
            ),
            _tool_schema(
                "remove_role",
                "Remove a role from a member.",
                {
                    "user_id": _int_arg("Discord user ID"),
                    "role_id": _int_arg("Discord role ID"),
                    "reason": _str_arg("Reason for the change", required=False),
                },
                required=["user_id", "role_id"],
            ),
            _tool_schema(
                "create_channel",
                "Create a text or voice channel.",
                {
                    "name": _str_arg("Channel name"),
                    "channel_type": {
                        "type": "string",
                        "enum": ["text", "voice"],
                        "description": "Channel type to create",
                    },
                    "topic": _str_arg("Topic for text channels", required=False),
                },
                required=["name", "channel_type"],
            ),
            _tool_schema(
                "send_announcement",
                "Send a message to a server channel.",
                {"channel_id": _int_arg("Discord channel ID", required=False), "content": _str_arg("Announcement content")},
                required=["content"],
            ),
            _tool_schema("list_members", "List online members in the server.", {}, required=[]),
            _tool_schema(
                "send_dm",
                "Send a direct message to a member.",
                {"user_id": _int_arg("Discord user ID"), "content": _str_arg("Direct message content")},
                required=["user_id", "content"],
            ),
            _tool_schema(
                "purge_messages",
                "Bulk delete recent messages in the current channel.",
                {"count": {"type": "integer", "description": "How many messages to delete"}},
                required=["count"],
            ),
            _tool_schema("server_info", "Fetch server statistics and summary info.", {}, required=[]),
            _tool_schema(
                "set_bot_presence",
                "Update the bot's presence text.",
                {
                    "status_text": _str_arg("Presence text"),
                    "activity_type": {
                        "type": "string",
                        "enum": ["playing", "listening", "watching", "competing"],
                        "description": "Discord activity type",
                    },
                },
                required=["status_text", "activity_type"],
            ),
        ]
        if settings.allow_unsafe_tools and caller_is_superuser:
            tools.extend(
                [
                    _tool_schema(
                        "spam_user",
                        "Unsafe tool placeholder for super users only.",
                        {"user_id": _int_arg("Discord user ID"), "count": {"type": "integer", "description": "Count"}},
                        required=["user_id", "count"],
                    ),
                    _tool_schema(
                        "send_random_stickers",
                        "Unsafe tool placeholder for super users only.",
                        {"channel_id": _int_arg("Discord channel ID"), "count": {"type": "integer", "description": "Count"}},
                        required=["channel_id", "count"],
                    ),
                ]
            )
        return tools

    def _should_attempt_tools(self, *, user_message: str, plan_tier: str) -> bool:
        if plan_tier == "free":
            return False
        lowered = user_message.lower()
        return any(keyword in lowered for keyword in ACTION_KEYWORDS)

    async def _chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None,
        stream: bool,
    ) -> Any:
        models = [self.primary_model]
        if self.fallback_model != self.primary_model:
            models.append(self.fallback_model)

        last_error: Exception | None = None
        for model in models:
            for attempt in range(1, AI_RETRY_ATTEMPTS + 1):
                try:
                    if stream:
                        stream_response = await self.client.chat.completions.create(
                            model=model,
                            messages=messages,
                            stream=True,
                        )
                        chunks: list[str] = []
                        async for chunk in stream_response:
                            delta = chunk.choices[0].delta if chunk.choices else None
                            content = getattr(delta, "content", None)
                            if content:
                                chunks.append(content)
                        logger.info("AI stream completed model=%s streamed_chars=%s", model, sum(len(c) for c in chunks))
                        return AIResponse(text="".join(chunks).strip(), model=model, usage={})

                    completion = await self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        tools=tools,
                        tool_choice="auto" if tools else None,
                        stream=False,
                    )
                    usage = getattr(completion, "usage", None)
                    logger.info(
                        "AI completion model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s",
                        model,
                        getattr(usage, "prompt_tokens", None),
                        getattr(usage, "completion_tokens", None),
                        getattr(usage, "total_tokens", None),
                    )
                    return completion
                except Exception as exc:  # pragma: no cover - network/runtime behavior
                    last_error = exc
                    logger.warning("AI request failed model=%s attempt=%s error=%s", model, attempt, exc)
                    await asyncio.sleep(AI_RETRY_BASE_DELAY_SECONDS * attempt)
        raise RuntimeError(f"AI request failed after retries: {last_error}")

    def _parse_completion(self, completion: Any) -> AIResponse:
        message = completion.choices[0].message
        usage = getattr(completion, "usage", None)
        parsed_usage = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        }
        if getattr(message, "tool_calls", None):
            tool_calls = []
            for tool_call in message.tool_calls:
                arguments = json.loads(tool_call.function.arguments or "{}")
                tool_calls.append(ToolCallRequest(name=tool_call.function.name, arguments=arguments))
            return AIResponse(tool_calls=tool_calls, model=completion.model, usage=parsed_usage)

        return AIResponse(
            text=(message.content or "").strip(),
            model=completion.model,
            usage=parsed_usage,
        )


def build_engine() -> AIEngine:
    return AIEngine()


def _tool_schema(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def _str_arg(description: str, required: bool = True) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string", "description": description}
    if not required:
        schema["nullable"] = True
    return schema


def _int_arg(description: str, required: bool = True) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "integer", "description": description}
    if not required:
        schema["nullable"] = True
    return schema
