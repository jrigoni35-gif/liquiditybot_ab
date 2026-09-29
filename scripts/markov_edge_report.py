"""scripts/markov_edge_report.py - walk-forward test of the Markov-modulated
Brownian edge model (ml/markov_edge.py). REPORT-ONLY: reads
outputs/signal_history.csv, writes nothing, decides nothing.

QUESTION. Do market states, built from the bot's own weak directional signals
and chained by a Markov transition matrix, carry a Brownian drift that moves
the barrier-win probability past the fair-game break-even p* = (b + C)/(a + b)
out of sample?

PRE-REGISTERED 2026-09-29, before the first run (changing any of this after
seeing output is a new registration and must say so):
  corpus   triple-barrier candidate rows (source != live), label_era
           triple_barrier*, signal_ts >= ERA9_START (cut #12 restart).
  specs    SPECS below - 6 state definitions, reported ALL, never the best
           alone. 6 specs x 2 variants = 12 tests: a single p < 0.05 is
           expected by chance ~0.6 times.
  folds    one UTC day per test fold; train = rows whose label had fully
           resolved before the test day began (signal_ts < day_start - H,
           H = ml.label_max_bars x 300 s): the purge. Bin edges, drifts and
           the transition matrix are fitted on train rows only.
           MIN_TRAIN_DAYS distinct train days before a day is tested.
  prior    PRIOR_N = 50 driftless pseudo-observations per state.
  chain    hold length k (in candidate steps, per asset) = driftless
           expected exit time E[tau] = (a/sigma)(b/sigma) bars, capped at the
           vertical, divided by the asset's median train candidate gap.
           variant "static" = k 1 (state drift only); "chain" = k above.
  metric   (1) calibration: mean per-day log-loss GAIN of P(up first) over
           the driftless fair game (psi = 0), resolved rows only.
           (2) decision: per-day mean realised label return of rows the rule
           takes (EV > 0 for the row's own side) minus the day's mean over
           all rows. Realised returns are net of the label cost and include
           time-outs.
           Day-block bootstrap CI (BOOT reps); within-day state-permutation
           null (NULL_REPS reps) for the calibration gain.
  AMENDMENT 2026-09-29, added AFTER run 1 and labelled as such: run 1 showed
           the per-day share of up-first outcomes swinging 0.005..0.96 (the
           assets trend together), so metric (1) is dominated by an
           unpredictable day LEVEL. Metric (3) separates it: mean per-day
           AUC of the row's predicted drift vs up-first (resolved rows) -
           does the state RANK outcomes within a day. 0.5 = no information.
           Same null and CI machinery.
  counting CS-1: every corpus row lands in exactly one bucket.

Usage:  python scripts/markov_edge_report.py [--history PATH] [--json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.cohort import COUNTING_STANDARD, reconcile  # noqa: E402
from ml import markov_edge as me  # noqa: E402

ERA9_START = 1788911265.0      # cut #12 runner restart 2026-09-08T23:47:45Z
BAR_SEC = 300.0                # 5-minute bars (ml.label_max_bars is in bars)
MIN_TRAIN_DAYS = 7
PRIOR_N = 50.0
ALPHA = 1.0                    # Dirichlet smoothing of transitions
BOOT = 2000
NULL_REPS = 200
SEED = 7
REGIMES = ["regime_bull_quiet", "regime_bull_vol", "regime_range",
           "regime_bear", "regime_crisis"]


def _f(x, default=None):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if np.isfinite(v) else default


def _label_horizon_sec() -> float:
    try:
        cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        return float(cfg["ml"]["label_max_bars"]) * BAR_SEC
    except (OSError, KeyError, TypeError, ValueError):
        return 432 * BAR_SEC


def load(path: Path) -> tuple[dict, dict]:
    """Corpus arrays + CS-1 drop buckets. Market-absolute features are the
    side-relative *_dir features times the side (ml/features.py dir_sign)."""
    drops = {"not_candidate_tb": 0, "pre_era9": 0, "unparseable": 0}
    cols: dict[str, list] = {k: [] for k in (
        "ts", "asset", "side", "up_first", "resolved", "r", "pt", "sl",
        "cost", "ret", "sigma", "basis", "disloc", "regime")}
    n_read = 0
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            n_read += 1
            if row.get("source") == "live" or not (
                    row.get("label_era") or "").startswith("triple_barrier"):
                drops["not_candidate_tb"] += 1
                continue
            ts = _f(row.get("signal_ts"))
            side = _f(row.get("direction"))
            pt, sl = _f(row.get("pt_frac")), _f(row.get("sl_frac"))
            ret = _f(row.get("label_ret_pct"))
            sig = _f(row.get("sigma_bar_pct"))
            bar = row.get("barrier") or ""
            if ts is not None and ts < ERA9_START:
                drops["pre_era9"] += 1
                continue
            if (ts is None or side not in (1.0, -1.0) or not pt or not sl
                    or pt <= 0 or sl <= 0 or ret is None or not sig
                    or bar not in ("tb_pt", "tb_sl", "tb_time")):
                drops["unparseable"] += 1
                continue
            s = int(side)
            # market "up first": a long's target / a short's stop is up
            up_first = (bar == "tb_pt") == (s > 0)
            up_d, dn_d = (pt, sl) if s > 0 else (sl, pt)
            # label cost, recovered exactly from resolved rows
            # (ml/labeling.triple_barrier: ret = +-barrier*100 - cost_pct)
            cost = (pt * 100 - ret if bar == "tb_pt" else
                    -sl * 100 - ret if bar == "tb_sl" else np.nan)
            reg = [_f(row.get(c), 0.0) for c in REGIMES]
            cols["ts"].append(ts)
            cols["asset"].append(row.get("asset") or "")
            cols["side"].append(s)
            cols["up_first"].append(1.0 if up_first else 0.0)
            cols["resolved"].append(bar != "tb_time")
            cols["r"].append(dn_d / (up_d + dn_d))
            cols["pt"].append(pt)
            cols["sl"].append(sl)
            cols["cost"].append(cost / 100.0)
            cols["ret"].append(ret / 100.0)
            cols["sigma"].append(sig / 100.0)
            cols["basis"].append(s * _f(row.get("basis_dir"), 0.0))
            cols["disloc"].append(s * _f(row.get("venue_disloc_dir"), 0.0))
            cols["regime"].append(int(np.argmax(reg)) if max(reg) > 0 else -1)
    data = {k: np.asarray(v) for k, v in cols.items()}
    data["day"] = (data["ts"] // 86400).astype(int)
    drops["n_read"] = n_read
    return data, drops


# ---- state specs: fn(data, train_mask) -> (state int array, n_states) ----
def _terciles(x, train):
    lo, hi = np.quantile(x[train], [1 / 3, 2 / 3])
    return np.digitize(x, [lo, hi]) if hi > lo else np.zeros(len(x), int)


def _basis(d, tr):
    return _terciles(d["basis"], tr), 3


def _disloc(d, tr):
    # 0 = dislocation unavailable/zero (about half the corpus), 1 below,
    # 2 above - a sign, not a fitted cut
    x = d["disloc"]
    return np.where(x == 0, 0, np.where(x < 0, 1, 2)), 3


def _hmm(d, tr):
    # the macro engine's own Markov-switching regime (regime/macro_regime),
    # one-hot on every row; -1 (none) folds into its own state
    return d["regime"] + 1, len(REGIMES) + 1


def _pooled(d, tr):
    return np.zeros(len(d["ts"]), int), 1


def _cross(f, g):
    def spec(d, tr):
        a, na = f(d, tr)
        b, nb = g(d, tr)
        return a * nb + b, na * nb
    return spec


SPECS = {
    "pooled": _pooled,
    "hmm": _hmm,
    "basis": _basis,
    "disloc": _disloc,
    "basis_x_disloc": _cross(_basis, _disloc),
    "hmm_x_basis": _cross(_hmm, _basis),
}


def _sequences(d, states, mask):
    """Per-asset state sequences in time order, one entry per distinct
    signal_ts (a long/short pair at one instant is one market state)."""
    out = []
    for a in np.unique(d["asset"][mask]):
        ix = np.where(mask & (d["asset"] == a))[0]
        ix = ix[np.argsort(d["ts"][ix], kind="stable")]
        _, first = np.unique(d["ts"][ix], return_index=True)
        out.append((a, ix[np.sort(first)]))
    return [(a, states[ix], d["ts"][ix]) for a, ix in out]


def _hold_steps(d, mask, seqs, horizon_sec) -> dict:
    """k per asset: E[tau] = (a/sigma)(b/sigma) bars (driftless BM expected
    exit time), capped at the vertical, over the median candidate gap."""
    k = {}
    for a, _, ts in seqs:
        m = mask & (d["asset"] == a)
        etau = np.median(np.minimum(
            d["pt"][m] * d["sl"][m] / d["sigma"][m] ** 2 * BAR_SEC,
            horizon_sec))
        gaps = np.diff(ts)
        gap = np.median(gaps[gaps > 0]) if np.any(gaps > 0) else horizon_sec
        k[a] = max(1, int(round(etau / gap)))
    return k


def train_mask(d, day: int, horizon_sec: float) -> np.ndarray:
    """Rows usable to fit a model tested on `day`: the label (at most
    horizon_sec after signal_ts) resolved before the test day began."""
    return d["ts"] < day * 86400.0 - horizon_sec


def _auc(score, y) -> float:
    """Mann-Whitney AUC with average ranks for ties; nan if one class."""
    pos, n1 = y == 1, int((y == 1).sum())
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty(len(score))
    sx = score[order]
    i = 0
    while i < len(sx):
        j = i
        while j + 1 < len(sx) and sx[j + 1] == sx[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def walk_forward(d, loglik, spec, rng=None, horizon_sec=None):
    """One walk-forward pass. Returns per-test-row arrays and per-day
    aggregates for both variants. `rng` set = permutation null: states are
    shuffled within each UTC day before anything is fitted."""
    horizon_sec = horizon_sec or _label_horizon_sec()
    days = np.unique(d["day"])
    sd = me.prior_sd(float(np.mean(d["r"])), PRIOR_N)
    res = {v: {"gain": [], "uplift": [], "auc": [], "taken": 0, "rows": 0}
           for v in ("static", "chain")}
    tested = np.zeros(len(d["ts"]), bool)
    for day in days:
        train = train_mask(d, day, horizon_sec)
        test = d["day"] == day
        if len(np.unique(d["day"][train])) < MIN_TRAIN_DAYS or not test.any():
            continue
        if (train & test).any():       # look-ahead is a bug, never a result
            raise RuntimeError(f"walk-forward look-ahead on day {day}")
        states, K = spec(d, train)
        if rng is not None:
            states = states.copy()
            for dd in np.unique(d["day"]):
                ix = np.where(d["day"] == dd)[0]
                states[ix] = rng.permutation(states[ix])
        fit = train & d["resolved"]
        psis = np.array([me.map_psi(loglik[fit & (states == s)], sd)
                         for s in range(K)])
        seqs = _sequences(d, states, train)
        A = me.transition_matrix([s for _, s, _ in seqs], K, ALPHA)
        ksteps = _hold_steps(d, train, seqs, horizon_sec)
        k_default = int(np.median(list(ksteps.values()))) if ksteps else 1
        cost_fill = float(np.nanmedian(d["cost"][train]))
        tix = np.where(test)[0]
        tested[tix] = True
        # chain drift depends only on (state, hold steps): one table per fold
        k_row = np.array([ksteps.get(a, k_default) for a in d["asset"][tix]])
        chain_tab = {(s, k): me.effective_psi(A, psis, s, k)
                     for s in range(K) for k in np.unique(k_row)}
        for variant in ("static", "chain"):
            psi_row = (psis[states[tix]] if variant == "static" else
                       np.array([chain_tab[(s, k)] for s, k in
                                 zip(states[tix], k_row, strict=True)]))
            # (1) calibration on resolved rows: P(up first)
            rmask = d["resolved"][tix]
            if rmask.any():
                p = np.clip(me.hit_prob(psi_row[rmask], d["r"][tix][rmask]),
                            1e-12, 1 - 1e-12)
                p0 = d["r"][tix][rmask]
                y = d["up_first"][tix][rmask]
                ll = y * np.log(p) + (1 - y) * np.log1p(-p)
                ll0 = y * np.log(p0) + (1 - y) * np.log1p(-p0)
                res[variant]["gain"].append(float(np.mean(ll - ll0)))
                a = _auc(psi_row[rmask], y)
                if a == a:
                    res[variant]["auc"].append(a)
            # (2) decision on all rows: take iff EV > 0 for the row's side
            side = d["side"][tix]
            r_side = d["sl"][tix] / (d["pt"][tix] + d["sl"][tix])
            p_side = me.hit_prob(np.where(side > 0, psi_row, -psi_row),
                                 r_side)
            cost = np.where(np.isnan(d["cost"][tix]), cost_fill,
                            d["cost"][tix])
            ev = me.expected_value(p_side, d["pt"][tix], d["sl"][tix], cost)
            take = ev > 0
            ret = d["ret"][tix]
            res[variant]["uplift"].append(
                float(ret[take].mean() - ret.mean()) if take.any() else 0.0)
            res[variant]["taken"] += int(take.sum())
            res[variant]["rows"] += len(tix)
    return res, tested


def _boot_ci(x, rng, reps=BOOT):
    x = np.asarray(x, float)
    if len(x) < 2:
        return (float("nan"), float("nan"))
    m = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(reps)]
    return tuple(float(v) for v in np.percentile(m, [2.5, 97.5]))


def describe(d, loglik, spec) -> list:
    """IN-SAMPLE per-state table on the full corpus - descriptive only."""
    allrows = np.ones(len(d["ts"]), bool)
    states, K = spec(d, allrows)
    sd = me.prior_sd(float(np.mean(d["r"])), PRIOR_N)
    seqs = _sequences(d, states, allrows)
    A = me.transition_matrix([s for _, s, _ in seqs], K, ALPHA)
    a, b = float(np.median(d["pt"])), float(np.median(d["sl"]))
    c = float(np.nanmedian(d["cost"]))
    out = []
    for s in range(K):
        m = d["resolved"] & (states == s)
        psi = me.map_psi(loglik[m], sd)
        act, p, ev = me.best_action(psi, a, b, c)
        out.append({"state": s, "n": int((states == s).sum()),
                    "n_resolved": int(m.sum()), "psi": psi,
                    "p_long": me.side_p(psi, a, b, +1),
                    "p_short": me.side_p(psi, a, b, -1),
                    "p_star": me.fair_p(a, b, c), "best": act,
                    "ev_bps": ev * 1e4, "stay": float(A[s, s]),
                    "dwell_steps": float(1 / max(1 - A[s, s], 1e-9))})
    return out


def run(history: Path, null_reps: int = NULL_REPS) -> dict:
    d, drops = load(history)
    loglik = me.outcome_loglik(d["up_first"], d["r"])
    rng = np.random.default_rng(SEED)
    out = {"report": "markov_edge", "counting_standard": COUNTING_STANDARD,
           "rows": int(len(d["ts"])), "days": int(len(np.unique(d["day"]))),
           "base_up_first": float(d["up_first"][d["resolved"]].mean()),
           "specs": {}}
    tested_any = None
    for name, spec in SPECS.items():
        res, tested = walk_forward(d, loglik, spec)
        tested_any = tested
        entry = {}
        nulls = {"static": [], "chain": []}
        nulls_auc = {"static": [], "chain": []}
        for _ in range(null_reps):
            nres, _ = walk_forward(d, loglik, spec, rng=rng)
            for v in nulls:
                nulls[v].append(float(np.mean(nres[v]["gain"]))
                                if nres[v]["gain"] else 0.0)
                nulls_auc[v].append(abs(float(np.mean(nres[v]["auc"])) - 0.5)
                                    if nres[v]["auc"] else 0.0)
        for v in ("static", "chain"):
            g, u = res[v]["gain"], res[v]["uplift"]
            obs = float(np.mean(g)) if g else float("nan")
            entry[v] = {
                "test_days": len(g),
                "gain_mean": obs, "gain_ci": _boot_ci(g, rng),
                "null_p": (1 + sum(n >= obs for n in nulls[v]))
                / (1 + len(nulls[v])) if null_reps else float("nan"),
                "auc_mean": float(np.mean(res[v]["auc"]))
                if res[v]["auc"] else float("nan"),
                "auc_ci": _boot_ci(res[v]["auc"], rng),
                "auc_null_p": (1 + sum(n >= abs(float(np.mean(res[v]["auc"]))
                                                 - 0.5)
                                       for n in nulls_auc[v]))
                / (1 + len(nulls_auc[v]))
                if null_reps and res[v]["auc"] else float("nan"),
                "uplift_mean": float(np.mean(u)) if u else float("nan"),
                "uplift_ci": _boot_ci(u, rng),
                "taken": res[v]["taken"], "rows": res[v]["rows"]}
        entry["states"] = describe(d, loglik, spec)
        out["specs"][name] = entry
    n_scored = int(tested_any.sum()) if tested_any is not None else 0
    out["counting"] = reconcile(drops["n_read"], {
        "not_candidate_tb": drops["not_candidate_tb"],
        "pre_era9": drops["pre_era9"], "unparseable": drops["unparseable"],
        "burn_in_train_only": len(d["ts"]) - n_scored,
        "scored": n_scored})
    return out


def render(rep: dict) -> str:
    L = [f"markov_edge - walk-forward, {rep['rows']} rows over "
         f"{rep['days']} days; base P(up first) resolved = "
         f"{rep['base_up_first']:.3f}", rep["counting"]["line"], ""]
    L.append("spec            variant  days  gain(nats/row)  [95% CI]"
             "              null_p  | within-day AUC [95% CI]      null_p"
             "  | uplift(bps)  [95% CI]        taken/rows")
    for name, e in rep["specs"].items():
        for v in ("static", "chain"):
            x = e[v]
            L.append(
                f"{name:15s} {v:7s} {x['test_days']:5d}  "
                f"{x['gain_mean']:+.5f}  [{x['gain_ci'][0]:+.5f},"
                f"{x['gain_ci'][1]:+.5f}]  {x['null_p']:.3f}  | "
                f"{x['auc_mean']:.3f} [{x['auc_ci'][0]:.3f},"
                f"{x['auc_ci'][1]:.3f}]  {x['auc_null_p']:.3f}  | "
                f"{x['uplift_mean'] * 1e4:+8.1f}  [{x['uplift_ci'][0] * 1e4:+.1f},"
                f"{x['uplift_ci'][1] * 1e4:+.1f}]  {x['taken']}/{x['rows']}")
    L += ["", "IN-SAMPLE state tables (descriptive, NOT evidence):"]
    for name, e in rep["specs"].items():
        L.append(f"-- {name}")
        for s in e["states"]:
            L.append(f"   s{s['state']:<3d} n={s['n']:5d} psi={s['psi']:+.3f} "
                     f"pL={s['p_long']:.3f} pS={s['p_short']:.3f} "
                     f"p*={s['p_star']:.3f} best={s['best']:5s} "
                     f"ev={s['ev_bps']:+6.1f}bps stay={s['stay']:.2f}")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--history", type=Path,
                    default=ROOT / "outputs" / "signal_history.csv")
    ap.add_argument("--null-reps", type=int, default=NULL_REPS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rep = run(args.history, args.null_reps)
    print(json.dumps(rep, indent=1, default=float) if args.json
          else render(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
