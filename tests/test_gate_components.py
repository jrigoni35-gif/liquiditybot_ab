"""Gate-truth instrumentation T1: the informed-flow engine exposes its
component scores on the SignalResult so the realization path can grade
them (2026-07-28 audit: components were computed and discarded — the
weights were unfalsifiable)."""
import csv
import math

import numpy as np

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


# ---- Task 2: history schema +7 sg_* telemetry columns --------------------


def _mk_store(tmp_path):
    from ml.history import HistoryStore
    return HistoryStore(str(tmp_path / "hist.csv"))


def _feats():
    from ml.features import FEATURE_NAMES
    return np.zeros(len(FEATURE_NAMES))


SG = {"flow": 0.5, "delta": -0.25, "accum": 0.1, "burst": 0.0,
      "trend": 0.33, "evidence": 0.91, "conc": 0.4}


def test_header_gains_seven_sg_columns_last(tmp_path):
    hs = _mk_store(tmp_path)
    assert hs._header[-7:] == ["sg_flow", "sg_delta", "sg_accum",
                               "sg_burst", "sg_trend", "sg_evidence",
                               "sg_conc"]
    assert hs._header[-9:-7] == ["pt_frac", "sl_frac"]   # order preserved


def test_append_row_writes_components_and_defaults_zero(tmp_path):
    hs = _mk_store(tmp_path)
    hs._append_row("p1", "ETH", "long", _feats(), 1, 0.0, "candidate",
                   gate_components=SG)
    hs._append_row("p2", "ETH", "long", _feats(), 0, 0.0, "candidate")
    rows = list(csv.DictReader(open(hs.path, encoding="utf-8")))
    assert rows[0]["sg_flow"] == "0.5000"
    assert rows[0]["sg_delta"] == "-0.2500"
    assert rows[0]["sg_evidence"] == "0.9100"
    assert rows[1]["sg_flow"] == "0.0000"          # default: uninstrumented


def test_nonfinite_component_sanitizes_never_drops(tmp_path):
    hs = _mk_store(tmp_path)
    bad = dict(SG, flow=float("nan"), conc=float("inf"))
    hs._append_row("p3", "ETH", "long", _feats(), 1, 0.0, "candidate",
                   gate_components=bad)
    rows = list(csv.DictReader(open(hs.path, encoding="utf-8")))
    assert len(rows) == 1                          # row kept
    assert rows[0]["sg_flow"] == "0.0000"
    assert rows[0]["sg_conc"] == "0.0000"
    assert rows[0]["sg_delta"] == "-0.2500"        # good keys survive


def test_live_row_carries_components_via_pending_tuple(tmp_path):
    hs = _mk_store(tmp_path)
    hs.log_entry("pos9", "ETH", "short", _feats(), probe=True,
                 candidate_id="cand-1", book="5m", gate_components=SG)
    hs.log_close("pos9", -1.25, barrier="tb_sl")
    rows = list(csv.DictReader(open(hs.path, encoding="utf-8")))
    assert rows[0]["source"] == "live" and rows[0]["barrier"] == "tb_sl"
    assert rows[0]["sg_flow"] == "0.5000"
    assert rows[0]["sg_trend"] == "0.3300"


def test_legacy_pending_tuple_shapes_still_close(tmp_path):
    # a pre-instrumentation snapshot restores 7-element pending tuples —
    # closing one must still write a row (sg_* all zero)
    hs = _mk_store(tmp_path)
    hs._pending["old1"] = ("ETH", "long", _feats(), 123.0, False, "", "5m")
    hs.log_close("old1", 2.0)
    rows = list(csv.DictReader(open(hs.path, encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["sg_flow"] == "0.0000"


# ---- Task 3: candidate-path threading (register -> _emit_label) ---------


def test_candidate_row_carries_components_through_labeler(tmp_path):
    """register(gate_components=...) -> poll() -> the persisted candidate
    row carries the scores; a candidate registered without them writes
    zeros. Drives CandidateLabeler directly with the same register() /
    update_candles() / poll() idiom as
    tests/test_early_labeling.py::test_barrier_hit_labels_immediately (a
    pt/sl barrier touch inside the window is early-decidable, so both
    candidates label on the first poll() - no need to feed a full horizon
    of bars)."""
    from ml.history import CandidateLabeler, HistoryStore
    cfg = {"label_max_bars": 96, "label_pt_vol_mult": 8.0,
           "label_sl_vol_mult": 6.0, "label_round_trip_cost_pct": 0.1,
           "label_include_spread": False}
    store = HistoryStore(str(tmp_path / "hist.csv"))
    lab = CandidateLabeler(store, cfg)
    feats = _feats()
    lab.register("ETH", "long", feats, 0.005, 0,
                 gates_passed={"g": True}, gate_components=SG)
    lab.register("SOL", "short", feats, 0.005, 0)   # no components: legacy
    # bar 5 jumps +5.5% -> a barrier touch for either direction, decidable
    # immediately (see ml/history.py CandidateLabeler.poll's EARLY
    # DECIDABILITY note) - only 10 of 96 horizon bars needed
    bars = [{"time": k * 300, "open": 100.0, "close": 100.0,
             "high": 105.5 if k >= 5 else 100.01, "low": 99.99}
            for k in range(10)]
    lab.update_candles("ETH", bars)
    lab.update_candles("SOL", bars)
    wrote = lab.poll()
    # the +5.5% high is a barrier touch for BOTH (ETH long pt at +4%,
    # SOL short sl at +3%) - both label on this one poll, so the legacy
    # zero-assertion below can never silently skip (T3 review ⚠️)
    assert wrote == 2
    rows = list(csv.DictReader(open(store.path, encoding="utf-8")))
    by_asset = {r["asset"]: r for r in rows}
    assert by_asset["ETH"]["sg_flow"] == "0.5000"
    assert by_asset["ETH"]["sg_conc"] == "0.4000"
    assert by_asset["SOL"]["sg_flow"] == "0.0000"
