"""Gate-truth instrumentation T1: the informed-flow engine exposes its
component scores on the SignalResult so the realization path can grade
them (2026-07-28 audit: components were computed and discarded — the
weights were unfalsifiable)."""
import math

from strategies.signal_gates import SignalResult


def test_signalresult_components_defaults_empty():
    r = SignalResult(symbol="ETH/USD", direction=None, confidence=0.0,
                     size=0.0, all_confirmed=False)
    assert r.components == {}


def _view(n_bars=40, imb=1.4):
    candles = []
    px = 100.0
    for i in range(n_bars):
        px *= 1.003
        candles.append({"time": 1000 + i * 300, "open": px * 0.999,
                        "high": px * 1.002, "low": px * 0.997,
                        "close": px, "volume": 50.0 + (i % 5)})
    return {"kraken_symbol": "ETH/USD", "candles": candles,
            "imbalance_ratio": imb, "funding_rate": 0.0,
            "funding_available": True}


def test_informed_flow_populates_all_seven_keys():
    from strategies.informed_flow import InformedFlowEngine
    eng = InformedFlowEngine({})
    view = _view()
    for _ in range(6):                      # feed the EWMAs/persistence
        r = eng.evaluate_asset("ETH", view)
    assert set(r.components) == {"flow", "delta", "accum", "burst",
                                 "trend", "evidence", "conc"}
    assert all(isinstance(v, float) and math.isfinite(v)
               for v in r.components.values())
    # evidence is the fused sum the confirmation thresholds on — the
    # persisted value must be the same quantity (raw, signed)
    w = eng.w
    fused = sum(w[k] * r.components[k]
                for k in ("flow", "delta", "accum", "burst", "trend"))
    assert abs(fused - r.components["evidence"]) < 1e-9
    assert 0.0 <= r.components["conc"] <= 1.0


def test_warmup_return_has_empty_components():
    from strategies.informed_flow import InformedFlowEngine
    eng = InformedFlowEngine({})
    r = eng.evaluate_asset("ETH", _view(n_bars=3))     # < min_bars
    assert r.components == {}


def test_fault_path_has_empty_components():
    from strategies.informed_flow import InformedFlowEngine
    eng = InformedFlowEngine({})
    # a non-dict candle raises inside _evaluate (int has no .get) BEFORE
    # the warmup check - this exercises the fail-closed except branch,
    # which the warmup test above cannot reach
    r = eng.evaluate_asset("ETH", {"candles": [42]})
    assert r.components == {}
    assert r.direction is None and r.confidence == 0.0
    # discriminator: warmup returns {"v3_data_sufficiency": False}; the
    # fail-closed branch returns an EMPTY gates dict
    assert r.gates_passed == {}
