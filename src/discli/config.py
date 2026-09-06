import json
import os
import sys
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".discli" / "config.json"


def _warn(message: str) -> None:
    sys.stderr.write(f"Warning: {message}\n")
    sys.stderr.flush()


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_config(data: dict, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            path.parent.chmod(0o700)
        except OSError as exc:
            _warn(f"could not set permissions on {path.parent}: {exc}")

    existing = load_config(path)
    existing.update(data)
    content = json.dumps(existing, indent=2) + "\n"

    if os.name == "nt":
        path.write_text(content, encoding="utf-8")
        return

    # O_CREAT's mode argument is ignored when the file already exists, so an
    # inherited 0644 config would survive the write. fchmod() after the
    # O_TRUNC is what actually tightens it -- and it runs while the file is
    # still empty, so the secret is never on disk at the looser mode.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
    except OSError as exc:
        # Worth continuing: a token in a loose-moded file still beats no
        # token at all, as long as the weakened guarantee is not silent.
        _warn(f"could not set permissions on {path}: {exc}")

    try:
        handle = os.fdopen(fd, "w", encoding="utf-8")
    except BaseException:
        # The only window where nothing else owns the descriptor. Once
        # fdopen() returns, the file object owns it and closing here too
        # would be a double close -- which is not merely redundant: a
        # concurrent thread can claim the number in between and lose its
        # own file.
        os.close(fd)
        raise
    with handle:
        handle.write(content)
