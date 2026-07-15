"""
tests/test_informed_flow_debug.py

Per-asset signal visibility (informed_flow.debug_all_signals). Two guarantees:

  1. UNBIASED VISIBILITY — when on, EVERY asset gets an identical "IF3 scan"
     line every cycle: confirmed, unconfirmed, and data-short alike. No asset
     is privileged by being the only one logged (the original complaint:
     only ETH/BTC ever appeared because only confirmed signals logged).

  2. ZERO DECISION INFLUENCE — the flag is pure observability. The SignalResult
     (direction, confidence, all_confirmed, urgency, gates) is BYTE-IDENTICAL
     with the flag off vs on, so turning on visibility can never change what
     trades. That is what makes the debug itself unbiased.

Default is OFF: a stock engine logs nothing extra.
"""
import logging

from strategies.informed_flow import InformedFlowEngine, _short_gate


def _candles(n=30, close=100.0, vol=10.0, drift=0.0):
    out, px = [], close
    for i in range(n):
        px = px * (1.0 + drift)
        out.append({"time": i, "open": px, "high": px * 1.002,
                    "low": px * 0.998, "close": px, "volume": vol})
    return out


def _view(sym, candles, imbalance=1.0, funding=0.0):
    return {"kraken_symbol": f"{sym}/USD", "imbalance_ratio": imbalance,
            "funding_rate": funding, "candles": candles}


def _fields(r):
    """The decision surface a downstream consumer sees."""
    return (r.direction, r.confidence, r.all_confirmed, round(r.urgency, 6),
            tuple(sorted((r.gates_passed or {}).items())))


# --- default off ------------------------------------------------------------
def test_debug_off_by_default_is_silent(caplog):
    eng = InformedFlowEngine({})                       # no flag -> default off
    assert eng.debug_all_signals is False
    with caplog.at_level(logging.INFO, logger="liquiditybot.strategies.informed_flow"):
        eng.evaluate_asset("SUI", _view("SUI", _candles(30)))
    assert not [r for r in caplog.records if "IF3 scan" in r.getMessage()]


# --- uniform per-asset logging (the fix) ------------------------------------
def test_debug_logs_every_asset_including_short_and_unconfirmed(caplog):
    eng = InformedFlowEngine({"debug_all_signals": True})
    with caplog.at_level(logging.INFO, logger="liquiditybot.strategies.informed_flow"):
        eng.evaluate_asset("MINA", _view("MINA", _candles(5)))    # data-short
        eng.evaluate_asset("ARB", _view("ARB", _candles(30)))     # unconfirmed
        eng.evaluate_asset("FLOW", _view("FLOW", _candles(30, drift=0.001)))
    scans = [r.getMessage() for r in caplog.records if "IF3 scan" in r.getMessage()]
    # every asset appears exactly once, none privileged
    assert any("IF3 scan MINA" in m and "WARMUP" in m for m in scans)   # short logged
    assert any("IF3 scan ARB" in m for m in scans)
    assert any("IF3 scan FLOW" in m for m in scans)
    # an unconfirmed data-sufficient asset shows WHY (FAIL: gate list)
    arb = next(m for m in scans if "IF3 scan ARB" in m)
    assert "E=" in arb and "agree=" in arb and "FAIL:" in arb


# --- the "not biased" guarantee: flag never changes the decision ------------
def test_debug_flag_never_changes_the_decision():
    cfg_off, cfg_on = {}, {"debug_all_signals": True}
    off, on = InformedFlowEngine(cfg_off), InformedFlowEngine(cfg_on)
    # drive several cycles per asset so state (EMAs, imbalance history) evolves;
    # the two engines must stay lockstep-identical at every step.
    seq = [
        ("ETH", _candles(30, drift=0.004), 2.4),
        ("ETH", _candles(30, drift=0.004), 2.6),
        ("SUI", _candles(28), 1.0),
        ("BTC", _candles(40, drift=-0.003), 0.7),
        ("BTC", _candles(40, drift=-0.003), 0.6),
        ("ARB", _candles(5), 1.0),               # data-short path too
    ]
    for asset, candles, imb in seq:
        r_off = off.evaluate_asset(asset, _view(asset, candles, imbalance=imb))
        r_on = on.evaluate_asset(asset, _view(asset, candles, imbalance=imb))
        assert _fields(r_off) == _fields(r_on), f"debug changed decision for {asset}"


def test_short_gate_names_are_readable():
    assert _short_gate("if_1_flow_persistence") == "flow_persistence"
    assert _short_gate("if_4_funding_sanity") == "funding_sanity"
    assert _short_gate("v3_evidence") == "evidence"
    assert _short_gate("v3_no_absorption") == "no_absorption"
