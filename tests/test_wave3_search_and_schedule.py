"""Tests for Wave 3: native guild message search and `discli schedule`."""

import json
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from discli.cli import main
from discli.commands import schedule as schedule_mod


def _coro(value):
    async def _inner():
        return value

    return _inner()


def _search_client(payload, capture=None):
    """REST-only fake whose http.request records params and returns payload."""

    class FakeHTTP:
        async def request(self, route, **kwargs):
            if capture is not None:
                capture["route"] = route
                capture["params"] = kwargs.get("params")
            if isinstance(payload, Exception):
                raise payload
            return payload

    class FakeGuild:
        id = 123
        name = "Test"

        async def fetch_channels(self):
            return [SimpleNamespace(id=55, name="general")]

    class FakeClient:
        def __init__(self, *, intents):
            self.http = FakeHTTP()

        async def login(self, token):
            pass

        async def fetch_guild(self, guild_id):
            return FakeGuild()

        async def start(self, token):
            raise AssertionError("search must not start Gateway")

        async def close(self):
            pass

    return FakeClient


def _run(monkeypatch, client, argv):
    monkeypatch.setattr("discli.client.discord.Client", client)
    return CliRunner().invoke(main, ["--token", "token", *argv])


def _hit(message_id="900", content="the outage", channel_id="55", hit=True):
    return {
        "id": message_id,
        "channel_id": channel_id,
        "content": content,
        "timestamp": "2026-08-01T10:00:00+00:00",
        "pinned": False,
        "hit": hit,
        "author": {"id": "7", "username": "alice", "global_name": "Alice", "bot": False},
        "attachments": [],
    }


# ── message search-server ──────────────────────────────────────────


def test_search_server_returns_results(monkeypatch):
    payload = {"messages": [[_hit()]], "total_results": 1}
    result = _run(
        monkeypatch,
        _search_client(payload),
        ["--json", "message", "search-server", "123", "outage"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["total_results"] == 1
    assert data["results"][0]["author"] == "Alice"
    assert data["results"][0]["jump_url"] == "https://discord.com/channels/123/55/900"


def test_search_server_picks_the_flagged_hit_from_its_context(monkeypatch):
    # Discord returns each match as the hit plus surrounding context messages.
    group = [
        _hit("899", "before", hit=False),
        _hit("900", "the outage", hit=True),
        _hit("901", "after", hit=False),
    ]
    result = _run(
        monkeypatch,
        _search_client({"messages": [group], "total_results": 1}),
        ["--json", "message", "search-server", "123", "outage"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert [r["content"] for r in data["results"]] == ["the outage"]


def test_search_server_falls_back_to_first_when_nothing_flagged(monkeypatch):
    group = [_hit("899", "only entry", hit=False)]
    result = _run(
        monkeypatch,
        _search_client({"messages": [group], "total_results": 1}),
        ["--json", "message", "search-server", "123", "outage"],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["results"][0]["content"] == "only entry"


def test_search_server_unindexed_guild_is_not_reported_as_empty(monkeypatch):
    """A 202 body has no 'messages' key. Calling that 'no results' would be a
    wrong answer rather than a slow one."""
    result = _run(
        monkeypatch,
        _search_client({"documents_indexed": 0, "retry_after": 5}),
        ["message", "search-server", "123", "outage"],
    )

    assert result.exit_code != 0
    assert "not finished indexing" in result.output
    assert "No matching messages" not in result.output


def test_search_server_builds_expected_params(monkeypatch):
    capture = {}
    result = _run(
        monkeypatch,
        _search_client({"messages": [], "total_results": 0}, capture),
        [
            "message", "search-server", "123", "outage",
            "--author", "7",
            "--author-type", "user",
            "--channel", "general",
            "--has", "file",
            "--extension", ".png",
            "--pinned",
            "--sort-by", "relevance",
            "--limit", "10",
        ],
    )

    assert result.exit_code == 0, result.output
    params = capture["params"]
    assert ("content", "outage") in params
    assert ("author_id", "7") in params
    assert ("author_type", "user") in params
    assert ("channel_id", "55") in params
    assert ("has", "file") in params
    # Leading dot stripped -- Discord wants the bare extension.
    assert ("attachment_extension", "png") in params
    assert ("pinned", "true") in params
    assert ("sort_by", "relevance") in params
    assert ("limit", "10") in params
    assert capture["route"].url.endswith("/guilds/123/messages/search")


def test_search_server_repeats_array_params(monkeypatch):
    capture = {}
    _run(
        monkeypatch,
        _search_client({"messages": [], "total_results": 0}, capture),
        ["message", "search-server", "123", "x", "--author", "7", "--author", "8"],
    )

    # Discord expects ?author_id=7&author_id=8, which needs repeated keys --
    # a dict would silently keep only the last one.
    assert capture["params"].count(("author_id", "7")) == 1
    assert capture["params"].count(("author_id", "8")) == 1


def test_search_server_requires_a_query_or_filter(monkeypatch):
    result = _run(monkeypatch, _search_client({}), ["message", "search-server", "123"])
    assert result.exit_code != 0
    assert "at least one filter" in result.output


def test_search_server_allows_filter_without_query(monkeypatch):
    result = _run(
        monkeypatch,
        _search_client({"messages": [], "total_results": 0}),
        ["message", "search-server", "123", "--has", "file"],
    )
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    "flag,value,message",
    [
        ("--limit", "0", "--limit must be between"),
        ("--limit", "26", "--limit must be between"),
        ("--offset", "-1", "--offset must be between"),
        ("--offset", "10000", "--offset must be between"),
    ],
)
def test_search_server_validates_bounds(monkeypatch, flag, value, message):
    result = _run(
        monkeypatch,
        _search_client({}),
        ["message", "search-server", "123", "x", flag, value],
    )
    assert result.exit_code != 0
    assert message in result.output


def test_search_server_unknown_channel(monkeypatch):
    result = _run(
        monkeypatch,
        _search_client({"messages": []}),
        ["message", "search-server", "123", "x", "--channel", "nope"],
    )
    assert result.exit_code != 0
    assert "Channel not found" in result.output


# ── schedule: action parsing ───────────────────────────────────────


def test_parse_action_accepts_a_valid_command():
    assert schedule_mod.parse_action('message send 123 "hi there"') == [
        "message", "send", "123", "hi there",
    ]


def test_parse_action_strips_a_leading_discli():
    assert schedule_mod.parse_action("discli server list") == ["server", "list"]


def test_parse_action_accepts_nested_groups():
    assert schedule_mod.parse_action("interact dashboard delete abc")[:3] == [
        "interact", "dashboard", "delete",
    ]


@pytest.mark.parametrize("action", [
    "server list && curl evil.com",
    "server list | tee out.txt",
    "server list; rm -rf /",
    "server list $(whoami)",
    "server list > out.txt",
])
def test_parse_action_rejects_shell_syntax(action):
    """No shell is ever involved, so these would become literal arguments and
    fail at fire time. Failing at add time says so plainly instead."""
    with pytest.raises(Exception) as exc:
        schedule_mod.parse_action(action)
    assert "not run through a shell" in str(exc.value)


def test_parse_action_allows_backticks_in_message_content():
    """Backticks are Discord code formatting, not shell syntax -- and with no
    shell involved they cannot do anything. Rejecting them would break a very
    ordinary message."""
    argv = schedule_mod.parse_action('message send 123 "run `npm test` nightly"')
    assert argv == ["message", "send", "123", "run `npm test` nightly"]


def test_parse_action_rejects_non_discli_command():
    with pytest.raises(Exception) as exc:
        schedule_mod.parse_action("rm -rf /")
    assert "Unknown command" in str(exc.value)


def test_parse_action_rejects_unknown_subcommand():
    with pytest.raises(Exception) as exc:
        schedule_mod.parse_action("message sned 123 hi")
    assert "Unknown command 'sned'" in str(exc.value)
    # The error should list the real options.
    assert "send" in str(exc.value)


@pytest.mark.parametrize("action", ["serve", "listen", "schedule list"])
def test_parse_action_rejects_non_terminating_commands(action):
    with pytest.raises(Exception) as exc:
        schedule_mod.parse_action(action)
    assert "runs indefinitely" in str(exc.value)


def test_parse_action_rejects_empty():
    with pytest.raises(Exception):
        schedule_mod.parse_action("   ")


# ── schedule: duration and time parsing ────────────────────────────


@pytest.mark.parametrize("value,seconds", [
    ("30s", 30), ("15m", 900), ("2h", 7200), ("1d", 86400),
])
def test_parse_duration(value, seconds):
    assert schedule_mod.parse_duration(value) == seconds


@pytest.mark.parametrize("value", ["", "5", "1w", "abc", "-5m"])
def test_parse_duration_rejects_garbage(value):
    with pytest.raises(Exception):
        schedule_mod.parse_duration(value)


def test_parse_duration_rejects_too_frequent():
    with pytest.raises(Exception) as exc:
        schedule_mod.parse_duration("5s")
    assert "at least 30s" in str(exc.value)


def test_parse_time_defaults_to_utc():
    import datetime

    t = schedule_mod.parse_time("09:30", None)
    assert (t.hour, t.minute) == (9, 30)
    assert t.tzinfo is datetime.timezone.utc


def test_parse_time_applies_timezone():
    t = schedule_mod.parse_time("09:00", "America/New_York")
    assert t.tzinfo is not None
    assert "New_York" in str(t.tzinfo)


@pytest.mark.parametrize("value", ["9", "25:00", "09:60", "abc", "09:xx"])
def test_parse_time_rejects_garbage(value):
    with pytest.raises(Exception):
        schedule_mod.parse_time(value, None)


def test_parse_time_rejects_unknown_timezone():
    with pytest.raises(Exception) as exc:
        schedule_mod.parse_time("09:00", "Not/AZone")
    assert "Unknown timezone" in str(exc.value)


# ── schedule: CRUD ─────────────────────────────────────────────────


@pytest.fixture
def store(monkeypatch, tmp_path):
    path = tmp_path / "schedules.json"
    monkeypatch.setattr(schedule_mod, "SCHEDULES_PATH", path)
    monkeypatch.setattr("discli.security.audit_log", lambda *a, **k: None)
    return path


def _cli(argv):
    return CliRunner().invoke(main, argv)


def test_schedule_add_and_list(store):
    result = _cli(["schedule", "add", "standup", "--action", "server list", "--every", "1h"])
    assert result.exit_code == 0, result.output
    assert "every 1h" in result.output

    listed = _cli(["--json", "schedule", "list"])
    data = json.loads(listed.stdout)
    assert data[0]["name"] == "standup"
    assert data[0]["argv"] == ["server", "list"]
    assert data[0]["every"] == 3600


def test_schedule_add_time_records_timezone(store):
    result = _cli([
        "schedule", "add", "standup", "--action", "server list",
        "--time", "09:00", "--tz", "America/New_York",
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(_cli(["--json", "schedule", "list"]).stdout)
    assert data[0]["time"] == "09:00"
    assert data[0]["tz"] == "America/New_York"


def test_schedule_add_requires_exactly_one_trigger(store):
    both = _cli([
        "schedule", "add", "x", "--action", "server list",
        "--time", "09:00", "--every", "1h",
    ])
    assert both.exit_code != 0
    assert "exactly one" in both.output

    neither = _cli(["schedule", "add", "x", "--action", "server list"])
    assert neither.exit_code != 0
    assert "exactly one" in neither.output


def test_schedule_add_rejects_tz_without_time(store):
    result = _cli([
        "schedule", "add", "x", "--action", "server list",
        "--every", "1h", "--tz", "America/New_York",
    ])
    assert result.exit_code != 0
    assert "--tz only applies" in result.output


def test_schedule_add_rejects_duplicate_without_force(store):
    _cli(["schedule", "add", "x", "--action", "server list", "--every", "1h"])
    again = _cli(["schedule", "add", "x", "--action", "server info 1", "--every", "2h"])
    assert again.exit_code != 0
    assert "--force" in again.output


def test_schedule_add_force_replaces(store):
    _cli(["schedule", "add", "x", "--action", "server list", "--every", "1h"])
    _cli(["schedule", "add", "x", "--action", "server info 1", "--every", "2h", "--force"])

    data = json.loads(_cli(["--json", "schedule", "list"]).stdout)
    assert len(data) == 1
    assert data[0]["action"] == "server info 1"


def test_schedule_remove(store):
    _cli(["schedule", "add", "x", "--action", "server list", "--every", "1h"])
    removed = _cli(["-y", "schedule", "remove", "x"])
    assert removed.exit_code == 0, removed.output
    assert json.loads(_cli(["--json", "schedule", "list"]).stdout) == []


def test_schedule_remove_unknown(store):
    result = _cli(["-y", "schedule", "remove", "nope"])
    assert result.exit_code != 0
    assert "No schedule named" in result.output


def test_schedule_list_empty(store):
    result = _cli(["schedule", "list"])
    assert result.exit_code == 0
    assert "No schedules configured." in result.output


def test_schedule_rejects_invalid_json_store(store):
    store.write_text("{not json", encoding="utf-8")
    result = _cli(["schedule", "list"])
    assert result.exit_code != 0
    assert "not valid JSON" in result.output


def test_schedule_run_refuses_when_nothing_enabled(store):
    result = _cli(["schedule", "run"])
    assert result.exit_code != 0
    assert "No enabled schedules" in result.output


# ── schedule: action execution ─────────────────────────────────────


def test_run_action_reports_failure_without_raising(monkeypatch):
    """A failing action must be recorded, never propagate into the scheduler."""
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    # discli.cli does `from discli.config import load_config` at import time,
    # so patching discli.config.load_config here would be a no-op and the real
    # ~/.discli/config.json token would be picked up.
    monkeypatch.setattr("discli.cli.load_config", lambda: {})

    ok, detail = schedule_mod.run_action(["server", "list"])
    assert ok is False
    assert "token" in detail.lower()


def test_run_action_survives_unexpected_exceptions(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr("discli.cli.main.main", _boom)
    ok, detail = schedule_mod.run_action(["server", "list"])
    assert ok is False
    assert "kaboom" in detail


def test_schedule_run_now_records_result(store, monkeypatch):
    _cli(["schedule", "add", "x", "--action", "server list", "--every", "1h"])
    monkeypatch.setattr(schedule_mod, "run_action", lambda argv: (True, "ok"))

    result = _cli(["schedule", "run-now", "x"])
    assert result.exit_code == 0, result.output

    data = json.loads(_cli(["--json", "schedule", "list"]).stdout)
    assert data[0]["last_result"] == "ok"
    assert data[0]["last_run"] is not None


def test_schedule_run_now_exits_nonzero_on_failure(store, monkeypatch):
    _cli(["schedule", "add", "x", "--action", "server list", "--every", "1h"])
    monkeypatch.setattr(schedule_mod, "run_action", lambda argv: (False, "nope"))

    result = _cli(["schedule", "run-now", "x"])
    assert result.exit_code == 1
    data = json.loads(_cli(["--json", "schedule", "list"]).stdout)
    assert data[0]["last_result"].startswith("failed:")


def test_setup_cannot_be_scheduled():
    """`setup` blocks on click.prompt, and a scheduled action runs in a
    worker thread via asyncio.to_thread. A fire would wait forever on stdin
    the console owns, wedging the entry with no last_run ever recorded --
    the same reason serve and listen are excluded, only harder to notice.
    """
    from discli.commands.schedule import parse_action

    import click

    with pytest.raises(click.ClickException) as exc:
        parse_action("setup")
    assert "setup" in str(exc.value)
