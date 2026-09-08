"""Tests for monitor/tape.py — Kraken tape in the market-microstructure shape.

Pure-function tests on synthetic Kraken rows. Pins the two live patterns
found on FLOWUSD in the 2026-09-07/08 sweep: one fixed quantity printing
on both taker sides, and buys + sells inside a single second.
"""

from __future__ import annotations

import pytest

from monitor import tape

T0 = 1_757_000_000.0


def row(price, qty, t, side="b", typ="l"):
    return [f"{price:.5f}", f"{qty:.8f}", t, side, typ, "", 1]


def test_to_records_shape_and_sides():
    recs = tape.to_records(
        [row(0.0294, 100, T0, "b", "m"), row(0.0293, 50, T0 - 1, "s", "l")]
    )
    assert [r["side"] for r in recs] == ["sell", "buy"]  # sorted by time
    r = recs[1]
    assert r["order_type"] == "market"
    assert r["volume_usd"] == pytest.approx(2.94)
    assert r["wallet"] == "q:100.00000000"


def test_pressure_net_and_shares():
    recs = tape.to_records(
        [
            row(0.03, 1000, T0, "b", "m"),
            row(0.03, 500, T0 + 1, "s"),
            row(0.03, 500, T0 + 2, "b"),
        ]
    )
    p = tape.pressure(recs)
    assert p["buy_usd"] == pytest.approx(45.0)
    assert p["sell_usd"] == pytest.approx(15.0)
    assert p["net_usd"] == pytest.approx(30.0)
    assert p["buy_volume_pct"] == pytest.approx(0.75)
    assert p["market_share"] == pytest.approx(1 / 3)


def test_pressure_empty_is_neutral():
    p = tape.pressure([])
    assert p["n"] == 0 and p["buy_volume_pct"] == 0.5 and p["market_share"] == 0.0


def test_size_skew_mean_over_median():
    recs = tape.to_records(
        [row(1.0, 10, T0 + i) for i in range(9)] + [row(1.0, 1000, T0 + 9)]
    )
    s = tape.size_skew(recs)
    assert s["median"] == 10
    assert s["skew"] == pytest.approx((9 * 10 + 1000) / 10 / 10)
    assert s["whale_pct"] == pytest.approx(1000 / 1090)


def test_clip_repeats_counts_exact_quantities():
    recs = tape.to_records(
        [row(0.03, 594.8437, T0 + i) for i in range(4)] + [row(0.03, 7, T0 + 9)]
    )
    reps = tape.clip_repeats(recs, min_repeats=3)
    assert reps == [("q:594.84370000", 4)]


def test_both_sides_lots_flags_fixed_lot_and_at_cost_round_trip():
    lot = 58095.28518759
    recs = tape.to_records(
        [
            row(0.0300, lot, T0, "s"),
            row(0.0289, lot, T0 + 3600, "s"),
            row(0.0296, lot, T0 + 7200, "b"),
            row(0.0296, 6756.75675675, T0 + 10, "b"),
            row(0.0296, 6756.75675675, T0 + 200, "s"),
            row(0.0296, 12, T0 + 5, "b"),  # below min_usd, ignored
        ]
    )
    out = tape.both_sides_lots(recs, min_usd=100.0)
    by = {d["wallet"]: d for d in out}
    big = by[f"q:{lot:.8f}"]
    assert (big["buys"], big["sells"]) == (1, 2)
    assert big["same_price_round_trip"] is False
    small = by["q:6756.75675675"]
    assert small["same_price_round_trip"] is True
    assert out[0]["wallet"] == big["wallet"]  # sorted by USD


def test_same_second_cross_requires_both_sides_and_size():
    recs = tape.to_records(
        [
            row(0.0294, 287238, T0 + 0.2, "b"),
            row(0.0293, 100000, T0 + 0.7, "s"),
            row(0.0294, 10, T0 + 5, "b"),
            row(0.0294, 10, T0 + 5.5, "s"),
        ]
    )
    out = tape.same_second_cross(recs, min_usd=1000.0)
    assert len(out) == 1
    assert out[0]["second"] == int(T0)
    assert out[0]["prints"] == 2
    assert out[0]["prices"] == [0.0293, 0.0294]


def test_hourly_buckets_and_acceleration():
    recs = tape.to_records(
        [
            row(0.03, 100, T0, "b"),
            row(0.03, 100, T0 + 10, "s"),
            row(0.03, 300, T0 + 3600, "b"),
        ]
    )
    hb = tape.hourly_buckets(recs)
    assert len(hb) == 2
    assert hb[0]["net_usd"] == pytest.approx(0.0)
    assert hb[1]["usd"] == pytest.approx(9.0)
    # first half = first record only ($3), second half = $3 + $9
    assert tape.acceleration(recs) == pytest.approx(12 / 3)


def test_momentum_score_formula_bounds_and_neutral():
    assert tape.momentum_score(0.5, 1.0, 0.5, 0.0) == 0.0
    assert tape.momentum_score(1.0, 10.0, 1.0, 10.0) == 100.0
    assert tape.momentum_score(0.0, 0.0, 0.0, -10.0) == -100.0
    assert tape.interpret(36.1) == "moderate buying"
    assert tape.interpret(-70) == "strong distribution"


def test_momentum_inputs_use_fingerprints_not_wallets():
    recs = tape.to_records(
        [
            row(0.03, 50000, T0, "b"),
            row(0.03, 50000, T0 + 1, "b"),
            row(0.03, 1, T0 + 2, "s"),
            row(0.03, 2, T0 + 3, "s"),
        ]
    )
    mi = tape.momentum_inputs(recs)
    assert mi["whale_buy_pct"] == 1.0  # both >= $1k prints are buys
    assert mi["unique_trader_trend"] == pytest.approx(
        1.0
    )  # 1 fingerprint -> 2 fingerprints


def test_report_is_json_serialisable_and_labelled():
    import json

    recs = tape.to_records(
        [row(0.03, 100, T0 + i, "b" if i % 2 else "s") for i in range(10)]
    )
    rep = tape.report(recs, "FLOWUSD", 1.0)
    json.dumps(rep)
    assert rep["momentum_label"] in {
        "neutral",
        "moderate buying",
        "moderate selling",
        "strong accumulation",
        "strong distribution",
    }


def test_get_refuses_non_kraken_host(monkeypatch):
    monkeypatch.setattr(tape, "KRAKEN", "https://evil.example/0/public")
    with pytest.raises(ValueError):
        tape._get("Trades", "pair=FLOWUSD")
