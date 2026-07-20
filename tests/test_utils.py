import json

import click
import pytest

from discli.utils import (
    fetch_guilds,
    format_output,
    resolve_channel,
    resolve_guild,
    resolve_member,
    resolve_role,
    resolve_thread,
    resolve_user,
)


def test_format_output_plain():
    result = format_output("hello world", use_json=False)
    assert result == "hello world"


def test_format_output_json_dict():
    data = {"key": "value"}
    result = format_output(data, use_json=True)
    assert json.loads(result) == data


def test_format_output_json_list():
    data = [{"id": 1}, {"id": 2}]
    result = format_output(data, use_json=True)
    assert json.loads(result) == data


@pytest.mark.asyncio
async def test_resolve_channel_id_uses_http_fetch():
    expected = object()

    class FakeClient:
        async def fetch_channel(self, channel_id):
            assert channel_id == 123
            return expected

    assert await resolve_channel(FakeClient(), "123") is expected


@pytest.mark.asyncio
async def test_fetch_guilds_prefers_gateway_cache():
    expected = object()

    class FakeClient:
        guilds = [expected]

        def fetch_guilds(self, *, limit):
            raise AssertionError("populated Gateway cache must avoid HTTP")

    assert await fetch_guilds(FakeClient()) == [expected]


@pytest.mark.asyncio
async def test_resolve_guild_id_prefers_gateway_cache():
    expected = object()

    class FakeClient:
        def get_guild(self, guild_id):
            assert guild_id == 123
            return expected

        async def fetch_guild(self, guild_id):
            raise AssertionError("cached guild must avoid HTTP")

    assert await resolve_guild(FakeClient(), "123") is expected


@pytest.mark.asyncio
async def test_resolve_guild_name_falls_back_to_http_after_cache_miss():
    class FakeGuild:
        def __init__(self, guild_id, name):
            self.id = guild_id
            self.name = name

    expected = FakeGuild(456, "Target")

    class FakeClient:
        guilds = [FakeGuild(123, "Cached")]

        async def fetch_guilds(self, *, limit):
            assert limit is None
            yield expected

    assert await resolve_guild(FakeClient(), "target") is expected


@pytest.mark.asyncio
async def test_resolve_channel_id_prefers_gateway_cache():
    expected = object()

    class FakeClient:
        def get_channel(self, channel_id):
            assert channel_id == 123
            return expected

        async def fetch_channel(self, channel_id):
            raise AssertionError("cached channel must avoid HTTP")

    assert await resolve_channel(FakeClient(), "123") is expected


@pytest.mark.asyncio
async def test_resolve_member_id_prefers_gateway_cache():
    expected = object()

    class FakeGuild:
        def get_member(self, member_id):
            assert member_id == 123
            return expected

        async def fetch_member(self, member_id):
            raise AssertionError("cached member must avoid HTTP")

    assert await resolve_member(FakeGuild(), "123") is expected


@pytest.mark.asyncio
async def test_resolve_user_id_prefers_gateway_cache():
    expected = object()

    class FakeClient:
        def get_user(self, user_id):
            assert user_id == 123
            return expected

        async def fetch_user(self, user_id):
            raise AssertionError("cached user must avoid HTTP")

    assert await resolve_user(FakeClient(), "123") is expected


@pytest.mark.asyncio
async def test_resolve_role_name_prefers_gateway_cache():
    class FakeRole:
        id = 123
        name = "Moderator"

    expected = FakeRole()

    class FakeGuild:
        roles = [expected]

        async def fetch_roles(self):
            raise AssertionError("cached role must avoid HTTP")

    assert await resolve_role(FakeGuild(), "moderator") is expected


@pytest.mark.asyncio
async def test_resolve_thread_name_prefers_gateway_cache():
    class FakeThread:
        id = 123
        name = "Support"

    expected = FakeThread()

    class FakeGuild:
        threads = [expected]

        async def active_threads(self):
            raise AssertionError("cached thread must avoid HTTP")

    class FakeClient:
        guilds = [FakeGuild()]

    assert await resolve_thread(FakeClient(), "support") is expected


@pytest.mark.asyncio
async def test_resolve_channel_name_rejects_ambiguous_matches():
    class FakeChannel:
        def __init__(self, channel_id):
            self.id = channel_id
            self.name = "general"

    class FakeGuild:
        async def fetch_channels(self):
            return [FakeChannel(id(self))]

    class FakeClient:
        async def fetch_guilds(self, *, limit):
            assert limit is None
            for guild in (FakeGuild(), FakeGuild()):
                yield guild

    with pytest.raises(click.ClickException, match="Multiple channels"):
        await resolve_channel(FakeClient(), "#general")
