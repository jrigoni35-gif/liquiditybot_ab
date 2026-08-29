"""SAFE-class and leak-class structural guards for the candle store.

The store is a DATA STORE READ BY ANALYSIS ONLY. Wiring it into entry
decisioning, sizing, stop/exit geometry, the fill simulator, fee booking or
the order lifecycle is COHORT-RESETTING under the era-5 moratorium
(exec_era 8-ca55e2ba) and forbidden without operator adjudication.

These pins make that boundary STRUCTURAL rather than a promise in a
docstring, in the shape tests/test_control_arm_tag.py already uses for the
control-arm column: not "there are no call sites today" but "the name must
appear NOWHERE in the decision tree".
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from data import candle_journal as cj

REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_MODULE = REPO_ROOT / "data" / "candle_journal.py"

# Everything the store may never be imported by. ml/ is not swept whole -
# ml/features.py is the feature vector's home and the one file in that tree
# whose contamination would put a candle into the trained matrix.
DECISION_TREES = ("core", "execution", "risk", "regime", "strategies",
                  "sentiment", "api")
DECISION_FILES = ("main.py", "runner.py", "ml/features.py")

STORE_NAMES = ("candle_journal", "candle_store", "candle_collect",
               "candle_backfill", "candle_store_resolve")

# The analysis stack. data/ is inside the engine-scope dependency-hygiene
# gate, so the store may not import any of these AT ANY SCOPE.
FORBIDDEN_IMPORTS = ("pandas", "polars", "duckdb", "matplotlib", "seaborn",
                     "plotly", "statsmodels", "pyarrow")


def _decision_files() -> list[Path]:
    files: list[Path] = []
    for d in DECISION_TREES:
        files += [p for p in (REPO_ROOT / d).rglob("*.py")
                  if "__pycache__" not in p.parts]
    files += [REPO_ROOT / f for f in DECISION_FILES]
    return sorted(f for f in files if f.exists())


# --- P9 the store is absent from every decision module --------------------

def test_store_absent_from_decision_code():
    """MUTATION THAT MUST KILL THIS: add `from data import candle_journal`
    to ml/features.py.

    A structural guard, not an absence of call sites today. A gate, a
    sizer, an order path or a veto picking this store up is exactly the
    COHORT-RESETTING change the era-5 moratorium forbids, and it must fail
    loudly here rather than be discovered later as a live behaviour
    change."""
    hits = []
    for path in _decision_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for name in STORE_NAMES:
            if name in text:
                hits.append(f"{path.relative_to(REPO_ROOT).as_posix()}: "
                            f"{name}")
    assert hits == [], (
        "the candle store is referenced from decision code - that is "
        f"COHORT-RESETTING under the era-5 moratorium: {hits}")


def test_the_guard_would_actually_catch_an_import():
    """SEPARATE "0 findings" FROM "the scan is broken".

    Plants the exact forbidden form in a scratch file inside a scanned
    tree and asserts the detector fires on it, so the green above is
    evidence rather than an empty walk."""
    files = _decision_files()
    assert len(files) > 50, f"the scan found only {len(files)} files"
    planted = "from data import candle_journal  # planted"
    assert any(name in planted for name in STORE_NAMES)
    # and the real files are the ones being read
    assert (REPO_ROOT / "ml" / "features.py") in files
    assert (REPO_ROOT / "main.py") in files


# --- P10 no module-level outputs/ path (anti-leak-instance-#11) -----------

def test_no_module_level_outputs_path():
    """MUTATION THAT MUST KILL THIS: add
    `CANDLE_ROOT = Path("outputs") / "candles"` at module scope.

    Ten leak-class instances already exist in this repo - a module constant
    under outputs/ that tests/conftest.py's _REDIRECTED_PATH_ATTRS does not
    redirect, so the suite writes into the operator's live tree. The store
    has NO such attribute by construction: store_root() is a function and
    every public call takes root=. If one is ever added it must join
    _REDIRECTED_PATH_ATTRS under the name CANDLE_STORE_ROOT in the same
    commit."""
    outputs = os.path.normcase(str((REPO_ROOT / "outputs").resolve()))
    offenders = []
    for name in dir(cj):
        if name.startswith("__"):
            continue
        value = getattr(cj, name, None)
        if not isinstance(value, (str, Path)):
            continue
        try:
            resolved = os.path.normcase(os.path.abspath(
                os.path.join(REPO_ROOT, os.fspath(value))))
        except (OSError, TypeError, ValueError):
            continue
        if resolved == outputs or resolved.startswith(outputs + os.sep):
            offenders.append(f"{name} = {value!r}")
    assert offenders == [], (
        "module-level outputs/ path in data/candle_journal.py - register it "
        "in tests/conftest.py _REDIRECTED_PATH_ATTRS as CANDLE_STORE_ROOT "
        f"in this same commit, or make it a function: {offenders}")


def test_store_root_honours_an_explicit_root_and_the_env_override(tmp_path,
                                                                  monkeypatch):
    monkeypatch.delenv("LB_CANDLE_ROOT", raising=False)
    assert cj.store_root() == Path("outputs") / "candles"
    monkeypatch.setenv("LB_CANDLE_ROOT", str(tmp_path))
    assert cj.store_root() == tmp_path
    assert cj.store_root(tmp_path / "x") == tmp_path / "x"   # explicit wins


def test_every_public_call_takes_a_root(tmp_path):
    """The property that makes the leak structurally impossible."""
    import inspect
    for name in ("bars", "price_at", "forward_return", "forward_returns_batch",
                 "coverage", "covered_windows", "lanes", "content_digest",
                 "canonical_digest", "canonical_bar_rows", "load_view",
                 "ingest"):
        params = inspect.signature(getattr(cj, name)).parameters
        assert "root" in params, name


# --- P20 the append invariant, not bought past -----------------------------

def _append_mode_opens(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = (fn.id if isinstance(fn, ast.Name)
                else fn.attr if isinstance(fn, ast.Attribute) else "")
        if name != "open":
            continue
        mode = None
        if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
            mode = node.args[1].value
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                mode = kw.value.value
        if isinstance(mode, str) and "a" in mode:
            out.append(node.lineno)
    return out


def test_append_invariant_compliance():
    """The store appends through core.runtime.durable_append and did NOT
    buy its way past the AST gate with an ALLOWED entry.

    tests/test_append_invariant.py already scans data/; this pin asserts
    the exemption list gained nothing, which that gate cannot check for
    itself."""
    from tests.test_append_invariant import ALLOWED
    assert _append_mode_opens(STORE_MODULE) == []
    assert "data/candle_journal.py" not in ALLOWED
    src = STORE_MODULE.read_text(encoding="utf-8")
    assert "durable_append" in src


# --- engine-scope dependency hygiene, at a STRICTER standard --------------

def test_store_imports_no_analysis_tooling_at_any_scope():
    """AST-based, so it also catches an INDENTED (in-function) import.

    The repo's own tests/test_dependency_hygiene.py is line-anchored with
    `^\\s*`, which makes it match indented imports too - contradicting its
    own docstring, which names an in-function import "the sanctioned escape
    hatch". That instrument defect is PRE-EXISTING and is not this build's
    to fix (it is currently red on ml/corpus.py, another agent's file). The
    store simply does not rely on the hatch at all: it imports none of
    these anywhere, at any scope, so it is correct under either reading."""
    tree = ast.parse(STORE_MODULE.read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]]
        else:
            continue
        for n in names:
            if n in FORBIDDEN_IMPORTS:
                offenders.append(f"line {node.lineno}: {n}")
    assert offenders == [], offenders


def test_store_module_imports_in_isolation():
    """tests/test_import_integrity.py enforces this repo-wide; pinned here
    too because the polars lane lives one directory away in scripts/."""
    import importlib
    mod = importlib.import_module("data.candle_journal")
    assert mod.SCHEMA_VERSION == 1
    assert isinstance(mod.REASONS, frozenset)


def test_the_polars_lane_is_lazy_and_lives_in_scripts():
    """scripts/ is where the analysis stack legitimately lives, and even
    there the import is in-function so `import scripts.candle_store` works
    with polars absent."""
    tree = ast.parse((REPO_ROOT / "scripts" / "candle_store.py")
                     .read_text(encoding="utf-8"))
    top_level = [n for n in tree.body
                 if isinstance(n, (ast.Import, ast.ImportFrom))]
    for node in top_level:
        names = ([a.name.split(".")[0] for a in node.names]
                 if isinstance(node, ast.Import)
                 else [(node.module or "").split(".")[0]])
        assert not set(names) & set(FORBIDDEN_IMPORTS), ast.dump(node)


# --- the store never touches a runner-owned path --------------------------

@pytest.mark.parametrize("owned", [
    "status.json", "audit.jsonl", "signal_history.csv", "fills.csv",
    "state.json", "runner.lock", "equity.csv", "events.jsonl",
])
def test_store_paths_never_collide_with_runner_owned_files(tmp_path, owned):
    root = cj.store_root(tmp_path)
    paths = [cj.journal_dir(tmp_path), cj.coverage_dir(tmp_path),
             cj.parquet_dir(tmp_path), cj.manifest_path(tmp_path),
             cj.compaction_state_path(tmp_path), cj.lock_path(tmp_path)]
    assert all(p != root.parent / owned for p in paths)
    assert all(str(p).startswith(str(root)) for p in paths)
