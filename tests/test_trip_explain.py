"""Pins for scripts/trip_explain.py (TE-1 per-trip PnL explanation, SAFE).

The contract: the components of every trip sum EXACTLY to its net USD, the
verdict is a deterministic function of them, beta never sees a bar after
entry, and a price anchor never uses the bar that contains the fill.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import trip_explain as te  # noqa: E402


def _leg(ts, purpose, side, size, price, ref=None, fees=0.1, rem=0.0,
         reason="", symbol="ETH/USD", fp=""):
    return {"ts": ts, "purpose": purpose, "side": side, "size": size,
            "price": price, "ref": price if ref is None else ref,
            "fees": fees, "remaining": rem, "reason": reason,
            "symbol": symbol, "fp": fp}


class FakeTape:
    """Asset and basket moves are given directly."""

    def __init__(self, r_asset, r_basket, beta=1.0):
        self.ra, self.rb, self.b = r_asset, r_basket, beta

    def ret(self, asset, t0, times, weights):
        r = self.ra if asset == "ETH" else self.rb
        return (r, "bot_cache") if r is not None else (None, None)

    def beta(self, asset, basket, t0):
        return None if self.b is None else (self.b, "bot_cache", 500)

    def price(self, asset, lane, ts):
        return None                      # no anchor -> no timing split


def _sum(rec_components):
    return sum(v for v in rec_components.values() if v is not None)


@pytest.mark.parametrize("side", ["b", "s"])
def test_identity_is_exact_long_and_short(side):
    opp = "s" if side == "b" else "b"
    legs = [_leg(0, "entry", side, 2.0, 100.0, ref=100.1),
            _leg(3600, "exit", opp, 1.0, 103.0, ref=102.9),
            _leg(7200, "exit", opp, 1.0, 98.0, ref=98.2, reason="tb_sl")]
    d = te.decompose(legs, "ETH", FakeTape(0.004, -0.002, 0.8))
    cash = sum((1 if x["side"] == "s" else -1) * x["size"] * x["price"]
               for x in legs) - sum(x["fees"] for x in legs)
    assert d["net"] == pytest.approx(cash, abs=1e-12)
    assert _sum(d["components"]) == pytest.approx(d["net"], abs=1e-12)
    assert d["identity_residual"] == pytest.approx(0.0, abs=1e-12)
    assert d["components"]["price_unattributed"] is None


def test_component_signs_follow_the_side():
    legs_l = [_leg(0, "entry", "b", 1, 100), _leg(60, "exit", "s", 1, 100)]
    legs_s = [_leg(0, "entry", "s", 1, 100), _leg(60, "exit", "b", 1, 100)]
    tape = FakeTape(0.01, 0.01, 1.0)       # everything went up 1%
    ml = te.decompose(legs_l, "ETH", tape)["components"]["market"]
    ms = te.decompose(legs_s, "ETH", tape)["components"]["market"]
    assert ml == pytest.approx(1.0) and ms == pytest.approx(-1.0)


def test_slippage_is_measured_against_each_legs_arrival_ref():
    # buy 1 @101 with mid 100 (paid 1 over), sell 1 @99 with mid 100
    legs = [_leg(0, "entry", "b", 1, 101, ref=100, fees=0),
            _leg(60, "exit", "s", 1, 99, ref=100, fees=0)]
    d = te.decompose(legs, "ETH", None)
    assert d["components"]["slippage"] == pytest.approx(-2.0)
    assert d["price"] == pytest.approx(0.0)            # mid to mid: flat


def test_no_tape_reports_price_whole_and_still_closes():
    legs = [_leg(0, "entry", "b", 1, 100), _leg(60, "exit", "s", 1, 102)]
    for tape, why in ((FakeTape(None, 0.0), "no_asset_tape"),
                      (FakeTape(0.02, None), "no_basket_tape"),
                      (FakeTape(0.02, 0.0, beta=None), "beta_window_short"),
                      (None, "no_asset_tape")):
        d = te.decompose(legs, "ETH", tape)
        c = d["components"]
        assert c["market"] is None and c["price_unattributed"] == \
            pytest.approx(2.0)
        assert d["coverage"]["reason"] == why
        assert _sum(c) == pytest.approx(d["net"], abs=1e-12)


@pytest.mark.parametrize("net,price,comp,expect", [
    (1.0, 1.2, {"market": 0.2, "asset_specific": 1.1, "timing": -0.1},
     "WIN_ASSET"),
    (-0.1, 0.3, {"market": 0.3, "asset_specific": 0.0, "timing": 0.0},
     "COST_EATEN"),
    (-1.0, -0.8, {"market": -0.9, "asset_specific": 0.2, "timing": -0.1},
     "LOSS_MARKET"),
    (-1.0, -0.8, {"market": None, "asset_specific": None, "timing": None,
                  "price_unattributed": -0.8}, "LOSS_PRICE"),
])
def test_verdict_is_a_function_of_the_components(net, price, comp, expect):
    c = {"market": None, "asset_specific": None, "timing": None,
         "price_unattributed": None, "fees": -0.2, "slippage": 0.0}
    c.update(comp)
    v, _ = te.verdict({"net": net, "price": price, "components": c,
                       "notional": 100.0}, None)
    assert v == expect


def test_loss_path_tag_uses_the_trips_own_cost():
    c = {"market": -1.0, "asset_specific": 0.0, "timing": 0.0,
         "price_unattributed": None, "fees": -0.5, "slippage": 0.0}
    dec = {"net": -1.5, "price": -1.0, "components": c, "notional": 100.0}
    # cost = 0.5 USD on 100 = 0.5%
    assert te.verdict(dec, {"mfe_pct": 0.6})[1] == "AHEAD_THEN_REVERSED"
    assert te.verdict(dec, {"mfe_pct": 0.4})[1] == "NEVER_AHEAD"


def _tape(series):
    t = te.Tape.__new__(te.Tape)
    t.series = series
    return t


def test_anchor_is_the_last_closed_bar_never_the_containing_one():
    t = np.array([0, 300, 600, 900], float)
    c = np.array([10.0, 11.0, 12.0, 13.0])
    tp = _tape({("ETH", "bot_cache"): (t, c)})
    # at ts 650 the bar opened at 600 has NOT closed (closes at 900)
    assert tp.price("ETH", "bot_cache", 650) == 11.0
    assert tp.price("ETH", "bot_cache", 900) == 12.0
    assert tp.price("ETH", "bot_cache", 5000) is None      # gap = no anchor


def test_beta_never_sees_a_bar_after_entry():
    rng = np.random.default_rng(0)
    n = 700
    t = np.arange(n, dtype=float) * 300
    xb = rng.normal(0, 0.002, n)
    ya = 2.0 * xb + rng.normal(0, 0.0005, n)
    t0 = t[400]                               # entry
    ya[400:] = -3.0 * xb[400:]                # the future says beta -3
    mk = lambda r: 100 * np.cumprod(1 + r)   # noqa: E731
    tp = _tape({("ETH", "bot_cache"): (t, mk(ya)),
                ("BTC", "bot_cache"): (t, mk(xb)),
                ("LINK", "bot_cache"): (t, mk(xb))})
    beta, lane, nb = tp.beta("ETH", ["BTC", "LINK"], t0)
    assert beta == pytest.approx(2.0, abs=0.1) and lane == "bot_cache"
    assert nb >= te.BETA_MIN_BARS


def test_one_lane_per_return_never_mixed():
    t = np.array([0, 300, 600, 900], float)
    tp = _tape({("ETH", "bot_cache"): (t[:2], np.array([10.0, 10.0])),
                ("ETH", "kraken"): (t, np.array([20.0, 20.0, 22.0, 22.0]))})
    # exit 2000: bot_cache's last close (600) is 1400 s stale, beyond the
    # 3-bar tolerance; kraken's (1200) is 800 s -> kraken for BOTH ends
    r, lane = tp.ret("ETH", 600, [2000], [1.0])
    assert lane == "kraken" and r == pytest.approx(22.0 / 20.0 - 1)


def test_cs1_buckets_every_position(tmp_path):
    f = tmp_path / "fills.csv"
    hdr = ("ts,order_id,position_id,purpose,symbol,side,ordertype,post_only,"
           "attempt,fill_size,fill_price,arrival_ref,slip_bps,fees_delta_usd,"
           "remaining,reason,exec_era,book,decision_fp\n")
    rows = ["1,o,A,entry,ETH/USD,buy,limit,1,1,1,100,100,0,0.1,0,,,,",
            "2,o,A,exit,ETH/USD,sell,limit,1,1,1,101,101,0,0.1,0,tb_pt,,,",
            "1,o,B,entry,ETH/USD,buy,limit,1,1,1,100,100,0,0.1,0,,,,",
            "1,o,C,hedge,ETH/USD,sell,limit,1,1,1,100,100,0,0.1,0,,,,",
            "2,o,C,exit,ETH/USD,buy,limit,1,1,1,99,99,0,0.1,0,unwind,,,",
            "2,o,D,exit,ETH/USD,sell,limit,1,1,1,99,99,0,0.1,0,x,,,"]
    f.write_text(hdr + "\n".join(rows) + "\n", encoding="utf-8")
    closed, b = te.load_positions(f)
    assert set(closed) == {"A"}
    assert b == {"explained": 1, "open": 1, "hedge_book": 1,
                 "exit_without_entry": 1}


def test_record_schema_and_atomic_write(tmp_path):
    legs = [_leg(0, "entry", "b", 1, 100, fp="abc123"),
            _leg(60, "exit", "s", 1, 99, reason="tb_sl")]
    ev = {"P": {"features": {"basis_dir": 0.5, "mom_dir": -0.2,
                             "ofi_dir": 0.1}, "gate_confidence": 0.7}}
    r = te.explain("P", legs, FakeTape(-0.01, -0.012, 1.0), ev, {})
    assert r["schema"] == "TE-1" and r["cohort"] == "abc123"
    assert r["verdict"].startswith("LOSS_")
    assert r["evidence"]["majority"] == "with"
    assert r["evidence"]["price_moved"] == "against"
    assert r["evidence"]["majority_matched"] is False
    assert abs(_sum(r["components_usd"]) - r["net_usd"]) < 1e-3
    out = tmp_path / "trip_explanations.jsonl"
    te.write_jsonl(out, [r, r])
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["position_id"] == "P"
    assert not (tmp_path / "trip_explanations.jsonl.tmp").exists()


def test_nothing_in_the_order_path_imports_it():
    hits = []
    for base in ("main.py", "runner.py", "core", "execution", "risk",
                 "strategies", "ml", "regime", "data", "api"):
        p = ROOT / base
        for f in [p] if p.is_file() else p.rglob("*.py"):
            if "trip_explain" in f.read_text(encoding="utf-8",
                                             errors="ignore"):
                hits.append(str(f))
    assert hits == []


class AnchoredTape(FakeTape):
    def __init__(self, *a, p0=100.0, **k):
        super().__init__(*a, **k)
        self.p0 = p0

    def price(self, asset, lane, ts):
        return self.p0


@pytest.mark.parametrize("side", ["b", "s"])
def test_timing_split_sums_to_timing_and_signs_the_chase(side):
    opp = "s" if side == "b" else "b"
    # entry arrival mid 100.5 vs anchor 100: a long paid 0.5 over the anchor
    legs = [_leg(0, "entry", side, 2.0, 100.5, ref=100.5),
            _leg(600, "exit", opp, 2.0, 101.0, ref=101.0)]
    d = te.decompose(legs, "ETH", AnchoredTape(0.01, 0.0, 1.0, p0=100.0))
    sp, t = d["timing_split"], d["components"]["timing"]
    assert sp["entry"] + sp["exit"] == pytest.approx(t, abs=1e-12)
    sgn = 1 if side == "b" else -1
    assert sp["entry"] == pytest.approx(sgn * (100.0 - 100.5) * 2.0)
    assert _sum(d["components"]) == pytest.approx(d["net"], abs=1e-12)


def test_lane_is_carried_so_p_win_is_never_read_alone():
    legs = [_leg(0, "entry", "b", 1, 100), _leg(60, "exit", "s", 1, 99)]
    ev = {"P": {"features": {"basis_dir": 0.5}, "gate_confidence": None,
                "lane": "probe"}}
    r = te.explain("P", legs, None, ev, {"P": {"p_win": 0.85}})
    assert r["evidence"]["lane"] == "probe"
