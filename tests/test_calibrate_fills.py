"""Fill-model calibrator data extraction (scripts/calibrate_fills.py).

The calibrator feeds core.fill_calibration with real numbers:
  * ledger_maker_fill_summary — observed sim maker/taker mix + slippage from the
    per-fill ledger (context: what the CURRENT model produced);
  * trade_through_counts — the non-circular calibration TARGET measured from
    recorded book frames: how often the market actually crossed a hypothetical
    resting limit within its life, as a function of distance-from-mid.

These pin the extraction math before wiring it to disk I/O.
"""
import csv

from scripts.calibrate_fills import (
    ledger_maker_fill_summary,
    trade_through_counts,
)


def _write_ledger(path, rows):
    cols = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
            "ordertype", "post_only", "attempt", "fill_size", "fill_price",
            "arrival_ref", "slip_bps", "fees_delta_usd", "remaining", "reason"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def test_ledger_summary_splits_maker_taker_and_reports_slip(tmp_path):
    p = tmp_path / "fills.csv"
    _write_ledger(p, [
        {"ordertype": "limit", "post_only": "1", "slip_bps": "10",
         "fees_delta_usd": "0.02"},
        {"ordertype": "limit", "post_only": "1", "slip_bps": "20",
         "fees_delta_usd": "0.02"},
        {"ordertype": "limit", "post_only": "1", "slip_bps": "30",
         "fees_delta_usd": "0.02"},
        {"ordertype": "market", "post_only": "0", "slip_bps": "45",
         "fees_delta_usd": "0.05"},
    ])
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    s = ledger_maker_fill_summary(rows)
    assert s["maker_fills"] == 3 and s["taker_fills"] == 1
    assert s["slip_p50_bps"] == 20.0
    assert 28.0 <= s["slip_p95_bps"] <= 30.0


def test_ledger_summary_is_empty_safe():
    s = ledger_maker_fill_summary([])
    assert s["maker_fills"] == 0 and s["taker_fills"] == 0
    assert s["slip_p50_bps"] is None


def _frame(ts, bid, ask):
    return {"ts": ts, "bid": bid, "ask": ask}


def test_trade_through_counts_detects_a_real_crossing():
    # mid ~100; at t=10 the ask dips to 99.0, crossing a buy limit 50bps below
    frames = [_frame(0, 99.9, 100.1), _frame(5, 99.9, 100.1),
              _frame(10, 98.8, 99.0), _frame(15, 99.9, 100.1)]
    out = trade_through_counts(frames, life_polls=3, dist_bps_grid=[50.0],
                               sigma_bps=40.0)
    assert len(out) == 1
    b = out[0]
    assert b["dist_bps"] == 50.0
    assert abs(b["d_bar"] - 50.0 / 40.0) < 1e-9
    assert b["n"] > 0 and b["k"] >= 1          # the dip crossed >=1 buy limit


def test_trade_through_counts_no_crossing_far_from_mid():
    frames = [_frame(0, 99.9, 100.1), _frame(5, 99.9, 100.1),
              _frame(10, 99.9, 100.1), _frame(15, 99.9, 100.1)]
    out = trade_through_counts(frames, life_polls=3, dist_bps_grid=[500.0],
                               sigma_bps=40.0)
    assert out[0]["k"] == 0                     # 500bps away: never crossed
    assert out[0]["n"] > 0


def test_trade_through_counts_empty_frames_safe():
    assert trade_through_counts([], life_polls=3, dist_bps_grid=[50.0],
                                sigma_bps=40.0) == [
        {"dist_bps": 50.0, "d_bar": 50.0 / 40.0, "k": 0, "n": 0}]
