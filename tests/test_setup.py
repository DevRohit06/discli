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


@pytest.fixture(autouse=True)
def _isolate_profile(monkeypatch, tmp_path):
    """Keep an ambient permission profile out of every test in this file.

    enforce_profile() consults DISCLI_PROFILE (an envvar on the root group)
    and ~/.discli/permissions.json, and it denies `setup` before the
    terminal check runs. On a machine with either set, most of these tests
    fail with "denied by the readonly permission profile" -- a reason that
    has nothing to do with what they assert. Same class of leakage that
    conftest's no_network fixture exists to prevent.
    """
    monkeypatch.delenv("DISCLI_PROFILE", raising=False)
    monkeypatch.setattr("discli.security.PERMISSIONS_PATH", tmp_path / "permissions.json")


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

    assert info == {"id": 42, "name": "testbot", "guilds": ["Guild A", "Guild B"], "more": 0}


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
def wizard(monkeypatch):
    """A wizard with a terminal, an empty config, and a stubbed login."""
    monkeypatch.setattr("discli.commands.setup._is_interactive", lambda: True)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

    saved = {}
    # Store-backed rather than a black hole: step 5 runs doctor's real token
    # check, which reads load_config(), so a save that went nowhere would
    # make the wizard report a failure it had just fixed.
    store = lambda *a, **k: dict(saved)
    monkeypatch.setattr("discli.config.load_config", store)
    # doctor.py binds load_config at import, so patching discli.config alone
    # never reaches step 5's token check.
    monkeypatch.setattr("discli.commands.doctor.load_config", store)
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
    # Claiming the extras are installed also makes doctor run the real VOICE
    # section, which fails on a machine without libopus. This test is about
    # step 4, so step 5 is stubbed out rather than asserted around.
    monkeypatch.setattr("discli.commands.doctor._gather", lambda server=None: [])

    result = CliRunner().invoke(
        main, ["setup"], input="tok-abc\ny\nn\nn\nn\nchat\ny\nelevenlabs\nnone\n"
    )

    assert result.exit_code == 0, result.output
    assert "DISCLI_TTS" in result.output
    assert "ELEVENLABS_API_KEY" in result.output


def test_the_generated_invite_passes_doctors_own_permission_split_check():
    """A bot invited with `manage_messages` but not `bypass_slowmode` holds
    the old bit and not the split-out one, which is exactly the regression
    doctor reports. The wizard prints an invite URL and then, at step 5,
    runs the check that would condemn it -- so any bundle granting a legacy
    permission has to grant what Discord split out of it too.
    """
    import discord

    from discli.commands.doctor import PERMISSION_SPLITS
    from discli.commands.setup import BUNDLES

    granted = [name for _desc, names in BUNDLES.values() for name in names]
    perms = discord.Permissions(**{name: True for name in granted})

    regressions = [
        new for new, legacy, _since, _affected in PERMISSION_SPLITS
        if getattr(perms, legacy, False) and not getattr(perms, new, False)
    ]
    assert regressions == [], (
        "granting every bundle still trips doctor's split check for: "
        + ", ".join(regressions)
    )


def test_an_active_custom_profile_stays_selectable(monkeypatch, tmp_path, wizard):
    """security.get_active_profile() supports a `profiles` map of custom
    profiles, so the wizard has to as well. Offering a default that is not
    one of the click.Choice values means pressing Enter is rejected -- and
    with show_choices off, the valid set is never even shown.
    """
    import json

    perms = tmp_path / "permissions.json"
    perms.write_text(json.dumps({
        "active_profile": "mycustom",
        "profiles": {"mycustom": {"description": "custom", "allowed": ["*"], "denied": []}},
    }))
    monkeypatch.setattr("discli.security.PERMISSIONS_PATH", perms)

    # Empty answer at the profile prompt = keep what is already active.
    result = CliRunner().invoke(main, ["setup"], input="tok-abc\ny\nn\nn\nn\n\nn\n")

    assert result.exit_code == 0, result.output
    assert wizard["profile"] == "mycustom"
    assert "is not one of" not in result.output


# ── exit status and stream detection ───────────────────────────────


class _Stream:
    def __init__(self, tty):
        self._tty = tty

    def isatty(self):
        return self._tty


def test_a_redirected_stdout_is_not_interactive(monkeypatch):
    """`discli setup > log` keeps a tty on stdin, so a stdin-only check
    passes -- and then click writes every prompt into the file. The user
    sees a silent hung terminal, which is the exact failure the guard is
    supposed to prevent."""
    from discli.commands import setup as setup_mod

    monkeypatch.setattr(setup_mod.sys, "stdin", _Stream(True))
    monkeypatch.setattr(setup_mod.sys, "stdout", _Stream(False))

    assert setup_mod._is_interactive() is False


def test_two_terminals_are_interactive(monkeypatch):
    from discli.commands import setup as setup_mod

    monkeypatch.setattr(setup_mod.sys, "stdin", _Stream(True))
    monkeypatch.setattr(setup_mod.sys, "stdout", _Stream(True))

    assert setup_mod._is_interactive() is True


def test_the_wizard_exits_nonzero_when_its_own_report_shows_failures(wizard, monkeypatch):
    """`discli doctor` exits 1 on failures. If setup prints the same report
    and exits 0, `discli setup && echo ready` says ready for a broken
    install, and any onboarding script keying on $? reads success."""
    from discli.commands.doctor import Check, Section

    monkeypatch.setattr(
        "discli.commands.doctor._gather",
        lambda server=None: [Section("CORE", [Check("ffmpeg", False, "not on PATH")])],
    )

    result = CliRunner().invoke(main, ["setup"], input=WIZARD_INPUT)

    assert result.exit_code == 1, result.output


def test_the_wizard_exits_zero_when_everything_checks_out(wizard):
    result = CliRunner().invoke(main, ["setup"], input=WIZARD_INPUT)

    assert result.exit_code == 0, result.output


def test_the_voice_step_defaults_to_the_providers_already_configured(wizard, monkeypatch):
    """README promises re-running is safe because "every step shows what is
    already configured and offers to keep it". Hardcoding `none` makes step 4
    offer to un-configure a working setup."""
    monkeypatch.setenv("DISCLI_TTS", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-live")

    # ... profile, then yes to voice, then Enter through both providers.
    result = CliRunner().invoke(main, ["setup"], input="tok-abc\ny\nn\nn\nn\nchat\ny\n\n\n")

    assert result.exit_code == 0, result.output
    assert "DISCLI_TTS=elevenlabs" in result.output or 'DISCLI_TTS "elevenlabs"' in result.output


def test_voice_can_be_declined_even_when_the_extras_are_installed(wizard, monkeypatch):
    """The skip only existed when the extras were missing, so someone who
    installed them for `voice play` alone was marched through two provider
    prompts they never wanted. The step is titled "(optional)"."""
    monkeypatch.setattr("discli.commands.doctor._voice_extras_installed", lambda: True)
    monkeypatch.setattr("discli.commands.doctor._gather", lambda server=None: [])

    result = CliRunner().invoke(main, ["setup"], input=WIZARD_INPUT)

    assert result.exit_code == 0, result.output
    assert "TTS provider" not in result.output


def test_saving_a_token_while_the_env_var_shadows_it_says_so(wizard, monkeypatch):
    """cli.py resolves --token from DISCORD_BOT_TOKEN before falling back to
    config.json. Saving a different token there and reporting OK leaves the
    user certain they switched bots when every command still uses the old
    one."""
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "env-token")

    # Decline the env token, paste a different one.
    result = CliRunner().invoke(
        main, ["setup"], input="n\npasted-token\ny\nn\nn\nn\nchat\nn\n"
    )

    assert wizard["token"] == "pasted-token"
    assert "still takes precedence" in result.output


def test_setup_picks_up_discord_token_candidate_without_shadowing(wizard, monkeypatch):
    """setup offers DISCORD_TOKEN as fallback candidate, but saving to config does not warn of shadowing."""
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.setenv("DISCORD_TOKEN", "discord-token")

    result = CliRunner().invoke(
        main, ["setup"], input="n\npasted-token\ny\nn\nn\nn\nchat\nn\n"
    )

    assert wizard["token"] == "pasted-token"
    assert "still takes precedence" not in result.output


def test_setup_reuses_discord_token_when_confirmed(wizard, monkeypatch):
    """setup accepts DISCORD_TOKEN when user confirms reusing existing token."""
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.setenv("DISCORD_TOKEN", "discord-token")

    result = CliRunner().invoke(
        main, ["setup"], input="y\ny\nn\nn\nn\nchat\nn\n"
    )

    assert result.exit_code == 0
    assert "1. Bot token" in result.output
    assert "still takes precedence" not in result.output


@pytest.mark.asyncio
async def test_identify_caps_the_guild_list_it_reports():
    """The step only needs to prove *which* bot the token belongs to. A bot
    in 500 guilds should not pay for five paginated requests, nor render 500
    names into one wrapped line, to establish that."""
    from discli.commands.setup import _identify

    client = type("C", (), {})()
    client.user = _FakeUser(42, "testbot")
    client.guilds = [_FakeGuild(f"G{i}") for i in range(12)]

    info = await _identify(client)

    assert len(info["guilds"]) == 10
    assert info["more"] == 2


def test_git_bash_on_windows_gets_export_not_setx(monkeypatch):
    """os.name is "nt" inside Git Bash and MSYS -- the shell this repo's own
    tooling runs in -- where setx is either missing or sets a variable bash
    will never read."""
    from discli.commands.setup import _windows_shell

    monkeypatch.setattr("discli.commands.setup.os.name", "nt")
    monkeypatch.setenv("MSYSTEM", "MINGW64")

    assert _windows_shell() is False


def test_a_plain_windows_console_gets_setx(monkeypatch):
    from discli.commands.setup import _windows_shell

    monkeypatch.setattr("discli.commands.setup.os.name", "nt")
    monkeypatch.delenv("MSYSTEM", raising=False)
    monkeypatch.delenv("SHELL", raising=False)

    assert _windows_shell() is True


def test_every_permission_discli_uses_is_offered_by_some_bundle():
    """The other direction of the same invariant. Without it, a permission
    added to doctor's map is never offered by the wizard, so `setup` quietly
    stops producing an invite that covers every command."""
    from discli.commands.doctor import DISCLI_PERMISSIONS
    from discli.commands.setup import BUNDLES

    offered = {name for _desc, names in BUNDLES.values() for name in names}
    missing = sorted(set(DISCLI_PERMISSIONS) - offered)

    assert missing == [], f"no bundle offers: {', '.join(missing)}"
