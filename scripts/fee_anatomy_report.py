"""scripts/fee_anatomy_report.py — fee anatomy of REALIZED round-trips.

REPORT-ONLY. Reads outputs/fills.csv (the per-fill execution ledger,
core/fill_ledger.py) and answers, from ACTUAL fills, the question the flat
replay-cost assumption cannot:

  1. maker/taker MIX per leg (entry / exit / hedge), read off the persisted
     post_only flag — the flag order_manager books maker_fee_bps vs
     taker_fee_bps against (execution/order_manager.py:527-528).
  2. BOOKED round-trip cost (the rate in force when each fill was written)
     vs VENUE-TRUE round-trip cost (the SAME fills re-priced at the given
     maker/taker schedule, default Kraken Tier-1 40/80). Distribution +
     histogram.
  3. the maker-vs-taker DOLLAR split of the fee bill.
  4. the counterfactual PRIZE of forcing every taker EXIT to maker, split
     into a STRUCTURAL floor (stops / hedge-unwinds — a stop MUST be allowed
     to exit, a hedge unwind is never gated) and a DEFERRABLE remainder.

WHY RE-PRICING IS HONEST AND POOLING GROSS IS NOT. The fee re-price at
40/80 is era-INVARIANT: it applies one schedule to each fill's own
post_only flag, so it is a valid "what would this mix cost at venue truth"
regardless of which config booked the row. GROSS P&L is NOT era-invariant
(different cost manifolds, different tapes) — this tool pools it only to
size the bleed, prints its clustered SE, and refuses to treat the pooled
mean as an edge. Trips overlap: the trip COUNT is nominal, not effective-n.

Nothing here mutates state or reads config.json's history. A fee-constant
or label-cost change is an operator decision (spec D4); this only measures.

    .venv/Scripts/python.exe scripts/fee_anatomy_report.py [--json]
    .venv/Scripts/python.exe scripts/fee_anatomy_report.py \
        --fills outputs/fills.csv --maker-bps 40 --taker-bps 80
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A hedge OPENS exposure like an entry; kept distinct from "entry" so the
# per-leg mix can report the three purposes separately (a hedge leg is
# structurally taker and must not be pooled into the entry-maker rate).
_OPEN_PURPOSES = ("entry", "hedge")

# THE "VENUE-TRUE" DEFAULT WAS NEITHER VENUE-TRUE NOR CURRENT.
# 40/80 is not a row Kraken publishes at ANY volume (the live schedule read
# from api.kraken.com/0/public/AssetPairs runs 25/40, 20/35, 14/24, 12/22 …
# 0/5 — see core/venue_fees.py), and it is ~2x the schedule this bot has
# actually booked since cut #9 (22/38). Every figure this tool called
# "VENUE-TRUE" was inflated accordingly: median 120.85 -> 60.41 bps, aggregate
# $775.84 -> $371.38, maker prize $202.71 -> $76.02.
#
# Read the BOOKED schedule instead of a module literal, so the report cannot
# drift from the book again. --maker-bps/--taker-bps still override, and the
# fallback is the venue's WORST published row (25/40) rather than a number
# that appears nowhere in the schedule: if config is unreadable, over-stating
# cost with a REAL row is the conservative failure.
def _booked_fees() -> tuple:
    try:
        _pt = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                         .read_text(encoding="utf-8")).get("pretrade", {})
        return (float(_pt["maker_fee_bps"]), float(_pt["taker_fee_bps"]))
    except (OSError, ValueError, KeyError, TypeError):
        return (25.0, 40.0)          # venue's worst PUBLISHED row


KRAKEN_T1_MAKER_BPS, KRAKEN_T1_TAKER_BPS = _booked_fees()

# Exit-reason prefixes whose taker fill is STRUCTURAL: the position must be
# allowed out and cannot honestly rest as a passive maker.
#   tb_sl / stop        - stop-loss (CLAUDE.md: exits are ALWAYS allowed)
#   hard cap            - hard risk-cap breach
#   stale loser         - forced time+regime close
#   time-stop / tb_time - time-barrier / time-stop expiry (forced at instant)
#   operator flatten    - operator kill
#   hedge unwind        - hedge unwinds are NEVER gated (CLAUDE.md)
_STRUCTURAL_EXIT_PREFIXES = (
    "tb_sl", "stop ", "hard cap", "stale loser", "time-stop",
    "tb_time", "operator flatten", "hedge unwind",
)


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def med(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def is_structural_exit(reason: str) -> bool:
    """True when a taker exit fill could NOT honestly have been a maker."""
    r = (reason or "").lower().lstrip()
    return any(r.startswith(p) for p in _STRUCTURAL_EXIT_PREFIXES)


def _leg_mix(rows: list) -> dict:
    """maker/taker fill counts per purpose. post_only=='1' -> maker."""
    mix = {p: {"maker": 0, "taker": 0} for p in ("entry", "exit", "hedge")}
    for r in rows:
        pur = r.get("purpose")
        if pur not in mix:
            continue
        key = "maker" if str(r.get("post_only")) == "1" else "taker"
        mix[pur][key] += 1
    return mix


def _fee_dollars_by_flag(rows: list, maker_bps: float, taker_bps: float) -> dict:
    """Venue-true fee dollars split maker vs taker, over every fill (each
    re-priced at its own post_only flag)."""
    out = {"maker": 0.0, "taker": 0.0}
    n = {"maker": 0, "taker": 0}
    for r in rows:
        sz, px = _f(r.get("fill_size")), _f(r.get("fill_price"))
        if not sz or not px or sz <= 0 or px <= 0:
            continue
        maker = str(r.get("post_only")) == "1"
        rate = maker_bps if maker else taker_bps
        key = "maker" if maker else "taker"
        out[key] += sz * px * rate / 1e4
        n[key] += 1
    return {"maker_usd": out["maker"], "taker_usd": out["taker"],
            "maker_n": n["maker"], "taker_n": n["taker"]}


def _exit_counterfactual(rows: list, maker_bps: float, taker_bps: float) -> dict:
    """Prize of moving each TAKER exit to maker (rate drop taker->maker),
    split structural vs deferrable. Reported at the given (venue-true)
    schedule, since it bounds the go-forward prize."""
    drop = (taker_bps - maker_bps) / 1e4
    agg = {"structural": {"n": 0, "notional": 0.0},
           "deferrable": {"n": 0, "notional": 0.0}}
    defer_reasons: Counter = Counter()
    for r in rows:
        if r.get("purpose") != "exit" or str(r.get("post_only")) == "1":
            continue
        sz, px = _f(r.get("fill_size")), _f(r.get("fill_price"))
        if not sz or not px or sz <= 0 or px <= 0:
            continue
        notl = sz * px
        bucket = "structural" if is_structural_exit(r.get("reason", "")) \
            else "deferrable"
        agg[bucket]["n"] += 1
        agg[bucket]["notional"] += notl
        if bucket == "deferrable":
            defer_reasons[(r.get("reason") or "")[:24]] += 1
    return {
        "rate_drop_bps": taker_bps - maker_bps,
        "structural_n": agg["structural"]["n"],
        "structural_notional": agg["structural"]["notional"],
        "structural_floor_usd": agg["structural"]["notional"] * drop,
        "deferrable_n": agg["deferrable"]["n"],
        "deferrable_notional": agg["deferrable"]["notional"],
        "deferrable_prize_usd": agg["deferrable"]["notional"] * drop,
        "max_prize_usd": (agg["structural"]["notional"]
                          + agg["deferrable"]["notional"]) * drop,
        "deferrable_reasons": dict(defer_reasons.most_common()),
    }


def build_trips(rows: list, maker_bps: float, taker_bps: float) -> tuple:
    """Fully-closed round-trips, deduplicated by FILL PATTERN (same identity
    rule as cost_attribution.load — position_id carries the restart-replay
    duplication). Each trip carries booked fees (as written) AND venue-true
    fees (re-priced at maker_bps/taker_bps per fill's post_only)."""
    by_pid = defaultdict(list)
    for r in rows:
        if r.get("position_id"):
            by_pid[r["position_id"]].append(r)
    trips = []
    seen = set()
    skipped: Counter = Counter()
    for fills in by_pid.values():
        cash = booked = vtrue = notional = ez = xz = 0.0
        ok = True
        sig = []
        for r in fills:
            sz, px = _f(r.get("fill_size")), _f(r.get("fill_price"))
            fee = _f(r.get("fees_delta_usd"))
            if not sz or not px or fee is None or sz <= 0 or px <= 0:
                ok = False
                break
            val = sz * px
            cash += val if r.get("side") == "sell" else -val
            booked += fee
            rate = maker_bps if str(r.get("post_only")) == "1" else taker_bps
            vtrue += val * rate / 1e4
            if r.get("purpose") in _OPEN_PURPOSES:
                ez += sz
                notional += val
            elif r.get("purpose") == "exit":
                xz += sz
            sig.append((r.get("purpose"), r.get("side"),
                        round(sz, 6), round(px, 4)))
        if not ok:
            skipped["malformed_row"] += 1
            continue
        if ez <= 0 or notional <= 0:
            skipped["no_opening_leg"] += 1
            continue
        if xz <= 0:
            skipped["still_open"] += 1
            continue
        if abs(xz - ez) / ez > 0.02:
            skipped["size_mismatch"] += 1
            continue
        key = tuple(sig)
        if key in seen:
            skipped["duplicate_fill_pattern"] += 1
            continue
        seen.add(key)
        trips.append({
            "notional": notional, "gross": cash,
            "booked": booked, "vtrue": vtrue,
            "gross_pct": 100.0 * cash / notional,
            "booked_bps": 1e4 * booked / notional,
            "vtrue_bps": 1e4 * vtrue / notional,
        })
    return trips, skipped


def compute(fills_path: str, maker_bps: float = KRAKEN_T1_MAKER_BPS,
            taker_bps: float = KRAKEN_T1_TAKER_BPS) -> dict:
    p = Path(fills_path)
    rows = list(csv.DictReader(open(p, newline="", encoding="utf-8")))
    ts = [_f(r.get("ts")) for r in rows]
    ts = [t for t in ts if t is not None]
    mix = _leg_mix(rows)
    fee_split = _fee_dollars_by_flag(rows, maker_bps, taker_bps)
    cf = _exit_counterfactual(rows, maker_bps, taker_bps)
    trips, skipped = build_trips(rows, maker_bps, taker_bps)
    n = len(trips)

    def leg_frac(pur):
        m, t = mix[pur]["maker"], mix[pur]["taker"]
        tot = m + t
        return {"maker": m, "taker": t, "total": tot,
                "maker_frac": (m / tot) if tot else None}

    res = {
        "n_fill_rows": len(rows),
        "ts_min": min(ts) if ts else None,
        "ts_max": max(ts) if ts else None,
        "maker_bps": maker_bps, "taker_bps": taker_bps,
        "mix": {pur: leg_frac(pur) for pur in ("entry", "exit", "hedge")},
        "fee_dollars": fee_split,
        "exit_counterfactual": cf,
        "n_trips": n,
        "skipped": dict(skipped),
    }
    if n:
        g = [t["gross_pct"] for t in trips]
        bk = [t["booked_bps"] for t in trips]
        vt = [t["vtrue_bps"] for t in trips]
        hist = Counter(int(x // 20) * 20 for x in vt)
        res["trips"] = {
            "mean_gross_pct": sum(g) / n, "median_gross_pct": med(g),
            "booked_rt_bps": {"min": min(bk), "median": med(bk),
                              "mean": sum(bk) / n, "max": max(bk)},
            "vtrue_rt_bps": {"min": min(vt), "median": med(vt),
                             "mean": sum(vt) / n, "max": max(vt)},
            "vtrue_hist_20bps": {str(k): hist[k] for k in sorted(hist)},
            "mean_booked_pct": sum(t["booked_bps"] for t in trips) / n / 100.0,
            "mean_vtrue_pct": sum(t["vtrue_bps"] for t in trips) / n / 100.0,
            "net_at_booked_pct": (sum(g) / n)
            - sum(t["booked_bps"] for t in trips) / n / 100.0,
            "net_at_vtrue_pct": (sum(g) / n)
            - sum(t["vtrue_bps"] for t in trips) / n / 100.0,
            "agg_gross_usd": sum(t["gross"] for t in trips),
            "agg_booked_usd": sum(t["booked"] for t in trips),
            "agg_vtrue_usd": sum(t["vtrue"] for t in trips),
            "agg_notional_usd": sum(t["notional"] for t in trips),
        }
    return res


def _fmt(res: dict) -> str:
    L = []
    L.append("=== FEE ANATOMY of realized round-trips (report-only) ===")
    L.append(f"fills: n_fill_rows={res['n_fill_rows']}  "
             f"ts=[{res['ts_min']}, {res['ts_max']}]")
    L.append(f"schedule re-priced at maker={res['maker_bps']:.0f} / "
             f"taker={res['taker_bps']:.0f} bps (Kraken T1; NOT OM-080 "
             "venue-reconciled)")
    L.append("")
    L.append("[1] MAKER/TAKER MIX per leg (post_only flag on actual fills)")
    for pur in ("entry", "exit", "hedge"):
        m = res["mix"][pur]
        frac = "n/a" if m["maker_frac"] is None else f"{100*m['maker_frac']:.1f}%"
        L.append(f"    {pur:6s} n={m['total']:4d}  maker={m['maker']:4d} "
                 f"({frac})  taker={m['taker']:4d}")
    L.append("")
    fd = res["fee_dollars"]
    tot = fd["maker_usd"] + fd["taker_usd"]
    L.append("[2] FEE DOLLARS (venue-true, split by leg type)")
    if tot > 0:
        L.append(f"    maker=${fd['maker_usd']:.2f} "
                 f"({100*fd['maker_usd']/tot:.1f}%, n={fd['maker_n']})  "
                 f"taker=${fd['taker_usd']:.2f} "
                 f"({100*fd['taker_usd']/tot:.1f}%, n={fd['taker_n']})")
    L.append("")
    if "trips" in res:
        t = res["trips"]
        L.append(f"[3] ROUND-TRIP cost distribution (n_trips={res['n_trips']}, "
                 "dedup by fill-pattern)")
        b, v = t["booked_rt_bps"], t["vtrue_rt_bps"]
        L.append(f"    BOOKED    bps: min={b['min']:.1f} median={b['median']:.1f} "
                 f"mean={b['mean']:.1f} max={b['max']:.1f}")
        L.append(f"    VENUE-TRUE bps: min={v['min']:.1f} median={v['median']:.1f} "
                 f"mean={v['mean']:.1f} max={v['max']:.1f}")
        L.append("    venue-true histogram (20bps bins): "
                 + " ".join(f"[{k})={c}" for k, c in t["vtrue_hist_20bps"].items()))
        L.append(f"    mean gross={t['mean_gross_pct']:+.4f}%  "
                 f"median gross={t['median_gross_pct']:+.4f}%")
        L.append(f"    net @ booked={t['net_at_booked_pct']:+.4f}%   "
                 f"net @ venue-true={t['net_at_vtrue_pct']:+.4f}%")
        L.append(f"    agg: gross=${t['agg_gross_usd']:+.2f} "
                 f"booked=${t['agg_booked_usd']:.2f} "
                 f"venue-true=${t['agg_vtrue_usd']:.2f} "
                 f"notional=${t['agg_notional_usd']:.0f}")
    L.append("")
    cf = res["exit_counterfactual"]
    L.append(f"[4] MAKER-EXIT COUNTERFACTUAL (taker->maker, "
             f"{cf['rate_drop_bps']:.0f}bps drop per exit leg)")
    L.append(f"    STRUCTURAL floor (unavoidable): n={cf['structural_n']} "
             f"notional=${cf['structural_notional']:.0f} "
             f"-> ${cf['structural_floor_usd']:.2f} NOT capturable")
    L.append(f"    DEFERRABLE prize: n={cf['deferrable_n']} "
             f"notional=${cf['deferrable_notional']:.0f} "
             f"-> ${cf['deferrable_prize_usd']:.2f} capturable ceiling")
    L.append(f"    MAX (all taker exits): ${cf['max_prize_usd']:.2f}")
    L.append(f"    deferrable reasons: {cf['deferrable_reasons']}")
    if res["skipped"]:
        L.append("")
        L.append(f"skipped trips: {res['skipped']}")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fills", default=str(ROOT / "outputs" / "fills.csv"))
    ap.add_argument("--maker-bps", type=float, default=KRAKEN_T1_MAKER_BPS)
    ap.add_argument("--taker-bps", type=float, default=KRAKEN_T1_TAKER_BPS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    p = Path(args.fills)
    if not p.exists():
        print(f"no fills at {p}")
        return 1
    res = compute(args.fills, args.maker_bps, args.taker_bps)
    if args.json:
        print(json.dumps(res, indent=1))
    else:
        print(_fmt(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
