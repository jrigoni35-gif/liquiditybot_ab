"""scripts/markov_ensemble.py - a RANDOMIZED ensemble of Markov state
partitions: does ANY way of carving the market into states predict what comes
next? (SAFE: measurement only.)

    python scripts/markov_ensemble.py               # K=200 partitions
    python scripts/markov_ensemble.py --k 50        # faster

WHY RANDOM. Every hand-built state definition this project has used was a
forking path: the analyst picks the variables, the cuts and the horizon after
seeing data, and the best-looking partition is the one reported. Drawing the
partitions at random (seeded, reproducible) and correcting across ALL of them
removes the analyst from the selection - the "unpredictable" sets the operator
asked for, made honest.

REGISTERED BEFORE THE FIRST RUN (2026-10-02):
  data       independent 20-asset Binance panel (alpha_decay_report cache),
             resampled to daily closes at 00:00 UTC, 2023-01..2026-08.
  variables  11, all past-only, each turned into its past-365-day percentile
             rank: r1, r7, r28 (returns), volratio (7d/28d sigma), rel7 (vs
             the basket), volz (log volume vs 28d), imb1 (daily taker
             imbalance), funding_z, gpr_z, stable_z (exogenous), dow.
  partition  1-2 variables, 2-3 bins each, cuts uniform in (0.2, 0.8);
             K = 200 partitions, seed 7.
  targets    next-1-day and next-7-day DRIFT-ADJUSTED log returns.
  test       between-state variance of the target vs a CIRCULAR-SHIFT null
             (each asset's target series rotated by a random offset; keeps
             every series' own autocorrelation, breaks only the state ->
             future link; 199 shifts). Persistent rolling states cannot fake
             significance - the trap that caught the idea lab's classifier.
  family     Holm over all 2K tests.
  selection  walk-forward: the partition with the best FIRST-half p on the
             7-day target is the only one tested on the SECOND half.
  economics  that partition's out-of-sample per-state mean 7-day return vs
             the round trip 2c = 45 bps (and as a tilt).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SEED = 7
K = 200
N_SHIFT = 199
RANK_WINDOW = 365
VARIABLES = ("r1", "r7", "r28", "volratio", "rel7", "volz", "imb1",
             "funding_z", "gpr_z", "stable_z", "dow")


def percentile_rank_past(x: np.ndarray, n: int) -> np.ndarray:
    """r[t] = share of x[t-n : t] strictly below x[t]; NaN before n."""
    x = np.asarray(x, float)
    out = np.full(len(x), np.nan)
    for t in range(n, len(x)):
        w = x[t - n:t]
        w = w[np.isfinite(w)]
        if len(w) >= n // 2 and np.isfinite(x[t]):
            out[t] = float((w < x[t]).mean())
    return out


def random_partition(rng, names) -> dict:
    k = int(rng.integers(1, 3))
    vs = [str(v) for v in rng.choice(list(names), size=k, replace=False)]
    cuts = {}
    for v in vs:
        bins = int(rng.integers(2, 4))
        cuts[v] = sorted(round(float(c), 2) for c in rng.uniform(0.2, 0.8, bins - 1))
    return {"vars": vs, "cuts": cuts}


def n_states(part: dict) -> int:
    n = 1
    for v in part["vars"]:
        n *= len(part["cuts"][v]) + 1
    return n


def states(part: dict, ranks: dict) -> np.ndarray:
    """Mixed-radix state code; -1 where any variable is undefined."""
    code = None
    for v in part["vars"]:
        r = np.asarray(ranks[v], float)
        b = np.searchsorted(np.asarray(part["cuts"][v]), np.nan_to_num(r, nan=0.0), side="right")
        b = np.where(np.isfinite(r), b, -1)
        base = len(part["cuts"][v]) + 1
        if code is None:
            code = b.astype(int)
        else:
            code = np.where((code < 0) | (b < 0), -1, code * base + b)
    return code if code is not None else np.array([], int)


def _between(st: np.ndarray, y: np.ndarray) -> float:
    ok = (st >= 0) & np.isfinite(y)
    if ok.sum() < 10:
        return 0.0
    s, v = st[ok], y[ok]
    cnt = np.bincount(s)
    tot = np.bincount(s, weights=v)
    nz = cnt > 0
    means = tot[nz] / cnt[nz]
    return float((cnt[nz] * (means - v.mean()) ** 2).sum() / ok.sum())


def shift_pvalue(st, ret, n_shift: int, rng) -> float:
    """Single series: between-state variance vs circular shifts of `ret`."""
    return panel_shift_pvalue([(np.asarray(st), np.asarray(ret, float))], n_shift, rng)


def panel_shift_pvalue(pairs: list, n_shift: int, rng) -> float:
    st = np.concatenate([p[0] for p in pairs])
    y = np.concatenate([p[1] for p in pairs])
    obs = _between(st, y)
    ge = 0
    for _ in range(n_shift):
        ys = []
        for _s, r in pairs:
            n = len(r)
            k = int(rng.integers(max(1, n // 10), max(2, 9 * n // 10)))
            ys.append(np.roll(r, k))
        ge += _between(st, np.concatenate(ys)) >= obs
    return (1 + ge) / (1 + n_shift)


def holm(p: dict) -> dict:
    items = sorted(p.items(), key=lambda kv: kv[1])
    m, out, run = len(items), {}, 0.0
    for i, (k, v) in enumerate(items):
        run = max(run, min(1.0, (m - i) * v))
        out[k] = run
    return out


# ------------------------------------------------------------------ data
def build_panel(cache: Path) -> dict:
    """Daily, past-only variable ranks and drift-adjusted targets per asset."""
    from scripts import alpha_decay_report as ad
    data = {a: ad.binance_klines(f"{a}USDT", "1h", ad.PANEL_MONTHS, cache)
            for a in ad.PANEL_UNIVERSE}
    gpr = ad.load_gpr(cache)
    stb = ad.defillama_stables(cache)
    daily = {}
    for a, d in data.items():
        if len(d["close"]) < 2000:
            continue
        t = d["t"]
        i = np.where((t % 86400) == 0)[0]
        day_t = t[i]
        c = d["close"][i]
        # daily volume / taker volume = sums of the 24 hourly bars ENDING at i
        cv = np.concatenate([[0.0], np.cumsum(d["vol"])])
        ctb = np.concatenate([[0.0], np.cumsum(d["taker_buy"])])
        lo = np.maximum(i - 24, 0)
        vol = cv[i] - cv[lo]
        tbv = ctb[i] - ctb[lo]
        daily[a] = {"t": day_t, "lp": np.log(c), "vol": vol, "tb": tbv,
                    "fund": ad.binance_funding(a, ad.PANEL_MONTHS, cache)}
    basket_r7 = {}
    for d in daily.values():
        for tt, r in zip(d["t"][7:], d["lp"][7:] - d["lp"][:-7], strict=True):
            basket_r7.setdefault(tt, []).append(r)
    out = {}
    for a, d in daily.items():
        lp, t = d["lp"], d["t"]
        n = len(lp)
        r1 = np.r_[np.nan, np.diff(lp)]
        r7 = np.r_[np.full(7, np.nan), lp[7:] - lp[:-7]]
        r28 = np.r_[np.full(28, np.nan), lp[28:] - lp[:-28]]
        sd7 = np.array([np.nanstd(r1[max(0, k - 6):k + 1]) if k >= 7 else np.nan for k in range(n)])
        sd28 = np.array([np.nanstd(r1[max(0, k - 27):k + 1]) if k >= 28 else np.nan for k in range(n)])
        bk = np.array([np.mean(basket_r7.get(tt, [np.nan])) for tt in t])
        lv = np.log(np.where(d["vol"] > 0, d["vol"], np.nan))
        volz = lv - np.array([np.nanmean(lv[max(0, k - 28):k]) if k >= 28 else np.nan for k in range(n)])
        imb = np.where(d["vol"] > 0, (2 * d["tb"] - d["vol"]) / np.where(d["vol"] > 0, d["vol"], 1), np.nan)
        f = d["fund"]
        fz = ad._daily_z(f["t"], f["rate"], t, "level7") if len(f["t"]) else np.full(n, np.nan)
        raw = {"r1": r1, "r7": r7, "r28": r28, "volratio": sd7 / sd28, "rel7": r7 - bk,
               "volz": volz, "imb1": imb, "funding_z": fz,
               "gpr_z": ad._daily_z(gpr["t"], gpr["v"], t, "level7"),
               "stable_z": ad._daily_z(stb["t"], stb["usd"], t, "chg7")}
        ranks = {k: percentile_rank_past(v, RANK_WINDOW) for k, v in raw.items()}
        ranks["dow"] = (((t // 86400) + 3) % 7) / 6.0          # 1970-01-01 was Thursday
        F = ad.forward(lp, (1, 7))
        D = ad.expanding_drift(lp, (1, 7), 90)
        out[a] = {"t": t, "ranks": ranks, "y1": F[:, 0] - D[:, 0], "y7": F[:, 1] - D[:, 1]}
    return out


def run(cache: Path, k: int, rng) -> dict:
    panel = build_panel(cache)
    parts = [random_partition(np.random.default_rng(SEED + i), VARIABLES) for i in range(k)]
    tmid = np.median(np.concatenate([p["t"] for p in panel.values()]))
    rows, pv = [], {}
    for i, part in enumerate(parts):
        st = {a: states(part, p["ranks"]) for a, p in panel.items()}
        row = {"i": i, "part": part, "n_states": n_states(part)}
        for tgt in ("y1", "y7"):
            pairs = [(st[a], p[tgt]) for a, p in panel.items()]
            row[f"p_{tgt}"] = panel_shift_pvalue(pairs, N_SHIFT, rng)
            pv[f"{i}:{tgt}"] = row[f"p_{tgt}"]
            first = [(st[a][p["t"] < tmid], p[tgt][p["t"] < tmid]) for a, p in panel.items()]
            row[f"p_{tgt}_first"] = panel_shift_pvalue(first, 99, rng) if tgt == "y7" else None
        rows.append(row)
    hp = holm(pv)
    for r in rows:
        r["p_holm_y1"], r["p_holm_y7"] = hp[f"{r['i']}:y1"], hp[f"{r['i']}:y7"]
    best = min(rows, key=lambda r: r["p_y7_first"])
    part = best["part"]
    st = {a: states(part, p["ranks"]) for a, p in panel.items()}
    second = [(st[a][p["t"] >= tmid], p["y7"][p["t"] >= tmid]) for a, p in panel.items()]
    p_oos = panel_shift_pvalue(second, N_SHIFT, rng)
    s_all = np.concatenate([x[0] for x in second])
    y_all = np.concatenate([x[1] for x in second])
    ok = (s_all >= 0) & np.isfinite(y_all)
    per_state = {int(s): {"n": int((s_all[ok] == s).sum()),
                          "mean_bps": float(y_all[ok][s_all[ok] == s].mean() * 1e4)}
                 for s in np.unique(s_all[ok])}
    return {"k": k, "n_tests": len(pv), "assets": sorted(panel),
            "survive_holm": [r["i"] for r in rows if min(r["p_holm_y1"], r["p_holm_y7"]) < 0.05],
            "min_p_y1": min(r["p_y1"] for r in rows), "min_p_y7": min(r["p_y7"] for r in rows),
            "share_p_below_05": float(np.mean([v < 0.05 for v in pv.values()])),
            "walk_forward": {"chosen": best["i"], "partition": part,
                             "p_first_half": best["p_y7_first"], "p_second_half": p_oos,
                             "per_state_7d_oos": per_state},
            "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--k", type=int, default=K)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    cache = ROOT / "outputs" / "reports" / "alpha_decay" / "cache"
    t0 = time.time()
    res = run(cache, args.k, np.random.default_rng(SEED))
    out_dir = Path(args.out) if args.out else ROOT / "outputs" / "reports" / "markov_ensemble"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"ensemble_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    path.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    wf = res["walk_forward"]
    print(f"randomized Markov ensemble: K={res['k']} partitions x 2 targets = {res['n_tests']} "
          f"tests on {len(res['assets'])} assets (daily, 2023-01..2026-08)")
    print(f"  share of raw p < 0.05: {res['share_p_below_05']:.3f} (null expectation 0.05)")
    print(f"  smallest raw p: next-day {res['min_p_y1']:.4f}, next-week {res['min_p_y7']:.4f}")
    print(f"  partitions surviving Holm across all tests: {res['survive_holm'] or 'none'}")
    print(f"  walk-forward: chose #{wf['chosen']} {wf['partition']} on first-half p "
          f"{wf['p_first_half']:.3f}; second-half p {wf['p_second_half']:.3f}")
    for s, v in sorted(wf["per_state_7d_oos"].items()):
        print(f"    state {s}: n={v['n']:>5} next-week drift-adjusted {v['mean_bps']:+7.1f} bps")
    print(f"({time.time() - t0:.0f}s) wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
