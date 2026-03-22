---
name: discord-support-bot
description: "Build Discord support/helpdesk bots with discli. Thread-per-ticket systems, FAQ auto-responders, knowledge base search, ticket routing, status tracking, and canned responses. Works with AI or rule-based approaches."
---

# Discord Support Bot Builder

Build support and helpdesk bots that handle user questions, create ticket threads, route issues, and provide automated responses using discli.

## When to Use

Use this skill when the user wants to:
- Build a support ticket system on Discord
- Create a FAQ bot or knowledge base responder
- Build a helpdesk with thread-per-ticket workflow
- Create a bot that routes questions to the right team
- Build an AI-powered Q&A assistant for a community

## Pattern 1: Thread-per-Ticket System

Each support request gets its own thread. Clean, organized, searchable.

```python
import asyncio
import json
from datetime import datetime

SUPPORT_CHANNEL_ID = "YOUR_CHANNEL_ID"  # The channel where users ask for help
TRIGGER_WORDS = ["help", "support", "issue", "bug", "problem", "question"]

# Track open tickets: user_id -> thread_id
open_tickets: dict[str, str] = {}


async def handle_support_request(event: dict, send) -> None:
    author = event["author"]
    author_id = event["author_id"]
    channel_id = event["channel_id"]
    message_id = event["message_id"]
    content = event["content"]

    # Check if user already has an open ticket
    if author_id in open_tickets:
        thread_id = open_tickets[author_id]
        await send("thread_send", thread_id=thread_id,
                    content=f"New message from {author}:\n> {content}")
        await send("reaction_add", channel_id=channel_id, message_id=message_id, emoji="📨")
        return

    # Create new support thread
    ticket_name = f"Support: {author} — {datetime.utcnow().strftime('%m/%d %H:%M')}"

    await send("thread_create",
               channel_id=channel_id,
               message_id=message_id,
               name=ticket_name,
               content=f"**New support ticket from {author}**\n\n"
                       f"> {content}\n\n"
                       f"A team member will respond shortly.")

    # React to confirm ticket creation
    await send("reaction_add", channel_id=channel_id, message_id=message_id, emoji="🎫")

    # Note: thread_id comes back in the response event — track it


async def close_ticket(user_id: str, thread_id: str, send) -> None:
    """Close a support ticket."""
    await send("thread_send", thread_id=thread_id,
               content="This ticket has been resolved and will be archived.",
               embed={"title": "Ticket Closed", "color": "57F287",
                      "footer": f"Closed at {datetime.utcnow().isoformat()[:19]}"})
    await send("thread_archive", thread_id=thread_id, archived=True)
    open_tickets.pop(user_id, None)
```

## Pattern 2: FAQ Auto-Responder

Match questions to a knowledge base and respond automatically.

```python
FAQ = [
    {
        "keywords": ["install", "setup", "get started", "download"],
        "title": "Installation",
        "answer": "Install with `pip install discord-cli-agent`. See our [setup guide](https://example.com/setup).",
    },
    {
        "keywords": ["token", "bot token", "authentication", "login"],
        "title": "Bot Token Setup",
        "answer": "1. Go to Discord Developer Portal\n2. Create a bot\n3. Copy the token\n4. Run `discli config set token YOUR_TOKEN`",
    },
    {
        "keywords": ["permission", "permissions", "access denied", "not allowed"],
        "title": "Permissions",
        "answer": "Make sure your bot has the required permissions. Enable all privileged intents in the Developer Portal.",
    },
    {
        "keywords": ["error", "crash", "not working", "broken"],
        "title": "Troubleshooting",
        "answer": "1. Check `discli config show` for valid token\n2. Ensure bot is in the server\n3. Check permissions\n4. Try `discli server list` to verify connection",
    },
]


def find_faq_match(content: str) -> dict | None:
    content_lower = content.lower()
    best_match = None
    best_score = 0

    for entry in FAQ:
        score = sum(1 for kw in entry["keywords"] if kw in content_lower)
        if score > best_score:
            best_score = score
            best_match = entry

    return best_match if best_score > 0 else None


async def handle_faq(event: dict, send) -> bool:
    """Try to answer from FAQ. Returns True if answered."""
    match = find_faq_match(event["content"])
    if not match:
        return False

    await send("reply",
               channel_id=event["channel_id"],
               message_id=event["message_id"],
               content="",
               embed={
                   "title": match["title"],
                   "description": match["answer"],
                   "color": "5865F2",
                   "footer": "From our FAQ — was this helpful? React with 👍 or 👎",
               })
    return True
```

## Pattern 3: AI-Powered Support with Context

Combine FAQ with an LLM for questions the FAQ doesn't cover.

```python
import anthropic

api = anthropic.Anthropic()
KNOWLEDGE_BASE = """
# Product Documentation
- Installation: pip install discord-cli-agent
- Configuration: discli config set token YOUR_TOKEN
- Commands: See discli --help
# Known Issues
- Windows: Use Python 3.10+
- Rate limits: Built-in 5 calls/5s limiter
"""

SYSTEM = f"""You are a support agent. Answer questions using this knowledge base:

{KNOWLEDGE_BASE}

Rules:
- Be concise (under 300 words)
- If you don't know, say so and suggest opening a GitHub issue
- Include relevant command examples when applicable
- Format with Discord markdown (bold, code blocks, lists)
"""


async def ai_support(event: dict, send) -> None:
    """Answer using AI when FAQ doesn't match."""
    # Try FAQ first
    if await handle_faq(event, send):
        return

    # Fall back to AI
    await send("typing_start", channel_id=event["channel_id"])

    response = api.messages.create(
        model="claude-sonnet-4-20250514",
        system=SYSTEM,
        messages=[{"role": "user", "content": event["content"]}],
        max_tokens=512,
    )

    answer = response.content[0].text
    await send("typing_stop", channel_id=event["channel_id"])
    await send("reply",
               channel_id=event["channel_id"],
               message_id=event["message_id"],
               content=answer)
```

## Pattern 4: Slash Commands for Support

```json
[
  {"name": "ticket", "description": "Open a support ticket", "params": [
    {"name": "issue", "type": "string", "description": "Describe your issue"}
  ]},
  {"name": "close", "description": "Close the current support ticket"},
  {"name": "faq", "description": "Search the FAQ", "params": [
    {"name": "query", "type": "string", "description": "What are you looking for?"}
  ]},
  {"name": "status", "description": "Check your ticket status"}
]
```

## Pattern 5: Ticket Status with Embeds

```python
STATUS_COLORS = {
    "open": "FEE75C",      # yellow
    "in_progress": "5865F2", # blue
    "resolved": "57F287",    # green
    "closed": "99AAB5",      # grey
}


async def send_ticket_status(ticket: dict, channel_id: str, send) -> None:
    await send("send", channel_id=channel_id, embed={
        "title": f"Ticket #{ticket['id']}",
        "color": STATUS_COLORS.get(ticket["status"], "99AAB5"),
        "fields": [
            {"name": "Status", "value": ticket["status"].replace("_", " ").title(), "inline": True},
            {"name": "Created by", "value": ticket["author"], "inline": True},
            {"name": "Created at", "value": ticket["created_at"], "inline": True},
            {"name": "Description", "value": ticket["description"][:1024], "inline": False},
        ],
        "footer": "React with ✅ to close this ticket",
    })
```

## Complete Support Bot Skeleton

```python
async def handle_event(event: dict, send) -> None:
    etype = event.get("event")

    if etype == "message" and not event.get("is_bot"):
        if event.get("mentions_bot"):
            # Try FAQ, then AI, then create ticket
            if not await handle_faq(event, send):
                await ai_support(event, send)

        elif any(w in event["content"].lower() for w in TRIGGER_WORDS):
            if event["channel_id"] == SUPPORT_CHANNEL_ID:
                await handle_support_request(event, send)

    elif etype == "slash_command":
        await handle_slash_command(event, send)

    elif etype == "reaction_add":
        if event["emoji"] == "✅":
            # Check if this is a ticket thread, close it
            pass

    elif etype == "component_interaction":
        # Handle button clicks on ticket embeds
        pass
```

## Guidelines

- Create threads in a dedicated support channel, not everywhere
- Archive threads on close so they're searchable but not cluttering
- React to acknowledge receipt (🎫 for new ticket, 📨 for existing)
- Include ticket ID/timestamp in thread names for easy reference
- Use embeds for structured information (status, FAQ answers)
- Set up a `/close` command so staff can resolve tickets
- Log resolved tickets for analytics (response time, resolution rate)
- Rate-limit ticket creation to prevent abuse
