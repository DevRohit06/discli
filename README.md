<p align="center">
  <img src="docs/public/logo.svg" width="80" height="80" alt="discli logo" />
</p>
<h1 align="center">discli</h1>
<p align="center">Discord CLI for AI agents and humans</p>

<p align="center">
  <a href="https://pypi.org/project/discord-cli-agent/"><img src="https://img.shields.io/pypi/v/discord-cli-agent?color=blue&label=PyPI" alt="PyPI"></a>
  <a href="https://pypi.org/project/discord-cli-agent/"><img src="https://img.shields.io/pypi/pyversions/discord-cli-agent" alt="Python"></a>
  <a href="https://github.com/DevRohit06/discli/actions/workflows/release.yml"><img src="https://github.com/DevRohit06/discli/actions/workflows/release.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/DevRohit06/discli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/DevRohit06/discli" alt="License"></a>
  <a href="https://github.com/DevRohit06/discli/releases"><img src="https://img.shields.io/github/v/release/DevRohit06/discli?label=Latest" alt="Release"></a>
  <a href="https://github.com/DevRohit06/discli/stargazers"><img src="https://img.shields.io/github/stars/DevRohit06/discli" alt="Stars"></a>
  <a href="https://www.producthunt.com/products/discli/discli/launch-day?utm_source=badge"><img src="https://img.shields.io/badge/Product%20Hunt-Launch%20Day-%23DA552F?logo=producthunt&logoColor=white" alt="Product Hunt"></a>
</p>

---

Manage Discord servers, send messages, react, handle DMs, threads, and monitor events, all from the terminal. Built with security and AI agent integration in mind.

## How it works

```mermaid
graph TD
    A[discli CLI] --> B[Commands]
    A --> C[Listen]
    A --> D[Security]

    B --> |fire & exit| E[discord.py]
    C --> |stay connected| E

    D --> D1[Permission Profiles]
    D --> D2[Audit Logging]
    D --> D3[Rate Limiting]
    D --> D4[User Permission Check]

    E --> F[Discord Bot API]

    style A fill:#5865F2,color:#fff
    style F fill:#5865F2,color:#fff
    style D fill:#ED4245,color:#fff
```

```mermaid
graph LR
    A[discli serve] -->|stdout JSONL| B[AI Agent\ne.g. Claude]
    B -->|stdin JSONL| A
    A <-->|persistent| C[Discord Bot API]

    style A fill:#5865F2,color:#fff
    style B fill:#D97706,color:#fff
    style C fill:#5865F2,color:#fff
```

```mermaid
graph TD
    subgraph Security Layer
        P[Permission Profiles] --> |full / chat / readonly| CHECK{Allowed?}
        CHECK --> |Yes| EXEC[Execute Command]
        CHECK --> |No| DENY[Deny + Log]
        EXEC --> CONFIRM{Destructive?}
        CONFIRM --> |Yes| PROMPT[Confirm or --yes]
        CONFIRM --> |No| RUN[Run]
        PROMPT --> RUN
        RUN --> AUDIT[Audit Log]
        RUN --> RATE[Rate Limiter]
    end

    style P fill:#ED4245,color:#fff
    style DENY fill:#ED4245,color:#fff
    style AUDIT fill:#57F287,color:#000
```

## Install

```bash
# macOS/Linux
curl -fsSL https://raw.githubusercontent.com/DevRohit06/discli/main/installers/install.sh | bash

# Windows (PowerShell)
irm https://raw.githubusercontent.com/DevRohit06/discli/main/installers/install.ps1 | iex
```

Or with pip:

```bash
pip install discord-cli-agent
```

Requires Python 3.10+.

## Setup

1. Create a bot at [Discord Developer Portal](https://discord.com/developers/applications)
2. Enable **all privileged intents** (Presence, Server Members, Message Content)
3. Add the bot to your server with appropriate permissions
4. Configure your token:

```bash
# Option A: Save to config
discli config set token YOUR_BOT_TOKEN

# Option B: Environment variable
export DISCORD_BOT_TOKEN=YOUR_BOT_TOKEN

# Option C: Pass directly
discli --token YOUR_BOT_TOKEN server list
```

## Usage

Every command supports `--json` for machine-readable output.

### Messages

```bash
discli message send #general "Hello world!"
discli message send #general "Check this out" --embed-title "News" --embed-desc "Big update"
discli message send #general "Alert" --embed-color ff0000 --embed-footer "Footer" --embed-field "Name::Value::true"
discli message bulk-delete #general 111 222 333
discli message send #general "Here's the report" --file report.pdf
discli message send #general "Screenshots" --file bug.png --file logs.txt
discli message list #general --limit 20
discli message list #general --after 2026-03-01 --before 2026-03-14
discli message get #general 123456789
discli message reply #general 123456789 "Here you go" --file fix.patch
discli message edit #general 123456789 "Updated text"
discli message delete #general 123456789
```

### Search & History

```bash
# Search messages by content
discli message search #general "bug report" --limit 100
discli message search #general "help" --author alice --after 2026-03-01

# Deep history backfill
discli message history #general --days 7
discli message history #general --hours 24 --limit 500
```

### Direct Messages

```bash
discli dm send alice "Hey, need help?"
discli dm send alice "Check this file" --file notes.pdf
discli dm send 123456789 "Sent by user ID"
discli dm list alice --limit 10
```

### Reactions

```bash
discli reaction add #general 123456789 👍
discli reaction remove #general 123456789 👍
discli reaction list #general 123456789
discli reaction users #general 123456789 👍 --limit 100
```

### Channels

```bash
discli channel list --server "My Server"
discli channel create "My Server" new-channel --type text
discli channel create "My Server" voice-room --type voice
discli channel info #general
discli channel edit #general --name new-name --topic "New topic" --slowmode 10
discli channel create "My Server" "forum-name" --type forum --topic "Forum topic"
discli channel forum-post #forum-channel "Post Title" "Post content"
discli channel set-permissions #general @Moderator --allow send_messages,read_messages --deny manage_messages --target-type role
discli channel delete #old-channel
```

### Threads

```bash
discli thread create #general 123456789 "Support Ticket"
discli thread list #general
discli thread send 987654321 "Following up on your issue"
discli thread send 987654321 "Attached the logs" --file debug.log
discli thread archive 987654321
discli thread unarchive 987654321
discli thread rename 987654321 "New Thread Name"
discli thread add-member 987654321 123456789
discli thread remove-member 987654321 123456789
```

### Servers

```bash
discli server list
discli server info "My Server"
```

### Roles

```bash
discli role list "My Server"
discli role create "My Server" Moderator --color ff0000
discli role assign "My Server" alice Moderator
discli role remove "My Server" alice Moderator
discli role edit "My Server" Moderator --name "Senior Mod" --color 00ff00 --hoist --mentionable
discli role delete "My Server" Moderator
```

### Members

```bash
discli member list "My Server" --limit 100
discli member info "My Server" alice
discli member kick "My Server" alice --reason "Spam"
discli member ban "My Server" alice --reason "Repeated violations"
discli member unban "My Server" alice
discli member timeout "My Server" alice 3600 --reason "Spam"
discli member timeout "My Server" alice 0    # remove timeout
```

### Polls

```bash
discli poll results #general 123456789
discli poll end #general 123456789
```

### Webhooks

```bash
discli webhook list #general
discli webhook create #general "my-webhook"
discli webhook delete #general 123456789
```

### Events

```bash
discli event list "My Server"
discli event create "My Server" "Game Night" "2026-04-01T18:00:00" --location "Park" --end-time "2026-04-01T20:00:00"
discli event create "My Server" "Voice Hangout" "2026-04-01T18:00:00" --channel #voice-room
discli event delete "My Server" 123456789
```

### Typing Indicator

```bash
discli typing #general                # 5 seconds (default)
discli typing #general --duration 10  # 10 seconds
```

### Live Event Monitoring

```bash
# Listen to everything
discli listen

# Filter by server/channel
discli listen --server "My Server" --channel #general

# Filter by event type
discli listen --events messages,reactions,voice

# Include bot messages (ignored by default)
discli listen --include-bots

# JSON output for piping to an agent
discli --json listen --events messages
```

Supported event types: `messages`, `reactions`, `members`, `edits`, `deletes`, `voice`

### Persistent Bot (serve)

`discli serve` keeps a persistent connection and communicates via stdin/stdout JSONL — ideal for building full Discord bots.

```bash
# Start with slash commands and presence
discli serve --slash-commands commands.json --status online --activity playing --activity-text "Helping"

# Filter by server
discli serve --server "My Server"
```

**Events (stdout):**
```json
{"event": "ready", "bot_id": "123", "bot_name": "MyBot#1234"}
{"event": "message", "channel_id": "456", "author": "alice", "content": "hello", "mentions_bot": true, ...}
{"event": "slash_command", "command": "paw", "args": {"message": "hi"}, "interaction_token": "abc123", ...}
{"event": "voice_state", "action": "joined", "member": "alice", "channel": "General", "channel_id": "456"}
{"event": "component_interaction", "custom_id": "ok_btn", "user": "alice", "interaction_token": "itk"}
{"event": "modal_submit", "custom_id": "myform", "fields": {"name": "Alice"}, "interaction_token": "itk"}
```

**Commands (stdin):**
```json
{"action": "send", "channel_id": "456", "content": "Hello!", "req_id": "1"}
{"action": "send", "channel_id": "456", "content": "Rich!", "embed": {"title": "T", "description": "D", "color": "ff0000"}}
{"action": "send", "channel_id": "456", "content": "Click!", "components": [[{"type": "button", "label": "OK", "style": "primary", "custom_id": "ok_btn"}]]}
{"action": "reply", "channel_id": "456", "message_id": "789", "content": "Hi!", "req_id": "2"}
{"action": "typing_start", "channel_id": "456"}
{"action": "typing_stop", "channel_id": "456"}
{"action": "presence", "status": "idle", "activity_type": "watching", "activity_text": "the logs"}
{"action": "channel_edit", "channel_id": "456", "topic": "New topic", "slowmode": 10}
{"action": "forum_post", "channel_id": "456", "title": "Post Title", "content": "Body"}
{"action": "webhook_create", "channel_id": "456", "name": "My Webhook"}
{"action": "event_create", "guild_id": "111", "name": "Hangout", "start_time": "2026-04-01T18:00:00"}
```

**Streaming edits** (bot response builds in real-time, edited every 1.5s):
```json
{"action": "stream_start", "channel_id": "456", "reply_to": "789"}
{"action": "stream_chunk", "stream_id": "s1", "content": "new tokens..."}
{"action": "stream_end", "stream_id": "s1"}
```

**Slash commands** are defined in a JSON file:
```json
[
  {"name": "paw", "description": "Talk to the bot", "params": [{"name": "message", "type": "string"}]},
  {"name": "new", "description": "Start a new session"}
]
```

## Security & Permissions

### Confirmation Prompts

Destructive actions (kick, ban, delete) require confirmation by default:

```bash
$ discli member kick "My Server" spammer
Warning: Destructive action: member kick (spammer from My Server). Continue? [y/N]

# Skip with --yes for automation
$ discli -y member kick "My Server" spammer --reason "Spam"
```

### Permission Profiles

Restrict which commands an agent can use:

```bash
# List available profiles
discli permission profiles

# Set a profile (persisted)
discli permission set chat        # Messages, reactions, threads only, no moderation
discli permission set readonly    # Can only read, no sending or deleting
discli permission set moderation  # Full access including kick/ban
discli permission set full        # Everything (default)

# Override per invocation (not persisted)
discli --profile chat message send #general "hello"
DISCLI_PROFILE=readonly discli message list #general
```

| Profile | Can Send | Can Delete | Can Kick/Ban | Can Manage Channels |
|---------|----------|------------|--------------|---------------------|
| `full` | Yes | Yes | Yes | Yes |
| `moderation` | Yes | Yes | Yes | Yes |
| `chat` | Yes | No | No | No |
| `readonly` | No | No | No | No |

### User Permission Checking

Verify the Discord user who triggered an action actually has the required permissions:

```bash
discli member kick "My Server" target --triggered-by 123456789
```

This checks that user `123456789` has `kick_members` permission in the server. Server owners and administrators always pass. If the user can't be found in cache, it fetches from the API. If that also fails, it warns but doesn't block.

### Audit Log

Every destructive action is logged to `~/.discli/audit.log`:

```bash
# View recent actions
discli audit show --limit 20

# JSON output
discli --json audit show

# Clear the log
discli audit clear
```

### Rate Limiting

Built-in rate limiter (5 calls per 5 seconds) on destructive actions to prevent Discord API bans. If the limit is hit, discli waits automatically.

## Resolving Identifiers

All commands accept both **IDs** and **names**:

| Type | By ID | By Name |
|------|-------|---------|
| Channel | `123456789` | `#general` |
| Server | `123456789` | `My Server` |
| Member | `123456789` | `alice` |
| Role | `123456789` | `Moderator` |
| Thread | `123456789` | `Support Ticket` |
| User (DM) | `123456789` | `alice` |

## JSON Output

Add `--json` **before the subcommand** for machine-readable output:

```bash
$ discli --json message list #general --limit 1
[
  {
    "id": "123456789",
    "author": "alice",
    "content": "Hello!",
    "timestamp": "2026-03-14T10:32:00+00:00",
    "attachments": [],
    "embeds": []
  }
]

$ discli --json listen --events messages
{"event": "message", "server": "My Server", "channel": "general", "channel_id": "111", "author": "alice", "author_id": "222", "content": "hello", "message_id": "333", "mentions_bot": false, "attachments": []}
```

## Examples

### AI Agent (recommended)

The all-in-one AI agent uses Claude Agent SDK + `discli serve` for full Discord control — messages, embeds, buttons, selects, modals, streaming, channels, roles, and more:

```bash
pip install discord-cli-agent claude-agent-sdk
discli config set token YOUR_BOT_TOKEN
python examples/ai_serve_agent.py
```

Then @mention the bot in Discord:
```
@bot send a blue embed with title "Status" and fields Online=42, Messages=1337
@bot send 3 buttons: Accept (green), Decline (red), Maybe (grey)
@bot send a color picker dropdown with Red, Blue, Green
@bot send a button that opens a feedback form with Name and Message fields
@bot create a channel called announcements
@bot list all roles
@bot create a poll: "Best language?" with Python, Rust, Go
```

Uses your existing Claude Code authentication. No API key needed.

### All Examples

| Example | Description |
|---------|-------------|
| [`ai_serve_agent.py`](examples/ai_serve_agent.py) | **All-in-one AI agent** — Claude + serve mode, buttons, selects, modals, embeds, streaming |
| [`component_test_bot.py`](examples/component_test_bot.py) | Interactive component test bot — buttons, selects, modals, embeds, streaming |
| [`serve_bot.py`](examples/serve_bot.py) | Echo bot using `discli serve` with streaming and slash commands |
| [`claude_agent.py`](examples/claude_agent.py) | Lightweight AI agent using Claude Agent SDK + `discli listen` |
| [`moderation_bot.py`](examples/moderation_bot.py) | Keyword filter with warnings and kick escalation |
| [`support_agent.py`](examples/support_agent.py) | Rule-based support bot that replies to @mentions |
| [`thread_support_agent.py`](examples/thread_support_agent.py) | Thread-per-ticket support system |
| [`channel_logger.sh`](examples/channel_logger.sh) | Log messages to JSONL file |
| [`reaction_poll.sh`](examples/reaction_poll.sh) | Emoji reaction poll |

### Agent Instructions

The [`agents/discord-agent.md`](agents/discord-agent.md) file contains the full discli command reference for AI agents. Drop it into any agent's system prompt. Works with Claude, OpenAI, LangChain, or any framework.

### Claude Code Skills

Install skills for building Discord bots with discli:

```bash
npx skills add DevRohit06/discli@discord-bot          # Bot scaffolding + JSONL reference
npx skills add DevRohit06/discli@discord-agent         # AI agent patterns (Claude/OpenAI)
npx skills add DevRohit06/discli@discord-moderation    # Auto-mod, keyword filtering
npx skills add DevRohit06/discli@discord-support-bot   # Helpdesk, thread-per-ticket
npx skills add DevRohit06/discli@discord-welcome       # Onboarding, role buttons
npx skills add DevRohit06/discli@discord-logger        # Activity logging, analytics
npx skills add DevRohit06/discli@discord-slash-commands # Slash command generator
```

### Quick start: Bash agent

```bash
discli --json listen --events messages | while read -r event; do
  mentions_bot=$(echo "$event" | jq -r '.mentions_bot')
  if [ "$mentions_bot" = "true" ]; then
    channel_id=$(echo "$event" | jq -r '.channel_id')
    message_id=$(echo "$event" | jq -r '.message_id')
    discli typing "$channel_id" --duration 3 &
    discli message reply "$channel_id" "$message_id" "Hello! How can I help?"
  fi
done
```

## Project Structure

```
discli/
├── src/discli/
│   ├── cli.py           # Root click group + permission/audit commands
│   ├── client.py        # Async discord.py wrapper
│   ├── config.py        # Token storage (~/.discli/config.json)
│   ├── security.py      # Permissions, audit logging, rate limiting
│   ├── utils.py         # Output formatting, resolvers
│   └── commands/        # Command groups (message, channel, serve, etc.)
├── agents/
│   └── discord-agent.md # Full command reference for AI agents
├── skills/              # Claude Code skills for skills.sh
├── examples/            # Ready-to-run agent examples
├── installers/          # curl-friendly install scripts
├── tests/               # Unit tests
└── pyproject.toml
```

## Configuration

Config is stored at `~/.discli/config.json`.

```bash
discli config set token YOUR_TOKEN
discli config show
discli config show --json
```

Token resolution order: `--token` flag > `DISCORD_BOT_TOKEN` env var > config file.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, how to add commands, and release process.

## License

MIT
