"""tests/test_reconcile_weekly.py — the waterfall must RECOVER a known
decomposition, not merely run.

The fixture plants every named confound with exact, hand-computed truth:
  * a hedge round trip (net -10.11) in 2026-W02  -> the hedge stage,
  * a pre-sweep leg (+4.95) in 2026-W03          -> the sweep stage,
  * a tier partial (3.95 in W02) whose trade closes in W03
                                                  -> the timing stage,
  * a duplicate fill-pattern position            -> the dedupe,
  * an orphan exit leg                           -> counted, never priced,
  * a still-open position's partial exit         -> never realigned.
The planted ledger is written to the fixture's OWN truth model
(hedge-excluded, sweep-zeroed, leg-grain), so the waterfall's stage-2
residual must be exactly zero — anything else is a wrong rebuild, not a
wrong market.

Hand-computed stage table (exit-fee-net USD):
             W02      W03
  s0        -5.17    -3.13     (all legs, hedges in)
  s1        +4.94    -3.13     (hedge -10.11 removed from W02)
  s2        +4.94    -8.08     (pre-sweep +4.95 removed from W03)
  s3        +0.99    -4.13     (P1's 3.95 tier leg moves W02 -> W03)
  ledger    +4.94    -8.08     (fixture truth: r2 == 0 exactly)
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.reconcile_weekly import (build_positions, build_report,
                                      chain_check, iso_week_key,
                                      load_fills, load_ledger, parse_ts,
                                      waterfall)

_FILL_COLS = ["ts", "order_id", "position_id", "purpose", "symbol",
              "side", "ordertype", "post_only", "attempt", "fill_size",
              "fill_price", "arrival_ref", "slip_bps", "fees_delta_usd",
              "remaining", "reason", "exec_era"]
_LEDGER_COLS = ["week", "weekly_realized", "reserve_refill", "cash",
                "savings", "reserve", "realized_total", "goal", "hit",
                "category", "attainment_pct", "shortfall_usd",
                "miss_reason"]


def _ts(*args):
    return datetime(*args, tzinfo=timezone.utc).timestamp()


# 2026-01-05 is Monday of ISO 2026-W02; 2026-01-12 starts 2026-W03.
T_E1 = _ts(2026, 1, 6, 10)      # P1 entry           (W02)
T_X1 = _ts(2026, 1, 7, 10)      # P1 tier exit       (W02)
T_H1 = _ts(2026, 1, 6, 11)      # P2 hedge open      (W02)
T_HX = _ts(2026, 1, 7, 11)      # P2 hedge unwind    (W02)
T_O1 = _ts(2026, 1, 6, 12)      # P6 entry           (W02)
T_OX = _ts(2026, 1, 7, 12)      # P6 partial exit    (W02) — stays open
T_P3E = _ts(2026, 1, 13, 1)     # P3 entry           (W03)
T_P3X = _ts(2026, 1, 13, 3)     # P3 exit PRE-SWEEP  (W03)
T_SWEEP = _ts(2026, 1, 13, 6)   # planted capital sweep      (W03)
T_X2 = _ts(2026, 1, 14, 10)     # P1 final exit      (W03)
T_P4E = _ts(2026, 1, 14, 1)     # P4 entry           (W03)
T_P4X = _ts(2026, 1, 15, 1)     # P4 exit            (W03)
T_ORPH = _ts(2026, 1, 7, 13)    # orphan exit        (W02)


def _row(ts, pid, purpose, side, size, price, fee, oid="o"):
    return {"ts": f"{ts:.3f}", "order_id": oid, "position_id": pid,
            "purpose": purpose, "symbol": "ETH/USD", "side": side,
            "ordertype": "limit", "post_only": 1, "attempt": 0,
            "fill_size": f"{size:.10g}", "fill_price": f"{price:.10g}",
            "arrival_ref": "", "slip_bps": "",
            "fees_delta_usd": f"{fee:.6f}", "remaining": "0",
            "reason": "", "exec_era": "t"}


def _fixture_rows():
    return [
        # P1: entry book, long; tier leg +3.95 (W02), final -6.06 (W03)
        _row(T_E1, "P1", "entry", "buy", 1.0, 100.0, 0.10),
        _row(T_X1, "P1", "exit", "sell", 0.4, 110.0, 0.05),
        _row(T_X2, "P1", "exit", "sell", 0.6, 90.0, 0.06),
        # P2: hedge book, short; net -10.11 (W02)
        _row(T_H1, "P2", "hedge", "sell", 2.0, 50.0, 0.10),
        _row(T_HX, "P2", "exit", "buy", 2.0, 55.0, 0.11),
        # P3: +4.95 realized BEFORE the sweep, same ISO week (W03)
        _row(T_P3E, "P3", "entry", "buy", 1.0, 100.0, 0.05),
        _row(T_P3X, "P3", "exit", "sell", 1.0, 105.0, 0.05),
        # P4: -2.02 after the sweep (W03)
        _row(T_P4E, "P4", "entry", "buy", 1.0, 100.0, 0.05),
        _row(T_P4X, "P4", "exit", "sell", 1.0, 98.0, 0.02),
        # P5: byte-identical fill pattern to P1 under a fresh position_id
        # (the restart-replay signature) — must dedupe away
        _row(T_E1, "P5", "entry", "buy", 1.0, 100.0, 0.10),
        _row(T_X1, "P5", "exit", "sell", 0.4, 110.0, 0.05),
        _row(T_X2, "P5", "exit", "sell", 0.6, 90.0, 0.06),
        # P6: still open after a partial (+0.99 W02) — never realigned
        _row(T_O1, "P6", "entry", "buy", 2.0, 10.0, 0.01),
        _row(T_OX, "P6", "exit", "sell", 0.5, 12.0, 0.01),
        # orphan exit: no opening fill on file — counted, never priced
        _row(T_ORPH, "ORPH", "exit", "sell", 1.0, 100.0, 0.01),
    ]


def _write_fills(path: Path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_FILL_COLS)
        w.writeheader()
        w.writerows(rows)


def _write_ledger(path: Path):
    """Fixture truth: hedge-EXCLUDED, sweep-zeroed, leg-grain weekly rows.
    W02 = 3.95 + 0.99 = 4.94; W03 (post-sweep only) = -6.06 - 2.02 =
    -8.08; the sweep also zeroed realized_total, so rt(W03) = -8.08."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_LEDGER_COLS)
        w.writeheader()
        w.writerow({"week": "2026-W02", "weekly_realized": 4.94,
                    "reserve_refill": 0.0, "cash": 100.0, "savings": 0.0,
                    "reserve": 0.0, "realized_total": 4.94, "goal": 0,
                    "hit": False, "category": "win", "attainment_pct": 0,
                    "shortfall_usd": 0, "miss_reason": ""})
        w.writerow({"week": "2026-W03", "weekly_realized": -8.08,
                    "reserve_refill": 0.0, "cash": 92.0, "savings": 0.0,
                    "reserve": 0.0, "realized_total": -8.08, "goal": 0,
                    "hit": False, "category": "loss", "attainment_pct": 0,
                    "shortfall_usd": 0, "miss_reason": ""})


def _report(tmp_path, sweeps=(T_SWEEP,)):
    fills = tmp_path / "fills.csv"
    ledger = tmp_path / "weekly_ledger.csv"
    _write_fills(fills, _fixture_rows())
    _write_ledger(ledger)
    return build_report(fills, ledger, list(sweeps))


def test_waterfall_recovers_planted_decomposition(tmp_path):
    rep = _report(tmp_path)
    w2, w3 = rep["weeks"]["2026-W02"], rep["weeks"]["2026-W03"]
    # stage sums, hand-computed in the module docstring
    assert w2["s0"] == -5.17 and w3["s0"] == -3.13
    assert w2["s1"] == 4.94 and w3["s1"] == -3.13
    assert w2["s2"] == 4.94 and w3["s2"] == -8.08
    # exact recovery: after the hedge + sweep stages the residual is ZERO
    assert w2["r2"] == 0.0 and w3["r2"] == 0.0
    # each named confound carries exactly its planted quantity
    assert w2["hedge_legs"] == -10.11
    assert w3["presweep_legs"] == 4.95


def test_r0_is_the_direct_mismatch_naming_each_confound(tmp_path):
    rep = _report(tmp_path)
    w2, w3 = rep["weeks"]["2026-W02"], rep["weeks"]["2026-W03"]
    # W02's whole raw-stage residual is the hedge book, W03's the sweep
    assert w2["r0"] == 10.11 == -w2["hedge_legs"]
    assert w3["r0"] == -4.95 == -w3["presweep_legs"]


def test_tier_timing_realignment(tmp_path):
    rep = _report(tmp_path)
    w2, w3 = rep["weeks"]["2026-W02"], rep["weeks"]["2026-W03"]
    # P1's 3.95 tier leg moves to its close week; the shift nets to zero
    assert w2["tier_shift"] == -3.95 and w3["tier_shift"] == 3.95
    # P6 is still OPEN: its +0.99 W02 leg must NOT be realigned
    assert w2["s3"] == 0.99
    assert w3["s3"] == -4.13


def test_duplicate_fill_pattern_deduped_and_counted(tmp_path):
    rep = _report(tmp_path)
    assert rep["skipped"]["duplicate_fill_pattern"] == 1
    # the dup carried P1's whole pattern: had it been double-counted,
    # W02 s0 would read -1.22 and W03 s0 -9.19 — pinned by test 1's sums
    assert rep["positions"]["total"] == 5          # P1 P2 P3 P4 P6


def test_orphan_exit_counted_never_priced(tmp_path):
    rep = _report(tmp_path)
    assert rep["skipped"]["orphan_exit_leg"] == 1
    assert rep["skipped"]["orphan_only"] == 1
    # nothing about the orphan reached any stage sum (W02 totals pinned
    # elsewhere would shift by its un-priceable leg otherwise)


def test_chain_check_flags_only_the_sweep_week(tmp_path):
    rep = _report(tmp_path)
    by_week = {c["week"]: c for c in rep["ledger_chain"]}
    assert by_week["2026-W02"]["chain_residual"] is None      # first row
    assert by_week["2026-W02"]["sweep_signature"] is False
    assert by_week["2026-W03"]["sweep_signature"] is True
    # rt was re-zeroed: -8.08 - 4.94 - (-8.08) = -4.94
    assert by_week["2026-W03"]["chain_residual"] == -4.94


def test_no_sweep_arg_means_s2_equals_s1(tmp_path):
    rep = _report(tmp_path, sweeps=())
    for wk in ("2026-W02", "2026-W03"):
        assert rep["weeks"][wk]["s2"] == rep["weeks"][wk]["s1"]
        assert rep["weeks"][wk]["presweep_legs"] == 0.0
    # and the ledger chain check STILL names the sweep week on its own
    by_week = {c["week"]: c for c in rep["ledger_chain"]}
    assert by_week["2026-W03"]["sweep_signature"] is True


def test_short_direction_math():
    # a short's gain is price DOWN: sell-open 2@50, buy-close 2@45
    rows, skipped = load_fills_from(
        [_row(T_H1, "S1", "hedge", "sell", 2.0, 50.0, 0.10),
         _row(T_HX, "S1", "exit", "buy", 2.0, 45.0, 0.11)])
    positions, _ = build_positions(rows)
    assert len(positions) == 1
    leg = positions[0]["legs"][0]
    assert abs(leg["net"] - (10.0 - 0.11)) < 1e-9
    assert positions[0]["is_hedge"] and positions[0]["closed"]
    assert not skipped


def load_fills_from(rows):
    """In-memory adapter: run load_fills' parse on literal fixture rows."""
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=_FILL_COLS)
    w.writeheader()
    w.writerows(rows)
    buf.seek(0)
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False,
                                     newline="", encoding="utf-8") as f:
        f.write(buf.getvalue())
        p = Path(f.name)
    try:
        return load_fills(p)
    finally:
        p.unlink(missing_ok=True)


def test_parse_ts_forms():
    assert parse_ts("1786400673") == 1786400673.0
    iso = parse_ts("2026-01-13T06:00:00Z")
    assert iso == T_SWEEP
    assert parse_ts("2026-01-13T06:00:00+00:00") == T_SWEEP
    assert iso_week_key(T_SWEEP) == "2026-W03"
    assert iso_week_key(T_X1) == "2026-W02"


def test_entry_vwap_matches_engine_averaging():
    """Averaging adds re-anchor the mean against CURRENT size (the
    engine's own formula) — a second entry after a partial exit must
    blend against the reduced size, not the original."""
    rows, _ = load_fills_from([
        _row(T_E1, "A1", "entry", "buy", 1.0, 100.0, 0.0),
        _row(T_X1, "A1", "exit", "sell", 0.5, 110.0, 0.0),   # +5.00
        _row(T_P3E, "A1", "entry", "buy", 0.5, 120.0, 0.0),  # avg -> 110
        _row(T_P4X, "A1", "exit", "sell", 1.0, 110.0, 0.0),  # 0.00
    ])
    positions, _ = build_positions(rows)
    legs = positions[0]["legs"]
    assert abs(legs[0]["net"] - 5.0) < 1e-9
    assert abs(legs[1]["net"] - 0.0) < 1e-9


def test_cli_json_writes_nothing_into_outputs(tmp_path, monkeypatch,
                                              capsys):
    import scripts.reconcile_weekly as rw
    outdir = tmp_path / "outputs"
    outdir.mkdir()
    _write_fills(outdir / "fills.csv", _fixture_rows())
    _write_ledger(outdir / "weekly_ledger.csv")
    before = sorted(p.name for p in outdir.iterdir())
    monkeypatch.setattr("sys.argv", [
        "reconcile_weekly.py", "--root", str(tmp_path), "--json",
        "--sweep", "2026-01-13T06:00:00Z"])
    assert rw.main() == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["weeks"]["2026-W02"]["r2"] == 0.0
    assert rep["weeks"]["2026-W03"]["r2"] == 0.0
    assert rep["sweeps"][0]["week"] == "2026-W03"
    # read-only: the tool must not have added a single file to outputs/
    assert sorted(p.name for p in outdir.iterdir()) == before


def test_missing_fills_is_a_clean_refusal(tmp_path, monkeypatch, capsys):
    import scripts.reconcile_weekly as rw
    monkeypatch.setattr("sys.argv",
                        ["reconcile_weekly.py", "--root", str(tmp_path)])
    assert rw.main() == 2
    assert "nothing to reconcile" in capsys.readouterr().out


def test_ledger_loader_and_chain_on_real_shape(tmp_path):
    p = tmp_path / "weekly_ledger.csv"
    _write_ledger(p)
    rows = load_ledger(p)
    assert [r["week"] for r in rows] == ["2026-W02", "2026-W03"]
    chain = chain_check(rows)
    assert chain[0]["pre_window_accrual"] == 0.0
    assert chain[1]["sweep_signature"] is True


def test_waterfall_pure_function_units():
    """waterfall() on hand-built positions: one closed cross-week trade,
    one hedge — no CSV in the loop at all."""
    positions = [
        {"pid": "a", "is_hedge": False, "closed": True,
         "close_week": "2026-W03",
         "legs": [{"ts": T_X1, "week": "2026-W02", "net": 3.0},
                  {"ts": T_X2, "week": "2026-W03", "net": -1.0}]},
        {"pid": "h", "is_hedge": True, "closed": True,
         "close_week": "2026-W02",
         "legs": [{"ts": T_HX, "week": "2026-W02", "net": -7.0}]},
    ]
    st = waterfall(positions, [])
    assert st["s0"]["2026-W02"] == -4.0
    assert st["s1"]["2026-W02"] == 3.0
    assert st["hedge_legs"]["2026-W02"] == -7.0
    assert st["s3"] == {"2026-W03": 2.0}
    assert st["tier_shift"]["2026-W02"] == -3.0
