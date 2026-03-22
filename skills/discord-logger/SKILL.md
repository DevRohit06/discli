---
name: discord-logger
description: "Build Discord logging and analytics bots with discli. Message logging, audit trails, activity dashboards, channel archives, voice activity tracking, user statistics, and event monitoring. Bash or Python."
---

# Discord Logger & Analytics Bot Builder

Build bots that log Discord activity, create audit trails, track statistics, and archive channels using discli.

## When to Use

Use this skill when the user wants to:
- Log messages, edits, and deletes to a file or channel
- Build an audit trail for moderation
- Track server activity and generate statistics
- Archive channels or export message history
- Monitor voice channel activity
- Build a dashboard that shows server health metrics

## Pattern 1: Bash — JSONL File Logger

The simplest logger. One line of bash.

```bash
#!/bin/bash
# Log all messages to a JSONL file
discli --json listen --events messages,edits,deletes,members,voice \
  | tee -a discord_log_$(date +%Y%m%d).jsonl
```

With server/channel filtering:

```bash
discli --json listen \
  --server "My Server" \
  --channel "#general" \
  --events messages,edits,deletes \
  | tee -a general_log.jsonl
```

## Pattern 2: Mod Log Channel

Forward edits, deletes, and member changes to a staff-only log channel.

```python
import asyncio
import json
from datetime import datetime

LOG_CHANNEL_ID = "YOUR_LOG_CHANNEL_ID"


async def handle_event(event: dict, send) -> None:
    etype = event.get("event")

    if etype == "message_edit":
        await send("send", channel_id=LOG_CHANNEL_ID, embed={
            "title": "Message Edited",
            "color": "FEE75C",
            "fields": [
                {"name": "Author", "value": f"{event['author']} ({event['author_id']})", "inline": True},
                {"name": "Channel", "value": f"<#{event['channel_id']}>", "inline": True},
                {"name": "Before", "value": (event.get("old_content") or "(unknown)")[:1024], "inline": False},
                {"name": "After", "value": (event.get("new_content") or "(empty)")[:1024], "inline": False},
            ],
            "footer": f"Message ID: {event['message_id']}",
        })

    elif etype == "message_delete":
        await send("send", channel_id=LOG_CHANNEL_ID, embed={
            "title": "Message Deleted",
            "color": "ED4245",
            "fields": [
                {"name": "Author", "value": f"{event.get('author', 'Unknown')} ({event.get('author_id', '?')})", "inline": True},
                {"name": "Channel", "value": f"<#{event['channel_id']}>", "inline": True},
                {"name": "Content", "value": (event.get("content") or "(not cached)")[:1024], "inline": False},
            ],
            "footer": f"Message ID: {event['message_id']}",
        })

    elif etype == "member_join":
        await send("send", channel_id=LOG_CHANNEL_ID, embed={
            "title": "Member Joined",
            "color": "57F287",
            "description": f"**{event['member']}** (`{event['member_id']}`)",
        })

    elif etype == "member_remove":
        await send("send", channel_id=LOG_CHANNEL_ID, embed={
            "title": "Member Left",
            "color": "ED4245",
            "description": f"**{event['member']}** (`{event['member_id']}`)",
        })

    elif etype == "voice_state":
        action = event.get("action")
        if action in ("joined", "left", "moved"):
            colors = {"joined": "57F287", "left": "ED4245", "moved": "FEE75C"}
            desc = f"**{event['member']}** {action} voice"
            if action == "moved":
                desc += f" from #{event.get('from_channel')} to #{event.get('channel')}"
            else:
                desc += f" #{event.get('channel')}"
            await send("send", channel_id=LOG_CHANNEL_ID, embed={
                "title": f"Voice: {action.title()}",
                "color": colors.get(action, "99AAB5"),
                "description": desc,
            })
```

## Pattern 3: Channel Archiver

Export a channel's history to a JSONL file.

```bash
#!/bin/bash
# Archive last 30 days of #general
discli --json message history "#general" --days 30 > general_archive.jsonl
echo "Archived $(wc -l < general_archive.jsonl) messages"
```

Python version with progress:

```python
import json
import subprocess

def archive_channel(channel: str, days: int, output_file: str):
    result = subprocess.run(
        ["discli", "--json", "message", "history", channel, "--days", str(days)],
        capture_output=True, text=True,
    )
    messages = json.loads(result.stdout)
    with open(output_file, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
    print(f"Archived {len(messages)} messages to {output_file}")
```

## Pattern 4: Activity Statistics

Track and report server activity.

```python
from collections import defaultdict, Counter
from datetime import datetime, timedelta

# In-memory stats (reset on restart)
message_counts: dict[str, int] = defaultdict(int)  # user_id -> count
channel_activity: dict[str, int] = defaultdict(int)  # channel_id -> count
hourly_activity: dict[int, int] = defaultdict(int)   # hour -> count
active_users: set[str] = set()


async def track_message(event: dict) -> None:
    """Track a message for statistics."""
    message_counts[event["author_id"]] += 1
    channel_activity[event["channel_id"]] += 1
    hour = datetime.fromisoformat(event["timestamp"]).hour
    hourly_activity[hour] += 1
    active_users.add(event["author_id"])


async def send_stats(channel_id: str, send) -> None:
    """Send activity summary as an embed."""
    total = sum(message_counts.values())
    top_users = sorted(message_counts.items(), key=lambda x: -x[1])[:5]
    top_channels = sorted(channel_activity.items(), key=lambda x: -x[1])[:5]
    peak_hour = max(hourly_activity.items(), key=lambda x: x[1])[0] if hourly_activity else 0

    users_text = "\n".join(f"<@{uid}>: {count}" for uid, count in top_users) or "No data"
    channels_text = "\n".join(f"<#{cid}>: {count}" for cid, count in top_channels) or "No data"

    await send("send", channel_id=channel_id, embed={
        "title": "Server Activity Report",
        "color": "5865F2",
        "fields": [
            {"name": "Total Messages", "value": str(total), "inline": True},
            {"name": "Active Users", "value": str(len(active_users)), "inline": True},
            {"name": "Peak Hour", "value": f"{peak_hour}:00 UTC", "inline": True},
            {"name": "Top Users", "value": users_text, "inline": False},
            {"name": "Top Channels", "value": channels_text, "inline": False},
        ],
        "footer": "Stats since last restart",
    })
```

## Pattern 5: Scheduled Stats Report

```json
[
  {"name": "stats", "description": "Show server activity statistics"},
  {"name": "archive", "description": "Archive a channel's history", "params": [
    {"name": "channel", "type": "string", "description": "Channel to archive"},
    {"name": "days", "type": "integer", "description": "Days of history", "required": false}
  ]}
]
```

## Bash One-Liners

```bash
# Count messages per user in last 24h
discli --json message history "#general" --hours 24 | jq -r '.[].author' | sort | uniq -c | sort -rn

# Find all messages with attachments
discli --json message history "#general" --days 7 | jq '.[] | select(.attachments | length > 0)'

# Export user list
discli --json member list "My Server" --limit 1000 | jq -r '.[] | [.id, .name] | @csv'

# Monitor for deleted messages in real-time
discli --json listen --events deletes | jq -r '"DELETED: \(.author) in #\(.channel): \(.content)"'
```

## Guidelines

- Log to both file and channel — files for long-term, channels for real-time staff awareness
- Use embed colors consistently: green=join, red=leave/delete, yellow=edit
- Truncate long content in embeds (1024 char limit per field)
- Include message IDs and user IDs in logs for cross-referencing
- Voice state logging can be noisy — consider only logging joins/leaves, not mute/deaf changes
- For large servers, write to file not channel to avoid rate limits
- Archive logs daily with date-stamped filenames
- Deleted message content may be `null` if the message wasn't cached
