"""Engine-scope dependency hygiene (2026-08-04, operator: "Repair this").

The rule existed only as prose in a session log: analysis tooling
(pandas & co.) belongs in scripts/, never in engine/runner code, because
everything the engine imports lands inside the deploy battery's
import-integrity gate on the PC - one `import pandas` at engine scope
makes a heavyweight optional-quality dependency load-bearing for every
deploy, every restart, and every `python -m compileall` on the target
machine. A rule that lives in prose is a rule the next session violates
without knowing it existed; this file is the rule as code.

Static scan, not import: importing modules to inspect them would execute
engine import side effects and be slower than reading the files. The
scan is deliberately dumb (line-anchored regex) so a false negative
requires actively hiding an import - and hiding it inside a function
body is the sanctioned escape hatch: a LAZY, optional, failure-tolerant
import in a seam (the moomoo/grpc pattern) does not create a hard
dependency and does not match here.

scripts/ and tests/ are OUT of scope on purpose: that is where pandas
belongs (it ships in the venv for offline analysis - 3.0.3 today).
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Engine scope = exactly the trees the CLAUDE.md battery gates with
# pyright/ruff at shipped-scope severity, plus the two entry files.
ENGINE_DIRS = ("core", "data", "execution", "ml", "risk", "regime",
               "strategies", "sentiment", "api")
ENGINE_FILES = ("main.py", "runner.py")

# Analysis/plotting stacks: fine in scripts/, forbidden as engine
# imports. numpy/sklearn are NOT here - they are load-bearing engine
# dependencies by design.
FORBIDDEN = ("pandas", "polars", "duckdb", "matplotlib", "seaborn",
             "plotly", "statsmodels", "pyarrow")

_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(" + "|".join(FORBIDDEN) + r")\b")


def _engine_py_files():
    for d in ENGINE_DIRS:
        yield from (ROOT / d).rglob("*.py")
    for f in ENGINE_FILES:
        yield ROOT / f


def test_engine_never_imports_analysis_tooling():
    offenders = []
    for path in _engine_py_files():
        for n, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            m = _IMPORT.match(line)
            if m:
                offenders.append(
                    f"{path.relative_to(ROOT)}:{n}: {line.strip()}")
    assert not offenders, (
        "analysis tooling imported at engine scope - move it to scripts/ "
        "or make it a lazy optional seam (moomoo/grpc pattern):\n  "
        + "\n  ".join(offenders))


def test_scripts_are_deliberately_out_of_scope():
    """Pin the boundary itself: the guard must never creep over scripts/,
    where pandas legitimately lives - a hygiene rule that blocks the
    analysis tooling from its own home would just get deleted."""
    assert "scripts" not in ENGINE_DIRS
    assert "tests" not in ENGINE_DIRS


# ---------------------------------------------------------------------
# Suite COLLECTABILITY without the optional analysis stack (2026-09-03).
#
# THE DEFECT THIS KILLS: pytest aborts the ENTIRE run when any test module
# raises at IMPORT time - "Interrupted: N errors during collection", zero
# tests executed. So one unguarded `import pandas` in one test file does
# not cost that one file, it costs the whole definition-of-done matrix on
# every machine that lacks pandas. Measured on a cloud container
# 2026-09-03: 4,541 tests collected, ZERO run, rc=2, from three modules
# added 09-01/09-02 (test_kraken_trades_backfill, test_markout_report,
# test_tape_to_candles - the latter two pulling pandas TRANSITIVELY
# through scripts/). requirements.txt pins only requests/numpy/defusedxml,
# so a venv built straight from it cannot run the suite at all.
#
# Why no static scan: two of the three offenders imported pandas through
# `from scripts import ...`, which a line-anchored regex over the TEST
# file cannot see. This pins the PROPERTY (the suite still collects)
# rather than the pattern, so any future transitive pull is caught too.
#
# The fix when this goes red is never to pin the dep in requirements.txt
# - that is what test_engine_never_imports_analysis_tooling above exists
# to prevent - but `pytest.importorskip("<dep>")` at module scope BEFORE
# the offending import, the pattern already used by
# tests/test_feed_freeze_gate.py and tests/test_moomoo_persistence.py.
# ---------------------------------------------------------------------
# Everything requirements.txt does NOT pin. numpy/requests/defusedxml are
# deliberately absent from this list: they ARE hard dependencies.
OPTIONAL_DEPS = ("pandas", "polars", "duckdb", "pyarrow", "matplotlib",
                 "seaborn", "plotly", "statsmodels", "sklearn", "scipy",
                 "torch", "ccxt", "moomoo", "numba")


@pytest.mark.timing            # spawns a full collection pass in a child
def test_suite_collects_without_optional_analysis_stack(tmp_path):
    """`pytest --collect-only` must succeed with every optional dep absent.

    Absence is SIMULATED (rather than asserted from the live venv) so the
    pin is identical on the PC, where the whole analysis stack IS
    installed and a real absence can never be observed.
    """
    blocker = tmp_path / "blocked"
    blocker.mkdir()
    for name in OPTIONAL_DEPS:
        # shadows site-packages: PYTHONPATH precedes it on sys.path
        (blocker / f"{name}.py").write_text(
            f'raise ModuleNotFoundError("No module named {name!r}")\n',
            encoding="utf-8")

    env = {**os.environ, "PYTHONPATH": str(blocker), "PYTHONUTF8": "1",
           "PYTHONIOENCODING": "utf-8"}
    env.pop("LB_OUTPUTS", None)
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--collect-only",
         "-p", "no:cacheprovider"],
        cwd=str(ROOT), capture_output=True, encoding="utf-8",
        errors="replace", timeout=900, env=env)

    if r.returncode != 0:
        blob = (r.stdout or "") + (r.stderr or "")
        offenders = sorted({
            ln.split()[1] for ln in blob.splitlines()
            if ln.startswith("ERROR ") and len(ln.split()) > 1})
        raise AssertionError(
            "the suite does not COLLECT with the optional analysis stack "
            f"absent (rc={r.returncode}) - on such a machine the whole "
            "battery runs ZERO tests, not just these files. Guard each "
            'offender with pytest.importorskip("<dep>") at module scope '
            "BEFORE the import that pulls it:\n  "
            + "\n  ".join(offenders or ["(no ERROR lines; see tail)"])
            + "\n--- tail ---\n" + "\n".join(blob.splitlines()[-15:]))
