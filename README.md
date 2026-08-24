<p align="center">
  <img src="https://raw.githubusercontent.com/DevRohit06/discli/9a0da5803f4de8b2609297d44514143833a0cfd2/docs/public/logo.svg" width="80" height="80" alt="discli logo" />
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

**Talk to Discord from your terminal.** Send messages, manage channels, run polls, watch live events, and build bots: all with one command-line tool that AI agents can drive too.

## Quick look

```bash
# Send a message
discli message send "#general" "Hello world"

# React, edit, delete, all from the terminal
discli reaction add "#general" 12345 "👍"
discli message edit "#general" 12345 "Hello, friends"

# Watch events as JSON, pipe into anything
discli --json listen --events messages

# Run a persistent bot driven by an AI agent
discli serve
```

Every command has a `--json` flag for scripts. Identifiers accept both names and IDs (`#general` or `123456789`, `alice` or her snowflake). One token, one CLI, no boilerplate.

## Connection model

One-shot commands use Discord's HTTP API and do not open a Gateway session or consume an `IDENTIFY`. This includes message, reaction, channel, role, member, thread, poll, webhook, event, DM, and typing commands.

Gateway connections are reserved for features that need live Discord state: `listen`, `serve`, and voice commands. These commands request only the intents required by their selected event types; discli does not use `Intents.all()`.

Some Discord HTTP endpoints and response fields are still restricted by application settings. For example, listing all guild members can require Server Members Intent, and reading arbitrary message content can require Message Content Intent. Those restrictions do not cause one-shot commands to open a Gateway connection.

## What you can do

- **Messages**: send, edit, delete, search, history, embeds, attachments, replies
- **Channels & roles**: create, edit, delete, list, get info
- **Members**: list, info, kick, ban, nickname, role assignment, move between voice channels
- **Threads**: create, list, archive, message inside
- **DMs**: send and read direct messages
- **Reactions & polls**: manage emoji reactions, run polls with multiple choices
- **Server admin**: edit name/icon/banner, read Discord's audit log, manage invites and custom emoji
- **Webhooks**: create, list, and post through them under a custom name and avatar
- **Live events**: `discli listen` streams every message, reaction, member event as JSONL
- **AI agents**: `discli serve` keeps a persistent bot open over stdin/stdout JSONL; drive it from Claude, OpenAI, LangChain, bash
- **Interactive components**: modals, multi-step workflows with state, persistent dashboards
- **Voice** *(optional extra)*: join voice channels, transcribe speech, TTS, audio playback, live meeting summaries
- **Doctor**: `discli doctor` verifies your setup in one command

## Install

```bash
pip install discord-cli-agent
```

Requires Python 3.10+. That's it for text features. No voice deps are pulled in unless you ask for them.

**Voice (optional):**

```bash
pip install 'discord-cli-agent[voice,deepgram]'
```

You'll also need **libopus** (`apt install libopus0` / `brew install opus`) and **ffmpeg** for playback. See [`docs/guides/voice.mdx`](docs/guides/voice.mdx) for the rest.

## Setup

1. Create a bot at [Discord Developer Portal](https://discord.com/developers/applications).
2. Enable privileged intents only when a selected feature needs them (Message Content for live message content, Members for member lists or name lookups). Standard intents such as Voice States are requested automatically by the relevant Gateway command.
3. Invite the bot to your server with the permissions you actually need.
4. Save your token:

   ```bash
   discli config set token YOUR_BOT_TOKEN
   ```

5. Verify everything works:

   ```bash
   discli doctor
   ```

   Doctor reports what's set up and what's missing. Optional features you haven't asked for stay silent.

## A bash agent in 8 lines

No Python required, just `jq` and `discli`:

```bash
discli --json listen --events messages | while read -r event; do
  mentions_bot=$(echo "$event" | jq -r '.mentions_bot')
  if [ "$mentions_bot" = "true" ]; then
    channel=$(echo "$event" | jq -r '.channel_id')
    msg=$(echo "$event" | jq -r '.message_id')
    discli message reply "$channel" "$msg" "Hello! How can I help?"
  fi
done
```

Pipe `discli --json listen` into any language. For richer bots, `discli serve` keeps a single Discord connection open and accepts 54 JSONL actions over stdin. See [Serve Mode](docs/guides/serve-mode.mdx).

## Drive it with Claude

The bundled [`examples/ai_serve_agent.py`](examples/ai_serve_agent.py) is a Claude agent that fully controls Discord: messages, embeds, buttons, selects, modals, channels, roles, polls, threads. @-mention the bot and ask in plain English:

```
@bot send a blue embed with title "Status" and fields Online=42, Messages=1337
@bot send 3 buttons: Accept (green), Decline (red), Maybe (grey)
@bot create a channel called announcements
@bot create a poll: "Best language?" with Python, Rust, Go
```

## Security & permissions

Four profiles control what an invocation can do:

| Profile | Description | Destructive ops |
|---------|-------------|-----------------|
| `full` | Everything (default) | yes |
| `moderation` | Everything including bans / kicks / role mgmt | yes |
| `chat` | Messages, reactions, threads, interactions | denied |
| `readonly` | List / info / get / search only | denied |

```bash
discli --profile chat message send "#general" "hi"     # ok
discli --profile chat channel delete announcements      # denied
```

Every destructive action is logged to `~/.discli/audit.log`. View with `discli audit show`. Built-in rate limiter (5 calls per 5s on destructive ops) keeps you from getting banned. Full security model: [`docs/architecture/security-model.mdx`](docs/architecture/security-model.mdx).

## Examples

| Example | What it does |
|---------|--------------|
| [`ai_serve_agent.py`](examples/ai_serve_agent.py) | **All-in-one Claude agent** with messages, buttons, selects, modals, embeds, streaming |
| [`claude_agent.py`](examples/claude_agent.py) | Smaller Claude agent driven by `@mention` |
| [`serve_bot.py`](examples/serve_bot.py) | Minimal echo bot using `discli serve` |
| [`component_test_bot.py`](examples/component_test_bot.py) | Buttons / selects / modals / embeds reference |
| [`moderation_bot.py`](examples/moderation_bot.py) | Keyword filter with warnings and kick escalation |
| [`support_agent.py`](examples/support_agent.py) | Rule-based support bot |
| [`thread_support_agent.py`](examples/thread_support_agent.py) | Thread-per-ticket helpdesk |
| [`meeting_transcriber.py`](examples/meeting_transcriber.py) | Voice channel transcript + Claude summary (requires `[voice]`) |
| [`channel_logger.sh`](examples/channel_logger.sh) | Log every message to a JSONL file |
| [`reaction_poll.sh`](examples/reaction_poll.sh) | Emoji reaction poll |

The full reference [`agents/discord-agent.md`](agents/discord-agent.md) drops into any LLM's system prompt: Claude, OpenAI, LangChain, anything that takes a prompt.

## Voice (optional)

discli also handles voice channels: joining, speaking via TTS, transcribing speech with streaming STT, and live meeting summaries.

```bash
discli voice join "general"
discli voice speak "joining the call now"
discli voice listen        # prints transcripts as people speak
```

Voice needs the `[voice]` extra plus a provider (`[deepgram]` / `[elevenlabs]` / `[openai-voice]`). Full walkthrough, including the DAVE encryption fix that makes listening work on modern Discord, lives in [`docs/guides/voice.mdx`](docs/guides/voice.mdx).

## Configuration

```bash
discli config set token YOUR_TOKEN
discli config show
```

Stored at `~/.discli/config.json`. Token resolution: `--token` flag → `DISCORD_BOT_TOKEN` env var → config file.

## Documentation

Full docs live in [`docs/`](docs/):

- [Installation](docs/getting-started/installation.mdx) · [Quickstart](docs/getting-started/quickstart.mdx) · [Configuration](docs/getting-started/configuration.mdx)
- Guides: [CLI Usage](docs/guides/cli-usage.mdx) · [Serve Mode](docs/guides/serve-mode.mdx) · [Components & Modals](docs/guides/components-modals.mdx) · [Voice](docs/guides/voice.mdx) · [Building Agents](docs/guides/building-agents.mdx)
- Reference: [CLI Commands](docs/reference/cli-commands.mdx) · [Serve Actions](docs/reference/serve-actions.mdx) · [Serve Events](docs/reference/serve-events.mdx) · [Permission Profiles](docs/reference/permission-profiles.mdx)
- [Troubleshooting](docs/troubleshooting/common-issues.mdx)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Tests run via `uv run pytest tests/`. Commits follow conventional commits (`feat:`, `fix:`, `docs:`, `chore:`).

## License

MIT. See [LICENSE](LICENSE).
