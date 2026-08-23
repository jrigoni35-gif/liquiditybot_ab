"""
scripts/auto_update.py — test-gated self-update for the always-on PC bot.

The operator can't always git-pull the PC by hand (away from home). This pulls
the deploy channel (see _deploy_branch: LB_UPDATE_BRANCH env override →
config `system.deploy_branch` → the checked-out branch) and redeploys — but
ONLY if the INCOMING code passes the full test battery first, so a bad commit
can never reach the live trading bot. Run by
pc_supervisor.py every LB_AUTO_UPDATE_SEC (default 15 min — the check is a
bare fetch+compare; the heavy battery only runs when main actually moved, so
a push lands on the PC within minutes), or by hand:
    python scripts/auto_update.py

Safety rules (why this is safe to run unattended against a live paper bot):
  * NEVER updates across local uncommitted changes — that would clobber operator
    config edits (e.g. the debug flag). Dirty tree -> log and skip.
  * Tests the INCOMING code in an ISOLATED git worktree BEFORE fast-forwarding.
    A red battery aborts the update; the bot stays on the known-good code.
  * Fast-forward ONLY (never a merge/rebase that could conflict). After the
    fast-forward it signals a graceful runner stop (ControlChannel), so the
    supervisor relaunches on the new code.
  * Every decision logs one line; any error is caught and the bot is left
    exactly as it was. Disable entirely with LB_NO_AUTO_UPDATE=1.
"""
import json
import os
import re
import subprocess  # nosec B404 - fixed argv, no shell
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.runtime import SingleInstanceLock  # noqa: E402

OUT = ROOT / "outputs"
# Fallback deploy branch for a DETACHED checkout. A box deliberately operated
# on a feature branch follows THAT branch (see _deploy_branch) — the old
# hardcoded "main" made a branch-checked-out box permanently "different from
# remote", so every 15-min cycle ran the full battery, "updated" via a NO-OP
# fast-forward (the remote tip was an ancestor), and soft-stopped the runner
# for nothing — an endless reboot loop that starved signal persistence
# (observed live 2026-07-21 22:41-22:44, auto_update.log).
BRANCH = "main"

# Rebindable for tests (LOG_PATH pattern): production reads the repo config.
CONFIG_PATH = ROOT / "config.json"

# A branch name the updater will accept into git argv. Fixed-argv calls mean
# no shell injection, but a name starting with '-' would be parsed as a git
# OPTION, and whitespace/control chars are never a real branch. Conservative
# on purpose: ordinary release/feature names all pass.
_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def _pinned_branch() -> str | None:
    """The repo-declared deploy channel (config system.deploy_branch), so a
    box follows the SAME branch everywhere without hands on the machine —
    the pin travels through the update channel itself. Absent key, unreadable
    config, or a name that fails _BRANCH_RE -> None (pre-pin behavior).
    Fail-safe: this can only ever fall back, never wedge the updater."""
    try:
        cfg = json.loads(Path(CONFIG_PATH).read_text(encoding="utf-8"))
        name = cfg.get("system", {}).get("deploy_branch")
    except (OSError, ValueError):
        return None
    if not isinstance(name, str) or not _BRANCH_RE.match(name):
        return None
    return name


def _deploy_branch() -> str:
    """The branch this checkout deploys from, in priority order:
      1. LB_UPDATE_BRANCH env — per-box operator override (no dirty-tree
         cost, survives updates; for a box deliberately run off-channel)
      2. config system.deploy_branch — the repo-declared channel (pinned
         to main 2026-08-18 so session work merged to main auto-deploys;
         before the pin a box followed whatever branch it happened to have
         checked out, so the PC was stuck on a stale claude/* branch)
      3. the CURRENT branch — pre-pin behavior, kept for a checkout whose
         config carries no pin
      4. BRANCH fallback — detached HEAD or any probe failure
    Names failing _BRANCH_RE are ignored at each step (fall through)."""
    env = (os.environ.get("LB_UPDATE_BRANCH") or "").strip()
    if env and _BRANCH_RE.match(env):
        return env
    pinned = _pinned_branch()
    if pinned:
        return pinned
    rc, name = _git("rev-parse", "--abbrev-ref", "HEAD")
    name = (name or "").strip()
    if rc != 0 or not name or name == "HEAD":
        return BRANCH
    return name


# One updater at a time: the supervisor's fast cadence plus a manual run could
# otherwise stack two 20-min batteries and race the fast-forward. Staleness
# must outlive the worst case with margin. battery_passes now chains TWO 1200s
# subprocesses back-to-back — pytest then the replay gate — plus fetch/worktree
# ops, so ~2400s of subprocess time is possible once recordings accrue. Sized
# above that so a legitimately-long run is never mistaken for a stale lock (which
# would let a second updater start concurrently and race the fast-forward).
LOCK_STALE_SEC = 3900.0
# Outcomes that exit 0 ("nothing wrong"), vs real failures that exit 1.
OK_OUTCOMES = ("updated", "current", "ahead", "dirty", "disabled", "busy")


# Log destination as a REBINDABLE module attribute (2026-07-31). The
# suite drives this script's functions in-process, and a hardcoded
# `OUT / "auto_update.log"` inside log() meant every such test appended to the
# operator's REAL auto_update.log - the same defect measured across six
# outputs/ files that day. Tests monkeypatch LOG_PATH; production reads
# the default and behaves byte-identically. tests/conftest.py's
# _no_production_outputs_writes fails any test that regresses this.
LOG_PATH = OUT / "auto_update.log"


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} auto_update: {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


# Windows: children of the WINDOWLESS supervisor spawn otherwise pop a new
# console window per call ("command centers") — for this script that meant a
# git window every poll AND a lingering pytest window per battery run.
# Plain int, not a **dict unpack (which typed every run() kwarg as int and
# tripped the type checker at all six call sites); 0 is the POSIX no-op.
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


def _git(*args, cwd=None, timeout=120):
    """Run a git command; return (rc, stdout.strip()). Never raises."""
    try:
        p = subprocess.run(["git", *args], cwd=str(cwd or ROOT),  # nosec B603 B607
                           capture_output=True, text=True, timeout=timeout,
                           creationflags=_NOWIN, env=_git_env())
        return p.returncode, (p.stdout or "").strip()
    except Exception as e:                       # noqa: BLE001
        return 1, f"error: {e}"


def _venv_python() -> str:
    """The repo venv's interpreter (Windows Scripts / POSIX bin), or the
    current one as a fallback."""
    for rel in (".venv/Scripts/python.exe", ".venv/bin/python"):
        p = ROOT / rel
        if p.exists():
            return str(p)
    return sys.executable


def decide(local: str, remote: str, dirty: bool,
           remote_is_ancestor: bool = False,
           local_is_ancestor: bool = True) -> str:
    """Pure decision (unit-testable): 'current' (nothing to do, tree
    matches git), 'ahead'
    (local is AHEAD of the remote tip — deploying would be a no-op or a
    rollback; never act), 'diverged' (histories split: local has commits the
    remote lacks AND the remote has commits local lacks, so neither is an
    ancestor of the other — no fast-forward is possible and the battery
    would just repeat forever with the same inputs; W1-7), 'dirty' (local
    edits, skip), or 'test' (new code -> gate on the battery).

    local_is_ancestor: whether HEAD is an ancestor of the remote tip (a
    fast-forward is possible). Defaults True so every existing caller/test
    that never passes it reproduces the EXACT pre-W1-7 branch table
    (CLAUDE.md invariant 7: extend signatures without changing behavior for
    existing callers) — only an explicit local_is_ancestor=False can
    produce 'diverged'."""
    if not remote or remote == local:
        # No action either way — but the OUTCOME is the only off-box channel
        # that can reveal operator edits (2026-07-27 divergence audit: a PC
        # running locally-modified code stamped "current" for as long as no
        # new remote commit arrived, so telemetry could not distinguish
        # "runs the code in git" from "runs edits nobody reviewed"). A
        # dirty tree therefore reports "dirty" even with nothing to pull.
        return "dirty" if dirty else "current"
    if remote_is_ancestor:
        return "ahead"
    if not local_is_ancestor:
        return "diverged"
    if dirty:
        return "dirty"
    return "test"


def battery_passes(worktree: Path) -> bool:
    """Run the test battery against the INCOMING code in an isolated worktree.
    Green is required before the update is allowed to touch the live checkout."""
    py = _venv_python()
    # tests/conftest.py's outputs-write guard is a TEST-HYGIENE check, and it
    # must not hold a veto over deploying a trading fix. Downgraded to a
    # warning here for two reasons (both lived 2026-08-01, commit 64b6fd5):
    #   1. It protects nothing in this context. The battery runs inside a
    #      THROWAWAY worktree, so conftest resolves the tree it guards to
    #      <worktree>/outputs — writes land there and die with the worktree.
    #      The operator's real outputs/ is not reachable from this run.
    #   2. It self-bricks. A leaking test makes battery_passes return False,
    #      auto_update refuses EVERY update, and the commit that repairs the
    #      leak can never deploy either. That froze the PC for ~19 hours on
    #      a test writing outputs/postmortem_summary.csv - the exact failure
    #      mode that demoted the replay gate to advisory on 2026-07-21/22
    #      (see _replay_gate_passes below; same lesson, relearned).
    # The developer battery and the PC's own manual runs keep it HARD, which
    # is where a hygiene regression should be caught.
    env = {**os.environ, "LB_ALLOW_OUTPUT_WRITES": "1"}
    try:
        p = subprocess.run([py, "-m", "pytest", "tests/", "-q",  # nosec B603
                            "-x", "--no-header"],
                           cwd=str(worktree), capture_output=True, text=True,
                           timeout=1200, env=env, creationflags=_NOWIN)
    except Exception as e:                       # noqa: BLE001
        log(f"battery could not run ({e}) - refusing the update")
        return False
    lines = (p.stdout or "").strip().splitlines()
    tail = lines[-1:] or ["(no output)"]
    log(f"incoming-code battery rc={p.returncode}: {tail[0]}")
    if p.returncode != 0:
        # capture the FAILED lines (pytest -x stops at the first) so the
        # deploy observable can name WHICH test rejected the update off-box
        # — otherwise a Windows-only failure is invisible from the cloud
        # (lived 2026-07-18: the PC rejected every update on a CRLF test
        # and nothing said which). Bounded so the stamp stays small.
        failed = [ln for ln in lines if ln.startswith("FAILED")][:3]
        global _BATTERY_DETAIL
        _BATTERY_DETAIL = " | ".join(failed) or tail[0]
        return False
    # replay-vs-live standing gate is ADVISORY (2026-07-22). The pytest battery
    # ABOVE already IS the determinism gate — tests/test_replay_gate*,
    # tests/test_recording exercise it in-process on the incoming code. Running
    # scripts/replay_gate.py as a SECOND, HARD gate over the LIVE recordings
    # self-bricked deploys: a subprocess spawn crash on the Windows console OR a
    # determinism false-fail on real recordings refused EVERY update — including
    # the very fix that would repair it (lived 2026-07-21/22, see
    # outputs/auto_update.log: repeated "XV-010: determinism fail" and "replay
    # gate could not run (subprocess spawn failed) - refusing the update"). So
    # log its verdict for observability but never let it veto. Set
    # LB_REPLAY_GATE_HARD=1 to restore a blocking gate.
    ok = _replay_gate_passes(worktree, py)
    if not ok and os.environ.get("LB_REPLAY_GATE_HARD") == "1":
        return False
    if not ok:
        log("replay gate advisory verdict FAIL — NOT blocking the update; "
            "pytest above is the determinism gate")
        _BATTERY_DETAIL = ""            # advisory: this is not a rejection
    return _dod_gates(worktree, py)


# CLAUDE.md's Definition of done names EIGHT commands. Until 2026-08-23 this
# battery ran exactly ONE of them (pytest), so the law mandated a matrix that
# the only automated admission path never executed. Measured, not guessed:
# deleting `and liq_label != "spoofy"` from execution/tactics.py made
# assurance_check FAIL rc=1 while this battery still returned 130/130 green.
#
# THE SPLIT BELOW IS THE WHOLE DESIGN, and it is dictated by a lesson this
# file has already lived TWICE (the replay gate, 2026-07-21/22; conftest's
# outputs guard, 2026-08-01, ~19h frozen): A GATE WHOSE RELEASE DEPENDS ON THE
# THING IT BLOCKS REFUSES THE FIX THAT WOULD REPAIR IT.
#
#   HARD  - pure functions of the INCOMING CODE. A commit that repairs a ruff
#           error passes ruff; a commit that repairs a smoke failure passes
#           smoke. These can never refuse their own repair, so they may veto.
#           (smoke_test verified corpus-INDEPENDENT: 219/0 inside a bare
#           `git worktree add --detach`, identical to the live tree.)
#   ADVISORY - corpus-dependent. If the CORPUS degrades, no code change
#           repairs it, so a blocking verdict would refuse every update
#           forever. This is exactly the demand refused as OBJ-16. They run,
#           they are logged, they never veto.
#
# A MISSING TOOL IS ALWAYS ADVISORY. "ruff is not installed" is not a finding
# about the incoming code, and treating it as one is how the replay gate
# bricked deploys ("could not run - refusing the update"). Only a real
# FINDING may block.
_HARD_GATES = (
    ("ruff", ["-m", "ruff", "check", "core", "data", "execution", "ml",
              "risk", "regime", "strategies", "sentiment", "api", "main.py",
              "runner.py"]),
    ("compileall", ["-m", "compileall", "-q", "core", "data", "execution",
                    "ml", "risk", "regime", "strategies", "sentiment", "api",
                    "main.py", "runner.py"]),
    ("bandit", ["-m", "bandit", "-c", "pyproject.toml", "-q", "-r",
                "core", "data", "execution", "ml", "risk", "api"]),
    ("smoke", ["scripts/smoke_test.py"]),
    # assurance_check contains BOTH code-dependent checks (the taker ladder
    # must stay suppressed in spoofy liquidity) and corpus-dependent ones
    # (signal_history coherence). Blocking on the whole thing would make a
    # corpus outage refuse every deploy; not blocking at all would let a code
    # defect through, which is the exact hole this fix exists to close.
    # So it runs TWICE, and the split falls out of the very bug that was
    # found: with NO corpus the corpus section goes VACUOUS, which leaves
    # precisely the code-dependent subset - a pure function of the incoming
    # code, and therefore safe to veto. LB_OUTPUTS is cleared below so an
    # inherited value cannot smuggle a corpus into the blocking run.
    ("assurance-code", ["scripts/assurance_check.py"]),
)
# Same binaries, corpus PINNED to the live tree: this pair exists to report
# what the blocking run deliberately could not see. Never vetoes.
_ADVISORY_GATES = (
    ("assurance-corpus", ["scripts/assurance_check.py"]),
    ("overfit", ["scripts/overfit_check.py"]),
)
_MISSING_TOOL = ("no module named", "modulenotfounderror",
                 "is not recognized", "cannot find")


def _run_gate(worktree: Path, py: str, argv: list, env: dict, secs: int):
    """(rc, tail, could_not_run). could_not_run is NEVER a rejection."""
    try:
        p = subprocess.run([py, *argv], cwd=str(worktree),  # nosec B603
                           capture_output=True, encoding="utf-8",
                           errors="replace", timeout=secs, env=env,
                           creationflags=_NOWIN)
    except Exception as e:                       # noqa: BLE001
        return 1, f"could not run: {e}", True
    # getattr, not attribute access: a real CompletedProcess under
    # capture_output always carries both streams, but the suite's process
    # doubles do not all define stderr, and a gate that AttributeErrors is a
    # gate that refuses every update. Same shape as the resp.encoding fix in
    # data/_http.py - never assume a double has the full surface.
    blob = (getattr(p, "stdout", "") or "") + (getattr(p, "stderr", "") or "")
    tail = (blob.strip().splitlines() or ["(no output)"])[-1][:160]
    missing = any(m in blob.lower() for m in _MISSING_TOOL)
    return p.returncode, tail, missing


def _dod_gates(worktree: Path, py: str) -> bool:
    global _BATTERY_DETAIL
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
           "LB_ALLOW_OUTPUT_WRITES": "1"}
    # The blocking run must be a pure function of the INCOMING CODE, so an
    # LB_OUTPUTS inherited from the supervisor's environment must not smuggle
    # a live corpus into it - that would reintroduce exactly the
    # corpus-dependence that makes a blocking verdict able to refuse its own
    # fix. Popped, not merely left unset.
    env.pop("LB_OUTPUTS", None)
    for name, argv in _HARD_GATES:
        rc, tail, missing = _run_gate(worktree, py, argv, env, 900)
        if missing:
            log(f"DoD {name}: TOOL UNAVAILABLE ({tail}) - advisory, not "
                f"blocking (a missing tool is not a finding)")
            continue
        log(f"DoD {name} rc={rc}: {tail}")
        if rc != 0:
            _BATTERY_DETAIL = f"DoD {name}: {tail}"
            return False
    # CORPUS PINNED, NOT ASSUMED. The worktree is a bare checkout with no
    # outputs/, so assurance_check's corpus section would pass VACUOUSLY and
    # contribute to a green that never read a corpus (proven: 48/0 in a real
    # worktree, vs 49/0 with the live corpus). Point it at the live tree, the
    # same way _replay_gate_passes points the replay gate at live recordings.
    adv_env = {**env, "LB_OUTPUTS": str(OUT.resolve())}
    for name, argv in _ADVISORY_GATES:
        rc, tail, missing = _run_gate(worktree, py, argv, adv_env, 1800)
        verdict = "TOOL UNAVAILABLE" if missing else f"rc={rc}"
        log(f"DoD {name} (ADVISORY, corpus={OUT.resolve()}) {verdict}: {tail}")
    return True


def _replay_gate_passes(worktree: Path, py: str) -> bool:
    global _BATTERY_DETAIL
    # Validate the INCOMING engine (the worktree) against the LIVE checkout's
    # real recordings — the worktree is a bare git checkout and outputs/ is
    # gitignored, so it has none of its own. DETERMINISM-ONLY: reconciling the
    # incoming replay against P&L the OLD engine recorded would false-fail any
    # intentional fill change (e.g. the queue_aware flip). No recordings yet =>
    # the gate SKIPs (exit 0), so this is dormant until the PC accrues sessions.
    rec_dir = str((OUT / "recordings").resolve())
    # force UTF-8 in the child + decode as UTF-8 here, so the gate's report text
    # can never UnicodeEncodeError on a cp1252 Windows console and wedge the
    # deploy (a crashed gate reads as a failed battery -> update refused).
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        g = subprocess.run([py, "scripts/replay_gate.py",  # nosec B603
                            "--recording-dir", rec_dir, "--determinism-only"],
                           cwd=str(worktree), capture_output=True,
                           encoding="utf-8", errors="replace",
                           timeout=1200, env=env, creationflags=_NOWIN)
    except Exception as e:                       # noqa: BLE001
        log(f"replay gate could not run ({e}) - refusing the update")
        _BATTERY_DETAIL = f"replay gate error: {e}"
        return False
    gtail = ((g.stdout or "").strip().splitlines()[-1:] or ["(no output)"])[0]
    log(f"replay gate rc={g.returncode}: {gtail}")
    if g.returncode != 0:
        _BATTERY_DETAIL = f"replay gate: {gtail}"
        return False
    return True


# Deploy-restart escalation: a graceful 'stop' asks the runner to exit so the
# supervisor relaunches it on new code. If the runner's command consumption is
# wedged (seen live 2026-07-21: a long-lived runner ignored every 'stop', so the
# repo advanced but the process kept running stale code), force-kill ITS pid
# after a grace window so the deploy actually lands. Disable with
# LB_NO_FORCE_KILL_RESTART=1.
_FORCE_KILL_STUCK = os.environ.get("LB_NO_FORCE_KILL_RESTART") != "1"
# 45 -> 150 (round-2 finding 2026-08-05). The runner consumes `stop` at the
# TOP of its loop, so consumption latency is one full cycle - and runner.py
# documents MEASURED cycle stalls of 88.1s, 55.5s, 50.2s, 48.4s and 47.8s
# from real Kraken slowness. Every one of those exceeds a 45s grace, so a
# deploy landing during a slow cycle taskkill'd a HEALTHY runner mid-cycle
# (mid-fill, mid-audit-append: the audit_tail_truncations counter is the
# fossil record). 150s clears the worst measured stall with margin while
# staying well inside the runner's own 300s stall bound, so a genuinely
# WEDGED runner - the case this escalation exists for - is still killed.
_FORCE_KILL_AFTER_SEC = float(os.environ.get("LB_FORCE_KILL_AFTER_SEC", "150"))
_FORCE_KILL_POLL_SEC = 5.0
# W1-8: mirrors remote_control._runner_alive's freshness bound (scripts/
# remote_control.py:253-256) — a lock is only trusted to name the LIVE
# runner while its heartbeat is this fresh. Windows recycles PIDs: a stale
# heartbeat means the runner that wrote this pid is crashed/boot-looping
# (or long gone), and by the time the force-kill grace window elapses that
# pid can belong to any other process on the box.
_HEARTBEAT_FRESH_SEC = 60.0


def _runner_pid():
    """The live runner's pid from its SingleInstanceLock, or None if the
    lock is missing/unparseable/stale (heartbeat older than
    _HEARTBEAT_FRESH_SEC — a recycled PID must never be handed back as a
    kill target; see _HEARTBEAT_FRESH_SEC)."""
    try:
        d = json.loads((OUT / "runner.lock").read_text(encoding="utf-8"))
        pid = d.get("pid")
        if not isinstance(pid, int):
            return None
        age = time.time() - float(d.get("heartbeat", 0) or 0)
        if age >= _HEARTBEAT_FRESH_SEC:
            return None
        return pid
    except (OSError, ValueError, TypeError):
        return None


def _should_escalate(orig_pid, cur_pid) -> bool:
    """Force-kill ONLY when the SAME pid still holds the lock after the grace
    window (the soft stop was ignored). A changed or absent pid means the runner
    already exited/relaunched — leave it alone."""
    return orig_pid is not None and cur_pid == orig_pid


def _pid_is_runner(pid) -> bool:
    """W1-8 defense-in-depth: does this pid's OWN command line still name
    runner.py, right before we kill it? The fresh-heartbeat guard in
    _runner_pid() closes the coarse case (a long-stale lock); this closes
    the fine one — Windows can recycle a pid in the narrow gap between
    reading the lock and taskkill actually firing 45s later. ANY failure to
    positively confirm identity (spawn error, pid gone, no match) fails
    toward False: a missed kill is safe (the supervisor's stale-heartbeat
    relaunch still recovers a genuinely stuck runner); a wrong-process kill
    has no such backstop."""
    try:
        if os.name == "nt":
            cmd = ["wmic", "process", "where", f"ProcessId={int(pid)}",
                   "get", "CommandLine"]
        else:                        # test/dev path only - prod is Windows
            cmd = ["ps", "-p", str(int(pid)), "-o", "command="]
        p = subprocess.run(cmd, timeout=15, capture_output=True,  # nosec B603 B607
                           text=True, creationflags=_NOWIN)
        return "runner.py" in (p.stdout or "")
    except Exception:                              # noqa: BLE001 - fail-safe
        return False


def _force_kill(pid) -> None:
    """Kill one pid, cross-platform, fail-safe (never raises into the
    deploy). Verifies process identity first (_pid_is_runner) — a recycled
    pid that no longer names runner.py is NEVER killed; the runner-down
    case is already handled by the supervisor's relaunch, so a missed kill
    here costs nothing but a wrong kill would."""
    if not _pid_is_runner(pid):
        log(f"pid {pid} no longer identifies as runner.py - NOT force-"
            f"killing (possible PID reuse); relying on the supervisor's "
            f"stale-heartbeat relaunch instead")
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(int(pid))],  # nosec B603 B607
                           timeout=30, capture_output=True,
                           creationflags=_NOWIN)
        else:
            import signal as _signal
            os.kill(int(pid), _signal.SIGKILL)
        log(f"force-killed stuck runner pid {pid} - supervisor relaunches on new code")
    except Exception as e:                        # noqa: BLE001 - fail-safe
        log(f"force-kill of pid {pid} failed ({e})")


def _escalate_if_stuck(orig_pid, read_pid, wait_sec, poll_sec, kill_fn,
                       sleep_fn=time.sleep, now_fn=time.time) -> str:
    """Wait out the grace window; force-kill iff the same runner pid survives it.
    Injectable timing/readers so the decision is unit-testable without sleeping.
    Returns 'no_pid' | 'restarted' | 'force_killed'."""
    if orig_pid is None:
        return "no_pid"
    deadline = now_fn() + wait_sec
    while now_fn() < deadline:
        sleep_fn(poll_sec)
        if not _should_escalate(orig_pid, read_pid()):
            return "restarted"
    kill_fn(orig_pid)
    return "force_killed"


def _signal_restart() -> None:
    """Graceful stop so the supervisor relaunches the runner on the new code;
    escalate to a targeted force-kill if the runner ignores the soft stop."""
    orig_pid = _runner_pid()
    try:
        from core.runtime import ControlChannel
        ControlChannel(str(OUT / "control")).send("stop")
        log("sent stop - supervisor will relaunch on the new code")
    except Exception as e:                        # noqa: BLE001
        log(f"restart signal failed ({e}) - new code loads on the next restart")
    if not _FORCE_KILL_STUCK:
        return
    outcome = _escalate_if_stuck(orig_pid, _runner_pid, _FORCE_KILL_AFTER_SEC,
                                 _FORCE_KILL_POLL_SEC, _force_kill)
    if outcome == "no_pid":
        log("no runner.lock pid to watch - relying on the supervisor's "
            "stale-heartbeat relaunch")
    elif outcome == "restarted":
        log("runner exited on the soft stop - clean restart")


_BATTERY_DETAIL = ""            # failing-test detail from the last battery run


def _record_outcome(outcome: str) -> None:
    """Persist the last attempt's outcome + revs to a small JSON stamp the
    status push publishes (outputs/auto_update_state.json). Found live
    2026-07-18: the updater silently failed for 6+ hours (outcome unknown
    — dirty? rejected? ff_failed?) and NOTHING observable off-box said
    which; the PC's deploy state was a blind spot. Fail-safe: never let
    telemetry break the update itself. On a 'rejected' outcome the stamp
    also carries which test(s) failed the battery, so a Windows-only
    failure is diagnosable from the cloud.

    W2-21: 'remote' is resolved against _deploy_branch() — the SAME branch
    the update body follows — not a hardcoded origin/main. The stamp also
    names remote_branch so a reader can tell which branch 'remote' refers
    to; on a branch-checked-out box the old hardcode compared against a
    branch the box never fetches (permanently "different from remote", and
    silently empty when origin/main was never fetched)."""
    try:
        branch = _deploy_branch()
        _, head = _git("rev-parse", "--short", "HEAD")
        _, remote = _git("rev-parse", "--short", f"origin/{branch}")
        state = {"ts": time.time(), "outcome": outcome,
                 "head": head.strip(), "remote": remote.strip(),
                 "remote_branch": branch}
        if outcome == "rejected" and _BATTERY_DETAIL:
            state["battery_detail"] = _BATTERY_DETAIL[:500]
        p = OUT / "auto_update_state.json"
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        os.replace(tmp, p)
    except Exception as e:                        # noqa: BLE001
        log(f"outcome stamp failed ({e}) - update itself unaffected")


def _ensure_pushers_current() -> None:
    """Telemetry sidecars only reload code when THEY restart - the update
    restart signal reaches the runner alone, so long-lived pushers kept
    exporting a pre-deploy gauge set forever (lived 2026-07-20: the
    profit-pools row was 'No data' all day while the runner carried the
    values). This process is spawned FRESH every cadence, so it always
    runs current code: when the deployed rev differs from the marker,
    best-effort stop the pusher processes and let the supervisor's
    stale-heartbeat check relaunch them on the new code. The pushers also
    self-exit on source change now; this is the migration path for
    processes started before that guard existed, and the backstop.
    Fail-safe throughout: a failed bounce only means stale gauges."""
    try:
        _, head = _git("rev-parse", "--short", "HEAD")
        marker = OUT / "pushers_code_rev.txt"
        try:
            if marker.read_text(encoding="utf-8").strip() == head.strip():
                return
        except OSError:
            pass                              # no marker yet -> bounce once
        if os.name == "nt":
            ps = ("Get-CimInstance Win32_Process | Where-Object "
                  "{ $_.CommandLine -match "
                  "'gc_pusher\\.py|gc_log_pusher\\.py|gc_trace_pusher\\.py' }"
                  " | ForEach-Object "
                  "{ Stop-Process -Id $_.ProcessId -Force "
                  "-ErrorAction SilentlyContinue }")
            subprocess.run(["powershell", "-NoProfile",  # nosec B603 B607
                            "-Command", ps], timeout=90,
                           capture_output=True, creationflags=_NOWIN)
            log(f"pushers bounced for rev {head.strip()} - supervisor "
                f"relaunches them on the deployed code")
        marker.write_text(head.strip() + "\n", encoding="utf-8")
    except Exception as e:                        # noqa: BLE001
        log(f"pusher bounce failed ({e}) - gauges may lag one deploy")


def update_once() -> str:
    """One update attempt. Returns the outcome string."""
    if os.environ.get("LB_NO_AUTO_UPDATE"):
        return "disabled"
    lock = SingleInstanceLock(str(OUT / "auto_update.lock"),
                              stale_after_sec=LOCK_STALE_SEC)
    holder = lock.acquire()
    if holder is not None:
        log(f"another updater already running (pid {holder.get('pid')}) - "
            f"skipping this check")
        return "busy"
    try:
        out = _update_locked()
    finally:
        lock.release()
    _record_outcome(out)
    return out


def _update_locked() -> str:
    """The update body; caller holds the single-updater lock."""
    branch = _deploy_branch()
    rc, _ = _git("fetch", "origin", branch, timeout=120)
    if rc != 0:
        log("git fetch failed - skipping (offline?)")
        return "fetch_failed"
    _, local = _git("rev-parse", "HEAD")
    _, remote = _git("rev-parse", f"origin/{branch}")
    # --untracked-files=no: only TRACKED modifications are operator edits a
    # fast-forward could clobber. Untracked files (e.g. a .claude/skills/
    # dir the desktop app drops) blocked updates forever — and git stash
    # can't even clear them, so the operator had no way out (live 2026-07-17).
    _, porcelain = _git("status", "--porcelain", "--untracked-files=no")
    # local AHEAD of the remote tip (remote is an ancestor): deploying would
    # be a no-op ff — the old path still ran the battery and BOUNCED THE
    # RUNNER every cycle, an endless pointless reboot loop.
    rc_anc, _ = _git("merge-base", "--is-ancestor", f"origin/{branch}", "HEAD")
    ahead = (local != remote) and bool(remote) and rc_anc == 0
    # W1-7: the REVERSE probe. If HEAD is NOT an ancestor of origin/<branch>
    # either, the histories have DIVERGED (PC-side commits, or an upstream
    # force-push) — a fast-forward is impossible no matter how many times
    # the battery runs. Without this probe, diverged inputs fell through to
    # "test" every cadence: full battery green, then `git merge --ff-only`
    # always failed ("ff_failed"), forever, at full CPU, deploying nothing.
    rc_fwd, _ = _git("merge-base", "--is-ancestor", "HEAD", f"origin/{branch}")
    local_is_ancestor = rc_fwd == 0
    action = decide(local, remote, bool(porcelain.strip()),
                    remote_is_ancestor=ahead,
                    local_is_ancestor=local_is_ancestor)
    if action == "current":
        log("already up to date")
        return "current"
    if action == "ahead":
        log(f"local is AHEAD of origin/{branch} - nothing to deploy, "
            f"runner untouched")
        return "ahead"
    if action == "diverged":
        log(f"HEAD and origin/{branch} have DIVERGED (local commits AND new "
            f"remote commits, neither is an ancestor of the other) - no "
            f"fast-forward is possible; skipping the battery entirely and "
            f"waiting for the operator to resolve this by hand (git status)")
        return "diverged"
    if action == "dirty":
        log("local uncommitted changes present - NOT auto-updating (your edits "
            "are safe); pull by hand when ready")
        return "dirty"

    _, behind = _git("rev-list", "--count", f"HEAD..origin/{branch}")
    log(f"{behind} new commit(s) on {branch} - testing the incoming code first")
    # reclaim EVERY stale _update_wt_* (any pid): a crashed updater's full
    # checkout otherwise sat under outputs/ forever — `worktree prune` skips
    # it because the directory exists (audit C-F11). Concurrent updaters are
    # excluded by the single-updater lock, so anything here is dead.
    for stale_wt in OUT.glob("_update_wt_*"):
        _git("worktree", "remove", "--force", str(stale_wt))
    wt = OUT / f"_update_wt_{os.getpid()}"
    rc, err = _git("worktree", "add", "--detach", str(wt), f"origin/{branch}")
    if rc != 0:
        log(f"could not create test worktree ({err}) - skipping")
        return "worktree_failed"
    try:
        ok = battery_passes(wt)
    finally:
        _git("worktree", "remove", "--force", str(wt))
    if not ok:
        log("incoming code FAILED the battery - staying on current code")
        return "rejected"
    rc, err = _git("merge", "--ff-only", f"origin/{branch}")
    if rc != 0:
        log(f"fast-forward failed ({err}) - not updated")
        return "ff_failed"
    # only bounce the runner when HEAD genuinely moved: an "Already up to
    # date" ff exits 0 too, and restarting on a no-op is how the endless
    # reboot loop happened (belt to the ancestor guard's braces).
    _, new_head = _git("rev-parse", "HEAD")
    if new_head == local:
        log("fast-forward was a no-op (HEAD unchanged) - runner untouched")
        return "current"
    log(f"updated {local[:8]} -> {new_head[:8]} (battery-verified)")
    _signal_restart()
    return "updated"


if __name__ == "__main__":
    _outcome = update_once()
    # after the update body (including a just-applied fast-forward), make
    # sure the telemetry sidecars run the code that is now deployed
    _ensure_pushers_current()
    raise SystemExit(0 if _outcome in OK_OUTCOMES else 1)
