"""
scripts/tune_search.py — champion calibration engine (offline, REPORT-ONLY).

Synthesis of the reference stack behind arXiv:2003.11294 ("Preference-based
MPC calibration"), adapted to this repo's overfit protocols. Each cited
school of thought contributes exactly the part that survives adversarial
review against the others:

  * Surrogate optimization of EXPENSIVE experiments (Brochu et al. BO
    tutorial; Bemporad GLIS; Gutmann/McDonald RBF global opt): each config
    candidate costs a full deterministic replay or a multi-day paper run,
    so never grid-search — fit a cheap surrogate to observed (knobs ->
    net objective) points and let an acquisition function pick the next
    candidate. We take the RBF interpolant + IDW exploration of GLIS over
    GP-based BO: no kernel hyper-tuning, no scipy/GP dependency, and the
    heuristic acquisition is honest about being one (the GP's calibrated
    posterior is a luxury that costs a fragile ML dependency here).
  * Exploration term (GLIS inverse-distance weighting): pure exploitation
    of the surrogate converges to the first local basin; the IDW term pays
    to look far from every tested point. delta is the knob the Brochu
    school calls exploration weight.
  * SAFE/CONSTRAINED search (Berkenkamp SafeOpt; Fiducioso safe
    contextual BO; Driess constrained BO): an infeasible candidate — one
    that fails config_guard, the quant gates G1-G5, or the pretrade cost
    stack — is not merely bad, it poisons the region around it. Feasible
    experiments carry their objective; infeasible ones enter a BAD SET
    that adds an IDW proximity penalty to the acquisition (the paper's
    own future-work "good/bad classifier", realized without a classifier
    dependency). Unlike SafeOpt we need no conservative safe-set
    guarantee: experiments are replays/paper runs — failure is free, only
    misleading, so we penalize rather than forbid.
  * Space-filling initialization (McKay Latin Hypercube): the surrogate
    is garbage until the space is covered; LHS beats uniform random for
    the first N points at identical cost.
  * The REFEREE is cross-validation (Stone 1974), not the surrogate: a
    winning candidate is only a CHALLENGER. Promotion requires beating
    the incumbent OUT-OF-SAMPLE under the repo's existing quant gates and
    OF battery — the surrogate proposes, the gates dispose. This engine
    therefore NEVER writes config.json; it emits a report.
  * Preferences (Christiano et al.; Wirth survey; GLISp) enter ONLY as a
    tie-breaker: when two candidates' objectives sit inside the noise
    band, the operator's judgment (style: smoother equity, fewer flips)
    picks — preferences where the ledger is silent, never instead of it.
    Trading history is full of blowups from "felt better" beating
    "measured better"; the inverse-RL school (Menner, Rosbach, Wang)
    learns objectives from behavior, which for a trading book is exactly
    the self-deception the OF battery exists to block.

Usage (state lives in outputs/tune_search_state.json):
  python scripts/tune_search.py --spec knobs.json --init 8
  python scripts/tune_search.py --spec knobs.json --record '<theta-json>' \
      --objective -1.23 [--infeasible]
  python scripts/tune_search.py --spec knobs.json --propose

knobs.json: [{"name": "pretrade.min_edge_cost_ratio", "lo": 1.0,
              "hi": 3.0}, ...]  (2-10 knobs; bounds are the trust region)
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "outputs" / "tune_search_state.json"
# objective noise band: candidates within this relative band are TIES the
# operator may break by preference (style), per the GLISp school
TIE_BAND_FRAC = 0.05


# ---------------------------------------------------------------- sampling
def latin_hypercube(n: int, bounds: np.ndarray, seed: int = 7) -> np.ndarray:
    """McKay et al. 1979: one sample per axis-stratum, shuffled per
    dimension — space-filling coverage at random-sampling cost."""
    rng = np.random.default_rng(seed)
    d = len(bounds)
    u = (rng.random((n, d)) + np.arange(n)[:, None]) / n
    for j in range(d):
        rng.shuffle(u[:, j])
    return bounds[:, 0] + u * (bounds[:, 1] - bounds[:, 0])


# ---------------------------------------------------------------- surrogate
def _phi(eps_d):
    return 1.0 / (1.0 + eps_d ** 2)            # inverse-quadratic RBF


def _dist2(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    return ((A[:, None, :] - B[None, :, :]) ** 2).sum(-1)


def fit_rbf(X: np.ndarray, y: np.ndarray, eps: float = 1.0) -> np.ndarray:
    """Gutmann-style RBF interpolation coefficients, ridge-stabilized so
    near-duplicate experiments never blow up the solve."""
    M = _phi(eps * _dist2(X, X))
    return np.linalg.solve(M + 1e-8 * np.eye(len(X)), y)


def surrogate(theta: np.ndarray, X: np.ndarray, beta: np.ndarray,
              eps: float = 1.0) -> np.ndarray:
    return _phi(eps * _dist2(np.atleast_2d(theta), X)) @ beta


def idw(theta: np.ndarray, X: np.ndarray) -> np.ndarray:
    """GLIS exploration: 0 at every tested point, growing (bounded by
    arctan) with distance from ALL of them."""
    d2 = _dist2(np.atleast_2d(theta), X)
    with np.errstate(divide="ignore"):
        w = np.where(d2 > 0, 1.0 / np.maximum(d2, 1e-300), np.inf)
    s = w.sum(axis=1)
    out = np.arctan(1.0 / s)
    out[np.isinf(s)] = 0.0                     # exactly at a sample
    return out


# ------------------------------------------------------------- acquisition
def acquisition(theta: np.ndarray, X, y, beta, bad_X,
                eps: float = 1.0, delta: float = 1.0,
                gamma: float = 2.0) -> np.ndarray:
    """Normalized surrogate (exploit) − delta·IDW (explore) + gamma·bad-
    proximity (the safe-BO school's constraint pressure, classifier-free:
    infeasible points repel via the same bounded IDW geometry)."""
    theta = np.atleast_2d(theta)
    span = max(float(y.max() - y.min()), 1e-9)
    a = surrogate(theta, X, beta, eps) / span
    a = a - delta * idw(theta, X)
    if bad_X is not None and len(bad_X):
        d2 = _dist2(theta, np.atleast_2d(bad_X))
        a = a + gamma * (1.0 / (1.0 + d2.min(axis=1)))
    return a


def propose(X, y, bounds, bad_X=None, eps=1.0, delta=1.0,
            gamma=2.0, seed=7, n_starts=2000) -> np.ndarray:
    """Next candidate = argmin acquisition, by dense random multistart
    inside the trust region (portable stand-in for PSwarm: derivative-free
    and good enough at <=10 knobs; the acquisition is a heuristic anyway —
    per the paper itself — so a global-exact inner solve buys nothing)."""
    rng = np.random.default_rng(seed + len(X))
    cand = bounds[:, 0] + rng.random((n_starts, len(bounds))) \
        * (bounds[:, 1] - bounds[:, 0])
    beta = fit_rbf(X, y, eps)
    a = acquisition(cand, X, y, beta, bad_X, eps, delta, gamma)
    return cand[int(np.argmin(a))]


# ------------------------------------------------------------------ state
def _load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"evals": []}


def _save_state(st):
    STATE.parent.mkdir(exist_ok=True)
    tmp = STATE.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(st, indent=1), encoding="utf-8")
    os.replace(tmp, STATE)


def _spec(path: str):
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    if not (2 <= len(spec) <= 10):
        raise SystemExit("knob spec must have 2-10 knobs (trust region "
                         "discipline: tune few things at once)")
    bounds = np.array([[float(k["lo"]), float(k["hi"])] for k in spec])
    if not np.all(bounds[:, 1] > bounds[:, 0]):
        raise SystemExit("every knob needs hi > lo")
    return spec, bounds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--init", type=int, metavar="N")
    g.add_argument("--record", metavar="THETA_JSON")
    g.add_argument("--propose", action="store_true")
    ap.add_argument("--objective", type=float,
                    help="NET objective for --record (lower is better, "
                         "e.g. -net_usd from the gated replay)")
    ap.add_argument("--infeasible", action="store_true",
                    help="candidate failed config_guard/quant gates")
    ap.add_argument("--delta", type=float, default=1.0)
    args = ap.parse_args()
    spec, bounds = _spec(args.spec)
    names = [k["name"] for k in spec]
    st = _load_state()

    if args.init is not None:
        pts = latin_hypercube(args.init, bounds)
        print(json.dumps([dict(zip(names, map(float, p))) for p in pts],
                         indent=1))
        return 0

    if args.record is not None:
        theta = json.loads(args.record)
        if set(theta) != set(names):
            raise SystemExit(f"theta keys must be exactly {names}")
        if not args.infeasible and args.objective is None:
            raise SystemExit("--record needs --objective (or --infeasible)")
        st["evals"].append({"theta": {n: float(theta[n]) for n in names},
                            "objective": (None if args.infeasible
                                          else float(args.objective)),
                            "feasible": not args.infeasible})
        _save_state(st)
        print(f"recorded ({len(st['evals'])} total)")
        return 0

    evals = st["evals"]
    ok = [e for e in evals if e["feasible"]]
    if len(ok) < 2:
        raise SystemExit("need >= 2 feasible evals recorded before "
                         "--propose (run --init and evaluate those first)")
    X = np.array([[e["theta"][n] for n in names] for e in ok])
    y = np.array([e["objective"] for e in ok])
    bad = [e for e in evals if not e["feasible"]]
    bad_X = np.array([[e["theta"][n] for n in names] for e in bad]) \
        if bad else None
    nxt = propose(X, y, bounds, bad_X, delta=args.delta)
    best = ok[int(np.argmin(y))]
    span = max(float(y.max() - y.min()), 1e-9)
    ties = [e for e in ok
            if abs(e["objective"] - best["objective"]) <= TIE_BAND_FRAC * span
            and e is not best]
    out = {"next_candidate": dict(zip(names, map(float, nxt))),
           "incumbent_best": best,
           "preference_ties": ties,
           "note": ("REPORT-ONLY: promotion requires beating the incumbent "
                    "OUT-OF-SAMPLE under quant gates G1-G5 + the OF "
                    "battery. Ties inside the noise band are the "
                    "operator's style call.")}
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
