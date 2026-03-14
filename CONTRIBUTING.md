# Contributing to discli

Thanks for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/DevRohit06/discli.git
cd discli
pip install -e ".[dev]"
pytest tests/ -v
```

## Adding a New Command

1. Create a new file in `src/discli/commands/` (e.g. `webhook.py`)
2. Define a click group or command following existing patterns
3. Register it in `src/discli/cli.py`
4. Add tests in `tests/`
5. Update `agents/discord-agent.md` with the new command reference

## Running Tests

```bash
pytest tests/ -v
```

## Commit Style

Use conventional commits:

- `feat:` — new feature or command
- `fix:` — bug fix
- `docs:` — documentation only
- `chore:` — maintenance, deps, CI

## Releasing

Releases are automated via GitHub Actions. To release:

1. Bump version in `pyproject.toml`
2. Commit and push
3. Tag: `git tag v0.2.0 && git push origin v0.2.0`
4. CI builds, tests, creates GitHub Release, and publishes to PyPI
