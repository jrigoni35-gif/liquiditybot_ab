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
used: dedup by position_id, append-only merge, manifest+sha verification,
NEVER-list protection for state/status/locks.

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


def _log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} corpus_sync: {msg}"
    print(line, flush=True)
    try:
        OUT.mkdir(exist_ok=True)
        with open(OUT / "corpus_sync.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def _git(*args, cwd, timeout=120):
    try:
        p = subprocess.run(["git", *args], cwd=str(cwd),  # nosec B603 B607
                           capture_output=True, text=True, timeout=timeout)
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
                           capture_output=True, timeout=timeout)
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


def sync_once(root: Path = ROOT) -> str:
    if os.environ.get("LB_NO_CORPUS_SYNC"):
        return "disabled"
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
                cwd=str(root), capture_output=True, text=True, timeout=300)
            if p.returncode == 0:
                merged += 1
            else:
                refused += 1
                tail = (p.stdout or p.stderr or "").strip().splitlines()[-1:]
                _log(f"bundle {b.name} refused: "
                     f"{tail[0] if tail else 'unknown'}")
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
