# discli — Discord CLI for AI Agents

## Overview

A Python CLI that wraps Discord's Bot API, allowing AI agents and humans to manage Discord servers, send messages, react, and monitor events from the terminal.

## Tech Stack

- **Python 3.10+**
- **discord.py** — Discord API client
- **click** — CLI framework

## Architecture

### Authentication

Bot token resolved in order: `--token` flag → `DISCORD_BOT_TOKEN` env var → `~/.discli/config.json`.

### Client Pattern

- **Command-based actions:** Connect bot on `on_ready`, execute action, print output, disconnect.
- **Listen mode:** Bot stays connected, streams events to stdout.

### Project Structure

```
discli/
├── pyproject.toml
├── src/
│   └── discli/
│       ├── __init__.py
│       ├── cli.py              # root click group + config loading
│       ├── config.py           # token storage (~/.discli/config.json)
│       ├── client.py           # async discord.py wrapper
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── message.py      # message send/list/delete/edit
│       │   ├── reaction.py     # reaction add/remove/list
│       │   ├── channel.py      # channel create/delete/list/info
│       │   ├── server.py       # server list/info
│       │   ├── role.py         # role create/delete/assign/remove/list
│       │   ├── member.py       # member list/info/kick/ban/unban
│       │   ├── listen.py       # real-time event streaming
│       │   └── config_cmd.py   # config set/get/show
│       └── utils.py            # output formatting, resolvers
```

## Command Groups

```
discli config set token <value>
discli config show

discli message send <channel> <text> [--embed-title] [--embed-desc]
discli message list <channel> [--limit N]
discli message edit <channel> <message-id> <new-text>
discli message delete <channel> <message-id>

discli reaction add <channel> <message-id> <emoji>
discli reaction remove <channel> <message-id> <emoji>
discli reaction list <channel> <message-id>

discli channel list [--server <server>]
discli channel create <server> <name> [--type text|voice|category]
discli channel delete <channel>
discli channel info <channel>

discli server list
discli server info <server>

discli role list <server>
discli role create <server> <name> [--color] [--permissions]
discli role delete <server> <role>
discli role assign <server> <member> <role>
discli role remove <server> <member> <role>

discli member list <server> [--limit N]
discli member info <server> <member>
discli member kick <server> <member> [--reason]
discli member ban <server> <member> [--reason]
discli member unban <server> <member>

discli listen [--server <server>] [--channel <channel>] [--events messages,reactions,members]
```

### Channel/Server Resolution

Accept IDs directly or `#channel-name` / `server-name`. The CLI resolves names to IDs automatically.

## Output

- **Plain text (default):** Human-readable, one item per line.
- **JSON (`--json` flag):** Machine-readable output on every command.
- **Listen + `--json`:** JSONL format, one JSON object per line per event.
- **Exit codes:** 0 success, 1 error, 2 invalid usage.

## Dependencies

```toml
[project]
name = "discli"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "discord.py>=2.3",
    "click>=8.1",
]

[project.scripts]
discli = "discli.cli:main"
```

## Key Decisions

- **Intents:** Request all intents (privileged intents must be enabled in Discord developer portal).
- **Stateless:** No caching beyond what discord.py provides.
- **Error handling:** Discord API errors printed as clear CLI errors with exit code 1.
