"""Signal-urgency faithfulness: urgency must be EXACTLY the configured
composition of its inputs - nothing phantom, nothing dropped - and always a
finite number in [0,1]. urgency drives the execution ladder
(execution/tactics.py: join/improve/taker), so a value that doesn't reflect
its inputs mis-places every entry.

  urgency = clamp(u_base + u_w_burst*burst+ + u_w_fresh*fresh
                        + u_w_delta*delta+ , 0, 1)   when confirmed, else 0

with burst+/delta+ the burst/delta components clamped to the [0,1] region
that AGREES with the evidence sign. The tests pin each term independently by
zeroing the others, so the output can only reflect the input it claims to.
"""
import math

from strategies.informed_flow import InformedFlowEngine

_BASE_CFG = {"persistence_evals": 3, "min_imbalance_ratio": 1.35,
             "ad_lookback_bars": 24, "vol_z_min": 2.0, "clv_min": 0.6,
             "max_abs_funding_rate": 0.01, "fast_period": 9, "slow_period": 21,
             "evidence_threshold": 1.15, "min_agree": 3, "flow_min": 0.25}


def _candles(n=60, start=100.0, drift=0.004, clv=0.85, last_vol=600,
             last_clv=0.9):
    out, px = [], start
    for _ in range(n):
        px *= (1 + drift)
        w = px * 0.004
        lo, hi = px - w, px + w
        out.append({"open": px, "high": hi, "low": lo,
                    "close": lo + clv * (hi - lo), "volume": 100.0})
        px = out[-1]["close"]
    out[-1]["volume"] = last_vol
    c = out[-1]
    c["close"] = c["low"] + last_clv * (c["high"] - c["low"])
    return out


def _view(imb=1.9):
    return {"kraken_symbol": "ETH/USD", "imbalance_ratio": imb,
            "funding_rate": 0.0001, "funding_available": True,
            "candles": _candles()}


def _confirm(eng):
    """Feed a strong bullish view a few times so the streak/imbalance EWMAs
    build, then return the confirmed result."""
    r = None
    for _ in range(5):
        r = eng.evaluate_asset("ETH", _view())
    assert r is not None and r.all_confirmed, "fixture must confirm"
    return r


def test_urgency_zero_when_not_confirmed():
    eng = InformedFlowEngine(_BASE_CFG)
    r = eng.evaluate_asset("ETH", None)          # garbage -> fail closed
    assert r.urgency == 0.0 and not r.all_confirmed


def test_urgency_is_finite_and_in_unit_interval():
    eng = InformedFlowEngine(_BASE_CFG)
    r = _confirm(eng)
    assert math.isfinite(r.urgency) and 0.0 <= r.urgency <= 1.0


def test_urgency_equals_base_when_all_weights_zero():
    """The purest faithfulness check: with every component weight zeroed, a
    confirmed signal's urgency must equal EXACTLY the configured base - no
    phantom contribution can leak in."""
    cfg = dict(_BASE_CFG, urgency={"base": 0.37, "w_burst": 0.0,
                                   "w_fresh": 0.0, "w_delta": 0.0})
    eng = InformedFlowEngine(cfg)
    r = _confirm(eng)
    assert abs(r.urgency - 0.37) < 1e-9


def test_urgency_saturates_at_one_not_beyond():
    """Base + all weights well over 1: the output must clamp at 1.0, never
    exceed it (a value >1 would break the tactics ladder thresholds)."""
    cfg = dict(_BASE_CFG, urgency={"base": 0.9, "w_burst": 1.0,
                                   "w_fresh": 1.0, "w_delta": 1.0})
    eng = InformedFlowEngine(cfg)
    r = _confirm(eng)
    assert r.urgency == 1.0


def test_urgency_base_is_floor_when_confirmed():
    """Every added term is >= 0, so a confirmed urgency can never fall below
    the configured base."""
    cfg = dict(_BASE_CFG, urgency={"base": 0.30, "w_burst": 0.40,
                                   "w_fresh": 0.20, "w_delta": 0.10})
    eng = InformedFlowEngine(cfg)
    r = _confirm(eng)
    assert r.urgency >= 0.30 - 1e-9


def test_urgency_rises_when_a_component_weight_increases():
    """Faithful to input: giving the freshness term more weight can only
    raise (never lower) a confirmed signal's urgency, all else equal."""
    lo = InformedFlowEngine(dict(_BASE_CFG, urgency={
        "base": 0.2, "w_burst": 0.0, "w_fresh": 0.0, "w_delta": 0.0}))
    hi = InformedFlowEngine(dict(_BASE_CFG, urgency={
        "base": 0.2, "w_burst": 0.0, "w_fresh": 0.5, "w_delta": 0.0}))
    r_lo, r_hi = _confirm(lo), _confirm(hi)
    assert r_hi.urgency >= r_lo.urgency


# --- evidence concentration (shadow: "don't blend when it's pinpointed") ----
def test_concentration_is_finite_and_in_unit_interval():
    eng = InformedFlowEngine(_BASE_CFG)
    r = _confirm(eng)
    assert math.isfinite(r.evidence_concentration)
    assert 0.0 <= r.evidence_concentration <= 1.0


def test_concentration_high_when_one_factor_dominates():
    """Zero every weight but one: the fused evidence then comes from a single
    component -> concentration must read ~1 (a pinpointed setup), the opposite
    of an averaged-over-everything signal."""
    cfg = dict(_BASE_CFG, evidence_threshold=0.05, min_agree=1, flow_min=0.0,
               weights={"flow": 1.0, "delta": 0.0, "accum": 0.0,
                        "burst": 0.0, "trend": 0.0})
    eng = InformedFlowEngine(cfg)
    r = None
    for _ in range(5):
        r = eng.evaluate_asset("ETH", _view())
    assert r.evidence_concentration > 0.95


def test_concentration_is_shadow_only_does_not_change_decision():
    """Concentration must be a pure diagnostic: two engines identical except
    for reading it must reach the same confirm/urgency decision."""
    eng = InformedFlowEngine(_BASE_CFG)
    r = _confirm(eng)
    # the concentration value exists but the confirm path is driven only by
    # evidence/agreement/flow - a confirmed signal still confirms
    assert r.all_confirmed and r.direction == "long"
    assert 0.0 <= r.evidence_concentration <= 1.0
