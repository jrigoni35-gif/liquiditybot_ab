"""
ml/models.py

Model zoo for the meta-labeling layer.

NumpyMLP       - 2-hidden-layer MLP (ReLU, dropout, Adam, early
                stopping, class weighting) in pure numpy. Zero heavy
                dependencies, deterministic, trains in seconds on the
                dataset sizes this bot produces, and serializes to
                JSON so a trained model ships inside the repo.
LogisticModel  - L2 logistic regression baseline. If the MLP can't
                beat this out-of-sample, the walk-forward harness
                keeps the simpler model (it usually should early on -
                deep nets need data).
torch upgrade  - if PyTorch is installed, ml/torch_model.py-style
                sequence models can slot in behind the same
                predict_proba interface; nothing else changes.

All models expose fit / predict_proba / save / load and standardize
inputs internally with train-set statistics.
"""

import json
import logging
import math
from pathlib import Path

import numpy as np

log = logging.getLogger("liquiditybot.ml.models")

EPS = 1e-9


def auc_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Rank-based AUC (Mann-Whitney), ties handled by average rank."""
    y_true = np.asarray(y_true).astype(float)
    y_prob = np.asarray(y_prob).astype(float)
    pos = y_true > 0.5
    n_pos, n_neg = int(pos.sum()), int((~pos).sum())
    if n_pos == 0 or n_neg == 0:
        return 0.5
    order = np.argsort(y_prob, kind="mergesort")
    ranks = np.empty_like(order, dtype=float)
    sorted_p = y_prob[order]
    i = 0
    r = 1.0
    while i < len(sorted_p):
        j = i
        while j + 1 < len(sorted_p) and sorted_p[j + 1] == sorted_p[i]:
            j += 1
        avg = (r + r + (j - i)) / 2.0
        ranks[order[i:j + 1]] = avg
        r += (j - i) + 1
        i = j + 1
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


class _Standardizer:
    def __init__(self):
        self.mu = None
        self.sd = None

    def fit(self, X):
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0) + EPS

    def transform(self, X):
        return (X - self.mu) / self.sd


class LogisticModel:
    kind = "logistic"

    def __init__(self, l2: float = 1e-3, lr: float = 0.05, epochs: int = 400,
                seed: int = 7):
        self.l2, self.lr, self.epochs, self.seed = l2, lr, epochs, seed
        self.w = None
        self.b = 0.0
        self.std = _Standardizer()

    def fit(self, X: np.ndarray, y: np.ndarray,
            Xv: np.ndarray | None = None, yv: np.ndarray | None = None,
            sample_weight: np.ndarray | None = None) -> "LogisticModel":
        """Fit weighted L2 logistic regression on (X rows, y in {0,1});
        standardizes with train-set stats. Xv/yv accepted for interface
        parity (unused). Returns self."""
        rng = np.random.default_rng(self.seed)
        self.std.fit(X)
        Xs = self.std.transform(X)
        n, d = Xs.shape
        self.w = rng.normal(0, 0.01, d)
        self.b = 0.0
        pos_w = float((len(y) - y.sum()) / max(y.sum(), 1.0))
        sw = np.ones(n) if sample_weight is None else \
            np.asarray(sample_weight, float)
        sw = sw / (sw.mean() + EPS)
        for _ in range(self.epochs):
            z = Xs @ self.w + self.b
            p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
            wgt = np.where(y > 0.5, pos_w, 1.0) * sw
            g = (p - y) * wgt
            self.w -= self.lr * (Xs.T @ g / n + self.l2 * self.w)
            self.b -= self.lr * float(g.mean())
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Per-row P(win) in [0,1]; standardizes with train-set stats."""
        Xs = self.std.transform(np.atleast_2d(X))
        z = Xs @ self.w + self.b
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))

    @property
    def n_features(self):
        """Input width this model was fit on (None if unfitted). Lets the
        loader reject a champion trained under a superseded feature schema
        instead of faulting it on every inference (ML-013)."""
        mu = getattr(self.std, "mu", None)
        return None if mu is None else int(np.asarray(mu).shape[0])

    def to_dict(self) -> dict:
        """JSON-serializable artifact: kind + weights + standardizer stats
        (model must be fitted)."""
        assert (self.w is not None and self.std.mu is not None
                and self.std.sd is not None), "model must be fitted before to_dict()"
        return {"kind": self.kind, "w": self.w.tolist(), "b": self.b,
                "mu": self.std.mu.tolist(), "sd": self.std.sd.tolist()}

    @classmethod
    def from_dict(cls, d: dict) -> "LogisticModel":
        """Rebuild a fitted model from to_dict() output."""
        m = cls()
        m.w = np.array(d["w"])
        m.b = float(d["b"])
        m.std.mu = np.array(d["mu"])
        m.std.sd = np.array(d["sd"])
        return m


class NumpyMLP:
    kind = "mlp"

    def __init__(self, hidden=(32, 16), lr: float = 3e-3, l2: float = 1e-4,
                dropout: float = 0.15, epochs: int = 300, batch: int = 64,
                patience: int = 25, seed: int = 7):
        self.hidden = tuple(hidden)
        self.lr, self.l2, self.dropout = lr, l2, dropout
        self.epochs, self.batch, self.patience, self.seed = epochs, batch, patience, seed
        self.params = None
        self.std = _Standardizer()

    # --- core ---------------------------------------------------------
    def _init(self, d_in, rng):
        dims = [d_in, *self.hidden, 1]
        P = {}
        for i in range(len(dims) - 1):
            scale = np.sqrt(2.0 / dims[i])
            P[f"W{i}"] = rng.normal(0, scale, (dims[i], dims[i + 1]))
            P[f"b{i}"] = np.zeros(dims[i + 1])
        return P

    def _forward(self, X, P, train, rng):
        h = X
        caches = []
        L = len(self.hidden)
        for i in range(L):
            z = h @ P[f"W{i}"] + P[f"b{i}"]
            a = np.maximum(z, 0.0)
            mask = None
            if train and self.dropout > 0:
                mask = (rng.random(a.shape) >= self.dropout) / (1 - self.dropout)
                a = a * mask
            caches.append((h, z, mask))
            h = a
        z = h @ P[f"W{L}"] + P[f"b{L}"]
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        caches.append((h, z, None))
        return p.ravel(), caches

    def _backward(self, P, caches, p, y, wgt):
        grads = {}
        n = len(y)
        L = len(self.hidden)
        dz = ((p - y) * wgt / n).reshape(-1, 1)
        h_last = caches[L][0]
        grads[f"W{L}"] = h_last.T @ dz + self.l2 * P[f"W{L}"]
        grads[f"b{L}"] = dz.sum(axis=0)
        da = dz @ P[f"W{L}"].T
        for i in range(L - 1, -1, -1):
            h_in, z, mask = caches[i]
            if mask is not None:
                da = da * mask
            dz = da * (z > 0)
            grads[f"W{i}"] = h_in.T @ dz + self.l2 * P[f"W{i}"]
            grads[f"b{i}"] = dz.sum(axis=0)
            da = dz @ P[f"W{i}"].T
        return grads

    def fit(self, X: np.ndarray, y: np.ndarray,
            Xv: np.ndarray | None = None, yv: np.ndarray | None = None,
            sample_weight: np.ndarray | None = None) -> "NumpyMLP":
        """Train with Adam + dropout + early stopping on a validation
        slice (tail split when Xv/yv not given). Returns self."""
        rng = np.random.default_rng(self.seed)
        X = np.asarray(X, float)
        y = np.asarray(y, float)
        sw = np.ones(len(y)) if sample_weight is None else \
            np.asarray(sample_weight, float)
        sw = sw / (sw.mean() + EPS)
        self.std.fit(X)
        Xs = self.std.transform(X)
        if Xv is None:
            cut = max(int(len(Xs) * 0.85), 1)
            Xs, Xvs = Xs[:cut], Xs[cut:]
            y, yv, sw = y[:cut], y[cut:], sw[:cut]
        else:
            Xvs = self.std.transform(np.asarray(Xv, float))
            yv = np.asarray(yv, float)

        P = self._init(Xs.shape[1], rng)
        m = {k: np.zeros_like(v) for k, v in P.items()}
        v = {k: np.zeros_like(vv) for k, vv in P.items()}
        b1, b2, eps, t = 0.9, 0.999, 1e-8, 0
        pos_w = float((len(y) - y.sum()) / max(y.sum(), 1.0))
        wgt_all = np.where(y > 0.5, pos_w, 1.0) * sw

        best_loss, best_P, bad = np.inf, None, 0
        idx = np.arange(len(Xs))
        for _ in range(self.epochs):
            rng.shuffle(idx)
            for s in range(0, len(idx), self.batch):
                bi = idx[s:s + self.batch]
                p, caches = self._forward(Xs[bi], P, True, rng)
                grads = self._backward(P, caches, p, y[bi], wgt_all[bi])
                t += 1
                for k in P:
                    m[k] = b1 * m[k] + (1 - b1) * grads[k]
                    v[k] = b2 * v[k] + (1 - b2) * grads[k] ** 2
                    mh = m[k] / (1 - b1 ** t)
                    vh = v[k] / (1 - b2 ** t)
                    P[k] -= self.lr * mh / (np.sqrt(vh) + eps)
            if len(Xvs):
                pv, _ = self._forward(Xvs, P, False, rng)
                pv = np.clip(pv, 1e-7, 1 - 1e-7)
                loss = float(-(yv * np.log(pv) + (1 - yv) * np.log(1 - pv)).mean())
                if loss < best_loss - 1e-5:
                    best_loss, bad = loss, 0
                    best_P = {k: vv.copy() for k, vv in P.items()}
                else:
                    bad += 1
                    if bad >= self.patience:
                        break
        self.params = best_P or P
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Per-row P(win) in [0,1]; standardizes with train-set stats,
        dropout disabled (inference mode)."""
        Xs = self.std.transform(np.atleast_2d(np.asarray(X, float)))
        p, _ = self._forward(Xs, self.params, False, np.random.default_rng(0))
        return p

    @property
    def n_features(self):
        """Input width this model was fit on (None if unfitted)."""
        mu = getattr(self.std, "mu", None)
        return None if mu is None else int(np.asarray(mu).shape[0])

    def to_dict(self) -> dict:
        """JSON-serializable artifact: kind + layer params + standardizer
        stats (model must be fitted)."""
        assert (self.params is not None and self.std.mu is not None
                and self.std.sd is not None), "model must be fitted before to_dict()"
        return {"kind": self.kind, "hidden": list(self.hidden),
                "params": {k: v.tolist() for k, v in self.params.items()},
                "mu": self.std.mu.tolist(), "sd": self.std.sd.tolist()}

    @classmethod
    def from_dict(cls, d: dict) -> "NumpyMLP":
        """Rebuild a fitted model from to_dict() output."""
        m = cls(hidden=tuple(d["hidden"]))
        m.params = {k: np.array(v) for k, v in d["params"].items()}
        m.std.mu = np.array(d["mu"])
        m.std.sd = np.array(d["sd"])
        return m


class EnsembleMLP:
    """k NumpyMLPs on different seeds, probability-averaged. At small,
    noisy sample sizes a single MLP's fit varies materially with its
    init; averaging seeds is a pure variance reduction - expected Brier
    can only improve, cost is a few extra seconds of training."""
    kind = "ensemble_mlp"

    def __init__(self, k: int = 3, seed: int = 7, **mlp_kwargs):
        self.k = int(k)
        self.seed = seed
        self.mlp_kwargs = mlp_kwargs
        self.members = []

    def fit(self, X: np.ndarray, y: np.ndarray,
            Xv: np.ndarray | None = None, yv: np.ndarray | None = None,
            sample_weight: np.ndarray | None = None) -> "EnsembleMLP":
        """Fit k NumpyMLP members on decorrelated seeds. Returns self."""
        self.members = []
        for i in range(self.k):
            m = NumpyMLP(seed=self.seed + 101 * i, **self.mlp_kwargs)
            m.fit(X, y, Xv, yv, sample_weight=sample_weight)
            self.members.append(m)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Per-row P(win) in [0,1]: mean of the members' probabilities."""
        return np.mean([m.predict_proba(X) for m in self.members], axis=0)

    @property
    def n_features(self):
        """Input width this model was fit on (None if unfitted)."""
        return self.members[0].n_features if self.members else None

    def to_dict(self) -> dict:
        """JSON-serializable artifact: kind + k + member artifacts."""
        return {"kind": self.kind, "k": self.k,
                "members": [m.to_dict() for m in self.members]}

    @classmethod
    def from_dict(cls, d: dict) -> "EnsembleMLP":
        """Rebuild a fitted ensemble from to_dict() output."""
        e = cls(k=int(d.get("k", 3)))
        e.members = [NumpyMLP.from_dict(m) for m in d["members"]]
        return e


_NOT_GIVEN = object()  # sentinel: expect_prior_sha256 not passed at all


def save_model(model, path: str, extra: dict | None = None,
              expect_prior_sha256=_NOT_GIVEN) -> bool:
    """Persist the artifact AND register it (Assurance Build): SHA-256
    identity, immutable archive copy, model card in the append-only
    registry ledger. Registration failure never blocks the save.

    W2-2: the write is ATOMIC — temp file in the same directory + os.replace
    via core.runtime.atomic_write_json (the repo's own atomic-write pattern,
    already used for status.json/runner.lock) — so a crash or a transient
    Windows PermissionError mid-write can never leave a torn/truncated
    artifact on disk; the destination holds either the old bytes or the new
    ones, never a mix.

    `expect_prior_sha256` is a stale-gate CAS: the runner's in-process
    auto-retrain and a CLI scripts/train_meta.py run can both gate a
    challenger against the CURRENT champion and then race the write — the
    slower one to finish must not silently clobber the other's already-
    deployed artifact with a decision made against a champion that no
    longer exists on disk. Pass the sha256 of the artifact your deploy gate
    read (ml.registry.sha256_file), captured immediately before the gate
    decision — or None if the gate saw no artifact at all (cold start).
    Immediately before the write, the CURRENT on-disk hash is re-checked
    against it; a mismatch means another writer already deployed since your
    gate read, and the write is refused (logged loud, artifact untouched)
    rather than overwriting the newer one. Omit the parameter entirely to
    skip the check (single-writer callers, most tests) — the default
    preserves the old unconditional-write behavior exactly.

    Returns True on a completed save, False only on a CAS refusal."""
    if expect_prior_sha256 is not _NOT_GIVEN:
        from ml.registry import sha256_file
        p = Path(path)
        try:
            current = sha256_file(p) if p.exists() else None
        except OSError:
            current = None
        if current != expect_prior_sha256:
            log.error(
                "W2-2 CAS refused: %s changed since the deploy gate read it "
                "(gate expected %s, on-disk is %s) — a concurrent writer "
                "already deployed; keeping the newer artifact instead of "
                "clobbering it", path, expect_prior_sha256, current)
            return False
    d = model.to_dict()
    if extra:
        d.update(extra)
    # self-describing artifact: stamp the feature schema the model was
    # trained under so the loader can reject a champion left behind by a
    # schema bump (ML-013) instead of faulting it on every inference. The
    # running code's schema IS the artifact's schema at save time.
    from ml.contracts import SCHEMA_VERSION
    d["feature_schema_version"] = SCHEMA_VERSION
    from core.runtime import atomic_write_json
    atomic_write_json(Path(path), d)
    log.info(f"model saved -> {path}")
    try:
        from ml.registry import get_registry
        x = extra or {}
        card = {"kind": d.get("kind"),
                "oof_brier": x.get("oof_brier"),
                "rows": x.get("rows"),
                "class_balance": x.get("class_balance"),
                "train_data_sha": x.get("train_data_sha"),
                "importance_top5": (x.get("importance") or [])[:5],
                "feature_schema_version": SCHEMA_VERSION,
                "seed": getattr(model, "seed", None),
                "calibrated": bool(x.get("calibration"))}
        get_registry().register(path, card)
    except Exception:
        log.exception("model registry registration failed — artifact "
                      "saved but has no pedigree")
    return True


def load_model(path: str):
    """Load a saved artifact, dispatching on its 'kind' tag; None when the
    file does not exist. Unknown/missing kind falls back to logistic."""
    p = Path(path)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    kind = d.get("kind")
    if kind == "ensemble_mlp":
        return EnsembleMLP.from_dict(d)
    if kind == "mlp":
        return NumpyMLP.from_dict(d)
    if kind == "gbt":
        return GradientBoostedStumps.from_dict(d)
    if kind == "adaptive_gbt":
        return AdaptiveGBT.from_dict(d)
    if kind == "blend":
        return BlendModel.from_dict(d)
    return LogisticModel.from_dict(d)


class GradientBoostedStumps:
    """Newton-boosted depth-2 trees on logloss, pure numpy, JSON-
    serializable. On the tabular, few-hundred-to-few-thousand-row
    datasets this bot produces, boosted shallow trees are the
    empirically strongest learner class (they own every tabular
    benchmark at this scale) — added as a third honest candidate, not
    a replacement: walk-forward still has to pick it.

    Mechanics: second-order (Newton) boosting — per-round gradients
    g = p - y and hessians h = p(1-p); each leaf's value is
    -Σg / (Σh + λ). Shallow depth (default 3, ≤8 leaves)
    captures the regime-conditional interactions that matter in market
    features — "imbalance only predicts within bull_volatile" — without
    the variance of deep trees. (Zero-marginal symmetric products are
    invisible to ALL greedy axis-aligned trees; that pathology does not
    occur in this feature set, where every driver has a marginal trace.) Row subsampling per round decorrelates trees; early
    stopping on a validation slice picks the round count. Gain-based
    feature importance is recorded for the model card.

    monotone_constraints (T3.4): dict[int, int] | None, {feature_index:
    +1 | -1} — a priori economic sign constraints (e.g. "wider spread
    cannot improve fill odds"), so the tree cannot fit a wrong-sign
    pattern from noise. A model that learns "wider spread => better
    fill odds" has learned noise, not signal; the constraint removes
    that hypothesis from the search space entirely rather than hoping
    regularization prunes it out.

    Enforcement is BOUND PROPAGATION, not leaf reordering — reordering
    only fixes an immediate parent's two children and says nothing once
    either child is itself split again, which is exactly what happens
    at this class's own default max_depth=2 (root children are 2-level
    subtrees, not leaves). Every node in `_grow` carries an inherited
    value interval (lo, hi); the root starts at (-inf, +inf). At a split
    on a flagged feature f with sign s, let v_L, v_R be the UNCLAMPED
    tentative leaf values of the two children (the Newton leaf estimate
    -Σg/(Σh+λ) on each child's own row set, ignoring any further split)
    and h_L, h_R their hessian masses (Σh over each child's rows); the
    boundary value is their hessian-weighted mean:

        mid = (h_L·v_L + h_R·v_R) / (h_L + h_R)

    clamped into the parent's own (lo, hi) first (mid = min(max(mid,
    lo), hi)) so a child's interval is always a SUBSET of its parent's —
    the invariant every deeper split relies on. L holds the rows with
    the LOWER feature values (X[:,f] <= threshold). For s=+1 (value
    must not decrease as the feature increases): L inherits (lo, mid),
    R inherits (mid, hi) — forcing L's eventual value <= mid <= R's.
    For s=-1 the assignment is reversed: L inherits (mid, hi), R
    inherits (lo, mid). A split on an UNFLAGGED feature passes the
    parent's (lo, hi) through to both children unchanged. Every LEAF's
    final value is clamped to its inherited interval: v_leaf =
    min(max(v, lo), hi). Because each node's interval nests inside its
    parent's, this holds no matter how many times the flagged feature
    is re-split deeper in the tree, and because it constrains the
    per-tree contribution (not just one node), the boosted SUM over
    trees — and therefore predict_proba after the monotone sigmoid — is
    monotone in the flagged feature whenever all other inputs are held
    fixed.

    monotone_constraints=None (the default) never narrows any interval
    (every node stays at (-inf, +inf), so every clamp is a no-op) — the
    model is BYTE-IDENTICAL to the pre-T3.4 unconstrained tree for the
    same seed and corpus.
    """

    kind = "gbt"

    def __init__(self, n_estimators: int = 300, lr: float = 0.03,
                 l2: float = 3.0, min_child_hess: float = 5.0,
                 max_depth: int = 2,
                 subsample: float = 0.7, colsample: float = 0.6,
                 max_bins: int = 64,
                 patience: int = 30, seed: int = 7,
                 monotone_constraints: "dict[int, int] | None" = None):
        # regularized defaults (rev-4.1): at ~few-hundred-to-few-thousand
        # rows x 35 features the rev-4 defaults (depth 3, lr .05, l2 1,
        # min_child 1, 400 trees, no colsample) memorized — the overfit
        # audit measured a +0.18 train/OOF AUC gap. depth 2 caps
        # interaction order to pairwise, colsample decorrelates trees the
        # way it does in a random forest (the right lever at this feature
        # width), heavier l2/min_child prune tiny noise leaves, a slower
        # lr with the same early stopping trades a few trees for lower
        # variance. Column subsampling is per-tree and seed-deterministic.
        self.n_estimators = int(n_estimators)
        self.lr = float(lr)
        self.l2 = float(l2)
        self.min_child_hess = float(min_child_hess)
        self.max_depth = max(int(max_depth), 1)
        self.subsample = float(subsample)
        self.colsample = min(max(float(colsample), 0.1), 1.0)
        self.max_bins = int(max_bins)
        self.patience = int(patience)
        self.seed = seed
        # T3.4: {feature_index: +1|-1} a priori sign constraints, enforced
        # by bound-propagation in _grow (see class docstring for the
        # equations). Normalized to int keys/values here so a caller
        # passing JSON-round-tripped string keys (from_dict) or plain
        # ints behaves identically; falsy (None/{}) -> None, the no-op
        # fast path that keeps _grow byte-identical to pre-T3.4.
        self.monotone_constraints = ({int(k): int(v) for k, v in
                                      monotone_constraints.items()}
                                     if monotone_constraints else None)
        self.trees: list = []
        self.base = 0.0
        self.importance_: dict = {}
        self.n_features_ = None       # input width, stamped at fit

    # ---- split machinery ------------------------------------------------
    # Exact greedy scan, vectorized: each feature is argsorted ONCE per
    # fit; per node the global order is filtered to the node's rows and
    # Newton gains at every distinct-value boundary come from two
    # cumulative sums. Identical maths to the naive loop, ~20x faster.
    def _presort(self, X):
        self._order = [np.argsort(X[:, j], kind="stable")
                       for j in range(X.shape[1])]

    def _best_split(self, X, g, h, rows, feats=None):
        n_all = len(g)
        inrow = np.zeros(n_all, dtype=bool)
        inrow[rows] = True
        G, H = g[rows].sum(), h[rows].sum()
        parent = G * G / (H + self.l2)
        best = (None, 0.0, 0.0)          # (feature, threshold, gain)
        for j in (range(X.shape[1]) if feats is None else feats):
            oj = self._order[j]
            idx = oj[inrow[oj]]           # node rows, sorted by feature j
            if len(idx) < 2:
                continue
            col = X[idx, j]
            boundary = np.nonzero(col[:-1] != col[1:])[0]
            if len(boundary) == 0:
                continue
            if len(boundary) > self.max_bins:
                pick = np.linspace(0, len(boundary) - 1,
                                   self.max_bins).astype(int)
                boundary = boundary[pick]
            cg = np.cumsum(g[idx])
            ch = np.cumsum(h[idx])
            GL, HL = cg[boundary], ch[boundary]
            GR, HR = G - GL, H - HL
            ok = (HL >= self.min_child_hess) & (HR >= self.min_child_hess)
            if not ok.any():
                continue
            gain = np.where(ok, GL * GL / (HL + self.l2) +
                            GR * GR / (HR + self.l2) - parent, -np.inf)
            k = int(np.argmax(gain))
            if gain[k] > best[2] + 1e-12:
                thr = 0.5 * (col[boundary[k]] + col[boundary[k] + 1])
                best = (j, float(thr), float(gain[k]))
        return best

    def _leaf(self, g, h, rows) -> float:
        return float(-g[rows].sum() / (h[rows].sum() + self.l2))

    @staticmethod
    def _clamp(v: float, lo: float, hi: float) -> float:
        """min(max(v, lo), hi) — the leaf-value monotone clamp. lo/hi
        default to -inf/+inf everywhere monotone_constraints is None, so
        this is a no-op for the unconstrained model."""
        return min(max(v, lo), hi)

    def _grow(self, X, g, h, rows, depth, importance, feats=None,
              lo: float = -np.inf, hi: float = np.inf):
        if depth <= 0 or len(rows) < 2 * self.min_child_hess:
            return {"v": self._clamp(self._leaf(g, h, rows), lo, hi)}
        f, t, gain = self._best_split(X, g, h, rows, feats)
        if f is None:
            return {"v": self._clamp(self._leaf(g, h, rows), lo, hi)}
        importance[f] = importance.get(f, 0.0) + gain
        m = X[rows, f] <= t
        rows_l, rows_r = rows[m], rows[~m]
        lo_l, hi_l, lo_r, hi_r = lo, hi, lo, hi
        sign = (self.monotone_constraints or {}).get(f)
        if sign:
            # T3.4 bound propagation (see class docstring for the full
            # derivation): the boundary between the two children is the
            # hessian-weighted mean of their own UNCLAMPED tentative leaf
            # values, clamped into THIS node's own (lo, hi) so every
            # descendant's interval nests inside its parent's — the
            # invariant that makes the guarantee hold no matter how many
            # times the flagged feature is re-split deeper in the tree.
            v_l = self._leaf(g, h, rows_l)
            v_r = self._leaf(g, h, rows_r)
            h_l = float(h[rows_l].sum())
            h_r = float(h[rows_r].sum())
            h_sum = h_l + h_r
            mid = (h_l * v_l + h_r * v_r) / h_sum if h_sum > 0 else \
                0.5 * (v_l + v_r)
            mid = self._clamp(mid, lo, hi)
            if sign > 0:
                hi_l, lo_r = mid, mid
            else:
                lo_l, hi_r = mid, mid
        return {"f": int(f), "t": t,
                "L": self._grow(X, g, h, rows_l, depth - 1, importance,
                                 feats, lo_l, hi_l),
                "R": self._grow(X, g, h, rows_r, depth - 1, importance,
                                 feats, lo_r, hi_r)}

    @staticmethod
    def _node_out(node, X):
        if "v" in node:
            return np.full(len(X), node["v"])
        m = X[:, node["f"]] <= node["t"]
        if "L" in node:
            out = np.empty(len(X))
            out[m] = GradientBoostedStumps._node_out(node["L"], X[m])
            out[~m] = GradientBoostedStumps._node_out(node["R"], X[~m])
            return out
        return np.where(m, node["vl"], node["vr"])  # legacy depth-2 artifacts

    # ---- API --------------------------------------------------------------
    def fit(self, X: np.ndarray, y: np.ndarray,
            Xv: np.ndarray | None = None, yv: np.ndarray | None = None,
            sample_weight: np.ndarray | None = None
            ) -> "GradientBoostedStumps":
        """Newton-boost shallow trees on logloss with early stopping on a
        validation slice (tail split when Xv/yv not given). Returns self."""
        rng = np.random.default_rng(self.seed)
        X = np.asarray(X, float)
        y = np.asarray(y, float)
        self.n_features_ = int(X.shape[1])   # input width, before val split
        sw = np.ones(len(y)) if sample_weight is None else \
            np.asarray(sample_weight, float)
        sw = sw / (sw.mean() + EPS)
        pos_w = float((len(y) - y.sum()) / max(y.sum(), 1.0))
        wgt = np.where(y > 0.5, pos_w, 1.0) * sw

        if Xv is None:
            cut = max(int(len(X) * 0.85), 1)
            X, Xv = X[:cut], X[cut:]
            y, yv = y[:cut], y[cut:]
            wgt = wgt[:cut]
        else:
            Xv = np.asarray(Xv, float)
            yv = np.asarray(yv, float)

        self._presort(X)
        p0 = float(np.clip(np.average(y, weights=wgt), 1e-3, 1 - 1e-3))
        self.base = math.log(p0 / (1 - p0))
        raw_tr = np.full(len(X), self.base)
        raw_va = np.full(len(Xv), self.base) if len(Xv) else np.empty(0)

        self.trees = []
        importance: dict = {}
        best_loss, best_n, bad = np.inf, 0, 0
        n = len(X)
        for _ in range(self.n_estimators):
            p = 1.0 / (1.0 + np.exp(-np.clip(raw_tr, -30, 30)))
            g = (p - y) * wgt
            h = np.maximum(p * (1 - p) * wgt, 1e-6)
            rows = np.arange(n) if self.subsample >= 1.0 else \
                rng.choice(n, size=max(int(n * self.subsample), 8),
                           replace=False)
            d_feat = X.shape[1]
            feats = None if self.colsample >= 1.0 else \
                rng.choice(d_feat, size=max(int(d_feat * self.colsample), 1),
                           replace=False)
            tree = self._grow(X, g, h, rows, self.max_depth, importance,
                              feats)
            self.trees.append(tree)
            raw_tr += self.lr * self._node_out(tree, X)
            if len(Xv):
                raw_va += self.lr * self._node_out(tree, Xv)
                pv = np.clip(1.0 / (1.0 + np.exp(-np.clip(raw_va, -30, 30))),
                             1e-7, 1 - 1e-7)
                loss = float(-(yv * np.log(pv) +
                               (1 - yv) * np.log(1 - pv)).mean())
                if loss < best_loss - 1e-5:
                    best_loss, best_n, bad = loss, len(self.trees), 0
                else:
                    bad += 1
                    if bad >= self.patience:
                        break
        if len(Xv) and best_n:
            self.trees = self.trees[:best_n]
        tot = sum(importance.values()) or 1.0
        self.importance_ = {int(k): v / tot for k, v in importance.items()}
        return self

    def continue_fit(self, X, y, n_rounds: int, sample_weight=None):
        """Warm-start continuation: append up to `n_rounds` boosting rounds
        on NEW labels, continuing from the current ensemble instead of
        discarding it. This is the incremental-learning primitive AdaptiveGBT
        uses for cheap between-retrain refresh: the appended rounds fit the
        residuals the trained trees leave on the fresh batch, so the model
        leans toward the most recent regime by construction (the intended
        behavior for a non-stationary market) while keeping everything it
        already learned. Callers bound the total tree count.

        No-op (returns self unchanged) when there is nothing to continue from
        (unfitted), the width disagrees, or n_rounds<=0 — a warm update must
        never be able to corrupt a healthy champion. importance_ is left as
        the original fit's: it is diagnostic only, and mixing normalized
        fractions with fresh raw gains would be incoherent."""
        if not self.trees or self.n_features_ is None:
            return self
        X = np.asarray(X, float)
        y = np.asarray(y, float)
        if X.ndim != 2 or X.shape[1] != self.n_features_:
            return self
        n = len(X)
        n_rounds = int(n_rounds)
        if n_rounds <= 0 or n < 2:
            return self
        # seed derived from tree count so repeated updates don't reuse draws
        rng = np.random.default_rng(self.seed + 7919 + len(self.trees))
        sw = np.ones(n) if sample_weight is None else \
            np.asarray(sample_weight, float)
        sw = sw / (sw.mean() + EPS)
        pos_w = float((n - y.sum()) / max(y.sum(), 1.0))
        wgt = np.where(y > 0.5, pos_w, 1.0) * sw
        self._presort(X)
        raw = np.full(n, self.base)
        for tree in self.trees:
            raw += self.lr * self._node_out(tree, X)
        scratch: dict = {}          # throwaway: keep importance_ untouched
        for _ in range(n_rounds):
            p = 1.0 / (1.0 + np.exp(-np.clip(raw, -30, 30)))
            g = (p - y) * wgt
            h = np.maximum(p * (1 - p) * wgt, 1e-6)
            rows = np.arange(n) if self.subsample >= 1.0 else \
                rng.choice(n, size=max(int(n * self.subsample), min(8, n)),
                           replace=False)
            feats = None if self.colsample >= 1.0 else \
                rng.choice(self.n_features_,
                           size=max(int(self.n_features_ * self.colsample), 1),
                           replace=False)
            tree = self._grow(X, g, h, rows, self.max_depth, scratch, feats)
            self.trees.append(tree)
            raw += self.lr * self._node_out(tree, X)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Per-row P(win) in [0,1]: sigmoid of base + sum of tree outputs."""
        X = np.atleast_2d(np.asarray(X, float))
        raw = np.full(len(X), self.base)
        for tree in self.trees:
            raw += self.lr * self._node_out(tree, X)
        return 1.0 / (1.0 + np.exp(-np.clip(raw, -30, 30)))

    @property
    def n_features(self):
        """Input width this model was fit on (None if unfitted)."""
        return self.n_features_

    def to_dict(self) -> dict:
        # subsample/l2/min_child_hess/seed are serialized so a model loaded
        # from disk can continue_fit() with its ORIGINAL regularization, not
        # the constructor defaults — a warm update after a restart must be
        # faithful. Older artifacts lack these keys; from_dict falls back to
        # the current defaults, which is behavior-preserving for predict.
        d = {"kind": self.kind, "base": self.base, "lr": self.lr,
             "max_depth": self.max_depth, "colsample": self.colsample,
             "subsample": self.subsample, "l2": self.l2,
             "min_child_hess": self.min_child_hess, "seed": self.seed,
             "n_features": self.n_features_,
             "trees": self.trees,
             "importance": {str(k): v for k, v in self.importance_.items()}}
        # T3.4: key added ONLY when constraints are actually set - the
        # None default (no constraints) must produce a BYTE-IDENTICAL dict
        # to the pre-T3.4 model (regression-pinned in
        # tests/test_gbt_monotone.py), so the key cannot merely be `None`.
        if self.monotone_constraints:
            d["monotone_constraints"] = {str(k): v for k, v in
                                         self.monotone_constraints.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "GradientBoostedStumps":
        """Rebuild a fitted model from to_dict() output (older artifacts
        without the regularization keys get the current defaults)."""
        m = cls()
        m.base = float(d["base"])
        m.lr = float(d.get("lr", 0.05))
        m.max_depth = int(d.get("max_depth", 2))
        m.colsample = float(d.get("colsample", 1.0))
        # regularization for a faithful continue_fit after load (defaults
        # match __init__ so pre-stamp artifacts stay behavior-identical)
        m.subsample = float(d.get("subsample", 0.7))
        m.l2 = float(d.get("l2", 3.0))
        m.min_child_hess = float(d.get("min_child_hess", 5.0))
        m.seed = d.get("seed", 7)
        nf = d.get("n_features")
        m.n_features_ = int(nf) if nf is not None else None
        m.trees = d["trees"]
        # tolerate a clobbered/foreign importance field (an artifact's extra
        # metadata once overwrote it with a list): importance is diagnostic
        # only - never let it block loading an otherwise-valid model
        imp = d.get("importance")
        m.importance_ = {int(k): float(v) for k, v in imp.items()} \
            if isinstance(imp, dict) else {}
        # T3.4: string keys are a JSON round-trip artifact - convert back
        # to int (the column index _grow/predict actually index with).
        # Absent (older artifacts, or a constraint-free model) -> None.
        mc = d.get("monotone_constraints")
        m.monotone_constraints = ({int(k): int(v) for k, v in mc.items()}
                                  if isinstance(mc, dict) and mc else None)
        return m


class BlendModel:
    """Equal-weight probability blend of the linear baseline and the
    boosted stumps — two decorrelated hypothesis classes averaged for
    pure variance reduction. The blend weight is deliberately NOT
    fitted: a tuned weight is one more degree of freedom to overfit on
    the small datasets this bot produces (OF-7 discipline). It occupies
    the ladder rung above gbt and ships only by beating gbt
    out-of-sample by the Brier margin, like every other rung."""
    kind = "blend"

    def __init__(self, seed: int = 7):
        self.seed = seed
        self.a = LogisticModel(seed=seed)
        self.b = GradientBoostedStumps(seed=seed)

    def fit(self, X: np.ndarray, y: np.ndarray,
            sample_weight: np.ndarray | None = None) -> "BlendModel":
        """Fit both members on the same data. Returns self."""
        self.a.fit(X, y, sample_weight=sample_weight)
        self.b.fit(X, y, sample_weight=sample_weight)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Per-row P(win) in [0,1]: equal-weight mean of both members."""
        return 0.5 * (self.a.predict_proba(X) + self.b.predict_proba(X))

    @property
    def n_features(self):
        """Input width this model was fit on (None if unfitted)."""
        # the logistic member always carries a standardizer -> reliable width
        return self.a.n_features

    def to_dict(self) -> dict:
        """JSON-serializable artifact: kind + both member artifacts."""
        return {"kind": self.kind, "seed": self.seed,
                "a": self.a.to_dict(), "b": self.b.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> "BlendModel":
        """Rebuild a fitted blend from to_dict() output."""
        m = cls(seed=int(d.get("seed", 7)))
        m.a = LogisticModel.from_dict(d["a"])
        m.b = GradientBoostedStumps.from_dict(d["b"])
        return m


class AdaptiveGBT:
    """Drift-adaptive, continuously-learnable boosted-tree model.

    Two upgrades over the single `gbt` rung, both aimed at a small-sample,
    non-stationary, always-learning trading corpus — and both free of any
    FITTED degree of freedom, so the simplicity ladder still has to elect
    this rung on out-of-sample merit (it ships above `mlp`, config-gated,
    exactly like every other complexity step):

      1. BAGGED boosting. k boosted-stump models on decorrelated seeds,
         probability-averaged — the same pure-variance-reduction move
         EnsembleMLP makes for MLPs. Boosted shallow trees are the
         strongest learner class at this data scale; averaging seeds
         trims the run-to-run variance a single GBT carries at a few
         hundred rows without touching bias. k is fixed config, not tuned.

      2. WARM continuous learning. `warm_update(X_new, y_new)` appends a
         bounded number of boosting rounds to every member on freshly
         labeled rows, continuing from the trained ensemble rather than
         retraining from zero. Between the scheduled full retrains this
         lets the champion track a shifting regime cheaply, leaning recent
         by construction, hard-capped at `max_total_trees` per member so
         it can never grow unbounded or let one small batch run away.

    Same fit/predict_proba/n_features/save/load contract as every other
    model; JSON-serializable end to end, so warm updates survive a
    restart."""
    kind = "adaptive_gbt"

    def __init__(self, k: int = 4, warm_rounds: int = 25,
                 max_total_trees: int = 800, seed: int = 7, **gbt_kwargs):
        self.k = max(int(k), 1)
        self.warm_rounds = max(int(warm_rounds), 0)
        self.max_total_trees = max(int(max_total_trees), 1)
        self.seed = seed
        self.gbt_kwargs = gbt_kwargs
        self.members: list = []

    def fit(self, X: np.ndarray, y: np.ndarray,
            Xv: np.ndarray | None = None, yv: np.ndarray | None = None,
            sample_weight: np.ndarray | None = None) -> "AdaptiveGBT":
        """Fit k GradientBoostedStumps members on decorrelated seeds.
        Returns self."""
        self.members = []
        for i in range(self.k):
            m = GradientBoostedStumps(seed=self.seed + 101 * i,
                                      **self.gbt_kwargs)
            m.fit(X, y, Xv, yv, sample_weight=sample_weight)
            self.members.append(m)
        return self

    def warm_update(self, X_new, y_new, sample_weight=None):
        """Incrementally teach every member on new labels, bounded by
        max_total_trees. Returns self. A no-op member (already at the tree
        cap, unfitted, or width-mismatched) is left untouched by
        continue_fit, so a warm update can only ever help or hold."""
        for m in self.members:
            room = self.max_total_trees - len(m.trees)
            if room > 0:
                m.continue_fit(X_new, y_new,
                               n_rounds=min(self.warm_rounds, room),
                               sample_weight=sample_weight)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Per-row P(win) in [0,1]: mean of the members' probabilities."""
        return np.mean([m.predict_proba(X) for m in self.members], axis=0)

    @property
    def n_features(self):
        """Input width this model was fit on (None if unfitted)."""
        return self.members[0].n_features if self.members else None

    def to_dict(self) -> dict:
        """JSON-serializable artifact: kind + warm-update caps + member
        artifacts (so warm updates survive a restart)."""
        return {"kind": self.kind, "k": self.k,
                "warm_rounds": self.warm_rounds,
                "max_total_trees": self.max_total_trees,
                "members": [m.to_dict() for m in self.members]}

    @classmethod
    def from_dict(cls, d: dict) -> "AdaptiveGBT":
        """Rebuild a fitted model from to_dict() output."""
        e = cls(k=int(d.get("k", 4)),
                warm_rounds=int(d.get("warm_rounds", 25)),
                max_total_trees=int(d.get("max_total_trees", 800)))
        e.members = [GradientBoostedStumps.from_dict(m)
                     for m in d.get("members", [])]
        return e
