"""Tests for the Wave 2 pass: channel-visibility disclosure and the
permission-bitfield check in `discli doctor`.

The visibility note is deliberately written to stderr so that `--json`
stdout stays a clean, unchanged payload. These tests pin that contract --
if the note ever moves to stdout, the JSON parse here breaks.
"""

import json
from types import SimpleNamespace

import discord
import pytest
from click.testing import CliRunner

from discli.cli import main
from discli.utils import CHANNEL_VISIBILITY_NOTE


def _make_client(**attrs):
    class FakeClient:
        def __init__(self, *, intents):
            self.closed = False
            self.user = SimpleNamespace(id=999)

        async def login(self, token):
            pass

        async def start(self, token):
            raise AssertionError("one-shot commands must not start Gateway")

        async def close(self):
            self.closed = True

    for name, value in attrs.items():
        setattr(FakeClient, name, value)
    return FakeClient


def _coro(value):
    async def _inner():
        return value

    return _inner()


def _run(monkeypatch, client, argv, **kwargs):
    monkeypatch.setattr("discli.client.discord.Client", client)
    return CliRunner().invoke(main, ["--token", "token", *argv], **kwargs)


# ── channel visibility disclosure ──────────────────────────────────


class _FakeTextChannel(discord.TextChannel):
    """Bypass discord.py's __init__; only isinstance and attrs are used."""

    def __init__(self, channel_id, name):
        self.id = channel_id
        self.name = name

    @property
    def type(self):
        return discord.ChannelType.text


def _guild_with_channels(channels):
    class FakeGuild:
        name = "Test"
        id = 123

        async def fetch_channels(self):
            return channels

    return FakeGuild()


def test_channel_list_json_stdout_stays_parseable(monkeypatch):
    guild = _guild_with_channels([_FakeTextChannel(1, "general")])
    client = _make_client(fetch_guild=lambda self, gid: _coro(guild))

    result = _run(monkeypatch, client, ["--json", "channel", "list", "--server", "123"])

    assert result.exit_code == 0, result.output
    # The whole point of routing the note to stderr: this must not raise.
    data = json.loads(result.stdout)
    assert [c["name"] for c in data] == ["general"]
    assert CHANNEL_VISIBILITY_NOTE in result.stderr


def test_channel_list_plain_emits_note_on_stderr(monkeypatch):
    guild = _guild_with_channels([_FakeTextChannel(1, "general")])
    client = _make_client(fetch_guild=lambda self, gid: _coro(guild))

    result = _run(monkeypatch, client, ["channel", "list", "--server", "123"])

    assert result.exit_code == 0, result.output
    assert "#general" in result.stdout
    assert CHANNEL_VISIBILITY_NOTE not in result.stdout
    assert CHANNEL_VISIBILITY_NOTE in result.stderr


def test_channel_list_warns_even_when_empty(monkeypatch):
    """An empty list is exactly the case the note exists to explain."""
    guild = _guild_with_channels([])
    client = _make_client(fetch_guild=lambda self, gid: _coro(guild))

    result = _run(monkeypatch, client, ["channel", "list", "--server", "123"])

    assert result.exit_code == 0, result.output
    assert "No channels found." in result.stdout
    assert CHANNEL_VISIBILITY_NOTE in result.stderr


def test_server_info_emits_visibility_note(monkeypatch):
    import datetime

    class FakeGuild:
        id = 123
        name = "Test"
        owner_id = 0
        member_count = 5
        approximate_member_count = 5
        created_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)

        async def fetch_channels(self):
            return [_FakeTextChannel(1, "general")]

        async def fetch_roles(self):
            return []

    client = _make_client(fetch_guild=lambda self, gid: _coro(FakeGuild()))
    result = _run(monkeypatch, client, ["server", "info", "123"])

    assert result.exit_code == 0, result.output
    assert "channel_count: 1" in result.stdout
    assert CHANNEL_VISIBILITY_NOTE in result.stderr


# ── doctor permission bitfield ─────────────────────────────────────


def _doctor_client(perms, guild_name="Test"):
    class FakeGuild:
        name = guild_name
        id = 123

        async def fetch_member(self, member_id):
            assert member_id == 999
            return SimpleNamespace(guild_permissions=perms)

    return _make_client(fetch_guild=lambda self, gid: _coro(FakeGuild()))


def _run_doctor(monkeypatch, client, argv):
    monkeypatch.setattr("discli.client.discord.Client", client)
    # doctor reads the token from the environment, not the --token flag.
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    return CliRunner().invoke(main, argv)


def test_doctor_without_server_skips_permission_check(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    result = CliRunner().invoke(main, ["doctor"])

    assert result.exit_code == 0, result.output
    assert "PERMISSIONS" in result.output
    assert "[--] guild permissions" in result.output
    assert "pass --server" in result.output


def test_doctor_detects_pin_messages_regression(monkeypatch):
    # The exact shape of the problem: a bot invited before January 2026 holds
    # manage_messages and used to be able to pin. It no longer can.
    perms = discord.Permissions(manage_messages=True, view_channel=True)
    result = _run_doctor(monkeypatch, _doctor_client(perms), ["doctor", "--server", "123"])

    assert result.exit_code == 1, result.output
    assert "[FAIL] permission splits" in result.output
    assert "pin_messages" in result.output
    assert "message pin" in result.output
    assert "Re-invite" in result.output


def test_doctor_flags_both_manage_messages_splits(monkeypatch):
    perms = discord.Permissions(manage_messages=True)
    result = _run_doctor(monkeypatch, _doctor_client(perms), ["doctor", "--server", "123"])

    assert result.exit_code == 1, result.output
    assert "pin_messages" in result.output
    assert "bypass_slowmode" in result.output


def test_doctor_no_regression_when_legacy_permission_absent(monkeypatch):
    # Never had manage_messages, so losing the split-out bit costs nothing.
    perms = discord.Permissions(view_channel=True, send_messages=True)
    result = _run_doctor(monkeypatch, _doctor_client(perms), ["doctor", "--server", "123"])

    assert result.exit_code == 0, result.output
    assert "[ok] permission splits" in result.output
    assert "no regressions" in result.output


def test_doctor_no_regression_when_both_bits_present(monkeypatch):
    perms = discord.Permissions(
        manage_messages=True,
        pin_messages=True,
        bypass_slowmode=True,
    )
    result = _run_doctor(monkeypatch, _doctor_client(perms), ["doctor", "--server", "123"])

    assert result.exit_code == 0, result.output
    assert "[ok] permission splits" in result.output


def test_doctor_administrator_short_circuits(monkeypatch):
    perms = discord.Permissions(administrator=True)
    result = _run_doctor(monkeypatch, _doctor_client(perms), ["doctor", "--server", "123"])

    assert result.exit_code == 0, result.output
    assert "every permission is implied" in result.output
    # A split check would be meaningless under Administrator.
    assert "permission splits" not in result.output


def test_doctor_missing_permissions_are_informational_not_failures(monkeypatch):
    perms = discord.Permissions(view_channel=True)
    result = _run_doctor(monkeypatch, _doctor_client(perms), ["doctor", "--server", "123"])

    # Not holding manage_guild is only a problem if you wanted `server edit`,
    # which doctor cannot know -- so it must not fail the run.
    assert result.exit_code == 0, result.output
    assert "[ok] discli permissions" in result.output
    assert "not granted:" in result.output
    assert "manage_guild" in result.output


def test_doctor_reports_guild_name(monkeypatch):
    perms = discord.Permissions(administrator=True)
    client = _doctor_client(perms, guild_name="My Server")
    result = _run_doctor(monkeypatch, client, ["doctor", "--server", "123"])

    assert "My Server (ID: 123)" in result.output


def test_doctor_lookup_failure_is_a_check_not_a_traceback(monkeypatch):
    class FakeGuild:
        pass

    def _boom(self, gid):
        async def _inner():
            raise RuntimeError("guild is gone")

        return _inner()

    client = _make_client(fetch_guild=_boom)
    result = _run_doctor(monkeypatch, client, ["doctor", "--server", "123"])

    assert result.exit_code == 1, result.output
    assert "[FAIL] guild permissions" in result.output
    assert "lookup failed" in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_doctor_without_token_reports_check_not_crash(monkeypatch, tmp_path):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.setattr("discli.commands.doctor.load_config", lambda: {})

    result = CliRunner().invoke(main, ["doctor", "--server", "123"])

    assert "[FAIL] guild permissions" in result.output
    assert "no token configured" in result.output


def test_doctor_json_includes_permissions_section(monkeypatch):
    perms = discord.Permissions(administrator=True)
    result = _run_doctor(
        monkeypatch, _doctor_client(perms), ["--json", "doctor", "--server", "123"]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    names = [s["name"] for s in payload["sections"]]
    assert "PERMISSIONS" in names
    perms_section = next(s for s in payload["sections"] if s["name"] == "PERMISSIONS")
    assert any(c["name"] == "administrator" and c["ok"] for c in perms_section["checks"])


@pytest.mark.parametrize(
    "new_bit,legacy_bit",
    [
        ("pin_messages", "manage_messages"),
        ("bypass_slowmode", "manage_messages"),
        ("create_expressions", "manage_expressions"),
        ("create_events", "manage_events"),
    ],
)
def test_every_declared_split_is_a_real_permission(new_bit, legacy_bit):
    """Guard against a typo silently disabling a split check forever.

    getattr(perms, "typo", False) returns False, which would read as
    "permission absent" and quietly never fire.
    """
    perms = discord.Permissions()
    assert hasattr(perms, new_bit), f"{new_bit} is not a discord.py permission"
    assert hasattr(perms, legacy_bit), f"{legacy_bit} is not a discord.py permission"


def test_declared_discli_permissions_all_exist():
    from discli.commands.doctor import DISCLI_PERMISSIONS

    perms = discord.Permissions()
    unknown = [p for p in DISCLI_PERMISSIONS if not hasattr(perms, p)]
    assert not unknown, f"unknown permission names: {unknown}"
