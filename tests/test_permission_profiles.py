"""Tests for the built-in permission profiles.

The `moderation` profile used to be `allowed: ["*"]`, byte-identical to `full`,
so selecting it for least privilege did nothing at all. These tests pin the
boundary so it cannot silently regress to that again.
"""

import click
import pytest

from discli.security import DEFAULT_PROFILES, is_command_allowed


def allowed(path, profile):
    return is_command_allowed(path, profile_override=profile)


# ── the regression that started this ───────────────────────────────


def test_moderation_is_not_a_synonym_for_full():
    assert DEFAULT_PROFILES["moderation"]["allowed"] != ["*"]
    assert DEFAULT_PROFILES["moderation"] != DEFAULT_PROFILES["full"]


def test_moderation_cannot_promote_itself():
    """The single most important exclusion: if `permission set` were allowed,
    the profile could switch itself to full and every other limit here would be
    decorative."""
    assert allowed("permission show", "moderation") is True
    assert allowed("permission set", "moderation") is False


# ── what a moderator can do ────────────────────────────────────────


@pytest.mark.parametrize("path", [
    "member kick", "member ban", "member unban", "member timeout", "member nick",
    "message delete", "message bulk-delete", "message pin", "message unpin",
    "reaction remove", "invite delete", "voice move",
    "role assign", "role remove",
    "channel edit", "channel set-permissions",
    "automod list", "automod create", "automod delete",
    "thread archive", "thread unarchive",
    "message send", "message reply", "dm send", "typing",
    "server audit-log", "listen", "serve",
])
def test_moderation_allows_moderation(path):
    assert allowed(path, "moderation") is True, f"{path} should be allowed"


# ── what it must not ───────────────────────────────────────────────


@pytest.mark.parametrize("path", [
    # Restructuring the server
    "channel create", "channel delete",
    "role create", "role delete", "role edit",
    "server edit", "server apply", "server onboarding edit",
    # Identity and integrations
    "emoji upload", "emoji delete", "webhook create", "webhook send", "webhook delete",
    "invite create",
    # Automation and configuration
    "schedule add", "schedule run", "config set",
    # Escalation and covering tracks
    "permission set", "audit clear",
    # Not moderation
    "poll create", "event create",
])
def test_moderation_denies_everything_else(path):
    assert allowed(path, "moderation") is False, f"{path} should be denied"


def test_moderation_is_a_superset_of_readonly():
    """A moderator should never be able to see less than a read-only user."""
    for path in DEFAULT_PROFILES["readonly"]["allowed"]:
        assert allowed(path, "moderation") is True, f"readonly allows {path}, moderation does not"


def test_prefix_matching_does_not_leak_siblings():
    """'message pin' must not also match 'message pins', and 'audit show' must
    not open up 'audit clear'."""
    assert allowed("message pin", "moderation") is True
    assert allowed("message pins", "moderation") is True
    assert allowed("audit show", "moderation") is True
    assert allowed("audit clear", "moderation") is False


# ── the other profiles still behave ────────────────────────────────


def test_full_allows_everything():
    for path in ("server apply", "permission set", "config set", "webhook delete"):
        assert allowed(path, "full") is True


def test_readonly_denies_writes():
    assert allowed("message list", "readonly") is True
    assert allowed("message send", "readonly") is False
    assert allowed("member kick", "readonly") is False


def test_chat_denies_moderation():
    assert allowed("message send", "chat") is True
    assert allowed("member kick", "chat") is False
    assert allowed("channel delete", "chat") is False


def test_every_profile_name_is_offered_by_the_cli():
    """--profile is a click.Choice, so a profile absent from it is unreachable
    and one listed but undefined would fall back to full."""
    from discli.cli import main

    option = next(p for p in main.params if p.name == "profile")
    assert isinstance(option.type, click.Choice)
    assert set(option.type.choices) == set(DEFAULT_PROFILES)


@pytest.mark.parametrize("name", sorted(DEFAULT_PROFILES))
def test_every_profile_has_a_description(name):
    assert DEFAULT_PROFILES[name].get("description")


def test_moderation_keeps_voice_and_interact_in_scope():
    """These were added deliberately in df6b606 ("update permission profiles
    with voice and interact scopes"). Narrowing the profile away from ["*"]
    must not quietly drop them."""
    for path in ("voice join", "voice speak", "voice play", "voice move",
                 "interact modal", "interact workflow start", "interact dashboard create"):
        assert allowed(path, "moderation") is True, f"{path} should stay allowed"


# ── enforcement, not just policy ───────────────────────────────────
#
# Found by running the real CLI: `is_command_allowed()` said "permission set"
# was denied under moderation, and it was -- but nothing ever *called* the
# check for that command. _check_permission() lived inside run_rest() /
# run_gateway(), so every command that does not talk to Discord skipped it and
# `discli --profile moderation permission set full` simply succeeded.


LOCAL_COMMANDS = [
    ["permission", "set", "full"],
    ["audit", "clear"],
    ["config", "set", "token", "x"],
    ["schedule", "add", "x", "--action", "server list", "--every", "1h"],
    ["schedule", "remove", "x"],
    ["schedule", "run-now", "x"],
    ["schedule", "run"],
]


@pytest.mark.parametrize("argv", LOCAL_COMMANDS, ids=lambda a: " ".join(a[:2]))
def test_local_commands_are_actually_denied(argv, monkeypatch, tmp_path):
    """These never reach Discord, so they must enforce the profile themselves."""
    monkeypatch.setattr("discli.security.PERMISSIONS_PATH", tmp_path / "permissions.json")
    monkeypatch.setattr("discli.commands.schedule.SCHEDULES_PATH", tmp_path / "schedules.json")
    from click.testing import CliRunner

    from discli.cli import main

    result = CliRunner().invoke(main, ["--profile", "readonly", *argv])
    assert result.exit_code != 0, f"{' '.join(argv)} was allowed under readonly"
    assert "denied by" in result.output, result.output


def test_permission_set_still_works_under_full(monkeypatch, tmp_path):
    """The guard must not break the legitimate path."""
    monkeypatch.setattr("discli.security.PERMISSIONS_PATH", tmp_path / "permissions.json")
    from click.testing import CliRunner

    from discli.cli import main

    result = CliRunner().invoke(main, ["--profile", "full", "permission", "set", "chat"])
    assert result.exit_code == 0, result.output
    assert "set to: chat" in result.output


# Commands whose own source shows no enforcement, with the reason each is fine.
ENFORCEMENT_EXEMPT = {
    # Delegate to a helper that calls run_rest().
    "automod enable": "delegates to _set_enabled",
    "automod disable": "delegates to _set_enabled",
    # Read-only and local; allowed by every profile including readonly.
    "audit show": "read-only local",
    "config show": "read-only local",
    "permission show": "read-only local",
    "permission profiles": "read-only local",
    "schedule list": "read-only local",
    "doctor": "read-only local diagnostic",
}


def test_no_command_silently_skips_the_permission_check():
    """Guard against the next local command forgetting to enforce.

    A command that neither goes through run_rest/run_gateway nor calls
    enforce_profile() is invisible to --profile entirely.
    """
    import inspect

    from discli.cli import main

    unguarded = []

    def walk(cmd, prefix=""):
        for name, sub in sorted(getattr(cmd, "commands", {}).items()):
            path = f"{prefix}{name}"
            if isinstance(sub, click.Group):
                walk(sub, path + " ")
                continue
            try:
                src = inspect.getsource(sub.callback)
            except OSError:  # pragma: no cover - source always available here
                continue
            if any(m in src for m in ("run_rest", "run_gateway", "enforce_profile")):
                continue
            if path in ENFORCEMENT_EXEMPT:
                continue
            unguarded.append(path)

    walk(main)
    assert not unguarded, (
        "these commands never consult the permission profile: "
        + ", ".join(unguarded)
        + " -- call enforce_profile(ctx) or add them to ENFORCEMENT_EXEMPT with a reason"
    )


# ── prefix grants must not silently widen ──────────────────────────


@pytest.mark.parametrize("profile", ["chat", "readonly", "moderation"])
@pytest.mark.parametrize("path", ["config set", "permission set", "audit clear", "setup"])
def test_only_full_may_reconfigure_discli(profile, path):
    """`config set` overwrites the stored bot token; `permission set` changes
    the profile itself; `audit clear` destroys the record; `setup` does the
    first two in one command, so a restricted profile that could run it could
    promote itself to full. None belongs to a restricted profile.

    `chat` used to grant `config set` -- and, once the server group grew an
    `apply`, a whole server restructure -- because it listed the bare prefixes
    "config" and "server" and patterns match by prefix.
    """
    assert allowed(path, profile) is False


@pytest.mark.parametrize("path", [
    "server apply", "server edit", "server onboarding edit",
    "config set", "channel delete", "role delete", "member kick",
])
def test_chat_cannot_reshape_a_server(path):
    assert allowed(path, "chat") is False, f"chat should not allow {path}"


@pytest.mark.parametrize("path", [
    "message send", "message reply", "reaction add", "thread create",
    "dm send", "typing", "server list", "server info", "config show",
])
def test_chat_keeps_what_it_is_for(path):
    assert allowed(path, "chat") is True, f"chat should still allow {path}"


def test_no_profile_grants_a_whole_group_by_bare_prefix():
    """A bare *group* name grants every command that group will ever have.

    That is how `chat` came to allow `config set` and, once the server group
    grew one, `server apply`. Bare *leaf* commands are fine -- they cannot
    acquire subcommands. Only groups where blanket access is genuinely intended
    may be listed bare.
    """
    from discli.cli import main

    intended_bare_groups = {
        "message", "reaction", "thread", "dm", "interact", "voice", "automod",
    }
    offenders = []
    for name, profile in DEFAULT_PROFILES.items():
        for pattern in profile.get("allowed", []):
            if pattern == "*" or " " in pattern:
                continue
            target = main.commands.get(pattern)
            if isinstance(target, click.Group) and pattern not in intended_bare_groups:
                offenders.append(f"{name}: {pattern!r}")
    assert not offenders, (
        "these profiles grant a whole group by bare prefix, so adding any "
        "command to that group silently widens them: " + ", ".join(offenders)
    )


def test_denied_destructive_command_does_not_prompt_first(monkeypatch, tmp_path):
    """Confirming an action you are not allowed to take is backwards."""
    monkeypatch.setattr("discli.security.PERMISSIONS_PATH", tmp_path / "permissions.json")
    from click.testing import CliRunner

    from discli.cli import main

    # No stdin: if it prompts, the runner sees EOF and the test would show it.
    result = CliRunner().invoke(main, ["--profile", "readonly", "member", "kick", "1", "2"])
    assert "Destructive action" not in result.output, "prompted before checking the profile"
    assert "denied by" in result.output


def test_get_active_profile_name_reports_a_custom_profile(monkeypatch, tmp_path):
    """The name and the body were read by three separate copies of the same
    parse -- cli.py's permission_show, setup's prompt default, and
    get_active_profile. They had already diverged over whether the
    `profiles` map counts."""
    import json

    from discli import security

    path = tmp_path / "permissions.json"
    path.write_text(json.dumps({
        "active_profile": "mycustom",
        "profiles": {"mycustom": {"description": "c", "allowed": ["*"], "denied": []}},
    }))
    monkeypatch.setattr(security, "PERMISSIONS_PATH", path)

    assert security.get_active_profile_name() == "mycustom"


def test_get_active_profile_name_defaults_to_full(monkeypatch, tmp_path):
    from discli import security

    monkeypatch.setattr(security, "PERMISSIONS_PATH", tmp_path / "missing.json")

    assert security.get_active_profile_name() == "full"
