---
name: discord-welcome
description: "Build Discord welcome/onboarding bots with discli. Greet new members with embeds, assign roles automatically, send DM onboarding flows, create introduction threads, and track member joins/leaves."
---

# Discord Welcome & Onboarding Bot Builder

Build bots that welcome new members, handle onboarding flows, auto-assign roles, and track member activity using discli.

## When to Use

Use this skill when the user wants to:
- Greet new members with a welcome message
- Auto-assign roles to new members
- Send DM onboarding sequences
- Create introduction threads for new members
- Track member joins and leaves
- Build a role-selection system with buttons

## Pattern 1: Welcome Message with Embed

```python
WELCOME_CHANNEL_ID = "YOUR_CHANNEL_ID"

async def on_member_join(event: dict, send) -> None:
    member = event["member"]
    member_id = event["member_id"]
    server = event["server"]

    await send("send", channel_id=WELCOME_CHANNEL_ID,
               content=f"Welcome to {server}, {member}! 🎉",
               embed={
                   "title": f"Welcome, {member}!",
                   "description": (
                       "We're glad to have you here. Here's how to get started:\n\n"
                       "1. Read the rules in #rules\n"
                       "2. Pick your roles in #roles\n"
                       "3. Introduce yourself in #introductions\n"
                       "4. Ask questions in #help"
                   ),
                   "color": "57F287",
                   "thumbnail": f"https://cdn.discordapp.com/avatars/{member_id}/default.png",
                   "footer": f"Member #{event.get('server_id', 'N/A')}",
               })
```

## Pattern 2: Auto-Role Assignment

```python
DEFAULT_ROLE_ID = "YOUR_ROLE_ID"  # e.g., "Member" role

async def on_member_join(event: dict, send) -> None:
    member_id = event["member_id"]
    guild_id = event["server_id"]

    # Assign default role
    await send("role_assign",
               guild_id=guild_id,
               member_id=member_id,
               role_id=DEFAULT_ROLE_ID)

    # Welcome in channel
    await send("send", channel_id=WELCOME_CHANNEL_ID,
               content=f"<@{member_id}> has joined and been given the Member role!")
```

## Pattern 3: DM Onboarding Flow

```python
async def on_member_join(event: dict, send) -> None:
    member_id = event["member_id"]
    server = event["server"]

    # Send DM welcome
    await send("dm_send", user_id=member_id,
               content=f"Welcome to **{server}**! Here are some things to know:")

    # Follow up with server-specific info
    await send("dm_send", user_id=member_id,
               content="",
               embed={
                   "title": "Getting Started",
                   "color": "5865F2",
                   "fields": [
                       {"name": "📜 Rules", "value": "Please read #rules before chatting", "inline": False},
                       {"name": "🎭 Roles", "value": "Use the /roles command to pick your interests", "inline": False},
                       {"name": "❓ Help", "value": "Ask in #help or DM a moderator", "inline": False},
                   ],
               })
```

## Pattern 4: Role Selection with Buttons

```python
ROLE_MENU_CHANNEL_ID = "YOUR_CHANNEL_ID"

ROLES = {
    "role_dev": {"name": "Developer", "role_id": "111", "emoji": "💻"},
    "role_design": {"name": "Designer", "role_id": "222", "emoji": "🎨"},
    "role_gamer": {"name": "Gamer", "role_id": "333", "emoji": "🎮"},
    "role_music": {"name": "Music", "role_id": "444", "emoji": "🎵"},
}


async def send_role_menu(send) -> None:
    """Send the role selection message with buttons."""
    components = [[
        {
            "type": "button",
            "label": f"{info['emoji']} {info['name']}",
            "style": "secondary",
            "custom_id": custom_id,
        }
        for custom_id, info in ROLES.items()
    ]]

    await send("send", channel_id=ROLE_MENU_CHANNEL_ID,
               content="",
               embed={
                   "title": "Pick Your Roles",
                   "description": "Click the buttons below to toggle roles:",
                   "color": "5865F2",
               },
               components=components)


async def on_component(event: dict, send) -> None:
    """Handle role button clicks."""
    custom_id = event.get("custom_id")
    if custom_id not in ROLES:
        return

    role_info = ROLES[custom_id]
    guild_id = event["guild_id"]
    user_id = event["user_id"]

    # Toggle role — try to add, if already has it, remove
    # Check current roles via member_info first
    await send("role_assign",
               guild_id=guild_id,
               member_id=user_id,
               role_id=role_info["role_id"])

    await send("interaction_followup",
               interaction_token=event["interaction_token"],
               content=f"Toggled role: **{role_info['name']}** {role_info['emoji']}")
```

## Pattern 5: Introduction Thread

```python
INTRO_CHANNEL_ID = "YOUR_CHANNEL_ID"

async def on_member_join(event: dict, send) -> None:
    member = event["member"]
    member_id = event["member_id"]

    # Create introduction thread for the new member
    await send("send", channel_id=INTRO_CHANNEL_ID,
               content=f"<@{member_id}> just joined! Say hi 👋")

    # The message_id will come back in the response — use it to create thread
    # For simplicity, send a standalone thread:
    await send("thread_create",
               channel_id=INTRO_CHANNEL_ID,
               name=f"Welcome {member}!",
               content=f"Hey {member}! Tell us about yourself:\n\n"
                       f"- What brings you here?\n"
                       f"- What are your interests?\n"
                       f"- Anything you'd like to share?")
```

## Pattern 6: Join/Leave Logging

```python
LOG_CHANNEL_ID = "YOUR_LOG_CHANNEL_ID"

async def handle_event(event: dict, send) -> None:
    etype = event.get("event")

    if etype == "member_join":
        await send("send", channel_id=LOG_CHANNEL_ID, embed={
            "title": "Member Joined",
            "description": f"**{event['member']}** (ID: {event['member_id']})",
            "color": "57F287",
            "footer": event.get("server", ""),
        })
        await on_member_join(event, send)

    elif etype == "member_remove":
        await send("send", channel_id=LOG_CHANNEL_ID, embed={
            "title": "Member Left",
            "description": f"**{event['member']}** (ID: {event['member_id']})",
            "color": "ED4245",
            "footer": event.get("server", ""),
        })
```

## Slash Commands for Onboarding

```json
[
  {"name": "roles", "description": "Show the role selection menu"},
  {"name": "intro", "description": "Start your introduction"},
  {"name": "rules", "description": "Show server rules"},
  {"name": "help", "description": "Get help navigating the server"}
]
```

## Guidelines

- Welcome messages should be warm but concise
- DM onboarding can fail if user has DMs disabled — handle gracefully
- Auto-role assignment requires the bot's role to be higher than the assigned role
- Use embeds for visual welcome messages — they stand out
- Don't spam new members — one welcome message is enough
- Log joins/leaves in a staff-only channel for moderation awareness
- Role buttons are better UX than reaction roles (no need to scroll up)
- Rate-limit welcome messages during raids (many joins in short window)
