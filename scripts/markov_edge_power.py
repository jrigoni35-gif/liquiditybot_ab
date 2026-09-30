"""scripts/markov_edge_power.py - can scripts/markov_edge_report.py see an edge?

REPORT-ONLY instrument verification (THE MINDSET: a surprising or null
number gets its instrument verified before it gets a theory). Keeps the REAL
corpus structure - rows, days, assets, barrier geometry r, the basis state
assignment, and each day's own trend - and replaces only the outcomes with
simulated ones carrying a PLANTED state edge delta:

    psi_row = delta * (state - 1) + psi_day[day]      (basis: 3 states)

psi_day = each real day's own MAP drift, so the unpredictable day level is
reproduced exactly; `--no-day-level` removes it for the control. Detection =
the day-block CI excluding no-effect (gain > 0, within-day AUC > 0.5).
Break-even needs psi ~ +1.2 (p 0.4286 -> p* 0.571 at the label geometry).

FIRST RUN (2026-09-30, snapshot 2026-09-29T20:10:58Z, 40 sims/cell): the
calibration gain detected NOTHING under the real day level - 0/40 even at
delta 2.0 - while the within-day AUC detected delta 0.6 in 38/40 and 1.2 in
40/40. Day drift sd 3.49 barrier-widths. Re-derive; never copy forward.

Usage: python scripts/markov_edge_power.py --history PATH [--sims 40]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from ml import markov_edge as me  # noqa: E402
import markov_edge_report as R  # noqa: E402

DELTAS = (0.0, 0.3, 0.6, 1.2, 2.0)
DAY_PRIOR_SD = 5.0          # weak: a day's own drift, barrier-widths


def day_drifts(d) -> dict:
    L = me.outcome_loglik(d["up_first"], d["r"])
    return {dd: me.map_psi(L[(d["day"] == dd) & d["resolved"]], DAY_PRIOR_SD)
            for dd in np.unique(d["day"])}


def simulate(d, state, level, delta, rng):
    """Outcomes from the planted model on the real rows."""
    psi = delta * (state - 1) + level
    return (rng.random(len(psi)) < me.hit_prob(psi, d["r"])).astype(float)


def one(d, state, level, delta, rng, as_of, horizon):
    up = simulate(d, state, level, delta, rng)
    d2 = dict(d, up_first=up)
    res, _ = R.walk_forward(d2, me.outcome_loglik(up, d2["r"]), R._basis,
                            horizon_sec=horizon, as_of=as_of)
    out = {}
    for v in ("static", "chain"):
        g, a = res[v]["gain"], res[v]["auc"]
        out[v] = (float(np.mean(g)) if g else float("nan"),
                  R._boot_ci(g, rng, 500)[0] > 0,
                  float(np.mean(a)) if a else float("nan"),
                  R._boot_ci(a, rng, 500)[0] > 0.5)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--history", type=Path, required=True)
    ap.add_argument("--sims", type=int, default=40)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args(argv)
    as_of = a.history.stat().st_mtime
    horizon = R._label_horizon_sec()
    d, _ = R.load(a.history)
    rng = np.random.default_rng(a.seed)
    pdays = day_drifts(d)
    pd_ = np.array(list(pdays.values()))
    print(f"read {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} as_of "
          f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(as_of))} rows "
          f"{len(d['ts'])}; day drift psi sd {pd_.std():.3f} range "
          f"[{pd_.min():+.2f}, {pd_.max():+.2f}]")
    state, _ = R._basis(d, np.ones(len(d["ts"]), bool))
    level = np.array([pdays[x] for x in d["day"]])
    print("delta  day_lvl | static: gain  P(CI>0)  AUC  P(CI>0.5) | "
          "chain: gain  P(CI>0)  AUC  P(CI>0.5)")
    for use_level in (True, False):
        for delta in DELTAS:
            rs = [one(d, state, level if use_level else 0.0, delta, rng,
                      as_of, horizon) for _ in range(a.sims)]
            row = f"{delta:4.1f}   {'real' if use_level else 'none':5s} |"
            for v in ("static", "chain"):
                row += (f" {np.mean([r[v][0] for r in rs]):+.4f}  "
                        f"{np.mean([r[v][1] for r in rs]):5.2f}  "
                        f"{np.mean([r[v][2] for r in rs]):.3f}  "
                        f"{np.mean([r[v][3] for r in rs]):5.2f} |")
            print(row, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
