import json
import os
import sys
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".discli" / "config.json"


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
            sys.stderr.write(f"Warning: could not set permissions on {path.parent}: {exc}\n")
            sys.stderr.flush()

    existing = load_config(path)
    existing.update(data)
    content = json.dumps(existing, indent=2) + "\n"

    if os.name != "nt":
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        try:
            fd = os.open(path, flags, 0o600)
        except OSError:
            path.write_text(content, encoding="utf-8")
            return

        try:
            try:
                os.fchmod(fd, 0o600)
            except OSError as exc:
                sys.stderr.write(f"Warning: could not set permissions on {path}: {exc}\n")
                sys.stderr.flush()
            with open(fd, "w", encoding="utf-8") as f:
                f.write(content)
            return
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            raise

    path.write_text(content, encoding="utf-8")
