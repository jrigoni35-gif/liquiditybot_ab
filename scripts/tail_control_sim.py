"""scripts/tail_control_sim.py — SAFE counterfactual: does capping the
left-tail losers flip the era-4 verdict cohort net-POSITIVE at real fees?

REPORT-ONLY / PRE-REGISTERED COUNTERFACTUAL. Reads outputs/fills.csv, writes
nothing, touches no config/decision/order path, mints no execution era. Same
class as HEDGE-SIM: it re-prices ALREADY-REALIZED trips under a hypothetical
exit policy and asks a decision question the live book cannot answer without
running the change.

THE QUESTION (registered before the readout). The bot loses net not because
it is edge-less but to FAT-TAIL LOSERS: at real Kraken Tier-3 fees the MEDIAN
realized trip clears the rake and the MEAN is dragged negative by a left tail
(docs/quant/2026-08-29_fee_anatomy.md, ..._game_theory_adverse_selection.md).
So: if a stop-cap had truncated every loser at -X%, does equal-weighted mean
net/trip cross zero at the real 60 bps round-trip, and is the improvement
distinguishable at EFFECTIVE-n?

WINDOW (pre-registered, do not widen). The era-4 verdict cohort exactly as
scripts/cohort_eval.era4_trips defines it — entry-opened closed round trips,
close-ts >= max(B4_TS, CAPITAL_EPOCH_TS) = 1786403127.0. This tool DELEGATES
selection, gross%, and trip spans to era4_trips (it does NOT re-implement the
reconstruction) and cross-checks its own USD reconstruction against that
gross% per trip (fatal assert on any divergence).

FEE BRACKETS (round-trip, flat — the operator's Kraken screenshot, 2026-08-29
Tier 3: maker 22 / taker 38 bps).
  * 60 bps  PRIMARY  — maker entry + taker exit (the realistic mix). The
                       registered verdict is read at THIS bracket only.
  * 76 bps  all-taker (both legs lift) — pessimistic bracket.
  * 44 bps  both-maker (both legs rest) — optimistic bracket.
Each is applied as a FLAT round-trip cost (`net% = gross% - RT/100`), matching
"price everything at 60 bps". Entry/exit sizes match within 2% (era4_trips'
tolerance), so a flat RT and a per-leg re-price agree to ~2%.

THE POLICY. STOP-CAP at cap C in {0.5, 1.0, 1.5, 2.0}%: every trip whose
re-priced net is worse than -C is truncated to -C (`max(net, -C)`). NULL = the
realized outcomes re-priced at the bracket with no cap.

TWO HAZARDS this tool CANNOT see, both of which push the true prize DOWN — a
green here is a CEILING, not a live prize:
  (1) FILL-AT-CAP. Truncating a -3% loser to -C assumes the stop filled at
      exactly -C. Real stops slip; a market that gapped past -C fills worse.
      Reported WITH all caps applied AND WITHOUT the deepest runners
      (null net < -2C — the "gap-through" proxy; fills carry no intra-trip
      path, so this is a coarse flag, not a measurement).
  (2) WINNER TRUNCATION — the dominant blind spot. A tight stop also fires on
      the ADVERSE EXCURSION of trips that went on to WIN: a +8% trip that
      dipped to -0.8% intraday becomes a -C loss under a -0.5% stop. This tool
      keeps every final winner at full value because fills record only the
      close, not the path. The realistic prize therefore requires the
      candle-store re-sim; on fills alone the stop-cap prize is an upper bound.
      This is exactly why the TIME-EXIT rungs below are SCREENING-ONLY.

TIME-EXIT (6/12/24h) is SCREENING-ONLY: it counts how many trips a shorter
hold would have touched; net is DEFERRED to the candle re-sim (a time exit
re-prices the close at a DIFFERENT price, unknowable from the realized close).

    .venv/Scripts/python.exe scripts/tail_control_sim.py [--json]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Delegate the pre-registered selection, spans, and gross% to the authority.
from scripts.cohort_eval import (  # noqa: E402
    B4_TS,
    CAPITAL_EPOCH_TS,
    _OPEN_PURPOSES,
    cohort_effective_n,
    era4_trips,
)

ROOT = Path(__file__).resolve().parents[1]

# Round-trip fee brackets in bps (flat). PRIMARY is the registered verdict
# bracket. Kraken Tier-3 (operator screenshot 2026-08-29): maker 22 / taker 38.
BRACKETS = {60: "primary (maker in + taker out)",
            76: "all-taker (pessimistic)",
            44: "both-maker (optimistic)"}
PRIMARY_BPS = 60

STOP_CAPS_PCT = (0.5, 1.0, 1.5, 2.0)
TIME_EXITS_H = (6, 12, 24)

# "gap-through" proxy: a capped trip whose null net ran past 2x the cap depth,
# where assuming a clean fill AT the cap is most optimistic. Fills carry no
# intra-trip path — this is a coarse disclosure flag, not a measurement.
GAP_THROUGH_MULT = 2.0

_GROSS_TOL = 1e-6  # cross-check of USD reconstruction vs era4_trips gross%


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def _sd(xs, m=None):
    """Population sd (÷n), matching cohort_eval's variance convention."""
    n = len(xs)
    if n == 0:
        return 0.0
    mu = _mean(xs) if m is None else m
    return math.sqrt(sum((v - mu) ** 2 for v in xs) / n)


def stop_cap(net_pct: float, cap_pct: float) -> float:
    """Truncate a loser to the cap. Pure; the one line the prize rests on."""
    return max(net_pct, -cap_pct)


def is_gap_through(null_net_pct: float, cap_pct: float) -> bool:
    """True for a capped loser whose realized net ran past GAP_THROUGH_MULT×cap
    — the trips where fill-at-cap is most optimistic."""
    return null_net_pct < -(GAP_THROUGH_MULT * cap_pct)


def _f(row, key):
    try:
        return float(row[key])
    except (TypeError, ValueError, KeyError):
        return None


def _financials(fills_path: str, want_pids: set) -> dict:
    """{pid: (cash_usd, notional_usd)} for the wanted pids, using the IDENTICAL
    per-fill arithmetic era4_trips/build_trips use (val=sz*px; cash += ±val;
    notional += val on opening legs). Not a new trip reconstruction — a USD
    accumulator whose gross% is asserted equal to era4_trips' downstream."""
    try:
        rows = list(csv.DictReader(open(fills_path, newline="",
                                        encoding="utf-8")))
    except OSError:
        return {}
    by_pid = collections.defaultdict(list)
    for r in rows:
        pid = r.get("position_id")
        if pid in want_pids:
            by_pid[pid].append(r)
    out = {}
    for pid, legs in by_pid.items():
        cash = notional = 0.0
        for r in legs:
            sz, px = _f(r, "fill_size"), _f(r, "fill_price")
            if sz is None or px is None or sz <= 0 or px <= 0:
                continue
            val = sz * px
            cash += val if r.get("side") == "sell" else -val
            if r.get("purpose") in _OPEN_PURPOSES:
                notional += val
        out[pid] = (cash, notional)
    return out


def load_cohort(fills_path: str) -> list:
    """The pre-registered era-4 cohort with per-trip USD attached.

    Selection, gross%, and spans come from cohort_eval.era4_trips (the
    authority). USD is reconstructed here and CROSS-CHECKED: each trip's
    100*cash/notional must equal era4_trips' gross% within _GROSS_TOL, or the
    accumulator has diverged and we refuse to report."""
    trips = era4_trips(fills_path)
    fin = _financials(fills_path, {t.get("pid") for t in trips})
    out = []
    for t in trips:
        pid = t.get("pid")
        cash, notional = fin.get(pid, (None, None))
        if not notional or notional <= 0:
            raise AssertionError(f"USD reconstruction missing for pid={pid!r}")
        gross_chk = 100.0 * cash / notional
        if abs(gross_chk - t["gross_pct"]) > _GROSS_TOL:
            raise AssertionError(
                f"gross% divergence pid={pid!r}: usd-route {gross_chk} vs "
                f"era4_trips {t['gross_pct']}")
        out.append({"pid": pid, "gross_pct": t["gross_pct"],
                    "t_open": t.get("t_open"), "t_close": t.get("t"),
                    "cash_usd": cash, "notional_usd": notional})
    return out


def reprice_null(trip: dict, rt_bps: float) -> tuple:
    """(net_pct, net_usd) of a realized trip re-priced at a flat RT bracket."""
    net_pct = trip["gross_pct"] - rt_bps / 100.0
    net_usd = trip["cash_usd"] - trip["notional_usd"] * rt_bps / 1e4
    return net_pct, net_usd


def policy_metrics(trips: list, rt_bps: float, cap_pct: float,
                   neff: float, se_infl: float) -> dict:
    """All metrics for one (bracket, stop-cap) cell.

    Effective-n deflation: SE_eff(x) = sd(x)/sqrt(n) * se_infl = sd(x)/sqrt(neff)
    (concurrent trips share a market path — cohort_eval.cohort_effective_n).
    The improvement test is PAIRED (delta_i = capped_i - null_i on the same
    trip), so SE_eff is taken on the delta series."""
    n = len(trips)
    nulls = [reprice_null(t, rt_bps)[0] for t in trips]
    null_usd = [reprice_null(t, rt_bps)[1] for t in trips]

    def _cell(capped_pct, tag):
        # net USD under the policy: cap the % then convert on the trip notional
        capped_usd = [capped_pct[i] / 100.0 * trips[i]["notional_usd"]
                      if capped_pct[i] != nulls[i] else null_usd[i]
                      for i in range(n)]
        delta = [capped_pct[i] - nulls[i] for i in range(n)]
        dmean = _mean(delta)
        se_delta = _sd(delta) / math.sqrt(neff) if neff > 0 else float("inf")
        mean_pct = _mean(capped_pct)
        return {
            "tag": tag,
            "mean_net_pct": mean_pct,
            "median_net_pct": _median(capped_pct),
            "net_positive_frac": sum(1 for v in capped_pct if v > 0) / n,
            "total_net_usd": sum(capped_usd),
            "n_capped": sum(1 for i in range(n) if capped_pct[i] != nulls[i]),
            "improvement_vs_null_pct": dmean,
            "se_eff_delta_pct": se_delta,
            "distinguishable": dmean > 2 * se_delta,
            "mean_net_positive": mean_pct > 0,
        }

    # WITH: apply the cap to every loser (fill-at-cap assumed everywhere).
    with_pct = [stop_cap(v, cap_pct) for v in nulls]
    # WITHOUT: deny the cap benefit to gap-through runners (leave them realized)
    wo_pct = [nulls[i] if is_gap_through(nulls[i], cap_pct)
              else stop_cap(nulls[i], cap_pct) for i in range(n)]
    gap_n = sum(1 for v in nulls if is_gap_through(v, cap_pct))

    return {"cap_pct": cap_pct, "gap_through_n": gap_n,
            "with_capfill": _cell(with_pct, "with_capfill"),
            "without_gapthrough": _cell(wo_pct, "without_gapthrough")}


def screen_time_exit(trips: list, hours: float) -> dict:
    """SCREENING-ONLY: count trips a shorter hold would have touched. Net is
    DEFERRED — a time exit re-prices the close at a price fills cannot supply."""
    spans = [(t["t_close"] - t["t_open"]) / 3600.0 for t in trips
             if t.get("t_open") is not None and t.get("t_close") is not None]
    n = len(spans)
    touched = sum(1 for d in spans if d > hours)
    return {"hours": hours, "n": n, "touched": touched,
            "touched_frac": touched / n if n else 0.0,
            "net_metrics": "DEFERRED_TO_CANDLE_RESIM"}


def compute(fills_path: str) -> dict:
    trips = load_cohort(fills_path)
    n = len(trips)
    en = cohort_effective_n(
        [{"t_open": t["t_open"], "t": t["t_close"]} for t in trips])
    neff = en.get("effective_n", float("nan"))
    se_infl = en.get("se_inflation", float("nan"))

    brackets = {}
    for rt in sorted(BRACKETS, reverse=True):
        nulls = [reprice_null(t, rt)[0] for t in trips]
        null_usd = [reprice_null(t, rt)[1] for t in trips]
        brackets[str(rt)] = {
            "label": BRACKETS[rt],
            "null": {"mean_net_pct": _mean(nulls),
                     "median_net_pct": _median(nulls),
                     "net_positive_frac": sum(1 for v in nulls if v > 0) / n,
                     "total_net_usd": sum(null_usd)},
            "policies": {f"cap_{c}": policy_metrics(trips, rt, c, neff, se_infl)
                         for c in STOP_CAPS_PCT},
        }

    # ---- registered verdict, read at the PRIMARY bracket only ----
    prim = brackets[str(PRIMARY_BPS)]["policies"]
    any_pos = any(p["with_capfill"]["mean_net_positive"] for p in prim.values())
    any_dist = any(p["with_capfill"]["mean_net_positive"]
                   and p["with_capfill"]["distinguishable"]
                   for p in prim.values())
    if any_dist:
        verdict = "TAIL-CONTROL-PAYS"
    elif any_pos:
        verdict = "UNDECIDABLE-AT-N"
    else:
        verdict = "DOESNT-PAY"

    # best policy at primary = highest mean net (WITH cap-fill)
    best_key = max(prim, key=lambda k: prim[k]["with_capfill"]["mean_net_pct"])
    best = prim[best_key]["with_capfill"]

    # ---- DOUBLE-DERIVE the best policy's primary mean: pct route vs USD route
    cap = prim[best_key]["cap_pct"]
    nulls = [reprice_null(t, PRIMARY_BPS)[0] for t in trips]
    capped_pct = [stop_cap(v, cap) for v in nulls]
    route1_mean = _mean(capped_pct)  # mean of per-trip pct
    # USD route: per-trip pct rebuilt from net_usd / notional, then meaned
    route2_terms = []
    for i, t in enumerate(trips):
        if capped_pct[i] != nulls[i]:
            usd = -cap / 100.0 * t["notional_usd"]
        else:
            usd = reprice_null(t, PRIMARY_BPS)[1]
        route2_terms.append(100.0 * usd / t["notional_usd"])
    route2_mean = _mean(route2_terms)

    return {
        "fills": fills_path,
        "cut_ts": max(B4_TS, CAPITAL_EPOCH_TS),
        "n": n,
        "effective_n": neff,
        "mean_uniqueness": en.get("mean_uniqueness"),
        "se_inflation": se_infl,
        "primary_bps": PRIMARY_BPS,
        "brackets": brackets,
        "time_exit_screen": {str(h): screen_time_exit(trips, h)
                             for h in TIME_EXITS_H},
        "verdict": verdict,
        "best_policy": {"bracket_bps": PRIMARY_BPS, "cap_pct": cap,
                        "mean_net_pct": best["mean_net_pct"],
                        "distinguishable": best["distinguishable"]},
        "double_derive_best_mean": {
            "route_pct": route1_mean, "route_usd": route2_mean,
            "agree": abs(route1_mean - route2_mean) < 1e-9},
    }


def _fmt(r: dict) -> str:
    L = []
    L.append("=== TAIL-CONTROL SIM — era-4 verdict cohort (SAFE, "
             "report-only) ===")
    L.append(f"fills={r['fills']}  cut_ts={r['cut_ts']:.1f}  n={r['n']}  "
             f"eff_n={r['effective_n']:.2f}  se_infl=x{r['se_inflation']:.2f}")
    L.append("stop-cap prize is a CEILING: fills cannot see fill-at-cap "
             "slippage OR winner-truncation (a tight stop also fires on the")
    L.append("adverse excursion of trips that went on to win). Realistic "
             "prize needs the candle re-sim; on fills it is an upper bound.")
    for rt in sorted(BRACKETS, reverse=True):
        b = r["brackets"][str(rt)]
        star = "  <== PRIMARY VERDICT" if rt == PRIMARY_BPS else ""
        L.append("")
        L.append(f"[{rt} bps] {b['label']}{star}")
        nz = b["null"]
        L.append(f"    NULL (no cap): mean {nz['mean_net_pct']:+.4f}%  "
                 f"median {nz['median_net_pct']:+.4f}%  "
                 f"pos {nz['net_positive_frac']:.3f}  "
                 f"total ${nz['total_net_usd']:+.2f}")
        for c in STOP_CAPS_PCT:
            p = b["policies"][f"cap_{c}"]
            w = p["with_capfill"]
            wo = p["without_gapthrough"]
            flag = "DISTINGUISHABLE" if w["distinguishable"] else "within-noise"
            L.append(
                f"    cap -{c:.1f}%: mean {w['mean_net_pct']:+.4f}%  "
                f"pos {w['net_positive_frac']:.3f}  "
                f"total ${w['total_net_usd']:+.2f}  "
                f"dMean {w['improvement_vs_null_pct']:+.4f} "
                f"(2*SEeff {2*w['se_eff_delta_pct']:.4f}) {flag}  "
                f"[capped {w['n_capped']}, gap-thru {p['gap_through_n']}; "
                f"WITHOUT-gap mean {wo['mean_net_pct']:+.4f}% "
                f"{'DIST' if wo['distinguishable'] else 'noise'}]")
    L.append("")
    L.append("TIME-EXIT screen (SCREENING-ONLY — net DEFERRED to candle "
             "re-sim):")
    for h in TIME_EXITS_H:
        s = r["time_exit_screen"][str(h)]
        L.append(f"    <{h}h hold: {s['touched']}/{s['n']} trips touched "
                 f"({100*s['touched_frac']:.1f}%)  net={s['net_metrics']}")
    L.append("")
    dd = r["double_derive_best_mean"]
    L.append(f"VERDICT (primary {r['primary_bps']} bps): {r['verdict']}")
    bp = r["best_policy"]
    L.append(f"  best policy: stop-cap -{bp['cap_pct']:.1f}% -> mean "
             f"{bp['mean_net_pct']:+.4f}%/trip  "
             f"({'distinguishable at eff-n' if bp['distinguishable'] else 'within eff-n noise'})")
    L.append(f"  double-derive best mean: pct-route {dd['route_pct']:+.6f}%  "
             f"usd-route {dd['route_usd']:+.6f}%  "
             f"agree={dd['agree']}")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fills", default=str(ROOT / "outputs" / "fills.csv"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not Path(args.fills).exists():
        print(f"no fills at {args.fills}")
        return 1
    res = compute(args.fills)
    print(json.dumps(res, indent=1, default=str) if args.json else _fmt(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
