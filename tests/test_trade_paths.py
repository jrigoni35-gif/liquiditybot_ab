"""The complete trade-path ledger (outputs/trade_paths.csv) - winners
included.

THE CENSORING THIS CLOSES: postmortem_summary.csv records only trades that
UNDERPERFORMED entry-time EV, so the excursion paths of winning trades - the
MAE envelope of trades that PAID, the one distribution any evidence-derived
stop geometry needs - were computed by _excursions and discarded (15
positive rows in 266; the winners' heat profile did not exist on disk).
trade_paths.csv records every finalized close; the summary keeps its
underperformer semantics byte-untouched.
"""
from __future__ import annotations

import csv

from ml.postmortem import PATHS_COLS, PostmortemEngine, TradeThesis


def _engine(tmp_path):
    return PostmortemEngine({
        "summary_path": str(tmp_path / "postmortem_summary.csv"),
        "paths_path": str(tmp_path / "trade_paths.csv"),
        "report_dir": str(tmp_path / "postmortems"),
        "observe_minutes": 0.0,          # finalize immediately on poll
        "mark_sample_sec": 0.0,
    })


def _thesis(pid, expected=0.5):
    return TradeThesis(position_id=pid, asset="ADA", symbol="ADA/USD",
                       direction="long", entry_ts=1000.0, p_win=0.6,
                       expected_ret_pct=expected, expected_cost_bps=50.0,
                       stop_pct=1.5, target_pct=2.0, fair_value=1.0,
                       quote_price=1.0, price_decimals=4,
                       entry_regime="bull_quiet", entry_liq="core",
                       narrative_label="", model_scored=True)


def _run_trade(eng, pid, expected, realized_usd, marks):
    t = _thesis(pid, expected=expected)
    eng.register_entry(t)
    eng.note_fill(pid, 1.0)
    for i, px in enumerate(marks):
        eng.record_marks({"ADA/USD": px}, 1000.0 + 30.0 * (i + 1))
    eng.on_close(pid, realized_usd, fees_usd=0.05, entry_usd=100.0,
                 stopped_out=False, exit_regime="bull_quiet",
                 exit_liq="core", now=5000.0)
    return eng.poll(10_000.0)


def _read(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_winner_reaches_paths_but_not_summary(tmp_path):
    eng = _engine(tmp_path)
    # realized +1% vs expected +0.5%: OVERperformed - no postmortem trigger
    _run_trade(eng, "win1", expected=0.5, realized_usd=1.0,
               marks=[1.002, 1.008, 1.012])
    paths = _read(tmp_path / "trade_paths.csv")
    assert len(paths) == 1
    assert paths[0]["position_id"] == "win1"
    assert paths[0]["cause"] == "", "a performing trade's cause is EMPTY"
    assert float(paths[0]["mfe_pct"]) > 0
    assert not (tmp_path / "postmortem_summary.csv").exists(), \
        "the summary's underperformer semantics must stay untouched"


def test_underperformer_reaches_both(tmp_path):
    eng = _engine(tmp_path)
    # realized -2% vs expected +0.5%: trigger fires
    _run_trade(eng, "loss1", expected=0.5, realized_usd=-2.0,
               marks=[1.001, 0.995, 0.985])
    paths = _read(tmp_path / "trade_paths.csv")
    summary = _read(tmp_path / "postmortem_summary.csv")
    assert len(paths) == 1 and len(summary) == 1
    assert paths[0]["cause"] == summary[0]["cause"] != ""
    # the path row carries the same excursions the summary attributes from
    assert paths[0]["mae_pct"] == summary[0]["mae_pct"]


def test_column_pin_and_winner_mae_is_the_point(tmp_path):
    eng = _engine(tmp_path)
    # a winner that took real heat first: dips to -1.5% then pays
    _run_trade(eng, "heat1", expected=0.2, realized_usd=0.8,
               marks=[0.995, 0.985, 1.005, 1.010])
    rows = _read(tmp_path / "trade_paths.csv")
    assert list(rows[0].keys()) == PATHS_COLS
    mae = float(rows[0]["mae_pct"])
    assert mae < -1.0, (
        f"the winner's adverse excursion ({mae}) is the quantity the old "
        f"ledgers discarded - it must survive here")
    assert float(rows[0]["realized_pct"]) > 0


def test_smoke_test_postmortem_harness_is_isolated():
    """Tenth QA-writes-production instance (2026-08-11): scripts/smoke_test.py
    built its PostmortemEngine without paths_path, so 2602371b's unconditional
    poll()-time ledger write sent pm1/pm2 fixture rows (synthetic clock,
    ts~1e6) into outputs/trade_paths.csv. The conftest tripwire runs only
    under pytest and can never see smoke_test - so this pin checks the
    harness source, and smoke_test carries its own synthetic-clock tripwire
    for everything the pin can't anticipate."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "scripts"
           / "smoke_test.py").read_text(encoding="utf-8")
    assert "PostmortemEngine({" in src
    cfg = src.split("PostmortemEngine({", 1)[1].split("})", 1)[0]
    assert "paths_path" in cfg, (
        "smoke_test's PostmortemEngine cfg lost its paths_path isolation - "
        "its fixture closes will land in the production trade_paths ledger")
    assert "synthetic-clock rows" in src, (
        "smoke_test's end-of-run synthetic-clock tripwire is gone")
