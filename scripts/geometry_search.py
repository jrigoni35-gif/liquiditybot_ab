"""scripts/geometry_search.py - can ANY bracket geometry make these entries pay?

THE QUESTION. The payoff decomposition says the sizes are wrong (losers
1.8x winners); the random-entry control says the entries carry no timing
signal; the multi-timeframe funnel doc measured gross alpha ~= 0 at every
horizon from 30m to 8h with P(PT|resolved) pinned to the driftless
gambler's-ruin value. If all three are right, NO exit geometry can turn
these entries net-positive - but that conclusion was assembled from three
separate tools, and "no geometry can work" deserves one direct measurement
before it hardens into policy. This is that measurement: every bracket in a
pre-registered grid, replayed on the real recorded 5-minute OHLC, over the
bot's own actual entries, with the configured fees applied by exit type.

THE GRID IS PRE-REGISTERED, NOT TUNED. Targets and stops bracket the
measured trade statistics (median MFE +0.246%, mean win +0.26%, mean loss
-0.47%) by a factor of ~2 in both directions; horizons are the shadow
ladder's 2h/8h plus the deployed 36h. 48 combinations, and the
significance bar is Bonferroni-corrected for all 48 - a combo must clear
z=3.26, not z=1.96, before it may be called a finding. Anything less is a
grid search dressed as a discovery, the exact "misconception of being
successful" this repo keeps having to un-learn.

MULTI-TIMEFRAME, PER ASSET. The MDPI label-driven-optimization paper's one
transferable claim is that the right horizon differs per asset. Section 2
tests it on our own shadow ladder: per (asset, horizon), resolution rate
and P(PT | resolved) with a Wilson interval against the 42.9% driftless
null. An asset whose interval EXCLUDES the null is a real anomaly worth
attention; matching the null means horizon tuning has nothing to grab.

WHAT THIS TOOL WILL NOT DO. It changes no config (the 432 cohort is in
flight at ~11/50 and a geometry change resets it), injects nothing into
the corpus (signal_history is append-only ground truth; relabeled or
simulated outcomes never enter it), and refuses a verdict that does not
clear the corrected bar. Report-only.

    python scripts/geometry_search.py [--json]
"""
import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from random_entry_control import (  # noqa: E402
    BAR_SEC, harvest_candles, wilson)

# Pre-registered grid (see docstring for the derivation - brackets the
# measured MFE/MAE quartiles, horizons from the shadow ladder + deployed).
TP_PCT = (0.25, 0.5, 1.0, 2.0)
SL_PCT = (0.25, 0.5, 1.0, 2.0)
HORIZON_BARS = (24, 96, 432)
N_TESTS = len(TP_PCT) * len(SL_PCT) * len(HORIZON_BARS)
# two-sided alpha=0.05 Bonferroni-corrected for 48 tests -> per-test z
Z_BONF = 3.26
# The driftless first-passage null is sl/(pt+sl) in BARRIER UNITS - for the
# shadow ladder that is label_sl_vol_mult/(label_pt_vol_mult +
# label_sl_vol_mult) = 6/14 = 0.429 (the funnel doc's 42.9%), read from
# config below rather than assumed. The first version of this section
# compared the LABEL rate against that null and found "anomalies"
# everywhere; the label nets out the cost stack, so it sits ~0.31 against a
# 0.42 touch rate BY CONSTRUCTION. Touch probability is the quantity the
# null speaks about; the gap between touch and label is the cost wedge,
# reported separately because it is a different fact.


def load_entries(fills_path: Path) -> list:
    """One record per position: (asset, t0, entry_px, long). Closure is NOT
    required - a bracket simulation needs only the entry; requiring closure
    would filter the population by the OLD geometry's exit behaviour, which
    is selection bias by the thing under test."""
    by_pid = defaultdict(list)
    with open(fills_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("position_id") and r.get("purpose") == "entry":
                by_pid[r["position_id"]].append(r)
    out = []
    for fills in by_pid.values():
        try:
            sz = sum(float(r["fill_size"]) for r in fills)
            if sz <= 0:
                continue
            px = sum(float(r["fill_size"]) * float(r["fill_price"])
                     for r in fills) / sz
            t0 = min(float(r["ts"]) for r in fills)
        except (KeyError, TypeError, ValueError):
            continue
        out.append({"asset": str(fills[0].get("symbol", "")).split("/")[0],
                    "t0": t0, "px": px,
                    "long": fills[0].get("side") == "buy"})
    return out


def bracket_outcome(keys, book, e, tp, sl, max_bars):
    """First-touch walk. Both barriers inside one bar -> STOP (conservative:
    the intrabar path is unknown and hope is not a tiebreak). Returns
    (net_pct, exit_kind) or None if the window is not densely covered."""
    t0, px, long = e["t0"], e["px"], e["long"]
    i0 = np.searchsorted(keys, t0, side="right") - 1
    if i0 < 0 or t0 - keys[i0] > 2 * BAR_SEC:
        return None
    i1 = np.searchsorted(keys, t0 + max_bars * BAR_SEC, side="right")
    win = keys[i0 + 1:i1]
    if len(win) < 0.8 * max_bars:
        return None
    up, dn = px * (1 + tp / 100.0), px * (1 - sl / 100.0)
    if not long:
        up, dn = px * (1 - tp / 100.0), px * (1 + sl / 100.0)
    for t in win:
        hi, lo, _c = book[t]
        if long:
            hit_tp, hit_sl = hi >= up, lo <= dn
        else:
            hit_tp, hit_sl = lo <= up, hi >= dn
        if hit_sl:                       # includes the both-touched bar
            return (-sl, "sl")
        if hit_tp:
            return (tp, "tp")
    close = book[win[-1]][2]
    raw = (close / px - 1.0) if long else (1.0 - close / px)
    return (100.0 * raw, "time")


def per_asset_ladder(shadow_path: Path, null_p: float) -> dict:
    """Section 2: per (asset, horizon) FIRST-TOUCH probability
    (exit_reason pt vs sl) against the barrier-ratio null, plus the pooled
    cost wedge - the fraction of winning touches whose label still nets 0
    because the touch did not clear the cost stack."""
    rows = defaultdict(lambda: [0, 0, 0])  # (asset,h) -> [n, pt, sl]
    touch_win = label_win = 0
    with open(shadow_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                k = (r["asset"], int(r["horizon_bars"]))
                reason = r.get("exit_reason", "")
                lab = int(r["label"])
            except (KeyError, TypeError, ValueError):
                continue
            rows[k][0] += 1
            if reason == "pt":
                rows[k][1] += 1
                touch_win += 1
                label_win += 1 if lab == 1 else 0
            elif reason == "sl":
                rows[k][2] += 1
    out = []
    for (a, h), (n, pt, sl) in sorted(rows.items()):
        res = pt + sl
        if res < 30:
            continue
        p, lo, hi = wilson(pt, res)
        out.append({"asset": a, "horizon": h, "n": n,
                    "resolution": res / n, "p_touch": p,
                    "ci": [lo, hi],
                    "off_null": lo > null_p or hi < null_p})
    wedge = 1.0 - (label_win / touch_win) if touch_win else 0.0
    return {"cells": out, "cost_wedge": wedge, "touch_wins": touch_win}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recordings", default=str(ROOT / "outputs" /
                                                "recordings"))
    ap.add_argument("--fills", default=str(ROOT / "outputs" / "fills.csv"))
    ap.add_argument("--shadow", default=str(ROOT / "outputs" /
                                            "horizon_shadow.csv"))
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()

    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    fees = cfg.get("execution", {})
    maker = float(fees.get("maker_fee_bps", 25.0)) / 100.0
    taker = float(fees.get("taker_fee_bps", 40.0)) / 100.0
    cost_tp = maker + maker        # limit entry, limit PT exit
    cost_sl = maker + taker        # limit entry, stop/time exits cross

    books = harvest_candles(Path(ns.recordings))
    keys = {a: np.array(sorted(b)) for a, b in books.items()}
    entries = load_entries(Path(ns.fills))

    combos = []
    for h in HORIZON_BARS:
        for tp in TP_PCT:
            for sl in SL_PCT:
                nets = []
                kinds = {"tp": 0, "sl": 0, "time": 0}
                for e in entries:
                    if e["asset"] not in books:
                        continue
                    r = bracket_outcome(keys[e["asset"]], books[e["asset"]],
                                        e, tp, sl, h)
                    if r is None:
                        continue
                    net = r[0] - (cost_tp if r[1] == "tp" else cost_sl)
                    nets.append(net)
                    kinds[r[1]] += 1
                n = len(nets)
                if n < 20:
                    continue
                arr = np.array(nets)
                mean, sd = float(arr.mean()), float(arr.std(ddof=1))
                se = sd / math.sqrt(n)
                combos.append({
                    "horizon_bars": h, "tp_pct": tp, "sl_pct": sl, "n": n,
                    "mean_net_pct": mean, "se": se,
                    "lower_bonf": mean - Z_BONF * se,
                    "p_pt_null": sl / (tp + sl),
                    "p_pt_obs": kinds["tp"] / max(kinds["tp"] + kinds["sl"],
                                                  1),
                    "exits": dict(kinds)})
    winners = [c for c in combos if c["lower_bonf"] > 0]
    ml = cfg.get("ml", {})
    pt_m = float(ml.get("label_pt_vol_mult", 8))
    sl_m = float(ml.get("label_sl_vol_mult", 6))
    null_p = sl_m / (pt_m + sl_m)
    lad = per_asset_ladder(Path(ns.shadow), null_p)
    ladder, anomalies = lad["cells"], [r for r in lad["cells"]
                                       if r["off_null"]]

    res = {"n_entries": len(entries), "n_combos_scored": len(combos),
           "n_tests": N_TESTS, "z_bonferroni": Z_BONF,
           "cost_tp_pct": cost_tp, "cost_sl_pct": cost_sl,
           "winners": winners,
           "best": max(combos, key=lambda c: c["mean_net_pct"])
           if combos else None,
           "touch_null": null_p, "cost_wedge": lad["cost_wedge"],
           "per_asset_ladder": ladder,
           "per_asset_anomalies": anomalies}
    if ns.json:
        print(json.dumps(res, indent=1))
        return 0

    print("GEOMETRY SEARCH - pre-registered bracket grid on real entries")
    print("=" * 70)
    print("%d entries, %d/%d combos scored (min n=20); costs tp %.2f%% / "
          "sl-time %.2f%%" % (len(entries), len(combos), N_TESTS,
                              cost_tp, cost_sl))
    print("\n  top 8 by mean net (Bonferroni lower bound is the verdict "
          "column):")
    print("  h_bars   tp%%    sl%%     n   mean_net    lower(z=%.2f)  "
          "P(PT) obs/null" % Z_BONF)
    for c in sorted(combos, key=lambda c: -c["mean_net_pct"])[:8]:
        print("   %4d   %4.2f  %4.2f  %4d   %+7.3f%%     %+7.3f%%      "
              "%.2f / %.2f"
              % (c["horizon_bars"], c["tp_pct"], c["sl_pct"], c["n"],
                 c["mean_net_pct"], c["lower_bonf"], c["p_pt_obs"],
                 c["p_pt_null"]))

    print("\n2. PER-ASSET MULTI-TIMEFRAME LADDER - first-touch P(PT) vs "
          "the %.1f%% barrier-ratio null" % (100 * res["touch_null"]))
    print("   (only intervals EXCLUDING the null are printed - the rest "
          "match it)")
    if anomalies:
        for r in anomalies:
            print("   %-5s h=%-3d P(touch PT) %.3f [%.3f, %.3f]  "
                  "resolved n=%d"
                  % (r["asset"], r["horizon"], r["p_touch"], r["ci"][0],
                     r["ci"][1], int(r["n"] * r["resolution"])))
        print("   An interval BELOW the null is a real per-asset drift or")
        print("   selection effect at that horizon; per-asset horizon")
        print("   tuning (the MDPI paper's claim) has something to grab")
        print("   ONLY in these cells.")
    else:
        print("   none - every (asset, horizon) cell is consistent with a")
        print("   driftless coin. Per-asset horizon tuning (the MDPI")
        print("   paper's central claim) has nothing to grab here.")
    print("\n   COST WEDGE: %.1f%% of winning PT touches still labeled 0 -"
          % (100 * res["cost_wedge"]))
    print("   the touch cleared the barrier but not the cost stack. That")
    print("   wedge is pure fee geometry and no horizon change moves it.")

    print("\n" + "=" * 70)
    if winners:
        print("SURVIVING GEOMETRIES (lower bound > 0 after correction):")
        for c in winners:
            print("  h=%d tp=%.2f sl=%.2f  mean %+.3f%%  lower %+.3f%%"
                  % (c["horizon_bars"], c["tp_pct"], c["sl_pct"],
                     c["mean_net_pct"], c["lower_bonf"]))
        print("Treat as CANDIDATES for a pre-registered forward test, not")
        print("as a discovery - an in-sample grid winner must earn a live")
        print("cohort like everything else.")
    else:
        best = res["best"]
        print("VERDICT: NO GEOMETRY SURVIVES. Best combo: h=%d tp=%.2f "
              "sl=%.2f" % (best["horizon_bars"], best["tp_pct"],
                           best["sl_pct"]))
        print("at mean %+.3f%% (lower bound %+.3f%%). No bracket in a grid"
              % (best["mean_net_pct"], best["lower_bonf"]))
        print("spanning 2h-36h and 0.25%-2% barriers makes these entries")
        print("net-positive at the configured fees. This is the direct")
        print("form of what three tools said separately: entries without")
        print("timing information plus 0.50-0.65% round trips leave no")
        print("geometry to find. Exit design can MINIMIZE bleed (fewer,")
        print("longer, maker-only round trips); it cannot create edge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
