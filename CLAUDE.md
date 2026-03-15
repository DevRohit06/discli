# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

discli is a Discord CLI for AI agents and humans — a Python command-line tool for managing Discord servers, messages, reactions, threads, DMs, and events from the terminal. Published on PyPI as `discord-cli-agent`.

## Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run a single test
pytest tests/test_utils.py -v

# Build package
python -m build
```

No linter is configured. Commit style: conventional commits (`feat:`, `fix:`, `docs:`, `chore:`).

## Architecture

**Entry point:** `src/discli/cli.py` → Click root group → registers all command groups.

**Core flow:** Click CLI → permission/audit check (security.py) → `run_discord()` (client.py) → async discord.py action → `output()` (utils.py).

**Key modules:**
- `client.py` — Token resolution (flag → env var → config file), `run_discord()` sync wrapper around async Discord actions
- `security.py` — Permission profiles (full/chat/readonly/moderation), audit logging to `~/.discli/audit.log` (JSONL), token-bucket rate limiter
- `utils.py` — Output formatting (text/JSON via `--json` flag), channel/guild resolvers
- `config.py` — Token storage at `~/.discli/config.json`

**Command pattern:** Each module in `commands/` defines Click commands, takes an async action function, and calls `run_discord(ctx, action)`. Follow existing modules when adding new commands.

**`serve` command (commands/serve.py):** The largest module (~1100 lines). Runs a persistent bot with bidirectional JSONL over stdin/stdout. Features: event forwarding, action dispatch (send/reply/edit/delete/stream/typing/reactions/threads/polls/channels/members/roles/DMs), slash command registration, streaming message edits with periodic flush, Windows-compatible stdin reading via threading.

## Adding a New Command

1. Create file in `src/discli/commands/`
2. Define Click group/command following existing patterns
3. Register in `src/discli/cli.py`
4. Add tests in `tests/`
5. Update `agents/discord-agent.md` with command reference

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
