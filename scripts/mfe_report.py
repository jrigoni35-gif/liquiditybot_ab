#!/usr/bin/env python3
"""WHAT THE GIVE-BACK OVERLAY ACTUALLY COSTS, IN DOLLARS.

WHY THIS EXISTS (2026-09-16). A firing audit established, from four config
values and no statistics at all, that the give-back trail can never pay a
labelled-PT-sized win while the bracket is armed: the label's profit target
sits at pt_cost_mult*cost, the trail locks (1 - giveback_frac) of peak, so
banking the target THROUGH the trail needs a peak of target/lock - and the
bracket's profit leg fires the instant price touches the target.

That is a STRUCTURAL certainty. Its DOLLAR COST was explicitly left NOT
ESTABLISHED, because "the overlay censored a winner" and "the market never
offered one" are the same observation in a ledger that records only the exit
price. Separating them needs the PEAK, and the peak was unrecoverable: the
engine tracks Position.high_water live and persists it for OPEN positions
(core/state.py, core/persistence.py), but NOTHING writes it to a durable
ledger when the position closes. fills.csv has no such column. The peak dies
with the trade.

THIS FILE RECOVERS IT BACKWARDS, from the price path. For every closed trip
it reconstructs the MAXIMUM FAVOURABLE EXCURSION - the best the trade was
ever worth between entry and exit - from the 5-minute candle store, and
compares it to the LABELLED profit target that trade actually carried, joined
per-position from signal_history.csv rather than re-derived. Then it asks the
only question that matters: for trades the overlay closed, had the labelled
win ALREADY been available?

REPORT-ONLY. Reads outputs/, writes nothing anywhere, touches no decision
path. It changes no threshold and no verdict.

THREE LIMITS, none of them small, all printed with the answer:
  1. CANDLE HIGH IS AN UPPER BOUND ON WHAT THE ENGINE COULD HAVE SEEN. A 5 m
     bar's high may have existed for a second between two of the bot's polls.
     So "the labelled win was available" here means available TO THE MARKET,
     never "the bot could have taken it". This biases the cost UPWARD and the
     bias is not small.
  2. COVERAGE ENDS BEFORE THE CURRENT ERA. The candle store's last 5 m bar
     predates the era-12 cut, so the accruing cohort is NOT in this report.
     What is covered is the earlier eras, under the SAME give-back arm and
     lock (both on every cut's untouched list) but DIFFERENT labelled widths
     - which is why the target is joined per trip instead of assumed.
  3. ONLY TRIPS CARRYING A LABELLED TARGET ARE SCORED. A trip with no
     signal_history row has no target to be measured against and is counted
     as unscored rather than assumed.

Usage:  python scripts/mfe_report.py [--json] [--era ERA] [--min-trips N]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UNKNOWN = "UNKNOWN"
#: Exit reasons that are the SENIOR OVERLAY pre-empting the bracket. Matched
#: as a prefix because the tier reasons carry an index ("tier 1", "tier 2").
OVERLAY_PREFIXES = ("tier trail", "tier ", "time-stop scratch")
#: Exit reasons that ARE the labelled bracket resolving on its own terms.
BRACKET_REASONS = ("tb_pt", "tb_sl", "tb_time")


def _f(row: dict, key: str, default: float = 0.0) -> float:
    try:
        v = row.get(key)
        return default if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return default


def _stamp(p: Path) -> str:
    try:
        return dt.datetime.fromtimestamp(
            p.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        return UNKNOWN


def _utc(ts: float) -> str:
    return dt.datetime.fromtimestamp(
        ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_targets(history: Path) -> dict:
    """position_id -> the LABELLED profit/stop this trade actually carried.

    Joined, never re-derived. The barrier geometry moved three times across
    the covered window (the cost floor steps with every fee re-book) while
    label_era encodes only the horizon, so assuming one width would silently
    price a 2.40% trade against a 1.80% target.

    csv module, never a plain comma split: 4,932 rows of this file carry
    commas inside quoted fields and a naive split reads the wrong column.
    """
    out: dict = {}
    try:
        with history.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                pid = (row.get("position_id") or "").strip()
                if not pid:
                    continue
                pt = _f(row, "pt_frac")
                if pt <= 0:
                    continue
                out[pid] = {
                    "pt_frac": pt,
                    "sl_frac": _f(row, "sl_frac"),
                    "label_era": (row.get("label_era") or "").strip(),
                    "barrier": (row.get("barrier") or "").strip(),
                    "probe": (row.get("probe") or "").strip(),
                }
    except OSError:
        return {}
    return out


def load_trips(fills: Path) -> list[dict]:
    """Closed trips from the fill ledger: entry, exit, side, size, reason.

    DELIBERATELY SIMPLER than scripts/cohort_eval.py's pre-registered
    reconstruction - no size tolerance, no book filter. This answers "what
    did the price do while we held it", not "what is the cohort", and must
    never be quoted as a cohort count.
    """
    legs: dict[str, list[dict]] = defaultdict(list)
    try:
        with fills.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                pid = (row.get("position_id") or "").strip()
                if pid:
                    legs[pid].append(row)
    except OSError:
        return []
    trips: list[dict] = []
    for pid, rows in legs.items():
        rows.sort(key=lambda r: _f(r, "ts"))
        sides = {(r.get("side") or "").strip().lower() for r in rows}
        if len(sides) < 2:
            # NEVER CLOSED. This guard is REDUNDANT with the opens/exits check
            # below and is kept deliberately: a one-sided position is excluded
            # twice, by "only one side present" and by "no exit leg". A
            # mutation sweep on 2026-09-16 recorded it as a SURVIVOR, and an
            # injection proved why - removing this line alone still yields 0
            # trips because the second guard catches it independently. That is
            # defence in depth, not a weak pin, and it is recorded here so the
            # next sweep does not spend a round rediscovering it.
            continue
        first = (rows[0].get("side") or "").strip().lower()
        long_side = first == "buy"
        opens = [r for r in rows
                 if (r.get("side") or "").strip().lower() == first]
        exits = [r for r in rows
                 if (r.get("side") or "").strip().lower() != first]
        if not opens or not exits:
            continue
        qty = sum(_f(r, "fill_size") for r in opens)
        if qty <= 0:
            continue
        entry_px = sum(_f(r, "fill_size") * _f(r, "fill_price")
                       for r in opens) / qty
        xqty = sum(_f(r, "fill_size") for r in exits) or 1.0
        exit_px = sum(_f(r, "fill_size") * _f(r, "fill_price")
                      for r in exits) / xqty
        if entry_px <= 0 or exit_px <= 0:
            continue
        trips.append({
            "pid": pid,
            "symbol": (rows[0].get("symbol") or "").strip(),
            "long": long_side,
            "t_open": _f(rows[0], "ts"),
            "t_close": max(_f(r, "ts") for r in exits),
            "entry_px": entry_px,
            "exit_px": exit_px,
            "qty": qty,
            "notional": qty * entry_px,
            "fees": sum(_f(r, "fees_delta_usd") for r in rows),
            "reason": (exits[-1].get("reason") or "").strip(),
            "era": (rows[-1].get("exec_era") or "").strip(),
        })
    return trips


def candle_path(symbol: str, candle_dir: Path, interval: int = 300) -> Path:
    """Where this symbol's bars live.

    SPLIT OUT SO IT CAN BE PINNED. The store keys on the BASE asset ('ETH'),
    the ledger on the pair ('ETH/USD'). Getting this wrong returns None for
    every symbol, scores every trip UNCOVERED, and the report then says
    nothing was measurable - silently, and in the flattering direction. A
    test that only checks "a bad path returns None" cannot tell a correct
    mapping from a broken one, so the mapping itself is the pinnable unit.
    """
    base = symbol.split("/")[0].strip().upper()
    return candle_dir / f"{base}_{interval}.parquet"


def load_candles(symbol: str, candle_dir: Path, interval: int = 300):
    """(t_open_s, high, low) arrays for one symbol, or None."""
    p = candle_path(symbol, candle_dir, interval)
    if not p.exists():
        return None
    try:
        import pandas as pd
    except ImportError:
        return None
    try:
        df = pd.read_parquet(p, columns=["t_open_s", "high", "low"])
    except Exception:                                       # noqa: BLE001
        return None
    if df.empty:
        return None
    df = df.sort_values("t_open_s")
    return (df["t_open_s"].to_numpy(dtype="int64"),
            df["high"].to_numpy(dtype="float64"),
            df["low"].to_numpy(dtype="float64"))


def excursion(trip: dict, candles, interval: int = 300) -> dict:
    """Maximum favourable excursion over the trip's own holding window.

    FAVOURABLE IS SIDE-DEPENDENT: a long's best is the highest HIGH, a short's
    best is the lowest LOW. Using the high for both would score every short
    backwards, and a short scored backwards looks like a censored winner.

    The window is [t_open, t_close] on BAR OPENS (the store's ts_anchor), and
    the bar containing t_close is included: the exit happened inside it, so
    its extreme was reachable before the exit fired.
    """
    if candles is None:
        return {"covered": False, "reason": "no candles for this symbol"}
    ts, hi, lo = candles
    a, b = trip["t_open"], trip["t_close"]
    if b < a:
        return {"covered": False, "reason": "exit precedes entry"}
    lo_i = int((ts >= a - interval).argmax()) if (ts >= a - interval).any() else None
    if lo_i is None or ts[-1] < a:
        return {"covered": False, "reason": "window starts after coverage ends"}
    mask = (ts >= a - interval) & (ts <= b)
    n = int(mask.sum())
    if n == 0:
        return {"covered": False, "reason": "no bars inside the window"}
    if ts[mask][-1] + interval < b:
        return {"covered": False, "reason": "coverage ends before the exit"}
    e = trip["entry_px"]
    best = float(hi[mask].max()) if trip["long"] else float(lo[mask].min())
    mfe_pct = ((best - e) / e * 100.0) if trip["long"] else ((e - best) / e * 100.0)
    realized = (((trip["exit_px"] - e) / e * 100.0) if trip["long"]
                else ((e - trip["exit_px"]) / e * 100.0))
    return {"covered": True, "bars": n, "best_px": best,
            "mfe_pct": mfe_pct, "realized_pct": realized}


def score(trips: list[dict], targets: dict, candle_dir: Path,
          era: str | None = None) -> dict:
    """Join, measure, and classify. Nothing here decides anything."""
    cache: dict = {}
    scored, unscored, uncovered = [], 0, 0
    for t in trips:
        if era and t["era"] != era:
            continue
        tgt = targets.get(t["pid"])
        if not tgt:
            unscored += 1
            continue
        sym = t["symbol"]
        if sym not in cache:
            cache[sym] = load_candles(sym, candle_dir)
        ex = excursion(t, cache[sym])
        if not ex.get("covered"):
            uncovered += 1
            continue
        pt_pct = tgt["pt_frac"] * 100.0
        row = dict(t)
        row.update(ex)
        row["pt_pct"] = pt_pct
        row["reached_pt"] = ex["mfe_pct"] >= pt_pct
        row["gave_back_pct"] = ex["mfe_pct"] - ex["realized_pct"]
        # SHORTFALL against the labelled target, and only for trades where
        # that target was demonstrably available. Never against the peak:
        # nobody exits at the peak, and pricing against it would manufacture a
        # loss out of hindsight.
        #
        # CLAMPED AT ZERO, and the first version was not. A trade that exits
        # ABOVE its labelled target (every tb_pt leg does, by a slipped tick)
        # produced a NEGATIVE "forgone", which summed into the total and made
        # the overlay's cost read as -$0.73 - a number with no meaning that a
        # reader would take for a profit. Exiting better than the target is
        # not forgone; it is counted separately.
        shortfall = ((pt_pct - ex["realized_pct"]) / 100.0) * t["notional"]
        row["shortfall_usd"] = (max(0.0, shortfall) if row["reached_pt"]
                                else 0.0)
        row["beat_target"] = bool(row["reached_pt"] and shortfall < 0)
        # THE GIVE-BACK ITSELF: peak to exit, in dollars. This is the number
        # that matters when the labelled target was never reachable - it is
        # what the overlay handed back of what it had. HINDSIGHT-PRICED and
        # labelled as such: no rule can exit at the peak, so this is an upper
        # bound on any achievable improvement, not a debt owed.
        row["giveback_usd"] = (row["gave_back_pct"] / 100.0) * t["notional"]
        row["overlay"] = t["reason"].startswith(OVERLAY_PREFIXES)
        row["bracket"] = t["reason"] in BRACKET_REASONS
        scored.append(row)
    return {"scored": scored, "unscored": unscored, "uncovered": uncovered}


def summarize(rows: list[dict]) -> dict:
    """Per-class aggregates. Classes are NOT pooled: the whole question is
    whether the overlay behaves differently from the bracket."""
    def agg(sel: list[dict]) -> dict:
        if not sel:
            return {"n": 0}
        mfe = [r["mfe_pct"] for r in sel]
        real = [r["realized_pct"] for r in sel]
        reached = [r for r in sel if r["reached_pt"]]
        return {
            "n": len(sel),
            "reached_pt": len(reached),
            "reached_pt_pct": round(100.0 * len(reached) / len(sel), 1),
            "mfe_pct_median": round(statistics.median(mfe), 3),
            "realized_pct_median": round(statistics.median(real), 3),
            "gave_back_pct_median": round(
                statistics.median([r["gave_back_pct"] for r in sel]), 3),
            "shortfall_usd_total": round(sum(r["shortfall_usd"] for r in sel), 2),
            "beat_target": sum(1 for r in sel if r["beat_target"]),
            # hindsight-priced upper bound, never a debt
            "giveback_usd_total": round(sum(r["giveback_usd"] for r in sel), 2),
            "giveback_usd_median": round(
                statistics.median([r["giveback_usd"] for r in sel]), 3),
            "notional_median": round(
                statistics.median([r["notional"] for r in sel]), 2),
        }
    by_reason: dict = {}
    for r in rows:
        by_reason.setdefault(r["reason"] or "(blank)", []).append(r)
    return {
        "all": agg(rows),
        "overlay": agg([r for r in rows if r["overlay"]]),
        "bracket": agg([r for r in rows if r["bracket"]]),
        "by_reason": {k: agg(v) for k, v in
                      sorted(by_reason.items(), key=lambda kv: -len(kv[1]))},
    }


def collect(era: str | None = None, history: str | None = None) -> dict:
    outputs = Path(os.environ.get("LB_OUTPUTS") or (ROOT / "outputs"))
    fills_p = outputs / "fills.csv"
    hist_p = Path(history) if history else (outputs / "signal_history.csv")
    candle_dir = outputs / "candles" / "parquet"
    trips = load_trips(fills_p)
    targets = load_targets(hist_p)
    res = score(trips, targets, candle_dir, era=era)
    cov_hi = None
    try:
        import pandas as pd
        ends = []
        for f in sorted(candle_dir.glob("*_300.parquet")):
            d = pd.read_parquet(f, columns=["t_open_s"])
            if not d.empty:
                ends.append(int(d["t_open_s"].max()))
        cov_hi = max(ends) if ends else None
    except Exception:                                       # noqa: BLE001
        cov_hi = None
    return {
        "read_at": dt.datetime.now(dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "stamps": {"fills.csv": _stamp(fills_p),
                   "signal_history.csv": _stamp(hist_p)},
        "era_filter": era or "(all)",
        "trips_closed": len(trips),
        "unscored_no_label": res["unscored"],
        "uncovered_no_candles": res["uncovered"],
        "coverage_ends": _utc(cov_hi) if cov_hi else UNKNOWN,
        "summary": summarize(res["scored"]),
        "rows": res["scored"],
    }


def render(d: dict) -> str:
    L: list[str] = []
    a = L.append
    s = d["summary"]
    a("=" * 76)
    a("MFE REPORT - what the give-back overlay cost, in dollars")
    a("=" * 76)
    a(f"read at {d['read_at']}   era filter {d['era_filter']}")
    for k, v in d["stamps"].items():
        a(f"  {k:22} mtime {v}")
    a(f"  candle coverage ends   {d['coverage_ends']}")
    a("")
    a(f"closed trips {d['trips_closed']}   scored {s['all'].get('n', 0)}   "
      f"no label {d['unscored_no_label']}   no candles {d['uncovered_no_candles']}")
    if not s["all"].get("n"):
        a("")
        a("NOTHING SCORED. Every closed trip either carries no labelled target")
        a("or falls outside candle coverage. This is a COVERAGE result, not a")
        a("finding about the strategy - do not read it as one.")
        return "\n".join(L)
    a("")
    a(f"{'class':<14}{'n':>5}{'reached PT':>13}{'MFE %':>8}"
      f"{'got %':>8}{'gave bk %':>10}{'shortfall $':>13}{'giveback $':>12}")
    for name in ("all", "overlay", "bracket"):
        g = s[name]
        if not g.get("n"):
            a(f"{name:<14}{0:>5}")
            continue
        a(f"{name:<14}{g['n']:>5}{g['reached_pt']:>6} "
          f"({g['reached_pt_pct']:>4.1f}%){g['mfe_pct_median']:>8.2f}"
          f"{g['realized_pct_median']:>8.2f}{g['gave_back_pct_median']:>10.2f}"
          f"{g['shortfall_usd_total']:>13.2f}{g['giveback_usd_total']:>12.2f}")
    a("")
    a("by exit reason:")
    for reason, g in list(s["by_reason"].items())[:10]:
        if not g.get("n"):
            continue
        a(f"  {reason[:24]:<26}{g['n']:>4}  reached PT {g['reached_pt']:>3}"
          f" ({g['reached_pt_pct']:>5.1f}%)  MFE {g['mfe_pct_median']:>6.2f}%"
          f"  got {g['realized_pct_median']:>6.2f}%"
          f"  gave back ${g['giveback_usd_total']:>7.2f}")
    a("")
    a("HOW TO READ THIS, and the three limits are not small:")
    a("  * 'reached PT' means the MARKET offered the labelled target while we")
    a("    held the trade. It does NOT mean the bot could have taken it: a 5 m")
    a("    bar's high may have lived for a second between two polls. This biases")
    a("    every number here UPWARD.")
    a("  * 'shortfall $' is priced against the LABELLED TARGET and counts only")
    a("    trades where that target was demonstrably available. It is clamped")
    a("    at zero: exiting ABOVE the target is not forgone.")
    a("  * 'giveback $' is peak-to-exit and is HINDSIGHT-PRICED. No rule can")
    a("    exit at the peak, so it is an UPPER BOUND on any achievable")
    a("    improvement - never a debt owed. It is the number that matters when")
    a("    the labelled target was never reachable in the first place.")
    a("  * Coverage ends before the current era, so the ACCRUING cohort is not")
    a("    in this report. The give-back arm and lock are unchanged across the")
    a("    covered window; the labelled widths are NOT, which is why the target")
    a("    is joined per trip rather than assumed.")
    a("Report-only. No order path was read or touched.")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Maximum favourable excursion per closed trip.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--era", default=None, help="restrict to one exec_era")
    ap.add_argument("--history", default=None)
    args = ap.parse_args(argv)
    d = collect(era=args.era, history=args.history)
    if args.json:
        print(json.dumps(d, indent=2, default=str))
    else:
        print(render(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
