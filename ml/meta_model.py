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
        # mtime of the artifact last loaded + its own OOF brier, so a LIVE bot
        # can pick up an EXTERNAL retrain (scripts/train_meta.py) and realign
        # the champion baseline to the deployed model instead of ignoring it.
        self._loaded_mtime = 0.0
        self.oof_brier = None
        self.reload()

    # ------------------------------------------------------------------
    def reload(self):
        self.model = None
        self.model_id = ""
        self.oof_brier = None
        self.calibrator = IsotonicCalibrator()
        self.feature_deciles = []
        p = Path(self.model_path)
        if not p.exists():
            self._loaded_mtime = 0.0
            log.info("no trained meta-model found — cold-start prior in "
                     "effect")
            return
        # stamp the mtime BEFORE accept/reject: a rejected artifact must not
        # re-trigger reload_if_changed every cycle (the file didn't change).
        try:
            self._loaded_mtime = p.stat().st_mtime
        except OSError:
            self._loaded_mtime = 0.0
        # integrity gate BEFORE the artifact touches the interpreter state
        v = get_registry().verify(str(p))
        if v.get("ok") is False:
            log.critical("ML-011: meta-model artifact failed integrity — "
                         "running on cold-start prior until a verified "
                         "model is deployed")
            return
        model = load_model(self.model_path)
        if model is None:
            return
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        # schema gate: a champion trained under a superseded feature schema
        # (or of a mismatched input width) must be REJECTED here, not loaded
        # and then faulted on every inference. Rejection drops the service to
        # the cold-start prior, which the retrain gate reads as "no champion"
        # and rebuilds against the current schema. (ML-013)
        reason = self._schema_mismatch(model, d)
        if reason:
            log.critical("ML-013: rejecting stale meta-model — %s; running on "
                         "cold-start prior until a current-schema model is "
                         "trained", reason)
            return
        self.model = model
        self.model_id = v.get("model_id", "")
        self.calibrator = IsotonicCalibrator.from_dict(d.get("calibration"))
        self.feature_deciles = d.get("feature_deciles") or []
        try:
            self.oof_brier = float(d["oof_brier"])
        except (KeyError, TypeError, ValueError):
            self.oof_brier = None
        log.info("meta-model %s loaded from %s (%s, calibrated=%s, "
                 "provenance=%s)", self.model_id or "?", self.model_path,
                 self.model.kind, self.calibrator.fitted,
                 {True: "verified", None: "unregistered"}.get(v.get("ok"),
                                                              "FAILED"))

    def reload_if_changed(self) -> bool:
        """Reload IFF the artifact changed on disk since the last load — i.e.
        an EXTERNAL retrain (scripts/train_meta.py run against a live bot).
        The bot's OWN in-process retrain calls reload() directly, which
        re-stamps the mtime, so this never double-fires for it. Returns True
        when a change was detected and a reload ran (whatever its outcome)."""
        try:
            mt = Path(self.model_path).stat().st_mtime
        except OSError:
            return False
        if mt <= self._loaded_mtime:
            return False
        self.reload()
        return True

    def _schema_mismatch(self, model, d: dict) -> str:
        """Non-empty reason if `model` does not match the current feature
        schema, else "". Three independent checks, in order of definitiveness:
          1. the artifact's stamped feature_schema_version vs the contract's
             SCHEMA_VERSION — kind-agnostic, definitive when present;
          2. the model's own input width vs the contract feature count —
             catches legacy artifacts saved before the stamp existed (the
             stale 43-feature champion that motivated this gate);
          3. FUNCTIONAL probe when BOTH the stamp and the reported width are
             absent (a bare, unstamped model, e.g. the current gbt champion):
             feed the model a contract-width vector. A wider/mismatched legacy
             artifact indexes past it or shape-mismatches and raises -> reject;
             a correct bare model returns a value -> accept. Closes the hole
             where n_features=None skipped check 2 and an unstamped artifact of
             the WRONG width was adopted silently. (A narrower unstamped gbt
             that merely ignores extra columns can still slip this probe, but
             every model saved since stamping carries checks 1+2; the governor's
             Brier monitor is the backstop for that shrinking legacy case.)"""
        from ml.contracts import SCHEMA_VERSION
        sv = d.get("feature_schema_version")
        if sv is not None:
            try:
                if int(sv) != int(SCHEMA_VERSION):
                    return f"feature-schema v{sv} != current v{SCHEMA_VERSION}"
            except (TypeError, ValueError):
                return f"unreadable feature-schema tag {sv!r}"
        width = getattr(model, "n_features", None)
        if width is not None and width != self.contract.n:
            return (f"model width {width} != current schema "
                    f"{self.contract.n} features")
        if sv is None and width is None:
            try:
                model.predict_proba(np.zeros((1, self.contract.n), dtype=float))
            except Exception as e:                       # noqa: BLE001
                return (f"unstamped unknown-width model failed a "
                        f"{self.contract.n}-feature probe ({type(e).__name__})")
        return ""

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
