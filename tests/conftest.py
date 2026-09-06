"""Shared test fixtures.

Deliberately does not set ``asyncio_mode``: async tests in this suite carry an
explicit ``@pytest.mark.asyncio``, and changing the mode would alter how every
existing test is collected.
"""

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail loudly if a test reaches Discord's API.

    Most tests replace ``discord.Client`` with a fake, so they never get near
    the network. But anything that drives the CLI end to end -- a scheduled
    action, for instance -- constructs the real client, and discli falls back
    to the token in ``~/.discli/config.json``. A test written that way passes
    on a developer machine while quietly making live API calls against their
    own Discord account, and fails in CI where no token exists.

    Patching at the HTTP layer catches that regardless of how the client was
    built. Autouse so no future test can opt out by forgetting.
    """
    import discord.http

    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)

    async def _blocked(*args, **kwargs):
        raise AssertionError(
            "test attempted a real Discord API request; fake discord.Client "
            "or patch the call instead"
        )

    monkeypatch.setattr(discord.http.HTTPClient, "request", _blocked)
    monkeypatch.setattr(discord.http.HTTPClient, "static_login", _blocked)
