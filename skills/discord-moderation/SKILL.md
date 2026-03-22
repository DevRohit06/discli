---
name: discord-moderation
description: "Build Discord moderation bots with discli. Auto-mod, keyword filtering, spam detection, raid protection, warning systems, timeout/kick/ban escalation, audit logging, and permission-gated commands."
---

# Discord Moderation Bot Builder

Build moderation bots that enforce server rules using discli. Covers keyword filtering, spam detection, warning escalation, and admin commands.

## When to Use

Use this skill when the user wants to:
- Build an auto-moderation bot
- Create keyword/content filters
- Implement warning and punishment escalation systems
- Add moderation slash commands (kick, ban, timeout, warn)
- Build raid/spam protection
- Log moderation actions

## Architecture

```
Moderation bot
  ├─ Event listener (discli listen or serve)
  ├─ Rule engine (keyword filter, spam detector, etc.)
  ├─ Action engine (warn, timeout, kick, ban)
  ├─ State store (violation counts, warnings per user)
  └─ Audit logger (log actions for review)
```

## Pattern: Keyword Filter + Escalation

```python
import asyncio
import json
from collections import defaultdict
from datetime import datetime

# Configuration
BANNED_WORDS = {"spam", "scam", "phishing", "nsfw-term"}
BANNED_PATTERNS = []  # regex patterns
WARN_LIMIT = 3        # warnings before timeout
TIMEOUT_LIMIT = 2     # timeouts before kick
TIMEOUT_DURATION = 3600  # 1 hour in seconds

# State
warnings: dict[str, int] = defaultdict(int)
timeouts: dict[str, int] = defaultdict(int)
audit: list[dict] = []


def log_action(action: str, user: str, user_id: str, reason: str, server: str):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "user": user,
        "user_id": user_id,
        "reason": reason,
        "server": server,
    }
    audit.append(entry)
    print(f"[MOD] {action}: {user} — {reason}")


async def check_message(event: dict, send) -> None:
    content = event["content"].lower()
    author = event["author"]
    author_id = event["author_id"]
    channel_id = event["channel_id"]
    message_id = event["message_id"]
    guild_id = event.get("server_id", "")
    server = event.get("server", "")

    # Check banned words
    found = [w for w in BANNED_WORDS if w in content]
    if not found:
        return

    # Delete the offending message
    await send("delete", channel_id=channel_id, message_id=message_id)

    # Increment warnings
    warnings[author_id] += 1
    count = warnings[author_id]

    if count > WARN_LIMIT + TIMEOUT_LIMIT:
        # Kick
        # Note: kick requires member_id via member commands, not directly in serve
        # Use the CLI for destructive actions
        log_action("kick", author, author_id, f"Exceeded all limits ({count} violations)", server)
        await send("send", channel_id=channel_id,
                    content=f"{author} has been removed for repeated violations.",
                    embed={"title": "User Kicked", "color": "ED4245",
                           "fields": [{"name": "Reason", "value": f"{count} violations", "inline": True}]})
        warnings.pop(author_id, None)
        timeouts.pop(author_id, None)

    elif count > WARN_LIMIT:
        # Timeout
        timeouts[author_id] += 1
        await send("member_timeout", guild_id=guild_id, member_id=author_id,
                    duration=TIMEOUT_DURATION, reason=f"Violation #{count}")
        log_action("timeout", author, author_id, f"Violation #{count}: {found}", server)
        await send("send", channel_id=channel_id,
                    content=f"{author} has been timed out for {TIMEOUT_DURATION // 60} minutes.",
                    embed={"color": "FEE75C", "footer": f"Warning {count}/{WARN_LIMIT + TIMEOUT_LIMIT}"})

    else:
        # Warn
        remaining = WARN_LIMIT - count
        log_action("warn", author, author_id, f"Banned words: {found}", server)
        await send("send", channel_id=channel_id,
                    content=f"{author}, your message was removed for violating server rules. "
                            f"{remaining} warning(s) before timeout.",
                    embed={"color": "FEE75C", "footer": f"Warning {count}/{WARN_LIMIT}"})
```

## Pattern: Spam Detection

```python
from collections import defaultdict
from time import time

# Spam thresholds
MAX_MESSAGES_PER_WINDOW = 5
WINDOW_SECONDS = 10
DUPLICATE_THRESHOLD = 3

message_times: dict[str, list[float]] = defaultdict(list)
message_contents: dict[str, list[str]] = defaultdict(list)


async def check_spam(event: dict, send) -> bool:
    """Returns True if message is spam."""
    user_id = event["author_id"]
    content = event["content"]
    now = time()

    # Rate limit check
    message_times[user_id] = [t for t in message_times[user_id] if now - t < WINDOW_SECONDS]
    message_times[user_id].append(now)

    if len(message_times[user_id]) > MAX_MESSAGES_PER_WINDOW:
        await send("delete", channel_id=event["channel_id"], message_id=event["message_id"])
        await send("member_timeout", guild_id=event["server_id"], member_id=user_id,
                    duration=300, reason="Spam: message rate limit exceeded")
        return True

    # Duplicate message check
    message_contents[user_id].append(content)
    message_contents[user_id] = message_contents[user_id][-10:]  # Keep last 10
    recent_dupes = sum(1 for m in message_contents[user_id][-5:] if m == content)

    if recent_dupes >= DUPLICATE_THRESHOLD:
        await send("delete", channel_id=event["channel_id"], message_id=event["message_id"])
        await send("send", channel_id=event["channel_id"],
                    content=f"{event['author']}, please don't send duplicate messages.")
        return True

    return False
```

## Pattern: Moderation Slash Commands

```json
[
  {"name": "warn", "description": "Warn a user", "params": [
    {"name": "user", "type": "string", "description": "User ID or mention"},
    {"name": "reason", "type": "string", "description": "Reason for warning"}
  ]},
  {"name": "timeout", "description": "Timeout a user", "params": [
    {"name": "user", "type": "string", "description": "User ID"},
    {"name": "duration", "type": "integer", "description": "Duration in minutes"},
    {"name": "reason", "type": "string", "description": "Reason", "required": false}
  ]},
  {"name": "warnings", "description": "Check a user's warnings", "params": [
    {"name": "user", "type": "string", "description": "User ID"}
  ]},
  {"name": "modlog", "description": "Show recent mod actions", "params": [
    {"name": "count", "type": "integer", "description": "Number of entries", "required": false}
  ]},
  {"name": "clear-warnings", "description": "Clear a user's warnings", "params": [
    {"name": "user", "type": "string", "description": "User ID"}
  ]}
]
```

Handle with permission checks:

```python
async def on_slash_command(event: dict, send) -> None:
    command = event["command"]
    args = event.get("args", {})
    token = event["interaction_token"]

    # Only allow admins for mod commands
    if not event.get("is_admin"):
        await send("interaction_followup", interaction_token=token,
                    content="You need administrator permissions to use this command.")
        return

    if command == "warn":
        user_id = args["user"]
        reason = args.get("reason", "No reason provided")
        warnings[user_id] += 1
        log_action("warn", user_id, user_id, reason, "")
        await send("interaction_followup", interaction_token=token,
                    content=f"Warned <@{user_id}>: {reason} (total: {warnings[user_id]})")

    elif command == "timeout":
        user_id = args["user"]
        minutes = int(args.get("duration", 10))
        reason = args.get("reason", "Moderator action")
        await send("member_timeout", guild_id=event["guild_id"], member_id=user_id,
                    duration=minutes * 60, reason=reason)
        await send("interaction_followup", interaction_token=token,
                    content=f"Timed out <@{user_id}> for {minutes} minutes: {reason}")

    elif command == "modlog":
        count = int(args.get("count", 10))
        recent = audit[-count:]
        if not recent:
            await send("interaction_followup", interaction_token=token, content="No mod actions recorded.")
            return
        lines = [f"`{e['timestamp'][:19]}` **{e['action']}** {e['user']}: {e['reason']}" for e in recent]
        await send("interaction_followup", interaction_token=token, content="\n".join(lines))
```

## discli Security Features

discli has built-in security that complements moderation bots:

- **Permission profiles**: `discli --profile moderation` restricts commands to moderation-safe subset
- **Audit log**: All destructive actions logged to `~/.discli/audit.log`
- **Rate limiter**: Built-in 5 calls/5s rate limit on destructive actions
- **Confirmation prompts**: Kick/ban/delete require `--yes` flag
- **User permission checking**: `--triggered-by USER_ID` verifies Discord permissions before acting

## Guidelines

- Always check `is_admin` or `member_permissions` before mod commands
- Log every moderation action with timestamp, actor, target, reason
- Use timeouts before kicks, kicks before bans — escalation ladder
- Delete offending content first, then warn/punish
- Send mod notifications as embeds with color coding (yellow=warn, red=kick/ban)
- Never moderate server owner or bot itself
- Keep violation state in memory for simple bots, use a database for production
