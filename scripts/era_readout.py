"""scripts/era_readout.py - the era readout AS REGISTERED, and nothing else.

WHY THIS EXISTS. The era-9 decision is pre-registered (cut-#11 adjudication,
docs/quant/2026-09-07_cut11_commit_adjudication.md section 3, adopted for
era-9 by CLAUDE.md "Era-9 accrual begins..."):

    Population   entry-opened closed round trips with EVERY leg stamped with
                 the era (stamp-purity); hedge legs excluded; straddling
                 trips excluded.
    Primary      net $/trip at booked fees (sum sell - sum buy - sum fees),
                 95% day-block bootstrap CI: blocks = UTC day of the CLOSING
                 fill, 4,000 reps, seed 7.
    Co-primary   gross %/trip, same CI.
    n = 50 LEAN  report sign + CI; act only if the CI excludes zero.
    n = 100      CONTINUE iff net mean > 0 with the CI excluding -fee.
    VERDICT      STOP iff gross mean <= 0 and median <= 0 (no edge), or
                 gross > 0 and net <= 0 (cost-bound). Else UNDETERMINED,
                 which the registration routes to "extend to 200".

Measured 2026-09-15: NO script in the repo computed that statistic.
scripts/cohort_eval.py - "untouched" by law, and therefore untouched here -
has one threshold, no n=100 tier, an iid SE on nominal n, %/trip not $/trip,
and decides on point-estimate signs over a population pooled across six
eras. This file is the SIBLING the law's wording allows: report-only, reads
outputs/fills.csv, writes nothing under outputs/, touches no decision path.

WHAT IT PRINTS BEYOND THE REGISTERED NUMBERS - all labelled, none in the rule:
  * a cluster-robust t interval (df = days-1, CR1) as a CALIBRATION line
    beside the registered percentile interval. The registered interval is
    what the rule reads; swapping families after seeing data is the move a
    pre-registration exists to prevent. See DISCLOSURES below.
  * effective n after overlap deflation (cohort_eval.cohort_effective_n,
    imported, not copied) AND the bootstrap-implied SE inflation - two
    different answers to "how much does this cohort know".
  * leave-one-day-out sensitivity of the interval.
  * BOTH membership rules side by side, neither labelled "REGISTERED": the
    registration names no book, so an operator SELECTS a row before the read
    point instead of inheriting one.
  * the three candidate fee nulls, with the one in force marked.
  * every trip NOT in a population row, with its reason - exclusions AND the
    open/partial trips that are not yet trips at all.

DISCLOSURES the page prints because they belong to the REGISTRATION, not to
this code (a flaw in the registered method is disclosed, never silently
repaired):
  * the 95% percentile day-block bootstrap UNDER-COVERS at few blocks
    (simulated ~0.85 at 6 blocks, ~0.92 at ~12, ~0.94 at ~24 [I, assumed
    error model]); the n=50 "act if the CI excludes zero" clause therefore
    fires under H0 at ~8-9%, not 5%.
  * close-day blocks capture within-closing-day dependence only; trips that
    cross UTC midnight share a market path across two blocks.
  * "seed 7" pins nothing without the generator: numpy PCG64 +
    integers(0,d,size=d) per rep + linear percentile. A different scheme
    moves the bound at the 2nd decimal when blocks are few.
  * H0's -fee is under-determined: cut-#11 says -0.33, CLAUDE.md says -0.27,
    the era measures its own. The band between them can flip the verdict.
  * the n=100 rule has a hole (gross mean <= 0, gross median > 0, net <= 0).
  * "$60 tickets" and "majors only" are HYPOTHESIS wording, not filters.

Usage:
    python scripts/era_readout.py
    python scripts/era_readout.py --era 12-10d4d0c2 --fee-null -0.33
    python scripts/era_readout.py --json > readout.json

Every number is as-of the fills.csv read time printed at the top. Re-derive,
never quote.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Registered constants. Changing any of these is changing the registration.
REPS = 4000
SEED = 7
CI_LO, CI_HI = 2.5, 97.5
N_LEAN = 50
N_VERDICT = 100
SIZE_TOL = 0.02          # cohort_eval's fully-closed tolerance, kept identical
FEE_NULL_CUT11 = -0.33   # cut-#11 registration: 55 bps x $60
FEE_NULL_CUT12 = -0.27   # CLAUDE.md era-9 block: 45 bps x $60
# OPERATOR ADJUDICATION 2026-09-15, recorded before the n=50 read point:
#   * H0's -fee is the era's OWN MEASURED mean booked fee per trip, not a
#     literal. It is never hardcoded here - it is recomputed from the
#     population at read time, because the tier rolls and the exit/entry
#     maker-taker mix moves. Today it is -0.2960 (49.3 bps of the $60.03
#     median ticket, because every exit pays taker).
#     NOTE, for the record: -0.296 is a LOWER bar for CONTINUE than the
#     -0.27 it replaces (CI lo > -0.296 is easier than CI lo > -0.27). It is
#     chosen because it is what the account actually paid, not because it is
#     conservative - and that direction is disclosed rather than buried.
#   * The selected population is the 5m book only (registration HYPOTHESIS,
#     "$60 tickets"), not the pooled row. See SELECTED_POP.
DEFAULT_FEE_NULL = "measured"
SELECTED_POP = "stamp-pure, 5m book only (registration HYPOTHESIS)"
FEW_BLOCKS = 5           # below this, print the read-the-sign-not-the-edges warning

# Student-t 0.975 quantiles. scipy is NOT in the repo venv (same reason and
# same shape as scripts/beta_alpha_decomposition.py's table). Used ONLY for
# the calibration interval, never for the registered one.
_T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
         8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160,
         14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
         20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
         26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042, 40: 2.021,
         60: 2.000, 120: 1.980}


def _t975(df: int) -> float:
    if df <= 0:
        return float("nan")
    if df in _T975:
        return _T975[df]
    if df > 120:
        return 1.960
    keys = sorted(_T975)
    lo = max(k for k in keys if k <= df)
    hi = min(k for k in keys if k >= df)
    if lo == hi:
        return _T975[lo]
    w = (df - lo) / (hi - lo)
    return _T975[lo] * (1 - w) + _T975[hi] * w


def _f(row: dict, key: str):
    v = row.get(key)
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _utc_day(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def reconstruct(rows: list[dict], era: str) -> dict:
    """Group fill legs into trips and classify each against the registration.

    Returns members / anyleg_extra / excluded / open_or_partial. NOTHING that
    touches the era is dropped without appearing in one of the four - the
    docstring above promises that, so the code must earn it (three silent
    `continue`s were found by injection 2026-09-15 and are now counted).

    Reconstruction: signed cash flow (sell +, buy -) is gross; fees are
    subtracted separately; a trip is closed when its last leg is an exit with
    nothing remaining and exit size matches entry size within SIZE_TOL.
    """
    by_pid: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        if r.get("position_id"):
            by_pid[r["position_id"]].append(r)
    members: list[dict] = []
    anyleg_extra: list[dict] = []
    excluded: list[dict] = []
    open_or_partial: list[dict] = []
    for pid, legs in by_pid.items():
        legs.sort(key=lambda r: _f(r, "ts") or 0.0)
        # Scope: only trips that touch THIS era are classified. Other eras'
        # trips are not this era's business - listing a 2026-07 hedge as
        # "excluded from era-9" would bury the one exclusion that matters.
        if not any((r.get("exec_era") or "").strip() == era for r in legs):
            continue
        sym = legs[0].get("symbol")
        exits = [r for r in legs if r.get("purpose") == "exit"]
        if not exits:
            open_or_partial.append({"pid": pid, "symbol": sym,
                                    "reason": "no exit leg (still open)"})
            continue
        last = legs[-1]
        rem = _f(last, "remaining")
        if last.get("purpose") != "exit":
            open_or_partial.append({"pid": pid, "symbol": sym,
                                    "reason": f"last leg is {last.get('purpose')!r}, not exit"})
            continue
        if rem is not None and rem > 1e-9:
            open_or_partial.append({"pid": pid, "symbol": sym,
                                    "reason": f"last exit leaves remaining {rem:.10g}"})
            continue
        # Registration: "hedge legs excluded". The OPENING leg is not the only
        # place a hedge leg can appear (injection, 2026-09-15): a hedge leg
        # inside an entry-opened trip used to be folded into cash and fees and
        # the trip stayed in the population.
        n_hedge = sum(1 for r in legs if r.get("purpose") == "hedge")
        opened_by = legs[0].get("purpose")
        if opened_by != "entry":
            excluded.append({"pid": pid, "symbol": sym,
                             "reason": f"opened by {opened_by!r}, not entry"})
            continue
        if n_hedge:
            excluded.append({"pid": pid, "symbol": sym,
                             "reason": f"hedge leg inside an entry-opened trip (x{n_hedge})"})
            continue
        cash = fees = esz = xsz = enot = 0.0
        bad = False
        eras = []
        for r in legs:
            sz, px, fee = _f(r, "fill_size"), _f(r, "fill_price"), _f(r, "fees_delta_usd")
            if sz is None or px is None or fee is None or sz <= 0 or px <= 0:
                bad = True
                break
            cash += sz * px if r.get("side") == "sell" else -(sz * px)
            fees += fee
            if r.get("purpose") == "exit":
                xsz += sz
            else:
                esz += sz
                enot += sz * px
            e = r.get("exec_era")
            eras.append("" if e is None else str(e).strip())
        if bad or esz <= 0 or enot <= 0:
            excluded.append({"pid": pid, "symbol": sym, "reason": "unparseable leg"})
            continue
        if abs(xsz - esz) / esz > SIZE_TOL:
            excluded.append({"pid": pid, "symbol": sym,
                             "reason": f"exit/entry size {xsz / esz:.2f}x "
                                       "(doubled exit or partial)"})
            continue
        t_open = _f(legs[0], "ts") or 0.0
        t_close = max(_f(r, "ts") or 0.0 for r in exits)   # LAST exit, per the registration
        trip = {
            "pid": pid, "symbol": sym,
            # book: ANY leg, because only entry/add legs carry 'long' in this
            # ledger - exits carry '' (ledger fact, verified 2026-09-15)
            "book": "long" if any((r.get("book") or "").strip() == "long" for r in legs) else "5m",
            "net_usd": cash - fees, "gross_usd": cash, "fees_usd": fees,
            "gross_pct": 100.0 * cash / enot, "ticket_usd": enot,
            "t_open": t_open, "t": t_close, "close_day": _utc_day(t_close),
            "legs": len(legs),
        }
        pure = all(e == era for e in eras)
        closes_in_era = eras[-1] == era
        if pure:
            trip["membership"] = "pure"
            members.append(trip)
        elif closes_in_era:
            trip["membership"] = ("straddler" if any(e and e != era for e in eras)
                                  else "unstamped-legs")
            anyleg_extra.append(trip)
        else:
            excluded.append({"pid": pid, "symbol": sym,
                             "reason": f"opened in era, closes outside it "
                                       f"(last leg stamp {eras[-1]!r})"})
    return {"members": members, "anyleg_extra": anyleg_extra,
            "excluded": excluded, "open_or_partial": open_or_partial}


def day_block_bootstrap(trips: list[dict], key: str, reps: int = REPS,
                        seed: int = SEED) -> dict:
    """95% CI of the mean of `key` by resampling UTC closing-days with
    replacement (cluster bootstrap on the day of the closing fill).

    THE REGISTERED INTERVAL. numpy is required: the pure-python fallback that
    used to live here produced a DIFFERENT interval for the same "seed 7"
    ([-0.9245, -0.1798] vs [-0.9247, -0.1644] on the 2026-09-15 ledger),
    which means the registration would have named two answers. One protocol:
    numpy PCG64, rng.integers(0, d, size=d) per rep, linear percentile.
    """
    try:
        import numpy as np
    except ImportError as exc:                          # pragma: no cover
        raise RuntimeError(
            "numpy is required for the registered CI: 'seed 7' pins a result "
            "only together with the generator (numpy PCG64) and the "
            "percentile method (linear). Install numpy or do not quote a CI."
        ) from exc
    days: dict[str, list[float]] = collections.defaultdict(list)
    for t in trips:
        days[t["close_day"]].append(float(t[key]))
    keys = sorted(days)
    d = len(keys)
    vals = [float(t[key]) for t in trips]
    proto = (f"numpy {np.__version__} PCG64 default_rng({seed}); "
             f"integers(0,d,size=d) per rep; percentile linear")
    if d == 0:
        return {"mean": float("nan"), "lo": float("nan"), "hi": float("nan"),
                "days": 0, "reps": 0, "protocol": proto, "boot_sd": float("nan"),
                "degenerate": True}
    mean = sum(vals) / len(vals)
    if d == 1:
        return {"mean": mean, "lo": mean, "hi": mean, "days": 1, "reps": 0,
                "protocol": proto + " [DEGENERATE: one block]",
                "boot_sd": 0.0, "degenerate": True}
    rng = np.random.default_rng(seed)
    blocks = [np.asarray(days[k], dtype=float) for k in keys]
    means = np.empty(reps)
    for i in range(reps):
        idx = rng.integers(0, d, size=d)       # resample DAYS with replacement
        samp = np.concatenate([blocks[j] for j in idx])
        means[i] = float(samp.mean())
    lo, hi = (float(x) for x in np.percentile(means, [CI_LO, CI_HI]))
    return {"mean": mean, "lo": lo, "hi": hi, "days": d, "reps": reps,
            "protocol": proto, "boot_sd": float(means.std(ddof=1)),
            "degenerate": False}


def cluster_t(trips: list[dict], key: str) -> dict:
    """CALIBRATION ONLY - NOT the registered interval, never read by a rule.

    Cluster-robust (CR1) t interval, clusters = closing day, df = G-1. Printed
    beside the registered percentile interval because the percentile bootstrap
    under-covers at few clusters; when the two disagree about excluding zero,
    the operator should know that before the read point, not after.
    """
    by_day: dict[str, list[float]] = collections.defaultdict(list)
    for t in trips:
        by_day[t["close_day"]].append(float(t[key]))
    g = len(by_day)
    n = sum(len(v) for v in by_day.values())
    if g < 2 or n < 2:
        return {"available": False, "g": g}
    xbar = sum(x for v in by_day.values() for x in v) / n
    meat = sum((sum(x - xbar for x in v)) ** 2 for v in by_day.values())
    se = math.sqrt(g / (g - 1) * meat) / n
    tq = _t975(g - 1)
    return {"available": True, "g": g, "df": g - 1, "se": se, "t": tq,
            "lo": xbar - tq * se, "hi": xbar + tq * se}


def resolve_fee_null(spec, measured: float) -> tuple[float, str]:
    """H0's -fee, from a named source or a literal.

    'measured' is the operator's 2026-09-15 adjudication and is recomputed at
    every read - never frozen into a constant, because the venue tier rolls
    and the maker/taker mix moves with the exit ladder.
    """
    if spec is None:
        spec = DEFAULT_FEE_NULL
    if isinstance(spec, str):
        key = spec.strip().lower()
        # A literal arrives as a STRING from argparse (--fee-null -0.41), so
        # numbers are resolved before names or the documented literal form
        # raises. Found by its own pin, 2026-09-15.
        try:
            return float(key), "operator --fee-null <literal>"
        except ValueError:
            pass
        if key == "measured":
            if measured != measured:                     # NaN: no trips yet
                return FEE_NULL_CUT12, ("era measured UNAVAILABLE (no trips) - "
                                        "fell back to CLAUDE.md cut-#12")
            return measured, ("era MEASURED mean booked fee/trip "
                              "(operator adjudication 2026-09-15)")
        if key == "cut11":
            return FEE_NULL_CUT11, "cut-#11 registration (55 bps x $60)"
        if key == "cut12":
            return FEE_NULL_CUT12, "CLAUDE.md era-9 block (cut-#12 45 bps x $60)"
        raise ValueError(f"--fee-null: expected a number or one of "
                         f"measured/cut11/cut12, got {spec!r}")
    return float(spec), "operator --fee-null <literal>"


def leave_one_day_out(trips: list[dict], key: str, reps: int, seed: int) -> dict:
    """Informational: how much does the interval depend on any single day?"""
    days = sorted({t["close_day"] for t in trips})
    if len(days) < 3:
        return {"available": False, "days": len(days)}
    los, his = [], []
    for dday in days:
        sub = [t for t in trips if t["close_day"] != dday]
        if len(sub) < 2:
            continue
        b = day_block_bootstrap(sub, key, reps, seed)
        los.append(b["lo"])
        his.append(b["hi"])
    if not los:
        return {"available": False, "days": len(days)}
    return {"available": True, "lo_min": min(los), "lo_max": max(los),
            "hi_min": min(his), "hi_max": max(his),
            "sign_stable": max(his) < 0 or min(los) > 0}


def rules(trips: list[dict], fee_null: float, reps: int, seed: int) -> dict:
    """Apply the registered read points to one membership population."""
    n = len(trips)
    out: dict = {"n": n}
    if n == 0:
        out["lean"] = out["verdict"] = "no trips"
        return out
    net = day_block_bootstrap(trips, "net_usd", reps, seed)
    gross = day_block_bootstrap(trips, "gross_pct", reps, seed)
    nets = [t["net_usd"] for t in trips]
    grosses = [t["gross_pct"] for t in trips]
    out["net"] = net
    out["gross_pct"] = gross
    out["net_median"] = statistics.median(nets)
    out["gross_median"] = statistics.median(grosses)
    out["fees_mean"] = sum(t["fees_usd"] for t in trips) / n
    out["ticket_median"] = statistics.median(t["ticket_usd"] for t in trips)
    out["ticket_min"] = min(t["ticket_usd"] for t in trips)
    out["ticket_max"] = max(t["ticket_usd"] for t in trips)
    out["wins"] = sum(1 for x in nets if x > 0)
    out["cluster_t_net"] = cluster_t(trips, "net_usd")
    out["loo_net"] = leave_one_day_out(trips, "net_usd", reps, seed)
    # ddof=1: the sample SD. pstdev understated the iid SE by sqrt(n/(n-1)) in
    # the operator-flattering direction (found 2026-09-15).
    sd = statistics.stdev(nets) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    try:
        from scripts.cohort_eval import cohort_effective_n
        eff = cohort_effective_n(trips)
    except Exception as exc:                            # pragma: no cover
        eff = {"available": False, "error": repr(exc)}
    out["effective"] = eff
    n_eff = eff.get("effective_n") if eff.get("available") else None
    se_eff = sd / math.sqrt(n_eff) if n_eff and n_eff > 0 else float("nan")
    out["sd"] = sd
    out["se_iid"] = se
    out["se_eff"] = se_eff
    out["se_inflation_boot"] = (net["boot_sd"] / se) if se and net.get("boot_sd") == net.get("boot_sd") else float("nan")
    # Informational only - no rule reads a z. Four of these invited picking.
    out["z_informational"] = net["mean"] / se if se else float("nan")
    out["z_all"] = {
        "vs_zero_iid": net["mean"] / se if se else float("nan"),
        "vs_fee_iid": (net["mean"] - fee_null) / se if se else float("nan"),
        "vs_zero_eff": net["mean"] / se_eff if se_eff == se_eff and se_eff else float("nan"),
        "vs_fee_eff": (net["mean"] - fee_null) / se_eff if se_eff == se_eff and se_eff else float("nan"),
    }
    # n = 50 LEAN
    excludes_zero = net["lo"] > 0 or net["hi"] < 0
    if n < N_LEAN:
        out["lean"] = f"NOT REACHED ({n}/{N_LEAN}); CI shown for calibration only"
    elif excludes_zero:
        out["lean"] = ("LEAN: ACT - CI excludes zero, sign "
                       + ("POSITIVE" if net["lo"] > 0 else "NEGATIVE"))
    else:
        out["lean"] = "LEAN: NO ACTION - CI includes zero"
    # n = 100 VERDICT (registered branches, verbatim order)
    if n < N_VERDICT:
        out["verdict"] = f"NOT REACHED ({n}/{N_VERDICT})"
    elif net["mean"] > 0 and net["lo"] > fee_null:
        out["verdict"] = "CONTINUE - net > 0 and CI excludes -fee"
    elif gross["mean"] <= 0 and out["gross_median"] <= 0:
        out["verdict"] = "STOP - no gross edge (mean <= 0 and median <= 0)"
    elif gross["mean"] > 0 and net["mean"] <= 0:
        out["verdict"] = "STOP - cost-bound (gross > 0, net <= 0)"
    else:
        out["verdict"] = ("UNDETERMINED - registered letter routes to extend-to-200 "
                          "(cut-#11 section 3, Power paragraph)")
        if net["hi"] < 0:
            out["verdict"] += ("  ** net CI excludes zero FROM BELOW; the registered "
                               "letter still routes here - the n=50 LEAN clause is the "
                               "one that applies **")
    return out


def render(res: dict) -> str:
    L: list[str] = []
    a = L.append
    m = res["meta"]
    c = m["fee_null_candidates"]
    a("era readout - AS REGISTERED (cut-#11 section 3, adopted for era-9)")
    a("=" * 78)
    a(f"fills: {m['fills']}")
    a(f"read {m['read_utc']}   mtime {m['mtime_utc']}   legs {m['legs']}")
    a(f"era {m['era']} ({m['era_source']})   reps {m['reps']}   seed {m['seed']}")
    a(f"protocol: {m['protocol']}")
    a(f"fee null IN FORCE {m['fee_null']:+.3f} $/trip ({m['fee_null_source']})")
    a(f"  candidates: cut-#11 registered {c['cut11_registered']:+.2f} | "
      f"CLAUDE.md cut-#12 {c['cut12_adopted']:+.2f} | "
      f"era measured {c['era_measured_mean']:+.4f}"
      + (f" ({c['era_measured_bps']:.1f} bps of the median ticket)"
         if c.get("era_measured_bps") == c.get("era_measured_bps") else ""))
    a("")
    a("MEMBERSHIP")
    a("  The registration names NO BOOK. The operator SELECTED the 5m-book row on")
    a("  2026-09-15, before the n=50 read point: the registered HYPOTHESIS names")
    a("  '$60 tickets', and the long book is a different strategy (12% thesis stops,")
    a("  $31-47 tickets) that no cut's configuration includes. Disclosed cost of that")
    a("  choice: the 5m row has the FRIENDLIER median, and at today's numbers it moves")
    a("  the population out of a clean STOP and into the n=100 rule's hole (Q9).")
    for name, blk in res["populations"].items():
        mark = "  <- SELECTED (operator, 2026-09-15)" if name == SELECTED_POP else ""
        a(f"  {name:<52} n={blk['n']}{mark}")
    op = res["open_or_partial"]
    a(f"  open / partially closed (not yet trips)       n={len(op)}" + (":" if op else ""))
    for e in op:
        a(f"      {e['pid'][:8]}  {(e.get('symbol') or ''):<9} {e['reason']}")
    ex = res["excluded"]
    a(f"  excluded, WITH reasons                        n={len(ex)}" + (":" if ex else ""))
    for e in ex:
        a(f"      {e['pid'][:8]}  {(e.get('symbol') or ''):<9} {e['reason']}")
    a("")
    for name, blk in res["populations"].items():
        a(f"--- {name}{'  [SELECTED]' if name == SELECTED_POP else ''} ---")
        if blk["n"] == 0:
            a("  (empty)")
            a("")
            continue
        net, g = blk["net"], blk["gross_pct"]
        a(f"  net $/trip   mean {net['mean']:+.4f}   95% CI [{net['lo']:+.4f}, {net['hi']:+.4f}]"
          f"   median {blk['net_median']:+.4f}   wins {blk['wins']}/{blk['n']}")
        a(f"  gross %/trip mean {g['mean']:+.3f}%  95% CI [{g['lo']:+.3f}%, {g['hi']:+.3f}%]"
          f"   median {blk['gross_median']:+.3f}%")
        a(f"  fees/trip mean {blk['fees_mean']:.4f}   ticket median ${blk['ticket_median']:.2f}"
          f" (range ${blk['ticket_min']:.2f}-${blk['ticket_max']:.2f})   day-blocks {net['days']}")
        ct = blk.get("cluster_t_net") or {}
        if ct.get("available"):
            a(f"  [calibration, NOT the rule] cluster-t net CI (CR1, df={ct['df']}): "
              f"[{ct['lo']:+.4f}, {ct['hi']:+.4f}]"
              + ("   <-- DISAGREES with the registered interval about excluding zero"
                 if (ct["lo"] < 0 < ct["hi"]) != (net["lo"] < 0 < net["hi"]) else ""))
        eff = blk["effective"]
        if eff.get("available"):
            a(f"  effective n {eff['effective_n']:.1f} of {blk['n']} (uniqueness "
              f"{eff['mean_uniqueness']:.3f}, SE inflation x{eff['se_inflation']:.2f});"
              f"  bootstrap-implied SE inflation x{blk['se_inflation_boot']:.2f}")
            a("    ^ two different answers to 'how much does this cohort know'; the")
            a("      registered CI uses the weaker (within-closing-day) one.")
        else:
            a(f"  effective n UNAVAILABLE: {eff.get('error', 'unknown')}")
        loo = blk.get("loo_net") or {}
        if loo.get("available"):
            a(f"  leave-one-day-out: lo [{loo['lo_min']:+.4f}, {loo['lo_max']:+.4f}]  "
              f"hi [{loo['hi_min']:+.4f}, {loo['hi_max']:+.4f}]  "
              f"sign {'ROBUST' if loo['sign_stable'] else 'NOT robust'} to dropping any one day")
        a(f"  z (informational, NOT in any rule): {blk['z_informational']:+.2f}")
        if net["days"] < FEW_BLOCKS:
            a(f"  ** only {net['days']} day-block(s): read the SIGN, not the edges **")
        a(f"  n=50  {blk['lean']}")
        a(f"  n=100 {blk['verdict']}")
        a("")
    a("READ THIS WITH THE VERDICT")
    a("  * The registered 95% PERCENTILE day-block bootstrap under-covers when blocks")
    a("    are few: ~0.85 at 6 blocks, ~0.92 at ~12 (about n=50), ~0.94 at ~24 (about")
    a("    n=100) [I, simulated under an assumed error model]. The n=50 clause 'act if")
    a("    the CI excludes zero' therefore fires under H0 nearer 8-9% than 5%. The RULE")
    a("    reads the registered interval; the cluster-t line above is the calibration.")
    a("    Changing interval family after seeing the data is the forbidden move - it")
    a("    would be a registration amendment, minuted by the operator, not a code fix.")
    a("  * Blocks are the UTC day of the CLOSING fill, as registered. Trips that cross")
    a("    midnight share a market path across two blocks; that dependence is not in")
    a("    the interval.")
    a("  * 'seed 7' reproduces only with the protocol line printed above.")
    a("  * Two looks (n=50, n=100) at nominal 95% each, with no alpha spending")
    a("    registered. Family-wise false-action rate under H0 is higher than 5% [I].")
    a("  * '$60 tickets' and 'majors only' are HYPOTHESIS wording, not filters: the")
    a("    ticket range is printed per row, and no symbol filter is applied.")
    a("  * The n=100 rule has a HOLE: gross mean <= 0 with gross median > 0 and net <= 0")
    a("    matches no CONTINUE/STOP clause and routes to UNDETERMINED.")
    a("  * The registration is 'powered to catch losing, not to certify small winning'.")
    a("Report-only. No order path was read or touched.")
    return "\n".join(L)


def run(fills: Path, era: str, fee_null: float | None, reps: int = REPS,
        seed: int = SEED, era_source: str = "operator --era") -> dict:
    read_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mtime = datetime.fromtimestamp(os.path.getmtime(fills), timezone.utc)
    with open(fills, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    rec = reconstruct(rows, era)
    pure = rec["members"]
    anyleg = pure + rec["anyleg_extra"]
    if pure:
        measured_fee = -sum(t["fees_usd"] for t in pure) / len(pure)
        med_ticket = statistics.median(t["ticket_usd"] for t in pure)
        measured_bps = 1e4 * (-measured_fee) / med_ticket if med_ticket else float("nan")
    else:
        measured_fee = measured_bps = float("nan")
    fee_null, src = resolve_fee_null(fee_null, measured_fee)
    pops: dict[str, dict] = {}
    # SELECTED first, by operator adjudication 2026-09-15.
    pops[SELECTED_POP] = rules(
        [t for t in pure if t["book"] != "long"], fee_null, reps, seed)
    pops["stamp-pure, all books (registration LETTER)"] = rules(pure, fee_null, reps, seed)
    pops["any-leg (closes in era, incl. straddlers)"] = rules(anyleg, fee_null, reps, seed)
    pops["stamp-pure, long book only (NOT pooled - its own question)"] = rules(
        [t for t in pure if t["book"] == "long"], fee_null, reps, seed)
    proto = next((p["net"]["protocol"] for p in pops.values() if p.get("net")), "n/a")
    return {
        "meta": {"fills": str(fills), "read_utc": read_utc,
                 "mtime_utc": mtime.strftime("%Y-%m-%dT%H:%M:%SZ"), "legs": len(rows),
                 "era": era, "era_source": era_source, "reps": reps, "seed": seed,
                 "protocol": proto,
                 "fee_null": fee_null, "fee_null_source": src,
                 "fee_null_candidates": {"cut11_registered": FEE_NULL_CUT11,
                                         "cut12_adopted": FEE_NULL_CUT12,
                                         "era_measured_mean": measured_fee,
                                         "era_measured_bps": measured_bps}},
        "populations": pops,
        "excluded": rec["excluded"],
        "open_or_partial": rec["open_or_partial"],
        "trips": {"pure": pure, "anyleg_extra": rec["anyleg_extra"]},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--fills", default=str(ROOT / "outputs" / "fills.csv"))
    ap.add_argument("--era", default=None, help="exec_era stamp; default core.fill_ledger.EXEC_ERA")
    ap.add_argument("--fee-null", default=None,
                    help="H0 net $/trip: a number, or measured (default, operator "
                         "adjudication 2026-09-15) | cut11 (-0.33) | cut12 (-0.27)")
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args(argv)
    era, era_source = ns.era, "operator --era"
    if era is None:
        from core.fill_ledger import EXEC_ERA
        era, era_source = EXEC_ERA, "default core.fill_ledger.EXEC_ERA"
    res = run(Path(ns.fills), era, ns.fee_null, ns.reps, ns.seed, era_source)
    if ns.json:
        res_out = dict(res)
        res_out.pop("trips")
        print(json.dumps(res_out, indent=1, default=str))
    else:
        print(render(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
