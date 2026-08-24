"""Tests for the commands added in the Wave 1 API-surface pass.

Every command here is one-shot REST, so each fake client asserts that
``start()`` is never called -- opening a Gateway session for these would
transmit intents and slow the command down.
"""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from discli.cli import main


@pytest.fixture(autouse=True)
def _no_audit_writes(monkeypatch):
    """Keep tests from appending to the real ~/.discli/audit.log."""
    monkeypatch.setattr("discli.security.audit_log", lambda *a, **k: None)


def _make_client(**attrs):
    """Build a REST-only fake client exposing the given resolver methods."""

    class FakeClient:
        def __init__(self, *, intents):
            self.closed = False

        async def login(self, token):
            assert token == "token"

        async def start(self, token):
            raise AssertionError("one-shot commands must not start Gateway")

        async def close(self):
            self.closed = True

    for name, value in attrs.items():
        setattr(FakeClient, name, value)
    return FakeClient


def _run(monkeypatch, client, argv):
    monkeypatch.setattr("discli.client.discord.Client", client)
    return CliRunner().invoke(main, ["--token", "token", *argv])


# ── message pin / unpin / pins ─────────────────────────────────────


class _FakeMessage:
    def __init__(self, message_id=456, content="hello"):
        self.id = message_id
        self.content = content
        self.author = "alice"
        self.created_at = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        self.jump_url = f"https://discord.com/channels/1/2/{message_id}"
        self.pinned_with = None
        self.unpinned_with = None

    async def pin(self, reason=None):
        self.pinned_with = reason

    async def unpin(self, reason=None):
        self.unpinned_with = reason


def test_message_pin(monkeypatch):
    msg = _FakeMessage()

    class FakeChannel:
        async def fetch_message(self, message_id):
            assert message_id == 456
            return msg

    client = _make_client(fetch_channel=lambda self, cid: _coro(FakeChannel()))
    result = _run(monkeypatch, client, ["message", "pin", "123", "456", "--reason", "important"])

    assert result.exit_code == 0, result.output
    assert "Pinned message 456" in result.output
    assert msg.pinned_with == "important"


def test_message_unpin(monkeypatch):
    msg = _FakeMessage()

    class FakeChannel:
        async def fetch_message(self, message_id):
            return msg

    client = _make_client(fetch_channel=lambda self, cid: _coro(FakeChannel()))
    result = _run(monkeypatch, client, ["message", "unpin", "123", "456", "--reason", "stale"])

    assert result.exit_code == 0, result.output
    assert "Unpinned message 456" in result.output
    assert msg.unpinned_with == "stale"


def test_message_pins_lists_pinned(monkeypatch):
    class FakeChannel:
        def pins(self, limit=50):
            assert limit == 10

            async def gen():
                yield _FakeMessage(1, "first")
                yield _FakeMessage(2, "second")

            return gen()

    client = _make_client(fetch_channel=lambda self, cid: _coro(FakeChannel()))
    result = _run(monkeypatch, client, ["--json", "message", "pins", "123", "--limit", "10"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert [p["content"] for p in data] == ["first", "second"]


# ── member nick ────────────────────────────────────────────────────


class _FakeMember:
    def __init__(self, nick="old"):
        self.id = 789
        self.nick = nick
        self.edited = {}

    def __str__(self):
        return "bob#0001"

    async def edit(self, **kwargs):
        self.edited = kwargs

    async def move_to(self, channel, reason=None):
        self.edited = {"voice_channel": channel, "reason": reason}


def _guild_client(guild):
    return _make_client(fetch_guild=lambda self, gid: _coro(guild))


def test_member_nick_sets(monkeypatch):
    member = _FakeMember()

    class FakeGuild:
        name = "Test"

        async def fetch_member(self, member_id):
            assert member_id == 789
            return member

    result = _run(
        monkeypatch,
        _guild_client(FakeGuild()),
        ["member", "nick", "123", "789", "newname"],
    )

    assert result.exit_code == 0, result.output
    assert "Set nickname for bob#0001 to 'newname'" in result.output
    assert member.edited["nick"] == "newname"


def test_member_nick_clear(monkeypatch):
    member = _FakeMember()

    class FakeGuild:
        name = "Test"

        async def fetch_member(self, member_id):
            return member

    result = _run(
        monkeypatch,
        _guild_client(FakeGuild()),
        ["member", "nick", "123", "789", "--clear"],
    )

    assert result.exit_code == 0, result.output
    assert "Cleared nickname for bob#0001" in result.output
    assert member.edited["nick"] is None


def test_member_nick_rejects_nickname_with_clear(monkeypatch):
    class FakeGuild:
        name = "Test"

    result = _run(
        monkeypatch,
        _guild_client(FakeGuild()),
        ["member", "nick", "123", "789", "newname", "--clear"],
    )

    assert result.exit_code != 0
    assert "not both" in result.output


def test_member_nick_requires_a_value(monkeypatch):
    class FakeGuild:
        name = "Test"

    result = _run(monkeypatch, _guild_client(FakeGuild()), ["member", "nick", "123", "789"])

    assert result.exit_code != 0
    assert "--clear" in result.output


# ── server audit-log / edit ────────────────────────────────────────


def _audit_entry():
    return SimpleNamespace(
        id=999,
        action=SimpleNamespace(name="channel_delete"),
        user="moderator#0002",
        user_id=42,
        target=SimpleNamespace(id=7, __str__=lambda self: "#general"),
        reason="spam",
        created_at=datetime(2026, 8, 25, 9, 30, tzinfo=timezone.utc),
        changes=SimpleNamespace(
            before=SimpleNamespace(name="general"),
            after=[("name", None)],
        ),
    )


def test_server_audit_log(monkeypatch):
    captured = {}

    class FakeGuild:
        name = "Test"

        def audit_logs(self, **kwargs):
            captured.update(kwargs)

            async def gen():
                yield _audit_entry()

            return gen()

    result = _run(
        monkeypatch,
        _guild_client(FakeGuild()),
        ["server", "audit-log", "123", "--limit", "5", "--action", "channel_delete"],
    )

    assert result.exit_code == 0, result.output
    assert captured["limit"] == 5
    assert captured["action"].name == "channel_delete"
    assert "moderator#0002 -> channel_delete" in result.output
    assert "spam" in result.output


def test_server_audit_log_rejects_unknown_action(monkeypatch):
    class FakeGuild:
        name = "Test"

    result = _run(
        monkeypatch,
        _guild_client(FakeGuild()),
        ["server", "audit-log", "123", "--action", "nonsense_action"],
    )

    assert result.exit_code != 0
    assert "Unknown audit action" in result.output


def test_server_audit_log_accepts_action_that_is_a_substring_of_others(monkeypatch):
    captured = {}

    class FakeGuild:
        name = "Test"

        def audit_logs(self, **kwargs):
            captured.update(kwargs)

            async def gen():
                if False:  # pragma: no cover - empty async generator
                    yield

            return gen()

    result = _run(
        monkeypatch,
        _guild_client(FakeGuild()),
        ["server", "audit-log", "123", "--action", "ban"],
    )

    # 'ban' is an exact member but also a substring of 'unban' and 'bot_add'
    # style names; the suggestion path must not swallow the exact match.
    assert result.exit_code == 0, result.output
    assert captured["action"].name == "ban"
    assert "No audit log entries." in result.output


def test_server_edit(monkeypatch):
    captured = {}

    class FakeGuild:
        id = 123
        name = "Test"

        async def edit(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(id=123, name=kwargs.get("name", "Test"))

    result = _run(
        monkeypatch,
        _guild_client(FakeGuild()),
        ["server", "edit", "123", "--name", "Renamed", "--verification-level", "high"],
    )

    assert result.exit_code == 0, result.output
    assert captured["name"] == "Renamed"
    assert captured["verification_level"].name == "high"
    assert "Updated Renamed" in result.output


def test_server_edit_requires_an_option(monkeypatch):
    class FakeGuild:
        name = "Test"

    result = _run(monkeypatch, _guild_client(FakeGuild()), ["server", "edit", "123"])

    assert result.exit_code != 0
    assert "Nothing to change" in result.output


# ── invite ─────────────────────────────────────────────────────────


def _fake_invite(code="abc123", **extra):
    base = dict(
        code=code,
        url=f"https://discord.gg/{code}",
        channel=SimpleNamespace(id=5, name="general"),
        guild=SimpleNamespace(name="Test"),
        inviter="alice#0001",
        uses=3,
        max_uses=10,
        max_age=0,
        temporary=False,
        created_at=None,
        expires_at=None,
        approximate_member_count=None,
        approximate_presence_count=None,
        target_type=None,
        target_application=None,
    )
    base.update(extra)
    return SimpleNamespace(**base)


def test_invite_list(monkeypatch):
    class FakeGuild:
        name = "Test"

        async def invites(self):
            return [_fake_invite()]

    result = _run(monkeypatch, _guild_client(FakeGuild()), ["invite", "list", "123"])

    assert result.exit_code == 0, result.output
    assert "https://discord.gg/abc123" in result.output
    assert "uses: 3/10" in result.output


def test_invite_create_with_activity(monkeypatch):
    import discord

    captured = {}

    class FakeVoiceChannel(discord.VoiceChannel):
        # Bypass discord.py's __init__; the command only needs isinstance and
        # create_invite, and VoiceChannel uses __slots__.
        def __init__(self):
            pass

        name = "Lounge"

        async def create_invite(self, **kwargs):
            captured.update(kwargs)
            return _fake_invite("act123")

    client = _make_client(fetch_channel=lambda self, cid: _coro(FakeVoiceChannel()))
    result = _run(
        monkeypatch,
        client,
        ["invite", "create", "555", "--activity", "880218394199220334"],
    )

    assert result.exit_code == 0, result.output
    assert captured["target_application_id"] == 880218394199220334
    assert captured["target_type"] is discord.InviteTarget.embedded_application


def test_invite_create_activity_rejects_text_channel(monkeypatch):
    class FakeTextChannel:
        name = "general"

        async def create_invite(self, **kwargs):
            raise AssertionError("must not reach Discord for an invalid channel type")

    client = _make_client(fetch_channel=lambda self, cid: _coro(FakeTextChannel()))
    result = _run(monkeypatch, client, ["invite", "create", "555", "--activity", "1234"])

    assert result.exit_code != 0
    assert "require a voice channel" in result.output


def test_invite_create_rejects_non_numeric_activity(monkeypatch):
    client = _make_client()
    result = _run(monkeypatch, client, ["invite", "create", "555", "--activity", "watch-together"])

    assert result.exit_code != 0
    assert "numeric application ID" in result.output


# ── emoji ──────────────────────────────────────────────────────────


class _FakeEmoji:
    def __init__(self, emoji_id=1, name="party", animated=False):
        self.id = emoji_id
        self.name = name
        self.animated = animated
        self.available = True
        self.managed = False
        self.url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png"

    def __str__(self):
        prefix = "a" if self.animated else ""
        return f"<{prefix}:{self.name}:{self.id}>"


def test_emoji_list(monkeypatch):
    class FakeGuild:
        name = "Test"

        async def fetch_emojis(self):
            return [_FakeEmoji(1, "party"), _FakeEmoji(2, "dance", animated=True)]

    result = _run(monkeypatch, _guild_client(FakeGuild()), ["emoji", "list", "123"])

    assert result.exit_code == 0, result.output
    assert "<:party:1>" in result.output
    assert "<a:dance:2>" in result.output
    assert "animated" in result.output


def test_emoji_upload(monkeypatch, tmp_path):
    image = tmp_path / "party.png"
    image.write_bytes(b"\x89PNG" + b"0" * 100)
    captured = {}

    class FakeGuild:
        name = "Test"

        async def create_custom_emoji(self, **kwargs):
            captured.update(kwargs)
            return _FakeEmoji(9, kwargs["name"])

    result = _run(
        monkeypatch,
        _guild_client(FakeGuild()),
        ["emoji", "upload", "123", "party", str(image)],
    )

    assert result.exit_code == 0, result.output
    assert captured["name"] == "party"
    assert captured["image"].startswith(b"\x89PNG")
    assert "<:party:9>" in result.output


def test_emoji_upload_rejects_oversized_image(monkeypatch, tmp_path):
    image = tmp_path / "big.png"
    image.write_bytes(b"0" * (256 * 1024 + 1))

    class FakeGuild:
        name = "Test"

        async def create_custom_emoji(self, **kwargs):
            raise AssertionError("oversized images must be rejected before upload")

    result = _run(
        monkeypatch,
        _guild_client(FakeGuild()),
        ["emoji", "upload", "123", "big", str(image)],
    )

    assert result.exit_code != 0
    assert "256 KB or smaller" in result.output


# ── webhook send ───────────────────────────────────────────────────


def test_webhook_send_by_name(monkeypatch):
    captured = {}

    class FakeWebhook:
        id = 77
        name = "announcer"

        async def send(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(id=888, content=kwargs["content"])

    class FakeChannel:
        name = "general"

        async def webhooks(self):
            return [FakeWebhook()]

    client = _make_client(fetch_channel=lambda self, cid: _coro(FakeChannel()))
    result = _run(
        monkeypatch,
        client,
        ["webhook", "send", "123", "announcer", "hello", "--username", "Deploy Bot"],
    )

    assert result.exit_code == 0, result.output
    assert captured["content"] == "hello"
    assert captured["username"] == "Deploy Bot"
    assert captured["wait"] is True
    assert "via webhook 'announcer'" in result.output


def test_webhook_send_unknown_webhook(monkeypatch):
    class FakeChannel:
        async def webhooks(self):
            return []

    client = _make_client(fetch_channel=lambda self, cid: _coro(FakeChannel()))
    result = _run(monkeypatch, client, ["webhook", "send", "123", "missing", "hi"])

    assert result.exit_code != 0
    assert "Webhook not found" in result.output


# ── voice move ─────────────────────────────────────────────────────


def test_voice_move(monkeypatch):
    import discord

    member = _FakeMember()

    class FakeVoiceChannel(discord.VoiceChannel):
        def __init__(self):
            pass

        id = 321
        name = "Lounge"

    target = FakeVoiceChannel()

    class FakeGuild:
        name = "Test"

        async def fetch_member(self, member_id):
            return member

        async def fetch_channels(self):
            return [target]

    result = _run(
        monkeypatch,
        _guild_client(FakeGuild()),
        ["voice", "move", "123", "789", "Lounge"],
    )

    assert result.exit_code == 0, result.output
    assert member.edited["voice_channel"] is target
    assert "Moved bob#0001 to voice channel #Lounge" in result.output


def test_voice_move_unknown_channel(monkeypatch):
    class FakeGuild:
        name = "Test"

        async def fetch_member(self, member_id):
            return _FakeMember()

        async def fetch_channels(self):
            return []

    result = _run(
        monkeypatch,
        _guild_client(FakeGuild()),
        ["voice", "move", "123", "789", "Nowhere"],
    )

    assert result.exit_code != 0
    assert "Voice channel not found" in result.output


def _coro(value):
    """Wrap a value in an awaitable, for fakes standing in for async methods."""

    async def _inner():
        return value

    return _inner()


def test_server_audit_log_normalises_dashed_action(monkeypatch):
    captured = {}

    class FakeGuild:
        name = "Test"

        def audit_logs(self, **kwargs):
            captured.update(kwargs)

            async def gen():
                if False:  # pragma: no cover - empty async generator
                    yield

            return gen()

    result = _run(
        monkeypatch,
        _guild_client(FakeGuild()),
        ["server", "audit-log", "123", "--action", "channel-delete"],
    )

    assert result.exit_code == 0, result.output
    assert captured["action"].name == "channel_delete"
