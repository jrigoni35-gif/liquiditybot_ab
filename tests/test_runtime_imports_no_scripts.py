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

# NOT the runtime tree: analysis, tooling, docs and generated state. Anything
# else at top level that is an importable package IS runtime and gets swept.
NON_RUNTIME_DIRS = frozenset({
    "tests", "scripts", "docs", "outputs", "diode", "tools", "build", "dist",
})

# The shipped decision tree as it stands today, mirroring CLAUDE.md's pyright
# line. This is a RATCHET, not the sweep list — see _runtime_trees().
EXPECTED_RUNTIME_TREES = frozenset({
    "core", "data", "execution", "ml", "risk", "regime",
    "strategies", "sentiment", "api",
})
RUNTIME_FILES = ("main.py", "runner.py")

FORBIDDEN_ROOT = "scripts"


def _runtime_trees() -> set[str]:
    """Top-level importable packages, DISCOVERED — never hardcoded.

    The first cut of this file swept a hardcoded 9-name tuple. An adversarial
    review mutation-confirmed the hole: a `scripts/` import placed in any
    package outside that tuple was invisible to the guard, so the fence went
    green on exactly the edit it exists to stop. A hardcoded sweep list is a
    guard that silently narrows every time the codebase grows.

    Discovery fails SAFE in the only direction that matters: an unrecognised
    top-level package is swept (more coverage), never skipped. `NON_RUNTIME_DIRS`
    is a deny-list rather than the runtime set being an allow-list, so
    forgetting to update anything results in MORE scanning, not less.

    That fail-safe claim was FALSE for one shape until 2026-09-10, and the
    docstring above asserted it anyway. Requiring `__init__.py` skipped PEP 420
    NAMESPACE packages, which are importable with no `__init__.py` at all - so
    a new top-level runtime tree created without one was invisible to the
    fence, the precise hole this function was written to close, reintroduced
    one level down. A directory holding importable `.py` files is now swept
    whether or not it declares `__init__.py`.

    Measured when the branch was added: it changes NOTHING on this tree - all
    nine runtime packages already carry `__init__.py`, and every other
    top-level directory is in NON_RUNTIME_DIRS. It is a fence for the tree's
    future, so it cannot be verified by observing today's behaviour; the
    injection test at the bottom of this file plants a namespace package with
    a forbidden import and proves the sweep reaches it.
    """
    def _importable(p: Path) -> bool:
        if (p / "__init__.py").is_file():
            return True
        # PEP 420: no marker file, so presence of any module is the signal.
        return any(q for q in p.rglob("*.py") if "__pycache__" not in q.parts)

    return {
        p.name for p in REPO_ROOT.iterdir()
        if p.is_dir()
        and not p.name.startswith(".")
        and p.name != "__pycache__"
        and p.name not in NON_RUNTIME_DIRS
        and _importable(p)
    }


def _runtime_files() -> list[Path]:
    out: list[Path] = []
    for tree in sorted(_runtime_trees()):
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
    for tree in EXPECTED_RUNTIME_TREES:
        if (REPO_ROOT / tree).is_dir():
            assert tree in swept, f"{tree}/ was not swept"


def test_discovery_finds_every_expected_runtime_tree():
    """Discovery must not silently NARROW below the known runtime set.

    If a package stops being discovered (an `__init__.py` deleted, a rename),
    the fence would quietly stop scanning it and stay green.
    """
    missing = {t for t in EXPECTED_RUNTIME_TREES
               if (REPO_ROOT / t).is_dir()} - _runtime_trees()
    assert not missing, (
        f"these shipped packages are no longer discovered: {sorted(missing)} - "
        f"the fence has silently narrowed")


def test_a_new_top_level_package_is_swept_automatically(tmp_path, monkeypatch):
    """THE PIN for the mutation an audit used to break the first cut.

    A new top-level runtime package must be swept WITHOUT anyone editing this
    file. Built in a scratch tree so the real repo is untouched.
    """
    import tests.test_runtime_imports_no_scripts as mod

    for tree in ("core", "markov"):          # one known, one brand new
        (tmp_path / tree).mkdir()
        (tmp_path / tree / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "markov" / "chain.py").write_text(
        "from scripts.util import helper\n", encoding="utf-8")

    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    assert "markov" in mod._runtime_trees(), "a new package was not discovered"
    assert "scripts" not in mod._runtime_trees(), "scripts/ must stay excluded"

    offenders = [p for p in mod._runtime_files()
                 if mod._imports_forbidden_root(p)]
    assert offenders, "the planted import in a NEW package was not caught"


def test_non_runtime_dirs_are_excluded_from_the_sweep(tmp_path, monkeypatch):
    """Control for the test above: without this, a discovery function that
    returned EVERY directory would also pass it."""
    import tests.test_runtime_imports_no_scripts as mod

    for name in ("tests", "scripts", "docs"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    assert mod._runtime_trees() == set(), (
        f"non-runtime dirs leaked into the sweep: {mod._runtime_trees()}")


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


def test_a_pep420_namespace_package_is_discovered_and_swept():
    """INJECTION, because observation cannot see this one.

    Every runtime package on this tree already carries `__init__.py`, so the
    namespace branch in `_runtime_trees` changes no verdict today and a
    passing suite is not evidence it works. This plants a real top-level
    package with NO `__init__.py` -- discovery reads the filesystem under
    REPO_ROOT, so tmp_path cannot stand in -- and walks the full chain:
    discovered as a runtime tree, included in the swept file list, and its
    forbidden import reported.

    Under the pre-2026-09-10 predicate (`(p / "__init__.py").is_file()`) the
    first assertion fails, which is what makes this test non-vacuous.
    """
    import shutil

    pkg = REPO_ROOT / "_pep420_probe_pkg"
    mod = pkg / "leaky.py"
    assert not pkg.exists(), "probe directory already present -- stale run?"
    try:
        pkg.mkdir()
        mod.write_text("from scripts.util import helper\n", encoding="utf-8")
        assert not (pkg / "__init__.py").is_file(), (
            "the probe must be a NAMESPACE package or it tests nothing")

        assert pkg.name in _runtime_trees(), (
            "a PEP 420 namespace package was not discovered as a runtime "
            "tree -- a new top-level package without __init__.py can import "
            "scripts/ with nothing to stop it")
        assert mod in set(_runtime_files()), (
            "discovered the tree but did not sweep its modules")
        hits = _imports_forbidden_root(mod)
        assert hits and all(FORBIDDEN_ROOT in h for h in hits), (
            "swept the module but did not report its forbidden import: %r"
            % (hits,))
    finally:
        shutil.rmtree(pkg, ignore_errors=True)
    assert not pkg.exists(), "probe directory survived the test"
