"""The torn-append invariant, enforced by a GATE rather than by adoption.

WHY THIS FILE EXISTS. Torn-append fusion has now been found four separate
times - core/fill_ledger.py and ml/registry.py (2026-08-05), then eight
more writers in the 2026-08-06 sweep, then a THIRD independent appender to
the training corpus in scripts/session_import.py that the sweep itself
missed. Each round was fixed by inspection, and each round the class came
back somewhere new, because nothing stopped the next writer from typing
`open(path, "a")`.

core/runtime.durable_append fixed the instances. It could not fix the
CLASS: an invariant enforced by everyone-remembering is not enforced. This
test is the gate. A new append-mode open in shipped code fails here and
the author has to either use the primitive or add an entry below with a
reason - a reviewed decision instead of a silent regression.

Same AST-based approach as tests/test_code_registry.py, and for the same
reason: a text regex false-positives on prose. Only real `open(...)` calls
with a literal append mode count.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Shipped scope. tests/ is deliberately excluded: a test that FABRICATES a
# torn tail must be able to open a scratch file in append mode.
SCANNED_DIRS = ("core", "data", "execution", "ml", "risk", "regime",
                "strategies", "sentiment", "api", "scripts")
SCANNED_FILES = ("main.py", "runner.py")

# (relative path, reason). Every entry is a file that appends WITHOUT
# core.runtime.durable_append, and is allowed to.
ALLOWED = {
    # --- the primitive itself, and the two heals that predate it ---------
    "core/runtime.py":
        "durable_append IS the primitive (and JsonlEventHandler.emit "
        "below); nothing to delegate to.",
    "core/fill_ledger.py":
        "the reference implementation - its own probe/heal/fsync at :70-86 "
        "is what durable_append was generalized FROM.",
    "ml/registry.py":
        "carries the JSONL variant of the same heal at :146-160, coupled to "
        "the hash chain's torn-tail semantics.",
    "core/audit.py":
        "_adopt_tail does more than heal - it truncates malformed lines and "
        "re-adopts seq/prev. Replacing the whole write would take the chain "
        "logic with it; only the newline probe is shared, and it is already "
        "correct as of the 2026-08-06 _synced re-arm.",
    # --- plain text logs: fusion costs two log lines, nothing durable ----
    "scripts/corpus_sync.py":
        "the :57 site is the human-readable corpus_sync.log. The DATA "
        "append (the recovery merge) does use durable_append.",
    "scripts/auto_update.py": "auto_update.log, human-readable text log.",
    "scripts/pc_supervisor.py": "pc_supervisor.log, human-readable text log.",
    "scripts/remote_control.py": "remote_control.log, human-readable text log.",
    "scripts/checkin.py": "check-in report text, regenerated on demand.",
    "scripts/run_checkin_quiet.py": "check-in wrapper's text log.",
    "scripts/assurance_check.py": "assurance report text, regenerated per run.",
    # --- operator-invoked, one-shot, supervised --------------------------
    "scripts/migrate_history.py":
        "operator-invoked one-shot migration, never automatic; its output "
        "is verified by the operator before it becomes the corpus.",
    "data/replay.py":
        "session recorder - a fused frame costs one replay frame out of "
        "~6.3 GB, and the recorder must not fsync on the hot REST path.",
}


def _append_opens(path: Path) -> list:
    """Every `open(..., <mode containing 'a'>)` call, as line numbers.
    Literal modes only - a computed mode cannot be judged statically and
    has never appeared in this repo."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
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


def _shipped_files() -> list:
    files = [p for d in SCANNED_DIRS
             for p in (ROOT / d).rglob("*.py")
             if "__pycache__" not in str(p)]
    files += [ROOT / f for f in SCANNED_FILES]
    return sorted(f for f in files if f.exists())


def test_no_unreviewed_append_mode_open_in_shipped_code():
    """The gate. A new bare append re-opens a defect class found four
    times - use core.runtime.durable_append, or justify an exemption."""
    offenders = {}
    for f in _shipped_files():
        rel = f.relative_to(ROOT).as_posix()
        if rel in ALLOWED:
            continue
        lines = _append_opens(f)
        if lines:
            offenders[rel] = lines
    assert not offenders, (
        "append-mode open() in shipped code without durable_append:\n  "
        + "\n  ".join(f"{k}: line(s) {v}" for k, v in offenders.items())
        + "\n\nUse core.runtime.durable_append (it heals a torn tail, "
          "writes the header on a ZERO-LENGTH file, and fsyncs), or add "
          "the file to ALLOWED in this test with a reason.")


def test_allowlist_has_no_stale_entries():
    """An exemption that no longer appends is an exemption that will
    silently cover a FUTURE append. Keep the list honest."""
    stale = [rel for rel in ALLOWED
             if (ROOT / rel).exists() and not _append_opens(ROOT / rel)]
    assert not stale, (
        f"these files no longer append and should leave ALLOWED: {stale}")


def test_every_allowlist_entry_exists():
    missing = [rel for rel in ALLOWED if not (ROOT / rel).exists()]
    assert not missing, f"ALLOWED names files that do not exist: {missing}"


@pytest.mark.parametrize("rel", [
    "ml/history.py",          # the 89-column training corpus
    "scripts/session_import.py",   # 3rd corpus writer, hourly + unattended
    "ml/postmortem.py",
    "ml/retrain_log.py",
    "data/context_engine.py",
])
def test_the_data_writers_actually_use_the_primitive(rel):
    """Not just "no bare append" - these must positively call it, so
    deleting the call is caught as well as replacing it."""
    src = (ROOT / rel).read_text(encoding="utf-8")
    assert "durable_append" in src, \
        f"{rel} must append through core.runtime.durable_append"
