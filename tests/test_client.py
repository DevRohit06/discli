import click
import pytest

from discli.client import resolve_token


def test_resolve_token_from_arg():
    assert resolve_token("my-token", {}) == "my-token"


def test_resolve_token_from_config():
    assert resolve_token(None, {"token": "config-token"}) == "config-token"


def test_resolve_token_missing():
    with pytest.raises(click.ClickException):
        resolve_token(None, {})
