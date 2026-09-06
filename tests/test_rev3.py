"""Acceptance suite for the rev-3 alpha stack (signals, exits, ML)."""
import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from strategies.informed_flow import InformedFlowEngine
from risk.profit_tiers import ProfitTierEngine
from core.state import Position
from core.persistence import position_from_dict, position_to_dict
from ml.models import GradientBoostedStumps, LogisticModel, auc_score
from ml.walkforward import evaluate_and_select


# ---------------------------------------------------------------- helpers
def make_candles(n=60, start=100.0, drift=0.0, vol_seq=None, clv=0.5,
                 last_vol=None, last_clv=None):
    out, px = [], start
    for i in range(n):
        px *= (1 + drift)
        rng_w = px * 0.004
        lo, hi = px - rng_w, px + rng_w
        close = lo + clv * (hi - lo)
        v = (vol_seq[i] if vol_seq else 100.0)
        out.append({"open": px, "high": hi, "low": lo, "close": close,
                    "volume": v})
        px = close
    if last_vol is not None:
        out[-1]["volume"] = last_vol
    if last_clv is not None:
        c = out[-1]
        c["close"] = c["low"] + last_clv * (c["high"] - c["low"])
    return out


def bullish_view(imb=1.9):
    return {"kraken_symbol": "ETH/USD", "imbalance_ratio": imb,
            "funding_rate": 0.0001,
            "candles": make_candles(60, drift=0.004, clv=0.85,
                                    last_vol=600, last_clv=0.9)}


IF_CFG = {"persistence_evals": 3, "min_imbalance_ratio": 1.35,
          "ad_lookback_bars": 24, "vol_z_min": 2.0, "clv_min": 0.6,
          "max_abs_funding_rate": 0.01, "fast_period": 9, "slow_period": 21,
          "evidence_threshold": 1.15, "min_agree": 3, "flow_min": 0.25}


# ---------------------------------------------------------------- informed_flow
def test_if3_fails_closed_on_garbage_and_insufficient_data():
    eng = InformedFlowEngine(IF_CFG)
    r = eng.evaluate_asset("ETH", None)
    assert not r.all_confirmed and r.direction is None
    r = eng.evaluate_asset("ETH", {"candles": make_candles(5)})
    assert not r.all_confirmed
    assert r.gates_passed.get("v3_data_sufficiency") is False


def test_if3_confirms_long_on_strong_aligned_evidence():
    eng = InformedFlowEngine(IF_CFG)
    r = None
    for _ in range(4):                    # build imbalance persistence
        r = eng.evaluate_asset("ETH", bullish_view())
    assert r is not None
    assert r.all_confirmed and r.direction == "long"
    assert r.confidence == 1.0            # downstream prior contract
    assert 0.0 < r.urgency <= 1.0
    assert r.gates_passed["v3_evidence"] and r.gates_passed["v3_agreement"]


def test_if3_symmetric_short():
    eng = InformedFlowEngine(IF_CFG)
    v = {"kraken_symbol": "ETH/USD", "imbalance_ratio": 1 / 1.9,
         "funding_rate": 0.0,
         "candles": make_candles(60, drift=-0.004, clv=0.15,
                                 last_vol=600, last_clv=0.1)}
    r = None
    for _ in range(4):
        r = eng.evaluate_asset("ETH", v)
    assert r is not None
    assert r.all_confirmed and r.direction == "short"


def test_if3_funding_veto_blocks_confirmation():
    eng = InformedFlowEngine(IF_CFG)
    v = bullish_view()
    v["funding_rate"] = 0.02              # 2x the cap
    r = None
    for _ in range(4):
        r = eng.evaluate_asset("ETH", v)
    assert r is not None
    assert not r.all_confirmed
    assert r.gates_passed["if_4_funding_sanity"] is False


def test_if3_absorption_veto_blocks_trap_side():
    """Price grinding up while volume-weighted CLV screams distribution
    must not confirm a long."""
    eng = InformedFlowEngine(IF_CFG)
    v = {"kraken_symbol": "ETH/USD", "imbalance_ratio": 1.9,
         "funding_rate": 0.0,
         "candles": make_candles(60, drift=0.004, clv=0.12,   # closes at lows
                                 last_vol=600, last_clv=0.12)}
    r = None
    for _ in range(4):
        r = eng.evaluate_asset("ETH", v)
    assert r is not None
    assert r.direction != "long" or not r.all_confirmed
    # and it is specifically the absorption gate that failed (not an incidental
    # veto): a False "no-absorption" gate means absorption WAS detected.
    assert r.gates_passed["v3_no_absorption"] is False


def test_if3_partial_confidence_bounded_when_unconfirmed():
    eng = InformedFlowEngine(IF_CFG)
    v = bullish_view(imb=1.05)            # weak flow
    r = None
    for _ in range(4):
        r = eng.evaluate_asset("ETH", v)
    assert r is not None
    assert not r.all_confirmed
    assert 0.0 <= r.confidence <= 0.99


def test_if3_incremental_ema_matches_full_recompute():
    eng = InformedFlowEngine(IF_CFG)
    closes = [100 * (1.003 ** i) for i in range(80)]
    # feed growing history incrementally
    for k in range(25, 81, 5):
        view = {"imbalance_ratio": 1.0, "funding_rate": 0.0,
                "candles": [{"open": c, "high": c * 1.001, "low": c * 0.999,
                             "close": c, "volume": 100} for c in closes[:k]]}
        eng.evaluate_asset("X", view)
    st = eng._st["X"]

    def full_ema(vals, period):
        k2 = 2.0 / (period + 1)
        e = vals[0]
        for v in vals[1:]:
            e = v * k2 + e * (1 - k2)
        return e
    assert math.isclose(st.ema_f, full_ema(closes, 9), rel_tol=1e-9)
    assert math.isclose(st.ema_s, full_ema(closes, 21), rel_tol=1e-9)


# ---------------------------------------------------------------- profit tiers
def make_pos(direction="long", entry=100.0, tier=0, size=1.0,
             age_min=0.0):
    return Position(position_id="p1", symbol="ETH/USD", direction=direction,
                    entry_price=entry, size=size, original_size=size,
                    opened_at=datetime.now(timezone.utc)
                    - timedelta(minutes=age_min),
                    tier_closed=tier)


PT_LEGACY = {"tier_1": {"trigger_pct_gain": 1.0, "close_pct_of_position": 25},
             "tier_2": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
             "tier_3": {"trigger_pct_gain": 3.5, "close_pct_of_position": 25},
             "tier_4": {"trigger_pct_gain": 5.0, "close_pct_of_position": 25},
             "trailing_stop": {"enabled": True, "activate_after_tier": 2,
                               "trail_pct": 1.0},
             # cut #10 (B2): the ABSENT est_fee_bps default moved 0.0 -> the
             # venue's worst taker row (fail conservative), which arms a
             # break-even floor this legacy fixture never had. The two-arg
             # CALL SHAPE this test pins is unchanged; the fixture states the
             # cost world it was written in (none) explicitly, as it should
             # have from the start.
             "est_fee_bps": 0}


def test_tiers_legacy_two_arg_call_still_exact():
    eng = ProfitTierEngine(PT_LEGACY)
    pos = make_pos()
    a = eng.evaluate(pos, 100.9)          # below 1.0% trigger
    assert not a.should_close_partial
    a = eng.evaluate(pos, 101.05)
    assert a.should_close_partial and a.tier_fired == 1 and a.close_pct == 25
    assert a.realized_pnl == pytest.approx(1.05 * 0.25, rel=1e-6)


def test_tiers_vol_scaled_with_clamp_band():
    cfg = dict(PT_LEGACY, vol_scaled=True)
    cfg["tier_1"] = dict(PT_LEGACY["tier_1"], trigger_vol_mult=8.0)
    eng = ProfitTierEngine(cfg)
    # high vol: 8 * 0.30% = 2.4% but clamped at 3x legacy? 3.0% cap -> 2.4 ok
    pos = make_pos()
    assert not eng.evaluate(pos, 101.5, sigma_bar_pct=0.30).should_close_partial
    assert eng.evaluate(pos, 102.5, sigma_bar_pct=0.30).tier_fired == 1
    # absurd vol input clamps to 3x legacy = 3.0%
    pos2 = make_pos()
    assert not eng.evaluate(pos2, 102.9, sigma_bar_pct=5.0).should_close_partial
    assert eng.evaluate(pos2, 103.1, sigma_bar_pct=5.0).tier_fired == 1
    # dead vol feed -> exact legacy trigger
    pos3 = make_pos()
    assert eng.evaluate(pos3, 101.05, sigma_bar_pct=0.0).tier_fired == 1


def test_break_even_ratchet_after_tier1():
    cfg = dict(PT_LEGACY, be_after_tier=1, be_buffer_bps=10, est_fee_bps=40)
    eng = ProfitTierEngine(cfg)
    pos = make_pos(tier=1)                # tier 1 already fired
    eng.evaluate(pos, 101.0)              # installs BE floor
    be = 100.0 * (1 + (2 * 40 + 10) / 1e4)
    assert pos.trailing_stop_price == pytest.approx(be)
    a = eng.evaluate(pos, be - 0.01)      # dip through the floor
    assert a.should_close_partial and a.close_pct == 100.0


def test_chandelier_anchors_high_water_and_ratchets_only():
    cfg = dict(PT_LEGACY, vol_scaled=True, chandelier_k=3.0,
               chandelier_bars=6, be_after_tier=99)
    eng = ProfitTierEngine(cfg)
    pos = make_pos(tier=4)                # ladder exhausted: pure trail
    eng.evaluate(pos, 105.0, sigma_bar_pct=0.20)
    assert pos.trailing_stop_price is not None
    hw1, st1 = pos.high_water, pos.trailing_stop_price
    assert hw1 == 105.0
    dist = max(0.01, 3.0 * 0.002 * math.sqrt(6))
    assert st1 == pytest.approx(105.0 * (1 - dist))
    eng.evaluate(pos, 103.0, sigma_bar_pct=0.20)   # pullback: no loosening
    assert pos.high_water == 105.0 and pos.trailing_stop_price == st1
    eng.evaluate(pos, 110.0, sigma_bar_pct=0.20)   # new high: ratchet up
    assert pos.trailing_stop_price is not None
    assert pos.high_water == 110.0
    assert pos.trailing_stop_price > st1
    a = eng.evaluate(pos, pos.trailing_stop_price - 0.01,
                     sigma_bar_pct=0.20)
    assert a.should_close_partial and a.close_pct == 100.0


def test_chandelier_short_side_symmetry():
    cfg = dict(PT_LEGACY, vol_scaled=True, be_after_tier=99)
    eng = ProfitTierEngine(cfg)
    pos = make_pos(direction="short", tier=4)
    eng.evaluate(pos, 95.0, sigma_bar_pct=0.20)
    assert pos.high_water == 95.0
    st = pos.trailing_stop_price
    assert st is not None
    assert st > 95.0
    eng.evaluate(pos, 97.0, sigma_bar_pct=0.20)    # adverse: no loosening
    assert pos.trailing_stop_price == st
    a = eng.evaluate(pos, st + 0.01, sigma_bar_pct=0.20)
    assert a.should_close_partial


def test_time_tightening_shrinks_trail_distance():
    cfg = dict(PT_LEGACY, vol_scaled=True, tighten_after_bars=96,
               tighten_factor=0.85, tighten_floor=0.45)
    young = ProfitTierEngine(cfg)
    d_young = young._trail_distance_frac(make_pos(age_min=0), 0.20)
    d_old = young._trail_distance_frac(make_pos(age_min=96 * 5 + 48 * 5 * 4),
                                       0.20)
    assert d_old < d_young
    assert d_old >= d_young * 0.45 - 1e-12


def test_position_high_water_persists_round_trip():
    pos = make_pos()
    pos.high_water = 123.45
    d = position_to_dict(pos)
    back = position_from_dict(d)
    assert back.high_water == 123.45
    d.pop("high_water")                    # old snapshot format
    legacy = position_from_dict(d)
    assert legacy.high_water is None


# ---------------------------------------------------------------- ML
def test_gbt_beats_linear_on_conditional_interaction_and_serdes():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2000, 8))
    logit = 0.6 * X[:, 0] + 1.8 * X[:, 1] * (X[:, 2] > 0) - 0.4
    y = (rng.random(2000) < 1 / (1 + np.exp(-logit))).astype(float)
    g = GradientBoostedStumps(seed=1).fit(X[:1500], y[:1500])
    lin = LogisticModel(seed=1).fit(X[:1500], y[:1500])
    ag = auc_score(y[1500:], g.predict_proba(X[1500:]))
    al = auc_score(y[1500:], lin.predict_proba(X[1500:]))
    assert ag > al + 0.03
    import json
    g2 = GradientBoostedStumps.from_dict(json.loads(json.dumps(g.to_dict())))
    assert g2 is not None
    assert np.allclose(g2.predict_proba(X[1500:]),
                       g.predict_proba(X[1500:]))


def test_walkforward_selects_gbt_only_when_earned():
    rng = np.random.default_rng(3)
    # pure-linear world: ladder must keep the baseline
    Xl = rng.normal(size=(700, 6))
    yl = (rng.random(700) < 1 / (1 + np.exp(-(0.9 * Xl[:, 0] - 0.1)))
          ).astype(float)
    r = evaluate_and_select(Xl, yl, label_span=30)
    assert r["selected"] == "logistic"
    # interaction world: gbt earns it
    Xi = rng.normal(size=(1400, 8))
    li = 0.5 * Xi[:, 0] + 2.0 * Xi[:, 1] * (Xi[:, 2] > 0) - 0.3
    yi = (rng.random(1400) < 1 / (1 + np.exp(-li))).astype(float)
    r2 = evaluate_and_select(Xi, yi, label_span=30)
    assert r2["selected"] == "gbt"
    assert {"logistic", "gbt", "mlp"} <= set(k for k in r2 if k in
                                             ("logistic", "gbt", "mlp"))


def test_meta_service_serves_gbt_artifact_end_to_end(tmp_path):
    """GBT through the full assurance path: save_model -> registry
    SHA ledger -> MetaModelService integrity-verified reload ->
    contract-gated p_win inference."""
    from ml.features import FEATURE_NAMES
    from ml.models import save_model
    from ml.meta_model import MetaModelService

    rng = np.random.default_rng(5)
    n_f = len(FEATURE_NAMES)
    # contract-legal design: zeros are inside every feature's range;
    # ret_1 (bounded ±6) carries the signal, direction/gate set validly
    X = np.zeros((400, n_f))
    X[:, 0] = np.clip(rng.normal(size=400), -6, 6)
    X[:, FEATURE_NAMES.index("direction")] = 1.0
    X[:, FEATURE_NAMES.index("gate_confidence")] = 1.0
    y = (rng.random(400) < 1 / (1 + np.exp(-X[:, 0]))).astype(float)
    m = GradientBoostedStumps(seed=2, n_estimators=60).fit(X, y)
    path = str(tmp_path / "meta_model.json")
    save_model(m, path, extra={"oof_brier": 0.24, "rows": 400})

    svc = MetaModelService({"model_path": path, "cold_start_prior_p": 0.56})
    assert svc.trained and svc.model is not None and svc.model.kind == "gbt"
    p = svc.p_win(X[0], gate_confidence=1.0)
    assert 0.05 <= p <= 0.95
    assert svc.fallbacks == 0
    # contract still guards it: garbage vector -> prior, counted
    bad = np.full(n_f, 99.0)
    p2 = svc.p_win(bad, gate_confidence=1.0)
    assert p2 == pytest.approx(0.56) and svc.fallbacks == 1


def test_cold_start_prior_used_regardless_of_gate_confidence(tmp_path):
    """Regression: p_win() used to gate the configured cold_start_prior_p
    on `gate_confidence >= 0.999`, but the sole production caller
    (main.py, after signal.all_confirmed is verified True) always passes a
    continuously-shaded score that is essentially never exactly >=0.999 -
    so the fallback silently served an unconfigurable 0.50 instead of the
    operator-configured prior. Confirmed dead by 2026-07-11 user sign-off:
    fix it to always use self.prior_p regardless of gate_confidence."""
    from ml.features import FEATURE_NAMES
    from ml.meta_model import MetaModelService

    # model_path defaults to outputs/meta_model.json - point it at a
    # nonexistent tmp path so this test doesn't pick up a real trained
    # model and stays a genuine cold-start (untrained) scenario
    svc = MetaModelService({"cold_start_prior_p": 0.56,
                            "model_path": str(tmp_path / "no_model.json")})
    assert not svc.trained
    zeros = np.zeros(len(FEATURE_NAMES))

    # the exact bug scenario: a realistic shaded confidence well below the
    # old dead 0.999 threshold must still get the configured prior, not 0.50
    for gc in (0.62, 0.7, 0.91, 0.0, 1.0):
        assert svc.p_win(zeros, gate_confidence=gc) == pytest.approx(0.56)


def test_informed_flow_rejects_alternating_imbalance():
    """Anti-spoof invariant: a materially opposing print inside the
    persistence window disqualifies flow, however strong the final
    print leaves the EWMA. Regression for the fusion-rewrite gap."""
    from strategies.informed_flow import InformedFlowEngine

    def candles(n=40):
        out, px = [], 2000.0
        for i in range(n):
            px *= 1.001
            rng_ = px * 0.004
            lo = px - rng_ * 0.9
            out.append({"open": px * 0.999, "high": lo + rng_, "low": lo,
                        "close": px, "volume": 300.0 * (0.9 if i % 2 else 1.1)})
        out[-1]["volume"] = 400.0
        return out

    eng = InformedFlowEngine({"persistence_evals": 3})
    view = {"kraken_symbol": "ETH/USD", "funding_rate": 0.0001,
            "candles": candles()}
    r = None
    for i in range(3):
        view["imbalance_ratio"] = 1.8 if i % 2 == 0 else 0.7
        r = eng.evaluate_asset("ETH", view)
    assert r is not None
    assert not r.all_confirmed
    assert not r.gates_passed["if_1_flow_persistence"]
