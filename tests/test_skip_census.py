"""A skipped test is a referee that is not running. Growth must be conscious.

D5 on the 2026-09-10 plan. Skips are legitimate - an optional dependency, a
platform-specific path, a tool that may be absent - but they are also the
cheapest way to make a red test disappear, and nothing in this repo noticed when
one appeared. A suite whose skip count drifts upward loses coverage with no
failing signal, which is the same silent-erosion shape as an unpinned gate tool.

TWO PROPERTIES, chosen because neither goes stale the way a hardcoded inventory
would (this repo has paid for stale literals in prose repeatedly):

  1. EVERY skip carries a REASON. pytest does not require one for `skipif`, and
     a reasonless skip is unauditable - a later reader cannot tell a deliberate
     platform guard from a parked failure.
  2. The TOTAL marker count is a RATCHET. One number, updated consciously when a
     skip is genuinely added. It cannot drift.

WHAT THIS DELIBERATELY DOES NOT CLAIM. Marker count is not runtime skip count:
19 files carry markers while the battery reports 9 actual skips, because most
markers are conditional and their condition is false on this host. This pins the
STATIC surface - the number of places that *can* skip. Pinning the runtime
number would mean running the suite from inside the suite.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS = REPO_ROOT / "tests"

# The static skip surface as measured 2026-09-10. RAISE THIS CONSCIOUSLY, in the
# same commit as the skip you are adding, and say in the message why the referee
# may stand down. Lowering it is always welcome.
MAX_SKIP_MARKERS = 31

_SKIP = re.compile(r"pytest\.mark\.skipif|pytest\.mark\.skip\b|pytest\.skip\b")


def _test_files() -> list:
    return sorted(p for p in TESTS.glob("*.py") if p.name.startswith("test_"))


def _skip_sites(path: Path) -> list:
    """(lineno, source line) for every skip marker, comments excluded."""
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8",
                                            errors="replace").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if _SKIP.search(line):
            out.append((n, stripped))
    return out


def test_the_census_actually_reaches_the_suite():
    """A census over an empty file list passes forever."""
    files = _test_files()
    assert len(files) > 200, f"only {len(files)} test files scanned"


def test_the_static_skip_surface_has_not_grown():
    sites = [(p.name, n, s) for p in _test_files() for n, s in _skip_sites(p)]
    assert len(sites) <= MAX_SKIP_MARKERS, (
        f"skip markers grew to {len(sites)} (ratchet {MAX_SKIP_MARKERS}). A "
        f"skipped test is a referee that is not running - raise the ratchet in "
        f"the same commit as the skip and say why it may stand down:\n  "
        + "\n  ".join(f"{f}:{n}: {s[:90]}" for f, n, s in sites[-8:]))


def test_the_ratchet_is_not_slack():
    """A ceiling far above reality stops catching anything. Keeps the ratchet
    honest by bounding the headroom it is allowed to carry."""
    actual = sum(len(_skip_sites(p)) for p in _test_files())
    assert actual >= MAX_SKIP_MARKERS - 6, (
        f"only {actual} skip markers against a ratchet of {MAX_SKIP_MARKERS} - "
        f"the ceiling has drifted above reality and no longer constrains. "
        f"Lower MAX_SKIP_MARKERS to {actual}.")


def test_every_skip_states_a_reason():
    """An unexplained skip is unauditable: a reader cannot tell a deliberate
    platform guard from a parked failure."""
    offenders = []
    for path in _test_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:                     # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
            if not (name.endswith("pytest.mark.skipif") or name.endswith("pytest.mark.skip")
                    or name.endswith("pytest.skip")):
                continue
            has_reason = any(k.arg == "reason" for k in node.keywords)
            # pytest.skip("why") and mark.skip("why") take it positionally
            if not has_reason and not node.args:
                offenders.append(f"{path.name}:{node.lineno}: {name}")
            elif not has_reason and node.args:
                first = node.args[-1]
                # An f-string is ast.JoinedStr, NOT ast.Constant. The first cut
                # of this check accepted only Constant and flagged three
                # correctly-reasoned skips as defective -
                # `pytest.skip(f"cohort boundary unavailable: {why}")` is a
                # BETTER reason than a literal, because it names the actual
                # cause at runtime. Caught by running the check, not by review.
                ok = (isinstance(first, ast.Constant)
                      and isinstance(first.value, str) and first.value.strip())
                ok = ok or isinstance(first, ast.JoinedStr)
                if not ok:
                    offenders.append(f"{path.name}:{node.lineno}: {name}")
    assert not offenders, (
        "skip markers with no reason - a reader cannot audit these:\n  "
        + "\n  ".join(offenders))
