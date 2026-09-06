import click
import discord
import pytest

from discli.client import (
    build_gateway_intents,
    gateway_features_for_events,
    resolve_token,
    run_gateway_action,
    run_rest_action,
)
from discli.utils import resolve_member


def test_resolve_token_from_arg():
    assert resolve_token("my-token", {}) == "my-token"


def test_resolve_token_from_config():
    assert resolve_token(None, {"token": "config-token"}) == "config-token"


def test_resolve_token_from_discord_token(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "token-from-discord-token")
    assert resolve_token(None, {}) == "token-from-discord-token"


def test_resolve_token_prefers_config_over_discord_token(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "fallback-token")
    assert resolve_token(None, {"token": "config-token"}) == "config-token"


def test_resolve_token_missing():
    with pytest.raises(click.ClickException) as excinfo:
        resolve_token(None, {})
    assert "DISCORD_BOT_TOKEN" in str(excinfo.value)
    assert "DISCORD_TOKEN" in str(excinfo.value)


def test_cli_resolves_token_from_discord_token(monkeypatch):
    from click.testing import CliRunner
    from discli.cli import main

    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.setenv("DISCORD_TOKEN", "token-from-discord-token")
    monkeypatch.setattr("discli.cli.load_config", lambda: {})

    captured = {}

    def fake_action(ctx, action):
        captured["token"] = ctx.obj["token"]

    monkeypatch.setattr("discli.commands.channel.run_rest", fake_action)

    result = CliRunner().invoke(main, ["channel", "list"])
    assert result.exit_code == 0
    assert captured.get("token") == "token-from-discord-token"


def test_cli_prefers_config_token_over_discord_token(monkeypatch):
    from click.testing import CliRunner
    from discli.cli import main

    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.setenv("DISCORD_TOKEN", "fallback-token")
    monkeypatch.setattr("discli.cli.load_config", lambda: {"token": "config-token"})

    captured = {}

    def fake_action(ctx, action):
        captured["token"] = ctx.obj["token"]

    monkeypatch.setattr("discli.commands.channel.run_rest", fake_action)

    result = CliRunner().invoke(main, ["channel", "list"])
    assert result.exit_code == 0
    assert captured.get("token") == "config-token"


def test_cli_prefers_discord_bot_token_over_all(monkeypatch):
    from click.testing import CliRunner
    from discli.cli import main

    monkeypatch.setenv("DISCORD_BOT_TOKEN", "bot-token-primary")
    monkeypatch.setenv("DISCORD_TOKEN", "fallback-token")
    monkeypatch.setattr("discli.cli.load_config", lambda: {"token": "config-token"})

    captured = {}

    def fake_action(ctx, action):
        captured["token"] = ctx.obj["token"]

    monkeypatch.setattr("discli.commands.channel.run_rest", fake_action)

    result = CliRunner().invoke(main, ["channel", "list"])
    assert result.exit_code == 0
    assert captured.get("token") == "bot-token-primary"


def test_build_gateway_intents_requests_only_selected_features():
    intents = build_gateway_intents({"reactions", "voice"})

    assert intents.guilds
    assert intents.guild_reactions
    assert intents.dm_reactions
    assert intents.guild_messages
    assert intents.dm_messages
    assert intents.voice_states
    assert not intents.message_content
    assert not intents.members
    assert not intents.presences


def test_gateway_features_for_filtered_events():
    assert gateway_features_for_events({"reactions", "voice"}) == {
        "reactions",
        "voice",
    }


def test_gateway_features_for_all_events():
    assert gateway_features_for_events(None) == {
        "messages",
        "reactions",
        "members",
        "voice",
    }


@pytest.mark.asyncio
async def test_run_rest_action_logs_in_without_starting_gateway(monkeypatch):
    class FakeClient:
        def __init__(self, *, intents):
            self.intents = intents
            self.logged_in = False
            self.closed = False

        async def login(self, token):
            assert token == "token"
            self.logged_in = True

        async def start(self, token):
            raise AssertionError("REST actions must not start Gateway")

        async def close(self):
            self.closed = True

    fake_client = None

    def make_client(*, intents):
        nonlocal fake_client
        fake_client = FakeClient(intents=intents)
        return fake_client

    monkeypatch.setattr("discli.client.discord.Client", make_client)

    async def action(client):
        assert client.logged_in
        return "ok"

    assert await run_rest_action("token", action) == "ok"
    assert fake_client is not None
    assert fake_client.closed


@pytest.mark.asyncio
async def test_run_rest_action_closes_client_when_action_fails(monkeypatch):
    class FakeClient:
        def __init__(self, *, intents):
            self.closed = False

        async def login(self, token):
            pass

        async def close(self):
            self.closed = True

    fake_client = None

    def make_client(*, intents):
        nonlocal fake_client
        fake_client = FakeClient(intents=intents)
        return fake_client

    monkeypatch.setattr("discli.client.discord.Client", make_client)

    async def action(client):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await run_rest_action("token", action)
    assert fake_client is not None
    assert fake_client.closed


@pytest.mark.asyncio
async def test_run_gateway_action_starts_gateway_with_supplied_intents(monkeypatch):
    class FakeClient:
        def __init__(self, *, intents):
            self.intents = intents
            self.closed = False
            self.on_ready = None

        def event(self, callback):
            self.on_ready = callback
            return callback

        async def start(self, token):
            assert token == "token"
            assert self.on_ready is not None
            await self.on_ready()

        async def close(self):
            self.closed = True

        def is_closed(self):
            return self.closed

    fake_client = None

    def make_client(*, intents):
        nonlocal fake_client
        fake_client = FakeClient(intents=intents)
        return fake_client

    monkeypatch.setattr("discli.client.discord.Client", make_client)
    intents = build_gateway_intents({"voice"})

    async def action(client):
        return "ready"

    assert await run_gateway_action("token", action, intents) == "ready"
    assert fake_client is not None
    assert fake_client.intents is intents
    assert fake_client.closed


@pytest.mark.asyncio
async def test_run_gateway_action_closes_client_when_start_fails(monkeypatch):
    class FakeClient:
        def __init__(self, *, intents):
            self.closed = False

        def event(self, callback):
            return callback

        async def start(self, token):
            raise RuntimeError("Gateway startup failed")

        async def close(self):
            self.closed = True

        def is_closed(self):
            return self.closed

    fake_client = None

    def make_client(*, intents):
        nonlocal fake_client
        fake_client = FakeClient(intents=intents)
        return fake_client

    monkeypatch.setattr("discli.client.discord.Client", make_client)

    async def action(client):
        raise AssertionError("action must not run before Gateway readiness")

    with pytest.raises(RuntimeError, match="Gateway startup failed"):
        await run_gateway_action("token", action, build_gateway_intents())
    assert fake_client is not None
    assert fake_client.closed


class _ForbiddenResponse:
    """Minimal stand-in for discord's HTTP response, to build discord.Forbidden."""

    status = 403
    reason = "Forbidden"
    headers = {}

    def json(self):
        return {"code": 50001, "message": "Missing Access"}

    @property
    def real_url(self):
        return "http://example.com"


async def _run_with_real_client(monkeypatch, action):
    """Drive run_rest_action with a real discord.Client, minus the network.

    These tests deliberately avoid a stub client: the behaviour under test lives
    in discord.py's ConnectionState, so a fake would pass no matter what
    run_rest_action configures.
    """

    async def fake_login(self, token):
        return None

    monkeypatch.setattr(discord.Client, "login", fake_login)
    return await run_rest_action("token", action)


@pytest.mark.asyncio
async def test_run_rest_action_client_can_iterate_guild_members(monkeypatch):
    """Guild.fetch_members() must not trip discord.py's local intent guard.

    fetch_members() raises ClientException when Intents.members is unset, before
    any request is issued. That guard is client-side, so it fires even when the
    developer portal has the intent enabled, and ClientException is a sibling of
    HTTPException -- so neither _run() nor the Forbidden handler in
    utils.resolve_member() catches it. Building the REST client with
    Intents.none() therefore broke `member list`, `member info <name>` and
    `role list --with-member-counts` outright.
    """
    seen = {}

    async def action(client):
        async def fake_get_members(guild_id, retrieve, after_id):
            seen["guild_id"] = guild_id
            return []

        monkeypatch.setattr(client._connection.http, "get_members", fake_get_members)
        # Exactly the Guild that Client.fetch_channel()/fetch_guild() produce.
        guild = client._connection._get_or_create_unavailable_guild(4242)
        return [member async for member in guild.fetch_members(limit=1)]

    assert await _run_with_real_client(monkeypatch, action) == []
    assert seen["guild_id"] == 4242


@pytest.mark.asyncio
async def test_run_rest_action_surfaces_missing_members_intent_as_click_exception(monkeypatch):
    """A disabled Server Members intent must reach the actionable hint.

    resolve_member() catches discord.Forbidden to explain that name lookup needs
    the Server Members intent, but that handler is only reachable if the request
    actually goes out. With Intents.none() the local guard fires first and the
    user gets a raw ClientException traceback instead.
    """

    async def action(client):
        async def fake_get_members(guild_id, retrieve, after_id):
            raise discord.Forbidden(_ForbiddenResponse(), "Missing Access")

        monkeypatch.setattr(client._connection.http, "get_members", fake_get_members)
        guild = client._connection._get_or_create_unavailable_guild(4242)
        return await resolve_member(guild, "someone")

    with pytest.raises(click.ClickException, match="Server Members privileged intent"):
        await _run_with_real_client(monkeypatch, action)


@pytest.mark.asyncio
async def test_run_rest_action_requests_no_privileged_content_intents(monkeypatch):
    """Relax only what the local guard needs; nothing reaches Discord anyway.

    Intents are transmitted solely in the Gateway IDENTIFY, so a login-only
    client never sends them -- but keeping the set minimal preserves the intent
    of the REST/Gateway split if this client is ever given a socket.
    """

    async def action(client):
        return client.intents

    intents = await _run_with_real_client(monkeypatch, action)

    assert intents.members
    assert not intents.message_content
    assert not intents.presences
    assert not intents.guilds
