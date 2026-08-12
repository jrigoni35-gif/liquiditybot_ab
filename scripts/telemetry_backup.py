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


# Windows: children of the WINDOWLESS supervisor spawn otherwise pop a new
# console window per call ("command centers"). CREATE_NO_WINDOW = silent.
# Plain int passed as creationflags= (0 is the POSIX no-op) — a **dict
# unpack typed every subprocess.run kwarg as int for the type checker.
_NOWIN = 0x08000000 if os.name == "nt" else 0


def _run(argv: list, cwd: Path | None = None, check: bool = True) -> str:
    """Run a fixed-argv command (no shell), returning stripped stdout."""
    p = subprocess.run(argv, cwd=str(cwd or ROOT), capture_output=True,  # nosec B603
                       text=True, creationflags=_NOWIN)
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


def _run_bytes(argv: list, cwd: Path) -> bytes:
    """Run a fixed-argv command returning RAW stdout bytes — the committed-
    tree verifier hashes blobs, and text-mode decoding would corrupt CRLF
    or non-UTF-8 bytes before they reach the hash."""
    p = subprocess.run(argv, cwd=str(cwd), capture_output=True,  # nosec B603
                       creationflags=_NOWIN)
    if p.returncode != 0:
        err = (p.stderr or p.stdout or b"").decode("utf-8", "replace")
        raise RuntimeError(
            f"{' '.join(argv[:3])}… exit {p.returncode}: {err.strip()[:200]}")
    return p.stdout


def committed_bundle_inconsistency(repo: Path, rev: str,
                                   label: str) -> str | None:
    """Verify the bundle AS COMMITTED at `rev` against the manifest in that
    same commit. Returns None when consistent, else a one-line reason.

    WHY this exists on top of bundle_inconsistency(): the pre-push check
    reads the bundle DIRECTORY, but what ships is what git STAGED — and
    staging can diverge from disk (2026-07-27: `git add` under
    core.checkStat=minimal kept a stale same-size/same-mtime-second
    manifest blob while staging the fresh digest; 2026-07-18: autocrlf
    rewrote sibling blobs at commit). Hashing the committed blobs is the
    only check that sees exactly what a future restore will see."""
    base = f"sessions/{label}"
    try:
        man = json.loads(_run_bytes(
            ["git", "cat-file", "blob", f"{rev}:{base}/manifest.json"],
            repo).decode("utf-8"))
    except (RuntimeError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return f"manifest unreadable in commit: {str(e)[:120]}"
    for name, meta in (man.get("files") or {}).items():
        try:
            blob = _run_bytes(
                ["git", "cat-file", "blob", f"{rev}:{base}/{name}"], repo)
        except RuntimeError:
            return f"{name}: listed in manifest but missing from commit"
        if hashlib.sha256(blob).hexdigest() != (meta or {}).get("sha256"):
            return f"{name}: committed bytes != manifest sha256"
    return None


class _NonFastForward(RuntimeError):
    """The push lost a tip race on the shared branch (another writer —
    e.g. the PC's 10-minute status pusher — advanced it mid-flow)."""


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
    # NON-FF RETRY (2026-07-26/27 pc-live outage): the PC's status pusher
    # writes to the SAME branch every 10 minutes at :x3:24 — squarely
    # between this flow's fetch and its push on the supervisor's :53
    # cadence — so the tip moved mid-flow and the non-force push was
    # rejected non-fast-forward EVERY tick. Treating that as a generic
    # failure meant waiting an hour for the phase-locked collision to
    # repeat (20+ hours of live corpus stranded on one disk). Losing the
    # race is NORMAL on a shared branch: re-fetch, rebuild the commit on
    # the fresh tip, try again — bounded, and never force (the
    # interleaved writer's commit must survive).
    last_err: Exception | None = None
    for attempt in range(3):
        if attempt:
            _run(["git", "fetch", cfg["remote"], cfg["branch"]], cwd=root)
        try:
            return _push_attempt(cfg, bundle, root, sha)
        except _NonFastForward as e:
            last_err = e
    raise RuntimeError(f"push lost the branch race 3 times: {last_err}")


def _push_attempt(cfg: dict, bundle: Path, root: Path, sha: str) -> str:
    """One worktree build+commit+push attempt against the CURRENT
    origin/<branch> tip. Raises _NonFastForward when the push loses a tip
    race, so push_bundle can re-fetch and rebuild on the moved tip."""
    remote_ref = f"{cfg['remote']}/{cfg['branch']}"
    with tempfile.TemporaryDirectory(prefix="lb_backup_wt_") as wtd:
        wt = Path(wtd) / "wt"
        # pin to the FRESH remote tip (last-writer-wins, no non-ff wedge)
        _run(["git", "worktree", "add", "--detach", "--force",
              str(wt), remote_ref], cwd=root)
        try:
            dest = wt / "sessions" / cfg["label"]
            # SHRINK GUARD: a bad boot (failed restore -> near-empty outputs)
            # or a second live session exporting less history must not
            # replace the durable tip's bundle with a smaller one — the
            # restore hook reads ONLY the tip (audit C-F4 2026-07-17).
            # Rows are append-only+dedup, so a legitimate export never
            # shrinks; LB_BACKUP_ALLOW_SHRINK=1 overrides deliberately.
            old_hist = dest / "signal_history.csv"
            if (old_hist.exists()
                    and not os.environ.get("LB_BACKUP_ALLOW_SHRINK")):
                old_rows = sum(1 for _ in open(old_hist,
                                               encoding="utf-8")) - 1
                new_rows = sum(1 for _ in open(bundle / "signal_history.csv",
                                               encoding="utf-8")) - 1
                if new_rows < old_rows:
                    return (f"refusing shrink: bundle has {new_rows} rows < "
                            f"tip's {old_rows} (LB_BACKUP_ALLOW_SHRINK=1 "
                            f"overrides)")
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(bundle, dest)
            # BYTE-EXACTNESS under core.autocrlf (the Windows-PC deploy
            # blocker, 2026-07-18): the manifest sha is computed over the
            # on-disk bundle bytes, but a pusher with autocrlf=true would
            # EOL-normalize CSV/text blobs at commit — so a puller reading
            # the blob (corpus_sync) sees different bytes and refuses the
            # bundle as "tampered", which also fails test_corpus_sync and
            # thus the whole auto-update battery on that machine. Pin the
            # durable branch to -text so git NEVER converts: the committed
            # blob equals the on-disk bytes on every machine, autocrlf or
            # not. Written before `git add` so it governs the same add.
            (wt / ".gitattributes").write_text("* -text\n", encoding="utf-8")
            # Stage ONLY this label's dir + .gitattributes — NEVER `git add
            # -A`. A blanket add re-stages every SIBLING bundle too, and on
            # a Windows pusher (autocrlf checkout -> CRLF on disk) at the
            # transition where the tip did not yet carry the `-text` pin,
            # those CRLF bytes get committed verbatim, rewriting sibling
            # blobs out of sync with their manifests and breaking the
            # integrity check for every puller (lived 2026-07-18: one
            # pc-live push corrupted hourly-latest/nightshift/dated bundles).
            # A push must be idempotent w.r.t. bundles it is not writing.
            #
            # STAT-BLIND STAGING (2026-07-27 cloud-mirror corruption): drop
            # this label's index entries before adding, so git hashes every
            # file's CONTENT instead of trusting checkout-time stat data.
            # Under core.checkStat=minimal (size + mtime-seconds only — the
            # container's global git config) a replaced file whose size
            # matches the checked-out one and whose copy2-preserved mtime
            # lands in the same wall-clock second is silently kept at its
            # stale blob: the first post-boot tick committed the previous
            # tick's manifest (size-stable at 3291 bytes) with the fresh
            # digest, and every later restore refused the bundle whole.
            _run(["git", "rm", "-r", "-q", "--cached", "--ignore-unmatch",
                  "--", f"sessions/{cfg['label']}"], cwd=wt)
            _run(["git", "add", "-A", "--", f"sessions/{cfg['label']}",
                  ".gitattributes"], cwd=wt)
            if not _run(["git", "status", "--porcelain"], cwd=wt):
                return f"no change ({cfg['label']} already current)"
            rows = sum(1 for _ in open(bundle / "signal_history.csv")) - 1
            _run(["git", "commit", "-m",
                  f"telemetry: sidecar backup @ {sha} "
                  f"({rows} rows, {cfg['label']})"], cwd=wt)
            new = _run(["git", "rev-parse", "HEAD"], cwd=wt)
            # LAST GATE before the tip changes: verify the bundle as
            # COMMITTED, not as staged-from-disk — the restore hook will
            # read these exact blobs. Raising here costs one tick; pushing
            # an inconsistent commit costs every future cold start.
            bad = committed_bundle_inconsistency(wt, new, cfg["label"])
            if bad:
                raise RuntimeError(
                    f"refusing to push inconsistent commit: {bad}")
            if cfg["dry_run"]:
                return f"DRY-RUN committed {rows} rows (not pushed)"
            try:
                _run(["git", "push", cfg["remote"],
                      f"{new}:refs/heads/{cfg['branch']}"], cwd=root)
            except RuntimeError as e:
                msg = str(e)
                if ("non-fast-forward" in msg or "[rejected]" in msg
                        or "fetch first" in msg):
                    raise _NonFastForward(msg) from e
                raise
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


def main(argv: list | None = None) -> int:
    """Loop mode (default, the cloud sidecar) or --once (the PC: its
    supervisor owns the cadence via a stamp, so each spawn is one
    export+push and exit). --label overrides LB_BACKUP_LABEL so the PC's
    live corpus lands under its own bundle name instead of shadowing the
    cloud mirror's."""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--label", default=None)
    args = ap.parse_args(argv)
    cfg = _cfg()
    if args.label:
        cfg["label"] = args.label
    if args.once:
        try:
            _log(backup_once(cfg))
            return 0
        except Exception as e:      # fail-safe: one line, next stamp retries
            _log(f"backup failed (next cadence retries): {e}")
            return 1
    _log(f"start: every {cfg['period']:.0f}s -> {cfg['branch']} "
         f"/sessions/{cfg['label']}{' (DRY-RUN)' if cfg['dry_run'] else ''}")
    while True:
        try:
            _log(backup_once(cfg))
        except Exception as e:  # fail-safe: never wedge, never crash the box
            _log(f"backup failed (will retry): {e}")
        time.sleep(cfg["period"])


if __name__ == "__main__":
    raise SystemExit(main())
