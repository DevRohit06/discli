---
name: discord-slash-commands
description: "Generate Discord slash command definitions for discli. Creates the JSON file used by `discli serve --slash-commands`. Supports string, integer, number, boolean params with descriptions and optional flags."
---

# Discord Slash Command Generator

Generate slash command JSON definitions for use with `discli serve --slash-commands commands.json`.

## When to Use

Use this skill when the user wants to:
- Create slash commands for their Discord bot
- Generate the JSON file for `discli serve --slash-commands`
- Add new commands to an existing slash commands file
- Understand the slash command format

## JSON Format

```json
[
  {
    "name": "command-name",
    "description": "What this command does (shown in Discord UI)",
    "params": [
      {
        "name": "param_name",
        "type": "string",
        "description": "Shown as placeholder text",
        "required": true
      }
    ]
  }
]
```

### Rules
- `name`: lowercase, no spaces, max 32 chars. Use hyphens: `my-command`
- `description`: max 100 chars. Shown in Discord's command picker
- `params`: optional array. Each param has `name`, `type`, `description`
- `type`: one of `string`, `integer`, `number`, `boolean`
- `required`: defaults to `true`. Set `false` for optional params
- Max 25 commands per bot, max 25 params per command

## Common Patterns

### Simple command (no params)
```json
{"name": "ping", "description": "Check if the bot is alive"}
```

### Single required param
```json
{"name": "ask", "description": "Ask the bot a question", "params": [
  {"name": "question", "type": "string", "description": "Your question"}
]}
```

### Multiple params, some optional
```json
{"name": "remind", "description": "Set a reminder", "params": [
  {"name": "message", "type": "string", "description": "What to remind you about"},
  {"name": "minutes", "type": "integer", "description": "Minutes from now", "required": false}
]}
```

### Boolean flag
```json
{"name": "search", "description": "Search messages", "params": [
  {"name": "query", "type": "string", "description": "Search terms"},
  {"name": "include-bots", "type": "boolean", "description": "Include bot messages", "required": false}
]}
```

## Example: Full Bot Command Set

```json
[
  {"name": "help", "description": "Show available commands"},
  {"name": "ask", "description": "Ask the AI a question", "params": [
    {"name": "question", "type": "string", "description": "Your question"}
  ]},
  {"name": "summarize", "description": "Summarize recent conversation", "params": [
    {"name": "messages", "type": "integer", "description": "Number of messages to summarize", "required": false}
  ]},
  {"name": "translate", "description": "Translate text", "params": [
    {"name": "text", "type": "string", "description": "Text to translate"},
    {"name": "language", "type": "string", "description": "Target language"}
  ]},
  {"name": "poll", "description": "Create a quick poll", "params": [
    {"name": "question", "type": "string", "description": "Poll question"},
    {"name": "option1", "type": "string", "description": "First option"},
    {"name": "option2", "type": "string", "description": "Second option"},
    {"name": "option3", "type": "string", "description": "Third option (optional)", "required": false}
  ]},
  {"name": "config", "description": "Configure bot settings", "params": [
    {"name": "setting", "type": "string", "description": "Setting name"},
    {"name": "value", "type": "string", "description": "New value", "required": false}
  ]},
  {"name": "stats", "description": "Show server statistics"},
  {"name": "clear", "description": "Clear conversation history"}
]
```

## Handling in Python

```python
async def on_slash_command(event: dict, send) -> None:
    command = event["command"]
    args = event.get("args", {})
    token = event["interaction_token"]

    if command == "ask":
        question = args.get("question", "")
        # ... process question ...
        await send("interaction_followup", interaction_token=token, content=answer)

    elif command == "help":
        await send("interaction_followup", interaction_token=token,
                    content="Available commands: /ask, /help, /stats")
```

## Usage

Save the JSON to a file, then:
```bash
discli serve --slash-commands commands.json
```

Commands sync to all servers on bot startup. The `slash_commands_synced` event confirms completion.
