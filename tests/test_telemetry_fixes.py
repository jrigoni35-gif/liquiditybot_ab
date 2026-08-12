"""Regression tests for two telemetry-correctness fixes revealed by a 38h
paper run:

F1  ml/postmortem.py fabricated a double-digit realized% from a ~$0 notional
    (entry_usd defaulted to 1.0), producing reports whose realized loss
    contradicted their own MAE and fed the monitor phantom causes.
F2  ml/monitor.py request_retrain() throttled only in-memory, so frequent
    restarts (in-memory clock resets to 0) defeated the cooldown and emitted
    ML-032 1670x. The flag file is now the restart-resilient cooldown.
"""
import math

import pytest

import core.audit
from core.audit import AuditTrail
from ml.monitor import ModelMonitor
from ml.postmortem import PostmortemEngine, TradeThesis


def _thesis(pid="p1"):
    return TradeThesis(
        position_id=pid, asset="ETH", symbol="ETH/USD", direction="long",
        entry_ts=1000.0, p_win=0.62, expected_ret_pct=0.18,
        expected_cost_bps=42.0, stop_pct=2.0, target_pct=2.19,
        entry_regime="bull_quiet", entry_liq="liquid", narrative_label="neutral",
        fair_value=2000.0, quote_price=1988.0, model_scored=False)


def _engine(tmp_path):
    return PostmortemEngine({
        "paths_path": str(tmp_path / "trade_paths.csv"),
        "report_dir": str(tmp_path / "pm"),
        "summary_path": str(tmp_path / "pm_summary.csv"),
        "observe_minutes": 0.0})     # finalize immediately in poll()


# --- F1 -------------------------------------------------------------------
def test_nonmaterial_notional_yields_nan_not_fabricated_pct(tmp_path):
    eng = _engine(tmp_path)
    t = _thesis()
    eng.register_entry(t)
    eng.note_fill(t.position_id, 1988.0)
    # sub-dollar PnL on a zero notional: the old code -> -18.47%, now -> NaN
    eng.on_close(t.position_id, realized_net_usd=-0.18, fees_usd=0.25,
                 entry_usd=0.0, stopped_out=False, exit_regime="bull_quiet",
                 exit_liq="liquid", now=2000.0)
    assert math.isnan(t.realized_ret_pct)
    assert t.entry_usd == 0.0


def test_nonmaterial_nonstopped_trade_does_not_trigger_report(tmp_path):
    eng = _engine(tmp_path)
    t = _thesis()
    eng.register_entry(t)
    eng.on_close(t.position_id, realized_net_usd=-0.18, fees_usd=0.25,
                 entry_usd=0.0, stopped_out=False, exit_regime="bull_quiet",
                 exit_liq="liquid", now=2000.0)
    done = eng.poll(now=3000.0)
    # NaN shortfall cannot exceed the trigger bar; not stopped -> no report,
    # and no phantom cause handed to the monitor
    assert done and done[0][0] == ""            # cause is empty
    assert not list((tmp_path / "pm").glob("*.md"))


def test_material_notional_computes_correct_pct(tmp_path):
    eng = _engine(tmp_path)
    t = _thesis()
    eng.register_entry(t)
    eng.on_close(t.position_id, realized_net_usd=-50.0, fees_usd=1.0,
                 entry_usd=1000.0, stopped_out=False, exit_regime="bull_quiet",
                 exit_liq="liquid", now=2000.0)
    assert t.realized_ret_pct == pytest.approx(-5.0)


# --- F2 -------------------------------------------------------------------
def test_retrain_cooldown_survives_restart(tmp_path, monkeypatch):
    # keep audit writes off the repo's real outputs/ dir
    monkeypatch.setattr(core.audit, "_AUDIT",
                        AuditTrail(str(tmp_path / "audit.jsonl")))
    flag = tmp_path / "retrain.flag"
    cfg = {"retrain_cooldown_hours": 12, "retrain_flag_path": str(flag)}

    m1 = ModelMonitor(cfg)
    m1.request_retrain("first reason")
    assert flag.exists()
    assert "first reason" in flag.read_text(encoding="utf-8")

    # simulate a process restart: a fresh monitor with the in-memory clock at 0
    m2 = ModelMonitor(cfg)
    assert m2._last_retrain_request == 0.0
    m2.request_retrain("second reason")
    # the on-disk flag is recent -> the duplicate is suppressed, flag untouched
    assert "first reason" in flag.read_text(encoding="utf-8")
    assert "second reason" not in flag.read_text(encoding="utf-8")


def test_retrain_zero_cooldown_still_fires(tmp_path, monkeypatch):
    # cooldown 0 (used by the smoke suite) must never be throttled
    monkeypatch.setattr(core.audit, "_AUDIT",
                        AuditTrail(str(tmp_path / "audit.jsonl")))
    flag = tmp_path / "retrain0.flag"
    m = ModelMonitor({"retrain_cooldown_hours": 0, "retrain_flag_path": str(flag)})
    m.request_retrain("a")
    assert "a" in flag.read_text(encoding="utf-8")
    m.request_retrain("b")     # cooldown 0 -> re-fires, flag rewritten
    assert "b" in flag.read_text(encoding="utf-8")
