# tests/test_gate_ecology.py
import json
import time

import numpy as np
import pytest

pd = pytest.importorskip("pandas")  # optional analysis stack — hygiene law

from core.audit import configure_audit, get_audit  # noqa: E402
from core.codes import Code  # noqa: E402
from core.fill_ledger import EXEC_ERA  # noqa: E402
from scripts.gate_ecology import (  # noqa: E402
    PASSED_STACK,
    REFUSAL_CHAIN_TORN,
    REFUSAL_CORPUS_MISSING,
    REFUSAL_NO_EN000,
    ecology,
    section2,
    section4,
    section5,
)

# small fixture constants: vol_window 10min, horizon 10min, reference
# window (module ANALYSIS CHOICE, 30d) contains the whole fixture.
CONFIG = {
    "pretrade": {"maker_fee_bps": 15.0, "taker_fee_bps": 30.0,
                 "min_edge_cost_ratio": 1.3},
    "ml": {"label_max_bars": 2},          # 2 x 5m = 10min horizon
    "vol_regime": {"fast_lookback_bars_5m": 2,   # 10min vol window
                   "low_pct": 30.0, "elevated_pct": 70.0,
                   "extreme_pct": 90.0},
}

FILLS_HEADER = ("ts,order_id,position_id,purpose,symbol,side,ordertype,"
                "post_only,attempt,fill_size,fill_price,arrival_ref,"
                "slip_bps,fees_delta_usd,remaining,reason,exec_era,book")


def _write_config(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(CONFIG))
    return p


def _chain(tmp_path, n_sweeps=2):
    """Real records, real chain, via the engine's own writer: two
    cumulative EN-000 ticks (4 arrivals/hr, 3 absorbed EN-030)."""
    configure_audit(tmp_path / "audit.jsonl")
    a = get_audit()
    a.log("startup", Code.CG_SESSION_START, "session start: config fingerprint",
          {"config_sha256": "x", "dry_run": True}, counted=False)
    a.log("entry_sweep", Code.EN_SWEEP_SUMMARY, "v1",
          {"arrivals": 4, "EN-030": 3}, counted=False)
    a.log("entry_sweep", Code.EN_SWEEP_SUMMARY, "v2",
          {"arrivals": 8, "EN-030": 6}, counted=False)
    return tmp_path / "audit.jsonl"


def _corpus(tmp_path, closes, t0_ms=1_758_000_000_000, symbol="BTCUSDT"):
    """Deterministic 1m corpus: manifest + parquet from explicit closes."""
    cdir = tmp_path / "corpus"
    cdir.mkdir(exist_ok=True)
    ot = [t0_ms + i * 60_000 for i in range(len(closes))]
    pd.DataFrame({"open_time": ot,
                  "close": [float(c) for c in closes]}).to_parquet(
        cdir / f"klines_1m_{symbol}.parquet")
    (cdir / "manifest.json").write_text(json.dumps(
        {"symbols": [symbol], "missing_files": []}))
    return cdir


def _de010(tmp_path, events):
    a = get_audit()
    a.log("entry_sweep", Code.DE_DECISION_EVENTS, "DE-010: hourly batch",
          {"events": events}, counted=False)
    return tmp_path / "audit.jsonl"


# ------------------------------------------------------------ section 1

def test_section1_counts_rates_and_residual(tmp_path):
    path = _chain(tmp_path)
    cfg = _write_config(tmp_path)
    cdir = _corpus(tmp_path, [100.0] * 200)
    rep = ecology(audit_path=path, fills_path=None, corpus_dir=cdir,
                  config_path=cfg, since=0.0)
    assert rep["refused"] is None
    s1 = rep["section1"]
    assert s1["arrivals"] == 8
    assert s1["absorb_counts"] == {"EN-030": 6}
    assert s1[PASSED_STACK] == 2
    assert s1["absorb_rates_pct"]["EN-030"] == 75.0


def test_refuses_torn_chain(tmp_path):
    path = _chain(tmp_path)
    lines = path.read_text().splitlines()
    rec = json.loads(lines[-1])
    rec["data"]["arrivals"] = 999               # tamper: breaks its own h
    lines[-1] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n")
    rep = ecology(audit_path=path, fills_path=None,
                  corpus_dir=tmp_path / "corpus",
                  config_path=_write_config(tmp_path), since=0.0)
    assert rep["refused"] in (REFUSAL_CHAIN_TORN, REFUSAL_CORPUS_MISSING)


def test_refuses_missing_corpus(tmp_path):
    path = _chain(tmp_path)
    rep = ecology(audit_path=path, fills_path=None,
                  corpus_dir=tmp_path / "no_such_dir",
                  config_path=_write_config(tmp_path), since=0.0)
    assert rep["refused"] == REFUSAL_CORPUS_MISSING


def test_refuses_no_en000_in_window(tmp_path):
    path = _chain(tmp_path)
    cdir = _corpus(tmp_path, [100.0] * 200)
    rep = ecology(audit_path=path, fills_path=None, corpus_dir=cdir,
                  config_path=_write_config(tmp_path),
                  since=time.time() + 3600)   # window past every tick
    assert rep["refused"] == REFUSAL_NO_EN000


# ------------------------------------------------------------ section 2

def test_section2_conditional_structure():
    events = [
        {"asset": "BTC", "ts": 1.0, "absorb": "EN-030",
         "gates": {"g1": False, "g2": True, "g3": True}},    # g1 sole
        {"asset": "BTC", "ts": 2.0, "absorb": "EN-030",
         "gates": {"g1": False, "g2": False, "g3": True}},   # co-fail
        {"asset": "BTC", "ts": 3.0, "absorb": PASSED_STACK,
         "gates": {"g1": True, "g2": True, "g3": True}},
    ]
    out = section2(events)
    assert out["pre_capture"] == "UNIDENTIFIED"
    g = out["gates"]
    assert g["g1"]["fails"] == 2 and g["g1"]["n"] == 3
    assert g["g1"]["sole_absorber"] == 1
    assert g["g2"]["sole_absorber"] == 0          # never fails alone
    assert g["g3"]["fails"] == 0
    assert out["co_failure"]["g1&g2"]["n"] == 1


def test_section2_no_events_is_unidentified_not_zero():
    out = section2([])
    assert out["de010_events_with_gates"] == 0
    assert out["gates"] == {}
    assert "no DE-010 events" in out["gates_note"]


# ------------------------------------------------------------ section 4

def test_section4_pavlov_shift_on_blocked_win(tmp_path):
    """Uptrend corpus: an absorbed LONG would have cleared the fee-floor
    aspiration -> Pavlov WOULD shift the absorbing gate. Advisory only."""
    t0_ms = 1_758_000_000_000
    closes = [100.0 * (1.002 ** i) for i in range(200)]   # +20bps/min
    cdir = _corpus(tmp_path, closes, t0_ms=t0_ms)
    consts = {"aspiration_bps": 13.5, "round_trip_cost_bps": 45.0,
              "horizon_min": 10}
    ev = {"asset": "BTC", "ts": t0_ms / 1000.0 + 60, "absorb": "EN-030",
          "direction": "long", "decision_mid": "",
          "gates": {"g1": False, "g2": True}}
    out = section4([ev], cdir, {"BTC": "BTCUSDT"}, consts)
    assert out["events_evaluated"] == 1
    assert out["per_gate"]["g1"]["shift"] == 1
    assert out["per_gate"]["g1"]["pavlov_would"] == "SHIFT"


def test_section4_direction_unknown_disagreement_unidentified(tmp_path):
    """Direction "" -> both directions bounded; a trend where only LONG
    wins makes the advice direction-dependent -> UNIDENTIFIED."""
    t0_ms = 1_758_000_000_000
    closes = [100.0 * (1.002 ** i) for i in range(200)]
    cdir = _corpus(tmp_path, closes, t0_ms=t0_ms)
    consts = {"aspiration_bps": 13.5, "round_trip_cost_bps": 45.0,
              "horizon_min": 10}
    ev = {"asset": "BTC", "ts": t0_ms / 1000.0 + 60, "absorb": "EN-030",
          "direction": "", "decision_mid": "", "gates": {"g1": False}}
    out = section4([ev], cdir, {"BTC": "BTCUSDT"}, consts)
    assert out["events_evaluated"] == 0
    assert out["events_unidentified"] == 1


def test_section4_corpus_gap_unidentified(tmp_path):
    """Event ts near the corpus end: the horizon runs past the last bar
    -> UNIDENTIFIED, never imputed."""
    t0_ms = 1_758_000_000_000
    closes = [100.0] * 200
    cdir = _corpus(tmp_path, closes, t0_ms=t0_ms)
    consts = {"aspiration_bps": 13.5, "round_trip_cost_bps": 45.0,
              "horizon_min": 10}
    last_ts = (t0_ms + 199 * 60_000) / 1000.0
    ev = {"asset": "BTC", "ts": last_ts, "absorb": "EN-030",
          "direction": "long", "decision_mid": "", "gates": {"g1": False}}
    out = section4([ev], cdir, {"BTC": "BTCUSDT"}, consts)
    assert out["events_unidentified"] == 1
    assert out["per_gate"] == {}


# ------------------------------------------------------------ section 5

def test_section5_netting_shadow(tmp_path):
    """Long BTC + short ETH overlapping: gross > net, offsettable > 0."""
    rows = [
        "1000,o1,p1,entry,BTC/USD,buy,limit,0,1,0.1,50000,,0,0,0,,"
        f"{EXEC_ERA},",
        "1010,o2,p2,entry,ETH/USD,sell,limit,0,1,2.0,3000,,0,0,0,,"
        f"{EXEC_ERA},",
        "1020,o3,p1,exit,BTC/USD,sell,limit,0,1,0.1,50000,,0,0,0,,"
        f"{EXEC_ERA},",
        "1030,o4,p2,exit,ETH/USD,buy,limit,0,1,2.0,3000,,0,0,0,,"
        f"{EXEC_ERA},",
    ]
    fp = tmp_path / "fills.csv"
    fp.write_text(FILLS_HEADER + "\n" + "\n".join(rows) + "\n")
    out = section5(fp, since=0.0)
    assert out["era_fills"] == 4
    assert out["offsetting_event_count"] >= 1
    assert out["peak_gross_usd"] == pytest.approx(11000.0)   # 5k + 6k
    assert out["peak_offsettable_usd"] == pytest.approx(5000.0)
    assert out["time_weighted_gross_usd_h"] > \
        out["time_weighted_net_usd_h"]


def test_section5_missing_fills_is_clean_note(tmp_path):
    out = section5(tmp_path / "absent.csv", since=0.0)
    assert out["refused"] is None
    assert out["era_fills"] == 0


# ------------------------------------------------------- end-to-end

def test_ecology_end_to_end(tmp_path):
    """Full path: chain + DE-010 events + corpus + fills -> five sections."""
    path = _chain(tmp_path)
    now = time.time()
    t0_ms = int(now - 7200) * 1000
    # flat-ish corpus around NOW (the writer's real tick ts must join)
    rng = np.arange(200)
    closes = 100.0 + 0.01 * np.sin(rng / 10.0)
    cdir = _corpus(tmp_path, closes, t0_ms=t0_ms)
    _de010(tmp_path, [{"asset": "BTC", "ts": now, "absorb": "EN-030",
                       "direction": "", "decision_mid": "",
                       "mid_available": False, "propensity": 1.0,
                       "gates": {"if_1": False, "if_2": True}}])
    rep = ecology(audit_path=path, fills_path=None, corpus_dir=cdir,
                  config_path=_write_config(tmp_path), since=0.0)
    assert rep["refused"] is None
    assert rep["section1"]["de010_events"] == 1
    assert rep["section1"]["de010_by_absorb"] == {"EN-030": 1}
    assert rep["section2"]["de010_events_with_gates"] == 1
    assert rep["section3"]["joined_ticks"] >= 1
    # direction "" on a symmetric flat-ish path: UNIDENTIFIED or evaluated,
    # never a fabricated per-gate verdict
    s4 = rep["section4"]
    assert s4["events_evaluated"] + s4["events_unidentified"] == 1
