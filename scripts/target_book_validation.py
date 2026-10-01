"""scripts/target_book_validation.py - prove or refute every claim behind the
SHADOW target book (SAFE: measurement only; places nothing).

    python scripts/target_book_validation.py                  # daily + weekly
    python scripts/target_book_validation.py --paths 100      # faster nulls
    python scripts/target_book_validation.py --csv-root DIR   # offline: DIR/<iv>m/<ASSET>.csv

REGISTERED BEFORE THE FIRST RUN (2026-10-01; changing any of these after
looking is a new registration): alpha 0.05 two-sided; walk-forward = 40%
initial train then 5 equal expanding folds, selection = in-sample argmax of
mean excess (the classical worst case) vs the fixed baseline; PBO via CSCV,
8 blocks; null paths per test = --paths (default 200), seed 7; variance-
ratio horizons q = 2, 4, 8, 16; Markov states per bar, permutation and GBM
nulls 2,000 / --paths; band sweep multipliers 0, 0.5, 1, 2, 4.

Sections (each prints its unit and its n):
  1 BACKTEST       every idea in the family + baseline vs buy-and-hold,
                   per-asset P&L attribution (does the book lose by buying
                   the loser?), fees vs the gap, fill-model + seeding
                   sensitivity.
  2 WALK-FORWARD   expanding-window selection, out-of-sample only; PBO.
  3 BROWNIAN       (a) Lo-MacKinlay variance ratios, assets and pair
                   ratios; (b) real result vs correlated-GBM worlds fitted
                   to the same data; (c) real vs time-shuffled history;
                   (d) theory: plan() == constant-mix exactly, constant-mix
                   growth == analytic diversification return, the
                   Janecek-Shreve band vs other widths under its own model,
                   the market-state classifier's false-positive rate.
  4 MARKOV         per-bar states (reversal/continuation x high/low vol,
                   no overlapping windows), transition matrix, stationary
                   law, dwell times, memory test vs permutation AND GBM
                   nulls, next-bar rebalancing payoff by state; the lab's
                   rolling-window state persistence vs its GBM null.
  5 LEDGER         every assumption, its test, its verdict.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.idea_lab import (Bars, Idea, ShadowBook, family,  # noqa: E402
                           read_market, step_book)
from core.target_book import BookParams, Pressure, plan  # noqa: E402
from scripts.target_book_replay import (align, default_out_dir,  # noqa: E402
                                        fetch_kraken, load_csv, params_from,
                                        save_csv)

ALPHA = 0.05
SEED = 7
VR_Q = (2, 4, 8, 16)
BAND_MULTS = (0.0, 0.5, 1.0, 2.0, 4.0)
N_FOLDS = 5
TRAIN_FRAC = 0.4


# ======================================================================= data
def load_bars(cfg: dict, iv: int, csv_root: Path | None, cache: Path) -> Bars:
    series = {}
    for a in cfg["target_book"]["assets"]:
        if csv_root is not None:
            series[a] = load_csv(csv_root / f"{iv}m" / f"{a}.csv")
        else:
            series[a] = fetch_kraken(a, iv)
            save_csv(cache / f"ohlc_{iv}m" / f"{a}.csv", series[a])
            time.sleep(1.1)
    return align(series)


def log_returns(bars: Bars) -> np.ndarray:
    """(T-1, A) log close-to-close returns, assets in sorted order."""
    c = np.array([bars.close[a] for a in sorted(bars.close)], float).T
    return np.diff(np.log(c), axis=0)


# ================================================================ policy runs
def run_policy(bars: Bars, idea: Idea, base: BookParams, cfg: dict, lim,
               start: int, end: int, cash: float = 800.0) -> dict:
    """Book from `start` to `end` (decisions start..end-1). Returns per-step
    returns, its buy-and-hold twin, fees, and per-asset attribution."""
    b = ShadowBook(idea, start, cash, {}, cash)
    contrib = {a: 0.0 for a in bars.close}
    for i in range(start, end):
        step_book(b, bars, i, base, cfg, lim)
        for a, u in b.units.items():
            contrib[a] += u * (bars.close[a][i + 1] - bars.close[a][i])
    px_end = {a: c[end] for a, c in bars.close.items()}
    px_start = {a: c[start] for a, c in bars.close.items()}
    bench_contrib = {a: b.bench_units.get(a, 0.0) * (px_end[a] - px_start[a])
                     for a in bars.close}
    eq_end = b.equity(px_end)
    bench_end = b.bench_cash + sum(u * px_end[a] for a, u in b.bench_units.items())
    return {"rets": np.array(b.rets), "bench": np.array(b.bench_rets),
            "eq_end": eq_end, "bench_end": bench_end, "fees": b.fees,
            "traded": b.traded_usd, "fills": b.fills, "attempts": b.attempts,
            "contrib": contrib, "bench_contrib": bench_contrib,
            "log_gap": math.log(eq_end / cash) - math.log(bench_end / cash)}


def baseline(base: BookParams) -> Idea:
    return Idea(base.gamma, base.aim_rate, base.weighting, "none")


# ================================================================ 1 backtest
def backtest(bars, base, cfg, lim, warm) -> dict:
    end = len(bars) - 1
    fam = family(cfg)
    rows = []
    for idea in fam:
        r = run_policy(bars, idea, base, cfg, lim, warm, end)
        rows.append({"id": idea.id, "log_gap": r["log_gap"], "fees": r["fees"],
                     "traded": r["traded"]})
    bl = run_policy(bars, baseline(base), base, cfg, lim, warm, end)
    gap_usd = bl["eq_end"] - bl["bench_end"]
    attr = {a: {"book": bl["contrib"][a], "hold": bl["bench_contrib"][a],
                "diff": bl["contrib"][a] - bl["bench_contrib"][a]}
            for a in sorted(bars.close)}
    explained = sum(v["diff"] for v in attr.values())
    sens = {}
    for pen in (0.0, 5.0, 20.0):
        c2 = {**cfg, "fill_penetration_bps": pen}
        sens[f"penetration_{pen:g}bps"] = run_policy(
            bars, baseline(base), base, c2, lim, warm, end)["log_gap"]
    sens["ramp_from_cash"] = run_policy(
        bars, baseline(base), base, {**cfg, "seed_at_target": False}, lim,
        warm, end)["log_gap"]
    beat = sum(1 for r in rows if r["log_gap"] > 0)
    return {"unit": "idea (full-period run)", "n": len(rows), "ideas": rows,
            "beat_hold": beat, "baseline": {
                "log_gap": bl["log_gap"], "gap_usd": gap_usd,
                "fees_usd": bl["fees"], "traded_usd": bl["traded"],
                "fills": bl["fills"], "attempts": bl["attempts"],
                "attribution": attr, "attribution_residual_usd": gap_usd - explained},
            "sensitivity_log_gap": sens}


# ============================================================ 2 walk-forward
def excess_matrix(bars, base, cfg, lim, warm) -> tuple:
    end = len(bars) - 1
    fam = family(cfg)
    cols = []
    for idea in fam:
        r = run_policy(bars, idea, base, cfg, lim, warm, end)
        cols.append(r["rets"] - r["bench"])
    return fam, np.array(cols).T                      # (T, N)


def walk_forward(bars, base, cfg, lim, warm) -> dict:
    fam, E = excess_matrix(bars, base, cfg, lim, warm)
    T = E.shape[0]
    t0 = int(T * TRAIN_FRAC)
    edges = np.linspace(t0, T, N_FOLDS + 1).astype(int)
    folds = []
    for k in range(N_FOLDS):
        a, b = int(edges[k]), int(edges[k + 1])
        if b - a < 2:
            continue
        pick = int(np.argmax(E[:a].mean(axis=0)))
        sel = run_policy(bars, fam[pick], base, cfg, lim, warm + a, warm + b)
        bl = run_policy(bars, baseline(base), base, cfg, lim, warm + a, warm + b)
        folds.append({"fold": k, "train_steps": a, "test_steps": b - a,
                      "picked": fam[pick].id,
                      "picked_is_mean_excess_bps": float(E[:a, pick].mean() * 1e4),
                      "oos_log_gap_selected": sel["log_gap"],
                      "oos_log_gap_baseline": bl["log_gap"]})
    sel = np.array([f["oos_log_gap_selected"] for f in folds])
    bas = np.array([f["oos_log_gap_baseline"] for f in folds])
    try:
        from ml.overfit import pbo_cscv
        pbo = pbo_cscv(E, n_blocks=8).get("pbo")
    except Exception as exc:  # noqa: BLE001 - report the gap, never guess
        pbo = f"unavailable: {exc}"
    return {"unit": "fold (out-of-sample only)", "n": len(folds), "folds": folds,
            "selected_beats_hold": int((sel > 0).sum()),
            "baseline_beats_hold": int((bas > 0).sum()),
            "selected_beats_baseline": int((sel > bas).sum()),
            "sign_p_selected": _binom_two_sided(int((sel > 0).sum()), len(sel)),
            "mean_oos_gap_selected": float(sel.mean()) if len(sel) else None,
            "mean_oos_gap_baseline": float(bas.mean()) if len(bas) else None,
            "pbo_cscv_8": pbo, "pbo_unit": f"{E.shape[1]} ideas x {T} steps"}


def _binom_two_sided(k: int, n: int) -> float | None:
    if n == 0:
        return None
    pk = [math.comb(n, i) * 0.5 ** n for i in range(n + 1)]
    return float(min(1.0, sum(p for p in pk if p <= pk[k] + 1e-15)))


# =============================================================== 3 brownian
def variance_ratio(x: np.ndarray, q: int) -> tuple:
    """Lo-MacKinlay (1988) VR(q) on a return series with the
    heteroskedasticity-robust z*. VR > 1 trending, < 1 mean-reverting."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 2 * q + 2:
        return float("nan"), float("nan")
    mu = x.mean()
    d = x - mu
    v1 = (d ** 2).sum() / (n - 1)
    m = q * (n - q + 1) * (1 - q / n)
    sq = np.convolve(x, np.ones(q), "valid")
    vq = ((sq - q * mu) ** 2).sum() / m
    vr = vq / v1
    den = (d ** 2).sum() ** 2
    theta = 0.0
    for j in range(1, q):
        delta = (d[j:] ** 2 * d[:-j] ** 2).sum() * n / den
        theta += (2 * (q - j) / q) ** 2 * delta
    z = (vr - 1) / math.sqrt(theta / n) if theta > 0 else float("nan")
    return float(vr), float(z)


def vr_table(bars: Bars) -> list:
    R = log_returns(bars)
    names = sorted(bars.close)
    out = []
    series = [(a, R[:, k]) for k, a in enumerate(names)]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            series.append((f"{names[i]}/{names[j]}", R[:, i] - R[:, j]))
    for nm, s in series:
        row = {"series": nm}
        for q in VR_Q:
            vr, z = variance_ratio(s, q)
            row[f"vr{q}"], row[f"z{q}"] = vr, z
        out.append(row)
    return out


def _bridge_extremes(x: np.ndarray, s2: np.ndarray, rng) -> tuple:
    """Exact max/min of a Brownian bridge from 0 to x with variance s2 over
    the bar (in log space), sampled independently (the joint law is not
    used: an approximation stated here, not hidden)."""
    u1, u2 = rng.random(x.shape), rng.random(x.shape)
    mx = (x + np.sqrt(x * x - 2 * s2 * np.log(u1))) / 2
    mn = (x - np.sqrt(x * x - 2 * s2 * np.log(u2))) / 2
    return mx, mn


def gbm_bars(mu: np.ndarray, cov: np.ndarray, T: int, names: list, rng,
             p0: float = 100.0) -> Bars:
    L = np.linalg.cholesky(cov + 1e-18 * np.eye(len(mu)))
    X = mu + rng.standard_normal((T - 1, len(mu))) @ L.T
    mx, mn = _bridge_extremes(X, np.diag(cov)[None, :], rng)
    lp = np.vstack([np.zeros(len(mu)), np.cumsum(X, axis=0)]) + math.log(p0)
    c = np.exp(lp)
    hi = np.vstack([c[:1], np.exp(lp[:-1] + mx)])
    lo = np.vstack([c[:1], np.exp(lp[:-1] + mn)])
    return Bars(list(range(T)), {a: hi[:, k].tolist() for k, a in enumerate(names)},
                {a: lo[:, k].tolist() for k, a in enumerate(names)},
                {a: c[:, k].tolist() for k, a in enumerate(names)})


def shuffled_bars(bars: Bars, rng) -> Bars:
    """Same bars, time order permuted jointly across assets: keeps every
    bar's cross-section and intrabar range, destroys serial structure."""
    names = sorted(bars.close)
    c = np.array([bars.close[a] for a in names]).T
    h = np.array([bars.high[a] for a in names]).T
    lo = np.array([bars.low[a] for a in names]).T
    r = np.diff(np.log(c), axis=0)
    hr = np.log(h[1:] / c[:-1])
    lr = np.log(lo[1:] / c[:-1])
    perm = rng.permutation(len(r))
    r, hr, lr = r[perm], hr[perm], lr[perm]
    lp = np.vstack([np.log(c[:1]), np.log(c[:1]) + np.cumsum(r, axis=0)])
    nc = np.exp(lp)
    nh = np.vstack([h[:1], np.exp(lp[:-1] + hr)])
    nl = np.vstack([lo[:1], np.exp(lp[:-1] + lr)])
    return Bars(list(bars.t), {a: nh[:, k].tolist() for k, a in enumerate(names)},
                {a: nl[:, k].tolist() for k, a in enumerate(names)},
                {a: nc[:, k].tolist() for k, a in enumerate(names)})


def null_position(real: float, null: list) -> dict:
    a = np.asarray(null, float)
    lo = float((a <= real).mean())
    return {"real": real, "null_mean": float(a.mean()),
            "null_p05": float(np.quantile(a, 0.05)),
            "null_p95": float(np.quantile(a, 0.95)),
            "percentile": lo, "p_two_sided": float(min(1.0, 2 * min(lo, 1 - lo + 1 / len(a)))),
            "n_paths": len(a)}


def constant_mix_numpy(R: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Frictionless constant-mix wealth path from log returns (reference)."""
    gross = np.exp(R)
    out = [1.0]
    for g in gross:
        out.append(out[-1] * (w @ g + (1 - w.sum())))
    return np.array(out)


def constant_mix_plan(R: np.ndarray, w: np.ndarray, names: list,
                      lam_bps: float = 0.0, gamma: float = 3.0,
                      band_mult: float = 0.0, start: float = 1.0) -> np.ndarray:
    """The same, driven by core.target_book.plan(): fills at the decision
    close, fee lam on every fill. band_mult=0 -> rebalance every bar."""
    params = BookParams(gamma=gamma, aim_rate=1.0, tilt_cap=0.0,
                        invest_frac=float(w.sum()), min_order_usd=0.0,
                        maker_fee_bps=lam_bps)
    lam = lam_bps / 1e4
    px = {a: 1.0 for a in names}
    units = {a: 0.0 for a in names}
    cash = start
    tgt = {a: float(w[k]) for k, a in enumerate(names)}
    path = []
    pr = Pressure(band_mult=band_mult)
    for t in range(len(R) + 1):
        if t > 0:
            for k, a in enumerate(names):
                px[a] *= math.exp(R[t - 1, k])
        p = plan(units, cash, px, tgt, params, pr)
        for o in p.orders:
            q = o.notional_usd / px[o.asset]
            if o.side == "sell":
                q = min(q, units[o.asset])
                units[o.asset] -= q
                cash += q * px[o.asset] * (1 - lam)
            else:
                cost = q * px[o.asset] * (1 + lam)
                if cost > cash:
                    q, cost = cash / (px[o.asset] * (1 + lam)), cash
                units[o.asset] += q
                cash -= cost
        path.append(cash + sum(units[a] * px[a] for a in names))
    return np.array(path)


def theory_checks(bars: Bars, base: BookParams, cfg: dict, n_paths: int,
                  rng) -> dict:
    names = sorted(bars.close)
    R = log_returns(bars)
    mu, cov = R.mean(axis=0), np.cov(R.T)
    A = len(names)
    w = np.full(A, base.invest_frac / A)
    # (i) plan() == constant mix, exactly, on the REAL path
    ref = constant_mix_numpy(R, w)
    via = constant_mix_plan(R, w, names)
    plan_err = float(np.max(np.abs(via / ref - 1)))
    # (ii) constant-mix growth vs analytic diversification return (GBM)
    T = len(R)
    g_sim = []
    for _ in range(n_paths):
        X = mu + rng.standard_normal((T, A)) @ np.linalg.cholesky(cov).T
        g_sim.append(math.log(constant_mix_numpy(X, w)[-1]) / T)
    g_sim = np.array(g_sim)
    var_i = np.diag(cov)
    g_theory = float(w @ (mu + var_i / 2) - 0.5 * w @ cov @ w)
    se = float(g_sim.std(ddof=1) / math.sqrt(len(g_sim)))
    div_ret = float(0.5 * (w @ var_i - w @ cov @ w))
    # Rebalancing beats holding only while the diversification return
    # exceeds the drift spread holding drifts into (best asset's log drift
    # minus the basket-weighted log drift).
    drift_spread = float(mu.max() - (w / w.sum()) @ mu)
    # (iii) band sweep under the band's own model: Merton-consistent drift
    gamma = base.gamma
    lam_bps = 50.0
    drift = gamma * cov @ w                       # arithmetic excess, per bar
    mu_m = drift - var_i / 2
    ce = {m: [] for m in BAND_MULTS}
    for _ in range(max(n_paths // 2, 20)):
        X = mu_m + rng.standard_normal((T, A)) @ np.linalg.cholesky(cov).T
        for m in BAND_MULTS:
            path = constant_mix_plan(X, w, names, lam_bps, gamma, m)
            ce[m].append(path[-1])
    U = {m: np.array(v) for m, v in ce.items()}
    crra = {m: float((np.mean(v ** (1 - gamma))) ** (1 / (1 - gamma)))
            for m, v in U.items()}
    best = max(crra, key=lambda k: crra[k])
    # paired bootstrap: CE(1) vs CE(best) and vs CE(0)
    paired = {}
    idx = np.arange(len(U[1.0]))
    for m in BAND_MULTS:
        boots = []
        for _ in range(500):
            s = rng.choice(idx, len(idx))
            c1 = np.mean(U[1.0][s] ** (1 - gamma)) ** (1 / (1 - gamma))
            cm = np.mean(U[m][s] ** (1 - gamma)) ** (1 / (1 - gamma))
            boots.append(math.log(c1 / cm))
        paired[str(m)] = [float(np.quantile(boots, 0.025)),
                          float(np.quantile(boots, 0.975))]
    # (iv) state classifier false-positive rate under GBM
    win = int(cfg["reading_window_bars"])
    short = int(cfg["vol_short_bars"])
    states = []
    for _ in range(max(2000, n_paths * 10)):   # a rate needs a big n
        gb = gbm_bars(mu, cov, win + 2, names, rng)
        states.append(read_market(gb, win + 1, win, short, 1e9).state)
    fpr = 1 - states.count("neutral") / len(states)
    real_states = [read_market(bars, i, win, short, 1e9).state
                   for i in range(win + 1, len(bars), win)]
    return {"plan_vs_constant_mix_max_rel_err": plan_err,
            "growth_sim_per_bar": float(g_sim.mean()), "growth_sim_se": se,
            "growth_theory_per_bar": g_theory,
            "growth_z": (float(g_sim.mean()) - g_theory) / se if se else None,
            "diversification_return_per_bar": div_ret,
            "drift_spread_per_bar": drift_spread,
            "band_sweep": {"cost_bps": lam_bps, "gamma": gamma,
                           "ce_wealth": {str(k): v for k, v in crra.items()},
                           "best_mult": best,
                           "log_ce1_minus_ce_m_ci95": paired,
                           "paths": len(U[1.0])},
            "classifier_fpr_gbm": fpr, "classifier_fpr_expected": 0.0455,
            "classifier_n": len(states),
            "real_nonoverlap_state_share": {
                s: real_states.count(s) / len(real_states)
                for s in ("reverting", "trending", "neutral")} if real_states else {},
            "real_nonoverlap_n": len(real_states)}


def brownian(bars, base, cfg, lim, warm, n_paths, rng) -> dict:
    names = sorted(bars.close)
    R = log_returns(bars)
    mu, cov = R.mean(axis=0), np.cov(R.T)
    end = len(bars) - 1
    real = run_policy(bars, baseline(base), base, cfg, lim, warm, end)["log_gap"]
    g_null, s_null = [], []
    for _ in range(n_paths):
        gb = gbm_bars(mu, cov, len(bars), names, rng)
        g_null.append(run_policy(gb, baseline(base), base, cfg, lim, warm, end)["log_gap"])
        sb = shuffled_bars(bars, rng)
        s_null.append(run_policy(sb, baseline(base), base, cfg, lim, warm, end)["log_gap"])
    return {"unit": "baseline log(book/hold) at period end",
            "variance_ratios": vr_table(bars),
            "vs_gbm": null_position(real, g_null),
            "vs_time_shuffle": null_position(real, s_null),
            "theory": theory_checks(bars, base, cfg, n_paths, rng)}


# ================================================================== 4 markov
STATES = ("rev-lo", "rev-hi", "cont-lo", "cont-hi")


def bar_states(R: np.ndarray, lookback: int) -> tuple:
    """Per-bar state from data <= t only: reversal/continuation = sign of
    the dot product of this bar's and last bar's cross-sectional relative
    returns; hi/lo = this bar's mean |return| vs the trailing median."""
    rel = R - R.mean(axis=1, keepdims=True)
    act = np.abs(R).mean(axis=1)
    out, idx = [], []
    for t in range(max(lookback, 1), len(R)):
        d = "rev" if float(rel[t] @ rel[t - 1]) < 0 else "cont"
        v = "hi" if act[t] > np.median(act[t - lookback:t]) else "lo"
        out.append(f"{d}-{v}")
        idx.append(t)
    return out, idx


def transition(seq: list) -> tuple:
    k = {s: i for i, s in enumerate(STATES)}
    N = np.zeros((len(STATES), len(STATES)))
    for a, b in zip(seq[:-1], seq[1:], strict=True):
        N[k[a], k[b]] += 1
    return N


def g_stat(N: np.ndarray) -> float:
    """Likelihood-ratio G for 'next state independent of current'."""
    tot = N.sum()
    if tot == 0:
        return 0.0
    row = N.sum(axis=1, keepdims=True)
    col = N.sum(axis=0, keepdims=True)
    E = row @ col / tot
    m = N > 0
    return float(2 * (N[m] * np.log(N[m] / E[m])).sum())


def stationary(P: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eig(P.T)
    v = np.real(vecs[:, np.argmin(np.abs(vals - 1))])
    return v / v.sum()


def rebalance_payoff(R: np.ndarray, w: np.ndarray) -> np.ndarray:
    """g[t+1] = constant-mix return - drifted-weights return over bar t+1,
    after bar t moved the weights. > 0 when undoing bar t's move paid."""
    S = np.exp(R) - 1
    out = np.full(len(R), np.nan)
    for t in range(len(R) - 1):
        wd = w * (1 + S[t])
        wd = wd / (wd.sum() + (1 - w.sum()))
        out[t + 1] = float(w @ S[t + 1] - wd @ S[t + 1])
    return out


def markov(bars, base, cfg, n_paths, rng) -> dict:
    names = sorted(bars.close)
    R = log_returns(bars)
    lb = int(cfg["vol_short_bars"]) * 4
    seq, idx = bar_states(R, lb)
    N = transition(seq)
    P = N / np.maximum(N.sum(axis=1, keepdims=True), 1)
    pi = stationary(P)
    G = g_stat(N)
    perm = []
    arr = np.array(seq)
    for _ in range(2000):
        perm.append(g_stat(transition(list(rng.permutation(arr)))))
    mu, cov = R.mean(axis=0), np.cov(R.T)
    gbm = []
    for _ in range(n_paths):
        X = mu + rng.standard_normal(R.shape) @ np.linalg.cholesky(cov).T
        gbm.append(g_stat(transition(bar_states(X, lb)[0])))
    w = np.full(len(names), base.invest_frac / len(names))
    pay = rebalance_payoff(R, w)
    by = {}
    for s in STATES:
        v = np.array([pay[t + 1] for k, t in enumerate(idx)
                      if seq[k] == s and t + 1 < len(pay)])
        v = v[np.isfinite(v)]
        if len(v) < 5:
            by[s] = {"n": len(v)}
            continue
        boots = [rng.choice(v, len(v)).mean() for _ in range(2000)]
        by[s] = {"n": len(v), "mean_bps": float(v.mean() * 1e4),
                 "ci95_bps": [float(np.quantile(boots, 0.025) * 1e4),
                              float(np.quantile(boots, 0.975) * 1e4)]}
    rev = np.array([pay[t + 1] for k, t in enumerate(idx)
                    if seq[k].startswith("rev") and t + 1 < len(pay)])
    cont = np.array([pay[t + 1] for k, t in enumerate(idx)
                     if seq[k].startswith("cont") and t + 1 < len(pay)])
    rev, cont = rev[np.isfinite(rev)], cont[np.isfinite(cont)]
    diff = float(rev.mean() - cont.mean()) if len(rev) and len(cont) else float("nan")
    pool = np.concatenate([rev, cont])
    dn = []
    for _ in range(2000):
        p = rng.permutation(pool)
        dn.append(p[:len(rev)].mean() - p[len(rev):].mean())
    p_diff = float((np.abs(dn) >= abs(diff)).mean()) if math.isfinite(diff) else None
    # the lab's own rolling-window states: persistence vs GBM null
    win = int(cfg["reading_window_bars"])
    short = int(cfg["vol_short_bars"])

    def stay_rate(b: Bars) -> float:
        st = [read_market(b, i, win, short, 1e9).state
              for i in range(win + 1, len(b))]
        return float(np.mean([x == y for x, y in zip(st[:-1], st[1:], strict=True)]))
    lab_real = stay_rate(bars)
    lab_null = [stay_rate(gbm_bars(mu, cov, len(bars), names, rng))
                for _ in range(max(n_paths // 10, 10))]
    return {"unit": "bar (state at t -> t+1)", "n_transitions": int(N.sum()),
            "states": list(STATES), "counts": N.tolist(), "P": P.tolist(),
            "stationary": dict(zip(STATES, pi.tolist(), strict=True)),
            "dwell_bars": {s: (1 / (1 - P[i, i]) if P[i, i] < 1 else None)
                           for i, s in enumerate(STATES)},
            "memory_G": G, "memory_vs_permutation": null_position(G, perm),
            "memory_vs_gbm": null_position(G, gbm),
            "rebalance_payoff_by_state": by,
            "rev_minus_cont_bps": diff * 1e4, "rev_minus_cont_p": p_diff,
            "lab_state_stay_rate_real": lab_real,
            "lab_state_stay_rate_gbm": null_position(lab_real, lab_null)}


# ================================================================== 5 ledger
def ledger(res: dict) -> list:
    rows = []

    def add(aid, claim, test, verdict, evidence):
        rows.append({"id": aid, "claim": claim, "test": test,
                     "verdict": verdict, "evidence": evidence})
    for iv, r in res.items():
        th = r["brownian"]["theory"]
        bt, wf, br, mk = r["backtest"], r["walk_forward"], r["brownian"], r["markov"]
        tag = f"[{iv}]"
        add(f"A1{tag}", "plan() implements constant-mix rebalancing",
            "plan()-driven frictionless path vs numpy constant-mix, real path",
            "PROVEN" if th["plan_vs_constant_mix_max_rel_err"] < 1e-9 else "REFUTED",
            f"max rel err {th['plan_vs_constant_mix_max_rel_err']:.2e}")
        z = th["growth_z"]
        add(f"A2{tag}", "constant-mix growth = sum w(mu+s2/2) - w'Sw/2 (GBM)",
            "simulated mean log growth vs analytic",
            "PROVEN" if z is not None and abs(z) < 3 else "REFUTED",
            f"z={z:+.2f}; diversification return {th['diversification_return_per_bar']*1e4:.2f} bps/bar")
        bs = th["band_sweep"]
        ci = bs["log_ce1_minus_ce_m_ci95"]
        worse = [m for m, (lo, hi) in ci.items() if hi < 0]
        add(f"A3{tag}", "Janecek-Shreve band width is near-optimal",
            f"CRRA CE over band x{list(BAND_MULTS)} at {bs['cost_bps']:g} bps, paired bootstrap",
            "REFUTED" if worse else "NOT REFUTED",
            f"best x{bs['best_mult']}; widths whose CE beats x1 with CI>0: {worse or 'none'}")
        f = th["classifier_fpr_gbm"]
        add(f"A4{tag}", "state classifier fires ~4.6% on pure noise (self-normalised 2-sigma cut)",
            f"GBM, n={th['classifier_n']}",
            "PROVEN" if abs(f - 0.0455) < 2.5 * math.sqrt(0.0455 * 0.9545 / th["classifier_n"]) + 0.01
            else "REFUTED", f"FPR {f:.3f} (n={th['classifier_n']})")
        add(f"A15{tag}", "holding beats rebalancing here because the drift spread exceeds the diversification return",
            "best-asset log drift minus basket drift vs 1/2(sum w s2 - w'Sw), per bar",
            "PROVEN" if th["drift_spread_per_bar"] > th["diversification_return_per_bar"]
            and bt["baseline"]["log_gap"] < 0 else "NOT PROVEN",
            f"spread {th['drift_spread_per_bar']*1e4:.2f} vs diversification "
            f"{th['diversification_return_per_bar']*1e4:.2f} bps/bar; baseline gap {bt['baseline']['log_gap']:+.3f}")
        b = bt["baseline"]
        worst = min(b["attribution"].items(), key=lambda kv: kv[1]["diff"])
        add(f"A5{tag}", "the book's gap to holding comes from rebalancing against the trend (selling winners / buying losers)",
            "per-asset P&L attribution, book vs hold",
            "SUPPORTED" if b["gap_usd"] < 0 and worst[1]["diff"] < 0
            and abs(b["attribution_residual_usd"]) < 0.2 * abs(b["gap_usd"]) else "NOT SUPPORTED",
            f"gap ${b['gap_usd']:+.2f}; largest drag {worst[0]} ${worst[1]['diff']:+.2f}; "
            f"residual ${b['attribution_residual_usd']:+.2f}")
        add(f"A6{tag}", "fees are not what loses money in the book",
            "fees vs |gap|", "PROVEN" if b["fees_usd"] < 0.2 * abs(b["gap_usd"]) else "NOT PROVEN",
            f"fees ${b['fees_usd']:.2f} vs gap ${b['gap_usd']:+.2f}")
        sens = bt["sensitivity_log_gap"]
        signs = {k: v > 0 for k, v in sens.items()}
        add(f"A7{tag}", "conclusions do not depend on the fill model or on seeding",
            "baseline gap at penetration 0/5/20 bps and ramp-from-cash",
            "PROVEN" if len(set(signs.values())) == 1 else "REFUTED",
            ", ".join(f"{k} {v:+.3f}" for k, v in sens.items()))
        sh = br["vs_time_shuffle"]
        add(f"A8{tag}", "time ORDER (trend/reversion) decided the rebalancing result",
            "real vs time-shuffled history",
            "PROVEN" if sh["p_two_sided"] < ALPHA else "NOT PROVEN",
            f"real {sh['real']:+.3f}, shuffle 90% [{sh['null_p05']:+.3f}, {sh['null_p95']:+.3f}], p={sh['p_two_sided']:.3f}")
        gb = br["vs_gbm"]
        add(f"A9{tag}", "the real result is consistent with a correlated random walk",
            "real vs GBM fitted to the same data",
            "CONSISTENT" if gb["p_two_sided"] >= ALPHA else "INCONSISTENT",
            f"percentile {gb['percentile']:.2f}, p={gb['p_two_sided']:.3f}")
        add(f"A10{tag}", "walk-forward selection adds value over the fixed baseline",
            f"{wf['n']} OOS folds, PBO",
            "SUPPORTED" if wf["selected_beats_baseline"] > wf["n"] / 2
            and isinstance(wf["pbo_cscv_8"], float) and wf["pbo_cscv_8"] < 0.5
            else "NOT SUPPORTED",
            f"selected>baseline {wf['selected_beats_baseline']}/{wf['n']}, "
            f"PBO {wf['pbo_cscv_8']}")
        mg = mk["memory_vs_gbm"]
        add(f"A11{tag}", "bar states have memory beyond a random walk (Markov)",
            "G-statistic vs GBM null built the same way",
            "PROVEN" if mg["p_two_sided"] < ALPHA else "NOT PROVEN",
            f"G={mk['memory_G']:.1f}, GBM p={mg['p_two_sided']:.3f}, "
            f"permutation p={mk['memory_vs_permutation']['p_two_sided']:.3f}")
        add(f"A12{tag}", "a reversal state predicts a better next-bar rebalancing payoff",
            "rev vs cont next-bar payoff, permutation",
            "PROVEN" if mk["rev_minus_cont_p"] is not None and mk["rev_minus_cont_p"] < ALPHA
            and mk["rev_minus_cont_bps"] > 0 else "NOT PROVEN",
            f"rev-cont {mk['rev_minus_cont_bps']:+.2f} bps, p={mk['rev_minus_cont_p']}")
        ls = mk["lab_state_stay_rate_gbm"]
        add(f"A13{tag}", "the lab's state changes are market signal, not window overlap",
            "rolling-state stay rate vs GBM null",
            "PROVEN" if ls["p_two_sided"] < ALPHA else "NOT PROVEN (persistence is mechanical)",
            f"real stay {ls['real']:.3f}, GBM mean {ls['null_mean']:.3f}, p={ls['p_two_sided']:.3f}")
        vr = br["variance_ratios"]
        pairs = [v for v in vr if "/" in v["series"]]
        sig_rev = [v["series"] for v in pairs if v["z4"] < -1.96]
        sig_trd = [v["series"] for v in pairs if v["z4"] > 1.96]
        add(f"A14{tag}", "relative prices mean-revert (the premise of rebalancing)",
            "Lo-MacKinlay VR(4) z* on each pair ratio",
            "PROVEN" if sig_rev and not sig_trd else "NOT PROVEN",
            f"reverting {sig_rev or 'none'}; trending {sig_trd or 'none'}")
    return rows


# ==================================================================== main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--intervals", default="1440,10080")
    ap.add_argument("--paths", type=int, default=200)
    ap.add_argument("--csv-root", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    cfg_full = json.loads(Path(args.config).read_text(encoding="utf-8"))
    base, lim, cfg = params_from(cfg_full)
    out_dir = Path(args.out) if args.out else default_out_dir()
    rng = np.random.default_rng(SEED)
    res = {}
    for iv in [int(x) for x in args.intervals.split(",")]:
        bars = load_bars(cfg_full, iv,
                         Path(args.csv_root) if args.csv_root else None, out_dir)
        warm = int(cfg["sigma_lookback_bars"])
        t0 = time.time()
        res[f"{iv}m"] = {
            "bars": len(bars), "span_days": (bars.t[-1] - bars.t[0]) / 86400,
            "backtest": backtest(bars, base, cfg, lim, warm),
            "walk_forward": walk_forward(bars, base, cfg, lim, warm),
            "brownian": brownian(bars, base, cfg, lim, warm, args.paths, rng),
            "markov": markov(bars, base, cfg, args.paths, rng),
            "secs": None}
        res[f"{iv}m"]["secs"] = time.time() - t0
    led = ledger(res)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = out_dir / f"validation_{stamp}.json"
    path.write_text(json.dumps({"registered": {
        "alpha": ALPHA, "seed": SEED, "vr_q": VR_Q, "band_mults": BAND_MULTS,
        "folds": N_FOLDS, "train_frac": TRAIN_FRAC, "paths": args.paths},
        "results": res, "ledger": led}, indent=1, default=_json),
        encoding="utf-8")
    _print(res, led)
    print(f"wrote {path}")
    return 0


def _json(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return str(o)


def _print(res: dict, led: list) -> None:
    for iv, r in res.items():
        bt, wf, br, mk = r["backtest"], r["walk_forward"], r["brownian"], r["markov"]
        b = bt["baseline"]
        print(f"\n=== {iv}: {r['bars']} bars, {r['span_days']:.0f} days ===")
        print(f"[1 BACKTEST] unit={bt['unit']} n={bt['n']}: {bt['beat_hold']} beat holding; "
              f"baseline log gap {b['log_gap']:+.3f} (${b['gap_usd']:+.2f}), fees ${b['fees_usd']:.2f}, "
              f"fills {b['fills']}/{b['attempts']}")
        for a, v in b["attribution"].items():
            print(f"    {a:<5} book ${v['book']:+8.2f}  hold ${v['hold']:+8.2f}  diff ${v['diff']:+8.2f}")
        print(f"    residual (trading/fees not in the per-asset sum) ${b['attribution_residual_usd']:+.2f}")
        print("    sensitivity: " + ", ".join(f"{k} {v:+.3f}" for k, v in bt["sensitivity_log_gap"].items()))
        print(f"[2 WALK-FORWARD] unit={wf['unit']} n={wf['n']}: selected beats hold "
              f"{wf['selected_beats_hold']}/{wf['n']} (sign p={wf['sign_p_selected']}), "
              f"beats baseline {wf['selected_beats_baseline']}/{wf['n']}; PBO={wf['pbo_cscv_8']} ({wf['pbo_unit']})")
        for f in wf["folds"]:
            print(f"    fold {f['fold']} train {f['train_steps']} test {f['test_steps']}: "
                  f"{f['picked']:<32} OOS {f['oos_log_gap_selected']:+.3f}  baseline {f['oos_log_gap_baseline']:+.3f}")
        print("[3 BROWNIAN] variance ratios (z* at q=4; |z|>1.96 rejects random walk):")
        for v in br["variance_ratios"]:
            print(f"    {v['series']:<10} VR2 {v['vr2']:.2f} VR4 {v['vr4']:.2f} (z {v['z4']:+.2f}) "
                  f"VR16 {v['vr16']:.2f} (z {v['z16']:+.2f})")
        for k in ("vs_gbm", "vs_time_shuffle"):
            n = br[k]
            print(f"    {k}: real {n['real']:+.3f}, null mean {n['null_mean']:+.3f} "
                  f"[{n['null_p05']:+.3f}, {n['null_p95']:+.3f}], pct {n['percentile']:.2f}, "
                  f"p={n['p_two_sided']:.3f} (n={n['n_paths']})")
        th = br["theory"]
        print(f"    theory: plan()==constant-mix err {th['plan_vs_constant_mix_max_rel_err']:.1e}; "
              f"growth sim {th['growth_sim_per_bar']*1e4:.2f} vs theory "
              f"{th['growth_theory_per_bar']*1e4:.2f} bps/bar (z {th['growth_z']:+.2f}); "
              f"classifier FPR {th['classifier_fpr_gbm']:.3f} (expect 0.046)")
        bs = th["band_sweep"]
        print(f"    band sweep @{bs['cost_bps']:g}bps gamma {bs['gamma']}: best x{bs['best_mult']}; "
              + ", ".join(f"x{m}: CI[{lo*1e4:+.1f},{hi*1e4:+.1f}]bp" for m, (lo, hi)
                          in bs["log_ce1_minus_ce_m_ci95"].items()))
        print(f"[4 MARKOV] unit={mk['unit']} n={mk['n_transitions']}  stationary "
              + ", ".join(f"{s} {p:.2f}" for s, p in mk["stationary"].items()))
        for i, s in enumerate(mk["states"]):
            print(f"    {s:<8} -> " + " ".join(f"{p:.2f}" for p in mk["P"][i])
                  + f"   dwell {mk['dwell_bars'][s]:.2f} bars")
        print(f"    memory G={mk['memory_G']:.1f}: permutation p={mk['memory_vs_permutation']['p_two_sided']:.3f}, "
              f"GBM p={mk['memory_vs_gbm']['p_two_sided']:.3f}")
        for s, v in mk["rebalance_payoff_by_state"].items():
            if "mean_bps" in v:
                print(f"    next-bar rebalance payoff | {s:<8} n={v['n']:<4} {v['mean_bps']:+.2f} bps "
                      f"CI [{v['ci95_bps'][0]:+.2f}, {v['ci95_bps'][1]:+.2f}]")
        print(f"    rev - cont {mk['rev_minus_cont_bps']:+.2f} bps, p={mk['rev_minus_cont_p']}")
        ls = mk["lab_state_stay_rate_gbm"]
        print(f"    lab rolling-state stay rate: real {ls['real']:.3f} vs GBM {ls['null_mean']:.3f} "
              f"[{ls['null_p05']:.3f}, {ls['null_p95']:.3f}]")
    print("\n[5 ASSUMPTION LEDGER]")
    for r in led:
        print(f"  {r['id']:<12} {r['verdict']:<36} {r['claim']}\n{'':15}{r['evidence']}")


if __name__ == "__main__":
    raise SystemExit(main())
