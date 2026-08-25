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
discli message pin <channel> <message_id> [--reason "why"]
discli message unpin <channel> <message_id>
discli message pins <channel> --limit 50
discli message search-server "server name" "query"          # whole server, Discord's own index
discli message search-server "server" "outage" --author <user> --has file --sort-by relevance
discli message search-server "server" --channel #general --pinned --limit 25
```
Two different searches, on purpose:
- `message search <channel> "q"` scans one channel's recent history client-side (`--scan`, default 500).
  Works everywhere, but misses anything older than the scan window.
- `message search-server "server" "q"` uses Discord's native index: every channel the bot can see,
  relevance ranking, and filters (`--author`, `--author-type`, `--mentions`, `--has`, `--extension`,
  `--pinned`) the local scan cannot express. Prefer this one. It is a Discord preview feature, and
  reports the server as *unindexed* rather than empty when Discord has not finished indexing it.
Pinning needs the **Pin Messages** permission, which Discord split out of Manage Messages in January 2026.

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

**Channel listings are permission-scoped.** `channel list` and `server info` only report
channels the bot can view, and from 2026-11-16 Discord omits the rest from the API
entirely. Both write a one-line note to **stderr**; `--json` stdout is unaffected, so
parsing stays safe. Over `serve`, the `channel_list` response carries `visible_only: true`
instead. A short list may mean missing permissions, not an empty server.

### Scheduling
```bash
discli schedule add standup --action 'message send <channel> "Standup in 5"' --time 09:00 --tz America/New_York
discli schedule add digest --action 'server list' --every 6h --count 10
discli schedule list
discli schedule run-now standup       # fire once, right now
discli schedule remove standup
discli schedule run                   # foreground scheduler; runs until interrupted
```
Schedules live in `~/.discli/schedules.json`. Nothing fires until `discli schedule run` is running.

An `--action` is a **discli command line, not a shell command**. It is split with `shlex` and validated
against the real command tree when you add it, so typos surface immediately rather than at 3am. Shell
operators (`&&`, `|`, `;`, `>`, `$(...)`) are rejected because no shell is involved and they would be
passed through as literal arguments. Give either `--time HH:MM` (daily, `--tz` defaults to UTC) or
`--every 30s|15m|2h|1d`; the minimum interval is 30s.

### Diagnostics
```bash
discli --version                           # installed version, e.g. "discli version 0.11.0"
discli doctor                              # local checks only, no network
discli doctor --server "server name"       # also verifies the bot's real permissions
```
`--server` is the one networked check. It flags permissions Discord split out of
broader ones during 2026 (`PIN_MESSAGES`, `BYPASS_SLOWMODE`, `CREATE_GUILD_EXPRESSIONS`,
`CREATE_EVENTS`) — a bot invited before the split keeps the old bit and silently loses
the new capability. Run it first when a command fails with a 403.

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
discli server edit "server name" --name "New Name" --description "..." --icon icon.png --banner banner.png
discli server edit "server name" --verification-level high --system-channel #general
discli server audit-log "server name" --limit 50
discli server audit-log "server name" --action ban --user <member> --changes
discli server onboarding show "server name"
discli server onboarding edit "server name" --enable --mode advanced --default-channel #welcome
```
`server audit-log` reads **Discord's** log of who did what in the server (needs View Audit Log).
That is a different thing from `discli audit`, which shows what this CLI did locally.

### Roles
```bash
discli role list "server name"                       # member counts omitted by default
discli role list "server name" --with-member-counts  # one extra request; needs Manage Roles
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
discli member nick "server name" <member> "New Nickname"
discli member nick "server name" <member> --clear
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
discli webhook send <channel> <webhook_id_or_name> "text" [--username "Name"] [--avatar-url URL]
discli webhook send <channel> "announcer" "text" --embed-title "Title" --file report.pdf
discli webhook delete <channel> <webhook_id>
```
`webhook send` posts under a custom name and avatar without changing the bot's own identity.

### AutoMod
```bash
discli automod list "server name"
discli automod create "server" "no-links" --trigger keyword --keyword badword --action block
discli automod create "server" "raid-guard" --trigger mention-spam --mention-limit 5 --action timeout --timeout 600
discli automod create "server" "profanity" --trigger keyword-preset --preset profanity --action alert --alert-channel #mod-log
discli automod edit "server" "no-links" --keyword a --keyword b   # replaces the list, does not append
discli automod enable|disable "server" "no-links"
discli automod delete "server" "no-links"
```
A rule is one `--trigger` (what to detect) plus one or more `--action` (what to do).
Triggers: `keyword`, `spam`, `keyword-preset`, `mention-spam`, `member-profile`.
Actions: `block`, `alert` (needs `--alert-channel`), `timeout` (needs `--timeout`, max 28 days).
Options that do not belong to the chosen trigger are rejected rather than silently ignored.

### Server as code
```bash
discli server export "server name" --out prod.json     # roles, categories, channels, overwrites
discli server diff "server name" prod.json             # read-only
discli server apply "server name" prod.json --dry-run  # show the plan
discli server apply "server name" prod.json            # additive: create + update only
discli server apply "server name" prod.json --prune    # also delete what the spec omits (confirms first)
```
Three things to know before using this:
- **Matched by name, not ID** — that is what makes a spec portable to another server, but it
  also means a rename reads as "delete the old, create the new".
- **`apply` never deletes without `--prune`**, which prompts for confirmation.
- **A field the spec omits is left alone.** Trimming a spec to the few fields you care about
  does not blank out the rest.

Covers roles, categories, channels, and role permission overwrites. Not covered (each has its
own commands): members, messages, emoji, webhooks, invites, AutoMod. Positions are exported for
reference but never applied — Discord renumbers siblings on every positional write.

### Invites
```bash
discli invite list "server name"
discli invite info <code_or_url>
discli invite create <channel> --max-age 3600 --max-uses 5 --temporary
discli invite create <voice_channel> --activity <application_id>   # launches a Discord Activity
discli invite delete <code_or_url>
```
`--activity` takes a numeric application ID and only works on voice channels.

### Emoji
```bash
discli emoji list "server name"
discli emoji upload "server name" <name> path/to/image.png [--role "Role"]
discli emoji rename "server name" <emoji_name_or_id> <new_name>
discli emoji delete "server name" <emoji_name_or_id>
```
Images must be 256 KB or smaller. Uploading needs the **Create Expressions** permission,
which Discord split out of Manage Expressions in February 2026.
`emoji list` returns a `mention` field (`<:name:id>`) you can pass straight to `discli reaction add`.

### Events
```bash
discli event list "server"
discli event create "server" "Event Name" "2026-04-01T18:00:00" --location "Park" --end-time "2026-04-01T20:00:00"
discli event create "server" "Voice Hangout" "2026-04-01T18:00:00" --channel #voice-room
discli event delete "server" <event_id>
```

### Voice
```bash
discli voice join <voice_channel>
discli voice leave <voice_channel>
discli voice speak <voice_channel> "text" --tts elevenlabs|openai --voice "voice-id"
discli voice play <voice_channel> path/to/audio.mp3
discli voice stop <voice_channel>
discli voice pause <voice_channel>
discli voice resume <voice_channel>
discli voice listen <voice_channel> --stt deepgram|openai --duration 10
discli voice status <voice_channel>
discli voice config <voice_channel> --tts elevenlabs --stt deepgram --vad enabled
discli voice move "server name" <member> <voice_channel> [--reason "why"]
```
`voice move` relocates a **member** who is already connected to voice (needs Move Members).
It is plain HTTP -- no voice extras or ffmpeg required, unlike the commands above it.

### Interactive
```bash
discli interact modal <channel> <message_id> --title "Form" --custom-id "myform" --field "name::string::true" --field "email::string::true"
discli interact workflow <channel> <message_id> --workflow-id "workflow123"
discli interact dashboard <channel> --dashboard-id "dash1" --data '{"key": "value"}'
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
**stdin commands:** `send`, `reply`, `edit`, `delete`, `typing_start`, `typing_stop`, `presence`, `reaction_add`, `reaction_remove`, `stream_start`, `stream_chunk`, `stream_end`, `interaction_followup`, `modal_send`, `channel_edit`, `channel_set_permissions`, `forum_post`, `thread_archive`, `thread_rename`, `thread_add_member`, `thread_remove_member`, `member_timeout`, `role_edit`, `reaction_users`, `poll_results`, `poll_end`, `webhook_list`, `webhook_create`, `webhook_delete`, `event_list`, `event_create`, `message_bulk_delete`, `voice_connect`, `voice_disconnect`, `voice_move`, `voice_speak`, `voice_play`, `voice_stop`, `voice_pause`, `voice_resume`, `voice_listen_start`, `voice_listen_stop`, `voice_status`, `voice_set_config`, `workflow_start`, `workflow_cancel`, `dashboard_create`, `dashboard_update`, `dashboard_delete`

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
{"action": "voice_connect", "channel_id": "789"}
{"action": "voice_disconnect", "channel_id": "789"}
{"action": "voice_speak", "channel_id": "789", "text": "Hello everyone!", "tts": "elevenlabs", "voice": "alloy"}
{"action": "voice_play", "channel_id": "789", "audio_url": "https://example.com/audio.mp3"}
{"action": "voice_stop", "channel_id": "789"}
{"action": "voice_pause", "channel_id": "789"}
{"action": "voice_resume", "channel_id": "789"}
{"action": "voice_listen_start", "channel_id": "789", "stt": "deepgram", "duration": 30}
{"action": "voice_listen_stop", "channel_id": "789"}
{"action": "voice_status", "channel_id": "789"}
{"action": "voice_set_config", "channel_id": "789", "tts": "openai", "stt": "openai", "vad_enabled": true}
{"action": "workflow_start", "guild_id": "111", "workflow_id": "wf123", "context": {"key": "value"}}
{"action": "workflow_cancel", "guild_id": "111", "workflow_id": "wf123"}
{"action": "dashboard_create", "guild_id": "111", "dashboard_id": "dash1", "data": {"title": "Dashboard"}}
{"action": "dashboard_update", "guild_id": "111", "dashboard_id": "dash1", "data": {"title": "Updated Dashboard"}}
{"action": "dashboard_delete", "guild_id": "111", "dashboard_id": "dash1"}
```

**stdout events:** `ready`, `message`, `slash_command`, `message_edit`, `message_delete`, `reaction_add`, `reaction_remove`, `member_join`, `member_remove`, `voice_state`, `voice_speech_detected`, `voice_audio_received`, `component_interaction`, `modal_submit`, `workflow_event`, `dashboard_interaction`, `disconnected`, `resumed`, `response`, `error`

**stdout event examples:**
```json
{"event": "voice_state", "action": "joined", "member": "alice", "channel": "General", "channel_id": "456"}
{"event": "voice_speech_detected", "channel_id": "789", "text": "What's up?", "confidence": 0.95, "language": "en"}
{"event": "voice_audio_received", "channel_id": "789", "duration_ms": 2000, "member": "bob"}
{"event": "component_interaction", "custom_id": "ok_btn", "user": "alice", "interaction_token": "itk"}
{"event": "modal_submit", "custom_id": "myform", "fields": {"name": "Alice"}, "interaction_token": "itk"}
{"event": "workflow_event", "workflow_id": "wf123", "event_type": "step_completed", "data": {"step": "validate"}}
{"event": "dashboard_interaction", "dashboard_id": "dash1", "action": "button_click", "user": "charlie"}
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
