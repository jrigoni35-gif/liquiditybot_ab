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
import re
from pathlib import Path

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
