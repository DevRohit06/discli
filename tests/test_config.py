import json
import os
import stat
from pathlib import Path

import pytest

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


@pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions not applicable on Windows")
def test_save_config_restricts_permissions(tmp_path):
    config_dir = tmp_path / ".discli"
    config_path = config_dir / "config.json"
    save_config({"token": "secret-token"}, config_path)

    # Config file should be 0600 (read/write by owner only)
    file_mode = stat.S_IMODE(config_path.stat().st_mode)
    assert file_mode == 0o600

    # Config directory should be 0700 (read/write/exec by owner only)
    dir_mode = stat.S_IMODE(config_dir.stat().st_mode)
    assert dir_mode == 0o700


@pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions not applicable on Windows")
def test_save_config_tightens_existing_loose_permissions(tmp_path):
    config_dir = tmp_path / ".discli"
    config_dir.mkdir(mode=0o755)
    config_path = config_dir / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    config_path.chmod(0o644)

    save_config({"token": "secret-token"}, config_path)

    assert stat.S_IMODE(config_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(config_dir.stat().st_mode) == 0o700
