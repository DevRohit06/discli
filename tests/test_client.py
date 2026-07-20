import click
import pytest

from discli.client import (
    build_gateway_intents,
    gateway_features_for_events,
    resolve_token,
    run_gateway_action,
    run_rest_action,
)


def test_resolve_token_from_arg():
    assert resolve_token("my-token", {}) == "my-token"


def test_resolve_token_from_config():
    assert resolve_token(None, {"token": "config-token"}) == "config-token"


def test_resolve_token_missing():
    with pytest.raises(click.ClickException):
        resolve_token(None, {})


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
