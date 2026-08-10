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

Report-only. Reads outputs/postmortem_summary.csv (432-cohort sections) and
outputs/fills.csv (era-4 section), touches no decision path.

KNOWN CENSORING, measured 2026-08-10 and left in place deliberately: the
432-cohort sections read postmortem_summary.csv, and ml/postmortem.py records
only trades that UNDERPERFORMED entry-time EV (shortfall > max(0.10*|EV|,
0.25%)). Coverage of entry-opened closes is 85.1% pre-432 / 93.1% post-432,
which biases the win rate LOW by a measured -1.5pp / -5.4pp. The bias runs
the same direction in both cohorts, so the comparison stands; the absolute
win rates read a few points worse than truth. The original registration is
not rewritten mid-flight - the era-4 gate below reads the COMPLETE population
instead, which is the fix applied where it can still be applied honestly:
before the data exists.
"""
import argparse
import collections
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Legs that OPEN risk - a hedge opens a position exactly as an entry does
# (main.py debits the entry fee for every non-exit leg). Reconstruction must
# treat both as opening legs or hedge-opened trips read as still-open and
# vanish - the defect that inverted breakeven_test's verdict. Pinned by
# tests/test_opening_leg_pin.py.
_OPEN_PURPOSES = ("entry", "hedge")

# --- PRE-REGISTERED, 2026-08-02. Changing these after seeing the data is
# --- exactly the thing pre-registration exists to prevent; if they must
# --- change, say so in the commit message and say why.
MIGRATION_TS = 1785634028      # 7566ea88, 432-bar migration
MIN_COHORT_N = 50              # closed trades before ANY verdict
STOP_IF_NET_PCT_BELOW = -1.0   # cohort mean net % per trade -> stand down
CONTINUE_IF_NET_PCT_ABOVE = 0.0
_PREREG = "2026-08-02"

# --- PRE-REGISTERED, 2026-08-10, at era-4 n=1 - the only honest moment to
# --- register a stopping rule for a cohort: before the data exists. Same
# --- discipline as above: changing these after the cohort accrues is the
# --- thing pre-registration exists to prevent.
#
# ERA 4 = execution-era boundary #4 (commit aeeaae36): the fill simulator
# stopped double-counting the market crossing, so era-4 fills are the first
# whose per-order fill rate matches what the recorded market actually
# granted. Every earlier era was measured under a ~1.88x near-touch fill
# inflation; era-4 numbers are therefore the first citable ones.
#
# POPULATION: entry-opened closed round trips reconstructed from fills.csv -
# the COMPLETE population, not the postmortem (underperformer-censored) set.
# Hedge-opened trips are reconstructed (a hedge is an opening leg) but are
# NOT the strategy's trades: a hedge is insurance and loses by design, the
# same split main.py:1671 applies to the performance ledger.
#
# READOUT RULE, registered before the data (adjudicated with the operator
# 2026-08-10, CAIO review): the tool never decides - it names which decision
# has become decidable.
#   gross mean <= 0 AND gross median <= 0  -> "NO GROSS EDGE": the
#       stop-strategy question goes to the operator. No execution, cost or
#       model change is on the table, because none of them create
#       expectancy (scripts/breakeven_test.py's corrected verdict).
#   gross > 0, net <= 0                    -> "COST-BOUND": an edge exists
#       and fees eat it; the fee levers held behind h432 become the live
#       discussion.
#   net > 0                                -> "CONTINUE".
B4_TS = datetime(2026, 8, 10, 11, 3, 35,
                 tzinfo=timezone.utc).timestamp()   # aeeaae36, UTC instant
ERA4_MIN_N = 50                # entry-opened closes before ANY verdict
_PREREG_ERA4 = "2026-08-10"


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


def era4_trips(fills_path):
    """Entry-opened closed round trips from fills.csv closing at/after B4_TS.

    Returns a list of {"t", "gross_pct", "net_pct"} - the complete era-4
    strategy population. Same reconstruction discipline as breakeven_test:
    signed cash flow is gross, fees subtracted separately, fully-closed only
    (2% size tolerance), duplicate fill patterns dropped.
    """
    try:
        rows = list(csv.DictReader(open(fills_path, newline="",
                                        encoding="utf-8")))
    except OSError:
        return []
    by_pid = collections.defaultdict(list)
    for r in rows:
        if r.get("position_id"):
            by_pid[r["position_id"]].append(r)
    out, seen = [], set()
    for legs in by_pid.values():
        legs.sort(key=lambda r: _f(r, "ts") or 0.0)
        cash = fees = esz = xsz = enot = 0.0
        tclose = None
        opened_by = None
        sig, ok = [], True
        for r in legs:
            sz, px = _f(r, "fill_size"), _f(r, "fill_price")
            fee = _f(r, "fees_delta_usd")
            if sz is None or px is None or fee is None or sz <= 0 or px <= 0:
                ok = False
                break
            cash += (sz * px) if r.get("side") == "sell" else -(sz * px)
            fees += fee
            if r.get("purpose") in _OPEN_PURPOSES:
                esz += sz
                enot += sz * px
                if opened_by is None:
                    opened_by = r.get("purpose")
            elif r.get("purpose") == "exit":
                xsz += sz
                tclose = _f(r, "ts")
            sig.append((r.get("purpose"), r.get("side"),
                        round(sz, 6), round(px, 4)))
        if not ok or esz <= 0 or xsz <= 0 or enot <= 0 or tclose is None:
            continue
        if abs(xsz - esz) / esz > 0.02:
            continue
        key = tuple(sig)
        if key in seen:
            continue
        seen.add(key)
        if opened_by != "entry":        # hedges are insurance, not the thesis
            continue
        if tclose < B4_TS:
            continue
        out.append({"t": tclose, "gross_pct": 100.0 * cash / enot,
                    "net_pct": 100.0 * (cash - fees) / enot})
    return out


def era4_section(trips):
    """The pre-registered era-4 readout. Never decides; names what became
    decidable."""
    n = len(trips)
    res = {"pre_registered": _PREREG_ERA4, "b4_ts": B4_TS,
           "min_n": ERA4_MIN_N, "n": n,
           "progress": f"{n}/{ERA4_MIN_N}",
           "verdict_available": n >= ERA4_MIN_N}
    if n:
        g = sorted(t["gross_pct"] for t in trips)
        nt = sorted(t["net_pct"] for t in trips)
        mean_g = sum(g) / n
        # SE of the mean, printed WITH the mean (challenge hardening #2,
        # added at n=2, pre-data). At n=50 with per-trade sd ~0.5% the SE is
        # ~0.07%, so only |edges| beyond ~0.14% are resolvable - an order of
        # magnitude above every gross edge this strategy has exhibited. The
        # readout rule is unchanged: it is a pre-committed decision TRIGGER,
        # not a significance claim, and the interval exists so nobody reads
        # a triggered readout as a measured effect size.
        var_g = sum((v - mean_g) ** 2 for v in g) / n
        se_g = math.sqrt(var_g / n) if n > 1 else float("nan")
        res.update({
            "gross_mean_pct": mean_g, "gross_median_pct": g[n // 2],
            "gross_se_pct": se_g,
            "net_mean_pct": sum(nt) / n, "net_median_pct": nt[n // 2],
            "gross_win_rate": sum(1 for v in g if v > 0) / n,
            "net_win_rate": sum(1 for v in nt if v > 0) / n,
        })
    if not res["verdict_available"]:
        res["readout"] = "ACCRUING"
    elif res["gross_mean_pct"] <= 0 and res["gross_median_pct"] <= 0:
        res["readout"] = "NO_GROSS_EDGE"
    elif res["net_mean_pct"] <= 0:
        res["readout"] = "COST_BOUND"
    else:
        res["readout"] = "CONTINUE"
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "outputs" /
                                         "postmortem_summary.csv"))
    ap.add_argument("--fills", default=str(ROOT / "outputs" / "fills.csv"))
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
                       summarize(new, "post-432 (36h horizon)")],
           "era4": era4_section(era4_trips(ns.fills))}
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

    print("\n  CAVEAT (measured 2026-08-10): these cohorts read the")
    print("  postmortem ledger, which records only trades that")
    print("  underperformed entry-time EV - coverage 85.1%/93.1% of")
    print("  entry-opened closes, biasing win rates LOW by -1.5pp/-5.4pp.")
    print("  Same direction both cohorts: the comparison stands, the")
    print("  absolute win rates read a few points worse than truth.")

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

    e4 = res["era4"]
    print("\n" + "=" * 68)
    print("ERA-4 GATE - pre-registered %s at n=1, the honest-fill cohort"
          % _PREREG_ERA4)
    print("(execution-era boundary #4, aeeaae36: first fills granted at the")
    print(" rate the recorded market actually crossed - all earlier eras")
    print(" carried a ~1.88x near-touch inflation. Complete population from")
    print(" fills.csv, entry-opened only; no postmortem censoring.)")
    print("\n  accrual: %s entry-opened closes toward the verdict gate"
          % e4["progress"])
    if e4["n"]:
        print("  gross  mean %+.4f%%  (SE %.4f%%)  median %+.4f%%  win %.1f%%"
              % (e4["gross_mean_pct"], e4.get("gross_se_pct", float("nan")),
                 e4["gross_median_pct"], e4["gross_win_rate"] * 100))
        print("  resolution note: the gate is a pre-committed TRIGGER, not a")
        print("  measurement - a readout does not claim the effect size is")
        print("  resolved beyond ~2x the SE above.")
        print("  net    mean %+.4f%%  median %+.4f%%  win %.1f%%"
              % (e4["net_mean_pct"], e4["net_median_pct"],
                 e4["net_win_rate"] * 100))
    if e4["readout"] == "ACCRUING":
        print("\n  No verdict below n=%d. Do not read these numbers as a"
              % ERA4_MIN_N)
        print("  trend; do not retune on them.")
    elif e4["readout"] == "NO_GROSS_EDGE":
        print("\n  NO GROSS EDGE at n>=%d on honest fills: the stop-strategy"
              % ERA4_MIN_N)
        print("  question goes to the operator. No execution, cost or model")
        print("  change is on the table - none of them create expectancy.")
    elif e4["readout"] == "COST_BOUND":
        print("\n  COST-BOUND: a gross edge exists on honest fills and fees")
        print("  eat it. The fee levers held behind h432 become the live")
        print("  discussion.")
    else:
        print("\n  CONTINUE: net-positive on honest fills at n>=%d."
              % ERA4_MIN_N)

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
