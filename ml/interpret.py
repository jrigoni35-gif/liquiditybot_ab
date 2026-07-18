"""
ml/interpret.py — post-hoc interpretability, exact where exactness exists.

The schools, argued against each other (full narrative in
docs/INTERPRET.md):

  * Lundberg's TreeSHAP line (arXiv 1802.03888): the INTERVENTIONAL
    (marginal) Shapley value is the attribution that satisfies
    consistency; the fast path-dependent variant is neither marginal nor
    conditional and can re-rank features between two trees computing the
    SAME function. Our GBT grows depth<=2 trees — at most 3 distinct
    features per tree — so we compute interventional Shapley EXACTLY by
    subset enumeration over each tree's own features against a stored
    background sample. No shap dependency, no sampling, no kernel.
  * Slack et al. (arXiv 1911.02508) fool LIME/KernelSHAP through the
    perturbation SAMPLER — off-manifold probe points a scaffolded model
    can detect. Exact enumeration has no sampler to attack, and the
    additivity audit (sum of contributions + base == the model's raw
    margin, to machine precision) is checkable evidence of fidelity on
    every explained row.
  * Rudin (arXiv 1811.10154): an explanation that cannot be faithful is
    a guess that breeds misplaced trust. Where we cannot be exact (the
    MLP/ensemble rungs) this module REFUSES rather than approximates;
    the logistic and GBT rungs — the ladder's usual occupants — carry
    exact attributions in their native margin (log-odds) space.
  * Hooker & Mentch (arXiv 1905.03151) + Lopez de Prado's clustered MDA:
    permute-and-predict importance lies under correlated features
    (permutation forces the model to extrapolate off-manifold) and
    substitution effects split credit across correlated partners until
    both look unimportant. So importance here permutes CORRELATION
    CLUSTERS as a unit, on held-out rows only, with the correlation
    structure estimated on the training window.

Everything is numpy + stdlib, deterministic under a seed, and
REPORT-ONLY: nothing here writes config or touches the decision path.
"""
import logging
from itertools import combinations
from math import comb

import numpy as np

log = logging.getLogger("liquiditybot.ml.interpret")

EPS = 1e-12


# ------------------------------------------------------------------ trees
def _tree_feats(node: dict, acc: set) -> set:
    if "f" in node:
        acc.add(int(node["f"]))
        _tree_feats(node["L"], acc)
        _tree_feats(node["R"], acc)
    return acc


def _tree_mixed(node: dict, x: np.ndarray, Z: np.ndarray,
                S: frozenset) -> np.ndarray:
    """Tree output over hybrid points: features in S come from x, the
    rest from each background row z. This is the interventional value
    function v(S) before averaging."""
    if "v" in node:
        return np.full(len(Z), float(node["v"]))
    f, t = int(node["f"]), float(node["t"])
    if f in S:
        branch = node["L"] if x[f] <= t else node["R"]
        return _tree_mixed(branch, x, Z, S)
    m = Z[:, f] <= t
    out = np.empty(len(Z))
    out[m] = _tree_mixed(node["L"], x, Z[m], S)
    out[~m] = _tree_mixed(node["R"], x, Z[~m], S)
    return out


def _shap_tree(tree: dict, x: np.ndarray, Z: np.ndarray) -> tuple:
    """Exact interventional Shapley for ONE tree: enumerate all subsets
    of the tree's own features (<= 3 at depth 2 -> <= 8 subsets).
    Returns ({feature: phi}, v_empty)."""
    feats = sorted(_tree_feats(tree, set()))
    k = len(feats)
    if k == 0:                                   # pure-leaf tree
        return {}, float(tree["v"])
    val = {}
    for r in range(k + 1):
        for S in combinations(feats, r):
            fs = frozenset(S)
            val[fs] = float(_tree_mixed(tree, x, Z, fs).mean())
    phi = {}
    for j in feats:
        others = [f for f in feats if f != j]
        total = 0.0
        for r in range(len(others) + 1):
            w = 1.0 / (k * comb(k - 1, r))       # |S|!(k-|S|-1)!/k!
            for S in combinations(others, r):
                fs = frozenset(S)
                total += w * (val[fs | {j}] - val[fs])
        phi[j] = total
    return phi, val[frozenset()]


def gbt_margin(model, x: np.ndarray) -> float:
    """Raw log-odds margin — the additive space attributions live in."""
    raw = model.base
    for tree in model.trees:
        raw += model.lr * float(
            type(model)._node_out(tree, np.atleast_2d(x))[0])
    return float(raw)


def gbt_shap(model, x: np.ndarray, background: np.ndarray) -> tuple:
    """Exact interventional Shapley for the whole ensemble (linearity in
    margin space). Returns (contrib vector, base): contrib.sum() + base
    == gbt_margin(model, x) to machine precision — the additivity audit
    every report re-verifies."""
    x = np.asarray(x, float).ravel()
    Z = np.atleast_2d(np.asarray(background, float))
    d = model.n_features or len(x)
    contrib = np.zeros(d)
    base = float(model.base)
    for tree in model.trees:
        phi, v0 = _shap_tree(tree, x, Z)
        base += model.lr * v0
        for f, p in phi.items():
            contrib[f] += model.lr * p
    return contrib, base


def logistic_attrib(model, x: np.ndarray) -> tuple:
    """Exact linear attribution in logit space: w_j standardized. For a
    linear model this IS the interventional Shapley value with the
    training mean as background."""
    x = np.asarray(x, float).ravel()
    xs = (x - model.std.mu) / model.std.sd
    contrib = model.w * xs
    return contrib, float(model.b)


def explain(model, x: np.ndarray, background=None) -> dict:
    """Faithful-or-refuse dispatch (the Rudin rule). Exact for gbt and
    logistic; blend returns both members' exact explanations; anything
    else gets an explicit refusal, never a plausible guess."""
    kind = getattr(model, "kind", "?")
    if kind == "gbt":
        if background is None:
            return {"kind": kind, "exact": False,
                    "refusal": "no background sample in artifact - "
                               "interventional SHAP undefined"}
        contrib, base = gbt_shap(model, x, background)
        return {"kind": kind, "exact": True, "space": "margin",
                "base": base, "contrib": contrib}
    if kind == "logistic":
        contrib, base = logistic_attrib(model, x)
        return {"kind": kind, "exact": True, "space": "margin",
                "base": base, "contrib": contrib}
    if kind == "blend":
        return {"kind": kind, "exact": True, "weights": [0.5, 0.5],
                "members": {"a": explain(model.a, x, background),
                            "b": explain(model.b, x, background)}}
    return {"kind": kind, "exact": False,
            "refusal": f"no faithful exact attribution exists for "
                       f"'{kind}' - refusing to guess (a wrong "
                       f"explanation is worse than none)"}


# ----------------------------------------------------------- importance
def cluster_features(X: np.ndarray, thr: float = 0.7) -> list:
    """Union-find over |pearson corr| >= thr. Permuting a cluster as a
    unit is the Hooker/de-Prado fix: partners inside a cluster move
    together, so the model is never probed off-manifold by breaking a
    within-cluster dependency, and substitution effects cannot split
    credit across the cluster boundary."""
    X = np.asarray(X, float)
    d = X.shape[1]
    sd = X.std(axis=0)
    live = sd > EPS
    parent = list(range(d))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    if live.sum() >= 2:
        idx = np.nonzero(live)[0]
        C = np.corrcoef(X[:, idx], rowvar=False)
        for ii in range(len(idx)):
            for jj in range(ii + 1, len(idx)):
                if abs(C[ii, jj]) >= thr:
                    ra, rb = find(idx[ii]), find(idx[jj])
                    if ra != rb:
                        parent[rb] = ra
    groups: dict = {}
    for j in range(d):
        groups.setdefault(find(j), []).append(j)
    return sorted(groups.values(), key=lambda g: g[0])


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def grouped_permutation_importance(predict, X: np.ndarray, y: np.ndarray,
                                   groups: list | None = None,
                                   n_repeats: int = 5,
                                   seed: int = 7) -> list:
    """Clustered MDA on held-out rows: permute each correlation cluster
    as a block (same row shuffle for every member) and measure the Brier
    degradation. Positive delta = the model NEEDS the cluster out of
    sample; ~zero = decorative; negative = the cluster actively hurts.
    Unlike gain/MDI importance this can call ALL features useless — the
    honest verdict MDI is structurally incapable of."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    if groups is None:
        groups = [[j] for j in range(X.shape[1])]
    rng = np.random.default_rng(seed)
    base = brier(y, predict(X))
    out = []
    for g in groups:
        deltas = []
        for _ in range(n_repeats):
            Xp = X.copy()
            perm = rng.permutation(len(X))
            Xp[:, g] = X[perm][:, g]             # block shuffle: cluster intact
            deltas.append(brier(y, predict(Xp)) - base)
        deltas = np.array(deltas)
        out.append({"features": list(map(int, g)),
                    "delta_brier_mean": float(deltas.mean()),
                    "delta_brier_std": float(deltas.std())})
    out.sort(key=lambda r: -r["delta_brier_mean"])
    return out


# ---------------------------------------------------------------- profile
def attribution_profile(model, X: np.ndarray, background=None) -> np.ndarray:
    """Normalized mean |phi| over rows — the model's attribution
    fingerprint. Blend averages its members' normalized profiles (each
    is exact in its own margin space; the profile is about SHAPE, not
    absolute scale). Returns a zero vector when no exact attribution
    exists (refusal propagates as 'no fingerprint', never a guess)."""
    X = np.atleast_2d(np.asarray(X, float))
    kind = getattr(model, "kind", "?")
    if kind == "blend":
        pa = attribution_profile(model.a, X, background)
        pb = attribution_profile(model.b, X, background)
        p = 0.5 * pa + 0.5 * pb
        s = p.sum()
        return p / s if s > EPS else p
    acc = np.zeros(X.shape[1])
    for row in X:
        e = explain(model, row, background)
        if not e.get("exact"):
            return np.zeros(X.shape[1])
        acc += np.abs(e["contrib"])
    s = acc.sum()
    return acc / s if s > EPS else acc


def profile_rotation(p1: np.ndarray, p2: np.ndarray) -> float:
    """Cosine similarity between two attribution fingerprints. A model
    whose PREDICTIONS look stable can still have rotated its reasons —
    attribution drift is the earlier tell (labels not required)."""
    a, b = np.asarray(p1, float), np.asarray(p2, float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < EPS or nb < EPS:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def background_sample(X: np.ndarray, rows: int = 64) -> list:
    """Deterministic, history-spanning background for the artifact:
    evenly spaced rows cover every regime era in the training window
    (a tail-only background would make attributions myopic to the
    latest regime)."""
    X = np.atleast_2d(np.asarray(X, float))
    if len(X) <= rows:
        idx = np.arange(len(X))
    else:
        idx = np.linspace(0, len(X) - 1, rows).astype(int)
    return [[round(float(v), 6) for v in r] for r in X[idx]]
