from click.testing import CliRunner
import discord

from discli.cli import main


def test_reaction_list_uses_http_without_gateway(monkeypatch):
    class FakeReaction:
        emoji = "ok"
        count = 3

    class FakeMessage:
        reactions = [FakeReaction()]

    class FakeChannel:
        async def fetch_message(self, message_id):
            assert message_id == 456
            return FakeMessage()

    class FakeClient:
        def __init__(self, *, intents):
            self.closed = False

        async def login(self, token):
            assert token == "token"

        async def fetch_channel(self, channel_id):
            assert channel_id == 123
            return FakeChannel()

        async def start(self, token):
            raise AssertionError("reaction list must not start Gateway")

        async def close(self):
            self.closed = True

    monkeypatch.setattr("discli.client.discord.Client", FakeClient)

    result = CliRunner().invoke(
        main,
        ["--token", "token", "reaction", "list", "123", "456"],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "ok x3\n"


class _FakeRoleResponse:
    """Minimal stand-in for discord's HTTP response to build discord.Forbidden."""

    status = 403
    reason = "Forbidden"
    headers = {}

    def json(self):
        return {"code": 50001, "message": "Missing Access"}

    @property
    def real_url(self):
        return "http://example.com"


class _FakeRole:
    def __init__(self, role_id, name):
        self.id = role_id
        self.name = name
        self.color = "#000000"


class _FakeMember:
    def __init__(self, role_ids):
        self.roles = [type("R", (), {"id": rid})() for rid in role_ids]


def _make_role_client(guild):
    class FakeClient:
        def __init__(self, *, intents):
            self.closed = False

        async def login(self, token):
            assert token == "token"

        async def fetch_guild(self, guild_id):
            assert guild_id == 123
            return guild

        async def start(self, token):
            raise AssertionError("role list must not start Gateway")

        async def close(self):
            self.closed = True

    return FakeClient


def test_role_list_skips_member_counts_by_default(monkeypatch):
    class FakeGuild:
        async def fetch_roles(self):
            return [_FakeRole(1, "Admin"), _FakeRole(2, "Mod")]

        async def fetch_members(self, limit=None):
            raise AssertionError("role list must not fetch members by default")
            yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr("discli.client.discord.Client", _make_role_client(FakeGuild()))

    result = CliRunner().invoke(
        main, ["--token", "token", "role", "list", "123"]
    )

    assert result.exit_code == 0, result.output
    assert "members: unavailable" in result.output
    assert "Admin (ID: 1" in result.output
    assert "Mod (ID: 2" in result.output


def test_role_list_with_member_counts(monkeypatch):
    class FakeGuild:
        async def fetch_roles(self):
            return [_FakeRole(1, "Admin"), _FakeRole(2, "Mod")]

        async def fetch_members(self, limit=None):
            yield _FakeMember([1])
            yield _FakeMember([1, 2])

    monkeypatch.setattr("discli.client.discord.Client", _make_role_client(FakeGuild()))

    result = CliRunner().invoke(
        main, ["--token", "token", "role", "list", "123", "--with-member-counts"]
    )

    assert result.exit_code == 0, result.output
    assert "Admin (ID: 1, color: #000000, members: 2)" in result.output
    assert "Mod (ID: 2, color: #000000, members: 1)" in result.output


def test_role_list_with_member_counts_forbidden_reports_unavailable(monkeypatch):
    class FakeGuild:
        async def fetch_roles(self):
            return [_FakeRole(1, "Admin"), _FakeRole(2, "Mod")]

        async def fetch_members(self, limit=None):
            raise discord.Forbidden(_FakeRoleResponse(), "Missing Access")
            yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr("discli.client.discord.Client", _make_role_client(FakeGuild()))

    result = CliRunner().invoke(
        main, ["--token", "token", "role", "list", "123", "--with-member-counts"]
    )

    assert result.exit_code == 0, result.output
    # Forbidden must surface as "unavailable", not 0, for every role.
    assert "members: 0" not in result.output
    assert result.output.count("members: unavailable") == 2
