"""scripts/label_transfer_filter.py - can old-era labels serve the new geometry?

THE QUESTION. 8,452 labeled candidates were accumulated under earlier
barrier geometries. Era exclusion currently treats them as all-or-nothing:
either the whole pool trains the model or none of it does. Neither is
obviously right. A label carries information about a SETUP as well as about
a horizon, and some of that survives translation while some does not.

This is the filter: keep what passes, leave the grounds behind. It is
deliberately capable of answering NO.

HOW TRANSFERABILITY IS MEASURED, rather than assumed. outputs/horizon_shadow
.csv labels the SAME candidate_id at several horizons at once, so agreement
between horizons is directly observable - no model, no assumption about how
labels decay. For every horizon pair it reports:

  agreement  P(same label) on candidates present at both horizons
  kappa      Cohen's kappa, CHANCE-CORRECTED agreement

Kappa is the number that matters and raw agreement is the trap. These labels
are 79% zeros, so two coin flips weighted 79/21 agree ~67% of the time while
sharing no information whatsoever. An 80%-agreement pair can be worth
nothing. Kappa subtracts exactly that chance floor: 0 means "no better than
guessing the base rate", 1 means perfect.

WHY THIS CAN ANSWER THE 432 QUESTION AT ALL. 432 bars is not in the shadow
ladder, so its agreement cannot be measured directly. But transferability
tracks the RATIO of the two horizons, not their absolute size, and the
ladder contains 6 -> 96, a 16x jump. The migration is 24 -> 432, an 18x
jump. That is close enough to be an ANALOGUE rather than an extrapolation,
which is the difference between an estimate and a guess. It is still an
analogue: stated here, and again in the output, so no reader mistakes it for
a measurement of 432 itself.

THE ADMISSION RULE, and why it has no tuned constant. A pool's weight is its
own measured kappa lower bound:

    weight(h) = max(0.0, kappa_lcb(h -> target_ratio))

A pool whose agreement with the target is chance-level gets weight 0 and
contributes nothing. A pool that genuinely predicts the target gets weight
proportional to how much, with sampling error already subtracted by using
the LOWER bound. Nothing here is fitted; the data sets the number, and the
repo's no-fitted-literals rule is satisfied because there is no literal to
fit.

Kish effective sample size reports what the weighted pool is actually worth:
8,452 rows at weight 0.1 is not 8,452 rows of evidence, and ESS says so.

    python scripts/label_transfer_filter.py [--json] [--target-ratio 18]

Report-only. Reads outputs/horizon_shadow.csv, writes nothing to any
decision path.

PROVENANCE CAVEAT: shadow_path was one of the QA leak paths closed in
858c8d71, and horizon_shadow.csv has no order_id column to crossref against
the audit trail, so ~41% of its rows (the ETH/BTC share) are UNDECIDABLE -
see scripts/provenance_audit.py. Kappa is a same-candidate agreement
statistic, so fixture candidates would perturb it only if a QA bot banked
shadow labels at multiple horizons; provenance_audit found 0 replay
collisions, which bounds but does not eliminate that risk.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def kappa(pairs):
    """Cohen's kappa with its standard error, on a list of (a, b) labels.

    Returns (kappa, se). The chance term uses the MARGINALS of each rater,
    which is what makes it immune to the 79%-zero base rate that inflates
    raw agreement.
    """
    n = len(pairs)
    if n == 0:
        return (0.0, 0.0)
    obs = sum(1 for a, b in pairs if a == b) / n
    pa1 = sum(1 for a, _ in pairs if a == 1) / n
    pb1 = sum(1 for _, b in pairs if b == 1) / n
    exp = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    if exp >= 1.0:
        return (0.0, 0.0)
    k = (obs - exp) / (1 - exp)
    se = math.sqrt(max(obs * (1 - obs), 1e-12) / n) / (1 - exp)
    return (k, se)


def effective_rows(weight: float, n: int) -> float:
    """What a uniformly down-weighted pool is worth: Σw = n * weight.

    The first version used Kish ESS here, which was WRONG in a way worth
    recording: Kish ((Σw)²/Σw²) measures the inefficiency of UNEQUAL
    weights, and on a uniform weight it returns exactly n no matter how
    small the weight is - so the tool printed "8,452 rows at weight 0.1 ->
    effective 8,452" while its own docstring promised the opposite. For a
    pool carried at one shared weight, the information measure that evidence
    gates should count is the weight-sum: each transferred label is worth
    `weight` of a native label, kappa being the fraction of its information
    that survives the horizon translation."""
    return max(0.0, weight) * max(0, n)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shadow", default=str(ROOT / "outputs" /
                                            "horizon_shadow.csv"))
    ap.add_argument("--target-ratio", type=float, default=18.0,
                    help="new horizon / old horizon (432/24 = 18)")
    ap.add_argument("--pool-rows", type=int, default=8452,
                    help="old-era labeled rows the filter would admit")
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()

    p = Path(ns.shadow)
    if not p.exists():
        print(f"no shadow data at {p}")
        return 1
    by_cand = defaultdict(dict)
    with open(p, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                by_cand[r["candidate_id"]][int(r["horizon_bars"])] = \
                    int(r["label"])
            except (TypeError, ValueError, KeyError):
                continue
    horizons = sorted({h for v in by_cand.values() for h in v})
    if len(horizons) < 2:
        print("need at least two horizons in the shadow ladder")
        return 1

    rows = []
    for i, h1 in enumerate(horizons):
        for h2 in horizons[i + 1:]:
            pairs = [(v[h1], v[h2]) for v in by_cand.values()
                     if h1 in v and h2 in v]
            if len(pairs) < 100:
                continue
            n = len(pairs)
            agree = sum(1 for a, b in pairs if a == b)
            ap_, alo, ahi = wilson(agree, n)
            k, se = kappa(pairs)
            klo = k - 1.96 * se
            rows.append({
                "from": h1, "to": h2, "ratio": h2 / h1, "n": n,
                "agree": ap_, "agree_lo": alo, "agree_hi": ahi,
                "kappa": k, "kappa_lo": klo, "kappa_hi": k + 1.96 * se,
                "base_from": sum(a for a, _ in pairs) / n,
                "base_to": sum(b for _, b in pairs) / n,
            })

    # The pair whose RATIO is closest to the migration's is the candidate
    # analogue - in LOG space, because transferability tracks the horizon
    # ratio multiplicatively (4x is as far below 18x as 81x is above it).
    # The first version took the closest survivor unconditionally and, when
    # thin overlap dropped every long-ratio pair, crowned a 4.0x pair "the
    # analogue" for an 18x migration. That is extrapolation wearing an
    # analogue's name tag, so the tool now REFUSES instead: a candidate
    # further than ANALOGUE_MAX_OFF from the target in ratio terms yields no
    # verdict, the same discipline as cohort_eval's n<50 refusal. 1.5x is a
    # refusal tolerance, not a fitted parameter: past it, the 6->96=16x pair
    # the docstring promises would itself be rejected in favour of nothing.
    ANALOGUE_MAX_OFF = 1.5
    best = min(rows, key=lambda r: abs(math.log(r["ratio"])
                                       - math.log(ns.target_ratio))) \
        if rows else None
    off = (max(best["ratio"], ns.target_ratio)
           / min(best["ratio"], ns.target_ratio)) if best else float("inf")
    analogue_ok = best is not None and off <= ANALOGUE_MAX_OFF
    weight = max(0.0, best["kappa_lo"]) if analogue_ok else 0.0
    ess = effective_rows(weight, ns.pool_rows)

    out = {"horizons": horizons, "pairs": rows,
           "target_ratio": ns.target_ratio,
           "candidate_analogue": best, "analogue_ok": analogue_ok,
           "ratio_off_by": off, "admit_weight": weight,
           "pool_rows": ns.pool_rows, "effective_rows": ess}
    if ns.json:
        print(json.dumps(out, indent=1))
        return 0

    print("LABEL TRANSFER FILTER - do old-era labels survive the geometry?")
    print("=" * 72)
    print("\nkappa is CHANCE-CORRECTED. These labels are ~79% zeros, so two")
    print("independent guesses agree ~67% of the time while sharing nothing.")
    print("Read kappa, not agreement.\n")
    print("  from ->   to   ratio       n   agreement            kappa"
          "  95% CI")
    print("  " + "-" * 68)
    for r in rows:
        mark = ("  <- analogue" if analogue_ok else "  <- closest (refused)") \
            if best and r is best else ""
        print("  %4d -> %4d  %5.1fx  %6d   %.3f [%.3f,%.3f]   %+.3f"
              "  [%+.3f,%+.3f]%s"
              % (r["from"], r["to"], r["ratio"], r["n"], r["agree"],
                 r["agree_lo"], r["agree_hi"], r["kappa"], r["kappa_lo"],
                 r["kappa_hi"], mark))

    print("\n" + "=" * 72)
    if not best:
        print("No horizon pair had enough overlap. No verdict.")
        return 0
    print("TARGET: ratio %.1fx (the 24 -> 432 migration)." % ns.target_ratio)
    print("CLOSEST PAIR: %d -> %d at %.1fx, kappa %+.3f [%+.3f, %+.3f] "
          "on n=%d."
          % (best["from"], best["to"], best["ratio"], best["kappa"],
             best["kappa_lo"], best["kappa_hi"], best["n"]))

    if not analogue_ok:
        print("\nVERDICT: NO ANALOGUE - REFUSING, not estimating.")
        print("The closest measurable pair is %.1fx off the target ratio"
              % off)
        print("(tolerance %.1fx). Weighting old labels from it would be an"
              % ANALOGUE_MAX_OFF)
        print("extrapolation presented as a measurement - the exact thing")
        print("this tool exists to prevent. The 16x pair (6 -> 96) becomes")
        print("measurable once enough candidates carry BOTH 6- and 96-bar")
        print("shadow labels; until then the era exclusion's all-or-nothing")
        print("answer stands unchallenged.")
        return 0

    print("\nThis is an ANALOGUE, not a measurement of 432. Transferability")
    print("tracks the horizon RATIO, and no 432-bar shadow labels exist yet.")
    print("\nADMISSION WEIGHT = max(0, kappa_lower_bound) = %.3f" % weight)
    if weight <= 0.0:
        print("\nVERDICT: DO NOT USE THE POOL AS A TEMPLATE.")
        print("At this ratio the old labels agree with the target no better")
        print("than chance once the base rate is accounted for. They would")
        print("add rows without adding information - which is worse than")
        print("adding nothing, because sample-size gates would read the row")
        print("count as evidence and unlock complexity the data cannot")
        print("support. Era exclusion is doing the right thing.")
    else:
        print("\n%d pooled rows at weight %.3f -> %.0f effective rows (sum "
              "of weights;" % (ns.pool_rows, weight, ess))
        print("each transferred label is worth `weight` of a native one).")
        print("\nVERDICT: ADMISSIBLE AS A WEIGHTED PRIOR, not as raw rows.")
        print("Carry them at the weight above so every evidence gate counts")
        print("effective rows, never the raw count. %.0f effective is what"
              % ess)
        print("this pool is worth; %d is what it would falsely claim."
              % ns.pool_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
