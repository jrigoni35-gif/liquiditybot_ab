"""
ml/history.py

Training-data plumbing.

HistoryStore  - logs the feature vector of every entry the bot takes
                (keyed by position_id), then appends the labeled row
                (win = net PnL > 0 after fees) when the position fully
                closes. This is the gold-standard dataset: the model
                  learns from the bot's *own* fills, costs and slippage,
                not idealized backtest fills.
bootstrap     - cold-start dataset built by replaying EMA-cross
                pseudo-signals over candle history through the
                triple-barrier labeler. Weaker than live data (no
                microstructure features vary historically) but enough
                to get a first calibrated prior. Clearly marked so
                train_meta.py reports which data trained the model.
"""

import csv
import os
import logging
import time
from pathlib import Path

import numpy as np

from ml.features import FEATURE_NAMES
from ml.labeling import triple_barrier

log = logging.getLogger("liquiditybot.ml.history")


class HistoryStore:
    def __init__(self, path: str = "outputs/signal_history.csv"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._pending: dict = {}      # position_id -> features
        # meta column named "side": FEATURE_NAMES also contains "direction",
        # and a duplicated CSV header made DictReader consumers silently read
        # whichever column came last.
        self._header = ["position_id", "asset", "side", *FEATURE_NAMES,
                        "label", "net_pnl_usd", "source", "ts"]

    def _ensure_schema(self):
        """Rotate-or-create, WRITE PATH ONLY. Rotation used to live in
        __init__, which made merely constructing a HistoryStore (e.g.
        overfit_check loading training data, or any QA script pointed at
        the default path) rotate the production CSV as a side effect —
        after a FEATURE_NAMES change, the first read-only QA run silently
        swept the bot's entire accumulated training set into a .bak.
        Checked before every append (not once) so a long-lived process
        holding an older schema in memory can never interleave misaligned
        rows into a file another process has since re-headered — observed
        live 2026-07-11: a pre-SMC runner appended 43-column rows under a
        50-column post-SMC header, corrupting all three."""
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                existing = f.readline().strip().split(",")
            if existing == self._header:
                return
            bak = self.path.with_suffix(f".bak_{int(time.time())}")
            os.replace(self.path, bak)      # cross-platform atomic
            log.warning(f"history schema changed - old file kept at {bak}")
        with open(self.path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(self._header)

    def log_entry(self, position_id: str, asset: str, direction: str,
                features: np.ndarray):
        self._pending[position_id] = (asset, direction, features.copy())

    def _append_row(self, position_id: str, asset: str, direction: str,
                    feats: np.ndarray, label: int, pnl_usd: float, source: str):
        self._ensure_schema()
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([position_id, asset, direction,
                                    *[f"{v:.6f}" for v in feats],
                                    label, f"{pnl_usd:.2f}", source,
                                    f"{time.time():.0f}"])

    def log_close(self, position_id: str, net_pnl_usd: float):
        entry = self._pending.pop(position_id, None)
        if entry is None:
            return
        asset, direction, feats = entry
        label = int(net_pnl_usd > 0)
        self._append_row(position_id, asset, direction, feats, label,
                        net_pnl_usd, "live")
        log.info(f"labeled trade {position_id[:8]}: label={label} "
                f"pnl=${net_pnl_usd:,.2f}")

    def row_count(self) -> int:
        if not self.path.exists():
            return 0
        with open(self.path, encoding="utf-8") as f:
            return max(sum(1 for _ in f) - 1, 0)

    def load_training_data(self, half_life_days: float = 30.0,
                        candidate_weight: float = 0.4):
        """Returns X, y, w. Sample weights encode two honest priors:
        recent rows matter more (markets are non-stationary; exponential
        recency decay with a config half-life), and live-fill rows carry
        real execution costs while candidate rows are barrier
        counterfactuals (down-weighted, not discarded)."""
        empty = (np.empty((0, len(FEATURE_NAMES))), np.empty(0), np.empty(0))
        if not self.path.exists():
            return empty
        X, y, w = [], [], []
        now = time.time()
        with open(self.path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    X.append([float(row[n]) for n in FEATURE_NAMES])
                    y.append(float(row["label"]))
                    age_d = max(now - float(row.get("ts") or now), 0.0) / 86400.0
                    ww = 0.5 ** (age_d / max(half_life_days, 1e-6))
                    if row.get("source") == "candidate":
                        ww *= candidate_weight
                    w.append(ww)
                except (KeyError, ValueError):
                    continue
        return np.array(X, float), np.array(y, float), np.array(w, float)


class CandidateLabeler:
    """Labels EVERY gate-confirmed signal - taken or vetoed - via
    triple-barrier on the subsequent price path. This is the dataset
    multiplier: the model otherwise only ever sees the few, selection-
    biased trades that survived every veto. Candidate rows are written
    with source="candidate" so training can weight or inspect them
    separately from live fills.
    """

    def __init__(self, store: HistoryStore, ml_cfg: dict, on_label=None):
        cfg = ml_cfg or {}
        self.store = store
        # optional callback(gates_passed: dict|None, label: int), fired as
        # each candidate labels - feeds per-gate predictive-power stats
        # (strategies.signal_gates.GateStats) without coupling this module
        # to any signal engine
        self._on_label = on_label
        self.horizon = int(cfg.get("label_max_bars", 96))
        self.pt = float(cfg.get("label_pt_vol_mult", 8.0))
        self.sl = float(cfg.get("label_sl_vol_mult", 6.0))
        # round-trip cost subtracted before the win/loss label. Defaults to the
        # maker round-trip (2 x 25bps = 0.5%) so labels reflect REALIZED net
        # profitability, not an optimistic ~0 - a 6bps default here taught the
        # model that near-breakeven trades were wins. Config-driven + guarded.
        self.rt_cost_pct = float(cfg.get("label_round_trip_cost_pct", 0.5))
        self.max_candidates = int(cfg.get("max_open_candidates", 200))
        self._bars: dict = {}          # asset -> {"t":[], "c":[], "h":[], "l":[]}
        self._cands: list = []
        self._seq = 0
        # (asset, direction) -> last registered bar_time: a signal that stays
        # confirmed across several slow cycles inside ONE candle must yield
        # ONE candidate row, not near-identical duplicates that overweight
        # that bar in training
        self._last_reg: dict = {}

    def update_candles(self, asset: str, candles: list):
        if not candles:
            return
        b = self._bars.setdefault(asset, {"t": [], "c": [], "h": [], "l": []})
        last_t = b["t"][-1] if b["t"] else -1
        for c in candles:
            if c["time"] > last_t:
                b["t"].append(c["time"])
                b["c"].append(c["close"])
                b["h"].append(c["high"])
                b["l"].append(c["low"])
                last_t = c["time"]
        cap = self.horizon * 5
        if len(b["t"]) > cap:
            for k in b:
                b[k] = b[k][-cap:]

    def register(self, asset: str, direction: str, features: np.ndarray,
                sigma_bar: float, bar_time, gates_passed=None) -> None:
        if self._last_reg.get((asset, direction)) == bar_time:
            return                      # same signal, same candle: no duplicate
        self._last_reg[(asset, direction)] = bar_time
        if len(self._cands) >= self.max_candidates:
            self._cands.pop(0)
        self._seq += 1
        self._cands.append({"id": f"cand-{self._seq}", "asset": asset,
                            "direction": direction,
                            "features": features.copy(),
                            "sigma_bar": float(max(sigma_bar, 1e-5)),
                            "bar_time": bar_time,
                            # which gates passed at signal time (JSON-safe
                            # bools); the labeled outcome feeds per-gate stats
                            "gates": {str(g): bool(v) for g, v in
                                      gates_passed.items()}
                            if isinstance(gates_passed, dict) else None})

    def poll(self) -> int:
        """Label candidates whose horizon has elapsed. Returns rows written."""
        written = 0
        for cand in list(self._cands):
            b = self._bars.get(cand["asset"])
            if not b or cand["bar_time"] not in b["t"]:
                # entry bar evicted or never cached: unlabelable, drop
                if b and b["t"] and cand["bar_time"] < b["t"][0]:
                    self._cands.remove(cand)
                continue
            i = b["t"].index(cand["bar_time"])
            if len(b["t"]) - 1 - i < self.horizon:
                continue
            closes = np.array(b["c"], float)
            highs = np.array(b["h"], float)
            lows = np.array(b["l"], float)
            side = 1 if cand["direction"] == "long" else -1
            out = triple_barrier(closes, highs, lows, i, side,
                                cand["sigma_bar"], self.pt, self.sl,
                                self.horizon, cost_pct=self.rt_cost_pct)
            self.store._append_row(cand["id"], cand["asset"],
                                cand["direction"], cand["features"],
                                out.label, 0.0, "candidate")
            if self._on_label is not None:
                try:
                    self._on_label(cand.get("gates"), out.label)
                except Exception:
                    log.exception("on_label callback failed - gate stats "
                                  "skipped for this candidate")
            self._cands.remove(cand)
            written += 1
        if written:
            log.info(f"labeled {written} candidate signal(s) via triple-barrier")
        return written

    # --- persistence hooks ---
    def to_dict(self) -> dict:
        return {"bars": self._bars, "seq": self._seq,
                "cands": [{**c, "features": c["features"].tolist()}
                        for c in self._cands],
                # JSON keys must be strings: "asset|direction" -> bar_time
                "last_reg": {f"{a}|{d}": t
                             for (a, d), t in self._last_reg.items()}}

    def restore(self, d: dict):
        if not d:
            return
        self._bars = {a: {k: list(v) for k, v in bb.items()}
                    for a, bb in d.get("bars", {}).items()}
        self._seq = int(d.get("seq", 0))
        self._cands = [{**c, "features": np.array(c["features"], float)}
                    for c in d.get("cands", [])]
        self._last_reg = {}
        for key, t in (d.get("last_reg") or {}).items():
            a, _, direc = key.partition("|")
            if direc:
                self._last_reg[(a, direc)] = t


def _ema(closes: np.ndarray, period: int) -> np.ndarray:
    k = 2.0 / (period + 1)
    out = np.empty_like(closes)
    out[0] = closes[0]
    for i in range(1, len(closes)):
        out[i] = closes[i] * k + out[i - 1] * (1 - k)
    return out


def bootstrap_dataset(candles_5m: list, direction_from_cross: bool = True,
                    pt_mult: float = 8.0, sl_mult: float = 6.0,
                    max_bars: int = 96, cost_pct: float = 0.5):
    """EMA-cross pseudo-signals -> triple-barrier labels over history.

    Microstructure/regime/sentiment features are unavailable historically
    and set to neutral; only price/vol/momentum features vary. Good
    enough for a calibrated prior, not a substitute for live history.
    """
    closes = np.array([c["close"] for c in candles_5m], float)
    highs = np.array([c["high"] for c in candles_5m], float)
    lows = np.array([c["low"] for c in candles_5m], float)
    vols = np.array([c["volume"] for c in candles_5m], float)
    if len(closes) < 300:
        return np.empty((0, len(FEATURE_NAMES))), np.empty(0)

    fast, slow = _ema(closes, 9), _ema(closes, 21)
    rets = np.diff(np.log(np.maximum(closes, 1e-9)))
    X, y = [], []
    for i in range(60, len(closes) - max_bars - 1):
        crossed_up = fast[i] > slow[i] and fast[i - 1] <= slow[i - 1]
        crossed_dn = fast[i] < slow[i] and fast[i - 1] >= slow[i - 1]
        if not (crossed_up or crossed_dn):
            continue
        side = 1 if crossed_up else -1
        sigma_bar = float(rets[max(i - 60, 0):i].std() + 1e-6)
        out = triple_barrier(closes, highs, lows, i, side, sigma_bar,
                            pt_mult, sl_mult, max_bars, cost_pct=cost_pct)
        feats = np.zeros(len(FEATURE_NAMES))
        name_idx = {n: k for k, n in enumerate(FEATURE_NAMES)}

        def setf(name, val):
            feats[name_idx[name]] = val

        for name, k in (("ret_1", 1), ("ret_6", 6), ("ret_12", 12), ("ret_48", 48)):
            if i - k >= 0 and closes[i - k] > 0:
                r = np.log(closes[i] / closes[i - k])
                setf(name, float(np.clip(r / (sigma_bar * np.sqrt(k) + 1e-9), -6, 6)))
        setf("sigma_bar_pct", float(np.clip(sigma_bar * 100, 0, 5)))
        vwin = vols[max(i - 48, 0):i]
        if len(vwin) > 2:
            setf("volume_z", float(np.clip((vols[i] - vwin.mean()) / (vwin.std() + 1e-9), -5, 5)))
        mom = np.sign(closes[i] - closes[max(i - 288, 0)])
        setf("mom_score", float(mom))
        setf("regime_range", 1.0)
        setf("turbulence_pct", 0.5)
        setf("direction", float(side))
        setf("gate_confidence", 1.0)
        X.append(feats)
        y.append(float(out.label))
    return np.array(X, float), np.array(y, float)
