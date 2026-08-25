"""Tests for the parts of `discli serve` that can be reached without a bot.

`serve` builds its handlers as closures inside `serve_cmd`, so most of it is
unreachable from a test. The two pieces that carry real behaviour rather than
plumbing -- the stream flush loop's failure handling, and the channel_list
payload -- were lifted to module level specifically so they could be verified
here instead of by reading.
"""

import asyncio
from types import SimpleNamespace

import discord
import pytest

from discli.commands.serve import make_stream_flush_loop, serialize_channels


# ── serialize_channels ─────────────────────────────────────────────


class _FakeText(discord.TextChannel):
    def __init__(self, channel_id, name):
        self.id = channel_id
        self.name = name


class _FakeVoice(discord.VoiceChannel):
    def __init__(self, channel_id, name):
        self.id = channel_id
        self.name = name


class _FakeForum(discord.ForumChannel):
    def __init__(self, channel_id, name):
        self.id = channel_id
        self.name = name


def _guild(channels, name="Test", guild_id=1):
    return SimpleNamespace(id=guild_id, name=name, channels=channels)


def test_serialize_channels_reports_visible_only():
    """Agents driving serve over JSONL have no stderr to read a note from, so
    the truncation disclosure has to travel in the payload."""
    payload = serialize_channels([_guild([_FakeText(10, "general")])])
    assert payload["visible_only"] is True
    assert payload["ok"] is True


def test_serialize_channels_labels_each_type():
    payload = serialize_channels([
        _guild([_FakeText(10, "general"), _FakeVoice(11, "Lounge"), _FakeForum(12, "help")])
    ])
    assert {c["name"]: c["type"] for c in payload["channels"]} == {
        "general": "text", "Lounge": "voice", "help": "forum",
    }


def test_serialize_channels_skips_categories_and_threads():
    class _FakeCategory(discord.CategoryChannel):
        def __init__(self):
            self.id = 99
            self.name = "Text Channels"

    payload = serialize_channels([_guild([_FakeText(10, "general"), _FakeCategory()])])
    assert [c["name"] for c in payload["channels"]] == ["general"]


def test_serialize_channels_tolerates_a_missing_guild():
    # resolve_guild_by_id returns None for an unknown id, and that list is
    # passed straight through.
    payload = serialize_channels([None, _guild([_FakeText(10, "general")])])
    assert len(payload["channels"]) == 1


def test_serialize_channels_empty_still_flags_visibility():
    payload = serialize_channels([_guild([])])
    assert payload["channels"] == []
    assert payload["visible_only"] is True


# ── make_stream_flush_loop ─────────────────────────────────────────


def _run(coro):
    return asyncio.run(coro)


async def _until(predicate, *, timeout=3.0, step=0.005):
    """Wait for a condition instead of a fixed sleep.

    These loops are driven by the event loop's scheduler, so "sleep long enough
    and hope" is flaky the moment the machine is busy -- which is exactly how
    the first version of these tests failed. Poll for the outcome with a
    generous ceiling instead.
    """
    waited = 0.0
    while not predicate():
        if waited >= timeout:
            return False
        await asyncio.sleep(step)
        waited += step
    return True


async def _settle(loop):
    if loop.is_running():
        loop.cancel()
    # Let cancellation and the error/after hooks run.
    await asyncio.sleep(0)


def test_flush_loop_calls_flush_while_the_stream_is_open():
    calls = []

    async def flush(stream_id):
        calls.append(stream_id)

    async def scenario():
        streams = {"s1": {"done": False}}
        loop = make_stream_flush_loop("s1", streams, flush, lambda e: None, interval=0.01)
        loop.start()
        reached = await _until(lambda: len(calls) >= 1)
        await _settle(loop)
        return reached

    assert _run(scenario()), "flush was never called"
    assert set(calls) == {"s1"}


def test_flush_loop_stops_once_the_stream_is_done():
    calls = []
    streams = {"s1": {"done": False}}

    async def flush(stream_id):
        calls.append(stream_id)
        streams["s1"]["done"] = True

    async def scenario():
        loop = make_stream_flush_loop("s1", streams, flush, lambda e: None, interval=0.01)
        loop.start()
        stopped = await _until(lambda: not loop.is_running())
        await _settle(loop)
        return stopped

    assert _run(scenario()), "loop kept running after the stream was done"
    # One flush, then the next tick sees done and stops.
    assert len(calls) == 1


def test_flush_loop_stops_when_the_stream_disappears():
    async def flush(stream_id):
        raise AssertionError("must not flush a stream that is gone")

    async def scenario():
        loop = make_stream_flush_loop("gone", {}, flush, lambda e: None, interval=0.01)
        loop.start()
        stopped = await _until(lambda: not loop.is_running())
        await _settle(loop)
        return stopped

    assert _run(scenario()), "loop kept running for a stream that no longer exists"


def test_flush_loop_reports_an_unexpected_failure():
    """The whole point of the tasks.Loop conversion.

    The hand-rolled loop caught only CancelledError, so any other exception
    killed flushing for that stream silently and permanently -- the task's
    exception was never retrieved. This must surface as a JSONL event.
    """
    emitted = []

    async def flush(stream_id):
        raise RuntimeError("kaboom")

    async def scenario():
        streams = {"s1": {"done": False}}
        loop = make_stream_flush_loop("s1", streams, flush, emitted.append, interval=0.01)
        loop.start()
        reported = await _until(lambda: bool(emitted))
        await _settle(loop)
        return reported

    assert _run(scenario()), "a failing flush emitted nothing"
    event = emitted[0]
    assert event["type"] == "error"
    assert event["stream_id"] == "s1"
    assert "kaboom" in event["error"]


def test_flush_loop_does_not_flush_before_the_first_interval():
    """tasks.Loop runs its body before the first sleep; the loop this replaced
    slept first. Without the before_loop hook, a stream that ends immediately
    would issue a spurious edit."""
    calls = []

    async def flush(stream_id):
        calls.append(stream_id)

    async def scenario():
        streams = {"s1": {"done": False}}
        # A whole second of headroom, checked after 50ms: a scheduling hiccup
        # cannot turn "did not fire yet" into a false pass.
        loop = make_stream_flush_loop("s1", streams, flush, lambda e: None, interval=1.0)
        loop.start()
        await asyncio.sleep(0.05)
        await _settle(loop)

    _run(scenario())
    assert calls == []


@pytest.mark.parametrize("transient", [OSError("net"), asyncio.TimeoutError()])
def test_flush_loop_does_not_report_transient_errors(transient):
    """tasks.Loop treats network-shaped errors as reconnectable, so they back
    off and retry rather than landing in the error handler.

    Asserted on the first failure only: reconnect backoff is randomised over
    seconds, so waiting for the actual retry would make this slow and flaky
    without testing anything more."""
    emitted = []
    calls = []

    async def flush(stream_id):
        calls.append(stream_id)
        raise transient

    async def scenario():
        streams = {"s1": {"done": False}}
        loop = make_stream_flush_loop("s1", streams, flush, emitted.append, interval=0.01)
        loop.start()
        fired = await _until(lambda: bool(calls))
        # Give the error path a chance to run if it were going to.
        await asyncio.sleep(0.05)
        await _settle(loop)
        return fired

    assert _run(scenario()), "flush never ran"
    assert emitted == [], f"transient error should not be reported: {emitted}"
