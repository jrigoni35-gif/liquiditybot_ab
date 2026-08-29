"""Tests for scripts/fee_anatomy_report.py — the fee-anatomy instrument.

Each assertion is written to DIE under a specific mutation of the code it
pins (documented inline), so a green here is evidence the instrument
measures what it claims, not that it merely runs.
"""
import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fee_anatomy_report as far  # noqa: E402

COLS = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
        "ordertype", "post_only", "attempt", "fill_size", "fill_price",
        "arrival_ref", "slip_bps", "fees_delta_usd", "remaining", "reason",
        "exec_era"]


def _row(**kw):
    r = {c: "" for c in COLS}
    r.update(kw)
    return r


def _write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


@pytest.fixture
def fills(tmp_path):
    """One closed maker-entry / taker-exit trip + one deferrable taker exit
    + one structural (stop) taker exit + a hedge leg. Sizes/prices chosen so
    fee arithmetic is exact.

    Trip A (pid=A): entry buy 1@100 maker (post_only=1), exit sell 1@101
    taker (post_only=0, reason 'tier 1' = deferrable). notional=100.
    Extra rows exercise the leg-mix and counterfactual buckets.
    """
    rows = [
        # trip A: maker entry, taker (deferrable) exit
        _row(ts="1000", position_id="A", purpose="entry", side="buy",
             post_only="1", fill_size="1", fill_price="100",
             fees_delta_usd="0.25", remaining="0", reason="signal"),
        _row(ts="1001", position_id="A", purpose="exit", side="sell",
             post_only="0", fill_size="1", fill_price="101",
             fees_delta_usd="0.404", remaining="0", reason="tier 1"),
        # trip B: maker entry, taker STRUCTURAL exit (stop)
        _row(ts="2000", position_id="B", purpose="entry", side="buy",
             post_only="1", fill_size="1", fill_price="200",
             fees_delta_usd="0.50", remaining="0", reason="signal"),
        _row(ts="2001", position_id="B", purpose="exit", side="sell",
             post_only="0", fill_size="1", fill_price="199",
             fees_delta_usd="0.796", remaining="0", reason="tb_sl"),
        # a hedge leg (open) — 100% taker, its own bucket
        _row(ts="3000", position_id="H", purpose="hedge", side="sell",
             post_only="0", fill_size="1", fill_price="50",
             fees_delta_usd="0.20", remaining="0", reason="hedge open"),
    ]
    p = tmp_path / "fills.csv"
    _write(p, rows)
    return str(p)


def test_leg_mix_reads_post_only(fills):
    res = far.compute(fills)
    # entries: 2 fills, both maker -> 100% maker. KILLS a mutation that reads
    # the wrong flag value or buckets exit fills into entry.
    assert res["mix"]["entry"] == {"maker": 2, "taker": 0, "total": 2,
                                   "maker_frac": 1.0}
    # exits: 2 fills, both taker -> 0% maker (the load-bearing finding shape).
    assert res["mix"]["exit"]["maker"] == 0
    assert res["mix"]["exit"]["taker"] == 2
    assert res["mix"]["exit"]["maker_frac"] == 0.0
    # hedge is its OWN bucket, never pooled into entry.
    assert res["mix"]["hedge"] == {"maker": 0, "taker": 1, "total": 1,
                                   "maker_frac": 0.0}


def test_venue_true_reprice_is_schedule_not_booked(fills):
    """Re-price must use the passed schedule against post_only, NOT the
    booked fees_delta_usd. KILLS a mutation that returns booked fees."""
    res = far.compute(fills, maker_bps=40.0, taker_bps=80.0)
    fd = res["fee_dollars"]
    # maker fills: entry A 1@100 + entry B 1@200 = notional 300 @ 40bps = 1.20
    assert fd["maker_usd"] == pytest.approx(300 * 40 / 1e4, abs=1e-9)
    # taker fills: exit A 101 + exit B 199 + hedge 50 = 350 @ 80bps = 2.80
    assert fd["taker_usd"] == pytest.approx(350 * 80 / 1e4, abs=1e-9)
    # booked totals differ from venue-true -> proves it is NOT reading booked
    assert res["trips"]["agg_booked_usd"] != pytest.approx(
        res["trips"]["agg_vtrue_usd"])


def test_structural_vs_deferrable_split(fills):
    """tb_sl exit is structural; 'tier 1' exit is deferrable. KILLS a
    mutation that mis-classifies (e.g. everything deferrable)."""
    cf = far.compute(fills)["exit_counterfactual"]
    assert cf["structural_n"] == 1          # tb_sl
    assert cf["deferrable_n"] == 1          # tier 1
    # deferrable notional = exit A = 1*101 = 101; prize @ 40bps drop = 0.404
    assert cf["deferrable_notional"] == pytest.approx(101.0)
    assert cf["deferrable_prize_usd"] == pytest.approx(101 * 40 / 1e4)
    # structural floor = exit B = 199; NOT capturable
    assert cf["structural_notional"] == pytest.approx(199.0)


def test_is_structural_exit_classifier():
    assert far.is_structural_exit("tb_sl")
    assert far.is_structural_exit("stop 65032.50 hit")
    assert far.is_structural_exit("hedge unwind: correlation 0.00 below floor")
    assert far.is_structural_exit("stale loser 100h, regime against")
    assert far.is_structural_exit("tb_time")
    # profit-taking / trail exits are deferrable (could rest maker)
    assert not far.is_structural_exit("tier trail")
    assert not far.is_structural_exit("tier 1")
    assert not far.is_structural_exit("label-mature realization (ML-073)")
    assert not far.is_structural_exit("tb_pt")


def test_trip_dedup_and_close_gate(fills, tmp_path):
    """An open position (no exit) is skipped, not counted; a duplicate
    fill-pattern is dropped."""
    res = far.compute(fills)
    assert res["n_trips"] == 2          # A and B; hedge-only H has no exit
    assert res["skipped"].get("still_open") == 1   # the hedge leg H
