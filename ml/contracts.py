"""
ml/contracts.py — data contracts for the learning stack (Assurance Build)

SR 11-7's first pillar is knowing your model's inputs are what you
think they are. This module is the enforcement point: a versioned
contract over the feature vector — name, order, and legal range per
feature — checked at EVERY inference and at training-data load.

Contract violations at inference never raise and never reach the
model: the caller falls back to the cold-start prior (fail-safe), the
violation is counted per feature, and repeated violations surface in
the governor's status. A model fed garbage silently is how "the ML
works" becomes "the ML worked until it didn't"; a model that refuses
garbage loudly is a component you can certify.

Ranges match the clipping already applied in ml/features.py — the
contract asserts the pipeline's own invariants, so a violation means
the pipeline is broken (schema drift, un-clipped new feature, NaN
leak), not that the market did something unusual.
"""

import logging

import numpy as np

from ml.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION

log = logging.getLogger("liquiditybot.ml.contracts")

# single source of truth: the feature-schema version is OWNED by ml.features
# (which owns FEATURE_NAMES). The contract, the model-artifact stamp
# (ml.models.save_model), the loader guard (ml.meta_model), and the
# snapshot/history versioning (core.persistence, ml.history) all reference
# this one number, so a schema bump cannot leave any of them disagreeing.
SCHEMA_VERSION = FEATURE_SCHEMA_VERSION

# name -> (lo, hi) inclusive legal range; tolerance added at check time
_RANGES = {
    "ret_1_dir": (-6, 6), "ret_6_dir": (-6, 6), "ret_12_dir": (-6, 6),
    "ret_48_dir": (-6, 6),
    "sigma_bar_pct": (0, 5), "vol_percentile": (0, 1),
    "imbalance_dir": (-2, 2), "spread_bps": (0, 6), "depth_log": (0, 3),
    "fv_edge_bps": (-5, 5), "basis_dir": (-8, 8),
    "volume_z": (-5, 5), "funding_dir": (-3, 3),
    "mom_dir": (-1, 1), "drawdown_pct": (0, 0.9),
    "regime_bull_quiet": (0, 1), "regime_bull_vol": (0, 1),
    "regime_range": (0, 1), "regime_bear": (0, 1), "regime_crisis": (0, 1),
    "corr_fast": (-1, 1), "corr_shift": (-1, 1), "turbulence_pct": (0, 1),
    "sent_dir": (-1, 1), "sent_fear": (0, 1),
    "fear_greed": (0, 1), "dominance_delta": (-3, 3),
    "equity_risk_z": (-4, 4),
    "hour_sin": (-1, 1), "hour_cos": (-1, 1), "weekend": (0, 1),
    "imbalance_delta_dir": (-2, 2), "other_ret_6_dir": (-3, 3),
    "depth_ratio": (0, 3),
    "mtf_align": (-1, 1), "pd_zone": (0, 1), "liq_pocket_pull": (0, 1),
    "fvg_pull": (0, 1), "fvg_liq_confluence": (0, 1),
    "poc_dist": (-1, 1), "va_pos": (-1, 1),
    "regime_age": (0, 1), "funding_dist": (0, 1),
    "venue_disloc_dir": (-3, 3),
    "th_grid": (0, 1), "th_metronome": (0, 1),
    "th_clockwork": (0, 1), "th_stopzone": (0, 1), "th_barclose": (0, 1),
    "opt_pcr_z": (-4, 4), "opt_oi_pcr_z": (-4, 4), "opt_iv_skew": (-3, 3),
    "manip_suspect": (0, 1),
    "pat_engulf_dir": (-1, 1), "pat_hammer_dir": (-1, 1), "pat_marubozu_dir": (-1, 1),
    "vol_term": (-2, 2), "mkt_ret_6_dir": (-3, 3),
    "book_touch_share": (0, 1), "flow_tox": (0, 1),
    "ofi_dir": (-3, 3), "basis_mom_dir": (-3, 3),
    "dp_surge_z": (-4, 4), "dp_vol_z": (-4, 4),
    "dp_hhi": (0, 1), "avail_dp": (0, 1),
    "direction": (-1, 1), "gate_confidence": (0, 1),
}
_TOL = 1e-6


class FeatureContract:
    def __init__(self):
        self.names = list(FEATURE_NAMES)
        self.n = len(self.names)
        self.violations: dict = {}
        self.checked = 0
        self.failed = 0
        missing = [n for n in self.names if n not in _RANGES]
        if missing:
            # a feature without a declared range is itself a contract
            # defect: refuse to arm rather than silently skip it
            raise RuntimeError(f"feature contract: no range declared for "
                               f"{missing} — update ml/contracts.py with "
                               f"the schema change")

    # ------------------------------------------------------------------
    def check(self, x) -> tuple:
        """Returns (ok, reasons). Never raises."""
        self.checked += 1
        reasons = []
        try:
            arr = np.asarray(x, dtype=float).ravel()
        except (TypeError, ValueError):
            self.failed += 1
            return False, ["ML-013: feature vector not numeric"]
        if arr.shape[0] != self.n:
            self.failed += 1
            return False, [f"ML-013: length {arr.shape[0]} != "
                           f"schema {self.n} (v{SCHEMA_VERSION})"]
        bad = ~np.isfinite(arr)
        if bad.any():
            for j in np.flatnonzero(bad)[:4]:
                reasons.append(f"ML-010: {self.names[j]} non-finite")
        else:
            for j, name in enumerate(self.names):
                lo, hi = _RANGES[name]
                v = arr[j]
                if v < lo - _TOL or v > hi + _TOL:
                    reasons.append(f"ML-010: {name}={v:.4g} outside "
                                   f"[{lo}, {hi}]")
                    if len(reasons) >= 4:
                        break
        if reasons:
            self.failed += 1
            for r in reasons:
                key = r.split(":", 1)[1].split("=")[0].strip() \
                    if ":" in r else r
                self.violations[key] = self.violations.get(key, 0) + 1
            return False, reasons
        return True, []

    def check_matrix(self, X) -> dict:
        """Training-data screen: per-row check, returns keep-mask +
        summary. Rows violating the contract are excluded from training
        rather than 'fixed' — imputing over a pipeline defect just
        launders it into the weights."""
        X = np.asarray(X, dtype=float)
        keep = np.ones(len(X), dtype=bool)
        for i in range(len(X)):
            ok, _ = self.check(X[i])
            keep[i] = ok
        dropped = int((~keep).sum())
        if dropped:
            log.warning("ML-010: training screen dropped %d/%d rows "
                        "violating the feature contract", dropped, len(X))
        return {"keep": keep, "dropped": dropped, "total": len(X)}

    def status(self) -> dict:
        return {"schema_version": SCHEMA_VERSION, "n_features": self.n,
                "checked": self.checked, "failed": self.failed,
                "violations": dict(sorted(self.violations.items(),
                                          key=lambda kv: -kv[1])[:8])}


_CONTRACT = None


def get_contract() -> FeatureContract:
    global _CONTRACT
    if _CONTRACT is None:
        _CONTRACT = FeatureContract()
    return _CONTRACT
