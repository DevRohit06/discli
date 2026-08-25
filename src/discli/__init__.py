"""discli — Discord CLI for AI agents."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("discord-cli-agent")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "unknown"

__all__ = ["__version__"]
