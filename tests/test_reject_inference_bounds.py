# tests/test_reject_inference_bounds.py
"""Synthetic-fixture tests for scripts/reject_inference_bounds.py.

Small, deterministic, no network, no real outputs/: a hand-built 1m
corpus (linear price path => closed-form forward returns), a real-writer
audit chain (census-test pattern), a synthetic fills.csv, and a manifest
that matches the parquets it describes. Hand-computed expectations pin
every number the script prints.
"""
import json

import pandas as pd

from core.audit import configure_audit, get_audit
from core.codes import Code
from core.fill_ledger import EXEC_ERA
from scripts.gradeability_census import CUT12_FLOOR
from scripts.reject_inference_bounds import (
    REFUSAL_CHAIN_TORN,
    REFUSAL_CORPUS_MISMATCH,
    REFUSAL_CORPUS_MISSING,
    REFUSAL_CORPUS_NO_COVERAGE,
    REFUSAL_INCONSISTENT,
    bounds_run,
)

# --- fixture geometry -------------------------------------------------------
# 20 days of 1m bars starting at the cut-#12 floor; the bar-i open is
# 100+i and its close 100+i+1 (linear walk), so a 60-bar forward gross
# return is exactly 61 / (100+i).  Horizon 60 min keeps the censored tail
# visible; fees 15+30 mirror the shipped pretrade keys.
T0 = CUT12_FLOOR                       # 2026-09-08T00:00:00Z
N_BARS = 20 * 24 * 60                  # 28,800 minutes
N_BARS_SHORT = 5 * 24 * 60             # tail-test corpus: ends 2026-09-13
P0 = 100.0
HORIZON_MIN = 60
FEE_RT_BPS = 45.0


def _corpus(tmp_path, n_bars=N_BARS, tamper_manifest=False):
    cdir = tmp_path / "corpus"
    cdir.mkdir(exist_ok=True)
    quality = {}
    for base in ("BTC", "ETH"):
        sym = f"{base}USDT"
        ot = [int(T0 * 1000) + i * 60_000 for i in range(n_bars)]
        df = pd.DataFrame({
            "open_time": ot,
            "open": [P0 + i for i in range(n_bars)],
            "close": [P0 + i + 1 for i in range(n_bars)],
        })
        df.to_parquet(cdir / f"klines_1m_{sym}.parquet")
        first = pd.Timestamp(ot[0], unit="ms", tz="UTC")
        last = pd.Timestamp(ot[-1], unit="ms", tz="UTC")
        quality[sym] = {
            "rows_1m": n_bars + (1 if tamper_manifest else 0),
            "first": str(first).replace("T", " "),
            "last": str(last).replace("T", " "),
            "parquet_1m": f"klines_1m_{sym}.parquet",
        }
    (cdir / "manifest.json").write_text(json.dumps({"quality": quality}))
    return cdir


def _config(tmp_path):
    cfg = {
        "pretrade": {"maker_fee_bps": 15.0, "taker_fee_bps": 30.0},
        "ml": {"label_max_bars": HORIZON_MIN // 5},   # x300s => 60 min
        "exchanges": {"kraken": {"trading_pairs": ["BTC/USD", "ETH/USD"]}},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg))
    return path


def _audit(tmp_path):
    """Real records, real chain, via the engine's own writer (census-test
    pattern). Two EN-000 ticks: +4 arrivals then +4 (3 EN-030 each hour),
    one CV-010 denial carrying asset+edge, one DE-010 batch whose event
    sits at bar 2 with decision_mid == that bar's open."""
    configure_audit(tmp_path / "audit.jsonl")
    a = get_audit()
    a.log("startup", Code.CG_SESSION_START, "session start: config fingerprint",
          {"config_sha256": "x", "dry_run": True}, counted=False)
    a.log("entry_sweep", Code.EN_SWEEP_SUMMARY, "v1",
          {"arrivals": 4, "EN-030": 3}, counted=False)
    a.log("entry_sweep", Code.EN_SWEEP_SUMMARY, "v2",
          {"arrivals": 8, "EN-030": 6}, counted=False)
    a.log("conviction", Code.CV_AGREEMENT_LOW, "CV-010: ETH denied",
          {"asset": "ETH", "est_edge_bps": 68.75, "est_cost_bps": 63.04},
          counted=False)
    a.log("entry_sweep", Code.DE_DECISION_EVENTS, "DE-010: hourly batch",
          {"events": [{"asset": "BTC", "ts": T0 + 120.0,
                       "decision_mid": "102.0", "mid_available": True,
                       "direction": "", "absorb": "EN-030",
                       "confidence": "", "gates": {}}]}, counted=False)
    return tmp_path / "audit.jsonl"


def _fills(tmp_path):
    """One era-stamped priced entry (the gradeable stratum, g=1), a long
    filled at bar 1."""
    path = tmp_path / "fills.csv"
    path.write_text(
        "ts,order_id,position_id,purpose,symbol,side,ordertype,post_only,"
        "attempt,fill_size,fill_price,arrival_ref,slip_bps,fees_delta_usd,"
        "remaining,reason,exec_era,book\n"
        f"{T0 + 60.0},o1,p1,entry,BTC/USD,buy,limit,true,1,0.01,101.0,"
        f"101.0,0.0,0.0,0.0,,{EXEC_ERA},5m\n")
    return path


def _net_long_bps(i0):
    """Hand-computed: enter open of bar i0 (100+i0), exit close of bar
    i0+60 (100+i0+61) => gross 61/(100+i0), net of the 45 bps round trip."""
    return 61.0 / (P0 + i0) * 1e4 - FEE_RT_BPS


def _run(tmp_path, *, audit_path=None, fills_path=None, corpus_dir=None,
         config_path=None, since=T0, n_bars=N_BARS):
    return bounds_run(
        audit_path=audit_path or _audit(tmp_path),
        fills_path=fills_path or _fills(tmp_path),
        corpus_dir=corpus_dir or _corpus(tmp_path, n_bars),
        config_path=config_path or _config(tmp_path),
        since=since)


# --- tests ------------------------------------------------------------------

def test_happy_path_strata_and_dr(tmp_path):
    out = _run(tmp_path)
    assert out["refused"] is None
    assert out["arrivals"] == 8
    s = out["strata"]
    assert s["lost_forever"]["n"] == 6           # EN-030 deltas
    assert s["deep_pipeline"]["n"] == 8 - 6 - 1  # residual = 1
    assert s["gradeable"]["n"] == 1
    assert s["cv_with_asset"]["n"] == 1
    assert s["de010_captured"]["n"] == 1
    # gradeable: entry at T0+60 => bar 1, long. propensity 1.0 under the
    # deterministic policy => DR estimate == the realized mean
    assert s["gradeable"]["dr_taken_mean_bps"] == round(_net_long_bps(1), 2)
    assert s["gradeable"]["propensity_taken"] == 1.0
    # unconditional era bound over minutes 0..N_BARS-1-H, both directions,
    # both assets (identical paths): best = long at bar 0 (lowest base =>
    # largest favorable move), worst = short at bar 0 (same 61% move is
    # adverse for a short, then the round trip comes out twice: once in
    # the gross sign flip, once as the fee)
    eb = out["era_bound_bps"]
    assert eb["best"] == round(_net_long_bps(0), 2)
    assert eb["worst"] == round(-(_net_long_bps(0) + FEE_RT_BPS)
                                - FEE_RT_BPS, 2)
    # fee/horizon derived from the fixture config, never struck
    assert out["fee_rt_bps"] == FEE_RT_BPS
    assert out["horizon_minutes"] == HORIZON_MIN


def test_de010_event_widened_both_directions(tmp_path):
    """The DE-010 event carries ts+asset+decision_mid but NO direction:
    the bound must be [min(L,S), max(L,S)] of the realized path priced at
    decision_mid, never a fabricated side."""
    out = _run(tmp_path)
    de = out["strata"]["de010_captured"]
    assert de["covered"] == 1 and de["censored"] == 0
    # event ts = bar 2, decision_mid 102.0 == bar-2 open; exit close of
    # bar 62 = 163.0
    gross = (163.0 - 102.0) / 102.0 * 1e4
    nl, ns = gross - FEE_RT_BPS, -gross - FEE_RT_BPS
    assert de["mean_bound"]["worst"] == round(min(nl, ns), 2)
    assert de["mean_bound"]["best"] == round(max(nl, ns), 2)


def test_uncovered_tail_counted_not_imputed(tmp_path):
    """EN-000 ticks past the last full-horizon minute attribute their
    arrival deltas to the UNMEASURABLE tail line: with a corpus ending
    2026-09-13, the writer-clock ticks (later) land entirely in the tail
    while the early gradeable fill stays covered."""
    out = _run(tmp_path, n_bars=N_BARS_SHORT)
    assert out["refused"] is None
    assert out["arrivals_tail_uncovered"] == 8
    assert out["arrivals_in_covered_window"] == 0
    assert out["strata"]["gradeable"]["covered"] == 1
    assert out["strata"]["cv_with_asset"]["censored"] == 1
    # the era bound still stands on the covered corpus minutes
    assert out["era_bound_bps"]["best"] == round(_net_long_bps(0), 2)


def test_refuses_torn_chain(tmp_path):
    audit = _audit(tmp_path)
    lines = audit.read_text().splitlines()
    rec = json.loads(lines[-2])
    rec["data"]["arrivals"] = 999              # tamper: breaks its own h
    lines[-2] = json.dumps(rec)
    audit.write_text("\n".join(lines) + "\n")
    out = _run(tmp_path, audit_path=audit)
    assert out["refused"] == REFUSAL_CHAIN_TORN


def test_refuses_manifest_mismatch(tmp_path):
    cdir = _corpus(tmp_path, tamper_manifest=True)
    out = _run(tmp_path, corpus_dir=cdir)
    assert out["refused"] == REFUSAL_CORPUS_MISMATCH


def test_refuses_missing_corpus(tmp_path):
    cdir = _corpus(tmp_path)
    (cdir / "klines_1m_ETHUSDT.parquet").unlink()
    out = _run(tmp_path, corpus_dir=cdir)
    assert out["refused"] == REFUSAL_CORPUS_MISSING


def test_refuses_zero_overlap(tmp_path):
    """An era window entirely after the corpus end is a clean refusal
    class (coverage, or the census's own no-ticks refusal upstream),
    never a traceback or a silently empty bound."""
    out = _run(tmp_path, since=T0 + (N_BARS + 10_000) * 60.0)
    assert out["refused"] in (REFUSAL_CORPUS_NO_COVERAGE,
                              REFUSAL_INCONSISTENT, "NO_EN000_IN_WINDOW")


def test_refuses_unreadable_audit(tmp_path):
    out = _run(tmp_path, audit_path=tmp_path / "nope.jsonl")
    assert out["refused"] in ("AUDIT_UNREADABLE", REFUSAL_INCONSISTENT)


def test_never_fabricates_direction(tmp_path):
    """A gradeable fill with an unknown side contributes no taken value -
    the DR mean runs over KNOWN directions only; the field is widened,
    not invented."""
    fills = _fills(tmp_path)
    fills.write_text(fills.read_text().replace(",buy,", ",mystery,"))
    out = _run(tmp_path, fills_path=fills)
    assert out["strata"]["gradeable"]["n"] == 1
    assert out["strata"]["gradeable"]["covered"] == 1
    assert out["strata"]["gradeable"]["dr_taken_mean_bps"] is None
