"""
scripts/corpus_sync.py — one-bot corpus sync: pull the durable branch's
learning bundles into local outputs/, so every machine trains on the SAME
foundation.

WHY: the cloud session-start hook restores bundles at boot, but the PC had
no import path at all (its checkin only EXPORTS) — so the two corpora
drifted: the PC lacked the cloud's live-trade labels, the cloud lacked the
PC's fresh candidate rows until a 4h checkin. This closes the loop from the
supervisor's cadence, Windows-safe (pure git, no tar, no bash).

WHAT: fetch the branch, materialize every sessions/<label>/ bundle at the
tip into a temp dir, and run scripts/session_import.py --apply on each,
newest bundle first (same ordering rule as the cloud hook: the freshest
meta_model must win copy-if-absent). session_import is the ONLY writer
used: dedup by position_id, append-only merge, manifest SELF-CONSISTENCY
checks, NEVER-list protection for state/status/locks.

The manifest checks are NOT a trust boundary and this line used to read as
though they were ("manifest+sha verification"). session_import.py says it
exactly: "Manifests are ATTACKER-AUTHORED... the per-file sha256 are
self-consistency checks on the bundle's own bytes, not a trust boundary."
A bundle's sha256 establishes that its bytes are the bytes that were
bundled - by whoever bundled them. It establishes nothing about whether
the contents are true, because the same party wrote both. What actually
guards this path is the strict bare-basename allow-list on every manifest
string that becomes a path, plus the NEVER-list - controls that do not
consult the bundle's own claims about itself.

SAFE BESIDE A LIVE RUNNER: the importer appends whole lines to
signal_history.csv; the training loader's width guard skips a torn seam
line and dedup re-heals it next sync. A schema mismatch (mid-update
window) makes the import refuse that bundle — logged, retried next
cadence, never forced.

ENV: LB_BACKUP_REMOTE / LB_BACKUP_BRANCH (shared transport defaults),
LB_NO_CORPUS_SYNC=1 disables.
"""
import json
import os
import subprocess  # nosec B404 - fixed argv, no shell
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"


def _log(msg: str, root: Path = ROOT) -> None:
    """Append one line to <root>/outputs/corpus_sync.log.

    `root` is NOT decoration: every other entry point here already takes it
    so a caller can operate on a throwaway tree, but this function used the
    module-level OUT unconditionally - so the suite's deliberately corrupted
    fixtures were appended to the REAL log ("INTEGRITY FAIL: ... bundle
    tampered or corrupt", "recovered 3 stranded row(s)", once per battery
    run since 2026-07-18). That log is operator forensics; a fabricated
    incident in it is worse than no log at all, and one such line sent a
    live investigation after a bundle that never existed. Production keeps
    byte-identical behavior via the default."""
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} corpus_sync: {msg}"
    print(line, flush=True)
    try:
        out = root / "outputs"
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "corpus_sync.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


# Windows: children of the WINDOWLESS supervisor spawn otherwise pop a new
# console window per call ("command centers"). CREATE_NO_WINDOW = silent.
# Plain int passed as creationflags= (0 is the POSIX no-op) — a **dict
# unpack typed every subprocess.run kwarg as int for the type checker.
_NOWIN = 0x08000000 if os.name == "nt" else 0

# DL-2 (measured 2026-08-13): a git call needing credentials pops an
# interactive Git-Credential-Manager dialog that nobody can answer in a
# headless sidecar, and timeout= cannot rescue it — the credential helper is a
# GRANDCHILD holding the inherited capture_output pipe, so communicate()
# blocks for an EOF that never arrives. Make git FAIL instead of ASK. Env-only
# injection; argv is left untouched. Full rationale: scripts/remote_control.py.
_NOPROMPT = {
    "GIT_TERMINAL_PROMPT": "0",     # core git: never prompt on a terminal
    "GIT_ASKPASS": "",              # disable GUI askpass; terminal path is
    "SSH_ASKPASS": "",              # then refused by GIT_TERMINAL_PROMPT=0
    "GCM_INTERACTIVE": "never",     # Git-Credential-Manager: never show UI
    # env-injected config (git >= 2.31) == `-c credential.interactive=false`
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "credential.interactive",
    "GIT_CONFIG_VALUE_0": "false",
}


def _git_env() -> dict:
    """os.environ plus the never-prompt overrides (read fresh per call)."""
    return {**os.environ, **_NOPROMPT}


def _git(*args, cwd, timeout=120):
    try:
        p = subprocess.run(["git", *args], cwd=str(cwd),  # nosec B603 B607
                           capture_output=True, text=True, timeout=timeout,
                           creationflags=_NOWIN, env=_git_env())
        return p.returncode, (p.stdout or "").strip()
    except Exception as e:                       # noqa: BLE001
        return 1, f"error: {e}"


def _git_bytes(*args, cwd, timeout=60):
    """Raw-bytes git (for `show`): session_import sha-verifies every bundle
    file, so extraction must be BYTE-EXACT — text mode + newline guessing
    altered files with no trailing newline (session_digest.json) by one
    byte and every real bundle was refused (self-audit 2026-07-18)."""
    try:
        p = subprocess.run(["git", *args], cwd=str(cwd),  # nosec B603 B607
                           capture_output=True, timeout=timeout,
                           creationflags=_NOWIN, env=_git_env())
        return p.returncode, p.stdout or b""
    except Exception:                            # noqa: BLE001
        return 1, b""


def _cfg() -> dict:
    return {"remote": os.environ.get("LB_BACKUP_REMOTE", "origin"),
            "branch": os.environ.get("LB_BACKUP_BRANCH", "paper-telemetry")}


def _bundle_order_key(bundle_dir: Path) -> str:
    try:
        man = json.loads((bundle_dir / "manifest.json")
                         .read_text(encoding="utf-8"))
        return str(man.get("created_at_utc", ""))
    except (OSError, json.JSONDecodeError):
        return ""


def recover_local_baks(root: Path = ROOT) -> str:
    """Re-import rows stranded in outputs/signal_history.bak_* rotations.

    A schema bump rotates the live CSV to .bak_<ts>; the durable branch only
    holds rows up to the LAST hourly backup, so labels banked between that
    backup and the rotation exist ONLY in the local .bak (observed live
    2026-07-19: live labels #46/#47 + ~19 candidates stranded when the
    barrier-column bump landed). Ground truth must never be stranded: run
    each .bak through the same migrate machinery bundles use, append rows
    whose position_id is absent (dedup = idempotent), then rename the .bak
    to .recovered_<name> so this runs once per rotation. The file is
    renamed, never deleted — nothing is ever lost."""
    out_dir = root / "outputs"
    dest = out_dir / "signal_history.csv"
    baks = sorted(out_dir.glob("signal_history.bak_*"))
    baks = [b for b in baks if not b.name.endswith(".recovered")]
    if not baks:
        return "no_baks"
    sys.path.insert(0, str(ROOT))
    from core.runtime import durable_append
    from ml.history import HistoryStore
    from scripts.migrate_history import migrate_rows
    import csv as _csv
    total = 0
    for bak in baks:
        try:
            rows, _padded = migrate_rows(str(bak))
        except SystemExit as e:
            # newer/unmappable schema: leave the .bak for a manual look
            _log(f"bak {bak.name} not auto-migratable ({e}) - left in place",
                 root=root)
            continue
        except (OSError, ValueError, KeyError) as e:
            _log(f"bak {bak.name} unreadable ({e}) - left in place", root=root)
            continue
        HistoryStore(str(dest))._ensure_schema()
        existing = set()
        if dest.exists():
            with open(dest, newline="", encoding="utf-8") as f:
                existing = {r.get("position_id")
                            for r in _csv.DictReader(f)}
        written = 0
        fresh = [row for row in rows if row[0] not in existing]
        if fresh:
            # SECOND writer to the training corpus (the runner's
            # HistoryStore._append_row is the first). Two independent
            # appenders with no torn-tail heal is exactly the seam that
            # produced SD-007 on the audit chain: whichever process is
            # killed mid-row, the other one welds onto the fragment and
            # BOTH labelled outcomes are lost. One probe per OPEN here,
            # not per row - the whole recovery batch is a single append.
            def _emit(f, batch=fresh):
                w = _csv.writer(f)
                for row in batch:
                    w.writerow(row)
            if durable_append(dest, _emit):
                written = len(fresh)
        total += written
        try:
            bak.rename(bak.with_name(bak.name + ".recovered"))
        except OSError:
            pass                       # next pass dedups to zero anyway
        _log(f"bak {bak.name}: recovered {written} stranded row(s)",
             root=root)
    return f"bak_recovered={total}"


def sync_once(root: Path = ROOT) -> str:
    if os.environ.get("LB_NO_CORPUS_SYNC"):
        return "disabled"
    # local rotations FIRST: their rows may be newer than the durable tip,
    # and the export sidecar can then durably back them up this same hour
    bak_note = recover_local_baks(root)
    if bak_note not in ("no_baks", "bak_recovered=0"):
        _log(f"local rotation recovery: {bak_note}", root=root)
    cfg = _cfg()
    rc, err = _git("fetch", cfg["remote"], cfg["branch"], cwd=root)
    if rc != 0:
        return f"fetch_failed: {err[:120]}"
    ref = f"{cfg['remote']}/{cfg['branch']}"
    rc, listing = _git("ls-tree", "-r", "--name-only", ref, "--", "sessions",
                       cwd=root)
    if rc != 0 or not listing.strip():
        return "no_bundles"
    with tempfile.TemporaryDirectory(prefix="lb_corpus_") as td:
        base = Path(td)
        for rel in listing.splitlines():
            rc, raw = _git_bytes("show", f"{ref}:{rel}", cwd=root)
            if rc != 0:
                continue
            dest = base / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
        bundles = sorted((p for p in (base / "sessions").iterdir()
                          if p.is_dir()),
                         key=_bundle_order_key, reverse=True)
        merged = refused = 0
        for b in bundles:
            if not (b / "signal_history.csv").exists():
                continue
            # the importer comes from THIS code checkout (ROOT); cwd=root so
            # its relative outputs/ writes land at the target root (they are
            # the same directory on the PC, distinct in tests)
            p = subprocess.run(                          # nosec B603
                [sys.executable, str(ROOT / "scripts" / "session_import.py"),
                 "--src", str(b), "--apply"],
                cwd=str(root), capture_output=True, text=True, timeout=300,
                creationflags=_NOWIN)
            if p.returncode == 0:
                merged += 1
            else:
                refused += 1
                tail = (p.stdout or p.stderr or "").strip().splitlines()[-1:]
                _log(f"bundle {b.name} refused: "
                     f"{tail[0] if tail else 'unknown'}", root=root)
        return f"bundles={len(bundles)} merged={merged} refused={refused}"


def main() -> int:
    try:
        out = sync_once()
        _log(out)
        return 0
    except Exception as e:  # noqa: BLE001 - fail-safe sidecar surface
        _log(f"error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
