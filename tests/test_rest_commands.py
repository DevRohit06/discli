from click.testing import CliRunner

from discli.cli import main


def test_reaction_list_uses_http_without_gateway(monkeypatch):
    class FakeReaction:
        emoji = "ok"
        count = 3

    class FakeMessage:
        reactions = [FakeReaction()]

    class FakeChannel:
        async def fetch_message(self, message_id):
            assert message_id == 456
            return FakeMessage()

    class FakeClient:
        def __init__(self, *, intents):
            self.closed = False

        async def login(self, token):
            assert token == "token"

        async def fetch_channel(self, channel_id):
            assert channel_id == 123
            return FakeChannel()

        async def start(self, token):
            raise AssertionError("reaction list must not start Gateway")

        async def close(self):
            self.closed = True

    monkeypatch.setattr("discli.client.discord.Client", FakeClient)

    result = CliRunner().invoke(
        main,
        ["--token", "token", "reaction", "list", "123", "456"],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "ok x3\n"
