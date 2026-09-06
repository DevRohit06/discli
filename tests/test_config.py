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


@pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions not applicable on Windows")
def test_save_config_refuses_rather_than_writing_the_token_unprotected(tmp_path, monkeypatch):
    """A failed open() must propagate, not fall back to a plain write.

    The fallback that used to live here wrote the token with whatever the
    umask gave it and said nothing, which is the exact exposure the rest of
    this function exists to prevent -- and it was invisible, because every
    other failure path in save_config warns on stderr.
    """
    config_path = tmp_path / ".discli" / "config.json"

    def refuse(*args, **kwargs):
        raise OSError("Permission denied on open")

    monkeypatch.setattr(os, "open", refuse)

    with pytest.raises(OSError):
        save_config({"token": "secret-token"}, config_path)

    assert not config_path.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions not applicable on Windows")
def test_save_config_releases_the_descriptor_if_it_cannot_be_wrapped(tmp_path, monkeypatch):
    """fdopen() failing is the one window where nothing else owns the fd."""
    config_path = tmp_path / ".discli" / "config.json"
    closed = []
    real_close = os.close

    def spy_close(fd):
        closed.append(fd)
        real_close(fd)

    def refuse(fd, *args, **kwargs):
        raise OSError("cannot wrap descriptor")

    monkeypatch.setattr(os, "close", spy_close)
    monkeypatch.setattr(os, "fdopen", refuse)

    with pytest.raises(OSError):
        save_config({"token": "secret-token"}, config_path)

    assert len(closed) == 1, "descriptor leaked when fdopen() failed"


@pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions not applicable on Windows")
def test_save_config_does_not_close_a_descriptor_the_file_object_owns(tmp_path, monkeypatch):
    """Once fdopen() returns, the file object closes the fd on its way out.

    Closing it a second time is not merely redundant: between the two calls
    another thread can open a file and be handed the same number, and the
    stray close takes that file down instead. serve.py runs threads.
    """
    config_path = tmp_path / ".discli" / "config.json"
    closed = []
    real_close = os.close
    real_fdopen = os.fdopen

    def spy_close(fd):
        closed.append(fd)
        real_close(fd)

    class ExplodesOnWrite:
        def __init__(self, handle):
            self._handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            self._handle.close()
            return False

        def write(self, _):
            raise OSError("No space left on device")

    monkeypatch.setattr(os, "close", spy_close)
    monkeypatch.setattr(os, "fdopen", lambda fd, *a, **k: ExplodesOnWrite(real_fdopen(fd, *a, **k)))

    with pytest.raises(OSError):
        save_config({"token": "secret-token"}, config_path)

    assert closed == [], "save_config closed a descriptor the file object already owns"
