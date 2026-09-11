"""A gate tool that moves under the repo changes what GREEN MEANS.

CLAUDE.md's definition of done is eight commands, and four of them are tools
whose behaviour decides whether a change ships: pytest, ruff, bandit, pyright.
Measured 2026-09-10, NONE was version-pinned in any tracked file, while the same
file requires pyright's shipped scope to hold at ZERO errors.

That is not a theoretical risk here. The same day, pyright went RED with
"Please install the new version..." and then GREEN after an install, with no
source change between the runs. The tool moved; the code did not. Nothing in the
repo would have recorded that.

WHAT THIS PINS, and what it deliberately does not. It asserts the INSTALLED
version satisfies the range declared in requirements-dev.txt - not that it
equals some literal written here. Exact equality would go red on every routine
patch bump and be deleted as noise inside a week; a range catches the event that
matters (a tool leaving the vetted window) and stays quiet otherwise.

It also asserts every DoD tool is actually declared, so the pin file cannot
silently fall behind the checklist it exists to cover.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PINS = REPO_ROOT / "requirements-dev.txt"

# Mirrors CLAUDE.md's definition-of-done command list.
DOD_TOOLS = ("pytest", "ruff", "bandit", "pyright")

_SPEC = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)\s*>=\s*(?P<lo>[0-9][0-9.]*)\s*,\s*<\s*(?P<hi>[0-9][0-9.]*)\s*$")


def _parse_pins() -> dict:
    out = {}
    for line in PINS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _SPEC.match(line)
        assert m, f"unparseable pin line (expected name>=lo,<hi): {line!r}"
        out[m.group("name")] = (m.group("lo"), m.group("hi"))
    return out


def _ver_tuple(s: str) -> tuple:
    return tuple(int(p) for p in re.findall(r"\d+", s))


def _installed(tool: str) -> str:
    """Ask the tool itself. Reading metadata would report what pip THINKS is
    installed; the battery runs the executable, so the executable is the
    authority."""
    out = subprocess.run([sys.executable, "-m", tool, "--version"],
                         capture_output=True, text=True, timeout=180)
    blob = (out.stdout or "") + (out.stderr or "")
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", blob)
    assert m, f"could not read a version out of `{tool} --version`: {blob[:200]!r}"
    return m.group(1)


# --------------------------------------------------------------------------

def test_the_pin_file_exists_and_parses():
    assert PINS.is_file(), "requirements-dev.txt is missing"
    assert _parse_pins(), "no pins parsed - the file guards nothing"


@pytest.mark.parametrize("tool", DOD_TOOLS)
def test_every_definition_of_done_tool_is_pinned(tool):
    """Non-vacuous coverage: the checklist and the pin file must not drift
    apart. A tool absent here is a tool that can move freely."""
    assert tool in _parse_pins(), (
        f"{tool} runs in CLAUDE.md's definition of done but is not pinned in "
        f"requirements-dev.txt - it can change what green means with no diff")


@pytest.mark.parametrize("tool", DOD_TOOLS)
def test_the_installed_version_is_inside_its_declared_window(tool):
    lo, hi = _parse_pins()[tool]
    got = _installed(tool)
    assert _ver_tuple(lo) <= _ver_tuple(got) < _ver_tuple(hi), (
        f"{tool} {got} is outside the vetted window [{lo}, {hi}). Either the "
        f"tool was upgraded without adjusting the pin, or the pin was raised "
        f"without installing. Bumping is fine - do it consciously: raise the "
        f"pin, run the full battery, read what changed.")


def test_the_window_is_a_window_not_a_wildcard():
    """A pin with no ceiling is not a pin. Guards against someone 'fixing' a
    red by widening the range to everything."""
    for name, (lo, hi) in _parse_pins().items():
        assert _ver_tuple(hi) > _ver_tuple(lo), f"{name}: ceiling <= floor"
        assert _ver_tuple(hi) != (9999,), f"{name}: wildcard ceiling"
