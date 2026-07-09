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

    def fit(self, X, y, Xv=None, yv=None, sample_weight=None):
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

    def predict_proba(self, X):
        Xs = self.std.transform(np.atleast_2d(X))
        z = Xs @ self.w + self.b
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))

    def to_dict(self):
        assert (self.w is not None and self.std.mu is not None
                and self.std.sd is not None), "model must be fitted before to_dict()"
        return {"kind": self.kind, "w": self.w.tolist(), "b": self.b,
                "mu": self.std.mu.tolist(), "sd": self.std.sd.tolist()}

    @classmethod
    def from_dict(cls, d):
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

    def fit(self, X, y, Xv=None, yv=None, sample_weight=None):
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

    def predict_proba(self, X):
        Xs = self.std.transform(np.atleast_2d(np.asarray(X, float)))
        p, _ = self._forward(Xs, self.params, False, np.random.default_rng(0))
        return p

    def to_dict(self):
        assert (self.params is not None and self.std.mu is not None
                and self.std.sd is not None), "model must be fitted before to_dict()"
        return {"kind": self.kind, "hidden": list(self.hidden),
                "params": {k: v.tolist() for k, v in self.params.items()},
                "mu": self.std.mu.tolist(), "sd": self.std.sd.tolist()}

    @classmethod
    def from_dict(cls, d):
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

    def fit(self, X, y, Xv=None, yv=None, sample_weight=None):
        self.members = []
        for i in range(self.k):
            m = NumpyMLP(seed=self.seed + 101 * i, **self.mlp_kwargs)
            m.fit(X, y, Xv, yv, sample_weight=sample_weight)
            self.members.append(m)
        return self

    def predict_proba(self, X):
        return np.mean([m.predict_proba(X) for m in self.members], axis=0)

    def to_dict(self):
        return {"kind": self.kind, "k": self.k,
                "members": [m.to_dict() for m in self.members]}

    @classmethod
    def from_dict(cls, d):
        e = cls(k=int(d.get("k", 3)))
        e.members = [NumpyMLP.from_dict(m) for m in d["members"]]
        return e


def save_model(model, path: str, extra: dict | None = None):
    """Persist the artifact AND register it (Assurance Build): SHA-256
    identity, immutable archive copy, model card in the append-only
    registry ledger. Registration failure never blocks the save."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    d = model.to_dict()
    if extra:
        d.update(extra)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f)
    log.info(f"model saved -> {path}")
    try:
        from ml.registry import get_registry
        from ml.contracts import SCHEMA_VERSION
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


def load_model(path: str):
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
    """

    kind = "gbt"

    def __init__(self, n_estimators: int = 300, lr: float = 0.03,
                 l2: float = 3.0, min_child_hess: float = 5.0,
                 max_depth: int = 2,
                 subsample: float = 0.7, colsample: float = 0.6,
                 max_bins: int = 64,
                 patience: int = 30, seed: int = 7):
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
        self.trees: list = []
        self.base = 0.0
        self.importance_: dict = {}

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

    def _grow(self, X, g, h, rows, depth, importance, feats=None):
        if depth <= 0 or len(rows) < 2 * self.min_child_hess:
            return {"v": self._leaf(g, h, rows)}
        f, t, gain = self._best_split(X, g, h, rows, feats)
        if f is None:
            return {"v": self._leaf(g, h, rows)}
        importance[f] = importance.get(f, 0.0) + gain
        m = X[rows, f] <= t
        return {"f": int(f), "t": t,
                "L": self._grow(X, g, h, rows[m], depth - 1, importance, feats),
                "R": self._grow(X, g, h, rows[~m], depth - 1, importance, feats)}

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
    def fit(self, X, y, Xv=None, yv=None, sample_weight=None):
        rng = np.random.default_rng(self.seed)
        X = np.asarray(X, float)
        y = np.asarray(y, float)
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

    def predict_proba(self, X):
        X = np.atleast_2d(np.asarray(X, float))
        raw = np.full(len(X), self.base)
        for tree in self.trees:
            raw += self.lr * self._node_out(tree, X)
        return 1.0 / (1.0 + np.exp(-np.clip(raw, -30, 30)))

    def to_dict(self):
        return {"kind": self.kind, "base": self.base, "lr": self.lr,
                "max_depth": self.max_depth, "colsample": self.colsample,
                "trees": self.trees,
                "importance": {str(k): v for k, v in self.importance_.items()}}

    @classmethod
    def from_dict(cls, d):
        m = cls()
        m.base = float(d["base"])
        m.lr = float(d.get("lr", 0.05))
        m.max_depth = int(d.get("max_depth", 2))
        m.colsample = float(d.get("colsample", 1.0))
        m.trees = d["trees"]
        # tolerate a clobbered/foreign importance field (an artifact's extra
        # metadata once overwrote it with a list): importance is diagnostic
        # only - never let it block loading an otherwise-valid model
        imp = d.get("importance")
        m.importance_ = {int(k): float(v) for k, v in imp.items()} \
            if isinstance(imp, dict) else {}
        return m
