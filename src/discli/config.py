import json
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".discli" / "config.json"


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_config(data: dict, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_config(path)
    existing.update(data)
    path.write_text(json.dumps(existing, indent=2))
