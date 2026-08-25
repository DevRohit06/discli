"""Tests for Wave 4: automod, onboarding, server-as-code, and Components v2."""

import json
from types import SimpleNamespace

import discord
import pytest
from click.testing import CliRunner

from discli.cli import main
from discli.commands import server_spec as spec_mod
from discli.interact_engine import (
    DashboardDefinition,
    DashboardPage,
    InteractError,
    build_v2_block,
    build_v2_view,
)


def _coro(value):
    async def _inner():
        return value

    return _inner()


def _client(**attrs):
    class FakeClient:
        def __init__(self, *, intents):
            pass

        async def login(self, token):
            pass

        async def start(self, token):
            raise AssertionError("one-shot commands must not start Gateway")

        async def close(self):
            pass

    for name, value in attrs.items():
        setattr(FakeClient, name, value)
    return FakeClient


def _run(monkeypatch, client, argv):
    monkeypatch.setattr("discli.client.discord.Client", client)
    monkeypatch.setattr("discli.security.audit_log", lambda *a, **k: None)
    return CliRunner().invoke(main, ["--token", "token", *argv])


def _guild_client(guild):
    return _client(fetch_guild=lambda self, gid: _coro(guild))


# ── automod ────────────────────────────────────────────────────────


def _fake_rule(name="no-links", rule_id=5, enabled=True):
    trigger = SimpleNamespace(
        type=discord.AutoModRuleTriggerType.keyword,
        keyword_filter=["badword"],
        regex_patterns=[],
        allow_list=[],
        mention_limit=None,
        presets=None,
    )
    return SimpleNamespace(
        id=rule_id,
        name=name,
        enabled=enabled,
        trigger=trigger,
        actions=[SimpleNamespace(
            type=discord.AutoModRuleActionType.block_message,
            channel_id=None,
            duration=None,
            custom_message="no",
        )],
        exempt_roles=[],
        exempt_channels=[],
        creator_id=1,
    )


def test_automod_list(monkeypatch):
    class FakeGuild:
        name = "Test"

        async def fetch_automod_rules(self):
            return [_fake_rule()]

    result = _run(monkeypatch, _guild_client(FakeGuild()), ["automod", "list", "123"])
    assert result.exit_code == 0, result.output
    assert "no-links [enabled]" in result.output
    assert "keywords: badword" in result.output


def test_automod_create_keyword(monkeypatch):
    captured = {}

    class FakeGuild:
        name = "Test"

        async def create_automod_rule(self, **kwargs):
            captured.update(kwargs)
            return _fake_rule()

    result = _run(monkeypatch, _guild_client(FakeGuild()), [
        "automod", "create", "123", "no-links",
        "--trigger", "keyword", "--keyword", "badword", "--action", "block",
    ])

    assert result.exit_code == 0, result.output
    assert captured["trigger"].type is discord.AutoModRuleTriggerType.keyword
    assert captured["trigger"].keyword_filter == ["badword"]
    assert captured["actions"][0].type is discord.AutoModRuleActionType.block_message


def test_automod_create_keyword_needs_a_pattern(monkeypatch):
    class FakeGuild:
        name = "Test"

        async def create_automod_rule(self, **kwargs):
            raise AssertionError("must not reach Discord with an empty keyword filter")

    result = _run(monkeypatch, _guild_client(FakeGuild()), [
        "automod", "create", "123", "x", "--trigger", "keyword", "--action", "block",
    ])
    assert result.exit_code != 0
    assert "--keyword or --regex" in result.output


def test_automod_preset_trigger_needs_a_preset(monkeypatch):
    class FakeGuild:
        name = "Test"

    result = _run(monkeypatch, _guild_client(FakeGuild()), [
        "automod", "create", "123", "x", "--trigger", "keyword-preset", "--action", "block",
    ])
    assert result.exit_code != 0
    assert "--preset" in result.output


def test_automod_mention_spam_needs_a_limit(monkeypatch):
    class FakeGuild:
        name = "Test"

    result = _run(monkeypatch, _guild_client(FakeGuild()), [
        "automod", "create", "123", "x", "--trigger", "mention-spam", "--action", "block",
    ])
    assert result.exit_code != 0
    assert "--mention-limit" in result.output


def test_automod_alert_action_needs_a_channel(monkeypatch):
    class FakeGuild:
        name = "Test"

        async def fetch_channels(self):
            return []

    result = _run(monkeypatch, _guild_client(FakeGuild()), [
        "automod", "create", "123", "x", "--trigger", "spam", "--action", "alert",
    ])
    assert result.exit_code != 0
    assert "--alert-channel" in result.output


def test_automod_timeout_bounds(monkeypatch):
    class FakeGuild:
        name = "Test"

    result = _run(monkeypatch, _guild_client(FakeGuild()), [
        "automod", "create", "123", "x", "--trigger", "spam",
        "--action", "timeout", "--timeout", "9999999",
    ])
    assert result.exit_code != 0
    assert "28 days" in result.output


def test_automod_disable(monkeypatch):
    captured = {}
    rule = _fake_rule()

    async def _edit(**kwargs):
        captured.update(kwargs)
        return rule

    rule.edit = _edit

    class FakeGuild:
        name = "Test"

        async def fetch_automod_rules(self):
            return [rule]

    result = _run(monkeypatch, _guild_client(FakeGuild()), ["automod", "disable", "123", "no-links"])
    assert result.exit_code == 0, result.output
    assert captured["enabled"] is False
    assert "Disabled AutoMod rule 'no-links'" in result.output


def test_automod_unknown_rule(monkeypatch):
    class FakeGuild:
        name = "Test"

        async def fetch_automod_rules(self):
            return []

    result = _run(monkeypatch, _guild_client(FakeGuild()), ["automod", "disable", "123", "nope"])
    assert result.exit_code != 0
    assert "AutoMod rule not found" in result.output


# ── onboarding ─────────────────────────────────────────────────────


def test_onboarding_show(monkeypatch):
    option = SimpleNamespace(id=1, title="Gaming", description=None, role_ids=[9], channel_ids=[])
    prompt = SimpleNamespace(
        id=2, title="Interests", type=SimpleNamespace(name="multiple_choice"),
        single_select=False, required=True, in_onboarding=True, options=[option],
    )

    class FakeGuild:
        name = "Test"

        async def onboarding(self):
            return SimpleNamespace(
                enabled=True,
                mode=SimpleNamespace(name="default"),
                default_channel_ids={55},
                prompts=[prompt],
            )

    result = _run(monkeypatch, _guild_client(FakeGuild()), ["server", "onboarding", "show", "123"])
    assert result.exit_code == 0, result.output
    assert "enabled: True" in result.output
    assert "prompt: Interests [required]" in result.output
    assert "- Gaming" in result.output


def test_onboarding_edit_requires_an_option(monkeypatch):
    class FakeGuild:
        name = "Test"

    result = _run(monkeypatch, _guild_client(FakeGuild()), ["server", "onboarding", "edit", "123"])
    assert result.exit_code != 0
    assert "Nothing to change" in result.output


def test_onboarding_edit_sets_mode(monkeypatch):
    captured = {}

    class FakeGuild:
        name = "Test"

        async def edit_onboarding(self, **kwargs):
            captured.update(kwargs)

    result = _run(monkeypatch, _guild_client(FakeGuild()), [
        "server", "onboarding", "edit", "123", "--mode", "advanced", "--enable",
    ])
    assert result.exit_code == 0, result.output
    assert captured["mode"] is discord.OnboardingMode.advanced
    assert captured["enabled"] is True


# ── server spec: diffing ───────────────────────────────────────────


def _live(roles=None, channels=None, categories=None, name="Test"):
    return {
        "version": 1,
        "server": {"name": name, "description": None, "verification_level": "medium"},
        "roles": roles or [],
        "categories": categories or [],
        "channels": channels or [],
    }


def _role(name, color="000000", hoist=False, permissions=None):
    return {
        "name": name, "color": color, "hoist": hoist, "mentionable": False,
        "permissions": permissions or [], "position": 1,
    }


def _channel(name, topic=None, category=None, ch_type="text"):
    return {
        "name": name, "type": ch_type, "category": category, "topic": topic,
        "slowmode": 0, "nsfw": False, "position": 0, "overwrites": [],
    }


def _ops(changes):
    return {(c.kind, c.name): c.op for c in changes}


def test_diff_reports_creates_updates_and_extras():
    spec = _live(
        roles=[_role("moderator"), _role("admin")],
        channels=[_channel("general", topic="new topic")],
    )
    live = _live(
        roles=[_role("admin")],
        channels=[_channel("general", topic="old topic"), _channel("old-stuff")],
    )

    ops = _ops(spec_mod.diff_spec(spec, live))
    assert ops[("role", "moderator")] == "create"
    assert ops[("role", "admin")] == "unchanged"
    assert ops[("channel", "general")] == "update"
    assert ops[("channel", "old-stuff")] == "extra"


def test_diff_ignores_fields_the_spec_omits():
    """A trimmed spec means 'I do not manage this field', not 'set it to null'.

    Without this, hand-editing a spec down to the few fields you care about
    would blank out everything you removed on the next apply.
    """
    spec = _live(channels=[{"name": "general", "topic": "same"}])
    live = _live(channels=[_channel("general", topic="same", category="Text")])

    ops = _ops(spec_mod.diff_spec(spec, live))
    assert ops[("channel", "general")] == "unchanged"


def test_diff_detects_permission_list_changes_regardless_of_order():
    spec = _live(roles=[_role("mod", permissions=["send_messages", "kick_members"])])
    live = _live(roles=[_role("mod", permissions=["kick_members", "send_messages"])])
    assert _ops(spec_mod.diff_spec(spec, live))[("role", "mod")] == "unchanged"

    spec2 = _live(roles=[_role("mod", permissions=["send_messages", "ban_members"])])
    assert _ops(spec_mod.diff_spec(spec2, live))[("role", "mod")] == "update"


def test_diff_detects_server_setting_changes():
    spec = {"server": {"name": "Renamed"}}
    changes = spec_mod.diff_spec(spec, _live(name="Test"))
    server_change = next(c for c in changes if c.kind == "server")
    assert server_change.op == "update"
    assert "name" in server_change.fields


def test_render_marks_extras_differently_under_prune():
    changes = spec_mod.diff_spec(_live(), _live(channels=[_channel("old")]))
    kept = spec_mod.render_changes(changes, prune=False, show_unchanged=False)
    pruned = spec_mod.render_changes(changes, prune=True, show_unchanged=False)
    assert "not in spec (kept)" in kept
    assert "DELETE" in pruned


def test_summarise_counts_every_op():
    spec = _live(roles=[_role("a"), _role("b")], channels=[_channel("c")])
    live = _live(roles=[_role("a")], channels=[_channel("c"), _channel("extra")])
    counts = spec_mod.summarise(spec_mod.diff_spec(spec, live))
    assert counts["create"] == 1 and counts["extra"] == 1 and counts["unchanged"] >= 1


# ── server spec: file handling ─────────────────────────────────────


def test_load_spec_rejects_a_future_version(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"version": 99}), encoding="utf-8")
    with pytest.raises(Exception) as exc:
        spec_mod.load_spec(str(path))
    assert "spec version 99" in str(exc.value)


def test_load_spec_rejects_invalid_json(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{nope", encoding="utf-8")
    with pytest.raises(Exception) as exc:
        spec_mod.load_spec(str(path))
    assert "not valid JSON" in str(exc.value)


def test_load_spec_rejects_a_non_object(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(Exception) as exc:
        spec_mod.load_spec(str(path))
    assert "object at the top level" in str(exc.value)


def test_permissions_accept_names_or_a_bitfield():
    from_names = spec_mod._permissions_from(["send_messages"], "mod")
    assert from_names.send_messages is True
    assert spec_mod._permissions_from("8", "mod").value == 8


def test_permissions_reject_unknown_names():
    with pytest.raises(Exception) as exc:
        spec_mod._permissions_from(["send_mesages"], "mod")
    assert "Unknown permission" in str(exc.value)


# ── server spec: apply ─────────────────────────────────────────────


class _FakeChannelObj:
    def __init__(self, name, topic=None, category=None):
        self.name = name
        self.topic = topic
        self.category = category
        self.position = 0
        self.nsfw = False
        self.slowmode_delay = 0
        self.overwrites = {}
        self.type = SimpleNamespace(name="text")
        self.edited = None
        self.deleted = False

    async def edit(self, **kwargs):
        self.edited = kwargs

    async def delete(self, reason=None):
        self.deleted = True

    async def set_permissions(self, target, overwrite=None, reason=None):
        self.overwrites[target] = overwrite


def _apply_guild(existing_channels=(), existing_roles=(), created=None):
    created = created if created is not None else {"roles": [], "channels": [], "categories": []}

    class FakeGuild:
        id = 123
        name = "Test"
        description = None
        verification_level = SimpleNamespace(name="medium")

        async def fetch_channels(self):
            return list(existing_channels)

        async def fetch_roles(self):
            return list(existing_roles)

        async def create_role(self, name, **kwargs):
            created["roles"].append(name)
            return SimpleNamespace(name=name, id=1)

        async def create_text_channel(self, name, **kwargs):
            created["channels"].append(name)
            return _FakeChannelObj(name)

        async def create_category(self, name, **kwargs):
            created["categories"].append(name)
            return _FakeChannelObj(name)

    return FakeGuild(), created


def test_apply_creates_what_the_spec_adds(monkeypatch, tmp_path):
    guild, created = _apply_guild()
    path = tmp_path / "s.json"
    path.write_text(json.dumps({
        "version": 1,
        "roles": [{"name": "moderator", "color": "ff0000"}],
        "channels": [{"name": "general", "type": "text"}],
    }), encoding="utf-8")

    result = _run(monkeypatch, _guild_client(guild), ["server", "apply", "123", str(path)])
    assert result.exit_code == 0, result.output
    assert created["roles"] == ["moderator"]
    assert created["channels"] == ["general"]


def test_apply_leaves_extras_alone_without_prune(monkeypatch, tmp_path):
    extra = _FakeChannelObj("old-stuff")
    guild, _ = _apply_guild(existing_channels=[extra])
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"version": 1, "channels": []}), encoding="utf-8")

    result = _run(monkeypatch, _guild_client(guild), ["server", "apply", "123", str(path)])
    assert result.exit_code == 0, result.output
    assert extra.deleted is False
    assert "left alone" in result.output
    assert "--prune" in result.output


def test_apply_prune_deletes_extras(monkeypatch, tmp_path):
    extra = _FakeChannelObj("old-stuff")
    guild, _ = _apply_guild(existing_channels=[extra])
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"version": 1, "channels": []}), encoding="utf-8")

    result = _run(monkeypatch, _guild_client(guild),
                  ["-y", "server", "apply", "123", str(path), "--prune"])
    assert result.exit_code == 0, result.output
    assert extra.deleted is True
    assert "Deleted 1" in result.output


def test_apply_prune_is_a_confirmed_destructive_action(monkeypatch, tmp_path):
    """Without -y the confirmation prompt must appear and refuse by default."""
    extra = _FakeChannelObj("old-stuff")
    guild, _ = _apply_guild(existing_channels=[extra])
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"version": 1, "channels": []}), encoding="utf-8")

    monkeypatch.setattr("discli.client.discord.Client", _guild_client(guild))
    monkeypatch.setattr("discli.security.audit_log", lambda *a, **k: None)
    result = CliRunner().invoke(
        main, ["--token", "token", "server", "apply", "123", str(path), "--prune"], input="n\n"
    )

    assert extra.deleted is False
    assert "Destructive" in result.output


def test_apply_dry_run_writes_nothing(monkeypatch, tmp_path):
    guild, created = _apply_guild()
    path = tmp_path / "s.json"
    path.write_text(json.dumps({
        "version": 1, "roles": [{"name": "moderator"}],
    }), encoding="utf-8")

    result = _run(monkeypatch, _guild_client(guild),
                  ["server", "apply", "123", str(path), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert created["roles"] == []
    assert "dry run" in result.output


def test_apply_refuses_to_create_an_unsupported_channel_type(monkeypatch, tmp_path):
    guild, _ = _apply_guild()
    path = tmp_path / "s.json"
    path.write_text(json.dumps({
        "version": 1, "channels": [{"name": "the-stage", "type": "stage_voice"}],
    }), encoding="utf-8")

    result = _run(monkeypatch, _guild_client(guild), ["server", "apply", "123", str(path)])
    assert result.exit_code != 0
    assert "does not create" in result.output


def test_apply_rejects_an_overwrite_for_an_unknown_role(monkeypatch, tmp_path):
    guild, _ = _apply_guild()
    path = tmp_path / "s.json"
    path.write_text(json.dumps({
        "version": 1,
        "channels": [{"name": "general", "type": "text",
                      "overwrites": [{"role": "ghost", "allow": ["send_messages"], "deny": []}]}],
    }), encoding="utf-8")

    result = _run(monkeypatch, _guild_client(guild), ["server", "apply", "123", str(path)])
    assert result.exit_code != 0
    assert "does not exist" in result.output


# ── server export / diff commands ──────────────────────────────────


def test_export_omits_everyone_and_managed_roles(monkeypatch):
    everyone = SimpleNamespace(name="@everyone", managed=False, position=0,
                               color=discord.Colour(0), hoist=False, mentionable=False,
                               permissions=discord.Permissions(0))
    bot_role = SimpleNamespace(name="SomeBot", managed=True, position=2,
                               color=discord.Colour(0), hoist=False, mentionable=False,
                               permissions=discord.Permissions(0))
    real = SimpleNamespace(name="moderator", managed=False, position=1,
                           color=discord.Colour(0xFF0000), hoist=True, mentionable=False,
                           permissions=discord.Permissions(send_messages=True))

    class FakeGuild:
        id = 123
        name = "Test"
        description = None
        verification_level = SimpleNamespace(name="medium")

        async def fetch_channels(self):
            return []

        async def fetch_roles(self):
            return [everyone, bot_role, real]

    result = _run(monkeypatch, _guild_client(FakeGuild()), ["server", "export", "123"])
    assert result.exit_code == 0, result.output
    spec = json.loads(result.stdout)
    assert [r["name"] for r in spec["roles"]] == ["moderator"]
    assert spec["roles"][0]["color"] == "ff0000"
    assert spec["roles"][0]["permissions"] == ["send_messages"]


# ── Components v2 ──────────────────────────────────────────────────


def test_v2_text_block():
    item = build_v2_block({"type": "text", "content": "hello"}, "d1")
    assert isinstance(item, discord.ui.TextDisplay)


def test_v2_container_with_children():
    item = build_v2_block({
        "type": "container", "accent": "5865f2",
        "children": [{"type": "text", "content": "x"}, {"type": "separator"}],
    }, "d1")
    assert isinstance(item, discord.ui.Container)
    assert len(item.children) == 2


def test_v2_button_keeps_the_dashboard_routing_prefix():
    """Routing must be identical to the embed layout, or v2 dashboards would
    silently stop dispatching their interactions."""
    row = build_v2_block({
        "type": "buttons", "items": [{"label": "Refresh", "custom_id": "refresh"}],
    }, "dash1")
    button = row.children[0]
    assert button.custom_id == "dash:dash1:refresh"


def test_v2_link_button_has_no_custom_id():
    row = build_v2_block({
        "type": "buttons",
        "items": [{"label": "Docs", "style": "link", "url": "https://example.com"}],
    }, "dash1")
    assert row.children[0].url == "https://example.com"


def test_v2_link_button_requires_a_url():
    with pytest.raises(InteractError) as exc:
        build_v2_block({"type": "buttons", "items": [{"label": "x", "style": "link"}]}, "d1")
    assert "needs a 'url'" in str(exc.value)


def test_v2_section_requires_an_accessory():
    with pytest.raises(InteractError) as exc:
        build_v2_block({"type": "section", "content": "hi"}, "d1")
    assert "thumbnail" in str(exc.value)


def test_v2_unknown_block_type_lists_the_valid_ones():
    with pytest.raises(InteractError) as exc:
        build_v2_block({"type": "carousel"}, "d1")
    assert "Unknown v2 block type" in str(exc.value)
    assert "container" in str(exc.value)


def test_v2_bad_accent_colour():
    with pytest.raises(InteractError) as exc:
        build_v2_block({"type": "container", "accent": "nothex",
                        "children": [{"type": "text", "content": "x"}]}, "d1")
    assert "accent colour" in str(exc.value)


def test_v2_page_needs_blocks():
    with pytest.raises(InteractError) as exc:
        build_v2_view(DashboardPage(layout="v2"), "d1")
    assert "at least one entry in 'blocks'" in str(exc.value)


def test_dashboard_defaults_to_the_embed_layout():
    page = DashboardPage(embed={"title": "t"})
    assert page.layout == "embed"
    assert page.is_v2() is False
    assert DashboardDefinition(dashboard_id="d", pages=[page]).is_v2() is False


def test_dashboard_refuses_mixed_layouts():
    """Discord fixes the Components v2 flag at send time, so a dashboard cannot
    page from an embed layout into a v2 one."""
    with pytest.raises(InteractError) as exc:
        DashboardDefinition(dashboard_id="d", pages=[
            DashboardPage(embed={"title": "a"}),
            DashboardPage(layout="v2", blocks=[{"type": "text", "content": "b"}]),
        ])
    assert "same layout" in str(exc.value)


def test_dashboard_all_v2_pages_are_fine():
    definition = DashboardDefinition(dashboard_id="d", pages=[
        DashboardPage(layout="v2", blocks=[{"type": "text", "content": "a"}]),
        DashboardPage(layout="v2", blocks=[{"type": "text", "content": "b"}]),
    ])
    assert definition.is_v2() is True


# ── export: category resolution ────────────────────────────────────


class _RestChannel(discord.TextChannel):
    """A channel as fetch_channels() actually returns it.

    The parent id is present, but `.category` resolves through
    guild.get_channel() against a cache that fetch_channels never populates --
    so on a REST-only client it is always None.
    """

    def __init__(self, channel_id, name, category_id=None):
        self.id = channel_id
        self.name = name
        self.category_id = category_id
        self.position = 0
        self.topic = None
        self.nsfw = False
        self.slowmode_delay = 0
        self._overwrites = []

    @property
    def type(self):
        return discord.ChannelType.text

    @property
    def category(self):
        return None  # the empty cache, reproduced

    @property
    def overwrites(self):
        return {}


class _RestCategory(discord.CategoryChannel):
    def __init__(self, channel_id, name):
        self.id = channel_id
        self.name = name
        self.position = 0

    @property
    def overwrites(self):
        return {}


@pytest.mark.asyncio
async def test_export_resolves_categories_without_the_guild_cache():
    """Found by running against a real server: 10 of 21 channels had a parent
    and every one exported as null, silently flattening the structure. apply
    would then recreate them all at the top level."""
    category = _RestCategory(100, "Text Channels")

    class FakeGuild:
        id = 1
        name = "Test"
        description = None
        verification_level = SimpleNamespace(name="medium")

        async def fetch_channels(self):
            return [category, _RestChannel(10, "general", category_id=100),
                    _RestChannel(11, "orphan", category_id=None)]

        async def fetch_roles(self):
            return []

    spec = await spec_mod.build_spec(FakeGuild())
    by_name = {c["name"]: c["category"] for c in spec["channels"]}
    assert by_name["general"] == "Text Channels", "parent category was dropped"
    assert by_name["orphan"] is None
