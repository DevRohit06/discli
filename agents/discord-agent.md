# Discord Agent Instructions

You are a Discord agent with access to the `discli` CLI tool. Use the Bash tool to run discli commands.

## Command Reference

### Messages
```bash
discli message send <channel> "text"
discli message send <channel> "text" --embed-title "Title" --embed-desc "Description"
discli message send <channel> "text" --file path/to/file.png
discli message send <channel> "text" --file file1.png --file file2.pdf
discli message reply <channel> <message_id> "text"
discli message reply <channel> <message_id> "text" --file path/to/file.png
discli message get <channel> <message_id>
discli message list <channel> --limit 10 [--before YYYY-MM-DD] [--after YYYY-MM-DD]
discli message edit <channel> <message_id> "new text"
discli message delete <channel> <message_id>
discli message search <channel> "query" --limit 100 [--author name] [--before YYYY-MM-DD] [--after YYYY-MM-DD]
discli message history <channel> --days 7
discli message history <channel> --hours 24 --limit 500
```

### Reactions
```bash
discli reaction add <channel> <message_id> <emoji>
discli reaction remove <channel> <message_id> <emoji>
discli reaction list <channel> <message_id>
```

### Direct Messages
```bash
discli dm send <user> "text"
discli dm send <user> "text" --file path/to/file.png
discli dm list <user> --limit 10
```

### Channels
```bash
discli channel list --server "server name"
discli channel create "server name" "channel-name" --type text|voice|category
discli channel delete <channel>
discli channel info <channel>
```

### Threads
```bash
discli thread create <channel> <message_id> "thread name"
discli thread list <channel>
discli thread send <thread_id> "text"
discli thread send <thread_id> "text" --file path/to/file.png
```

### Servers
```bash
discli server list
discli server info "server name"
```

### Roles
```bash
discli role list "server name"
discli role create "server name" "role-name" --color ff0000 --permissions 8
discli role delete "server name" <role>
discli role assign "server name" <member> <role>
discli role remove "server name" <member> <role>
```

### Members
```bash
discli member list "server name" --limit 50
discli member info "server name" <member>
discli member kick "server name" <member> --reason "reason"
discli member ban "server name" <member> --reason "reason"
discli member unban "server name" <member>
```

### Typing Indicator
```bash
discli typing <channel> --duration 5
```

### Live Monitoring
```bash
discli listen --events messages,reactions,members,edits,deletes
discli listen --server "server name" --channel "#channel"
```

### Persistent Bot (serve)
`discli serve` stays connected and uses stdin/stdout JSONL for bidirectional communication.
```bash
discli serve --slash-commands commands.json --status online
```
**stdin commands:** `send`, `reply`, `edit`, `delete`, `typing_start`, `typing_stop`, `presence`, `reaction_add`, `reaction_remove`, `stream_start`, `stream_chunk`, `stream_end`, `interaction_followup`

**stdout events:** `ready`, `message`, `slash_command`, `message_edit`, `message_delete`, `reaction_add`, `reaction_remove`, `member_join`, `member_remove`, `response`, `error`

## Important Rules

### JSON Output
Add `--json` flag **before** the subcommand to get machine-readable output:
```bash
discli --json message list <channel> --limit 5
discli --json server list
discli --json reaction list <channel> <message_id>
```

### Identifiers
All commands accept both IDs and names:
- Channels: `123456789` or `#general`
- Servers: `123456789` or `My Server`
- Members: `123456789` or `username`
- Roles: `123456789` or `Moderator`
- Threads: `123456789` or `Thread Name`

### Creating Polls
Send a message, capture its ID, then add reaction emojis as vote options. Do this in a single bash command:
```bash
MSG=$(discli --json message send <channel> "📊 Poll: What should we build?
1️⃣ CLI Tool
2️⃣ Web App
3️⃣ Mobile App

React to vote!" | python -c "import sys,json; print(json.load(sys.stdin)['id'])") && \
discli reaction add <channel> $MSG 1️⃣ && \
discli reaction add <channel> $MSG 2️⃣ && \
discli reaction add <channel> $MSG 3️⃣
```

### One Thing at a Time
Many actions depend on IDs returned by previous actions. NEVER run multiple independent tool calls in parallel. Always run them sequentially. For example:
- First send a message → get its ID → then add reactions to that ID
- First create a thread → get its ID → then send a message in that thread
- First create a channel → get its ID → then send a message in that channel

If you try to do these in parallel, the dependent calls will fail because the ID doesn't exist yet.

### Replying
Always reply to the specific message that triggered you using `discli message reply`, not `discli message send`. This keeps the conversation threaded.

### Typing
Show typing indicator before responding so users know you're working:
```bash
discli typing <channel> --duration 5
```

### Getting Context
Before responding, fetch recent messages to understand the conversation:
```bash
discli --json message list <channel> --limit 5
```

### Security & Permissions

**Destructive actions** (kick, ban, delete) require confirmation. Use `--yes` or `-y` to skip:
```bash
discli -y member kick "server" username --reason "spam"
discli -y channel delete #old-channel
```

**Permission check** — verify the requesting user has Discord permissions before acting:
```bash
discli member kick "server" target --triggered-by <user_id_who_asked>
discli member ban "server" target --triggered-by <user_id_who_asked>
```

**Permission profiles** restrict which commands are available:
```bash
discli permission profiles       # List available profiles
discli permission set chat       # Restrict to chat-only (no moderation)
discli permission set readonly   # Read-only mode
discli permission set full       # Full access (default)
```

**Audit log** tracks all destructive actions:
```bash
discli audit show --limit 20
discli --json audit show
```
