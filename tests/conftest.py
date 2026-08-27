"""Shared pytest plumbing.

Tests construct engines (firewall, order manager, ML governor) whose
internals write the process-wide audit singleton. Redirect it to a
session tmp file so synthetic QA records never enter the production
outputs/audit.jsonl trail - live audit pollution both buries real
dispositions and breaks the running bot's hash chain (SD-007).

The same hazard is NOT limited to the audit singleton. Any test that
drives a code path whose output path is a module constant, or a bare
relative default resolved against the repo root, writes into the
OPERATOR'S live outputs/ tree. Measured 2026-07-31 by snapshotting
outputs/ around a full suite run: six files were being mutated by the
suite, including two that are data rather than logs -
retrain_history.jsonl (305 of its 306 records were test fixtures; a
prior session saw the resulting degeneracy and built a workaround
instead of recognising the contamination) and session_digest.json.
outputs/corpus_sync.log had carried a fabricated "INTEGRITY FAIL:
signal_history.csv sha256 mismatch (bundle tampered or corrupt)" on
every battery run since 2026-07-18, and reading that log as forensics
sent a live investigation chasing a bundle that never existed.

_no_production_outputs_writes below closes the class structurally: an
audit hook watches every write-mode open/rename and fails the OFFENDING
test by name, so the next occurrence is caught at authoring time instead
of months later in an operator's log.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

_ROOT = Path(__file__).resolve().parents[1]
# normcase: Windows is the target runtime and its paths reach us in mixed
# case (C:\Users\... vs c:\users\...). A case-SENSITIVE prefix test would
# silently miss a real violation there - a guard that under-reports on the
# platform the bot actually runs on is worse than no guard, because it
# reads as proof of cleanliness. No-op on POSIX.
_OUTPUTS = os.path.normcase(str(_ROOT / "outputs") + os.sep)

# Paths under outputs/ the suite is ALLOWED to touch. Empty on purpose:
# every current write is a defect, and an allowlist entry must be argued
# in review, not added to silence a failure.
_ALLOWED: tuple[str, ...] = ()

# Populated by the audit hook, drained per test by the fixture below.
_violations: list[str] = []
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC


def _flag(path: object) -> None:
    try:
        p = os.path.normcase(os.path.abspath(
            os.fspath(path)))                 # type: ignore[arg-type]
    except (TypeError, ValueError):
        return
    if p.startswith(_OUTPUTS) and not p.startswith(_ALLOWED or ("\0",)):
        _violations.append(p)


def _audit(event: str, args: tuple) -> None:
    # Hot path: this runs on EVERY open in the process, so bail on the
    # event name before doing anything else.
    if event == "open":
        path, mode, flags = args
        if (mode is None and flags & _WRITE_FLAGS) or (
                mode is not None and any(c in mode for c in "wax+")):
            _flag(path)
    elif event in ("os.rename", "os.replace", "os.remove", "os.unlink"):
        for a in args:
            _flag(a)


sys.addaudithook(_audit)


@pytest.fixture(scope="session", autouse=True)
def _isolated_audit_trail(tmp_path_factory):
    from core.audit import configure_audit
    from ml.registry import configure_registry
    configure_audit(tmp_path_factory.mktemp("audit") / "audit.jsonl")
    configure_registry(tmp_path_factory.mktemp("models"))


# Module attributes naming a production path under outputs/. A module that
# exposes one of these gets it redirected to tmp for every test, so a code
# path whose destination is a module default cannot write to the operator's
# tree just because a test's minimal config omitted the key.
_REDIRECTED_PATH_ATTRS = (
    "LOG_PATH", "RETRAIN_FLAG_PATH_DEFAULT", "RETRAIN_HISTORY_PATH_DEFAULT",
    # pc_supervisor cadence stamps. Found 2026-08-01 by running the battery
    # in a FRESH worktree: these are written only when absent, so a working
    # tree with a populated outputs/ never fires them and both the hard
    # battery and the sha256 snapshot sweep were blind to the leak. The
    # throwaway worktree is the honest environment for this class.
    "_UPDATE_STAMP", "_REMOTE_CMD_STAMP", "_STATUS_PUSH_STAMP",
    "_TELEM_BACKUP_STAMP", "_CORPUS_SYNC_STAMP", "_CORPUS_ROTATION_MARKER",
    "_PROMPT_SWEEP_STAMP", "_TASK_MIGRATE_STAMP", "_OPEND_STAMP",
    "_DASH_IMPORT_STAMP",
    # 10th leak-class instance (2026-08-27, fix-wave 2): pc_supervisor's
    # vault-guard cadence stamp shipped alongside its 2026-08-23 spawn
    # wiring without joining this list, unlike every sibling cadence stamp
    # above. A fresh worktree has no outputs/.vault_guard_stamp on disk, so
    # sup.tick()'s _stamp_due(_VAULT_GUARD_STAMP, ...) call (the read side,
    # not the vault_guard.py spawn itself, which _tick_env already mocks)
    # touches the real repo tree the instant a test drives tick() -
    # tests/test_corpus_rotation_marker.py::
    # test_tick_spawns_corpus_sync_immediately_on_marker caught it.
    "_VAULT_GUARD_STAMP",
    # SHADOW_WEIGHTS_PATH (scripts/shadow_gate_weights.py, sandbox
    # prototype, 2026-08-27): the sidecar's own output path constant -
    # registered on introduction per this file's own rule above, not
    # discovered later as an unregistered-stamp defect.
    "SHADOW_WEIGHTS_PATH",
)

# Modules that must be PRESENT in sys.modules for the scan below to find
# their constant. A module imported lazily inside the function under test
# (train_meta does `from ml import retrain_log` at call time) is absent
# when the fixture runs, so the scan would silently redirect nothing and
# the write would land in the real tree. Import-only, no side effects -
# deliberately excludes the scripts.* sidecars, which do real work
# (directory creation) at import.
_REDIRECT_OWNERS = ("ml.retrain_log", "ml.monitor")


@pytest.fixture(autouse=True)
def _sidecar_logs_to_tmp(tmp_path, monkeypatch):
    """Point every loaded module's production LOG_PATH at this test's tmp
    dir, so a test that drives a sidecar in-process cannot append to the
    operator's real log.

    Matched by VALUE, not by module name: the suite imports these both as
    `pc_supervisor` and as `scripts.pc_supervisor`, which are two distinct
    module objects, and a name list silently missed one of them. Any
    module that grows a LOG_PATH under outputs/ is covered from the moment
    it exists - no registration step to forget."""
    import importlib
    for name in _REDIRECT_OWNERS:
        try:
            importlib.import_module(name)
        except ImportError:
            pass
    for mod in list(sys.modules.values()):
        for attr in _REDIRECTED_PATH_ATTRS:
            try:
                current = getattr(mod, attr, None)
            except Exception:        # noqa: BLE001 - PEP 562 __getattr__
                continue
            if current is None or isinstance(current, bool):
                continue
            resolved = Path(os.path.abspath(
                os.path.join(_ROOT, os.fspath(current))))
            if os.path.normcase(str(resolved)).startswith(_OUTPUTS):
                repl = tmp_path / resolved.name
                monkeypatch.setattr(
                    mod, attr,
                    str(repl) if isinstance(current, str) else repl)


@pytest.fixture(autouse=True)
def _no_production_outputs_writes(request):
    """Fail the test that writes into the repo's real outputs/ tree.

    Tests get tmp_path; the production tree belongs to the running bot and
    to the operator reading it as forensics. A synthetic row in
    retrain_history.jsonl or a fabricated INTEGRITY FAIL in a sidecar log
    is indistinguishable from the real thing after the fact.

    Fix by passing the throwaway root the code already accepts (most
    sidecars take `root=`), or by pointing the config key at tmp_path -
    not by widening _ALLOWED.

    LB_ALLOW_OUTPUT_WRITES=1 downgrades this to a warning for a one-off
    local investigation; it is never set in the battery.
    """
    del _violations[:]
    yield
    if not _violations:
        return
    hit = sorted(set(_violations))
    del _violations[:]
    msg = (f"{request.node.nodeid} wrote into the production outputs/ "
           f"tree: {', '.join(os.path.relpath(h, _ROOT) for h in hit)}")
    if os.environ.get("LB_ALLOW_OUTPUT_WRITES"):
        import warnings
        warnings.warn(msg, stacklevel=1)
    else:
        pytest.fail(msg)
