"""
Regression for scripts/checkin.py, the unattended 0/6/12/24h supervised
check-in. Verifies the anomaly detectors fire on the conditions they're
meant to catch (stale runner heartbeat, broken audit chain, unexpected
live mode) and that pause-on-anomaly only fires the ControlChannel
"pause" command - never touches dry_run, never stops/flattens - and only
when the runner is actually alive to receive it.
"""
import json
import time

from core.audit import AuditTrail
from core.codes import Code
import scripts.checkin as checkin_mod
from scripts.checkin import run_checkin


def _seed_valid_chain(outputs_dir):
    trail = AuditTrail(str(outputs_dir / "audit.jsonl"))
    trail.log("startup", Code.FW_FAULT_DEGRADED, "config coherent")


def _seed_equity(outputs_dir, equity=25010.0):
    now = time.time()
    (outputs_dir / "equity.csv").write_text(
        "ts,equity,daily_pnl\n"
        f"{now - 300:.0f},25000.0,0.0\n"
        f"{now:.0f},{equity},{equity - 25000.0:.2f}\n",
        encoding="utf-8")


def _seed_status(outputs_dir, mode="DRY_RUN", runner_state="RUNNING", equity=25000.0):
    (outputs_dir / "status.json").write_text(
        json.dumps({"mode": mode, "runner_state": runner_state, "equity": equity}),
        encoding="utf-8")


def _seed_lock(outputs_dir, heartbeat_age=0.0, pid=1234):
    (outputs_dir / "runner.lock").write_text(
        json.dumps({"pid": pid, "heartbeat": time.time() - heartbeat_age}),
        encoding="utf-8")


def test_clean_state_no_anomaly_no_pause(tmp_path):
    _seed_valid_chain(tmp_path)
    _seed_equity(tmp_path)
    _seed_status(tmp_path)
    _seed_lock(tmp_path)

    report = run_checkin("0h", str(tmp_path), str(tmp_path / "nonexistent_config.json"))

    assert report["anomaly"] is False
    assert report["paused_bot"] is False
    assert report["audit_chain_ok"] is True
    assert not list((tmp_path / "control").glob("cmd_*.json"))


def test_stale_heartbeat_flags_critical_but_cannot_pause_dead_runner(tmp_path):
    _seed_valid_chain(tmp_path)
    _seed_status(tmp_path)
    _seed_lock(tmp_path, heartbeat_age=999.0)

    report = run_checkin("6h", str(tmp_path), str(tmp_path / "nonexistent_config.json"))

    assert report["anomaly"] is True
    assert report["process_liveness"]["alive"] is False
    # can't pause a runner that isn't there to consume the command
    assert report["paused_bot"] is False
    assert not (tmp_path / "control").exists() or \
        not list((tmp_path / "control").glob("cmd_*.json"))


def test_unexpected_live_mode_pauses_alive_runner(tmp_path):
    _seed_valid_chain(tmp_path)
    _seed_status(tmp_path, mode="LIVE")
    _seed_lock(tmp_path, heartbeat_age=0.0)

    report = run_checkin("12h", str(tmp_path), str(tmp_path / "nonexistent_config.json"))

    assert report["anomaly"] is True
    assert any("LIVE" in c for c in report["critical"])
    assert report["paused_bot"] is True
    cmds = list((tmp_path / "control").glob("cmd_*.json"))
    assert len(cmds) == 1
    sent = json.loads(cmds[0].read_text(encoding="utf-8"))
    assert sent["cmd"] == "pause"


def test_broken_audit_chain_is_critical(tmp_path):
    # audit.jsonl deliberately absent -> session_digest reports chain_ok=False
    _seed_status(tmp_path)
    _seed_lock(tmp_path)

    report = run_checkin("24h", str(tmp_path), str(tmp_path / "nonexistent_config.json"))

    assert report["audit_chain_ok"] is False
    assert report["anomaly"] is True
    assert report["paused_bot"] is True


def test_warn_severity_digest_verdict_surfaces_as_warning_not_dropped(tmp_path, monkeypatch):
    # session_digest uses "warn" (not "warning") for its non-fatal severity;
    # regression for a string-mismatch bug that silently dropped every
    # warn-level verdict (e.g. SD-004 audit noise) instead of surfacing it.
    _seed_valid_chain(tmp_path)
    _seed_equity(tmp_path)
    _seed_status(tmp_path)
    _seed_lock(tmp_path)

    stub_digest = {
        "verdict": "SD-004 audit trail dominated by one code",
        "diagnostics": [{"id": "SD-004", "severity": "warn",
                         "title": "audit trail dominated by one code",
                         "detail": "stub"}],
        "audit": {"chain_ok": True},
        "model": {"monitor_level": 0},
        "events": {"feed_error_events": 0},
        "pnl": {"starting_capital": 25000.0, "equity_end": 25010.0},
    }
    monkeypatch.setattr(checkin_mod, "write_digest", lambda *a, **kw: stub_digest)

    report = run_checkin("warntest", str(tmp_path), str(tmp_path / "nonexistent_config.json"))

    assert report["anomaly"] is False
    assert report["paused_bot"] is False
    assert any("SD-004" in w for w in report["warnings"])


def test_report_files_written(tmp_path):
    _seed_valid_chain(tmp_path)
    _seed_status(tmp_path)
    _seed_lock(tmp_path)

    run_checkin("0h", str(tmp_path), str(tmp_path / "nonexistent_config.json"))

    checkin_dir = tmp_path / "checkin"
    assert (checkin_dir / "checkin_0h.json").exists()
    assert (checkin_dir / "checkin_0h.md").exists()
    log_lines = (checkin_dir / "checkin_log.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(log_lines) == 1
