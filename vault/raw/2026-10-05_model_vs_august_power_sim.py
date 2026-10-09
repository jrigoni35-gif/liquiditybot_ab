"""Simulate the MEASUREMENT, not the market: how many days of new labeled
rows does the paired August-vs-today Brier test need to detect a true gap?

Resamples the 13 REAL observed days (row counts + loss differentials), with
the daily differentials re-centred on a hypothetical true gap delta. Each
simulated window of N days is judged by a day-clustered 95% interval
(CR1, ratio estimator) - first checked against the real day-block bootstrap
at N=13. Power = share of windows whose interval excludes 0 on the right side.
"""
import sys
import numpy as np

z = np.load(sys.argv[1]); d, day = z["d"], z["day"]
days = np.unique(day)
n = np.array([np.sum(day == k) for k in days], float)          # rows per day
s = np.array([d[day == k].sum() for k in days], float)          # loss-diff sum per day
D_obs = s.sum() / n.sum()

def ci_cluster(n_, s_):
    D = s_.sum() / n_.sum(); N = len(n_)
    se = np.sqrt(N / (N - 1) * np.sum((s_ - D * n_) ** 2)) / n_.sum()
    return D, D - 1.96 * se, D + 1.96 * se

D, lo, hi = ci_cluster(n, s)
print(f"observed: {len(days)} days, {int(n.sum())} rows, gap {D_obs:+.4f}, "
      f"clustered CI [{lo:+.4f}, {hi:+.4f}]  (day-block bootstrap gave [-0.0050, +0.0164])")

rng = np.random.default_rng(7)
def power(N, delta, sims=4000):
    s_c = s + n * (delta - D_obs)                                 # re-centre on the true gap
    pick = rng.integers(0, len(days), size=(sims, N))
    hits = 0
    for row in pick:
        _, l, _ = ci_cluster(n[row], s_c[row])
        hits += l > 0
    return hits / sims

print("\npower to show 'today better' (CI excludes 0), by true gap and window length:")
grid = (13, 30, 45, 60, 90, 120, 180)
print("true gap   " + "".join(f"{N:>7}d" for N in grid))
for delta in (0.0025, 0.0053, 0.0100):
    print(f"{delta:+.4f}   " + "".join(f"{power(N, delta):>8.0%}" for N in grid))

for delta in (0.0025, 0.0053, 0.0100):
    need = next((N for N in range(13, 721, 3) if power(N, delta, sims=1500) >= 0.80), None)
    print(f"days for 80% power at gap {delta:+.4f}: {need if need else '> 720'}")
print("\nnull check (true gap 0): false 'better' rate at 60d =", f"{power(60, 0.0):.1%}", "(expected ~2.5%)")
