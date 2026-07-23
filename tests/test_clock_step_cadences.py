"""tests/test_clock_step_cadences.py — W2-13: a backwards clock step must
not read every liveness/cadence check as fresh/not-due forever.

Traced: pc_supervisor.py's _fresh, _auto_update_due, _stamp_due, and
_opend_relaunch_due all compute `time.time() - mtime` and compare only
`< threshold`. A future-dated mtime (RTC fast at boot, later corrected by
a time service) makes `time.time() - mtime` negative, which is < any
positive threshold — every one of these predicates reads "fresh"/"not
due" for as long as the clock lags the stamp, silencing remote commands,
status pushes, auto-update, corpus/telemetry sync, and (worst) blocking
the dead-runner relaunch. Fix: age outside [-skew_allowance, threshold)
is stale/due, applied uniformly via a shared helper.
"""
import json
import os
import time

import scripts.pc_supervisor as sup


def _future_mtime(path, seconds_ahead):
    path.write_text("x", encoding="utf-8")
    fut = time.time() + seconds_ahead
    os.utime(path, (fut, fut))


def test_fresh_rejects_future_mtime_heartbeat(tmp_path):
    hb = tmp_path / "status.json"
    _future_mtime(hb, 500.0)          # far beyond any reasonable clock skew
    assert sup._fresh(hb) is False


def test_fresh_rejects_future_mtime_json_key(tmp_path):
    hb = tmp_path / "status.json"
    hb.write_text(json.dumps({"written_at": time.time() + 500.0}),
                  encoding="utf-8")
    assert sup._fresh(hb, key="written_at") is False


def test_auto_update_due_after_backwards_clock_step(tmp_path, monkeypatch):
    monkeypatch.delenv("LB_NO_AUTO_UPDATE", raising=False)
    stamp = tmp_path / ".auto_update_stamp"
    _future_mtime(stamp, 500.0)
    monkeypatch.setattr(sup, "_UPDATE_STAMP", stamp)
    assert sup._auto_update_due() is True


def test_stamp_due_after_backwards_clock_step(tmp_path):
    stamp = tmp_path / ".some_stamp"
    _future_mtime(stamp, 500.0)
    assert sup._stamp_due(stamp, 600.0) is True
    # due path re-touches the stamp to now, same contract as before the fix
    assert abs(stamp.stat().st_mtime - time.time()) < 5.0


def test_opend_relaunch_due_after_backwards_clock_step(tmp_path, monkeypatch):
    stamp = tmp_path / ".opend_launch_stamp"
    _future_mtime(stamp, 500.0)
    monkeypatch.setattr(sup, "_OPEND_STAMP", stamp)
    assert sup._opend_relaunch_due() is True


def test_small_negative_age_within_skew_allowance_stays_fresh(tmp_path):
    # ordinary NTP jitter (a few seconds ahead) is not a clock-step; only a
    # jump beyond the skew allowance should be treated as suspect
    hb = tmp_path / "status.json"
    _future_mtime(hb, 5.0)
    assert sup._fresh(hb) is True
