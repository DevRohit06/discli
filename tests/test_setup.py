"""Tests for `discli setup`, the interactive first-run wizard.

The wizard is the only command in discli that is *required* to be
interactive, which makes two things worth pinning here: that it refuses
rather than hangs when there is no human on the other end, and that it
cannot be used to escape a restricted permission profile (it writes the
token and sets the profile, so it is `config set` and `permission set`
fused into one command).
"""

import pytest
from click.testing import CliRunner

from discli.cli import main


def test_json_mode_refuses_instead_of_prompting():
    """`--json` promises a parseable payload; a prompt would deadlock a
    caller that is piping us. Refuse up front and name the alternatives."""
    result = CliRunner().invoke(main, ["--json", "setup"])

    assert result.exit_code == 1
    assert "discli config set token" in result.stderr


def test_a_piped_stdin_refuses_instead_of_hanging():
    """An agent or CI job shelling out to `discli setup` has no human to
    answer a prompt. Blocking there is a hang, not an error, so the wizard
    checks for a terminal before it asks anything."""
    result = CliRunner().invoke(main, ["setup"])

    assert result.exit_code == 1
    assert "needs a terminal" in result.stderr


def test_a_restricted_profile_cannot_run_the_wizard():
    """setup stores the token and sets the active profile, so it is
    `config set` and `permission set` fused. If a restricted profile could
    run it, that profile could promote itself to full and every other limit
    would be decorative -- the same hole `moderation` had with
    `permission set`.

    The denial must also beat the terminal check: a forbidden command that
    answers "needs a terminal" first has told the caller to go find a
    terminal for something it was never allowed to do.
    """
    result = CliRunner().invoke(main, ["--profile", "readonly", "setup"])

    assert result.exit_code == 1
    assert "denied by the 'readonly' permission profile" in result.output


# ── step 1: token ──────────────────────────────────────────────────


class _FakeUser:
    def __init__(self, user_id, name):
        self.id = user_id
        self.name = name

    def __str__(self):
        return self.name


class _FakeGuild:
    def __init__(self, name):
        self.name = name


@pytest.mark.asyncio
async def test_identify_reports_the_bot_and_the_servers_it_is_in():
    """Validating a token is worth nothing if the wizard cannot tell you
    *which* bot it just authenticated as -- pasting the token of a different
    application is the most likely mistake at this step, and the only way to
    catch it is to show the name back."""
    from discli.commands.setup import _identify

    client = type("C", (), {})()
    client.user = _FakeUser(42, "testbot")
    client.guilds = [_FakeGuild("Guild A"), _FakeGuild("Guild B")]

    info = await _identify(client)

    assert info == {"id": 42, "name": "testbot", "guilds": ["Guild A", "Guild B"]}


# ── step 2: invite URL ─────────────────────────────────────────────


def test_invite_url_carries_the_bitfield_for_the_chosen_permissions():
    """The bitfield is the whole point of the step: an invite generated with
    the wrong bits produces a bot that logs in fine and then 403s on the
    first real command."""
    import discord

    from discli.commands.setup import _invite_url

    url = _invite_url(42, ["send_messages", "view_channel"])

    expected = discord.Permissions(send_messages=True, view_channel=True).value
    assert f"client_id=42" in url
    assert f"permissions={expected}" in url
    assert "scope=bot" in url


def test_every_bundled_permission_is_one_discli_actually_uses():
    """The invite the wizard generates and the permissions doctor checks for
    have to be the same set. If they drift, `discli setup` hands you a URL
    that grants something no command needs, or omits something every command
    does -- and `discli doctor --server X` then reports a gap the wizard just
    told you it had covered.
    """
    import discord

    from discli.commands.doctor import DISCLI_PERMISSIONS
    from discli.commands.setup import BUNDLES

    valid_flags = set(discord.Permissions.VALID_FLAGS)
    for bundle, (_desc, names) in BUNDLES.items():
        for name in names:
            assert name in valid_flags, f"{bundle}: {name} is not a discord.py permission"
            assert name in DISCLI_PERMISSIONS, (
                f"{bundle}: {name} is not in doctor's DISCLI_PERMISSIONS"
            )


# ── step 4: voice provider env vars ────────────────────────────────


def test_export_lines_use_posix_shell_syntax():
    from discli.commands.setup import _export_lines

    lines = _export_lines([("DISCLI_TTS", "elevenlabs")], windows=False)

    assert lines == ["export DISCLI_TTS=elevenlabs"]


def test_export_lines_use_setx_on_windows():
    """discli supports Windows first-class -- cli.py exists partly to cope
    with it -- so handing a Windows user `export` is handing them a line
    that does nothing."""
    from discli.commands.setup import _export_lines

    lines = _export_lines([("DISCLI_TTS", "elevenlabs")], windows=True)

    assert lines == ['setx DISCLI_TTS "elevenlabs"']


def test_export_lines_quote_a_placeholder_that_the_shell_would_eat():
    """The placeholder for an unknown secret contains angle brackets, which
    a posix shell reads as redirection -- pasted unquoted it truncates the
    file it points at."""
    from discli.commands.setup import _export_lines

    lines = _export_lines([("ELEVENLABS_API_KEY", "<your-key>")], windows=False)

    assert lines == ["export ELEVENLABS_API_KEY='<your-key>'"]


# ── driving the whole wizard ───────────────────────────────────────


WIZARD_INPUT = "tok-abc\ny\nn\nn\nn\nchat\nn\n"
"""Answers for a full run with no token configured and no voice extras:
token, the four capability bundles, the profile choice, then declining
voice. Leftover lines are simply never read, so a step that does not exist
yet does not invalidate the rest."""


def _login_returns(info):
    """Stand in for a real Discord login at the run_rest_action seam.

    conftest's autouse no_network fixture makes any real request an error,
    which is exactly right here -- this is the one place the wizard talks to
    Discord, and it has to be replaced rather than reached.
    """

    async def _fake(token, action):
        client = type("C", (), {})()
        client.user = _FakeUser(info["id"], info["name"])
        client.guilds = [_FakeGuild(name) for name in info["guilds"]]
        return await action(client)

    return _fake


@pytest.fixture
def wizard(monkeypatch, tmp_path):
    """A wizard with a terminal, an empty config, and a stubbed login."""
    monkeypatch.setattr("discli.commands.setup._is_interactive", lambda: True)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.setattr("discli.config.load_config", lambda *a, **k: {})
    # Otherwise the profile step reads the developer's own ~/.discli and the
    # prompt default varies by machine.
    monkeypatch.setattr("discli.security.PERMISSIONS_PATH", tmp_path / "permissions.json")

    saved = {}
    monkeypatch.setattr("discli.config.save_config", lambda data, *a, **k: saved.update(data))
    monkeypatch.setattr("discli.security.set_active_profile", lambda name: saved.update(profile=name))
    # Without this the voice step branches on whether the developer happens
    # to have the voice extras installed, and WIZARD_INPUT stops lining up.
    monkeypatch.setattr("discli.commands.doctor._voice_extras_installed", lambda: False)
    monkeypatch.setattr(
        "discli.client.run_rest_action",
        _login_returns({"id": 42, "name": "testbot", "guilds": ["Guild A"]}),
    )
    return saved


def test_the_wizard_saves_a_token_that_logs_in(wizard):
    result = CliRunner().invoke(main, ["setup"], input=WIZARD_INPUT)

    assert result.exit_code == 0, result.output
    assert wizard["token"] == "tok-abc"
    assert "testbot" in result.output


def test_a_token_discord_rejects_is_never_saved(wizard, monkeypatch):
    """Saving first and verifying later leaves a broken token in
    config.json that every later command picks up, so the failure surfaces
    somewhere far away from the paste that caused it."""
    import discord

    async def _rejects(token, action):
        raise discord.LoginFailure("Improper token has been passed.")

    monkeypatch.setattr("discli.client.run_rest_action", _rejects)

    result = CliRunner().invoke(main, ["setup"], input="bad1\nbad2\nbad3\n")

    assert result.exit_code == 1
    assert "token" not in wizard
    assert "No working bot token" in result.output


# ── step 2: invite ─────────────────────────────────────────────────


def test_the_wizard_offers_an_invite_url_for_the_bot_it_authenticated(wizard):
    """The bot user ID from step 1 is also the application ID, so the wizard
    never has to ask for a client ID separately."""
    import discord

    result = CliRunner().invoke(main, ["setup"], input=WIZARD_INPUT)

    messaging = discord.Permissions(**{n: True for n in _messaging_names()}).value
    assert f"client_id=42" in result.output
    assert f"permissions={messaging}" in result.output


def _messaging_names():
    from discli.commands.setup import BUNDLES

    return BUNDLES["messaging"][1]


# ── step 3: permission profile ─────────────────────────────────────


def test_the_wizard_writes_the_chosen_permission_profile(wizard):
    result = CliRunner().invoke(main, ["setup"], input=WIZARD_INPUT)

    assert result.exit_code == 0, result.output
    assert wizard["profile"] == "chat"


def test_choosing_a_restricted_profile_names_the_way_back_in(wizard):
    """setup is full-only, so the step that narrows the profile is also the
    step that locks the user out of re-running it. Saying so at the moment
    of the choice is the only place that warning is useful."""
    result = CliRunner().invoke(main, ["setup"], input=WIZARD_INPUT)

    assert "--profile full setup" in result.output


# ── step 4: voice ──────────────────────────────────────────────────


def test_declining_voice_asks_nothing_further_about_providers(wizard):
    """Most people never touch voice. The step should cost them one `n`,
    not a walk through provider choices they do not want."""
    result = CliRunner().invoke(main, ["setup"], input=WIZARD_INPUT)

    assert result.exit_code == 0, result.output
    assert "4. Voice" in result.output
    assert "DISCLI_TTS" not in result.output


def test_choosing_a_tts_provider_names_the_variables_to_export(wizard, monkeypatch):
    """tts.py reads its credentials from the environment, never from
    config.json, so the only thing the wizard can usefully do is say exactly
    which variables to set."""
    monkeypatch.setattr("discli.commands.doctor._voice_extras_installed", lambda: True)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    result = CliRunner().invoke(
        main, ["setup"], input="tok-abc\ny\nn\nn\nn\nchat\nelevenlabs\nnone\n"
    )

    assert result.exit_code == 0, result.output
    assert "DISCLI_TTS" in result.output
    assert "ELEVENLABS_API_KEY" in result.output
