"""
ai_engine.py — NVIDIA NIM API Integration
Handles: system prompt, tool definitions, AI response parsing
"""

import os
import json
import time
import logging
from openai import OpenAI
from dotenv import load_dotenv

logger = logging.getLogger("moloj.ai_engine")

load_dotenv()

# ─── NVIDIA Client Setup ───────────────────────────────────────────────────────
nvidia = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)

MODEL = "openai/gpt-oss-120b"   # Change to any NVIDIA NIM model you prefer
# Other options:
# "nvidia/llama-3.1-nemotron-70b-instruct"  ← best for reasoning + tool use
# "meta/llama-3.1-405b-instruct"            ← most powerful
# "mistralai/mixtral-8x22b-instruct-v0.1"   ← fast + cheap


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

## Important
- NEVER make up User IDs. If you don't know the ID, use `list_members` or ask.
- NEVER ban/kick without a stated reason.
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
            "name": "create_channel",
            "description": "Create a new text or voice channel in the server.",
            "parameters": {
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
    }
]

# ─── AI Response Function ──────────────────────────────────────────────────────
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
            response = nvidia.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.7
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
