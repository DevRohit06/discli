# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

discli is a Discord CLI for AI agents and humans — a Python command-line tool for managing Discord servers, messages, reactions, threads, DMs, events, voice audio, and rich interactive components (modals, workflows, dashboards) from the terminal. Published on PyPI as `discord-cli-agent`.

## Commands

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Install (editable, with dev deps) — creates .venv/ automatically
uv sync --dev

# Install with voice features (TTS/STT providers)
uv sync --dev --extra voice --extra elevenlabs --extra deepgram

# Run tests
uv run pytest tests/ -v

# Run a single test
uv run pytest tests/test_utils.py -v

# Run the CLI
uv run discli --help

# Build package
uv build
```

No linter is configured. Commit style: conventional commits (`feat:`, `fix:`, `docs:`, `chore:`).

There is no pytest config, and `asyncio_mode` is unset, so async tests need explicit `@pytest.mark.asyncio`. `tests/conftest.py` holds one autouse fixture, `no_network`, which patches `discord.http.HTTPClient.request`/`static_login` to raise — without it a test that drives the CLI end to end falls back to the developer's own token in `~/.discli/config.json` and makes live API calls that pass locally and fail in CI. `tests/test_examples.py` imports and executes every file in `examples/`, so a broken example breaks the suite.

## Environment Variables

- `DISCORD_BOT_TOKEN` — bot token (Click `envvar`, also read by `client.py`)
- `DISCLI_TTS` / `DISCLI_STT` / `DISCLI_TTS_VOICE` — provider selection
- `DISCLI_DEEPGRAM_MODEL` (default `nova-3`), `DISCLI_DEEPGRAM_LANGUAGE` (default `multi`)
- `ELEVENLABS_API_KEY`, `DEEPGRAM_API_KEY`, `OPENAI_API_KEY` — provider credentials

Note: `examples/meeting_transcriber.py` reads `DISCORD_TOKEN`, not `DISCORD_BOT_TOKEN`.

## Gotchas

- `discord-ext-voice-recv==0.5.2a179` is an exact pin — do not bump. See the justification comment in `pyproject.toml` (0.4.x lacks the required cipher; 0.5.0a167 has a circular import; 0.5.1a170 doesn't deliver audio).
- Voice requires **ffmpeg on PATH** and the DAVE encryption patch. Run `discli doctor` first when voice misbehaves.
- `audioop-lts` is a conditional dep for Python ≥3.13 (stdlib `audioop` removal).
- Intents are only sent on the Gateway path (`listen`, `serve`, `voice`). One-shot commands use `run_rest()` and transmit no intents. Missing privileged intents fail the whole Gateway connection (`PrivilegedIntentsRequired`) but only fail individual REST calls with a 403.
- `run_rest_action()` sets `Intents.members = True` on the login-only client. That flag never reaches Discord — it exists to defeat discord.py's *client-side* guard in `Guild.fetch_members()`, which raises `ClientException` (a sibling of `HTTPException`, so no handler catches it) before any request goes out. Do not "clean this up" to `Intents.none()`.
- Channel listings are scoped to what the bot can view, and from **2026-11-16** Discord drops channels without `VIEW_CHANNEL` from `GET /guilds/{id}/channels` and the Gateway entirely. No API reports how many were withheld. `channel list` and `server info` disclose this via `warn_channel_visibility()` on **stderr** — deliberately not stdout, so `--json` payloads stay parseable. `serve`'s `channel_list` sets `visible_only: true` in-band instead, because JSONL has no stderr equivalent.
- Discord split `PIN_MESSAGES`, `BYPASS_SLOWMODE`, `CREATE_GUILD_EXPRESSIONS`, and `CREATE_EVENTS` out of broader permissions during 2026. A bot invited before the split keeps the old bit and silently loses the new capability. `discli doctor --server <name>` detects exactly that case (holds legacy bit, lacks split bit); see `PERMISSION_SPLITS` in `commands/doctor.py`.
- `message search-server` calls `GET /guilds/{id}/messages/search` through a raw `discord.http.Route`, because discord.py 2.7.1 does not wrap that endpoint. Going through `Route` keeps it inside discord.py's rate limiter and auth. Discord answers **202 with no `messages` key** while it is still indexing a guild — treating that as an empty result set would report a wrong answer rather than a slow one.
- `schedule` actions are discli command lines, never shell commands. `parse_action()` lexes with `shlex(punctuation_chars=True)` so `;` and `&&` become their own tokens, then walks the real Click tree. Backticks and `$` are deliberately *not* rejected — no shell is involved, and a message containing backtick-wrapped code formatting is ordinary Discord content.
- Scheduled actions run via `asyncio.to_thread`: discli commands call `asyncio.run()` internally, which raises if invoked from the scheduler's own running event loop.
- `tzdata` is a Windows-only conditional dep. Windows ships no IANA tz database, so `schedule --tz` would otherwise raise `ZoneInfoNotFoundError`.

## Architecture

**Entry point:** `src/discli/cli.py` → Click root group → registers all command groups.

**Core flow:** Click CLI → permission/audit check (security.py) → `run_rest()` for one-shot HTTP actions or `run_gateway()` for live state → async discord.py action → `output()` (utils.py).

**Key modules:**
- `client.py` — Token resolution, REST/Gateway lifecycle separation, and minimal Gateway intent construction
- `security.py` — Permission profiles (full/chat/readonly/moderation), audit logging to `~/.discli/audit.log` (JSONL), token-bucket rate limiter
- `utils.py` — Output formatting plus async, cache-first resource resolvers with REST fallbacks
- `config.py` — Token storage at `~/.discli/config.json`
- `voice_engine.py` — VoiceEngine with AudioPlayer, AudioListener, VAD-based speech segmentation, audio codec handling
- `interact_engine.py` — InteractEngine for modals, workflows, and dashboards with interaction routing and state management
- `tts.py` — TTS provider protocol with ElevenLabs and OpenAI implementations
- `stt.py` — STT provider protocol with Deepgram and OpenAI Whisper implementations
- `commands/schedule.py` — `discli schedule`, recurring discli commands stored in `~/.discli/schedules.json`; `schedule run` drives them with `discord.ext.tasks`
- `commands/doctor.py` — `discli doctor`, the first-stop diagnostic: checks token, ffmpeg on PATH, DAVE/Opus voice patches, provider API keys. All local unless `--server` is passed, which adds the network permission-bitfield check

The `permission` and `audit` command groups are defined inline in `cli.py`, not in `commands/`.

**Command pattern:** Each module in `commands/` defines Click commands and an async action. One-shot commands call `run_rest(ctx, action)`. Only live events, voice state, and persistent connections call `run_gateway(ctx, action, features=...)` or manage a long-lived Gateway client directly.

**`serve` command (commands/serve.py):** The largest module (~2100 lines). Runs a persistent bot with bidirectional JSONL over stdin/stdout. Features: event forwarding, action dispatch (send/reply/edit/delete/stream/typing/reactions/threads/polls/channels/members/roles/DMs), voice actions (connect/speak/play/listen/etc.), interactive actions (workflows, dashboards), slash command registration, streaming message edits with periodic flush, Windows-compatible stdin reading via threading.

## Adding a New Command

1. Create file in `src/discli/commands/`
2. Define Click group/command following existing patterns
3. Register in `src/discli/cli.py`
4. Add tests in `tests/`
5. Update `agents/discord-agent.md` with command reference
6. Update the relevant `skills/*/SKILL.md` if the command appears there (7 skills ship in `skills/`)

## Docs Development

```bash
# Start docs dev server (Lito, Astro-based)
npx @litodocs/cli dev -i ./docs

# Build docs for production
npx @litodocs/cli build -i ./docs -o ./docs/dist
```

Docs live in `docs/` — Lito framework with `docs-config.json` for sidebar/theme. Custom landing page in `docs/_landing/`.

## Release Process

Bump version in `pyproject.toml` → commit → `git tag vX.Y.Z && git push origin vX.Y.Z` → CI runs tests (Python 3.10–3.13), builds, creates GitHub Release, publishes to PyPI.

**There is no CI on pushes or PRs** — tests run only on `v*` tags, so run `uv run pytest tests/ -v` locally before pushing. The docs workflow is path-filtered to `docs/**` on `main`.
