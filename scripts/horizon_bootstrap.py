"""scripts/horizon_bootstrap.py - error bars on the break-even selection curve.

THE CLAIM UNDER TEST. The 432-bar migration (commit 7566ea88) rests on a
monotone curve measured from outputs/horizon_shadow.csv: the fraction of
candidates a PERFECT selector could take while still averaging > 0 net of
cost rises with horizon - top 20% at 6 bars, 40% at 24, 51% at 48, 56% at
96. If that curve is a tail artifact of one lucky resample, the migration
rests on nothing.

Those were point estimates off unequal samples (1,327 rows at 6 bars,
6,606 at 96). A point estimate on 1,327 draws and one on 6,606 do not
deserve the same confidence, and a monotone-looking sequence of five noisy
numbers is exactly the shape noise produces by accident.

WHAT THIS MEASURES, precisely. The break-even selection rate is an ORACLE
bound: it assumes perfect ranking of the candidates. It is the CEILING on
what any selector could extract, not a forecast of what the model will.
Bootstrapping puts sampling error on that ceiling. It cannot tell you the
ceiling is reachable - only whether the ceiling itself is real.

METHOD. Non-parametric bootstrap: resample each horizon's outcomes with
replacement B times, recompute the statistic on each resample, report the
2.5/97.5 percentiles. No distributional assumption, which matters because
these returns are fat-tailed and visibly non-normal.

Deterministic: fixed seed, so a rerun on the same corpus reproduces the
same interval (the repo's replay-determinism rule applies to research
tooling too - an instrument whose answer moves between runs cannot settle
an argument).

    python scripts/horizon_bootstrap.py [--b 2000] [--seed 7] [--json]
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def breakeven_rate(sorted_desc: np.ndarray) -> float:
    """Largest fraction k such that the mean of the top k still exceeds 0.

    Computed on the ALREADY-SORTED descending array via a cumulative mean,
    so one resample costs O(n) rather than O(n) sorts - the difference
    between a 2,000-draw bootstrap finishing in seconds and in minutes.
    Returns 0.0 when even the single best outcome loses, which is the
    honest answer at very short horizons: there is nothing to select.
    """
    n = sorted_desc.size
    if n == 0:
        return 0.0
    cum_mean = np.cumsum(sorted_desc) / np.arange(1, n + 1)
    ok = np.nonzero(cum_mean > 0.0)[0]
    return float((ok[-1] + 1) / n) if ok.size else 0.0


def top_k_mean(sorted_desc: np.ndarray, k: float) -> float:
    n = max(1, int(sorted_desc.size * k))
    return float(sorted_desc[:n].mean())


def bootstrap(vals: np.ndarray, b: int, rng) -> dict:
    n = vals.size
    be = np.empty(b)
    d10 = np.empty(b)
    for i in range(b):
        s = np.sort(vals[rng.integers(0, n, n)])[::-1]
        be[i] = breakeven_rate(s)
        d10[i] = top_k_mean(s, 0.10)
    obs = np.sort(vals)[::-1]
    return {
        "n": int(n),
        "breakeven_point": breakeven_rate(obs),
        "breakeven_lo": float(np.percentile(be, 2.5)),
        "breakeven_hi": float(np.percentile(be, 97.5)),
        "top10_point": top_k_mean(obs, 0.10),
        "top10_lo": float(np.percentile(d10, 2.5)),
        "top10_hi": float(np.percentile(d10, 97.5)),
        "mean": float(vals.mean()),
        "sd": float(vals.std()),
    }


def monotone_prob(by_h: dict, b: int, rng) -> float:
    """P(the curve is monotone increasing) under joint resampling.

    The migration's premise is not "56% > 20%" for one pair - it is that
    the WHOLE curve rises. Resampling every horizon together and asking how
    often the ordering survives tests that premise directly, and is a much
    harder bar than any single pairwise comparison.
    """
    hs = sorted(by_h)
    if len(hs) < 2:
        return float("nan")
    hits = 0
    for _ in range(b):
        seq = []
        for h in hs:
            v = by_h[h]
            s = np.sort(v[rng.integers(0, v.size, v.size)])[::-1]
            seq.append(breakeven_rate(s))
        hits += all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1))
    return hits / b


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shadow", default=str(ROOT / "outputs" /
                                            "horizon_shadow.csv"))
    ap.add_argument("--b", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--min-n", type=int, default=200)
    ap.add_argument("--out", default=str(ROOT / "outputs" /
                                         "horizon_bootstrap.md"))
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()

    p = Path(ns.shadow)
    if not p.exists():
        print(f"no shadow data at {p}")
        return 1
    raw = defaultdict(list)
    with open(p, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                raw[int(r["horizon_bars"])].append(float(r["net_ret_pct"]))
            except (TypeError, ValueError, KeyError):
                continue
    by_h = {h: np.asarray(v, float) for h, v in raw.items()
            if len(v) >= ns.min_n}
    if not by_h:
        print("no horizon has enough rows")
        return 1

    rng = np.random.default_rng(ns.seed)
    res = {h: bootstrap(v, ns.b, rng) for h, v in sorted(by_h.items())}
    p_mono = monotone_prob(by_h, min(ns.b, 500), rng)

    if ns.json:
        print(json.dumps({"horizons": res, "p_monotone": p_mono}, indent=1))
        return 0

    L = ["# Horizon curve - bootstrap", "",
         f"B={ns.b} resamples, seed={ns.seed}, percentile intervals.", "",
         "The break-even rate is an ORACLE bound (perfect ranking). These",
         "intervals cover SAMPLING error on that ceiling; they say nothing",
         "about whether a real selector reaches it.", "",
         "| bars | n | break-even % of candidates | 95% CI | top-decile net | 95% CI |",
         "|---:|---:|---:|---|---:|---|"]
    for h, r in res.items():
        L.append(
            f"| {h} | {r['n']} | **{r['breakeven_point']:.1%}** "
            f"| [{r['breakeven_lo']:.1%}, {r['breakeven_hi']:.1%}] "
            f"| {r['top10_point']:+.3f}% "
            f"| [{r['top10_lo']:+.3f}, {r['top10_hi']:+.3f}] |")
    hs = sorted(res)
    lo_h, hi_h = hs[0], hs[-1]
    disjoint = res[lo_h]["breakeven_hi"] < res[hi_h]["breakeven_lo"]
    L += ["", "## Verdict", "",
          f"- shortest ({lo_h} bars) vs longest ({hi_h} bars): intervals "
          f"{'DO NOT overlap' if disjoint else 'OVERLAP'}",
          f"- P(whole curve monotone increasing under joint resampling) = "
          f"**{p_mono:.3f}**", ""]
    if disjoint and p_mono >= 0.95:
        L.append("The curve survives resampling. The horizon effect is real,")
        L.append("not a tail artifact, and the migration's premise holds.")
    elif disjoint:
        L.append("Endpoints separate, but the FULL ordering is not stable -")
        L.append("the direction is real; the smooth monotone shape is not")
        L.append("established. Treat intermediate horizons as unranked.")
    else:
        L.append("Endpoints overlap. The curve is NOT established by this")
        L.append("sample and the migration's premise is unsupported here.")
    md = "\n".join(L)
    Path(ns.out).write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
