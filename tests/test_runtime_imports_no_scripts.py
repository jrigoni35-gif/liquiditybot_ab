"""The runtime tree must not import from scripts/.

WHY THIS EXISTS. `scripts/` is the analysis-and-operator tree: report lenses,
backfills, one-shot tools. Nothing there is on the decision path, and several
things depend on that being true:

  * scripts/auto_update.py's deploy reasoning treats a scripts/-only change as
    unable to alter engine behaviour (and any future change-scoped restart
    would lean on it directly);
  * data/candle_journal.py's SAFE-class fence and this repo's report-only
    classification both assume analysis reads the decision tree, never the
    reverse;
  * the daily learning panel runs scripts/ as SUBPROCESSES precisely so their
    imports can never reach the engine.

The invariant HELD when this file was written (a repo-wide scan found zero
runtime imports of scripts). Nothing pinned it. tests/test_import_integrity.py
imports each runtime module in isolation and asserts it does not raise -- a
module that successfully does `from scripts.util import helper` passes that
suite green, because importing cleanly is exactly what it checks.

The break it allows is two commits and neither looks wrong alone:
  commit A  adds `from scripts.util import helper` inside core/something.py
            (touches core/, so any reviewer or classifier flags it correctly)
  commit B  changes ONLY scripts/util.py's body -- a scripts/-only diff that
            silently changes what the engine does.
This file makes commit A impossible, which is where the break is cheap.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The shipped decision tree, mirroring CLAUDE.md's pyright line.
RUNTIME_TREES = ("core", "data", "execution", "ml", "risk", "regime",
                 "strategies", "sentiment", "api")
RUNTIME_FILES = ("main.py", "runner.py")

FORBIDDEN_ROOT = "scripts"


def _runtime_files() -> list[Path]:
    out: list[Path] = []
    for tree in RUNTIME_TREES:
        d = REPO_ROOT / tree
        if not d.is_dir():
            continue
        out += [p for p in d.rglob("*.py") if "__pycache__" not in p.parts]
    for name in RUNTIME_FILES:
        p = REPO_ROOT / name
        if p.is_file():
            out.append(p)
    return out


def _imports_forbidden_root(path: Path) -> list[str]:
    """Every import in `path` whose top-level module is `scripts`.

    AST, not a substring grep: a docstring or comment that merely NAMES a
    script (several runtime modules legitimately point at their report tools)
    creates no dependency and must not trip this. An `import` statement
    cannot hide in a comment, so this is also the stricter check.

    Catches `import scripts.x`, `import scripts.x as y`, `from scripts import x`
    and `from scripts.x import y`. A RELATIVE import (level > 0) can never
    reach a top-level `scripts` package from inside these trees, so node.module
    is only consulted at level 0.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):  # pragma: no cover - compileall owns syntax
        return []
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] == FORBIDDEN_ROOT:
                    hits.append(f"line {node.lineno}: import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level:            # relative - cannot reach top-level scripts
                continue
            mod = node.module or ""
            if mod.split(".")[0] == FORBIDDEN_ROOT:
                names = ", ".join(a.name for a in node.names)
                hits.append(f"line {node.lineno}: from {mod} import {names}")
    return hits


# --------------------------------------------------------------------------
# the invariant
# --------------------------------------------------------------------------

def test_no_runtime_module_imports_from_scripts():
    offenders: dict[str, list[str]] = {}
    for p in _runtime_files():
        hits = _imports_forbidden_root(p)
        if hits:
            offenders[p.relative_to(REPO_ROOT).as_posix()] = hits
    assert not offenders, (
        "the runtime tree imported from scripts/, which breaks the premise "
        "that a scripts/-only change cannot alter engine behaviour:\n"
        + "\n".join(f"  {k}: {v}" for k, v in offenders.items())
        + "\nMove the shared code into a runtime package (core/ is usually "
          "right) and import it from BOTH sides, rather than reaching up "
          "into scripts/ from the engine.")


# --------------------------------------------------------------------------
# the guard must be able to fail, and must reach the real tree
# --------------------------------------------------------------------------

def test_the_scan_actually_reaches_the_runtime_tree():
    """A guard that sweeps nothing passes forever."""
    files = _runtime_files()
    assert len(files) > 100, f"only {len(files)} runtime files swept"
    names = {p.name for p in files}
    assert "main.py" in names and "runner.py" in names
    swept = {p.relative_to(REPO_ROOT).parts[0] for p in files}
    for tree in RUNTIME_TREES:
        if (REPO_ROOT / tree).is_dir():
            assert tree in swept, f"{tree}/ was not swept"


@pytest.mark.parametrize("snippet", [
    "import scripts.util\n",
    "import scripts.util as u\n",
    "from scripts import util\n",
    "from scripts.util import helper\n",
    "def f():\n    from scripts.util import helper\n    return helper\n",
])
def test_the_guard_catches_every_import_form(tmp_path, snippet):
    """Including a deferred import inside a function body -- the form someone
    reaches for precisely when they suspect a top-level import is wrong."""
    p = tmp_path / "planted.py"
    p.write_text(snippet, encoding="utf-8")
    assert _imports_forbidden_root(p), f"guard missed: {snippet!r}"


@pytest.mark.parametrize("snippet", [
    '"""See scripts/regime_chain_report.py for the surfaced chain."""\n',
    "# import scripts.util  <- deliberately not done\n",
    "import corescripts\n",
    "from scriptsy import thing\n",
    "from . import scripts\n",
])
def test_the_guard_does_not_fire_on_mentions_or_lookalikes(tmp_path, snippet):
    """It must not push the next author to delete a useful cross-reference to
    get the suite green -- that would trade a real comment for a fake pass."""
    p = tmp_path / "innocent.py"
    p.write_text(snippet, encoding="utf-8")
    assert not _imports_forbidden_root(p), f"false positive on: {snippet!r}"
