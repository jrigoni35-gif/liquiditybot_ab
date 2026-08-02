"""scripts/cohort_eval.py — pre-registered cohort evaluation of the 432-bar
migration, with era segmentation and an exit-asymmetry decomposition.

WHY THIS EXISTS. On 2026-08-02 the operator asked why the bot was profitable.
It was not: net -$50.44 over 20 days, and -$12.42 of that in the last 48
hours. What HAD changed was live_clean going 0 -> 24, the learning loop
restarting after the migration. Learning-loop-repaired and
strategy-profitable are different claims, and conflating them is how a losing
system keeps getting funded.

This tool exists so the next reading is settled by a rule written BEFORE the
data arrives rather than by whatever the number happens to be that morning.

THREE THINGS IT DOES, all of which the boards cannot:

1. PRE-REGISTRATION. The stopping rule is a constant in this file, committed
   to git, timestamped. MIN_COHORT_N is 50 closed trades under the new
   geometry. 48 hours at a 36-hour horizon is barely one horizon-length: a
   win rate off six trades has a Wilson interval so wide it is consistent
   with both ruin and riches, so reading it is worse than not looking.
   The tool REFUSES to render a verdict below the threshold.

2. ERA SEGMENTATION. Never one blended win rate. Nearly all of the 200-trade
   performance window is old-geometry, so a blended figure moves for purely
   COMPOSITIONAL reasons - it can show "recovery" purely because old losers
   aged out of the window, with no change in behaviour whatsoever. Cohorts
   are split at the migration commit (7566ea88, 2026-08-01 20:27:08 -0500).

3. EXIT ASYMMETRY. Win rate 5.5% together with payoff ratio 0.409 should not
   co-occur: a low win rate is normal when winners are LARGE. Small winners
   AND few of them means either winners are cut early or costs dominate. The
   decomposition below separates those two, because they have opposite fixes
   - one is an exit-policy bug, the other says the geometry cannot pay at
   this horizon no matter how good the selector is.

   The discriminator is MFE (max favourable excursion) against realized:
     capture   = realized / MFE   how much of the available move was taken
     cost drag = MAE  - realized  loss NOT explained by price moving against
   A trade with MFE +0.307%, MAE -0.075% and realized -0.410% never moved
   0.41% against you in the first place. That is not an exit problem.

    python scripts/cohort_eval.py [--json] [--csv PATH]

Report-only. Reads outputs/postmortem_summary.csv, touches no decision path.
"""
import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- PRE-REGISTERED, 2026-08-02. Changing these after seeing the data is
# --- exactly the thing pre-registration exists to prevent; if they must
# --- change, say so in the commit message and say why.
MIGRATION_TS = 1785634028      # 7566ea88, 432-bar migration
MIN_COHORT_N = 50              # closed trades before ANY verdict
STOP_IF_NET_PCT_BELOW = -1.0   # cohort mean net % per trade -> stand down
CONTINUE_IF_NET_PCT_ABOVE = 0.0
_PREREG = "2026-08-02"


def wilson(k: int, n: int, z: float = 1.96):
    """Wilson score interval — the honest interval for a proportion at small n.

    The normal approximation puts the bound outside [0,1] and understates
    width exactly where it matters most (few trades), which is the regime
    this whole tool is about.
    """
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def _f(row, key):
    try:
        return float(row[key])
    except (TypeError, ValueError, KeyError):
        return None


def summarize(rows, label):
    net = [r for r in (_f(x, "realized_pct") for x in rows) if r is not None]
    n = len(net)
    if n == 0:
        return {"cohort": label, "n": 0}
    wins = sum(1 for v in net if v > 0)
    w_p, w_lo, w_hi = wilson(wins, n)
    gp = sum(v for v in net if v > 0)
    gl = -sum(v for v in net if v < 0)
    avg_w = (gp / wins) if wins else 0.0
    avg_l = (gl / (n - wins)) if n - wins else 0.0

    # Exit asymmetry. capture is only meaningful where a favourable move
    # existed at all, so trades with MFE <= 0 are excluded rather than
    # counted as 0% capture - there was nothing to capture.
    caps, drags = [], []
    for x in rows:
        rp, mfe, mae = (_f(x, "realized_pct"), _f(x, "mfe_pct"),
                        _f(x, "mae_pct"))
        if rp is None:
            continue
        if mfe is not None and mfe > 0.01:
            caps.append(rp / mfe)
        if mae is not None:
            drags.append(mae - rp)      # >0 means worse than price alone
    return {
        "cohort": label, "n": n,
        "win_rate": w_p, "win_lo": w_lo, "win_hi": w_hi,
        "mean_net_pct": sum(net) / n,
        "median_net_pct": sorted(net)[n // 2],
        "payoff": (avg_w / avg_l) if avg_l else float("inf"),
        "profit_factor": (gp / gl) if gl else float("inf"),
        "capture_n": len(caps),
        "capture_median": sorted(caps)[len(caps) // 2] if caps else None,
        "cost_drag_median": (sorted(drags)[len(drags) // 2]
                             if drags else None),
        "mfe_positive_share": (len([1 for x in rows
                                    if (_f(x, "mfe_pct") or 0) > 0.01]) / n),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "outputs" /
                                         "postmortem_summary.csv"))
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()

    p = Path(ns.csv)
    if not p.exists():
        print(f"no postmortem data at {p}")
        return 1
    rows = list(csv.DictReader(open(p, newline="", encoding="utf-8")))
    old = [r for r in rows if (_f(r, "ts") or 0) < MIGRATION_TS]
    new = [r for r in rows if (_f(r, "ts") or 0) >= MIGRATION_TS]

    res = {"pre_registered": _PREREG, "min_cohort_n": MIN_COHORT_N,
           "migration_ts": MIGRATION_TS,
           "cohorts": [summarize(old, "pre-432 (old geometry)"),
                       summarize(new, "post-432 (36h horizon)")]}
    nn = res["cohorts"][1]["n"]
    res["verdict_available"] = nn >= MIN_COHORT_N
    res["progress"] = f"{nn}/{MIN_COHORT_N}"

    if ns.json:
        print(json.dumps(res, indent=1, default=str))
        return 0

    print("COHORT EVALUATION — pre-registered %s" % _PREREG)
    print("=" * 68)
    for c in res["cohorts"]:
        if not c["n"]:
            print("\n%s: no closed trades" % c["cohort"])
            continue
        print("\n%s  (n=%d)" % (c["cohort"], c["n"]))
        print("  win rate        %.1f%%   Wilson 95%% [%.1f%%, %.1f%%]"
              % (c["win_rate"] * 100, c["win_lo"] * 100, c["win_hi"] * 100))
        print("  mean net/trade  %+.3f%%   median %+.3f%%"
              % (c["mean_net_pct"], c["median_net_pct"]))
        print("  payoff ratio    %.3f    profit factor %.3f"
              % (c["payoff"], c["profit_factor"]))
        if c["capture_median"] is not None:
            print("  MFE capture     %.3f  (median realized/MFE over %d "
                  "trades that HAD a favourable move)"
                  % (c["capture_median"], c["capture_n"]))
        if c["cost_drag_median"] is not None:
            print("  cost drag       %+.3f%%  (median MAE-realized; >0 means "
                  "the loss exceeds the worst the price ever went)"
                  % c["cost_drag_median"])
        print("  had upside      %.0f%% of trades reached MFE > 0.01%%"
              % (c["mfe_positive_share"] * 100))

    print("\n" + "=" * 68)
    print("VERDICT GATE: %s toward the pre-registered %d closed trades"
          % (res["progress"], MIN_COHORT_N))
    if not res["verdict_available"]:
        print("\nNo verdict. The post-migration cohort is too small, and a")
        print("win rate at this n has a Wilson interval consistent with both")
        print("ruin and riches — reading it is worse than not looking.")
        print("Keep accruing. Do not retune on this number.")
    else:
        m = res["cohorts"][1]["mean_net_pct"]
        if m < STOP_IF_NET_PCT_BELOW:
            print("\nSTAND DOWN: cohort mean %+.3f%% is below the "
                  "pre-registered %.1f%%." % (m, STOP_IF_NET_PCT_BELOW))
        elif m > CONTINUE_IF_NET_PCT_ABOVE:
            print("\nCONTINUE: cohort mean %+.3f%% clears the bar." % m)
        else:
            print("\nINCONCLUSIVE: cohort mean %+.3f%% sits between the "
                  "pre-registered thresholds. Keep accruing." % m)

    c = res["cohorts"][0]
    if c["n"] and c.get("cost_drag_median") is not None \
            and c["cost_drag_median"] > 0:
        print("\nEXIT ASYMMETRY READ (old cohort): median loss exceeds the")
        print("worst adverse excursion by %+.3f%%. The price never moved that"
              % c["cost_drag_median"])
        print("far against these trades — so this is COST, not a stop being")
        print("hit too tight and not winners being cut early. An exit-policy")
        print("change cannot fix it; only a horizon long enough to earn more")
        print("than the round trip costs can.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
