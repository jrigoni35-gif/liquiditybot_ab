"""
scripts/lessons_digest.py

TA-A1 (per-decision outcome ledger + lessons digest,
docs/research/2026-07-23_tradingagents_gap.md §A1) shaped by FinMem's
decay-tiered memory (arXiv 2311.13743), ADAPTED as deterministic
retention tiers per docs/research/2026-07-24_compounder_context_evidence.md
pass-2 §2.5: "per asset/regime: last-N postmortems verbatim, trailing-
quarter aggregate, all-time archive; tiers config-lifted as conventions;
offline reporting shape only, no LLM, no engine import."

Joins already-audited dispositions to their realized outcome, entirely
OFFLINE: reads outputs/postmortem_summary.csv, outputs/weekly_ledger.csv,
outputs/monthly_ledger.csv, and outputs/session_digest.json (all if
present), and writes outputs/lessons_digest.md. Registers zero engine
state, zero new Code, is never imported by cycle_once or any live path,
and lives at the same trust tier as assurance_check.py/overfit_check.py's
output: a read-only dev-process artifact.

CONVENTIONS (reporting-layer choices, not fitted knobs; change the
constants below, not the logic, if a tier size needs to move):

  * Tier 1 "last-N verbatim" - the LAST_N_VERBATIM most recent postmortem
    rows for a bucket (asset or regime), newest first, printed with their
    raw fields. A literal excerpt, not a summary.
  * Tier 2 "trailing-quarter aggregate" - rows within TRAILING_QUARTER_DAYS
    days of the NEWEST row's own timestamp IN THAT BUCKET (never
    wall-clock "now" - this script is offline and deterministic; the
    same inputs must produce byte-identical output regardless of when it
    is run). 91 days approximates a calendar quarter; this is a
    convention for grouping, not a statistical claim about cycle length.
  * Tier 3 "all-time archive" - every row ever recorded for the bucket:
    counts + net.
  * "hit" (tier 2's hit rate) := realized_pct > 0.0 - the position still
    closed net positive despite the shortfall-vs-expectation that
    triggered this postmortem in the first place. Rows with an
    unparsable realized_pct are excluded from both the numerator and the
    denominator (never guessed).
  * "net" := the sum of realized_pct (percentage points) over the
    bucket's rows with a parsable realized_pct - a lessons-digest-only
    aggregate over the postmortem (shortfall) population, NOT the full
    trade blotter or a dollar P&L; postmortem_summary.csv carries no
    per-trade notional.
  * Grouping regime = regime_entry (the regime observed at trade entry,
    causally prior to the outcome). regime_exit is still shown verbatim
    in Tier 1 lines but never used for grouping, so a regime-transition
    trade is not double-counted under two "by regime" buckets.
  * Dominant-cause ties break alphabetically (deterministic regardless of
    input row order).
  * A row is USABLE if its ts parses to a float and asset is non-empty;
    any other field that fails to parse degrades to None/"n/a" for that
    field alone rather than dropping the row.
  * Any missing/unreadable/empty input file degrades its section to
    "no data" text - this script never raises on a missing or malformed
    input.
  * No timestamps beyond the newest input row's own appear anywhere in
    the output (no wall-clock "now") - required for byte-identical
    reruns against the same inputs.

Stdlib only. NO engine imports (nothing from main.py, runner.py,
core/, ml/, execution/, risk/, data/, sentiment/, api/). No LLM calls,
no network I/O.

Usage:
    python scripts/lessons_digest.py                    # reads ./outputs
    python scripts/lessons_digest.py --outputs-dir DIR   # a saved run
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---- tier size / window constants (reporting-layer conventions) ----------
LAST_N_VERBATIM = 10
TRAILING_QUARTER_DAYS = 91.0
DEFAULT_OUTPUTS_DIR = "outputs"
OUTPUT_FILENAME = "lessons_digest.md"

POSTMORTEM_FILENAME = "postmortem_summary.csv"
WEEKLY_LEDGER_FILENAME = "weekly_ledger.csv"
MONTHLY_LEDGER_FILENAME = "monthly_ledger.csv"
SESSION_DIGEST_FILENAME = "session_digest.json"

_NUMERIC_FIELDS = ("p_win", "expected_pct", "realized_pct", "shortfall_pct",
                   "cost_overrun_bps", "mfe_pct", "mae_pct")


def _to_float(x) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC")


def _fmt_pct(x: Optional[float]) -> str:
    return f"{x:+.2f}%" if x is not None else "n/a"


# ---------------------------------------------------------------------------
# input readers - each degrades to an empty/absent result, never raises
# ---------------------------------------------------------------------------
def read_postmortems(outputs_dir: Path) -> list:
    """Returns a list of dicts (one per usable postmortem row). A row is
    USABLE when its ts parses to a float and asset is non-empty; any other
    field that fails to parse becomes None rather than dropping the row.
    Missing file, empty file, or unreadable/malformed CSV -> []."""
    path = Path(outputs_dir) / POSTMORTEM_FILENAME
    out = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for raw in reader:
                ts = _to_float(raw.get("ts"))
                asset = (raw.get("asset") or "").strip()
                if ts is None or not asset:
                    continue
                row = {
                    "ts": ts,
                    "position_id": (raw.get("position_id") or "").strip(),
                    "asset": asset,
                    "direction": (raw.get("direction") or "").strip(),
                    "cause": (raw.get("cause") or "").strip() or "unknown",
                    "regime_entry": (raw.get("regime_entry") or "").strip()
                        or "unknown",
                    "regime_exit": (raw.get("regime_exit") or "").strip()
                        or "unknown",
                }
                for f_name in _NUMERIC_FIELDS:
                    row[f_name] = _to_float(raw.get(f_name))
                row["recovered_after_stop"] = _to_float(
                    raw.get("recovered_after_stop"))
                out.append(row)
    except (OSError, csv.Error):
        return []
    return out


def read_ledger_rows(path: Path) -> list:
    """Generic ledger CSV reader (weekly/monthly goal ledgers). Missing
    file, empty file, or unreadable/malformed CSV -> []."""
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except (OSError, csv.Error):
        return []


def read_session_digest(path: Path) -> dict:
    """Missing file or unreadable/malformed JSON -> {}."""
    try:
        parsed = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            return {}
        return parsed
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------------------
# aggregation helpers (pure functions over already-loaded rows)
# ---------------------------------------------------------------------------
def dominant_cause(rows: list) -> Optional[str]:
    if not rows:
        return None
    counts = Counter(r["cause"] for r in rows)
    # deterministic tie-break: highest count, then alphabetical
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def hit_rate(rows: list):
    """(hits, total) over rows with a parsable realized_pct; total == 0
    (hits == 0) means none do - the caller renders that as "n/a"."""
    usable = [r for r in rows if r.get("realized_pct") is not None]
    hits = sum(1 for r in usable if r["realized_pct"] > 0.0)
    return hits, len(usable)


def net_realized(rows: list) -> float:
    return round(sum(r["realized_pct"] for r in rows
                     if r.get("realized_pct") is not None), 2)


def _newest_ts(rows: list) -> Optional[float]:
    tss = [r["ts"] for r in rows]
    return max(tss) if tss else None


def trailing_quarter_rows(rows: list) -> list:
    """Rows within TRAILING_QUARTER_DAYS of THIS bucket's own newest ts -
    never wall-clock "now" (offline determinism)."""
    newest = _newest_ts(rows)
    if newest is None:
        return []
    cutoff = newest - TRAILING_QUARTER_DAYS * 86400.0
    return [r for r in rows if r["ts"] >= cutoff]


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
def _render_tier1(rows: list) -> str:
    if not rows:
        return "**Tier 1 — last-N verbatim**\n\nno data\n"
    newest_first = sorted(rows, key=lambda r: r["ts"], reverse=True)
    top = newest_first[:LAST_N_VERBATIM]
    lines = [f"**Tier 1 — last {LAST_N_VERBATIM} verbatim** "
            f"({len(top)} of {len(rows)} shown)", ""]
    for r in top:
        pid = r["position_id"][:8] or "(no-id)"
        lines.append(
            f"- {_fmt_ts(r['ts'])} | {pid} | {r['asset']} {r['direction']} "
            f"| cause={r['cause']} | realized={_fmt_pct(r['realized_pct'])} "
            f"| shortfall={_fmt_pct(r['shortfall_pct'])} "
            f"| regime {r['regime_entry']}->{r['regime_exit']}")
    return "\n".join(lines) + "\n"


def _render_tier2(rows: list) -> str:
    tq = trailing_quarter_rows(rows)
    newest = _newest_ts(rows)
    if not tq or newest is None:
        return "**Tier 2 — trailing quarter**\n\nno data\n"
    hits, total = hit_rate(tq)
    hit_str = (f"{hits}/{total} ({hits / total * 100.0:.1f}%)"
              if total else "n/a")
    lines = [
        f"**Tier 2 — trailing quarter "
        f"({int(TRAILING_QUARTER_DAYS)}d, ending {_fmt_ts(newest)})**", "",
        f"- dominant cause: {dominant_cause(tq)} | hit rate: {hit_str} "
        f"| net: {net_realized(tq):+.2f}% | n={len(tq)}",
    ]
    return "\n".join(lines) + "\n"


def _render_tier3(rows: list) -> str:
    if not rows:
        return "**Tier 3 — all-time archive**\n\nno data\n"
    lines = [
        "**Tier 3 — all-time archive**", "",
        f"- n={len(rows)} | net: {net_realized(rows):+.2f}%",
    ]
    return "\n".join(lines) + "\n"


def _render_bucket(name: str, rows: list) -> str:
    parts = [f"### {name}", ""]
    parts.append(_render_tier1(rows))
    parts.append(_render_tier2(rows))
    parts.append(_render_tier3(rows))
    return "\n".join(parts)


def _group_by(rows: list, key: str) -> dict:
    out = defaultdict(list)
    for r in rows:
        out[r[key]].append(r)
    return dict(out)


def _render_goal_section(weekly_rows: list, monthly_rows: list) -> str:
    lines = ["## Goal attainment", ""]
    if not weekly_rows and not monthly_rows:
        return "\n".join(lines + ["no data", ""])
    if weekly_rows:
        w = weekly_rows[-1]
        lines.append(
            f"- latest week {w.get('week', '?')}: {w.get('category', '?')} "
            f"(goal={w.get('goal', '?')}, actual="
            f"{w.get('weekly_realized', '?')}, "
            f"attainment={w.get('attainment_pct', '?')}%)")
    else:
        lines.append("- weekly: no data")
    if monthly_rows:
        m = monthly_rows[-1]
        lines.append(
            f"- latest month {m.get('month', '?')}: "
            f"{m.get('category', '?')} (goal={m.get('goal', '?')}, actual="
            f"{m.get('monthly_realized', '?')}, "
            f"attainment={m.get('attainment_pct', '?')}%)")
    else:
        lines.append("- monthly: no data")
    lines.append("")
    return "\n".join(lines)


def _render_governor_section(session_digest: dict) -> str:
    model = session_digest.get("model") if session_digest else None
    if not isinstance(model, dict):
        return "## Governor\n\nno data\n"
    lines = [
        "## Governor", "",
        f"- monitor_level: {model.get('monitor_level', 'n/a')} "
        f"| use_model: {model.get('use_model', 'n/a')} "
        f"| brier: {model.get('brier', 'n/a')} "
        f"| history_rows: {model.get('history_rows', 'n/a')} "
        f"| cold: {model.get('cold', 'n/a')}", "",
    ]
    return "\n".join(lines)


def _render_data_through(postmortems: list, session_digest: dict) -> str:
    candidates = []
    pm_newest = _newest_ts(postmortems)
    if pm_newest is not None:
        candidates.append(pm_newest)
    gen_at = _to_float((session_digest or {}).get("generated_at"))
    if gen_at is not None:
        candidates.append(gen_at)
    if not candidates:
        return "Data through: no data (no inputs found)\n"
    return f"Data through: {_fmt_ts(max(candidates))} (newest input row)\n"


# ---------------------------------------------------------------------------
# top-level assembly
# ---------------------------------------------------------------------------
def build_digest(outputs_dir="outputs") -> str:
    """Pure: reads the four input artifacts under `outputs_dir` (any/all
    may be absent) and returns the digest markdown text. Never raises."""
    out_dir = Path(outputs_dir)
    postmortems = read_postmortems(out_dir)
    weekly_rows = read_ledger_rows(out_dir / WEEKLY_LEDGER_FILENAME)
    monthly_rows = read_ledger_rows(out_dir / MONTHLY_LEDGER_FILENAME)
    session_digest = read_session_digest(out_dir / SESSION_DIGEST_FILENAME)

    parts = [
        "# Lessons digest", "",
        "_Reporting layer only — no decision-path meaning, no engine "
        "import, no LLM, no network. TA-A1 (per-decision outcome view) "
        "shaped by FinMem's decay-tiered memory, adapted as deterministic "
        "retention tiers "
        "(docs/research/2026-07-24_compounder_context_evidence.md pass-2 "
        "§2.5): Tier 1 last-N verbatim, Tier 2 trailing-quarter aggregate, "
        "Tier 3 all-time archive._", "",
        _render_data_through(postmortems, session_digest),
        _render_goal_section(weekly_rows, monthly_rows),
        _render_governor_section(session_digest),
    ]

    parts.append("## By asset")
    parts.append("")
    if not postmortems:
        parts.append("no data")
        parts.append("")
    else:
        by_asset = _group_by(postmortems, "asset")
        for asset in sorted(by_asset):
            parts.append(_render_bucket(asset, by_asset[asset]))

    parts.append("## By regime")
    parts.append("")
    if not postmortems:
        parts.append("no data")
        parts.append("")
    else:
        by_regime = _group_by(postmortems, "regime_entry")
        for regime in sorted(by_regime):
            parts.append(_render_bucket(regime, by_regime[regime]))

    return "\n".join(parts) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outputs-dir", default=DEFAULT_OUTPUTS_DIR,
                    help="directory holding postmortem_summary.csv, "
                         "weekly/monthly ledgers, session_digest.json")
    ap.add_argument("--out", default=None,
                    help="output path (default: <outputs-dir>/"
                         + OUTPUT_FILENAME + ")")
    args = ap.parse_args(argv)

    text = build_digest(args.outputs_dir)
    out_path = Path(args.out) if args.out else \
        Path(args.outputs_dir) / OUTPUT_FILENAME
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
