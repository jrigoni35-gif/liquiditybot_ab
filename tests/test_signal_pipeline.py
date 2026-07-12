"""Signal-pipeline data-integrity fixes (verified against live behavior):

1. SignalGateEngine silently ran on DEFAULTS: main passes the full config but
   the gate blocks live nested under config["signal_gates"] - every configured
   threshold was ignored on the rollback path. Now accepts both shapes.
2. The rollback engine trusted input shape: funding_rate=None crashed abs(),
   malformed candles raised KeyError into the trading cycle, non-finite values
   flowed into gate math. Now fail-closed like informed_flow.
3. CandidateLabeler registered the same (asset, direction, bar) every slow
   cycle while a signal stayed confirmed - duplicate near-identical training
   rows overweighting one candle. Now deduped per bar, persisted.
4. LiquidityModel.build_view was hardcoded to exactly two feeds, leaving the
   config-declared ccxt adapter unwired. Now source-agnostic.
"""
import numpy as np

from ml.history import CandidateLabeler, HistoryStore
from strategies.liquidity_model import LiquidityModel
from strategies.signal_gates import SignalGateEngine


def _candles(n=30, close=100.0, vol=10.0):
    return [{"time": i, "open": close, "high": close * 1.001,
             "low": close * 0.999, "close": close, "volume": vol}
            for i in range(n)]


def _view(**over):
    v = {"kraken_symbol": "ETH/USD", "liquidity_pool_usd": 1e9,
         "imbalance_ratio": 1.0, "funding_rate": 0.0,
         "candles": _candles()}
    v.update(over)
    return v


# --- 1: nested-config regression -------------------------------------------
def test_nested_signal_gates_config_is_honored():
    full_config = {"signal_gates": {
        "gate_1_liquidity_pool": {"enabled": True,
                                  "min_pool_size_usd": 5_000_000}}}
    eng = SignalGateEngine(full_config)          # full config, as main.py passes
    r = eng.evaluate_asset("ETH", _view(liquidity_pool_usd=1_000_000))
    assert r.gates_passed["gate_1_liquidity_pool"] is False   # threshold applied


def test_flat_config_still_works():
    eng = SignalGateEngine({"gate_1_liquidity_pool": {
        "enabled": True, "min_pool_size_usd": 5_000_000}})
    r = eng.evaluate_asset("ETH", _view(liquidity_pool_usd=1_000_000))
    assert r.gates_passed["gate_1_liquidity_pool"] is False


# --- 2: fail-closed input boundary ------------------------------------------
def test_none_funding_fails_closed_not_crash():
    r = SignalGateEngine({}).evaluate_asset("ETH", _view(funding_rate=None))
    assert r.all_confirmed is False
    assert r.gates_passed["gate_4_funding_rate"] is False


def test_malformed_candles_never_raise():
    bad = _view(candles=[{"time": 1}, {"close": float("nan")}, "garbage",
                         {"close": 100.0, "volume": None}])
    r = SignalGateEngine({}).evaluate_asset("ETH", bad)
    assert r.all_confirmed is False               # fails closed, no exception


def test_nonfinite_imbalance_fails_closed():
    r = SignalGateEngine({}).evaluate_asset(
        "ETH", _view(imbalance_ratio=float("nan")))
    assert r.gates_passed["gate_2_order_book_imbalance"] is False


def test_completely_empty_view_fails_closed():
    r = SignalGateEngine({}).evaluate_asset("ETH", {})
    assert r.all_confirmed is False and r.direction is None


# --- 3: candidate de-duplication ---------------------------------------------
def _labeler(tmp_path):
    return CandidateLabeler(HistoryStore(str(tmp_path / "h.csv")), {})


def test_same_bar_registers_once(tmp_path):
    lab = _labeler(tmp_path)
    feats = np.zeros(4)
    for _ in range(6):                            # 6 slow cycles, one candle
        lab.register("ETH", "long", feats, 0.004, bar_time=100)
    assert len(lab._cands) == 1


def test_new_bar_or_direction_registers_again(tmp_path):
    lab = _labeler(tmp_path)
    feats = np.zeros(4)
    lab.register("ETH", "long", feats, 0.004, bar_time=100)
    lab.register("ETH", "long", feats, 0.004, bar_time=105)   # next candle
    lab.register("ETH", "short", feats, 0.004, bar_time=105)  # other side
    lab.register("BTC", "long", feats, 0.004, bar_time=100)   # other asset
    assert len(lab._cands) == 4


def test_dedup_state_survives_snapshot_roundtrip(tmp_path):
    lab = _labeler(tmp_path)
    # restore's ML-013 width filter drops non-schema candidates, so the
    # roundtrip must carry a current-width vector to survive it
    from ml.features import FEATURE_NAMES
    feats = np.zeros(len(FEATURE_NAMES))
    lab.register("ETH", "long", feats, 0.004, bar_time=100)
    lab2 = _labeler(tmp_path)
    lab2.restore(lab.to_dict())
    lab2.register("ETH", "long", feats, 0.004, bar_time=100)  # post-restart dup
    assert len(lab2._cands) == 1


# --- 4: source-agnostic market view -----------------------------------------
def _feed(sym, px=2000.0):
    return {sym: {"order_book": {"bids": [[px, 1.0]], "asks": [[px + 1, 1.0]]},
                  "candles": _candles(20, close=px), "funding_rate": 0.0001,
                  "volume_24h": 1e6}}


def test_build_view_merges_any_number_of_sources():
    lm = LiquidityModel({})
    v2 = lm.build_view(_feed("ETH-USDT"), _feed("ETHUSD"))
    v3 = lm.build_view(_feed("ETH-USDT"), _feed("ETHUSD"), _feed("ETH/USDT:USDT"))
    assert "ETH" in v2 and "ETH" in v3
    assert v3["ETH"]["volume_24h"] > v2["ETH"]["volume_24h"]   # third source counted
    assert lm.build_view() == {}                               # degenerate: empty
