"""Task #51 deferred-audit fix batch — the five verified-live findings.

MP-5   side-aware submit rounding: a buy price must never round UP (post-only
       reject / unintended cross), a sell price never DOWN, and the submitted
       volume must never round past the approved size (oversell).
EX-8   _bars_in_trade was the LAST wall-clock read in the exit path: under
       replay, trail time-tightening depended on when the replay RAN. The
       engine's injected `now` must reach it end-to-end.
LP-6   the CLI retrain's deploy gate must pass n_oof so the deploy_min_oof
       evidence floor binds exactly as it does on the runner's auto path.
C-F10  the supervisor's four git sidecars share period divisors and all
       default-due at boot — absent stamps are seeded with phase offsets so
       the top-of-the-hour thundering herd cannot form.
DL-6   the status pusher stamps staleness (age + flag) so a frozen bot can
       never masquerade as live under a fresh pushed_at.
"""
import json
import time
from datetime import datetime, timedelta, timezone

from execution.order_manager import OrderManager
from risk.profit_tiers import ProfitTierEngine


def _om():
    om = OrderManager.__new__(OrderManager)      # rounding needs pair_meta only
    om.pair_meta = {"XETHZUSD": {"price_decimals": 2, "lot_decimals": 4}}
    return om


# ---- MP-5: side-aware rounding ---------------------------------------------

def test_buy_price_floors_sell_price_ceils():
    om = _om()
    assert om._fmt_price("XETHZUSD", 1937.129, side="buy") == "1937.12"
    assert om._fmt_price("XETHZUSD", 1937.121, side="sell") == "1937.13"
    # exact values pass through untouched on both sides
    assert om._fmt_price("XETHZUSD", 1937.12, side="buy") == "1937.12"
    assert om._fmt_price("XETHZUSD", 1937.12, side="sell") == "1937.12"


def test_volume_always_floors_never_oversubmits():
    om = _om()
    # round-half-even would have sent 0.1235 (> approved); floor sends 0.1234
    assert om._fmt_volume("XETHZUSD", 0.12345) == "0.1234"
    assert om._fmt_volume("XETHZUSD", 0.12349999) == "0.1234"
    assert om._fmt_volume("XETHZUSD", 0.1234) == "0.1234"    # exact: no-op


def test_sideless_price_keeps_legacy_rounding():
    om = _om()
    assert om._fmt_price("XETHZUSD", 1937.125) == f"{1937.125:.2f}"


# ---- EX-8: injected clock reaches the trail time-tightening -----------------

def _pos(age_hours: float, base_ts: float):
    class P:
        symbol = "ETH/USD"
        direction = "long"
        opened_at = datetime.fromtimestamp(base_ts, tz=timezone.utc) \
            - timedelta(hours=age_hours)
        tier_closed = 0
        high_water = 0.0
        confidence = 0.0
    return P()


def test_bars_in_trade_uses_injected_now_not_wall_clock():
    eng = ProfitTierEngine({})
    base = 1_700_000_000.0                       # frozen replay clock
    p = _pos(age_hours=10.0, base_ts=base)
    bars = eng._bars_in_trade(p, now=base)
    assert abs(bars - (10.0 * 60.0 / 5.0)) < 1e-6   # 120 bars, exactly
    # same position, same injected now, evaluated "later" in wall time —
    # the answer must not drift (this is the determinism contract)
    assert eng._bars_in_trade(p, now=base) == bars
    # and a DIFFERENT injected now moves it deterministically
    assert abs(eng._bars_in_trade(p, now=base + 3600.0) - (bars + 12.0)) < 1e-6


def test_bars_in_trade_wall_clock_fallback_still_works():
    eng = ProfitTierEngine({})
    p = _pos(age_hours=1.0, base_ts=time.time())
    assert abs(eng._bars_in_trade(p) - 12.0) < 0.1   # legacy callers safe


# ---- LP-6: CLI deploy gate carries the OOF evidence floor -------------------

def test_cli_deploy_gate_passes_n_oof():
    src = open("scripts/train_meta.py", encoding="utf-8").read()
    assert "should_deploy(challenger_brier, n_oof=n_oof)" in src
    assert "n_oof=int(len(oof_cal))" in src      # caller supplies the count


# ---- C-F10: sidecar stamp stagger ------------------------------------------

def test_stagger_seeds_absent_stamps_with_phase_offsets(monkeypatch, tmp_path):
    import scripts.pc_supervisor as sup
    monkeypatch.setattr(sup, "OUT", tmp_path)
    for name in ("_REMOTE_CMD_STAMP", "_STATUS_PUSH_STAMP",
                 "_CORPUS_SYNC_STAMP", "_TELEM_BACKUP_STAMP"):
        monkeypatch.setattr(sup, name, tmp_path / getattr(sup, name).name)
    sup._stagger_stamps()
    now = time.time()
    ages = {name: now - getattr(sup, name).stat().st_mtime
            for name in ("_REMOTE_CMD_STAMP", "_STATUS_PUSH_STAMP",
                         "_CORPUS_SYNC_STAMP", "_TELEM_BACKUP_STAMP")}
    # remote-cmd: due immediately (age ~= full period)
    assert ages["_REMOTE_CMD_STAMP"] >= sup.REMOTE_CMD_SEC - 5
    # status push: first due after ~half its period
    assert abs(ages["_STATUS_PUSH_STAMP"] - sup.STATUS_PUSH_SEC * 0.5) < 5
    # the two hourly jobs land half a period apart — never the same tick
    gap = abs((sup.CORPUS_SYNC_SEC - ages["_CORPUS_SYNC_STAMP"])
              - (sup.TELEM_BACKUP_SEC - ages["_TELEM_BACKUP_STAMP"]))
    assert gap > sup.CORPUS_SYNC_SEC * 0.25


def test_stagger_never_touches_existing_stamps(monkeypatch, tmp_path):
    import scripts.pc_supervisor as sup
    monkeypatch.setattr(sup, "OUT", tmp_path)
    stamp = tmp_path / ".remote_cmd_stamp"
    stamp.touch()
    old = time.time() - 42.0
    import os
    os.utime(stamp, (old, old))
    monkeypatch.setattr(sup, "_REMOTE_CMD_STAMP", stamp)
    for name in ("_STATUS_PUSH_STAMP", "_CORPUS_SYNC_STAMP",
                 "_TELEM_BACKUP_STAMP"):
        monkeypatch.setattr(sup, name, tmp_path / getattr(sup, name).name)
    sup._stagger_stamps()
    assert abs(stamp.stat().st_mtime - old) < 1.0    # untouched


# ---- DL-6: staleness stamped on the status push -----------------------------

def test_push_status_flags_stale_and_fresh(monkeypatch, tmp_path):
    import scripts.remote_control as rc
    captured = {}

    def _fake_publish(root, writes, deletes):
        captured.update(writes)
        return "pushed"
    monkeypatch.setattr(rc, "_publish", _fake_publish)
    monkeypatch.setattr(rc, "_load_consumed", lambda root: [])
    monkeypatch.setattr(rc, "_git", lambda *a, **k: (1, ""))
    out = tmp_path / "outputs"
    out.mkdir()

    (out / "status.json").write_text(json.dumps(
        {"written_at": time.time() - 1200.0, "runner_state": "RUNNING"}),
        encoding="utf-8")
    assert rc.push_pc_status(tmp_path) == "pushed"
    env = json.loads(captured[rc.STATUS_PATH])
    assert env["status_stale"] is True
    assert env["status_age_sec"] > 1000

    (out / "status.json").write_text(json.dumps(
        {"written_at": time.time() - 5.0, "runner_state": "RUNNING"}),
        encoding="utf-8")
    rc.push_pc_status(tmp_path)
    env = json.loads(captured[rc.STATUS_PATH])
    assert env["status_stale"] is False
    assert env["status_age_sec"] < 60
