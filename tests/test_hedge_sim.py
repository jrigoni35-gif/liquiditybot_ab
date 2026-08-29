"""Semantics pins for scripts/hedge_sim.py (HEDGE-SIM harness).

Injection evidence, not green-only: each pin plants the exact bad form
(or the exact arithmetic) and watches the harness respond. Registered
in docs/quant/2026-08-28_hedge_sim_registration.md.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.hedge_sim import (
    PairingError,
    RoundTrip,
    blocked_opens,
    crosscheck,
    drawdown_deltas,
    episodes,
    grid,
    load_round_trips,
    load_round_trips_supplement,
    run,
    verdict,
)

FILLS_COLS = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
              "ordertype", "post_only", "attempt", "fill_size", "fill_price",
              "arrival_ref", "slip_bps", "fees_delta_usd", "remaining",
              "reason", "exec_era"]


def _fill(ts, pid, purpose, side, size, px, fee, reason="", post_only="0"):
    return {"ts": ts, "order_id": "o" + pid, "position_id": pid,
            "purpose": purpose, "symbol": "ADA/USD", "side": side,
            "ordertype": "limit", "post_only": post_only, "attempt": "0",
            "fill_size": size, "fill_price": px, "arrival_ref": px,
            "slip_bps": "0", "fees_delta_usd": fee, "remaining": "0",
            "reason": reason, "exec_era": ""}


def _write_fills(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FILLS_COLS)
        w.writeheader()
        w.writerows(rows)
    return path


def _trip_rows(pid, open_ts, size, open_px, close_px, open_fee, close_fee):
    return [
        _fill(open_ts, pid, "hedge", "sell", size, open_px, open_fee,
              reason="net delta +100 beyond cap 50, beta=1.00"),
        _fill(open_ts + 60, pid, "exit", "buy", size, close_px, close_fee,
              reason="hedge unwind: correlation 0.00 below floor"),
    ]


def _mk_trip(pid="p1", open_ts=1000.0, size=100.0, open_px=1.0,
             close_px=1.0, open_fee=0.0, close_fee=0.0,
             post_only=False) -> RoundTrip:
    return RoundTrip(position_id=pid, open_ts=open_ts, close_ts=open_ts + 60,
                     size=size, open_px=open_px, close_px=close_px,
                     open_side="sell", open_fee=open_fee, close_fee=close_fee,
                     open_post_only=post_only, close_post_only=post_only)


# ---------------------------------------------------------------- loading

def test_load_pairs_and_window_filter(tmp_path):
    rows = _trip_rows("a", 100.0, 10.0, 1.0, 0.9, 0.04, 0.036)
    rows += _trip_rows("out", 99999.0, 10.0, 1.0, 0.9, 0.04, 0.036)
    p = _write_fills(tmp_path / "fills.csv", rows)
    trips = load_round_trips(p, lo=0.0, hi=1000.0)
    assert [t.position_id for t in trips] == ["a"]
    assert trips[0].size == 10.0 and trips[0].open_side == "sell"


def test_load_fails_on_unpaired_open(tmp_path):
    # planted defect: unwind row deleted -> must FAIL, not degrade
    rows = _trip_rows("a", 100.0, 10.0, 1.0, 0.9, 0.0, 0.0)[:1]
    p = _write_fills(tmp_path / "fills.csv", rows)
    with pytest.raises(PairingError):
        load_round_trips(p, lo=0.0, hi=1000.0)


def test_load_fails_on_unequal_leg_sizes(tmp_path):
    rows = _trip_rows("a", 100.0, 10.0, 1.0, 0.9, 0.0, 0.0)
    rows[1]["fill_size"] = 9.0   # planted size mismatch
    p = _write_fills(tmp_path / "fills.csv", rows)
    with pytest.raises(PairingError):
        load_round_trips(p, lo=0.0, hi=1000.0)


def test_supplement_aggregates_split_close_exactly(tmp_path):
    # the real 2026-08-28 shape: open 100, closed 40 (hard cap breach)
    # + 60 (hedge unwind). Strict must FAIL; supplement must balance and
    # keep gross EXACT (vwap identity).
    rows = [
        _fill(100.0, "s", "hedge", "sell", 100.0, 1.0, 0.4,
              reason="net delta +1 beyond cap 0, beta=1.0"),
        _fill(105.0, "s", "exit", "buy", 40.0, 0.95, 0.152,
              reason="hard cap breach (-1,247 USD)"),
        _fill(160.0, "s", "exit", "buy", 60.0, 0.90, 0.216,
              reason="hedge unwind: correlation 0.34 below floor"),
    ]
    p = _write_fills(tmp_path / "fills.csv", rows)
    with pytest.raises(PairingError):
        load_round_trips(p, lo=0.0, hi=1000.0)
    trips = load_round_trips_supplement(p, lo=0.0, hi=1000.0)
    assert len(trips) == 1
    t = trips[0]
    # gross = sum over legs (open - leg_px)*leg_size = 40*.05 + 60*.10
    assert t.gross == pytest.approx(40 * 0.05 + 60 * 0.10)
    assert t.close_fee == pytest.approx(0.152 + 0.216)
    assert t.close_ts == 160.0


def test_supplement_fails_when_legs_do_not_balance(tmp_path):
    rows = [
        _fill(100.0, "s", "hedge", "sell", 100.0, 1.0, 0.4),
        _fill(105.0, "s", "exit", "buy", 40.0, 0.95, 0.152,
              reason="hedge unwind: x"),
    ]
    p = _write_fills(tmp_path / "fills.csv", rows)
    with pytest.raises(PairingError):
        load_round_trips_supplement(p, lo=0.0, hi=1000.0)


def test_run_labels_supplement_on_strict_failure(tmp_path):
    rows = [
        _fill(1786064990.0, "s", "hedge", "sell", 100.0, 1.0, 0.4,
              reason="net delta"),
        _fill(1786064995.0, "s", "exit", "buy", 40.0, 0.95, 0.152,
              reason="hard cap breach"),
        _fill(1786065050.0, "s", "exit", "buy", 60.0, 0.90, 0.216,
              reason="hedge unwind: x"),
    ]
    fills = _write_fills(tmp_path / "fills.csv", rows)
    audit = tmp_path / "audit.jsonl"
    net_booked = (40 * 0.05 + 60 * 0.10) - (0.4 + 0.152 + 0.216)
    audit.write_text(json.dumps({
        "code": "PT-061", "ts": 1786065051.0, "src": "exit",
        "msg": "PT-061: close ADA",
        "data": {"position_id": "s", "net_usd": net_booked,
                 "close_reason": "hedge unwind: x"}}) + "\n",
        encoding="utf-8")
    eq = tmp_path / "equity.csv"
    eq.write_text("ts,equity,daily_pnl\n1786060900,100.0,0\n",
                  encoding="utf-8")
    report = run(fills, audit, eq, out=None)
    assert "REGISTERED VERDICT: **UNDECIDABLE-AT-N** (harness-failure arm)" \
        in report
    assert "SUPPLEMENTARY verdict" in report


# ------------------------------------------------------------- economics

def test_short_hedge_gross_sign():
    t = _mk_trip(open_px=1.0, close_px=0.9, size=100.0)
    assert t.gross == pytest.approx(10.0)          # short profits on a fall
    t2 = _mk_trip(open_px=1.0, close_px=1.1, size=100.0)
    assert t2.gross == pytest.approx(-10.0)


def test_truth_fees_80bps_both_legs_and_maker_branch():
    t = _mk_trip(size=100.0, open_px=1.0, close_px=0.9)
    # taker both legs: 0.008*(100*1.0) + 0.008*(100*0.9) = 0.8 + 0.72
    assert t.fees("era8_truth") == pytest.approx(1.52)
    m = _mk_trip(size=100.0, open_px=1.0, close_px=0.9, post_only=True)
    assert m.fees("era8_truth") == pytest.approx(0.76)   # 40 bps maker


def test_fee_free_beats_feed_by_exactly_the_fee_stack():
    # registration's named injection: booked fees planted at zero ->
    # booked net must exceed truth net by EXACTLY the truth fee stack.
    trips = [_mk_trip(pid=f"p{i}", open_ts=1000.0 + i, size=50.0 + i,
                      open_px=2.0, close_px=1.9)
             for i in range(5)]
    g = grid(trips)
    fee_stack = sum(t.fees("era8_truth") for t in trips)
    assert g["cells"][(1.0, "booked")]["net"] - \
        g["cells"][(1.0, "era8_truth")]["net"] == pytest.approx(fee_stack)
    # and linearity in k, as registered
    assert g["cells"][(2.0, "era8_truth")]["net"] == pytest.approx(
        2.0 * g["cells"][(1.0, "era8_truth")]["net"])


# ---------------------------------------------------------------- verdict

def _trips_with_episode_nets(nets):
    """One trip per episode, gross == requested net (fees zero booked;
    use price legs sized so truth fees are negligible? No - build via
    open/close px so TRUTH net equals requested sign robustly)."""
    trips = []
    for i, net in enumerate(nets):
        # short: gross = (open-close)*size ; make gross = net + truth fees
        size, open_px = 100.0, 1.0
        # solve close_px so that gross - truthfees == net
        # gross = (1 - c)*100 ; truth = 0.8 + 0.008*100*c
        # (1-c)*100 - 0.8 - 0.8c = net  ->  100 - 100.8c - 0.8 = net
        c = (100.0 - 0.8 - net) / 100.8
        trips.append(_mk_trip(pid=f"e{i}", open_ts=1000.0 + i * 10_000,
                              size=size, open_px=open_px, close_px=c))
    return trips


def test_verdict_all_negative_episodes_costs_more():
    v = verdict(_trips_with_episode_nets([-5.0, -3.0, -1.0]))
    assert v["verdict"] == "HEDGE_COSTS_MORE"
    assert v["n_episodes"] == 3 and v["ci95"] is None


def test_verdict_all_positive_episodes_pays():
    v = verdict(_trips_with_episode_nets([5.0, 3.0, 1.0]))
    assert v["verdict"] == "HEDGE_PAYS"


def test_verdict_mixed_signs_undecidable():
    v = verdict(_trips_with_episode_nets([5.0, -3.0]))
    assert v["verdict"] == "UNDECIDABLE-AT-N"


def test_episode_clustering_gap_rule():
    a = _mk_trip(pid="a", open_ts=0.0)
    b = _mk_trip(pid="b", open_ts=1800.0)      # <= gap: same episode
    c = _mk_trip(pid="c", open_ts=3601.0)      # > gap from b: new episode
    assert [len(e) for e in episodes([a, b, c])] == [2, 1]


# ------------------------------------------------------------ cross-check

def test_crosscheck_flags_planted_disagreement():
    t = _mk_trip(pid="x", open_px=1.0, close_px=0.9, size=100.0,
                 open_fee=0.4, close_fee=0.36)
    good = {"x": t.net("booked")}
    assert crosscheck([t], good)["ok"] is True
    bad = {"x": t.net("booked") + 0.5}          # planted $0.50 disagreement
    assert crosscheck([t], bad)["ok"] is False
    assert crosscheck([t], {})["ok"] is False   # planted missing record


def test_run_downgrades_verdict_on_crosscheck_failure(tmp_path):
    rows = _trip_rows("a", 1786064990.0, 100.0, 1.0, 0.9, 0.4, 0.36)
    fills = _write_fills(tmp_path / "fills.csv", rows)
    # audit with a PT-061 net that disagrees by $5 (planted)
    audit = tmp_path / "audit.jsonl"
    audit.write_text(json.dumps({
        "code": "PT-061", "ts": 1786065050.0, "src": "exit",
        "msg": "PT-061: close ADA: reason=hedge unwind: x",
        "data": {"position_id": "a", "net_usd": 99.0,
                 "close_reason": "hedge unwind: correlation"}}) + "\n",
        encoding="utf-8")
    eq = tmp_path / "equity.csv"
    eq.write_text("ts,equity,daily_pnl\n1786060900,100.0,0\n",
                  encoding="utf-8")
    report = run(fills, audit, eq, out=None)
    assert "UNDECIDABLE-AT-N" in report
    assert "cross-check failed" in report


# ------------------------------------------------- blocked opens / equity

def test_blocked_opens_parses_notional(tmp_path):
    audit = tmp_path / "audit.jsonl"
    audit.write_text(json.dumps({
        "code": "FW-040", "ts": 1.0, "src": "firewall",
        "msg": "ADAUSD sell hedge px=0.2 sz=1000.0 :: FW-040: notional"})
        + "\n", encoding="utf-8")
    b = blocked_opens(audit)
    assert b["count"] == 1
    assert b["notional_usd"] == pytest.approx(200.0)
    assert b["truth_fee_cost_usd"] == pytest.approx(200.0 * 2 * 0.008)


def test_drawdown_delta_handles_tied_close_timestamps():
    # real data has duplicate close_ts; must not TypeError on the sort
    t1 = _mk_trip(pid="t1", open_ts=100.0, open_px=1.0, close_px=1.05,
                  size=100.0)
    t2 = _mk_trip(pid="t2", open_ts=101.0, open_px=1.0, close_px=1.05,
                  size=100.0)
    assert t1.close_ts == t2.close_ts - 1.0
    t2.close_ts = t1.close_ts               # force the tie
    eq_pts = [(50.0, 100.0), (200.0, 90.0)]
    dd = drawdown_deltas(eq_pts, [t1, t2])
    assert dd["cells"][(0.0, "booked")] == pytest.approx(-10.0)


def test_drawdown_delta_k0_removes_hedge_loss():
    # equity flat at 100 until the unwind books a -10 hedge loss
    t = _mk_trip(pid="d", open_ts=100.0, open_px=1.0, close_px=1.1,
                 size=100.0)                      # gross -10, fees 0 booked
    eq_pts = [(50.0, 100.0), (100.0, 100.0), (200.0, 90.0), (300.0, 90.0)]
    dd = drawdown_deltas(eq_pts, [t])
    assert dd["actual_max_dd"] == pytest.approx(10.0)
    # k=0 booked: add the loss back -> flat path, dd delta = -10
    assert dd["cells"][(0.0, "booked")] == pytest.approx(-10.0)
    # k=2 booked: doubled loss -> dd delta = +10
    assert dd["cells"][(2.0, "booked")] == pytest.approx(10.0)
