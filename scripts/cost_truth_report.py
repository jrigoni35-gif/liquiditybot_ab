"""scripts/cost_truth_report.py — measured round-trip cost truth (T7).

REPORT-ONLY. Spec D4 (docs/superpowers/specs/2026-07-27-geometry-alignment-
design.md, "Cost honesty - measured, never assumed"): no blind fee edits.
This script reads the corpus of closed trades and prints what round-trip
cost actually ran, compared against the configured pretrade.maker_fee_bps
/ taker_fee_bps (default 25/40) within D4's +/-20% tolerance. It PRINTS; it
never opens config.json for writing and never calls get_audit().log() or
core.codes.tag() (a one-off CLI report must not mutate state or bump the
live process's code_stats tally). A config change, if the evidence
supports one, is the operator/controller's own conscious commit.

Two independent measured sources, used honestly for however much (or
little) of each is actually available - absence is reported as
"insufficient data", never silently treated as "measured zero deviation":

  1. MAKER-LEG bps - execution/order_manager.py's OM-080 fee_recon audit
     records (outputs/audit.jsonl). OM-080 carries the ACTUAL Kraken
     maker/taker fee tier read directly from the venue's own private
     TradeVolume endpoint - the most direct "measured" fee source there
     is, independent of any trade's cost model. It only fires (and only
     ever CAN fire) with live Kraken credentials configured, and only
     WARNs+audits on a mismatch past tolerance_bps - a normal, healthy
     DRY_RUN history can show zero records for reasons that have nothing
     to do with whether the configured bps are correct.

  2. ROUND-TRIP bps - ml/postmortem.py's outputs/postmortem_summary.csv.
     Its `cost_overrun_bps` column is (realized fee bps, round-trip,
     from Position.fees_paid_usd / entry notional + entry-leg slippage
     bps) MINUS the expected_cost_bps that was in force when THAT trade
     opened (main.py's decision.est_cost_bps, itself pretrade.maker_fee_
     bps + taker_fee_bps + spread/impact terms at entry time - see
     execution/pretrade.py PreTradeGate.evaluate). Adding today's
     configured round-trip fee baseline back onto the mean overrun
     recovers an estimate of the measured round-trip bps - valid only to
     the extent the configured bps have not changed since those trades
     opened. This script has no visibility into config.json's history,
     so that is stated as an explicit assumption, never silently baked
     in. Also: postmortem rows are only the trades whose postmortem
     TRIGGERED (stopped out, or shortfall past ml.postmortem's
     shortfall_ratio) - not the full closed-trade corpus - so [2] is a
     cost measurement on the underperforming subset, never a
     population-wide average. Duplicate position_id rows (a known
     write-path artifact) are deduplicated, keeping the first, and the
     drop count is reported.

Usage:
    .venv/bin/python scripts/cost_truth_report.py
    .venv/bin/python scripts/cost_truth_report.py --config config.json \\
        --postmortem-csv outputs/postmortem_summary.csv \\
        --audit outputs/audit.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.codes import Code  # noqa: E402

# Legs that OPEN risk. A hedge fill's fee rate belongs with the opening side;
# testing only for "entry" put every hedge leg in NEITHER bucket, understating
# the measured opening-leg count. Pinned by tests/test_opening_leg_pin.py.
_OPEN_PURPOSES = ("entry", "hedge")

BASE_DIR = Path(__file__).resolve().parents[1]

# spec D4: "+/-20% tolerance" - a fixed spec constant, not a fitted knob.
TOLERANCE = 0.20

DEFAULT_CONFIG = "config.json"
DEFAULT_POSTMORTEM_CSV = "outputs/postmortem_summary.csv"
DEFAULT_AUDIT = "outputs/audit.jsonl"


def _resolve(path_str: str) -> Path:
    """CWD-independent: a relative path that doesn't exist from the current
    directory falls back to the repo root (mirrors main.load_config), so
    this script works run from anywhere without pulling in all of main.py."""
    p = Path(path_str)
    if not p.is_absolute() and not p.exists():
        anchored = BASE_DIR / p
        if anchored.exists():
            return anchored
    return p


def _finite_float(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# --------------------------------------------------------------- configured
def configured_fees(cfg: dict) -> tuple:
    """(maker_fee_bps, taker_fee_bps) from cfg["pretrade"]; falls back to
    config.json's own documented public-floor default (25/40) if the
    section or keys are absent - never a fabricated "measured" value, this
    IS the configured side of the comparison."""
    pretrade = (cfg or {}).get("pretrade", {}) or {}
    maker = _finite_float(pretrade.get("maker_fee_bps"))
    taker = _finite_float(pretrade.get("taker_fee_bps"))
    return (maker if maker is not None else 25.0,
            taker if taker is not None else 40.0)


def load_config(path) -> dict:
    p = _resolve(str(path))
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


# ------------------------------------------------------------- postmortem
def read_postmortem_overruns(path) -> tuple:
    """Returns (overrun_bps_values, n_rows_seen, n_duplicates_dropped) from
    ml/postmortem.py's outputs/postmortem_summary.csv. Deduplicates by
    position_id (keeping the first occurrence) - a position_id should only
    ever finalize one postmortem row; a repeat is a write-path artifact,
    not a second trade. Missing file / missing column / unparseable value
    all degrade to "not counted", never a crash and never a fabricated 0.0."""
    p = _resolve(str(path))
    if not p.exists():
        return [], 0, 0
    overruns: list = []
    seen_ids: set = set()
    n_rows = 0
    n_dupe = 0
    try:
        with open(p, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "cost_overrun_bps" not in reader.fieldnames:
                return [], 0, 0
            for row in reader:
                n_rows += 1
                pid = (row.get("position_id") or "").strip()
                if pid:
                    if pid in seen_ids:
                        n_dupe += 1
                        continue
                    seen_ids.add(pid)
                val = _finite_float(row.get("cost_overrun_bps"))
                if val is None:
                    continue
                overruns.append(val)
    except OSError:
        return [], 0, 0
    return overruns, n_rows, n_dupe


# ------------------------------------------------- population fill scan
def read_audit_fill_costs(path) -> tuple:
    """Returns (entry_bps, exit_bps, n_fills_seen, n_skipped_no_notional)
    from OM-000 terminal-fill audit records. This is the POPULATION
    measurement the postmortem subset ([2]) cannot give: every terminal
    fill since 2026-07-28 carries filled_units/notional_usd (added for
    exactly this purpose - fees_usd alone yields no RATE), so
    fee_bps = fees_usd / notional_usd * 1e4 per fill, bucketed by leg
    (purpose entry/exit; hedge legs are neither and are not bucketed).
    Legacy records without notional are COUNTED and skipped - reported,
    never fabricated into a rate. Malformed lines skipped (forensic
    read; chain integrity is core/audit.py's job)."""
    p = _resolve(str(path))
    if not p.exists():
        return [], [], 0, 0
    entry_bps: list = []
    exit_bps: list = []
    n_seen = 0
    n_skipped = 0
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if r.get("code") != Code.OM_CLEAN_TERMINAL.value:
                    continue
                data = r.get("data") or {}
                terminal = data.get("terminal") or (
                    "filled" if "terminal=filled" in (r.get("msg") or "")
                    else "")
                if terminal != "filled":
                    continue
                n_seen += 1
                fees = _finite_float(data.get("fees_usd"))
                notional = _finite_float(data.get("notional_usd"))
                if fees is None or notional is None or notional <= 0.0:
                    n_skipped += 1
                    continue
                bps = fees / notional * 1e4
                purpose = str(data.get("purpose") or "")
                if purpose in _OPEN_PURPOSES:
                    entry_bps.append(bps)
                elif purpose == "exit":
                    exit_bps.append(bps)
    except OSError:
        return [], [], 0, 0
    return entry_bps, exit_bps, n_seen, n_skipped


# ------------------------------------------------------------------ OM-080
def read_om080_fee_recon(path) -> tuple:
    """Returns (maker_actual_bps, taker_actual_bps, n_records, n_pairs) from
    execution/order_manager.py's OM-080 fee_recon audit records
    (outputs/audit.jsonl), each carrying data["pairs"][pair] = {
    "maker_actual_bps", "taker_actual_bps", ...} straight from Kraken's own
    TradeVolume tier lookup. Uses the MOST RECENT record (fee tiers are a
    discrete venue-side step, not a distribution to average across stale
    history) but reports n_records so the reader knows how many
    reconciliation events this is drawn from. Malformed lines are skipped
    (this is a forensic read, not a chain-integrity check - that is
    core/audit.py's own verify()). No records (file absent, empty, or the
    code never fired) returns (None, None, 0, 0) - never a fabricated 0.0
    deviation."""
    records = _load_om080_records(path)
    if not records:
        return None, None, 0, 0
    latest = records[-1]
    pairs = ((latest.get("data") or {}).get("pairs") or {})
    makers = [_finite_float(v.get("maker_actual_bps")) for v in pairs.values()
              if isinstance(v, dict)]
    takers = [_finite_float(v.get("taker_actual_bps")) for v in pairs.values()
              if isinstance(v, dict)]
    makers = [m for m in makers if m is not None]
    takers = [t for t in takers if t is not None]
    maker_mean = sum(makers) / len(makers) if makers else None
    taker_mean = sum(takers) / len(takers) if takers else None
    return maker_mean, taker_mean, len(records), len(pairs)


def _load_om080_records(path) -> list:
    """Every OM-080 record in the audit file, sorted by seq ascending
    (malformed lines skipped, absent/unreadable file -> [])."""
    p = _resolve(str(path))
    if not p.exists():
        return []
    records: list = []
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict):
                    continue
                if rec.get("code") == Code.OM_FEE_RECON_MISMATCH.value:
                    records.append(rec)
    except OSError:
        return []
    records.sort(key=lambda r: _finite_float(r.get("seq")) or 0.0)
    return records


# Per-pair tier-context keys OM-080 carries since the FEE-3 remedy
# (execution/order_manager.py _FEE_TIER_CONTEXT_KEYS). Absent on records
# written before it -> None, reported as "not recorded", never inferred.
_TIER_CONTEXT_KEYS = tuple(
    f"{side}_{suffix}" for side in ("maker", "taker")
    for suffix in ("min_bps", "max_bps", "next_bps", "next_volume",
                   "tier_volume"))


def read_om080_tier_context(path) -> Optional[dict]:
    """FEE-3 remedy: the tier CONTEXT of the most recent OM-080 record -
    the fields that tell an account rate from a schedule top. Returns

        {"seq", "ts", "volume_30d", "volume_currency",
         "pairs": {pair: {"maker_actual_bps", "taker_actual_bps",
                          <_TIER_CONTEXT_KEYS>..., "at_schedule_top"}}}

    `at_schedule_top` is True when BOTH headline fees equal their
    recorded max (the bottom-tier / untraded-pair signature), False when
    both max fields are recorded and either differs, None when a max is
    not on the record (pre-remedy rows) - never inferred from absence.
    None when no OM-080 record exists."""
    records = _load_om080_records(path)
    if not records:
        return None
    latest = records[-1]
    data = latest.get("data") or {}
    raw_pairs = data.get("pairs") or {}
    pairs: dict = {}
    for pair, v in raw_pairs.items():
        if not isinstance(v, dict):
            continue
        row = {"maker_actual_bps": _finite_float(v.get("maker_actual_bps")),
               "taker_actual_bps": _finite_float(v.get("taker_actual_bps"))}
        for key in _TIER_CONTEXT_KEYS:
            row[key] = _finite_float(v.get(key))
        tops = []
        for side in ("maker", "taker"):
            fee, mx = row[f"{side}_actual_bps"], row[f"{side}_max_bps"]
            tops.append(None if fee is None or mx is None
                        else abs(fee - mx) < 1e-9)
        row["at_schedule_top"] = (None if any(t is None for t in tops)
                                  else all(tops))
        pairs[pair] = row
    currency = data.get("volume_currency")
    return {"seq": _finite_float(latest.get("seq")),
            "ts": latest.get("ts"),
            "volume_30d": _finite_float(data.get("volume_30d")),
            "volume_currency": currency if isinstance(currency, str) else None,
            "pairs": pairs}


def _fmt_ctx(v: Optional[float], unit: str = "") -> str:
    return "not recorded" if v is None else f"{v:.2f}{unit}"


def tier_context_lines(ctx: Optional[dict]) -> list:
    """Human lines for the [1] block's tier-context sub-section."""
    if not ctx:
        return []
    seq = ctx["seq"]
    seq_txt = (str(int(seq)) if seq is not None and seq == int(seq)
               else repr(seq))          # greppable against audit.jsonl
    lines = ["    tier context (FEE-3, most recent OM-080 record "
             f"seq={seq_txt}):"]
    vol = ctx["volume_30d"]
    cur = ctx["volume_currency"] or "?"
    lines.append("      account 30-day volume = "
                 + ("not recorded (pre-remedy record)" if vol is None
                    else f"{vol:.2f} {cur}"))
    for pair, row in sorted(ctx["pairs"].items()):
        top = row["at_schedule_top"]
        verdict = ("SCHEDULE TOP (fee == maxfee on both sides: bottom "
                   "tier / untraded pair, NOT an account-rate reading)"
                   if top is True else
                   "below schedule top (account tier discount in effect)"
                   if top is False else "undetermined (max not recorded)")
        lines.append(f"      {pair}: {verdict}")
        for side in ("maker", "taker"):
            lines.append(
                f"        {side}: fee={_fmt_ctx(row[f'{side}_actual_bps'], ' bps')}"
                f"  min={_fmt_ctx(row[f'{side}_min_bps'], ' bps')}"
                f"  max={_fmt_ctx(row[f'{side}_max_bps'], ' bps')}"
                f"  next={_fmt_ctx(row[f'{side}_next_bps'], ' bps')}"
                f"  tier_volume={_fmt_ctx(row[f'{side}_tier_volume'])}"
                f"  next_volume={_fmt_ctx(row[f'{side}_next_volume'])}")
    return lines


# ------------------------------------------------------------------ verdict
@dataclass
class Verdict:
    label: str
    code: str
    delta_bps: Optional[float]
    delta_pct: Optional[float]


def classify(measured_bps: Optional[float], configured_bps: float,
            tolerance: float = TOLERANCE) -> Verdict:
    """D4's three-way call: within tolerance / outside tolerance (configured
    overestimates - conservative, not dangerous) / DANGEROUS (configured
    UNDER measured beyond tolerance - the pretrade EV gate is underpricing
    real cost, the direction that can let a net-losing trade clear the
    gate). measured_bps=None (no data) or a non-positive configured
    baseline both mean "insufficient data" - never a fabricated verdict."""
    if measured_bps is None or configured_bps <= 0:
        return Verdict("insufficient data", Code.XV_COST_INSUFFICIENT.value,
                       None, None)
    delta_bps = measured_bps - configured_bps
    delta_pct = delta_bps / configured_bps
    if abs(delta_pct) <= tolerance:
        return Verdict("within tolerance (+/-20%, spec D4)",
                       Code.XV_COST_WITHIN_TOLERANCE.value,
                       delta_bps, delta_pct)
    if measured_bps > configured_bps:
        return Verdict(
            "DANGEROUS: configured UNDER measured (gate underprices real "
            "cost - the direction that can let a net-losing trade clear "
            "the EV gate)",
            Code.XV_COST_DANGEROUS.value, delta_bps, delta_pct)
    return Verdict(
        "outside tolerance (configured overestimates - conservative "
        "direction, not dangerous)",
        Code.XV_COST_OUTSIDE_TOLERANCE.value, delta_bps, delta_pct)


# ------------------------------------------------------------------- report
def build_report(config_path=DEFAULT_CONFIG,
                 postmortem_csv=DEFAULT_POSTMORTEM_CSV,
                 audit_path=DEFAULT_AUDIT,
                 tolerance: float = TOLERANCE) -> str:
    cfg = load_config(config_path)
    maker_cfg, taker_cfg = configured_fees(cfg)
    round_trip_cfg = maker_cfg + taker_cfg

    maker_meas, taker_meas, n_records, n_pairs = read_om080_fee_recon(audit_path)
    tier_ctx = read_om080_tier_context(audit_path)
    overruns, n_rows, n_dupe = read_postmortem_overruns(postmortem_csv)
    n_rt = len(overruns)
    mean_overrun = sum(overruns) / n_rt if n_rt else None
    rt_measured = (round_trip_cfg + mean_overrun) if mean_overrun is not None \
        else None

    maker_verdict = classify(maker_meas, maker_cfg, tolerance)
    rt_verdict = classify(rt_measured, round_trip_cfg, tolerance)

    lines = []
    lines.append("=== Cost Truth Report (T7) — spec D4: measured, never "
                 "assumed ===")
    lines.append(f"configured: pretrade.maker_fee_bps={maker_cfg:.1f} "
                 f"taker_fee_bps={taker_cfg:.1f}  "
                 f"(round-trip fee assumption maker+taker="
                 f"{round_trip_cfg:.1f} bps)")
    lines.append(f"tolerance: +/-{tolerance * 100:.0f}% (spec D4)")
    lines.append("")

    lines.append("[1] MAKER-LEG bps — source: OM-080 fee_recon audit "
                 f"records ({audit_path})")
    lines.append(f"    n_records={n_records}  n_pairs_in_latest={n_pairs}")
    if maker_meas is None:
        lines.append(
            f"    insufficient data (n={n_records}) — OM-080 has never "
            "fired (no live Kraken credentials configured, fee_recon "
            "disabled, or every reconciliation to date matched within "
            "tolerance). Absence is NOT evidence the configured maker bps "
            "is correct — no independent venue measurement exists yet.")
    else:
        lines.append(f"    measured maker-leg = {maker_meas:.2f} bps "
                     f"(actual Kraken tier, most recent OM-080 record)")
        lines.append(f"    configured maker-leg = {maker_cfg:.2f} bps")
        lines.append(f"    delta = {maker_verdict.delta_bps:+.2f} bps "
                     f"({maker_verdict.delta_pct * 100:+.1f}%)")
        lines.append(f"    VERDICT [{maker_verdict.code}]: "
                     f"{maker_verdict.label}")
        if taker_meas is not None:
            lines.append(f"    (context) measured taker-leg = "
                         f"{taker_meas:.2f} bps vs configured "
                         f"{taker_cfg:.2f} bps")
        lines.extend(tier_context_lines(tier_ctx))
    lines.append("")

    lines.append("[2] ROUND-TRIP bps — source: postmortem cost_overrun_bps "
                 f"({postmortem_csv})")
    lines.append(f"    n={n_rt} unique closed trades  "
                 f"({n_rows} rows read, {n_dupe} duplicate position_id "
                 "row(s) dropped)")
    if n_rt < 10:
        lines.append("    (n<10: sample is thin — interpret cautiously)")
    if rt_measured is None:
        lines.append(f"    insufficient data (n={n_rt})")
    else:
        lines.append(f"    mean cost_overrun = {mean_overrun:+.2f} bps  "
                     "(assumes configured pretrade fee bps unchanged "
                     "since these trades opened — this script cannot see "
                     "config.json's history)")
        lines.append(f"    measured round-trip = {round_trip_cfg:.2f} + "
                     f"{mean_overrun:+.2f} = {rt_measured:.2f} bps")
        lines.append(f"    configured round-trip = {round_trip_cfg:.2f} bps")
        lines.append(f"    delta = {rt_verdict.delta_bps:+.2f} bps "
                     f"({rt_verdict.delta_pct * 100:+.1f}%)")
        lines.append(f"    VERDICT [{rt_verdict.code}]: {rt_verdict.label}")
    lines.append("")

    e_bps, x_bps, n_fills, n_noqty = read_audit_fill_costs(audit_path)
    lines.append("[3] POPULATION fee bps — source: OM-000 terminal-fill "
                 f"audit records ({audit_path})")
    lines.append(f"    n_fills_seen={n_fills}  entry_legs={len(e_bps)}  "
                 f"exit_legs={len(x_bps)}")
    if n_noqty:
        lines.append(f"    {n_noqty} legacy fill(s) lack notional "
                     "(records predate 2026-07-28's filled_units/"
                     "notional_usd fields) — skipped, not fabricated")
    if e_bps and x_bps and (len(e_bps) + len(x_bps)) >= 10:
        mean_e = sum(e_bps) / len(e_bps)
        mean_x = sum(x_bps) / len(x_bps)
        pop_rt = mean_e + mean_x
        pop_verdict = classify(pop_rt, round_trip_cfg, tolerance)
        if (len(e_bps) + len(x_bps)) < 30:
            lines.append("    (n<30: sample is thin — interpret cautiously)")
        lines.append(f"    mean entry-leg = {mean_e:.2f} bps vs configured "
                     f"maker {maker_cfg:.2f}")
        lines.append(f"    mean exit-leg = {mean_x:.2f} bps vs configured "
                     f"taker {taker_cfg:.2f}")
        lines.append(f"    measured round-trip = {mean_e:.2f} + "
                     f"{mean_x:.2f} = {pop_rt:.2f} bps")
        lines.append(f"    configured round-trip = {round_trip_cfg:.2f} bps")
        lines.append(f"    delta = {pop_verdict.delta_bps:+.2f} bps "
                     f"({pop_verdict.delta_pct * 100:+.1f}%)")
        lines.append(f"    VERDICT [{pop_verdict.code}]: {pop_verdict.label}")
        lines.append("    (unlike [2], this is the WHOLE fill population — "
                     "no postmortem trigger bias; excludes non-fee costs "
                     "like slippage, which [2] includes)")
    else:
        lines.append(
            f"    insufficient data (entry={len(e_bps)} exit={len(x_bps)}, "
            "need both legs and >=10 total) — accrues from every terminal "
            "fill going forward")
    lines.append("")

    lines.append("=== Notes / caveats ===")
    lines.append(
        "- postmortem_summary.csv only contains trades whose postmortem "
        "TRIGGERED (stopped out, or shortfall past ml/postmortem.py's "
        "shortfall_ratio) — it is NOT the full closed-trade corpus. [2] "
        "measures the underperforming subset, not a population-wide "
        "average.")
    lines.append(
        "- [2]'s derivation assumes today's configured "
        "pretrade.maker_fee_bps/taker_fee_bps match what was configured "
        "when each historical trade opened. If config changed since, "
        "re-derive with the historical bps.")
    lines.append(
        "- report-only: nothing here mutates config.json. Any config "
        "change is a conscious operator/controller commit (spec D4).")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--postmortem-csv", default=DEFAULT_POSTMORTEM_CSV)
    ap.add_argument("--audit", default=DEFAULT_AUDIT)
    ap.add_argument("--tolerance", type=float, default=TOLERANCE)
    args = ap.parse_args(argv)
    report = build_report(args.config, args.postmortem_csv, args.audit,
                          args.tolerance)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
