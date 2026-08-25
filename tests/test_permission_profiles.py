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
