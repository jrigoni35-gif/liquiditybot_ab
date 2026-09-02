"""tests/test_cost_truth_report.py — scripts/cost_truth_report.py (T7).

Spec D4 ("measured, never assumed"): the report must derive its measured
bps from the corpus of closed trades / OM-080 audit records, never from a
fitted or assumed number, and it must NEVER mutate config.json — a config
change, if the evidence supports one, is the operator/controller's own
conscious commit. These tests pin: exact bps arithmetic from a synthetic
postmortem corpus with known fees/notionals, the dangerous-direction
verdict firing exactly when configured < measured beyond tolerance, the
insufficient-data path when a source has zero usable samples, and that
running the report never touches config.json on disk.
"""
import csv
import json

import pytest

from core.codes import Code
from scripts.cost_truth_report import (
    Verdict,
    build_report,
    classify,
    configured_fees,
    main,
    read_om080_fee_recon,
    read_om080_tier_context,
    read_postmortem_overruns,
    tier_context_lines,
)

POSTMORTEM_HEADER = [
    "ts", "position_id", "asset", "direction", "p_win", "expected_pct",
    "realized_pct", "shortfall_pct", "cause", "cost_overrun_bps",
    "mfe_pct", "mae_pct", "recovered_after_stop", "regime_entry",
    "regime_exit",
]


def _write_postmortem_csv(path, rows, header=None):
    header = header or POSTMORTEM_HEADER
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def _pm_row(position_id, cost_overrun_bps, ts=1000000, asset="BTC"):
    """One well-formed postmortem_summary.csv row (ml/postmortem.py's own
    column order) with the given cost_overrun_bps; the other fields are
    filler, since only cost_overrun_bps + position_id feed the report."""
    return [ts, position_id, asset, "long", "0.62", "0.25", "-1.0", "1.25",
            "cost_overrun", cost_overrun_bps, "0.0", "-1.0", 0, "range",
            "range"]


def _om080_record(seq, ts, pairs, tolerance_bps=1.0):
    return {"seq": seq, "ts": ts, "src": "order_manager", "code": "OM-080",
            "msg": "fee tier mismatch", "data": {"pairs": pairs,
                                                 "tolerance_bps": tolerance_bps},
            "prev": "0" * 16, "h": "f" * 16}


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


# --------------------------------------------------------------- configured
def test_configured_fees_reads_pretrade_section():
    cfg = {"pretrade": {"maker_fee_bps": 16.0, "taker_fee_bps": 26.0}}
    assert configured_fees(cfg) == (16.0, 26.0)


def test_configured_fees_falls_back_to_documented_default():
    assert configured_fees({}) == (25.0, 40.0)
    assert configured_fees({"pretrade": {}}) == (25.0, 40.0)


# ------------------------------------------------------------- postmortem
def test_read_postmortem_overruns_known_values_exact(tmp_path):
    p = tmp_path / "postmortem_summary.csv"
    _write_postmortem_csv(p, [
        _pm_row("a", "10.0"),
        _pm_row("b", "20.0"),
        _pm_row("c", "-5.0"),
    ])
    overruns, n_rows, n_dupe = read_postmortem_overruns(p)
    assert overruns == [10.0, 20.0, -5.0]
    assert n_rows == 3
    assert n_dupe == 0
    assert sum(overruns) / len(overruns) == pytest.approx(8.333333, abs=1e-4)


def test_read_postmortem_overruns_dedups_repeated_position_id(tmp_path):
    p = tmp_path / "postmortem_summary.csv"
    _write_postmortem_csv(p, [
        _pm_row("dup", "12.0"),
        _pm_row("dup", "12.0"),   # exact duplicate write, as seen in prod
        _pm_row("other", "8.0"),
    ])
    overruns, n_rows, n_dupe = read_postmortem_overruns(p)
    assert overruns == [12.0, 8.0]
    assert n_rows == 3
    assert n_dupe == 1


def test_read_postmortem_overruns_missing_file_is_insufficient(tmp_path):
    overruns, n_rows, n_dupe = read_postmortem_overruns(
        tmp_path / "does_not_exist.csv")
    assert overruns == [] and n_rows == 0 and n_dupe == 0


def test_read_postmortem_overruns_missing_column_is_insufficient(tmp_path):
    p = tmp_path / "postmortem_summary.csv"
    _write_postmortem_csv(p, [["1", "a"]], header=["ts", "position_id"])
    overruns, n_rows, n_dupe = read_postmortem_overruns(p)
    assert overruns == [] and n_rows == 0 and n_dupe == 0


def test_read_postmortem_overruns_skips_malformed_values(tmp_path):
    p = tmp_path / "postmortem_summary.csv"
    _write_postmortem_csv(p, [
        _pm_row("a", "10.0"),
        _pm_row("b", "n/a"),
        _pm_row("c", ""),
        _pm_row("d", "nan"),
        _pm_row("e", "30.0"),
    ])
    overruns, n_rows, n_dupe = read_postmortem_overruns(p)
    assert overruns == [10.0, 30.0]
    assert n_rows == 5


def test_read_postmortem_overruns_empty_file_beyond_header(tmp_path):
    p = tmp_path / "postmortem_summary.csv"
    _write_postmortem_csv(p, [])
    overruns, n_rows, n_dupe = read_postmortem_overruns(p)
    assert overruns == [] and n_rows == 0 and n_dupe == 0


# ------------------------------------------------------------------ OM-080
def test_read_om080_fee_recon_uses_most_recent_record(tmp_path):
    p = tmp_path / "audit.jsonl"
    _write_jsonl(p, [
        _om080_record(1, 100.0, {"XBT/USD": {"maker_actual_bps": 20.0,
                                              "taker_actual_bps": 30.0}}),
        _om080_record(2, 200.0, {"XBT/USD": {"maker_actual_bps": 16.0,
                                              "taker_actual_bps": 26.0},
                                 "ETH/USD": {"maker_actual_bps": 18.0,
                                             "taker_actual_bps": 28.0}}),
    ])
    maker, taker, n_records, n_pairs = read_om080_fee_recon(p)
    assert n_records == 2
    assert n_pairs == 2
    assert maker == pytest.approx(17.0)     # mean(16.0, 18.0) - latest record
    assert taker == pytest.approx(27.0)     # mean(26.0, 28.0) - latest record


def test_read_om080_fee_recon_ignores_non_matching_codes(tmp_path):
    p = tmp_path / "audit.jsonl"
    _write_jsonl(p, [
        {"seq": 1, "ts": 1.0, "src": "risk_firewall", "code": "FW-010",
         "msg": "x", "data": {}, "prev": "0" * 16, "h": "a" * 16},
        _om080_record(2, 2.0, {"XBT/USD": {"maker_actual_bps": 25.0,
                                           "taker_actual_bps": 40.0}}),
    ])
    maker, taker, n_records, n_pairs = read_om080_fee_recon(p)
    assert n_records == 1
    assert maker == pytest.approx(25.0)
    assert taker == pytest.approx(40.0)


def test_read_om080_fee_recon_absent_file_is_insufficient(tmp_path):
    maker, taker, n_records, n_pairs = read_om080_fee_recon(
        tmp_path / "no_audit.jsonl")
    assert maker is None and taker is None and n_records == 0 and n_pairs == 0


def test_read_om080_fee_recon_no_records_of_that_code_is_insufficient(tmp_path):
    p = tmp_path / "audit.jsonl"
    _write_jsonl(p, [
        {"seq": 1, "ts": 1.0, "src": "x", "code": "FW-010", "msg": "x",
         "data": {}, "prev": "0" * 16, "h": "a" * 16},
    ])
    maker, taker, n_records, n_pairs = read_om080_fee_recon(p)
    assert maker is None and n_records == 0


def test_read_om080_fee_recon_tolerates_malformed_lines(tmp_path):
    p = tmp_path / "audit.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        f.write("{not valid json\n")
        f.write(json.dumps(_om080_record(
            1, 1.0, {"XBT/USD": {"maker_actual_bps": 25.0,
                                 "taker_actual_bps": 40.0}})) + "\n")
        f.write("\n")   # blank line
    maker, taker, n_records, n_pairs = read_om080_fee_recon(p)
    assert n_records == 1
    assert maker == pytest.approx(25.0)


# ------------------------------------------------------- OM-080 tier context
# FEE-3 remedy: the report surfaces the tier context OM-080 now carries -
# the fields that tell an account rate from a schedule top.
_CTX_TOP = {   # fee == maxfee on both sides: the untraded-pair signature
    "maker_actual_bps": 25.0, "taker_actual_bps": 40.0,
    "maker_min_bps": 0.0, "maker_max_bps": 25.0, "maker_next_bps": 20.0,
    "maker_next_volume": 50000.0, "maker_tier_volume": 0.0,
    "taker_min_bps": 10.0, "taker_max_bps": 40.0, "taker_next_bps": 35.0,
    "taker_next_volume": 50000.0, "taker_tier_volume": 0.0,
}
_CTX_DISCOUNT = {   # below max on both sides: an account-tier reading
    "maker_actual_bps": 22.0, "taker_actual_bps": 38.0,
    "maker_min_bps": 0.0, "maker_max_bps": 25.0, "maker_next_bps": 20.0,
    "maker_next_volume": 50000.0, "maker_tier_volume": 10000.0,
    "taker_min_bps": 10.0, "taker_max_bps": 40.0, "taker_next_bps": 35.0,
    "taker_next_volume": 50000.0, "taker_tier_volume": 10000.0,
}


def _om080_record_ctx(seq, ts, pairs, volume_30d, volume_currency):
    rec = _om080_record(seq, ts, pairs)
    rec["data"]["volume_30d"] = volume_30d
    rec["data"]["volume_currency"] = volume_currency
    return rec


def test_read_om080_tier_context_latest_record_exact_fields(tmp_path):
    p = tmp_path / "audit.jsonl"
    _write_jsonl(p, [
        _om080_record_ctx(1, 100.0, {"XBTUSD": dict(_CTX_TOP)}, 0.0, "ZUSD"),
        _om080_record_ctx(2, 200.0, {"XBTUSD": dict(_CTX_DISCOUNT),
                                     "ETHUSD": dict(_CTX_TOP)},
                          17482.0, "ZUSD"),
    ])
    ctx = read_om080_tier_context(p)
    assert ctx is not None
    assert ctx["seq"] == 2.0
    assert ctx["volume_30d"] == 17482.0
    assert ctx["volume_currency"] == "ZUSD"
    assert set(ctx["pairs"]) == {"XBTUSD", "ETHUSD"}
    xbt = ctx["pairs"]["XBTUSD"]
    for k, v in _CTX_DISCOUNT.items():
        assert xbt[k] == v, k
    assert xbt["at_schedule_top"] is False
    assert ctx["pairs"]["ETHUSD"]["at_schedule_top"] is True


def test_read_om080_tier_context_pre_remedy_record_is_none_not_inferred(tmp_path):
    """A record written before the remedy carries only the headline fees:
    every context field reads None and at_schedule_top is None (NOT False -
    absence of a max is not evidence the fee is below it)."""
    p = tmp_path / "audit.jsonl"
    _write_jsonl(p, [_om080_record(1, 1.0, {"XBTUSD": {
        "maker_actual_bps": 40.0, "taker_actual_bps": 80.0}})])
    ctx = read_om080_tier_context(p)
    assert ctx is not None
    assert ctx["volume_30d"] is None and ctx["volume_currency"] is None
    row = ctx["pairs"]["XBTUSD"]
    assert row["maker_actual_bps"] == 40.0
    assert row["at_schedule_top"] is None
    for k in _CTX_TOP:
        if k.endswith("_actual_bps"):
            continue
        assert row[k] is None, k
    lines = "\n".join(tier_context_lines(ctx))
    assert "undetermined (max not recorded)" in lines
    assert "not recorded (pre-remedy record)" in lines


def test_read_om080_tier_context_absent_is_none(tmp_path):
    assert read_om080_tier_context(tmp_path / "nope.jsonl") is None
    assert tier_context_lines(None) == []


def test_build_report_prints_tier_context_block(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(
        {"pretrade": {"maker_fee_bps": 22.0, "taker_fee_bps": 38.0}}),
        encoding="utf-8")
    audit_path = tmp_path / "audit.jsonl"
    _write_jsonl(audit_path, [_om080_record_ctx(
        7, 100.0, {"XBTUSD": dict(_CTX_TOP), "ETHUSD": dict(_CTX_DISCOUNT)},
        17482.0, "ZUSD")])
    report = build_report(cfg_path, tmp_path / "missing_pm.csv", audit_path)
    assert "tier context (FEE-3, most recent OM-080 record seq=7)" in report
    assert "account 30-day volume = 17482.00 ZUSD" in report
    assert "XBTUSD: SCHEDULE TOP" in report
    assert "ETHUSD: below schedule top" in report
    assert ("taker: fee=38.00 bps  min=10.00 bps  max=40.00 bps  "
            "next=35.00 bps  tier_volume=10000.00  next_volume=50000.00"
            in report)


# ------------------------------------------------------------------ classify
def test_classify_within_tolerance_at_exact_boundary():
    v = classify(measured_bps=78.0, configured_bps=65.0)   # +20.0% exactly
    assert isinstance(v, Verdict)
    assert "within tolerance" in v.label
    assert v.delta_pct == pytest.approx(0.20)


def test_classify_dangerous_direction_fires_when_configured_below_measured():
    v = classify(measured_bps=90.0, configured_bps=65.0)   # +38.5%, measured > configured
    assert "DANGEROUS" in v.label
    assert v.delta_bps == pytest.approx(25.0)


def test_classify_outside_tolerance_conservative_when_configured_above_measured():
    v = classify(measured_bps=40.0, configured_bps=65.0)   # -38.5%, configured > measured
    assert "outside tolerance" in v.label
    assert "DANGEROUS" not in v.label


def test_classify_none_measured_is_insufficient_data():
    v = classify(measured_bps=None, configured_bps=65.0)
    assert v.label == "insufficient data"
    assert v.delta_bps is None and v.delta_pct is None


def test_classify_zero_configured_is_insufficient_data():
    v = classify(measured_bps=50.0, configured_bps=0.0)
    assert v.label == "insufficient data"


# -------------------------------------------------------------- build_report
def test_build_report_known_fees_and_notionals_gives_exact_measured_bps(
        tmp_path):
    """Two synthetic closed trades, fees/notionals chosen so the ROUND-TRIP
    cost_overrun_bps each row carries is exactly what ml/postmortem.py's own
    _cost_overrun_bps() would compute at entry (realized round-trip fee bps
    + entry-leg slippage bps) MINUS the configured 65bps baseline (25+40)
    used at entry time:
      trade 1: fees_usd=$10 on $2000 notional -> 50.0bps fee; quote 50000 /
               fill 50010 -> 2.0bps slip; overrun = (50.0+2.0)-65.0 = -13.0
      trade 2: fees_usd=$6.50 on $1000 notional -> 65.0bps fee; quote 100 /
               fill 100.30 -> 30.0bps slip; overrun = (65.0+30.0)-65.0 = 30.0
    mean overrun = 8.5bps -> measured round-trip = 65.0 + 8.5 = 73.5bps
    exactly, delta = +8.5bps (+13.08%), inside the +/-20% D4 tolerance."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(
        {"pretrade": {"maker_fee_bps": 25.0, "taker_fee_bps": 40.0}}),
        encoding="utf-8")
    pm_path = tmp_path / "postmortem_summary.csv"
    _write_postmortem_csv(pm_path, [
        _pm_row("t1", "-13.0"),
        _pm_row("t2", "30.0"),
    ])
    audit_path = tmp_path / "audit.jsonl"   # absent: OM-080 side insufficient

    report = build_report(cfg_path, pm_path, audit_path)

    assert "measured round-trip = 65.00 + +8.50 = 73.50 bps" in report
    assert "delta = +8.50 bps (+13.1%)" in report
    assert "within tolerance" in report
    assert "insufficient data (n=0)" in report   # OM-080 side, no audit file


def test_build_report_dangerous_direction_end_to_end(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(
        {"pretrade": {"maker_fee_bps": 25.0, "taker_fee_bps": 40.0}}),
        encoding="utf-8")
    pm_path = tmp_path / "postmortem_summary.csv"
    # mean overrun = +40 -> measured round-trip = 105 vs configured 65:
    # delta = +40 (+61.5%), well past +/-20% and measured > configured.
    _write_postmortem_csv(pm_path, [
        _pm_row("t1", "40.0"),
        _pm_row("t2", "40.0"),
    ])
    audit_path = tmp_path / "audit.jsonl"

    report = build_report(cfg_path, pm_path, audit_path)
    assert "DANGEROUS" in report
    assert f"[{Code.XV_COST_DANGEROUS.value}]" in report


def test_build_report_insufficient_data_both_sources(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(
        {"pretrade": {"maker_fee_bps": 25.0, "taker_fee_bps": 40.0}}),
        encoding="utf-8")
    report = build_report(cfg_path, tmp_path / "missing_pm.csv",
                          tmp_path / "missing_audit.jsonl")
    assert report.count("insufficient data (n=0)") == 2
    assert "VERDICT" not in report
    assert "DANGEROUS" not in report


# --------------------------------------------------------- never mutates config
def test_report_never_writes_config_json(tmp_path):
    cfg_path = tmp_path / "config.json"
    original = json.dumps(
        {"pretrade": {"maker_fee_bps": 25.0, "taker_fee_bps": 40.0}},
        indent=2)
    cfg_path.write_text(original, encoding="utf-8")
    before_mtime = cfg_path.stat().st_mtime_ns
    before_content = cfg_path.read_text(encoding="utf-8")

    pm_path = tmp_path / "postmortem_summary.csv"
    _write_postmortem_csv(pm_path, [_pm_row("t1", "10.0")])
    audit_path = tmp_path / "audit.jsonl"

    rc = main(["--config", str(cfg_path), "--postmortem-csv", str(pm_path),
              "--audit", str(audit_path)])

    assert rc == 0
    assert cfg_path.stat().st_mtime_ns == before_mtime
    assert cfg_path.read_text(encoding="utf-8") == before_content


def test_report_never_writes_config_json_even_when_dangerous(tmp_path):
    """Same guarantee under the DANGEROUS verdict path specifically - the
    branch most tempting to 'helpfully' auto-correct. It must not."""
    cfg_path = tmp_path / "config.json"
    original = json.dumps(
        {"pretrade": {"maker_fee_bps": 25.0, "taker_fee_bps": 40.0}},
        indent=2)
    cfg_path.write_text(original, encoding="utf-8")
    before_mtime = cfg_path.stat().st_mtime_ns
    before_content = cfg_path.read_text(encoding="utf-8")

    pm_path = tmp_path / "postmortem_summary.csv"
    _write_postmortem_csv(pm_path, [_pm_row("t1", "40.0"),
                                    _pm_row("t2", "40.0")])
    audit_path = tmp_path / "audit.jsonl"

    report = build_report(cfg_path, pm_path, audit_path)
    assert "DANGEROUS" in report
    assert cfg_path.stat().st_mtime_ns == before_mtime
    assert cfg_path.read_text(encoding="utf-8") == before_content


# ---------------------------------------------------------------------------
# [3] POPULATION — audit terminal-fill scan (2026-07-28). Terminal OM-000
# records now carry filled_units/notional_usd, so fee RATE is measurable
# over the WHOLE fill population, not the biased postmortem subset that
# forced XV-033's caveat. Legacy records without notional are counted and
# skipped honestly — never fabricated into a rate.
# ---------------------------------------------------------------------------
def _fill_line(purpose, fees_usd, notional_usd=None, code="OM-000"):
    data = {"purpose": purpose, "avg_price": 100.0,
            "fees_usd": fees_usd, "terminal": "filled"}
    if notional_usd is not None:
        data["filled_units"] = notional_usd / 100.0
        data["notional_usd"] = notional_usd
    return json.dumps({"code": code, "msg": "x terminal=filled (sim)",
                       "data": data, "ts": 1.0})


def test_audit_fill_costs_reader_exact_bps(tmp_path):
    from scripts.cost_truth_report import read_audit_fill_costs
    audit = tmp_path / "audit.jsonl"
    audit.write_text("\n".join([
        _fill_line("entry", 2.5, 1000.0),      # 25.0 bps
        _fill_line("exit", 4.0, 1000.0),       # 40.0 bps
        _fill_line("entry", 0.03),             # legacy shape: no notional
        json.dumps({"code": "SZ-023", "msg": "not a fill"}),
    ]) + "\n", encoding="utf-8")
    entry_bps, exit_bps, n_seen, n_skipped = read_audit_fill_costs(audit)
    assert entry_bps == [25.0]
    assert exit_bps == [40.0]
    assert n_seen == 3 and n_skipped == 1


def test_population_section_verdict_and_never_mutates_config(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(
        {"pretrade": {"maker_fee_bps": 25.0, "taker_fee_bps": 40.0}}),
        encoding="utf-8")
    before = cfg_path.read_bytes()
    audit = tmp_path / "audit.jsonl"
    lines = [_fill_line("entry", 2.5, 1000.0) for _ in range(5)]
    lines += [_fill_line("exit", 4.0, 1000.0) for _ in range(5)]
    audit.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = build_report(cfg_path, tmp_path / "missing_pm.csv", audit)
    assert "[3] POPULATION" in report
    assert "measured round-trip = 25.00 + 40.00 = 65.00 bps" in report
    pop = report.split("[3] POPULATION")[1]
    assert "within tolerance" in pop            # exact match: 65 vs 65
    assert "XV-031" in pop                      # the WITHIN verdict code
    assert cfg_path.read_bytes() == before      # report-only, still


def test_population_insufficient_when_only_legacy_records(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(
        {"pretrade": {"maker_fee_bps": 25.0, "taker_fee_bps": 40.0}}),
        encoding="utf-8")
    audit = tmp_path / "audit.jsonl"
    audit.write_text("\n".join(
        [_fill_line("entry", 0.03) for _ in range(20)]) + "\n",
        encoding="utf-8")
    report = build_report(cfg_path, tmp_path / "missing_pm.csv", audit)
    assert "[3] POPULATION" in report
    assert "insufficient" in report.split("[3] POPULATION")[1].split("===")[0]
    assert "20 legacy fill(s) lack notional" in report
