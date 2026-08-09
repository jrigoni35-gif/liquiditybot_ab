"""tests/test_import_integrity.py — every module must import in isolation.

The bug class this kills: a module nothing else imports (optional feed,
lazy adapter) silently drifts against a refactored API and only explodes
the day someone flips its config flag. pytest can't see it (it never
imports the module), ruff can't see it (no cross-module name checking),
compileall can't see it (syntax only). Found live in data/ccxt_feed.py,
which imported sanitize_book/sanitize_candles two renames after they
became clean_book/clean_candles.

Each module is imported in its OWN interpreter so import-order coupling
can't hide behind whatever pytest happened to load first. Missing
third-party packages (ccxt, moomoo, torch...) are optional by
design and skip; a NameError/ImportError originating in OUR packages
fails the suite.
"""
import pathlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

# timing (owed 44, tagged 2026-08-09 after it went red in the battery):
# this module is the single most SELF-SATURATING test in the suite - it
# fans 8 threads out over ~100 modules, each a fresh interpreter spawn
# under a hard 120s wall timeout. Run inside the battery's -n 8 parallel
# pass that is up to 64 concurrent interpreter startups competing with
# the 8 xdist workers AND the live BelowNormal runner, and the timeout
# fires with no code defect (observed: TimeoutExpired in
# subprocess.run's communicate; the same file passes in 4.3s solo).
# It belongs in the SERIAL pass for the same reason as the
# overfit_check CLI tests - a hard wall deadline around a CPU-heavy
# child is not a property a saturated box can honor.
pytestmark = pytest.mark.timing

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_PACKAGES = ("core", "data", "execution", "ml", "risk", "api")


def _modules():
    for pkg in _PACKAGES:
        for f in sorted((_ROOT / pkg).rglob("*.py")):
            if ".venv" in f.parts or "__pycache__" in f.parts:
                continue
            yield ".".join(f.relative_to(_ROOT).with_suffix("").parts)


def _probe(mod: str):
    r = subprocess.run([sys.executable, "-c", f"import {mod}"],
                       capture_output=True, text=True, cwd=str(_ROOT),
                       timeout=120)
    if r.returncode == 0:
        return mod, "ok", ""
    err = r.stderr.strip().splitlines()
    last = err[-1] if err else ""
    if last.startswith("ModuleNotFoundError"):
        missing = last.split("'")[1].split(".")[0] if "'" in last else ""
        if missing and missing not in _PACKAGES:
            return mod, "optional", missing      # absent 3rd-party dep
    return mod, "fail", "\n".join(err[-4:])


def test_every_module_imports_in_isolation():
    mods = list(_modules())
    assert len(mods) >= 40, f"module discovery broke: found {len(mods)}"
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(_probe, mods))
    fails = [(m, d) for m, s, d in results if s == "fail"]
    detail = "\n\n".join(f"--- {m} ---\n{d}" for m, d in fails)
    assert not fails, (
        f"{len(fails)} module(s) cannot import in isolation:\n{detail}")
