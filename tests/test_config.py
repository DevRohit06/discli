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


@pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions not applicable on Windows")
def test_save_config_fchmod_before_write(tmp_path, monkeypatch):
    config_dir = tmp_path / ".discli"
    config_dir.mkdir(mode=0o700)
    config_path = config_dir / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    config_path.chmod(0o644)

    fchmod_invoked_on_empty = []
    real_fchmod = os.fchmod

    def spy_fchmod(fd, mode):
        # Modes must be tightened before secret content is written to disk
        if os.fstat(fd).st_size == 0:
            fchmod_invoked_on_empty.append(True)
        real_fchmod(fd, mode)

    monkeypatch.setattr(os, "fchmod", spy_fchmod)
    save_config({"token": "secret-token"}, config_path)

    assert fchmod_invoked_on_empty
    assert stat.S_IMODE(config_path.stat().st_mode) == 0o600
    assert load_config(config_path) == {"token": "secret-token"}


@pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions not applicable on Windows")
def test_save_config_warns_on_stderr_if_file_chmod_fails(tmp_path, monkeypatch, capsys):
    config_dir = tmp_path / ".discli"
    config_path = config_dir / "config.json"

    def fail_fchmod(fd, mode):
        raise OSError("Permission denied on fchmod")

    monkeypatch.setattr(os, "fchmod", fail_fchmod)
    save_config({"token": "secret-token"}, config_path)

    captured = capsys.readouterr()
    assert "could not set permissions" in captured.err
    assert "Permission denied on fchmod" in captured.err
    assert load_config(config_path) == {"token": "secret-token"}


@pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions not applicable on Windows")
def test_save_config_warns_on_stderr_if_dir_chmod_fails(tmp_path, monkeypatch, capsys):
    config_dir = tmp_path / ".discli"
    config_path = config_dir / "config.json"

    real_chmod = os.chmod

    def fail_dir_chmod(path, mode, **kwargs):
        if str(path) == str(config_dir):
            raise OSError("Permission denied on dir chmod")
        return real_chmod(path, mode, **kwargs)

    monkeypatch.setattr(os, "chmod", fail_dir_chmod)
    save_config({"token": "secret-token"}, config_path)

    captured = capsys.readouterr()
    assert "could not set permissions" in captured.err
    assert "Permission denied on dir chmod" in captured.err
    assert load_config(config_path) == {"token": "secret-token"}
