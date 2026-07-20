"""tests/test_funding_unavailable_policy.py — unavailable funding is an
explicit, consistent, configurable policy (default: fail OPEN).

Funding is an OKX-perp crowding VETO. Kraken (the sole execution venue) is spot
and pays NO funding, so an unavailable rate is a lost minor filter, not an
unhedged cost — halting entries on a single-feed outage would starve trading.
Both engines default to PASSING the veto when funding is unavailable, disagree
no longer, and expose a knob for operators who want strict fail-closed. The
`funding_available` flag (set by the merge) is what distinguishes "genuinely ~0
funding" from "no funding source this cycle" — avg funding is 0.0 for both.
"""
from strategies.informed_flow import InformedFlowEngine
from strategies.signal_gates import SignalGateEngine


def _gate_view(**over):
    v = {"kraken_symbol": "ETH/USD", "liquidity_pool_usd": 1e9,
         "imbalance_ratio": 1.0, "funding_rate": 0.0,
         "candles": [{"time": i, "open": 100.0, "high": 100.1, "low": 99.9,
                      "close": 100.0, "volume": 10.0} for i in range(30)]}
    v.update(over)
    return v


# --- five_gate rollback engine ----------------------------------------------
def test_gate4_passes_when_funding_unavailable_by_default():
    eng = SignalGateEngine({})
    r = eng.evaluate_asset("ETH", _gate_view(funding_rate=0.0,
                                             funding_available=False))
    assert r.gates_passed["gate_4_funding_rate"] is True


def test_gate4_strict_fail_closed_when_configured():
    eng = SignalGateEngine({"gate_4_funding_rate": {"pass_when_unavailable": False}})
    r = eng.evaluate_asset("ETH", _gate_view(funding_available=False))
    assert r.gates_passed["gate_4_funding_rate"] is False


def test_gate4_still_vetoes_a_real_extreme_rate():
    # available + extreme funding must STILL fail the gate (the filter works)
    eng = SignalGateEngine({})
    r = eng.evaluate_asset("ETH", _gate_view(funding_rate=0.05,
                                             funding_available=True))
    assert r.gates_passed["gate_4_funding_rate"] is False


# --- deployed informed_flow engine ------------------------------------------
def test_informed_flow_reads_the_policy_flag():
    assert InformedFlowEngine({}).funding_pass_when_unavailable is True
    assert InformedFlowEngine(
        {"funding_pass_when_unavailable": False}).funding_pass_when_unavailable \
        is False


# --- merge sets funding_available honestly ----------------------------------
def test_merge_marks_funding_available_from_source_presence():
    from strategies.liquidity_model import LiquidityModel
    lm = LiquidityModel.__new__(LiquidityModel)   # real build_view, no full init
    lm.base_to_pair = {"ETH": "ETH/USD"}
    lm.imbalance_decay_bps = 0.0    # v8 knob build_view reads; irrelevant here

    def _src(funding):     # one OKX-style feed payload for ETH
        return {"ETH/USD": {"order_book": {"bids": [[100.0, 1.0]],
                                           "asks": [[100.1, 1.0]]},
                            "candles": [], "funding_rate": funding,
                            "volume_24h": 1.0}}

    # OKX supplies a rate -> available
    got = lm.build_view(_src(0.001))
    assert got["ETH"]["funding_available"] is True

    # perp feed down (funding_rate None, as Binance.US spot always returns) ->
    # no source, avg_funding falls back to 0.0 but the flag says UNAVAILABLE
    got2 = lm.build_view(_src(None))
    assert got2["ETH"]["funding_available"] is False
    assert got2["ETH"]["funding_rate"] == 0.0     # numeric consumers unaffected
