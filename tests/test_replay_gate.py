"""Replay-vs-live standing gate (core/replay_gate.py).

The gate makes the record/replay harness a truth-teller the battery can trust:
  * DETERMINISM (hard) — replaying one recording twice must produce identical
    P&L/fills; the harness's whole promise. A regression that changes engine
    behavior on recorded frames turns this red.
  * RECONCILIATION (conditional) — when a recording carries a flat-start
    sidecar, replay's realized-P&L must match the live session's delta within
    tolerance. It hard-fails ONLY on a self-contained recording (every input
    recorded); otherwise it WARNs, because unrecorded sentiment/webdata feeds
    legitimately move live P&L away from replay.
  * SKIP-safe — no recordings (fresh clone / cloud snapshot) => the gate is
    dormant and never reddens the battery.

Core logic is pure with an injected replay_fn, so these run without the engine.
"""
import os

from core.replay_gate import (
    GateResult,
    ReconResult,
    determinism_ok,
    discover_recordings,
    reconcile,
    run_gate,
)
from data.recording import pnl_snapshot, session_sink, update_sidecar


def _make_recording(d, ts, *, end_pnl=None, start_pnl=0.0, start_positions=0,
                    self_contained=True):
    sink = session_sink(str(d), ts)
    sink.write_text("{}\n", encoding="utf-8")
    os.utime(sink, (ts, ts))
    if end_pnl is not None:
        st = pnl_snapshot(start_pnl, 5000.0, start_positions, ts)
        st["self_contained"] = self_contained
        update_sidecar(sink, "start", st)
        update_sidecar(sink, "end",
                       pnl_snapshot(end_pnl, 5000.0 + end_pnl, 0, ts + 3600))
    return sink


_SUMMARY = {"realized_pnl": -3.40, "final_equity": 4996.60,
            "entries_filled": 1, "fees": 0.20, "exit_orders": 1,
            "labeled_rows": 1}


# ---------------------------------------------------------------- discovery
def test_discover_returns_newest_first_and_empty_when_none(tmp_path):
    assert discover_recordings(str(tmp_path)) == []
    _make_recording(tmp_path, 1000)
    _make_recording(tmp_path, 2000)
    recs = discover_recordings(str(tmp_path))
    assert recs[0].name == "session_2000.jsonl"    # newest first


# ------------------------------------------------------------- determinism
def test_determinism_ok_detects_divergence():
    ok, _ = determinism_ok(dict(_SUMMARY), dict(_SUMMARY))
    assert ok
    bad = dict(_SUMMARY)
    bad["realized_pnl"] = -9.99
    ok2, msg = determinism_ok(dict(_SUMMARY), bad)
    assert not ok2 and "realized_pnl" in msg


# ----------------------------------------------------------- reconciliation
def _sidecar(start_pnl, end_pnl, positions=0, self_contained=True):
    return {"start": {"realized_pnl": start_pnl, "open_positions": positions,
                      "self_contained": self_contained},
            "end": {"realized_pnl": end_pnl}}


def test_reconcile_ok_within_tolerance():
    r = reconcile({"realized_pnl": -3.40}, _sidecar(0.0, -3.41))
    assert isinstance(r, ReconResult) and r.status == "OK"


def test_reconcile_fails_on_self_contained_mismatch():
    r = reconcile({"realized_pnl": -3.40}, _sidecar(0.0, -9.0, self_contained=True))
    assert r.status == "FAIL"


def test_reconcile_warns_when_not_self_contained():
    r = reconcile({"realized_pnl": -3.40}, _sidecar(0.0, -9.0, self_contained=False))
    assert r.status == "WARN"


def test_reconcile_skips_non_flat_start():
    r = reconcile({"realized_pnl": -3.40}, _sidecar(0.0, -3.41, positions=2))
    assert r.status == "SKIP"


def test_reconcile_skips_without_sidecar():
    assert reconcile({"realized_pnl": 0.0}, None).status == "SKIP"


# ----------------------------------------------------------------- run_gate
def test_run_gate_skips_when_no_recordings(tmp_path):
    res = run_gate(str(tmp_path), replay_fn=lambda p: {})
    assert isinstance(res, GateResult)
    assert res.status == "SKIP" and res.recordings == 0


def test_run_gate_passes_on_deterministic_replay(tmp_path):
    _make_recording(tmp_path, 1000, end_pnl=-3.41, self_contained=True)
    res = run_gate(str(tmp_path), replay_fn=lambda p: dict(_SUMMARY))
    assert res.status == "PASS"


def test_run_gate_fails_on_nondeterministic_replay(tmp_path):
    _make_recording(tmp_path, 1000, end_pnl=-3.41)
    calls = {"n": 0}

    def flaky(_path):
        calls["n"] += 1
        s = dict(_SUMMARY)
        s["realized_pnl"] = -3.40 if calls["n"] == 1 else -9.99
        return s

    res = run_gate(str(tmp_path), replay_fn=flaky)
    assert res.status == "FAIL"


def test_run_gate_fails_on_self_contained_reconciliation_mismatch(tmp_path):
    # deterministic replay, but replay P&L disagrees with a self-contained live
    _make_recording(tmp_path, 1000, end_pnl=-9.0, self_contained=True)
    res = run_gate(str(tmp_path), replay_fn=lambda p: dict(_SUMMARY))
    assert res.status == "FAIL"
