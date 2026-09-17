#!/usr/bin/env python3
"""ONE PAGE FOR EVERYTHING THIS SYSTEM IS CURRENTLY THROWING AWAY.

WHY THIS EXISTS (2026-09-16). The operator said the corpus "can't learn if I
restart it every time I make a change". A restart destroys no disk store -
but something IS discarding most of his evidence, and no instrument anywhere
in this repo reported it in one place. The era-exclusion figure lives inside
status.json's ml.load_stats; the cohort exclusion exists only if you
reconstruct trips by hand; the stale-geometry share needs a per-row barrier
scan. He was feeling a real, large, invisible discard and attributing it to
the one mechanism he could see.

CLAUDE.md names the asymmetry that produced that blindness: the code that
tells you whether the governed code works is the code nothing governs. This
file is the missing governor's report - and it is REPORT-ONLY. It reads
outputs/ and writes nothing anywhere. It changes no threshold, no filter and
no decision; a discard it names is not thereby a defect, and several of them
are correct behaviour. What was missing was the SUM.

FOUR DISCARD PLANES, deliberately not blended:
  1. TRAINING CORPUS - rows the model never sees (parse, dirty, clash, epoch,
     era-exclusion). A LOAD-TIME VIEW: nothing is deleted from the file.
  2. TRADE COHORT - closed trips the era gate refuses to count, plus trips
     censored in flight by the stamp-purity rule.
  3. LABEL GEOMETRY - rows whose barrier floor the bot no longer uses. Not a
     discard at all; a CONTAMINATION, and the opposite failure (they are KEPT
     when arguably they should not be).
  4. PROCESS MEMORY - in-memory learning windows that die at a relaunch.

Usage:  python scripts/discard_ledger.py [--json] [--history PATH]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

UNKNOWN = "UNKNOWN"


def _stamp(p: Path) -> str:
    """The file's mtime in UTC. Every source here mutates under a live bot;
    a count without its stamp is not a measurement (CLAUDE.md rule c)."""
    try:
        m = dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc)
        return m.strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        return UNKNOWN


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ----------------------------------------------------------------- plane 1
def training_corpus(status: dict | None) -> dict:
    """What the model never sees, from the LOADER'S OWN telemetry.

    Read from status.json rather than re-running the loader: that is the
    number the LIVE fit actually used, and re-loading here would measure a
    different corpus snapshot and manufacture a two-route disagreement nobody
    needs. The trade-off is that this plane is only as fresh as the runner -
    the stamp says how fresh.
    """
    out: dict = {"available": False}
    load_stats = ((status or {}).get("ml") or {}).get("load_stats") or {}
    if not load_stats:
        out["reason"] = "status.json carries no ml.load_stats"
        return out
    era_block = load_stats.get("era_exclusion") or {}
    excluded = (era_block.get("excluded") or {}).get("total", 0) or 0
    named = {
        "parse errors": int(load_stats.get("dropped_parse", 0) or 0),
        "dirty rows": int(load_stats.get("dropped_dirty", 0) or 0),
        "id clash": int(load_stats.get("dropped_clash", 0) or 0),
        "epoch filter": int(load_stats.get("epoch_excluded", 0) or 0),
        "era exclusion": int(excluded),
    }
    rows = int(load_stats.get("rows", 0) or 0)
    total = sum(named.values())
    uniq = load_stats.get("mean_uniqueness")
    n_eff = None
    if isinstance(uniq, (int, float)) and rows:
        n_eff = round(rows * float(uniq), 1)
    out.update({
        "available": True,
        "rows_surviving": rows,
        "discards": named,
        "discard_total": total,
        "admissible": rows + total,
        "live_labels_surviving": int(load_stats.get("live_clean", 0) or 0),
        "mean_uniqueness": uniq,
        # de Prado average uniqueness computed PER (asset, 5m bar) by the
        # production loader (ml/history.py, the uniqueness_enabled block).
        # This is the authoritative effective n for this corpus. An
        # asset-BLIND route over the same rows reads far smaller because it
        # collapses every asset onto one path - report the route, always.
        "n_eff_per_asset": n_eff,
        "n_eff_route": "de Prado per-(asset, 5m bar), the production loader's own",
        "ess_kish": load_stats.get("ess_kish"),
        "era_filter_armed": bool(era_block.get("armed")),
        "era_filter_active": bool(era_block.get("active")),
        "era_exclusion_by_source": (era_block.get("excluded") or {}).get(
            "by_era_source"),
        "reversible_with": "config.json ml.era_exclusion.forced_off = true",
        "nothing_deleted": ("LOAD-TIME VIEW ONLY - ml/history.py says so "
                            "verbatim; every row is still in the file"),
    })
    return out


# ----------------------------------------------------------------- plane 2
def trade_cohort(fills_path: Path, current_era: str) -> dict:
    """Closed trips the era gate refuses, and trips censored in flight.

    A trip is an entry leg plus an exit leg sharing a position_id. A
    STRADDLER is a trip whose legs do not all carry one era stamp: the
    stamp-purity rule then excludes it from BOTH eras, so it is evidence
    that exists and counts for nothing. That censoring is the cost nobody
    prices, and its rate rises as eras get shorter.

    This is a LEDGER-SHAPE reconstruction, deliberately simpler than
    scripts/cohort_eval.py's pre-registered one (no size filter, no hedge-leg
    or book exclusion). It answers "how much is refused", not "what is the
    cohort" - never quote it as a cohort count.
    """
    out: dict = {"available": False, "current_era": current_era}
    if not fills_path.exists():
        out["reason"] = f"{fills_path.name} absent"
        return out
    legs: dict[str, list[dict]] = defaultdict(list)
    by_era: Counter = Counter()
    n_legs = 0
    try:
        with fills_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                n_legs += 1
                by_era[(row.get("exec_era") or "").strip()] += 1
                pid = (row.get("position_id") or "").strip()
                if pid:
                    legs[pid].append(row)
    except OSError as exc:                                  # noqa: BLE001
        out["reason"] = f"{type(exc).__name__}: {exc}"
        return out

    closed = pure = straddling = previous = unstamped = 0
    for rows in legs.values():
        sides = {(r.get("side") or "").strip().lower() for r in rows}
        if len(sides) < 2:               # one-sided: never closed
            continue
        closed += 1
        eras = {(r.get("exec_era") or "").strip() for r in rows}
        if eras == {current_era}:
            pure += 1
        elif current_era in eras:
            straddling += 1              # touched this era, not purely
        elif eras == {""}:
            # PREDATES STAMPING ENTIRELY. These were never excluded BY a mint
            # and must not be charged to one. Folding them into the "refused"
            # bucket is the exact denominator error a 2026-09-16 verification
            # pass refuted when it produced a "92.4% of trips outside the
            # gate" figure - the correct denominator for the cost of a mint is
            # STAMPED trips, not lifetime trips.
            unstamped += 1
        else:
            previous += 1
    stamped = pure + straddling + previous
    out.update({
        "available": True,
        "legs": n_legs,
        "legs_by_era": dict(by_era),
        "closed_trips_lifetime": closed,
        "closed_trips_stamped": stamped,
        "predate_stamping": unstamped,
        "counted_by_the_gate": pure,
        "censored_in_flight": straddling,
        "belong_to_a_previous_era": previous,
        # BOTH denominators, named. The lifetime share is the one a reader
        # reaches for and it is the misleading one.
        "share_of_stamped_counted_pct": (round(100.0 * pure / stamped, 1)
                                         if stamped else None),
        "share_of_stamped_refused_pct": (
            round(100.0 * (previous + straddling) / stamped, 1)
            if stamped else None),
        "denominator_note": ("the cost of a MINT is measured against STAMPED "
                             "trips; trips predating stamping were never "
                             "excluded by any mint"),
        "shape_note": ("looser than scripts/cohort_eval.py's pre-registered "
                       "reconstruction - no size filter, no hedge-leg or "
                       "book exclusion. Answers 'how much is refused', never "
                       "'what is the cohort'."),
        "nothing_deleted": ("every leg stays in fills.csv; the era gate is a "
                            "READER-SIDE view filter"),
    })
    return out


# ----------------------------------------------------------------- plane 3
def label_geometry(history_path: Path) -> dict:
    """Rows KEPT whose cost-floor barrier width the bot no longer uses.

    NOT a discard - a CONTAMINATION, and the opposite failure. label_era
    encodes the HORIZON only (ml/history.py's triple_barrier_era returns a
    name built from max_bars and reads nothing else), so a fee re-book moves
    the barrier floor WITHOUT changing the era name and the corpus pools
    several geometries under one label.

    The floor is recovered from the DAILY MINIMUM pt_frac: barrier_geometry
    takes max(sigma-derived, cost floor), so on any day carrying a low-sigma
    asset the minimum IS the floor. Rows above it are sigma-bound and today's
    config reproduces them unchanged - those are NOT stale, and counting them
    as stale overstates the contamination.
    """
    out: dict = {"available": False}
    if not history_path.exists():
        out["reason"] = f"{history_path.name} absent"
        return out
    by_day: dict[str, list[float]] = defaultdict(list)
    stamped_rows: list[tuple[float, float]] = []      # (ts, pt_frac)
    era_seen = None
    n_rows = 0
    try:
        # csv module, never a plain comma split: measured 2026-09-16, 4,932
        # rows carry embedded commas inside quoted fields and a naive split
        # silently reads the wrong column (19,414 -> 14,543).
        with history_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                era = (row.get("label_era") or "").strip()
                if not era.startswith("triple_barrier_h"):
                    continue
                if era_seen is None:
                    era_seen = era
                if era != era_seen:
                    continue
                try:
                    pt = float(row.get("pt_frac") or 0.0)
                    ts = float(row.get("ts") or 0.0)
                except ValueError:
                    continue
                if pt <= 0.0 or not (1.5e9 < ts < 4e9):
                    continue
                n_rows += 1
                stamped_rows.append((ts, pt))
                day = dt.datetime.fromtimestamp(
                    ts, dt.timezone.utc).strftime("%Y-%m-%d")
                by_day[day].append(pt)
    except OSError as exc:                                  # noqa: BLE001
        out["reason"] = f"{type(exc).__name__}: {exc}"
        return out
    if not by_day:
        out["reason"] = "no usable pt_frac rows in the current label era"
        return out

    floors = {d: min(v) for d, v in by_day.items()}
    current = floors[max(floors)]
    regimes = sorted({round(100.0 * f, 2) for f in floors.values()})

    # PARTITION BY DATE, NOT BY VALUE - and this is the whole design of this
    # plane. barrier_geometry floors sigma at pt_cost_mult*cost/pt_mult, so
    # pt_frac's floor is exactly pt_cost_mult*cost/100. Measured 2026-09-16:
    # ZERO rows sit at that value. The minimum is 0.0180030 against a floor of
    # 0.0180000, and 1,433 rows crowd a band 1e-4 wide just above it - because
    # 5 m crypto sigma sits right AT cost/2, exactly as CLAUDE.md says ("that
    # floor binds at any 5 m sigma below cost/2, the normal case").
    #
    # So FLOOR-BOUND vs SIGMA-BOUND is NOT separable from pt_frac alone: the
    # answer is entirely a choice of tolerance, and two defensible tolerances
    # gave 34.8% and 82.9% on the same rows. This function refuses to pick
    # one. What IS exact is WHEN a row was written, because the cost changed
    # at known instants - so the partition below needs no tolerance and is
    # checkable: the two sides must not overlap in their minimum pt_frac.
    onset = None
    for ts, pt in sorted(stamped_rows):
        if pt < current * 1.05:
            onset = ts
            break
    before = sum(1 for ts, _ in stamped_rows if onset and ts < onset)
    after = n_rows - before
    min_before = min((p for t, p in stamped_rows if onset and t < onset),
                     default=None)
    min_after = min((p for t, p in stamped_rows if onset and t >= onset),
                    default=None)
    out.update({
        "available": True,
        "label_era": era_seen,
        "rows": n_rows,
        "distinct_daily_floors": len(regimes),
        "floor_widths_pct": regimes,
        "current_floor_pct": round(100.0 * current, 3),
        "current_regime_onset": (
            dt.datetime.fromtimestamp(onset, dt.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ") if onset else UNKNOWN),
        "rows_under_a_retired_cost": before,
        "rows_under_the_current_cost": after,
        "share_under_a_retired_cost_pct": (round(100.0 * before / n_rows, 1)
                                           if n_rows else None),
        "separation_check": {
            "min_pt_before": min_before,
            "min_pt_after": min_after,
            "disjoint": (min_before is not None and min_after is not None
                         and min_before > min_after),
        },
        "note": ("these rows are KEPT, not discarded - the model trains on "
                 "several cost regimes under ONE era name, because label_era "
                 "encodes the HORIZON only"),
        "not_established": ("what SHARE of the retired-cost rows is actually "
                            "contaminated. A row whose sigma dominated the "
                            "floor carries the same width today, so the "
                            "contaminated subset is somewhere in [0, the "
                            "share above] and pt_frac alone cannot pin it"),
    })
    return out


# ----------------------------------------------------------------- plane 4
def process_memory(status: dict | None) -> dict:
    """In-memory learning windows that die at every relaunch.

    Only the watch lane's pending pool is instrumented (2026-09-15). The
    others are NAMED here from a code audit rather than measured, and are
    tagged as such: naming an unmeasured store is honest, printing a number
    for it would not be.

    Persisting any of the six would CHANGE DECISIONS (a restored CVaR history
    sizes differently), so that work is COHORT-RESETTING under the era-12
    moratorium, not SAFE. The watch lane was SAFE only because it places no
    orders.
    """
    watch = (status or {}).get("watch_lane") or {}
    return {
        "instrumented": {
            "watch lane pending pool": {
                "pending": watch.get("pending", UNKNOWN),
                "restored_on_boot": watch.get("restored_on_boot", UNKNOWN),
                "stale_dropped": watch.get("stale_dropped", UNKNOWN),
                "persistence_live": "pending" in watch,
            }
        },
        "named_but_not_measured": [
            "risk/conviction.py admit/deny window (no persistence in the file)",
            "per-symbol CVaR return deques",
            "informed-flow EMAs behind the if_1..if_5 gates",
            "liquidity-regime depth/imbalance history",
            "ML shadow records (the only path that can un-kill a champion)",
            "feature drift buffer",
        ],
        "caveat": ("[I] - the six were read against the persistence list, not "
                   "each independently confirmed. Persisting them is "
                   "COHORT-RESETTING, not SAFE."),
    }


def collect(history_path: str | None = None) -> dict:
    outputs = Path(os.environ.get("LB_OUTPUTS") or (ROOT / "outputs"))
    status_p = outputs / "status.json"
    fills_p = outputs / "fills.csv"
    hist_p = Path(history_path) if history_path else (outputs / "signal_history.csv")
    status = _load_json(status_p)
    era = UNKNOWN
    era_note = "core.fill_ledger.EXEC_ERA"
    try:
        from core.fill_ledger import EXEC_ERA
        era = str(EXEC_ERA)
    except Exception as exc:                                # noqa: BLE001
        # NOT a bare pass. This ledger's own rule is that a degraded plane
        # says WHY - an UNKNOWN era silently swallowing an ImportError would
        # make plane 2 report every trip as "a previous era" with no hint
        # that the era stamp was never read at all.
        era_note = f"unreadable: {type(exc).__name__}: {exc}"
    return {
        "exec_era_source": era_note,
        "read_at": _now(),
        "stamps": {
            "status.json": _stamp(status_p),
            "fills.csv": _stamp(fills_p),
            "signal_history.csv": _stamp(hist_p),
        },
        "exec_era": era,
        "training_corpus": training_corpus(status),
        "trade_cohort": trade_cohort(fills_p, era),
        "label_geometry": label_geometry(hist_p),
        "process_memory": process_memory(status),
    }


def render(d: dict) -> str:
    lines: list[str] = []
    add = lines.append
    add("=" * 74)
    add("DISCARD LEDGER - everything this system is currently throwing away")
    add("=" * 74)
    add(f"read at {d['read_at']}   exec_era {d['exec_era']}"
        + ("" if d.get("exec_era_source", "").startswith("core.")
           else f"   [ERA {d.get('exec_era_source')}]"))
    for name, stamp in d["stamps"].items():
        add(f"  {name:22} mtime {stamp}")
    add("")

    t = d["training_corpus"]
    add("[1] TRAINING CORPUS - rows the model never sees   (LOAD-TIME VIEW)")
    if not t.get("available"):
        add(f"    UNAVAILABLE: {t.get('reason')}")
    else:
        for name, count in t["discards"].items():
            add(f"    {name:24} {count:>8,}")
        add(f"    {'-' * 24} {'-' * 8}")
        pct = 100.0 * t["discard_total"] / max(t["admissible"], 1)
        add(f"    {'DISCARDED':24} {t['discard_total']:>8,}"
            f"   of {t['admissible']:,} admissible ({pct:.1f}%)")
        add(f"    {'surviving to the fit':24} {t['rows_surviving']:>8,}")
        add(f"    {'LIVE labels surviving':24} {t['live_labels_surviving']:>8,}"
            "   <- ground truth is the scarce row")
        add(f"    mean uniqueness {t['mean_uniqueness']} -> n_eff "
            f"{t['n_eff_per_asset']}   route: {t['n_eff_route']}")
        add(f"    Kish ESS from the training weights: {t['ess_kish']}")
        add(f"    era filter armed={t['era_filter_armed']} "
            f"active={t['era_filter_active']}")
        add(f"    NOTHING DELETED: {t['nothing_deleted']}")
        add(f"    reverse with: {t['reversible_with']}")
    add("")

    c = d["trade_cohort"]
    add("[2] TRADE COHORT - closed trips the era gate refuses  (VIEW FILTER)")
    if not c.get("available"):
        add(f"    UNAVAILABLE: {c.get('reason')}")
    else:
        add(f"    {'closed trips, lifetime':32} {c['closed_trips_lifetime']:>6,}")
        add(f"    {'  of which predate stamping':32} "
            f"{c['predate_stamping']:>6,}   <- NOT charged to any mint")
        add(f"    {'STAMPED trips (the denominator)':32} "
            f"{c['closed_trips_stamped']:>6,}")
        add(f"    {'  counted by the gate':32} {c['counted_by_the_gate']:>6,}"
            f"   ({c['share_of_stamped_counted_pct']}% of stamped)")
        add(f"    {'  refused: a previous era':32} "
            f"{c['belong_to_a_previous_era']:>6,}")
        add(f"    {'  refused: CENSORED IN FLIGHT':32} "
            f"{c['censored_in_flight']:>6,}   <- counted by NO era at all")
        add(f"    REFUSED, of stamped: {c['share_of_stamped_refused_pct']}%")
        add(f"    DENOMINATOR: {c['denominator_note']}")
        add(f"    SHAPE: {c['shape_note']}")
        add(f"    NOTHING DELETED: {c['nothing_deleted']}")
    add("")

    g = d["label_geometry"]
    add("[3] LABEL GEOMETRY - rows KEPT whose barriers the bot retired")
    if not g.get("available"):
        add(f"    UNAVAILABLE: {g.get('reason')}")
    else:
        add(f"    label_era {g['label_era']}   rows {g['rows']:,}")
        add(f"    distinct daily cost floors: {g['distinct_daily_floors']}"
            f"   PT widths seen (%): {g['floor_widths_pct']}")
        add(f"    current cost floor {g['current_floor_pct']}%  "
            f"onset {g['current_regime_onset']}")
        add(f"    rows under a RETIRED cost: "
            f"{g['rows_under_a_retired_cost']:,}"
            f"   ({g['share_under_a_retired_cost_pct']}%)")
        add(f"    rows under the CURRENT cost: "
            f"{g['rows_under_the_current_cost']:,}")
        sc = g["separation_check"]
        add(f"    separation check: min pt before {sc['min_pt_before']} vs "
            f"after {sc['min_pt_after']}  disjoint={sc['disjoint']}")
        add(f"    {g['note']}")
        add(f"    NOT ESTABLISHED: {g['not_established']}")
    add("")

    m = d["process_memory"]
    add("[4] PROCESS MEMORY - learning windows that die at a relaunch")
    for name, v in m["instrumented"].items():
        state = ("persisted" if v.get("persistence_live")
                 else "NOT persisted here (or the fix is not running yet)")
        add(f"    {name:32} {state}")
        add(f"      pending={v['pending']} restored_on_boot="
            f"{v['restored_on_boot']} stale_dropped={v['stale_dropped']}")
    add("    named by code audit, NOT measured here:")
    for s in m["named_but_not_measured"]:
        add(f"      - {s}")
    add(f"    {m['caveat']}")
    add("")
    add("READ NOTHING HERE AS A DEFECT. Several of these discards are correct")
    add("behaviour. What was missing was the SUM, in one place, with stamps.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Report every mechanism currently discarding evidence.")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--history", default=None, help="override corpus path")
    args = ap.parse_args()
    data = collect(args.history)
    print(json.dumps(data, indent=2, default=str) if args.json
          else render(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
