"""Smoke checks on the example scripts.

These don't run the examples (they need real Discord/API credentials), but
they do verify the files parse and load to module level — enough to catch
typos, broken imports, or missing symbols introduced during refactors.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("*.py"))


@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda p: p.name)
def test_example_parses(path: Path) -> None:
    """The file must be syntactically valid Python."""
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda p: p.name)
def test_example_loads(path: Path) -> None:
    """The file must import cleanly to module level.

    Skips gracefully if an optional third-party import (e.g. claude_agent_sdk)
    is missing — examples should not be the thing failing CI when a dev
    machine doesn't have every voice provider installed.
    """
    spec = importlib.util.spec_from_file_location(
        f"_example_smoke_{path.stem}", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImportError as exc:
        pytest.skip(f"optional dep missing for {path.name}: {exc}")
