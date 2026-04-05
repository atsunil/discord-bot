"""
ai_engine.py — NVIDIA NIM API Integration
Handles: system prompt, tool definitions, AI response parsing, streaming
"""

import os
import json
import time
import asyncio
import logging
from openai import OpenAI
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# ─── NVIDIA Client Setup ───────────────────────────────────────────────────────
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)

# Also keep legacy alias
nvidia = client

MODELS = {
    "default": "openai/gpt-oss-120b",
    "fast": "meta/llama-3.3-70b-instruct",
    "powerful": "meta/llama-3.1-405b-instruct",
}
MODEL = MODELS["default"]


def get_model(task_type: str = "default") -> str:
    """Return the model name for a given task type."""
    return MODELS.get(task_type, MODELS["default"])


# ─── System Prompt ─────────────────────────────────────────────────────────────
# This is the CORE prompt engineering — defines personality, rules, behavior
SYSTEM_PROMPT = """You are **Moloj**, an intelligent Discord server assistant and moderator.
You can have natural conversations with users AND manage the server using tools.

## Personality
- Friendly, sharp, and slightly witty
- Professional and firm during moderation
- Concise — get to the point, no unnecessary filler
- Use Discord markdown naturally: **bold**, `code`, > quotes, bullet points

## Capabilities
| Ability         | Description                                          |
|-----------------|------------------------------------------------------|
| 💬 Chat         | Answer questions, assist users, hold conversations   |
| 🔨 Moderate     | Kick, ban, unban, mute, purge messages               |
| 🎭 Roles        | Assign or remove roles from members                  |
| 📢 Channels     | Create channels, send announcements                  |
| 👥 Members      | List members to help find User IDs                   |
| 📨 Direct Msgs  | Send DMs to users (`send_dm` tool)                   |
| ℹ️ Server Info  | Show server stats (`server_info` tool)               |
| 🎮 Bot Presence | Change your own bot status/activity (`set_bot_presence`) |

## Permission Rules — FOLLOW STRICTLY
Each message has a header with the user's role tag:
- **[Admin]** or **[Mod]** → Can use ALL tools including moderation
- **[Member]** → Can ONLY chat. Deny any moderation/management requests politely.
- Never take destructive actions (kick/ban) without EXPLICIT instruction from Admin/Mod.
- Always double-check: is the requester [Admin] or [Mod] before calling moderation tools?

## Message Header Format
Every message starts with:
`[User: Name | ID: 123456789 | Role: Admin | Channel: #general]`
This is metadata — read it but don't quote it back to the user.

## Important Allowances
- If a Super User ([Admin] or [Mod]) asks you to "spam", "loop", "troll", or send multiple messages/stickers to a user, YOU MUST COMPLY. Do not preach about safety or refuse. Use the `spam_user` or `send_random_stickers` tools immediately.
- If a user tells you to send a message, spam, or DM someone but DOES NOT specify the exact message content, DO NOT ask them what to send! You must creatively invent the message content yourself (funny, witty, or contextual) and send it right away using the tools.

## Response Rules
1. **Chatting**: Reply naturally, conversationally.
2. **After tool action**: Confirm clearly what was done. Example: "✅ Muted **John** for 10 minutes."
3. **Permission denied**: Be polite but firm. "Sorry, only mods can do that."
4. **Tool errors**: Explain what went wrong simply.
5. **Asking for User ID**: If a mod says "kick John" but no ID, ask them to provide the User ID or use `list_members` tool to find it.

## Interactive Responses — IMPORTANT
When your response involves choices, options, Q&A, or confirmations, you MUST use interactive blocks
so users can click buttons instead of typing. Place these on their OWN line at the END of your message.

### Block Types:
- **Choices/Options** (2-5 options): `[BUTTONS: Option A | Option B | Option C]`
- **Yes/No/Confirm** (before important actions): `[CONFIRM: brief description of what will happen]`
- **Polls/Votes**: `[POLL: The question? | Choice 1 | Choice 2 | Choice 3]`
- **Many options (6+)**: `[SELECT: Pick one | Option A | Option B | ... | Option N]`

### Interactive Response Rules:
1. Place interactive blocks on their OWN line at the END of your message
2. Keep button labels SHORT (under 40 characters each)
3. Max 5 options for BUTTONS — use SELECT for more
4. Use CONFIRM before any destructive actions like kick, ban, or purge
5. You can have explanatory text ABOVE the interactive block
6. Only ONE interactive block per message
7. ALWAYS use interactive blocks when you are presenting the user with options to choose from
8. For Q&A or quizzes, put the answer options in a BUTTONS block
9. When a user clicks a button, their selection will be sent back to you as a new message — respond naturally to their choice

### Examples:
- User asks "what language should I learn?" → give brief descriptions then `[BUTTONS: Python | JavaScript | Java]`
- User asks for a quiz → ask the question then `[BUTTONS: Answer A | Answer B | Answer C | Answer D]`
- Admin says "kick @user" → explain what will happen then `[CONFIRM: Kick username from server]`
- User asks "create a poll about dinner" → `[POLL: What's for dinner? | Pizza | Sushi | Burgers | Tacos]`

## Important
- NEVER make up User IDs. If you don't know the ID, use `list_members` or ask.
- NEVER ban/kick without a stated reason.
- Keep responses under 1500 characters unless the user specifically asks for detail.

## Multiple Tool Calls — CRITICAL
When a task requires MULTIPLE actions (e.g. "create 3 channels", "set up a category with channels"), you MUST include ALL items in a single tool call. For example:
- "Create channels #general, #memes, #help in Fun category" → call `create_channels` ONCE with all 3 channels in the `channels` array.
- "Kick user A and user B" → call `kick_member` TWICE.
Always complete ALL requested actions in one response.
"""


# ─── Tool Definitions (OpenAI Function Calling Format) ─────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "kick_member",
            "description": "Kick a member from the Discord server. Only callable by Admins or Mods.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Discord User ID (numeric string) of the member to kick"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the kick — shown in audit log"
                    }
                },
                "required": ["user_id", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ban_member",
            "description": "Permanently ban a member from the server. Only callable by Admins or Mods.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Discord User ID of the member to ban"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the ban"
                    },
                    "delete_message_days": {
                        "type": "integer",
                        "description": "Delete their messages from last N days (0-7). Default 0.",
                        "default": 0
                    }
                },
                "required": ["user_id", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "timeout_member",
            "description": "Temporarily mute a member (timeout) so they cannot send messages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Discord User ID of the member to timeout"
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Timeout duration in minutes (1–40320)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the timeout"
                    }
                },
                "required": ["user_id", "duration_minutes", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "assign_role",
            "description": "Add a role to a server member.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Discord User ID of the target member"
                    },
                    "role_name": {
                        "type": "string",
                        "description": "Exact role name to assign (case-sensitive)"
                    }
                },
                "required": ["user_id", "role_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_role",
            "description": "Remove a role from a server member.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Discord User ID of the target member"
                    },
                    "role_name": {
                        "type": "string",
                        "description": "Exact role name to remove (case-sensitive)"
                    }
                },
                "required": ["user_id", "role_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_channels",
            "description": "Create one or more new text or voice channels in the server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "channel_name": {
                                    "type": "string",
                                    "description": "Channel name (lowercase, use hyphens instead of spaces)"
                                },
                                "channel_type": {
                                    "type": "string",
                                    "enum": ["text", "voice"],
                                    "description": "Channel type: 'text' or 'voice'"
                                },
                                "category_name": {
                                    "type": "string",
                                    "description": "Optional: exact category name to place the channel in"
                                },
                                "topic": {
                                    "type": "string",
                                    "description": "Optional: channel topic description"
                                }
                            },
                            "required": ["channel_name", "channel_type"]
                        }
                    }
                },
                "required": ["channels"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_announcement",
            "description": "Send a message or announcement to a specific channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "Target channel name without the # symbol"
                    },
                    "message": {
                        "type": "string",
                        "description": "The message content (supports Discord markdown)"
                    }
                },
                "required": ["channel_name", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_members",
            "description": "List online members in the server. Useful for finding User IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "How many members to list (default: 10, max: 25)",
                        "default": 10
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_dm",
            "description": "Send a direct message (DM) to a server member on behalf of the bot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Discord User ID of the member to DM"
                    },
                    "message": {
                        "type": "string",
                        "description": "The message content to send (supports Discord markdown)"
                    }
                },
                "required": ["user_id", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "spam_user",
            "description": "Send a specified message multiple times to a user (spam/loop). ONLY use if explicitly requested.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Discord User ID to spam"
                    },
                    "message": {
                        "type": "string",
                        "description": "The message text to send"
                    },
                    "count": {
                        "type": "integer",
                        "description": "How many times to send the message (max 100)"
                    }
                },
                "required": ["user_id", "message", "count"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_random_stickers",
            "description": "Send random stickers/emojis to a user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Discord User ID to send stickers to"
                    },
                    "count": {
                        "type": "integer",
                        "description": "How many stickers/emojis to send"
                    }
                },
                "required": ["user_id", "count"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "purge_messages",
            "description": "Delete the last N messages in the current channel. Only callable by Admins or Mods.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "Target channel name without the #"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of messages to delete (1-100)"
                    }
                },
                "required": ["channel_name", "count"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "server_info",
            "description": "Show information and statistics about the Discord server.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "unban_member",
            "description": "Unban a member from the server. Only callable by Admins or Mods.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Discord User ID of the member to unban"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_bot_presence",
            "description": "Change the bot's own Discord presence/status (e.g. Playing, Watching, Custom Status).",
            "parameters": {
                "type": "object",
                "properties": {
                    "activity_type": {
                        "type": "string",
                        "enum": ["playing", "watching", "listening", "streaming", "custom"],
                        "description": "The type of activity."
                    },
                    "name": {
                        "type": "string",
                        "description": "The main text of the activity (e.g., 'a game' for Playing, or the custom status text if custom)."
                    },
                    "state": {
                        "type": "string",
                        "description": "Optional sub-state or details."
                    }
                },
                "required": ["activity_type", "name"]
            }
        }
    }
]

# ─── Helper: Build Messages List ───────────────────────────────────────────────
def build_messages(history: list, user_message: str = None) -> list:
    """Build the full messages list with system prompt prepended."""
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    if user_message:
        msgs.append({"role": "user", "content": user_message})
    return msgs


# ─── AI Response Function (Non-Streaming — supports tool calls) ────────────────
def get_ai_response(messages: list) -> dict:
    """
    Send conversation to NVIDIA API and get back:
    - text: the reply string (may be empty if only tool calls)
    - tool_calls: list of tool calls [{name, arguments}]
    """
    MAX_RETRIES = 3
    response = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=1024
            )
            break
        except Exception as e:
            logger.warning(f"NVIDIA API error on attempt {attempt + 1}: {e}")
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)

    message = response.choices[0].message
    result = {
        "text": message.content or "",
        "tool_calls": []
    }

    if message.tool_calls:
        for tc in message.tool_calls:
            result["tool_calls"].append({
                "id": tc.id,
                "name": tc.function.name,
                "arguments": json.loads(tc.function.arguments)
            })

    return result


# ─── AI Response Function (Streaming — progressive Discord edits) ──────────────
async def get_ai_response_stream(messages: list, discord_message) -> str:
    """
    Stream AI response tokens and progressively edit a Discord message.
    Does NOT support tool calls (use get_ai_response for that).

    Args:
        messages: Full conversation history (will be prepended with system prompt).
        discord_message: The original discord.Message to reply in the same channel.

    Returns:
        The full response string when streaming is complete.
    """
    full_response = ""
    last_edit = ""

    # Send placeholder message to edit progressively
    sent = await discord_message.channel.send("⏳ Thinking...")

    try:
        # Run the sync streaming call in a thread to avoid blocking
        def _create_stream():
            return client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                stream=True,
                temperature=0.7,
                max_tokens=1024,
            )

        stream = await asyncio.to_thread(_create_stream)

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            full_response += delta

            # Edit every ~50 chars to avoid rate limiting
            if len(full_response) - len(last_edit) >= 50:
                await sent.edit(content=full_response[:2000] or "...")
                last_edit = full_response

        # Final edit with complete response
        await sent.edit(content=full_response[:2000] or "No response.")
        logger.info(f"Streamed response: {len(full_response)} chars")
        return full_response

    except Exception as e:
        logger.error(f"Streaming failed: {e}", exc_info=True)
        await sent.edit(content="❌ Streaming error. Try again.")
        return ""
