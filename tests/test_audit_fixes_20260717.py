"""tests/test_audit_fixes_20260717.py — pins for the advanced-protocol
debugging session's verified findings (2026-07-17 five-agent audit).

Each test names the finding it kills. These are regression pins: the bug
classes were CONFIRMED live, so a future edit that re-introduces one must
fail loudly here.
"""
import json
import time
from datetime import datetime, timezone

import pytest

from core.persistence import position_from_dict, position_to_dict
from core.state import PortfolioState, Position


def _pos(**over):
    base = dict(position_id="p1", symbol="ETH/USD", direction="long",
                entry_price=100.0, size=1.0, original_size=1.0,
                opened_at=datetime.now(timezone.utc))
    base.update(over)
    return Position(**base)


# ---------------- MP-2: entry-leg fees are real cash --------------------

def test_entry_fee_debits_cash():
    st = PortfolioState(starting_capital=1000.0)
    cash0 = st.cash_balance
    st.record_entry_fee(0.25)
    assert st.cash_balance == pytest.approx(cash0 - 0.25)
    # equity reflects the fee immediately (no open-position marks needed)
    assert st.total_equity() == pytest.approx(cash0 + st.savings_balance
                                              - 0.25)


def test_entry_fees_survive_snapshot_round_trip():
    p = _pos(entry_fees_usd=0.37, fees_paid_usd=0.61)
    q = position_from_dict(position_to_dict(p))
    assert q.entry_fees_usd == pytest.approx(0.37)
    assert q.fees_paid_usd == pytest.approx(0.61)


def test_legacy_snapshot_without_entry_fees_defaults_to_zero():
    d = position_to_dict(_pos())
    d.pop("entry_fees_usd")
    assert position_from_dict(d).entry_fees_usd == 0.0


# ---------------- MP-1: fills book at SEGMENT price ---------------------

def test_live_partial_fill_event_carries_segment_price():
    from execution.order_manager import EPS, ManagedOrder, OrderManager
    om = OrderManager.__new__(OrderManager)
    om.maker_fee_bps, om.taker_fee_bps = 16.0, 26.0
    om.timeout_sec = 9999.0
    om.maker_fills = om.taker_fills = 0
    om.maker_notional_usd = om.taker_notional_usd = 0.0
    from collections import deque
    om._slip_bps = deque(maxlen=200)
    om._transition = lambda *a, **k: None
    o = ManagedOrder(order_id="o1", txid="T1", asset="ETH", pair="ETHUSD",
                     symbol="ETH/USD", side="buy", price=100.0, size=2.0)
    o.filled, o.avg_price = 1.0, 100.0     # first segment 1.0 @ 100
    # second segment 1.0 @ 110 -> venue reports cumulative avg 105
    batch = {"T1": {"vol_exec": "2.0", "price": "105.0", "status": "open"}}
    events = om._poll_live(o, now=time.time(), batch=batch)
    fills = [e for e in events if e.fill_size > EPS]
    assert len(fills) == 1
    # booked at THIS segment's 110, not the 105 blend (audit MP-1)
    assert fills[0].fill_price == pytest.approx(110.0)
    # MP-3: the fee accrues on the segment notional too
    assert o.fees_usd == pytest.approx(1.0 * 110.0 * 16.0 / 1e4)


# ---------------- MP-9: sigma == 0 gets the floor, not the boost --------

def test_zero_sigma_vol_scalar_is_min():
    from risk.position_sizer import PositionSizer
    ps = PositionSizer.__new__(PositionSizer)
    ps.vol_target_ann_pct, ps.vol_sigma_floor_pct = 35.0, 5.0
    ps.vol_scalar_min, ps.vol_scalar_max = 0.3, 1.5
    assert ps._vol_scalar(0.0) == 0.3
    assert ps._vol_scalar(float("nan")) == 0.3
    assert ps._vol_scalar(-3.0) == 0.3
    assert ps._vol_scalar(35.0) == 1.0          # at target: full size


# ---------------- EX-1: BE floor arms only once price cleared it --------

def _tier_engine():
    # ProfitTierEngine takes the profit_taking SUBDICT directly
    from risk.profit_tiers import ProfitTierEngine
    return ProfitTierEngine({
        "enabled": True, "be_after_tier": 1, "est_fee_bps": 40.0,
        "be_buffer_bps": 6.0,
        "trailing_stop": {"enabled": False},
    })


def test_be_floor_not_armed_below_buffer():
    eng = _tier_engine()
    p = _pos(tier_closed=1)
    # +0.70% — tier 1 fired below the 86bps buffer: the floor must NOT
    # install above the market and instant-close the runner (audit EX-1)
    assert eng._exit_floor_hit(p, 100.70, sigma_bar_pct=0.1) is False
    assert p.trailing_stop_price is None


def test_be_floor_arms_after_clearing_and_holds_on_pullback():
    eng = _tier_engine()
    p = _pos(tier_closed=1)
    be_px = 100.0 * (1.0 + (2 * 40.0 + 6.0) / 1e4)          # 100.86
    assert eng._exit_floor_hit(p, 101.50, sigma_bar_pct=0.1) is False
    assert p.trailing_stop_price == pytest.approx(be_px)     # armed clear
    # pullback THROUGH the floor -> exit fires AT the floor, as designed
    assert eng._exit_floor_hit(p, 100.60, sigma_bar_pct=0.1) is True


def test_be_floor_short_side_mirrors():
    eng = _tier_engine()
    p = _pos(direction="short", tier_closed=1)
    assert eng._exit_floor_hit(p, 99.40, sigma_bar_pct=0.1) is False
    assert p.trailing_stop_price is None                     # not cleared
    assert eng._exit_floor_hit(p, 98.50, sigma_bar_pct=0.1) is False
    assert p.trailing_stop_price == pytest.approx(
        100.0 * (1.0 - 0.0086))                              # armed


# ---------------- C-F2: risk-off sentinels drive commands ---------------

def test_pause_and_entries_sentinels_written_and_cleared(tmp_path,
                                                         monkeypatch):
    import runner as runner_mod
    r = runner_mod.BotRunner.__new__(runner_mod.BotRunner)
    r._paused_sentinel = tmp_path / "paused.on"
    r._entries_off_sentinel = tmp_path / "entries_off.on"
    r.state = "RUNNING"
    r._stop = False
    r._step_requested = False

    class _Bot:
        entries_enabled = True
        dry_run = True
    r.bot = _Bot()
    monkeypatch.setattr(runner_mod, "get_audit",
                        lambda: type("A", (), {"log": lambda *a, **k: None})())
    r.handle_command({"cmd": "pause"})
    assert r.state == "PAUSED" and r._paused_sentinel.exists()
    r.handle_command({"cmd": "entries_off"})
    assert r.bot.entries_enabled is False
    assert r._entries_off_sentinel.exists()
    r.handle_command({"cmd": "start"})
    assert r.state == "RUNNING" and not r._paused_sentinel.exists()
    r.handle_command({"cmd": "entries_on"})
    assert r.bot.entries_enabled is True
    assert not r._entries_off_sentinel.exists()


# ---------------- C-F14: lock OSError fallback honors a live peer -------

def test_lock_fs_error_fallback_refuses_live_peer(tmp_path, monkeypatch):
    import os as _os

    from core.runtime import SingleInstanceLock
    path = tmp_path / "runner.lock"
    path.write_text(json.dumps({"pid": 999999, "heartbeat": time.time()}),
                    encoding="utf-8")
    lk = SingleInstanceLock(str(path), stale_after_sec=30.0)
    real_open = _os.open

    def failing_open(p, flags, *a, **k):
        if str(p) == str(path) and (flags & _os.O_EXCL):
            raise PermissionError("scanner holds the file")
        return real_open(p, flags, *a, **k)
    monkeypatch.setattr(_os, "open", failing_open)
    holder = lk.acquire()
    # the OLD fallback returned None (acquired!) past a LIVE peer
    assert holder is not None and holder.get("pid") == 999999
