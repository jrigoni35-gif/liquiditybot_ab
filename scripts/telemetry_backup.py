"""
scripts/telemetry_backup.py — periodic durable backup of learning data.

WHY: cloud containers are ephemeral and a hard restart can roll outputs/
back to an older filesystem snapshot. The session-start hook RESTORES the
newest bundle from the `paper-telemetry` orphan branch — but that only
recovers rows as fresh as the last PUSH. Historically the hourly push was
driven by an external scheduled trigger; a trigger firing INTO a session
stalls exactly when the session dies (the restart case), so recent rows
were silently lost. This sidecar makes the push part of the bot's own
lifecycle: the same hook that relaunches the runner relaunches this, so
"the bot is up" and "its learning is being checkpointed" are the same
fact.

WHAT it does every PERIOD: bundle the portable learning artifacts with
scripts/session_export.py, then commit that bundle to
`sessions/<label>/` on the `paper-telemetry` branch and push.

SAFETY:
  * WORKING-TREE-SAFE. All git work happens in an isolated, throwaway
    worktree under a temp dir; the runner's checkout, index, and current
    branch are never touched.
  * FAIL-SAFE. Any error (export, git, network) logs one line and retries
    next tick. The bot never imports this and never depends on it.
  * LAST-WRITER-WINS on the bundle. Each tick resets the worktree to the
    freshest remote tip before writing, so a concurrent home push is never
    clobbered (its bundle lives under a different label) and we never wedge
    on a non-fast-forward.
  * NO SECRETS travel: session_export's allow-list already excludes
    state/status/locks/tokens; this only moves that bundle.

ENV (all optional):
  LB_BACKUP_PERIOD_SEC  push interval seconds (default 1800 = 30 min)
  LB_BACKUP_LABEL       bundle label / subdir (default "hourly-latest")
  LB_BACKUP_BRANCH      durable branch (default "paper-telemetry")
  LB_OUTPUTS            outputs dir to export (default "outputs")
  LB_BACKUP_REMOTE      git remote (default "origin")
  LB_BACKUP_DRYRUN      set to "1" to export + commit but NOT push
"""
import hashlib
import json
import os
import shutil
import subprocess  # nosec B404 - git/venv calls with fixed argv, no shell
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} telemetry_backup: {msg}", flush=True)


def _run(argv: list, cwd: Path | None = None, check: bool = True) -> str:
    """Run a fixed-argv command (no shell), returning stripped stdout."""
    p = subprocess.run(argv, cwd=str(cwd or ROOT), capture_output=True,  # nosec B603
                       text=True)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"{' '.join(argv[:3])}… exit {p.returncode}: "
            f"{(p.stderr or p.stdout).strip()[:200]}")
    return (p.stdout or "").strip()


def _cfg() -> dict:
    return {
        "period": float(os.environ.get("LB_BACKUP_PERIOD_SEC", "1800")),
        "label": os.environ.get("LB_BACKUP_LABEL", "hourly-latest"),
        "branch": os.environ.get("LB_BACKUP_BRANCH", "paper-telemetry"),
        "outputs": os.environ.get("LB_OUTPUTS", "outputs"),
        "remote": os.environ.get("LB_BACKUP_REMOTE", "origin"),
        "dry_run": os.environ.get("LB_BACKUP_DRYRUN", "") == "1",
    }


def bundle_inconsistency(bundle: Path) -> str | None:
    """Verify every file the bundle's manifest describes matches its recorded
    sha256. Returns None when consistent, else a one-line reason.

    WHY: an internally inconsistent bundle (manifest hash != shipped bytes —
    seen live 2026-07-17 when two container boots' pushes interleaved) is
    REFUSED WHOLE by the restore hook's session_import, so pushing one
    replaces the durable tip with a bundle no future cold start can use.
    Refusing here costs one tick (the next backup retries with a fresh
    export); pushing it costs the restore. A manifest without a `files` map
    (foreign/minimal bundles) has nothing to verify and passes."""
    try:
        man = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return f"manifest unreadable: {e}"
    for name, meta in (man.get("files") or {}).items():
        p = bundle / name
        if not p.exists():
            return f"{name}: listed in manifest but missing"
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        if h.hexdigest() != meta.get("sha256"):
            return f"{name}: sha256 mismatch vs manifest"
    return None


def push_bundle(cfg: dict, bundle: Path, root: Path = ROOT) -> str:
    """Commit `bundle` to sessions/<label>/ on the durable branch and push,
    in an isolated worktree so `root`'s checkout/index/branch are untouched.
    Split out from backup_once so the git path is testable without a live
    export or network (point `remote` at a local bare repo)."""
    if not (bundle / "signal_history.csv").exists():
        raise RuntimeError("bundle has no signal_history.csv")
    reason = bundle_inconsistency(bundle)
    if reason:
        raise RuntimeError(f"refusing inconsistent bundle: {reason}")
    sha = _run(["git", "rev-parse", "--short", "HEAD"], cwd=root)
    # bootstrap the durable branch on a fresh remote: without this the very
    # first backup would fetch a non-existent branch and raise forever. Seed
    # an empty orphan root (git's canonical empty-tree SHA) so the worktree
    # flow below has a ref; subsequent backups just fetch it.
    if not _run(["git", "ls-remote", "--heads", cfg["remote"], cfg["branch"]],
                cwd=root, check=False):
        empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        root_commit = _run(["git", "commit-tree", empty_tree, "-m",
                            f"telemetry: bootstrap {cfg['branch']}"], cwd=root)
        _run(["git", "push", cfg["remote"],
              f"{root_commit}:refs/heads/{cfg['branch']}"], cwd=root)
    _run(["git", "fetch", cfg["remote"], cfg["branch"]], cwd=root)
    remote_ref = f"{cfg['remote']}/{cfg['branch']}"
    with tempfile.TemporaryDirectory(prefix="lb_backup_wt_") as wtd:
        wt = Path(wtd) / "wt"
        # pin to the FRESH remote tip (last-writer-wins, no non-ff wedge)
        _run(["git", "worktree", "add", "--detach", "--force",
              str(wt), remote_ref], cwd=root)
        try:
            dest = wt / "sessions" / cfg["label"]
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(bundle, dest)
            _run(["git", "add", "-A"], cwd=wt)
            if not _run(["git", "status", "--porcelain"], cwd=wt):
                return f"no change ({cfg['label']} already current)"
            rows = sum(1 for _ in open(bundle / "signal_history.csv")) - 1
            _run(["git", "commit", "-m",
                  f"telemetry: sidecar backup @ {sha} "
                  f"({rows} rows, {cfg['label']})"], cwd=wt)
            if cfg["dry_run"]:
                return f"DRY-RUN committed {rows} rows (not pushed)"
            new = _run(["git", "rev-parse", "HEAD"], cwd=wt)
            _run(["git", "push", cfg["remote"],
                  f"{new}:refs/heads/{cfg['branch']}"], cwd=root)
            return f"pushed {rows} rows -> {cfg['branch']}"
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt)],
                 cwd=root, check=False)
            _run(["git", "worktree", "prune"], cwd=root, check=False)


def backup_once(cfg: dict) -> str:
    """One export+commit+push cycle. Returns a short status string.
    Raises on failure so the caller can log and retry."""
    py = sys.executable
    with tempfile.TemporaryDirectory(prefix="lb_backup_") as td:
        bundle = Path(td) / "bundle"
        # export the portable learning bundle (dedup-safe, allow-listed)
        _run([py, "scripts/session_export.py", "--dest", str(bundle),
              "--label", cfg["label"], "--outputs", cfg["outputs"],
              "--refresh-digest"])
        return push_bundle(cfg, bundle)


def main() -> None:
    cfg = _cfg()
    _log(f"start: every {cfg['period']:.0f}s -> {cfg['branch']} "
         f"/sessions/{cfg['label']}{' (DRY-RUN)' if cfg['dry_run'] else ''}")
    while True:
        try:
            _log(backup_once(cfg))
        except Exception as e:  # fail-safe: never wedge, never crash the box
            _log(f"backup failed (will retry): {e}")
        time.sleep(cfg["period"])


if __name__ == "__main__":
    main()
