"""tests/test_remote_control.py — the one-bot git command bus.

The security posture IS the feature, so the pins are mostly negative:
arm_live can never ride this channel (whitelist invariant, sender refusal,
poller rejection), stale/future/malformed commands die at validation, and
an id is forwarded exactly once. The transport (fetch/worktree/push) is
exercised end-to-end against throwaway LOCAL repos — no network, and the
real paper-telemetry branch is never touched.
"""
import json
import subprocess
import time
from pathlib import Path

import pytest

import scripts.remote_control as rc
from core.runtime import VALID_COMMANDS


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


@pytest.fixture()
def repos(tmp_path, monkeypatch):
    """A bare 'origin' with a seeded paper-telemetry branch, plus a work
    repo cloned against it (stands in for the PC checkout)."""
    bare = tmp_path / "origin.git"
    _git("init", "--bare", "-b", "main", str(bare), cwd=tmp_path)
    root = tmp_path / "work"
    root.mkdir()
    _git("init", "-b", "main", str(root), cwd=tmp_path)
    _git("config", "user.email", "t@t.t", cwd=root)
    _git("config", "user.name", "t", cwd=root)
    _git("config", "commit.gpgsign", "false", cwd=root)
    (root / "code.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "init", cwd=root)
    _git("remote", "add", "origin", str(bare), cwd=root)
    _git("checkout", "--orphan", "paper-telemetry", cwd=root)
    _git("rm", "-rf", "--cached", ".", cwd=root)
    (root / "README").write_text("telemetry\n", encoding="utf-8")
    (root / "code.txt").unlink()
    _git("add", "README", cwd=root)
    _git("commit", "-m", "seed", cwd=root)
    _git("push", "origin", "paper-telemetry", cwd=root)
    _git("checkout", "main", cwd=root)
    monkeypatch.delenv("LB_NO_REMOTE_CMD", raising=False)
    monkeypatch.delenv("LB_NO_STATUS_PUSH", raising=False)
    # a LIVE runner heartbeat: without it the liveness gate (correctly)
    # retains every queued command instead of forwarding
    (root / "outputs").mkdir(exist_ok=True)
    _fresh_runner(root)
    return root, bare


def _fresh_runner(root: Path) -> None:
    (root / "outputs" / "status.json").write_text(
        json.dumps({"written_at": time.time(), "runner_state": "RUNNING"}),
        encoding="utf-8")


def _branch_file(bare: Path, rel: str) -> str | None:
    p = subprocess.run(["git", "show", f"paper-telemetry:{rel}"],
                       cwd=str(bare), capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


# ---------------- whitelist invariants (the point of the design) ----------

def test_whitelist_is_subset_of_valid_commands():
    assert rc.REMOTE_SAFE_COMMANDS <= VALID_COMMANDS


def test_arm_live_can_never_ride_the_channel():
    assert "arm_live" not in rc.REMOTE_SAFE_COMMANDS


def test_sim_shocks_are_console_only():
    assert not any(c.startswith("sim_") for c in rc.REMOTE_SAFE_COMMANDS)


def test_safe_direction_commands_are_present():
    # de-risking must always be remotely reachable
    assert {"force_dry", "flatten_all", "pause",
            "disarm_live"} <= rc.REMOTE_SAFE_COMMANDS


def test_sender_refuses_non_whitelisted_before_transport(repos):
    root, _ = repos
    with pytest.raises(ValueError, match="not remotely allowed"):
        rc.send_command("arm_live", root=root)


# ---------------- validation table ----------------------------------------

def _payload(**over):
    p = {"id": "abc", "cmd": "pause", "args": {}, "issued_at": 1000.0}
    p.update(over)
    return p


def test_valid_payload_passes():
    assert rc.validate_command(_payload(), "abc", now=1000.0) is None


@pytest.mark.parametrize("payload,fid", [
    (None, "abc"),                                   # not an object
    (_payload(id="other"), "abc"),                   # id/filename mismatch
    (_payload(cmd="arm_live"), "abc"),               # forbidden command
    (_payload(cmd="sim_price_shock"), "abc"),        # console-only command
    (_payload(issued_at=None), "abc"),               # missing timestamp
    (_payload(issued_at=1000.0 - 1801), "abc"),      # stale
    (_payload(issued_at=1000.0 + 301), "abc"),       # future
    (_payload(args="pause"), "abc"),                 # args not an object
])
def test_invalid_payloads_are_rejected(payload, fid):
    reason = rc.validate_command(payload, fid, now=1000.0)
    assert reason is not None and "RC-011" in reason


# ---------------- end-to-end over a local bare repo ------------------------

def test_command_round_trip_exactly_once(repos):
    root, bare = repos
    cid = rc.send_command("pause", root=root)
    out = rc.poll_once(root=root)
    assert out == "applied=1 rejected=0"
    # forwarded into the runner's local control queue
    cmds = list((root / "outputs" / "control").glob("cmd_*.json"))
    assert len(cmds) == 1
    body = json.loads(cmds[0].read_text(encoding="utf-8"))
    assert body["cmd"] == "pause"
    # ledger remembers the id; a second poll forwards nothing
    ledger = json.loads(
        (root / "outputs" / "remote_consumed.json").read_text("utf-8"))
    assert [e["id"] for e in ledger] == [cid]
    assert rc.poll_once(root=root) in ("queue_empty", "applied=0 rejected=0")
    assert len(list((root / "outputs" / "control").glob("cmd_*.json"))) == 1


def test_stale_command_is_rejected_not_forwarded(repos, monkeypatch):
    root, bare = repos
    cid = rc.send_command("pause", root=root)
    future = time.time() + rc.MAX_AGE_SEC + 60
    # keep the runner heartbeat fresh relative to the simulated clock so the
    # liveness gate doesn't mask the expiry path under test
    (root / "outputs" / "status.json").write_text(
        json.dumps({"written_at": future}), encoding="utf-8")
    out = rc.poll_once(root=root, now=future)
    assert out == "applied=0 rejected=1"
    assert not list((root / "outputs" / "control").glob("cmd_*.json"))
    ledger = json.loads(
        (root / "outputs" / "remote_consumed.json").read_text("utf-8"))
    assert ledger[0]["id"] == cid and ledger[0]["result"] == "rejected"


def test_runner_down_retains_queue_for_retry(repos):
    # forwarding into a dead runner would be ledgered 'applied' and then
    # purged by the next boot — the gate must retain the queue instead
    root, _ = repos
    rc.send_command("pause", root=root)
    (root / "outputs" / "status.json").write_text(
        json.dumps({"written_at": time.time() - 900}), encoding="utf-8")
    out = rc.poll_once(root=root)
    assert out.startswith("runner_down")
    assert not list((root / "outputs" / "control").glob("cmd_*.json"))
    assert not (root / "outputs" / "remote_consumed.json").exists()
    # runner comes back -> the same command forwards on the next poll
    _fresh_runner(root)
    assert rc.poll_once(root=root) == "applied=1 rejected=0"
    assert len(list((root / "outputs" / "control").glob("cmd_*.json"))) == 1


def test_stopped_runner_is_not_alive_despite_a_fresh_status(repos):
    """The runner's CLEAN SHUTDOWN writes a final status.json with
    runner_state STOPPED and a FRESH written_at (runner.py:1598-1601), so a
    freshness-only liveness gate reads a just-stopped runner as alive for a
    full 120s. Every deploy bounce opens that window: a command forwarded
    into it is ledgered 'applied' (at-most-once, never retried) and then
    discarded by the next runner's boot purge as predating _PROC_START — an
    acked flatten_all/stop that never executes, the C-F3 class this gate
    exists to prevent."""
    root, _ = repos
    rc.send_command("pause", root=root)
    (root / "outputs" / "status.json").write_text(
        json.dumps({"written_at": time.time(), "runner_state": "STOPPED"}),
        encoding="utf-8")
    out = rc.poll_once(root=root)
    assert out.startswith("runner_down"), \
        "a STOPPED runner with a fresh status must not read as alive"
    assert not list((root / "outputs" / "control").glob("cmd_*.json"))
    assert not (root / "outputs" / "remote_consumed.json").exists()
    # and the command survives for the next runner, exactly like runner_down
    _fresh_runner(root)
    assert rc.poll_once(root=root) == "applied=1 rejected=0"


def test_transient_git_failure_retries_instead_of_rejecting(repos,
                                                            monkeypatch):
    """A failed `git show` is a READ failure, not a malformed command. It
    used to yield payload=None -> "payload is not an object" -> a REJECTED
    entry in the exactly-once ledger, which is permanent: one git hiccup
    (spawn failure, AV scan, contention with the concurrent status-push
    child) silently and irreversibly dropped a live operator command that
    was still valid and fresh on the branch."""
    root, _ = repos
    cid = rc.send_command("pause", root=root)
    _fresh_runner(root)
    real_git = rc._git

    def flaky_git(*args, **kw):
        if args and args[0] == "show":
            return (128, "fatal: unable to read object")
        return real_git(*args, **kw)
    monkeypatch.setattr(rc, "_git", flaky_git)

    out = rc.poll_once(root=root)
    assert "rejected=0" in out, f"transient failure must not reject: {out}"
    ledger_p = root / "outputs" / "remote_consumed.json"
    if ledger_p.exists():
        ids = {e["id"] for e in json.loads(ledger_p.read_text("utf-8"))}
        assert cid not in ids, \
            "a transient read failure must not consume the command id"

    # git recovers -> the SAME command forwards on the next poll
    monkeypatch.setattr(rc, "_git", real_git)
    assert rc.poll_once(root=root) == "applied=1 rejected=0"
    assert len(list((root / "outputs" / "control").glob("cmd_*.json"))) == 1


def test_ledger_written_before_forwarding(repos, monkeypatch):
    # at-most-once: the id must be in the ledger BEFORE ControlChannel.send
    # runs, so a crash inside send can never lead to a double-forward
    root, _ = repos
    rc.send_command("pause", root=root)
    real_send = rc.ControlChannel.send

    def crashing_send(self, cmd, args=None):
        ledger = json.loads(
            (root / "outputs" / "remote_consumed.json").read_text("utf-8"))
        assert ledger and ledger[-1]["result"] == "forwarding"
        raise RuntimeError("simulated crash mid-send")
    monkeypatch.setattr(rc.ControlChannel, "send", crashing_send)
    with pytest.raises(RuntimeError, match="simulated crash"):
        rc.poll_once(root=root)
    monkeypatch.setattr(rc.ControlChannel, "send", real_send)
    # the id is consumed: the command is NOT retried (at-most-once), and
    # the honest 'forwarding' state survives for the pc_status acks
    assert rc.poll_once(root=root) in ("queue_empty", "applied=0 rejected=0")
    ledger = json.loads(
        (root / "outputs" / "remote_consumed.json").read_text("utf-8"))
    assert ledger[-1]["result"] == "forwarding"


def test_concurrent_poller_is_refused(repos):
    root, _ = repos
    lock = rc.SingleInstanceLock(
        str(root / "outputs" / "remote_poll.lock"), stale_after_sec=300.0)
    assert lock.acquire() is None            # peer holds the poll lock
    try:
        import os
        # a DIFFERENT pid must be refused; same-pid reclaim is by design,
        # so fake the peer's pid in the lockfile
        raw = json.loads(
            (root / "outputs" / "remote_poll.lock").read_text("utf-8"))
        raw["pid"] = os.getpid() + 1
        (root / "outputs" / "remote_poll.lock").write_text(
            json.dumps(raw), encoding="utf-8")
        assert rc.poll_once(root=root) == "busy"
    finally:
        (root / "outputs" / "remote_poll.lock").unlink()


def test_kill_switch_disables_polling(repos, monkeypatch):
    root, _ = repos
    rc.send_command("pause", root=root)
    monkeypatch.setenv("LB_NO_REMOTE_CMD", "1")
    assert rc.poll_once(root=root) == "disabled"
    assert not list((root / "outputs" / "control").glob("cmd_*.json"))


def test_status_push_publishes_and_gc_consumed_queue(repos):
    root, bare = repos
    (root / "outputs").mkdir(exist_ok=True)
    (root / "outputs" / "status.json").write_text(
        json.dumps({"equity": 5000.0, "runner_state": "RUNNING",
                    "written_at": time.time()}), encoding="utf-8")
    cid = rc.send_command("snapshot", root=root)
    assert rc.poll_once(root=root) == "applied=1 rejected=0"
    assert rc.push_pc_status(root=root) == "pushed"
    env = json.loads(_branch_file(bare, "control/pc_status.json"))
    assert env["status"]["equity"] == 5000.0
    assert env["remote_commands"][-1]["id"] == cid
    # the consumed queue file was garbage-collected in the same commit
    assert _branch_file(bare, f"control/queue/{cid}.json") is None
    # era-4 accrual travels in the envelope (2026-08-19): no fills.csv on
    # this box -> accrual_n None, target still published, push unharmed
    assert env["era4"]["target"] == 50
    assert env["era4"]["signed_continue_n"] == 100   # signed table, 1D/3A bound
    assert env["era4"]["accrual_n"] is None


def test_status_push_counts_era4_accrual_from_fills(repos):
    root, bare = repos
    (root / "outputs").mkdir(exist_ok=True)
    (root / "outputs" / "status.json").write_text(
        json.dumps({"equity": 1.0, "written_at": time.time()}),
        encoding="utf-8")
    # one fully-closed, entry-opened era-4 round trip in the REAL ledger
    # schema (core/fill_ledger.COLS), closing after the epoch cut
    (root / "outputs" / "fills.csv").write_text(
        "ts,order_id,position_id,purpose,symbol,side,ordertype,post_only,"
        "attempt,fill_size,fill_price,arrival_ref,slip_bps,fees_delta_usd,"
        "remaining,reason,exec_era\n"
        "1786900000,o1,pX,entry,ETH/USD,buy,limit,1,1,1.0,10.0,10.0,0.0,"
        "0.01,0.0,fill,7-e7d5ca1a\n"
        "1786903600,o2,pX,exit,ETH/USD,sell,limit,1,1,1.0,10.5,10.5,0.0,"
        "0.01,0.0,fill,7-e7d5ca1a\n",
        encoding="utf-8")
    assert rc.push_pc_status(root=root) == "pushed"
    env = json.loads(_branch_file(bare, "control/pc_status.json"))
    assert env["era4"]["accrual_n"] == 1
    assert env["era4"]["target"] == 50


def test_status_push_survives_already_gcd_consumed_delete(repos):
    # regression (2026-07-18): _publish staged `git add -A -- <pathspecs>`
    # including consumed-queue deletes. The consumed LEDGER keeps listing an
    # id after its queue file was GC'd on a prior push, so the delete
    # pathspec matched no file -> `git add` aborts (rc=128), nothing stages,
    # and push_pc_status returned "no_change" forever — the pc_status channel
    # went silent on the live PC. A push must survive an absent consumed
    # delete and still publish changed status.
    root, bare = repos
    (root / "outputs").mkdir(exist_ok=True)
    (root / "outputs" / "status.json").write_text(
        json.dumps({"equity": 5000.0, "written_at": time.time()}),
        encoding="utf-8")
    cid = rc.send_command("snapshot", root=root)
    assert rc.poll_once(root=root) == "applied=1 rejected=0"
    assert rc.push_pc_status(root=root) == "pushed"        # GCs the queue file
    assert _branch_file(bare, f"control/queue/{cid}.json") is None
    # second push: the consumed ledger STILL lists cid, so its (now-absent)
    # queue file is in `deletes` — must not wedge the push
    (root / "outputs" / "status.json").write_text(
        json.dumps({"equity": 5123.0, "written_at": time.time()}),
        encoding="utf-8")
    assert rc.push_pc_status(root=root) == "pushed"
    env = json.loads(_branch_file(bare, "control/pc_status.json"))
    assert env["status"]["equity"] == 5123.0               # change published


def test_status_push_without_status_is_a_noop(repos):
    # W2-14 re-decision (2026-07-23): this git-plane noop is KEPT — with no
    # status file there is nothing to publish, and the pc_status envelope's
    # pushed_at age is this plane's own staleness signal. The METRICS plane
    # (gc_pusher.collect) is where missing-status is loud: it pushes the
    # alarm batch with status_missing=1 (test_data_layer_batch.py). Do not
    # re-flag this pin as a blackout — the two planes split deliberately.
    root, _ = repos
    (root / "outputs" / "status.json").unlink()
    assert rc.push_pc_status(root=root) == "no_status"


def test_publish_leaves_caller_checkout_untouched(repos):
    root, _ = repos
    rc.send_command("pause", root=root)
    head = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                          cwd=str(root), check=True, capture_output=True,
                          text=True).stdout.strip()
    assert head == "main"
    wl = subprocess.run(["git", "worktree", "list"], cwd=str(root),
                        check=True, capture_output=True, text=True).stdout
    assert wl.count("\n") == 1


def test_status_push_carries_deploy_observable(repos):
    """2026-07-18: the PC's updater failed silently for 6+ hours and no
    off-box channel said which outcome it kept hitting. The envelope now
    carries the box's HEAD and the last auto-update outcome stamp."""
    root, bare = repos
    (root / "outputs").mkdir(exist_ok=True)
    (root / "outputs" / "status.json").write_text(
        json.dumps({"equity": 5000.0, "written_at": time.time()}),
        encoding="utf-8")
    (root / "outputs" / "auto_update_state.json").write_text(
        json.dumps({"ts": 123.0, "outcome": "dirty", "head": "aaa",
                    "remote": "bbb"}), encoding="utf-8")
    assert rc.push_pc_status(root=root) == "pushed"
    env = json.loads(_branch_file(bare, "control/pc_status.json"))
    assert env["deploy"]["auto_update"]["outcome"] == "dirty"
    assert env["deploy"]["head"]                  # real rev-parse of root


def test_git_redacts_credentials_in_returned_stderr(monkeypatch, tmp_path):
    """W2-25: _git falls back to stderr when stdout is empty, and callers
    log that text verbatim (fetch_failed / worktree_failed / commit_failed
    / push_failed). git occasionally echoes the remote URL it tried into
    stderr, which can carry an embedded credential (https://user:token@
    host/...) straight into a local gitignored log. The token must never
    reach the returned/logged text."""
    class _FakeCompleted:
        returncode = 128
        stdout = ""
        stderr = ("fatal: unable to access "
                  "'https://alice:sekrit-token-xyz@github.com/org/repo.git/'"
                  ": The requested URL returned error: 403")

    monkeypatch.setattr(rc.subprocess, "run",
                        lambda *a, **k: _FakeCompleted())
    code, out = rc._git("fetch", "origin", "main", cwd=tmp_path)
    assert code == 128
    assert "sekrit-token-xyz" not in out
    assert "alice" not in out
    assert "https://***@github.com/org/repo.git" in out


# ---- log containment (2026-07-31) ------------------------------------------
# Every entry point here takes `root` so the suite can drive a throwaway
# tree, but _log wrote to the module-level OUT unconditionally — so these
# tests appended their fixtures to the operator's REAL control-plane log:
# 356 copies of "runner down - retaining N queued command(s)" (reading as a
# chronically dead runner) and command ids paired at the same second, which
# a 120s poll can never produce. Same defect and same fix as
# scripts/corpus_sync.py's _log.
def test_log_honors_root_and_never_touches_the_repo_log(tmp_path):
    real = rc.OUT / "remote_control.log"
    before = real.read_text(encoding="utf-8") if real.exists() else None
    rc._log("scoped probe", root=tmp_path)
    assert "scoped probe" in (tmp_path / "outputs" / "remote_control.log"
                              ).read_text(encoding="utf-8")
    after = real.read_text(encoding="utf-8") if real.exists() else None
    assert after == before, "test logging leaked into the production log"


def test_runner_down_note_lands_in_the_caller_root(repos, tmp_path,
                                                   monkeypatch):
    """The whole poll path must be root-scoped, not just _log: the
    runner-down branch is the exact line that flooded the real log.

    rc.OUT IS REDIRECTED TO A TEMP DIR, and that is load-bearing. This test
    previously read the LIVE outputs/remote_control.log as its "production
    log" control, then asserted it was unchanged across the poll. But
    pc_supervisor spawns remote_control.py --poll every REMOTE_CMD_SEC=120s
    against that very file, so the assertion raced the running bot and failed
    whenever an ~8 minute suite straddled a write (observed 2026-08-23: log
    mtime 16:57:12 on a 120s cadence, one failure in 3991). Reading live
    mutable state as a fixture is the defect - USAGE.md rule (c). The INTENT
    (poll_once must not write into rc.OUT) is preserved exactly; only the
    file it is checked against is now one nothing else can touch."""
    root, _ = repos
    fake_out = tmp_path / "prod_outputs"
    fake_out.mkdir()
    monkeypatch.setattr(rc, "OUT", fake_out)
    rc.send_command("pause", root=root)
    (root / "outputs" / "status.json").write_text(
        json.dumps({"written_at": time.time() - 900}), encoding="utf-8")
    real = rc.OUT / "remote_control.log"
    before = real.read_text(encoding="utf-8") if real.exists() else None
    assert rc.poll_once(root=root).startswith("runner_down")
    after = real.read_text(encoding="utf-8") if real.exists() else None
    assert after == before, "poll_once leaked into the production log"
    assert "runner down" in (root / "outputs" / "remote_control.log"
                             ).read_text(encoding="utf-8")
