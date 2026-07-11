"""
ml/meta_model.py — rev 2.0 (Assurance Build)

Runtime inference service for the meta-labeling model, rebuilt around
one rule: THE MODEL NEVER SEES AN INPUT THE CONTRACT HASN'T PASSED,
AND THE SIZER NEVER SEES A PROBABILITY THE MODEL DIDN'T EARN.

  * Every p_win() call validates the feature vector against
    ml/contracts.py. Violation -> fail-safe: the conservative
    cold-start prior (ML-020), counted, never raised. A pipeline bug
    now degrades sizing gracefully instead of feeding garbage to Kelly.
  * Artifact loads verify SHA-256 against the model registry ledger
    (ML-011 on mismatch -> refuse the artifact, run on the prior,
    scream). A corrupted or tampered model file cannot make sizing
    decisions.
  * Inference itself is wrapped: an exception inside predict returns
    the prior and increments a fault counter — one bad matrix shape
    can't take the entry pipeline down.

Cold-start and shrinkage semantics unchanged: no model -> prior only
on fully-confirmed gates; probabilities squashed toward 0.5 by the
governor-supplied shrinkage; hard clip to [0.05, 0.95].
"""

import json
import logging
from pathlib import Path

import numpy as np

from ml.calibration import IsotonicCalibrator
from ml.contracts import get_contract
from ml.models import load_model
from ml.registry import get_registry

log = logging.getLogger("liquiditybot.ml.meta_model")


class MetaModelService:
    def __init__(self, config: dict):
        cfg = config or {}
        self.model_path = cfg.get("model_path", "outputs/meta_model.json")
        self.prior_p = float(cfg.get("cold_start_prior_p", 0.56))
        self.shrinkage = float(cfg.get("probability_shrinkage", 0.35))
        self.min_train_rows = int(cfg.get("min_train_rows", 150))
        self.model = None
        self.model_id = ""
        self.calibrator = IsotonicCalibrator()
        self.feature_deciles: list = []
        self.contract = get_contract()
        self.fallbacks = 0            # ML-020 count: prior served instead
        self.infer_faults = 0
        self.reload()

    # ------------------------------------------------------------------
    def reload(self):
        self.model = None
        self.model_id = ""
        self.calibrator = IsotonicCalibrator()
        self.feature_deciles = []
        p = Path(self.model_path)
        if not p.exists():
            log.info("no trained meta-model found — cold-start prior in "
                     "effect")
            return
        # integrity gate BEFORE the artifact touches the interpreter state
        v = get_registry().verify(str(p))
        if v.get("ok") is False:
            log.critical("ML-011: meta-model artifact failed integrity — "
                         "running on cold-start prior until a verified "
                         "model is deployed")
            return
        self.model = load_model(self.model_path)
        if self.model is None:
            return
        self.model_id = v.get("model_id", "")
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            self.calibrator = IsotonicCalibrator.from_dict(
                d.get("calibration"))
            self.feature_deciles = d.get("feature_deciles") or []
        except (OSError, ValueError):
            pass
        log.info("meta-model %s loaded from %s (%s, calibrated=%s, "
                 "provenance=%s)", self.model_id or "?", self.model_path,
                 self.model.kind, self.calibrator.fitted,
                 {True: "verified", None: "unregistered"}.get(v.get("ok"),
                                                              "FAILED"))

    @property
    def trained(self) -> bool:
        return self.model is not None

    # ------------------------------------------------------------------
    def p_win(self, features: np.ndarray, gate_confidence: float,
              shrinkage: float | None = None, use_model: bool = True) -> float:
        """shrinkage/use_model are live overrides from the governor —
        a degraded model gets pulled harder toward 0.5; a failing one
        is bypassed entirely (kill switch).

        prior is the cold-start/fallback estimate, served whenever there is
        no usable model output (untrained, contract violation, inference
        fault). Always self.prior_p: the sole caller (main.py) only ever
        invokes p_win() after signal.all_confirmed is verified True, so a
        prior gate of `gate_confidence >= 0.999` was dead code - gate_conf
        there is a continuously-shaded score (gate_stats weighted_confidence
        + THALES shading), essentially never exactly >=0.999, so every
        fallback silently used an unconfigurable 0.50 instead of the
        operator-configured cold_start_prior_p."""
        prior = self.prior_p
        if self.model is None or not use_model:
            return prior
        ok, reasons = self.contract.check(features)
        if not ok:
            self.fallbacks += 1
            log.warning("ML-020: contract violation -> prior %.2f (%s)",
                        prior, "; ".join(reasons[:2]))
            return prior
        try:
            p = float(self.model.predict_proba(
                np.asarray(features, float).reshape(1, -1))[0])
            if not np.isfinite(p):
                raise ValueError("non-finite model output")
            p = float(self.calibrator.transform(np.array([p]))[0])
        except Exception:
            self.infer_faults += 1
            self.fallbacks += 1
            log.exception("ML-020: inference fault -> prior %.2f", prior)
            return prior
        s = self.shrinkage if shrinkage is None else float(shrinkage)
        p = 0.5 + (1.0 - s) * (p - 0.5)
        return float(np.clip(p, 0.05, 0.95))

    def status(self) -> dict:
        return {"trained": self.trained, "model_id": self.model_id,
                "fallbacks": self.fallbacks,
                "infer_faults": self.infer_faults,
                "contract": self.contract.status()}
