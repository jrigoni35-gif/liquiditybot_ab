"""
scripts/remote_control.py — one-bot control plane over git (no open ports).

The operator talks to Claude from anywhere (phone / web / desktop); Claude
commits command files to the durable telemetry branch; the always-on PC
polls that branch, validates each command, and forwards it to the runner's
local ControlChannel — the same queue a console operator uses. The runner
consumes and acks exactly as it does for local commands. In the other
direction the PC publishes its full outputs/status.json to the branch so
the remote console sees the live bot, not just Grafana's metric subset.

SECURITY MODEL
  * Transport is the operator's own private repo: command authority ==
    repo write access == the trust level that already ships code the
    test-gated auto-updater executes. No listening sockets, no new
    inbound surface on the PC.
  * HARD INVARIANT (CLAUDE.md #1): REMOTE_SAFE_COMMANDS can NEVER carry
    arm_live. The only road to live stays config `dry_run:false` +
    restart + typed ARM LIVE at the PC console. force_dry — the safe
    direction — IS remotely allowed, as are pause/flatten/etc. (exits
    and de-risking must never be blocked; new risk must never be
    remotely armable).
  * Commands EXPIRE: older than MAX_AGE_SEC, or stamped in the future,
    are rejected — replaying a stale queue cannot move the bot.
  * EXACTLY-ONCE: consumed ids persist in outputs/remote_consumed.json;
    a command id is forwarded at most once, ever. Consumed queue files
    are deleted from the branch on the next status push (self-cleaning).
  * FAIL-SAFE: every entry point catches its own errors and returns a
    disposition string; the supervisor never wedges on this module.
  * Dispositions log registry codes (RC-010 applied / RC-011 rejected)
    to outputs/remote_control.log and the pc_status envelope — NOT to
    audit.jsonl, whose hash chain has exactly one writer (the runner;
    the runner's own ack covers execution there).

ENV (all optional):
  LB_BACKUP_REMOTE / LB_BACKUP_BRANCH  transport (defaults origin /
                                       paper-telemetry — shared with the
                                       learning-durability sidecar)
  LB_NO_REMOTE_CMD=1                   disable command polling
  LB_NO_STATUS_PUSH=1                  disable status publishing

CLI:
  python scripts/remote_control.py --poll          # PC: apply pending
  python scripts/remote_control.py --push-status   # PC: publish status
  python scripts/remote_control.py --send pause    # console: queue a cmd
"""
import argparse
import json
import os
import re
import socket
import subprocess  # nosec B404 - fixed argv git calls, no shell
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.codes import Code                          # noqa: E402
from core.runtime import (SingleInstanceLock, VALID_COMMANDS,  # noqa: E402
                          ControlChannel)

OUT = ROOT / "outputs"
QUEUE_DIR = "control/queue"
STATUS_PATH = "control/pc_status.json"
MAX_AGE_SEC = 1800.0        # a command older than this is dead on arrival
MAX_FUTURE_SEC = 300.0      # clock-skew allowance; beyond it = malformed
CONSUMED_CAP = 500          # ids retained in the exactly-once ledger

# The remote whitelist. arm_live is EXCLUDED BY CONSTRUCTION and must stay
# so (tests pin it); sim_* shocks are console-only tooling, not remote.
REMOTE_SAFE_COMMANDS = frozenset({
    "pause", "start", "stop", "entries_on", "entries_off",
    "force_dry", "flatten_all", "snapshot", "disarm_live",
})
# import-time invariant guard: the whitelist must be real commands and can
# never grow arm_live — a violation refuses to even import (tests pin this
# too, but the guard holds when someone edits the set without running them)
_bad = (REMOTE_SAFE_COMMANDS - VALID_COMMANDS) | (
    {"arm_live"} & REMOTE_SAFE_COMMANDS)
if _bad:
    raise RuntimeError(f"remote whitelist invariant violated: {sorted(_bad)}")


# Windows: a child of a WINDOWLESS parent (pc_supervisor spawns these
# sidecars with CREATE_NO_WINDOW) otherwise gets a brand-new console window
# on EVERY subprocess call — the "popping command centers" (this script's
# 120s git poll was the worst offender). CREATE_NO_WINDOW keeps them silent.
# Plain int passed as creationflags= (0 is the POSIX no-op) — a **dict
# unpack typed every subprocess.run kwarg as int for the type checker.
_NOWIN = 0x08000000 if os.name == "nt" else 0

# DL-2 (measured 2026-08-13, 14h auth outage): a git call needing credentials
# pops an interactive Git-Credential-Manager dialog, and nobody is there to
# answer it in a headless sidecar. timeout= does NOT save us — the credential
# helper is a GRANDCHILD holding the inherited capture_output pipe, so after
# subprocess kills the direct child, communicate() still blocks waiting for an
# EOF the survivor never sends. Twelve stacked pushers released together 14h
# later. The fix is upstream of the hang: make git FAIL instead of ASK.
# Injected via ENV ONLY — argv stays untouched, so callers that slice argv for
# error text keep naming the real subcommand.
_NOPROMPT = {
    "GIT_TERMINAL_PROMPT": "0",     # core git: never prompt on a terminal
    # empty askpass disables the GUI helper; git falls through to the terminal
    # path, which GIT_TERMINAL_PROMPT=0 above then refuses
    "GIT_ASKPASS": "",
    "SSH_ASKPASS": "",
    "GCM_INTERACTIVE": "never",     # Git-Credential-Manager: never show UI
    # env-injected config (git >= 2.31): same effect as
    # `-c credential.interactive=false` without touching argv
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "credential.interactive",
    "GIT_CONFIG_VALUE_0": "false",
}


def _git_env() -> dict:
    """os.environ plus the never-prompt overrides. Read fresh per call: the
    supervisor can re-exec these sidecars with a changed environment."""
    return {**os.environ, **_NOPROMPT}


# W2-25: git occasionally echoes the remote URL it tried into stderr (e.g.
# an auth failure names the URL it hit), and every caller logs that text
# verbatim to outputs/remote_control.log — gitignored but readable on the
# box. A remote configured with an embedded credential
# (https://user:token@host/...) would leak the token into that local log.
# Strip userinfo from any URL before it is ever returned/logged.
_URL_USERINFO_RE = re.compile(r"://[^/@\s]+@")


def _redact(text: str) -> str:
    return _URL_USERINFO_RE.sub("://***@", text)


def _git(*args, cwd, timeout=120):
    """Run a git command; return (rc, stdout.strip()). Never raises —
    every caller degrades to a disposition string on failure. Any URL
    userinfo (embedded credentials) in the output is redacted."""
    try:
        p = subprocess.run(["git", *args], cwd=str(cwd),  # nosec B603 B607
                           capture_output=True, text=True, timeout=timeout,
                           creationflags=_NOWIN, env=_git_env())
        out = (p.stdout or "").strip() or (p.stderr or "").strip()
        return p.returncode, _redact(out)
    except Exception as e:                       # noqa: BLE001
        return 1, _redact(f"error: {e}")


def _log(msg: str, root: Path = ROOT) -> None:
    """Append one line to <root>/outputs/remote_control.log.

    Same containment contract as corpus_sync._log (2026-07-31): poll_once /
    send_command already take `root` so a caller can drive a throwaway tree,
    but this wrote to the module-level OUT regardless - so the suite's
    fixtures landed in the operator's real control-plane log (356 copies of
    "runner down - retaining N queued command(s)", plus paired same-second
    command ids that no 120s poll could ever emit). Production behavior is
    unchanged via the default."""
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} remote_control: {msg}"
    # print guarded (security review M3, 2026-08-19): in the headless
    # sidecar a broken stdout pipe raised OSError out of the ONE _log call
    # that sits inside push_pc_status's fail-safe handler - the logger
    # aborting the push it exists to protect. Console output is best-effort
    # everywhere; the file append below was already guarded.
    try:
        print(line, flush=True)
    except OSError:
        pass
    try:
        out = root / "outputs"
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "remote_control.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def _cfg() -> dict:
    return {"remote": os.environ.get("LB_BACKUP_REMOTE", "origin"),
            "branch": os.environ.get("LB_BACKUP_BRANCH", "paper-telemetry")}


# ---------------------------------------------------------------- validation
def validate_command(payload, fname_id: str, now: float) -> str | None:
    """Pure validation: None = valid, else a one-line 'RC-011 …' reason."""
    if not isinstance(payload, dict):
        return f"{Code.RC_REJECTED.value}: payload is not an object"
    if payload.get("id") != fname_id:
        return f"{Code.RC_REJECTED.value}: id/filename mismatch"
    cmd = payload.get("cmd")
    if cmd not in REMOTE_SAFE_COMMANDS:
        return (f"{Code.RC_REJECTED.value}: '{cmd}' not remotely allowed "
                f"(whitelist: {sorted(REMOTE_SAFE_COMMANDS)})")
    try:
        # [] not .get(): a missing key raises KeyError (caught below) rather
        # than handing float() an explicit None; same rejection either way.
        issued = float(payload["issued_at"])
    except (KeyError, TypeError, ValueError):
        return f"{Code.RC_REJECTED.value}: missing/invalid issued_at"
    if now - issued > MAX_AGE_SEC:
        return (f"{Code.RC_REJECTED.value}: stale "
                f"({now - issued:.0f}s old > {MAX_AGE_SEC:.0f}s)")
    if issued - now > MAX_FUTURE_SEC:
        return f"{Code.RC_REJECTED.value}: issued_at is in the future"
    args = payload.get("args")
    if args is not None and not isinstance(args, dict):
        return f"{Code.RC_REJECTED.value}: args must be an object"
    if len(json.dumps(payload)) > 4096:
        return f"{Code.RC_REJECTED.value}: oversized payload"
    return None


# ------------------------------------------------------- exactly-once ledger
def _consumed_path(root: Path) -> Path:
    return root / "outputs" / "remote_consumed.json"


def _load_consumed(root: Path) -> list:
    try:
        v = json.loads(_consumed_path(root).read_text(encoding="utf-8"))
        return v if isinstance(v, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_consumed(root: Path, entries: list) -> None:
    p = _consumed_path(root)
    p.parent.mkdir(exist_ok=True)
    tmp = p.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(entries[-CONSUMED_CAP:], indent=1),
                   encoding="utf-8")
    os.replace(tmp, p)


# ----------------------------------------------------------- branch plumbing
def _publish(root: Path, writes: dict, deletes: list) -> str:
    """Commit {branch-relpath: text} writes and delete `deletes` paths on
    the durable branch, via an isolated worktree (checkout/index/branch of
    `root` untouched — same discipline as telemetry_backup.push_bundle)."""
    cfg = _cfg()
    rc, err = _git("fetch", cfg["remote"], cfg["branch"], cwd=root)
    if rc != 0:
        return f"fetch_failed: {err[:120]}"
    ref = f"{cfg['remote']}/{cfg['branch']}"
    with tempfile.TemporaryDirectory(prefix="lb_rc_wt_") as wtd:
        wt = Path(wtd) / "wt"
        rc, err = _git("worktree", "add", "--detach", "--force",
                       str(wt), ref, cwd=root)
        if rc != 0:
            return f"worktree_failed: {err[:120]}"
        try:
            for rel, text in writes.items():
                dest = wt / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text, encoding="utf-8")
            removed = []
            for rel in deletes:
                p = wt / rel
                if p.exists():
                    try:
                        p.unlink()
                        removed.append(rel)      # only a tracked, present file
                    except OSError:
                        pass
            # Stage ONLY the paths this publish touches — NEVER `git add -A`.
            # A blanket add re-stages sibling LEARNING bundles too, and on a
            # Windows pusher (pc_status is published every ~600s from the PC)
            # under the branch's `-text` pin their checked-out CRLF bytes get
            # committed verbatim, rewriting bundle blobs out of sync with
            # their manifests and breaking every puller's integrity check
            # (the 2026-07-18 corpus-integrity incident — telemetry_backup
            # had the identical bug). Keep the -text pin present too.
            #
            # Only pathspecs that EXIST are passed: `git add -A -- <path>`
            # aborts the WHOLE add (rc=128, nothing staged) if any pathspec
            # matches no file, and a consumed-queue delete often references
            # a file already GC'd on the tip — that regressed the status
            # push into a permanent "no_change" (blind pc_status, 2026-07-18).
            ga = wt / ".gitattributes"
            if not ga.exists():
                ga.write_text("* -text\n", encoding="utf-8")
            pathspecs = sorted(set(list(writes) + removed + [".gitattributes"]))
            _git("add", "-A", "--", *pathspecs, cwd=wt)
            rc, porcelain = _git("status", "--porcelain", cwd=wt)
            if not porcelain.strip():
                return "no_change"
            rc, err = _git("commit", "-m",
                           f"remote-control: {', '.join(writes) or 'gc'}",
                           cwd=wt)
            if rc != 0:
                return f"commit_failed: {err[:120]}"
            rc, new = _git("rev-parse", "HEAD", cwd=wt)
            rc, err = _git("push", cfg["remote"],
                           f"{new}:refs/heads/{cfg['branch']}", cwd=root)
            return "pushed" if rc == 0 else f"push_failed: {err[:120]}"
        finally:
            _git("worktree", "remove", "--force", str(wt), cwd=root)
            _git("worktree", "prune", cwd=root)


# ------------------------------------------------------------- PC: consume
def _runner_alive(root: Path, now: float) -> bool:
    """The runner purges its whole local control queue at boot as stale, so
    a command forwarded while it is DOWN would be ledgered 'applied' and
    then silently discarded by the next boot (audit C-F3 2026-07-17). Only
    forward into a live runner; otherwise the branch queue is retained and
    retried next poll (commands still expire on their own 30-min clock)."""
    try:
        s = json.loads((root / "outputs" / "status.json")
                       .read_text(encoding="utf-8"))
        # FRESHNESS IS NOT LIVENESS (2026-08-05): the clean-shutdown path
        # writes a FINAL status with runner_state STOPPED and a fresh
        # written_at (runner.py, the stop epilogue), so freshness alone
        # reads a just-stopped runner as alive for a full 120s. Every
        # deploy bounce opens that window, and a command forwarded into it
        # is ledgered 'applied' at-most-once and then purged by the next
        # boot as predating _PROC_START - an acked flatten_all/stop that
        # never runs. A terminal state means DOWN regardless of freshness;
        # the queue is retained and retried, which is the whole point of
        # the gate.
        if str(s.get("runner_state", "")).upper() in ("STOPPED", "EXITED"):
            return False
        if now - float(s.get("written_at", 0) or 0) < 120.0:
            return True
    except (OSError, ValueError, TypeError):
        pass
    try:
        lk = json.loads((root / "outputs" / "runner.lock")
                        .read_text(encoding="utf-8"))
        return now - float(lk.get("heartbeat", 0) or 0) < 60.0
    except (OSError, ValueError, TypeError):
        return False


def poll_once(root: Path = ROOT, now: float | None = None) -> str:
    """Fetch the branch, validate every unseen queue file, forward valid
    commands to the local ControlChannel. Returns a disposition summary.
    Single-instance locked: two overlapping pollers would both read the
    ledger before either saved it and double-forward (audit C-F6)."""
    if os.environ.get("LB_NO_REMOTE_CMD"):
        return "disabled"
    now = time.time() if now is None else now
    lock = SingleInstanceLock(str(root / "outputs" / "remote_poll.lock"),
                              stale_after_sec=300.0)
    if lock.acquire() is not None:
        return "busy"
    try:
        return _poll_locked(root, now)
    finally:
        lock.release()


def _poll_locked(root: Path, now: float) -> str:
    cfg = _cfg()
    rc, err = _git("fetch", cfg["remote"], cfg["branch"], cwd=root)
    if rc != 0:
        return f"fetch_failed: {err[:120]}"
    rc, listing = _git("ls-tree", "--name-only",
                       f"{cfg['remote']}/{cfg['branch']}:{QUEUE_DIR}",
                       cwd=root)
    if rc != 0 or not listing.strip():
        return "queue_empty"
    consumed = _load_consumed(root)
    seen = {e.get("id") for e in consumed}
    fresh = [f for f in listing.split()
             if f.endswith(".json") and f[:-5] not in seen]
    if fresh and not _runner_alive(root, now):
        _log(f"runner down - retaining {len(fresh)} queued command(s) for "
             f"the next poll (forwarding now would be purged at boot)",
             root=root)
        return f"runner_down retained={len(fresh)}"
    applied = rejected = 0
    for fname in fresh:
        fid = fname[:-5]
        rc, raw = _git("show",
                       f"{cfg['remote']}/{cfg['branch']}:{QUEUE_DIR}/{fname}",
                       cwd=root)
        if rc != 0:
            # TRANSIENT FETCH FAILURE IS NOT A BAD COMMAND (round-2 fix
            # 2026-08-05). A failed `git show` - subprocess spawn failure
            # (seen live 2026-07-21), an AV scan holding the object, git
            # contention with the concurrent status-push/telemetry-backup
            # children - used to produce payload=None, which validate_command
            # rightly calls "payload is not an object" and the exactly-once
            # ledger then makes PERMANENT. A one-off git hiccup silently and
            # irreversibly dropped a live operator command that was still
            # valid and fresh on the branch. Leave it UNLEDGERED so the next
            # poll retries it; the command's own 30-minute expiry still
            # bounds how long it can be retried.
            _log(f"transient read failure for id {fid} (git rc={rc}) - "
                 f"leaving it queued for the next poll", root=root)
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        reason = validate_command(payload, fid, now)
        if reason:
            rejected += 1
            _log(f"{reason} (id {fid})", root=root)
            consumed.append({"id": fid, "result": "rejected",
                             "reason": reason, "at": now})
            _save_consumed(root, consumed)
            continue
        # reason is None ⇒ validate_command proved payload is a dict
        payload = cast(dict, payload)
        cmd, args = payload["cmd"], payload.get("args") or {}
        # AT-MOST-ONCE: ledger the id BEFORE forwarding. A crash between
        # the two leaves an honest 'forwarding' entry (visible in the
        # pc_status acks) and the command is never re-forwarded — a
        # replayed flatten_all after a fill-and-reopen gap would flatten
        # positions the operator never asked about (audit C-F5).
        consumed.append({"id": fid, "result": "forwarding",
                         "cmd": cmd, "at": now})
        _save_consumed(root, consumed)
        ControlChannel(str(root / "outputs" / "control")).send(cmd, args)
        applied += 1
        _log(f"{Code.RC_APPLIED.value}: forwarded '{cmd}' to the "
             f"runner (id {fid})", root=root)
        consumed[-1]["result"] = "applied"
        _save_consumed(root, consumed)
    return f"applied={applied} rejected={rejected}"


# ------------------------------------------------------------- PC: publish
def push_pc_status(root: Path = ROOT) -> str:
    """Publish outputs/status.json (+ the remote-command ledger tail) to the
    branch, and garbage-collect consumed queue files in the same commit."""
    if os.environ.get("LB_NO_STATUS_PUSH"):
        return "disabled"
    status_p = root / "outputs" / "status.json"
    try:
        status = json.loads(status_p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "no_status"
    consumed = _load_consumed(root)
    # deploy observable: which code THIS box runs and how its last
    # self-update attempt ended. Found live 2026-07-18: the updater
    # failed silently for 6+ hours and no off-box channel said why.
    deploy: dict = {}
    try:
        rc, head = _git("rev-parse", "--short", "HEAD", cwd=root)
        if rc == 0:
            deploy["head"] = head.strip()
        au = root / "outputs" / "auto_update_state.json"
        if au.exists():
            deploy["auto_update"] = json.loads(au.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    # DL-6: a frozen bot would otherwise be republished every cycle with a
    # FRESH pushed_at, masquerading as live off-box. Stamp the staleness so
    # every consumer (Grafana, session digests, operators) reads it without
    # doing its own written_at arithmetic. Alarm-only: the push still
    # happens — a stale status is exactly what the off-box channel must
    # show, loudly, when the runner is wedged.
    push_ts = time.time()
    try:
        _age = push_ts - float(status.get("written_at", 0.0) or 0.0)
    except (TypeError, ValueError):
        _age = -1.0
    # era-4 gate accrual: the pre-registered n toward the verdict, computed
    # from fills.csv PC-side because fills never leave the box in real time
    # (measured 2026-08-18: the project's single most-awaited number was
    # unreadable off-box). Reuses cohort_eval's own reconstruction so this
    # can never drift from what the gate itself will count. Fail-safe: any
    # error -> None, the push itself is untouched.
    # target = ERA4_MIN_N (50): the FIRST-readout floor, unchanged from the
    # pre-registration. signed_continue_n: the operator-signed decision table
    # (docs/quant/2026-08-16_era4_readout_decision_table.md, signed
    # 2026-08-17T01:00Z) binds branches 1D and 3A to KEEP ACCRUING to n=100
    # past that first readout - publishing only 50 understated the plausible
    # wait by 2x (caught 2026-08-19 verifying an off-hand accrual claim).
    era4: dict = {"accrual_n": None, "target": None, "signed_continue_n": 100}
    try:
        from scripts.cohort_eval import ERA4_MIN_N, era4_trips
        era4["target"] = ERA4_MIN_N
        fills_p = root / "outputs" / "fills.csv"
        if fills_p.exists():
            era4["accrual_n"] = len(era4_trips(str(fills_p)))
    except Exception as e:                               # noqa: BLE001
        _log(f"era4 accrual skipped ({e}) - status push unaffected",
             root=root)
    envelope = {"pushed_at": push_ts, "host": socket.gethostname(),
                "status_age_sec": round(_age, 1),
                "status_stale": bool(_age > 300.0 or _age < 0.0),
                "status": status, "deploy": deploy, "era4": era4,
                "remote_commands": consumed[-20:]}
    deletes = [f"{QUEUE_DIR}/{e['id']}.json" for e in consumed
               if e.get("id")]
    return _publish(root, {STATUS_PATH: json.dumps(envelope, indent=1)},
                    deletes)


# --------------------------------------------------------- console: enqueue
def send_command(cmd: str, args: dict | None = None,
                 root: Path = ROOT) -> str:
    """Queue a remote command on the branch. Refuses anything outside the
    whitelist BEFORE it ever reaches the transport."""
    if cmd not in REMOTE_SAFE_COMMANDS:
        raise ValueError(f"'{cmd}' is not remotely allowed "
                         f"(whitelist: {sorted(REMOTE_SAFE_COMMANDS)})")
    cid = f"{int(time.time())}-{uuid.uuid4().hex[:10]}"
    payload = {"id": cid, "cmd": cmd, "args": args or {},
               "issued_at": time.time(), "issued_by": socket.gethostname()}
    out = _publish(root, {f"{QUEUE_DIR}/{cid}.json":
                          json.dumps(payload, indent=1)}, [])
    if out != "pushed":
        raise RuntimeError(f"command not queued: {out}")
    _log(f"queued '{cmd}' as {cid}", root=root)
    return cid


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--poll", action="store_true")
    g.add_argument("--push-status", action="store_true")
    g.add_argument("--send", metavar="CMD")
    ap.add_argument("--args", default="{}",
                    help="JSON object of command args (with --send)")
    ns = ap.parse_args()
    try:
        if ns.poll:
            out = poll_once()
        elif ns.push_status:
            out = push_pc_status()
        else:
            out = send_command(ns.send, json.loads(ns.args))
        _log(out)
        return 0
    except Exception as e:  # noqa: BLE001 - CLI surface: report, exit nonzero
        _log(f"error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
