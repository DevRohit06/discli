# Discord Agent Instructions

You are a Discord agent with access to the `discli` CLI tool. Use the Bash tool to run discli commands.

## Command Reference

### Messages
```bash
discli message send <channel> "text"
discli message send <channel> "text" --embed-title "Title" --embed-desc "Description"
discli message send <channel> "text" --embed-color ff0000 --embed-footer "Footer" --embed-image URL --embed-thumbnail URL --embed-author "Author" --embed-field "Name::Value::true"
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
discli message bulk-delete <channel> <msg_id1> <msg_id2> ...
```

### Reactions
```bash
discli reaction add <channel> <message_id> <emoji>
discli reaction remove <channel> <message_id> <emoji>
discli reaction list <channel> <message_id>
discli reaction users <channel> <message_id> <emoji> --limit 100
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
discli channel create "server" "forum-name" --type forum --topic "Forum topic"
discli channel edit <channel> --name new-name --topic "New topic" --slowmode 10 --nsfw
discli channel delete <channel>
discli channel info <channel>
discli channel forum-post <channel> "Post Title" "Post content"
discli channel set-permissions <channel> <role-or-member> --allow send_messages,read_messages --deny manage_messages --target-type role
```

### Threads
```bash
discli thread create <channel> <message_id> "thread name"
discli thread list <channel>
discli thread send <thread_id> "text"
discli thread send <thread_id> "text" --file path/to/file.png
discli thread archive <thread>
discli thread unarchive <thread>
discli thread rename <thread> "New Name"
discli thread add-member <thread> <member_id>
discli thread remove-member <thread> <member_id>
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
discli role edit "server name" "Role" --name "New Name" --color 00ff00 --hoist --mentionable
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
discli member timeout "server name" member 3600 --reason "Spam"
discli member timeout "server name" member 0    # remove timeout
```

### Typing Indicator
```bash
discli typing <channel> --duration 5
```

### Polls
```bash
discli poll results <channel> <message_id>
discli poll end <channel> <message_id>
```

### Webhooks
```bash
discli webhook list <channel>
discli webhook create <channel> "webhook-name"
discli webhook delete <channel> <webhook_id>
```

### Events
```bash
discli event list "server"
discli event create "server" "Event Name" "2026-04-01T18:00:00" --location "Park" --end-time "2026-04-01T20:00:00"
discli event create "server" "Voice Hangout" "2026-04-01T18:00:00" --channel #voice-room
discli event delete "server" <event_id>
```

### Live Monitoring
```bash
discli listen --events messages,reactions,members,edits,deletes,voice
discli listen --server "server name" --channel "#channel"
```

### Persistent Bot (serve)
`discli serve` stays connected and uses stdin/stdout JSONL for bidirectional communication.
```bash
discli serve --slash-commands commands.json --status online
```
**stdin commands:** `send`, `reply`, `edit`, `delete`, `typing_start`, `typing_stop`, `presence`, `reaction_add`, `reaction_remove`, `stream_start`, `stream_chunk`, `stream_end`, `interaction_followup`, `modal_send`, `channel_edit`, `channel_set_permissions`, `forum_post`, `thread_archive`, `thread_rename`, `thread_add_member`, `thread_remove_member`, `member_timeout`, `role_edit`, `reaction_users`, `poll_results`, `poll_end`, `webhook_list`, `webhook_create`, `webhook_delete`, `event_list`, `event_create`, `message_bulk_delete`

**stdin examples:**
```json
{"action": "send", "channel_id": "456", "content": "Hello!", "embed": {"title": "T", "description": "D", "color": "ff0000", "footer": "F", "fields": [{"name": "N", "value": "V", "inline": true}]}}
{"action": "send", "channel_id": "456", "content": "Click!", "components": [[{"type": "button", "label": "OK", "style": "primary", "custom_id": "ok_btn"}]]}
{"action": "modal_send", "interaction_token": "itk", "title": "Form", "custom_id": "myform", "fields": [{"label": "Name", "custom_id": "name", "style": "short"}]}
{"action": "channel_edit", "channel_id": "456", "topic": "New topic", "slowmode": 10}
{"action": "channel_set_permissions", "channel_id": "456", "target_id": "789", "target_type": "role", "allow": ["send_messages"], "deny": ["manage_messages"]}
{"action": "forum_post", "channel_id": "456", "title": "Post Title", "content": "Body"}
{"action": "thread_archive", "thread_id": "789", "archived": true}
{"action": "thread_rename", "thread_id": "789", "name": "New Name"}
{"action": "thread_add_member", "thread_id": "789", "member_id": "123"}
{"action": "thread_remove_member", "thread_id": "789", "member_id": "123"}
{"action": "member_timeout", "guild_id": "111", "member_id": "222", "duration": 3600, "reason": "Spam"}
{"action": "role_edit", "guild_id": "111", "role_id": "333", "name": "New Name", "color": "ff0000"}
{"action": "reaction_users", "channel_id": "456", "message_id": "789", "emoji": "👍"}
{"action": "poll_results", "channel_id": "456", "message_id": "789"}
{"action": "poll_end", "channel_id": "456", "message_id": "789"}
{"action": "webhook_list", "channel_id": "456"}
{"action": "webhook_create", "channel_id": "456", "name": "My Webhook"}
{"action": "webhook_delete", "channel_id": "456", "webhook_id": "999"}
{"action": "event_list", "guild_id": "111"}
{"action": "event_create", "guild_id": "111", "name": "Hangout", "start_time": "2026-04-01T18:00:00", "location": "Park", "end_time": "2026-04-01T20:00:00"}
{"action": "message_bulk_delete", "channel_id": "456", "message_ids": ["111", "222", "333"]}
```

**stdout events:** `ready`, `message`, `slash_command`, `message_edit`, `message_delete`, `reaction_add`, `reaction_remove`, `member_join`, `member_remove`, `voice_state`, `component_interaction`, `modal_submit`, `disconnected`, `resumed`, `response`, `error`

**stdout event examples:**
```json
{"event": "voice_state", "action": "joined", "member": "alice", "channel": "General", "channel_id": "456"}
{"event": "component_interaction", "custom_id": "ok_btn", "user": "alice", "interaction_token": "itk"}
{"event": "modal_submit", "custom_id": "myform", "fields": {"name": "Alice"}, "interaction_token": "itk"}
{"event": "disconnected"}
{"event": "resumed"}
```

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
Use `discli poll results` and `discli poll end` to check or close polls. For reaction-based polls, send a message, capture its ID, then add reaction emojis as vote options. Do this in a single bash command:
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
