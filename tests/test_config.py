import json
from pathlib import Path

from discli.config import load_config, save_config


def test_save_and_load_config(tmp_path):
    config_path = tmp_path / "config.json"
    save_config({"token": "test-token-123"}, config_path)
    loaded = load_config(config_path)
    assert loaded["token"] == "test-token-123"


def test_load_missing_config(tmp_path):
    config_path = tmp_path / "nonexistent.json"
    loaded = load_config(config_path)
    assert loaded == {}
