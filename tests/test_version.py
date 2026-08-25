from click.testing import CliRunner

import discli
from discli.cli import main


def test_version_long_flag():
    result = CliRunner().invoke(main, ["--version"])

    assert result.exit_code == 0, result.output
    assert result.output == f"discli version {discli.__version__}\n"


def test_version_short_flag():
    result = CliRunner().invoke(main, ["-V"])

    assert result.exit_code == 0, result.output
    assert result.output == f"discli version {discli.__version__}\n"


def test_version_needs_no_token(monkeypatch):
    """`--version` must not touch config or require a token."""

    def fail(*args, **kwargs):
        raise AssertionError("--version must not load the config file")

    monkeypatch.setattr("discli.cli.load_config", fail)

    result = CliRunner().invoke(main, ["--version"])

    assert result.exit_code == 0, result.output


def test_version_matches_package_metadata():
    assert discli.__version__ != "unknown"
    assert discli.__version__[0].isdigit()


def test_version_listed_in_help():
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0, result.output
    assert "-V, --version" in result.output
