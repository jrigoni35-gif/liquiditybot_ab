"""
ml/monitor.py — model risk governor, rev 2.0 (Assurance Build)

The ongoing-monitoring pillar of SR 11-7, implemented as a staged
governor over the meta-model. The model is treated the way a bank
treats a vendor model: it makes recommendations; this module decides
how much authority those recommendations carry, within hard bounds it
can tighten but never loosen.

Judgment (every closed model-scored trade):
  * rolling Brier vs the naive base-rate baseline (rev 1, kept)
  * expected calibration error (rev 1, kept)
  * NEW — Wilson lower confidence bound on the realized hit rate vs
    the average promised p. At n=20 a raw hit-rate comparison is a
    coin-flip reading; the Wilson LCB only indicts the model when the
    shortfall is statistically real at ~95%. Fewer false demotions,
    and the true ones carry evidence.

Escalation ladder (unchanged semantics, now audit-chained):
  L0 healthy   full authority.
  L1 degraded  shrinkage up, Kelly multiplier 0.7 — trades smaller.
  L2 failing   KILL SWITCH (ML-050): model output ignored, prior takes
               over, Kelly floors, retrain requested. Reversible only
               by a deployed challenger or a clean recovery window.

Deployment gate: challenger must beat the champion's OOF Brier by the
margin (or no real champion exists). Every level change, retrain
request, deploy, and reject lands in the hash-chained audit trail —
"why did the bot stop trusting its model on Tuesday" has a one-line
answer forever.

Bounded knob adjustments from postmortem causes kept as-is: the
governor can only make the bot MORE conservative than config, never
less. Interface + persistence keys are a strict superset of rev 1.
"""

import logging
import math
import time
from collections import Counter, deque
from pathlib import Path

import numpy as np

from core.audit import get_audit
from core.codes import Code
from ml.calibration import brier_score, calibration_gap, psi

log = logging.getLogger("liquiditybot.ml.monitor")


def wilson_lcb(successes: int, n: int, z: float = 1.645) -> float:
    """One-sided 95% Wilson lower bound on a binomial proportion."""
    if n <= 0:
        return 0.0
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = p + z2 / (2 * n)
    rad = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return max((center - rad) / denom, 0.0)


class ModelMonitor:
    def __init__(self, config: dict):
        cfg = config or {}
        self.window = int(cfg.get("window_trades", 30))
        self.min_trades = int(cfg.get("min_trades_to_judge", 15))
        self.brier_margin = float(cfg.get("brier_margin", 0.01))
        self.calib_gap_max = float(cfg.get("calibration_gap_max", 0.15))
        self.hit_shortfall_max = float(cfg.get("hit_shortfall_max", 0.08))
        self.retrain_cooldown_s = float(
            cfg.get("retrain_cooldown_hours", 12)) * 3600
        self.retrain_min_new_rows = int(cfg.get("retrain_min_new_rows", 40))
        self.retrain_min_rows = int(cfg.get("retrain_min_rows", 60))
        self.deploy_margin = float(cfg.get("challenger_brier_margin", 0.005))
        self.deploy_min_oof = int(cfg.get("deploy_min_oof", 30))
        self.flag_path = Path(cfg.get("retrain_flag_path",
                                      "outputs/retrain_requested.flag"))
        self.shrink_base = float(cfg.get("shrinkage_base", 0.35))
        self.cause_stale_sec = float(
            cfg.get("cause_stale_hours", 4.0)) * 3600.0
        self.shrink_max = float(cfg.get("shrinkage_max", 0.70))
        self.kelly_mult_min = float(cfg.get("kelly_mult_min", 0.40))
        self.edge_ratio_bump_max = float(cfg.get("edge_ratio_bump_max", 0.4))
        self.stop_widen_max = float(cfg.get("stop_widen_max", 1.5))

        self.drift_psi_threshold = float(cfg.get("drift_psi_threshold",
                                                 0.25))
        self.drift_min_rows = int(cfg.get("drift_min_rows", 40))
        self.drift_frac_features = float(cfg.get("drift_frac_features",
                                                 0.30))
        self._feat_buffer: deque = deque(maxlen=300)
        self.drift_share = 0.0
        self.drifting: list = []
        self._records: deque = deque(maxlen=self.window * 3)
        self._cause_tally: Counter = Counter()
        self._causes_window: deque = deque(maxlen=20)
        self._last_cause_ts = 0.0
        self.level = 0
        self._level_streak = 0
        self._last_retrain_request = 0.0
        self._rows_at_last_request = 0
        self.champion_brier: float = 0.25

        # live overrides consumed by main/meta/sizer (bounded, one-way
        # conservative)
        self.shrinkage = self.shrink_base
        self.kelly_mult = 1.0
        self.use_model = True
        self.edge_ratio_bump = 0.0
        self.stop_widen = 1.0

    # ------------------------------------------------------------------
    def record_close(self, p_predicted: float, label: int,
                     model_scored: bool, cause: str = ""):
        self._records.append((float(p_predicted), int(label),
                              bool(model_scored)))
        if cause:
            self._cause_tally[cause] += 1
            self._causes_window.append(cause)
            self._last_cause_ts = time.time()
            self._apply_cause_adjustments()
        self._evaluate()

    def _windows(self):
        recs = [r for r in self._records if r[2]][-self.window:]
        if len(recs) < self.min_trades:
            return None
        p = np.array([r[0] for r in recs])
        y = np.array([r[1] for r in recs])
        return p, y

    # ------------------------------------------------------------------
    def _evaluate(self):
        w = self._windows()
        if w is None:
            return
        p, y = w
        n = len(y)
        base_rate = float(np.clip(y.mean(), 0.05, 0.95))
        model_brier = brier_score(y, p)
        baseline_brier = brier_score(y, np.full_like(p, base_rate))
        gap = calibration_gap(y, p)
        # Wilson LCB judgment: does the realized hit rate credibly fall
        # short of what the model promised on these very trades?
        lcb = wilson_lcb(int(y.sum()), n)
        promised = float(p.mean())
        # indict only when the shortfall is BOTH material (raw gap beyond
        # the allowance) AND statistically credible (even the optimistic
        # Wilson bound can't explain it). An honest model at small n has
        # a wide LCB gap but ~zero raw gap: not a deficit.
        raw_gap = promised - float(y.mean())
        hit_deficit = raw_gap > self.hit_shortfall_max and \
            (promised - lcb) > self.hit_shortfall_max

        degraded = (model_brier > baseline_brier + self.brier_margin) or \
            (gap > self.calib_gap_max) or hit_deficit
        failing = model_brier > baseline_brier + 3 * self.brier_margin or \
            (hit_deficit and gap > self.calib_gap_max)

        prev = self.level
        if failing:
            self._level_streak = self._level_streak + 1 if prev >= 1 else 1
            self.level = 2 if (prev >= 1 or self._level_streak >= 2) else 1
        elif degraded:
            self.level = max(1, min(prev, 2)) if prev >= 1 else 1
            self._level_streak = 0
        else:
            self.level = max(prev - 1, 0)
            self._level_streak = 0

        self._apply_level()
        self._apply_cause_adjustments()
        if self.level != prev:
            detail = {"brier": round(model_brier, 4),
                      "baseline": round(baseline_brier, 4),
                      "calib_gap": round(gap, 4),
                      "hit_lcb": round(lcb, 3),
                      "promised_p": round(promised, 3), "n": n}
            log.warning("ML-030: governor level %d -> %d | %s | "
                        "shrinkage=%.2f kelly_mult=%.2f use_model=%s",
                        prev, self.level, detail, self.shrinkage,
                        self.kelly_mult, self.use_model)
            get_audit().log("ml_governor",
                            Code.ML_KILL_SWITCH if self.level >= 2
                            else Code.ML_LEVEL_CHANGE,
                            f"level {prev} -> {self.level}", detail)
        if self.level >= 2:
            self.request_retrain(f"brier {model_brier:.3f} vs baseline "
                                 f"{baseline_brier:.3f}, hit LCB {lcb:.2f} "
                                 f"vs promised {promised:.2f}")

    def _apply_level(self):
        if self.level == 0:
            self.shrinkage = self.shrink_base
            self.kelly_mult = 1.0
            self.use_model = True
        elif self.level == 1:
            self.shrinkage = min((self.shrink_base + self.shrink_max) / 2,
                                 self.shrink_max)
            self.kelly_mult = 0.7
            self.use_model = True
        else:
            self.shrinkage = self.shrink_max
            self.kelly_mult = self.kelly_mult_min
            self.use_model = False          # ML-050 kill switch

    def decay_stale_causes(self, now: float) -> None:
        """Adaptive penalties must never deadlock. Bumps raised by past
        postmortems normally decay when NEW closes refresh the causes
        window — but a raised entry bar can prevent the very trades that
        would refresh it (observed live: +0.4 edge bump on top of
        round-trip cost pricing = zero entries for hours, window frozen
        at 14 cost_overruns; entries need the bar down, the bar needs
        clean exits, exits need entries). Once no close has arrived for
        cause_stale_hours, each call retires one stale cause and decays
        the penalties one step, so the state converges on a silent book
        at an evidence-paced rate instead of never."""
        if not self._causes_window:
            return
        if self._last_cause_ts <= 0:
            # restored from a pre-upgrade snapshot (no timestamp) or the
            # causes predate this process: the age is unknown, so start
            # the staleness clock NOW - otherwise ts stays 0 until a new
            # close arrives, and the bump that blocks closes never decays
            # (the deadlock this method exists to break, one level deeper)
            self._last_cause_ts = now
            return
        if now - self._last_cause_ts < self.cause_stale_sec:
            return
        self._causes_window.popleft()
        if self.edge_ratio_bump > 0:
            self.edge_ratio_bump = max(self.edge_ratio_bump - 0.05, 0.0)
        if self.stop_widen > 1.0:
            self.stop_widen = max(self.stop_widen - 0.05, 1.0)
        log.info("stale-cause decay (no closes for %.1fh): edge_bump=%.2f "
                 "stop_widen=%.2f window=%d",
                 (now - self._last_cause_ts) / 3600.0,
                 self.edge_ratio_bump, self.stop_widen,
                 len(self._causes_window))

    def _apply_cause_adjustments(self):
        recent = Counter(self._causes_window)
        n = max(sum(recent.values()), 1)
        if recent.get("cost_overrun", 0) / n >= 0.4 and n >= 5:
            self.edge_ratio_bump = min(self.edge_ratio_bump + 0.1,
                                       self.edge_ratio_bump_max)
            log.warning("recurring cost overruns: min_edge_cost_ratio "
                        "bumped +%.1f", self.edge_ratio_bump)
        elif recent.get("cost_overrun", 0) == 0 and self.edge_ratio_bump > 0:
            self.edge_ratio_bump = max(self.edge_ratio_bump - 0.05, 0.0)
        if recent.get("whipsaw", 0) / n >= 0.4 and n >= 5:
            self.stop_widen = min(self.stop_widen + 0.1,
                                  self.stop_widen_max)
            log.warning("recurring whipsaws: stop widening x%.1f",
                        self.stop_widen)
        elif recent.get("whipsaw", 0) == 0 and self.stop_widen > 1.0:
            self.stop_widen = max(self.stop_widen - 0.05, 1.0)

    # ------------------------------------------------------------------
    def note_features(self, feats):
        self._feat_buffer.append(np.asarray(feats, float))

    def check_drift(self, train_deciles: list, feature_names: list):
        """Input drift is a LEADING indicator: distributions shift before
        outcome metrics can react (outcomes lag by the label horizon)."""
        if not train_deciles or len(self._feat_buffer) < self.drift_min_rows:
            return
        X = np.array(self._feat_buffer, float)
        if X.shape[1] != len(train_deciles):
            return
        drifting = []
        for j, edges in enumerate(train_deciles):
            if psi(edges, X[:, j]) >= self.drift_psi_threshold:
                drifting.append(feature_names[j] if j < len(feature_names)
                                else f"f{j}")
        self.drifting = drifting
        self.drift_share = len(drifting) / max(len(train_deciles), 1)
        if self.drift_share >= self.drift_frac_features:
            log.warning("ML-031: feature drift %d/%d shifted "
                        "(PSI>=%.2f): %s", len(drifting),
                        len(train_deciles), self.drift_psi_threshold,
                        drifting[:6])
            get_audit().log("ml_governor", Code.ML_DRIFT,
                            f"{self.drift_share:.0%} of features drifted",
                            {"features": drifting[:10]})
            self.request_retrain(
                f"input drift on {self.drift_share:.0%} of features")

    # ------------------------------------------------------------------
    def request_retrain(self, reason: str):
        now = time.time()
        # in-memory cooldown (fast path within a single process)
        if now - self._last_retrain_request < self.retrain_cooldown_s:
            return
        # restart-resilient cooldown: the in-memory timestamp resets to 0 on a
        # fresh process, so across frequent restarts the fast path above cannot
        # throttle (observed: ML-032 emitted 1670x over a 38h / ~100-restart
        # run - 42% of the audit trail). The flag file persists on disk, so an
        # existing recent flag means a request is already pending; adopt its age
        # and suppress the duplicate. note_deployed() clears the flag when a
        # retrain actually lands, which re-arms the next request.
        if self.retrain_cooldown_s > 0:
            try:
                age = now - self.flag_path.stat().st_mtime
                if 0 <= age < self.retrain_cooldown_s:
                    self._last_retrain_request = now - age
                    return
            except OSError:
                pass  # no flag (or unreadable): fall through and emit
        self._last_retrain_request = now
        try:
            self.flag_path.parent.mkdir(parents=True, exist_ok=True)
            self.flag_path.write_text(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} {reason}\n",
                encoding="utf-8")
        except Exception:
            # the flag is a convenience signal; failing to write it must
            # never take the governor (or the trading loop) down
            log.exception("retrain flag write failed (non-fatal)")
        get_audit().log("ml_governor", Code.ML_RETRAIN_REQUEST, reason, {})
        log.critical("ML-032 RETRAIN REQUESTED: %s — run "
                     "`python scripts/train_meta.py` (or let auto-retrain "
                     "pick it up next slow cycle)", reason)

    def should_deploy(self, challenger_brier: float,
                      n_oof: int | None = None) -> bool:
        """Champion/challenger deployment gate."""
        # evidence floor: when the purge first stops swallowing folds the
        # challenger may carry only a handful of OOF points, and a Brier
        # on 5 points beats a coin by luck. Calibration already demands
        # >= 20 points; CROWNING demands deploy_min_oof. None = caller
        # has no count (legacy/manual paths) - score-only gate applies.
        if n_oof is not None and n_oof < self.deploy_min_oof:
            get_audit().log("ml_governor", Code.ML_DEPLOY_REJECT,
                            f"challenger rejected: {n_oof} OOF points < "
                            f"deploy_min_oof {self.deploy_min_oof} - "
                            f"score {challenger_brier:.4f} is not evidence",
                            {"decision": "REJECT", "n_oof": int(n_oof)})
            log.info("challenger brier=%.4f on only %d OOF points "
                     "(< %d) -> REJECT (insufficient evidence)",
                     challenger_brier, n_oof, self.deploy_min_oof)
            return False
        # no-champion clause still demands the challenger beat a coin:
        # 0.25 is the Brier of predicting 0.5 forever — shipping a first
        # model WORSE than that would hand Kelly a net-harmful p
        ok = challenger_brier < self.champion_brier - self.deploy_margin \
            or (self.champion_brier >= 0.25 and challenger_brier < 0.25)
        get_audit().log("ml_governor",
                        Code.ML_DEPLOY if ok else Code.ML_DEPLOY_REJECT,
                        f"challenger brier {challenger_brier:.4f} vs "
                        f"champion {self.champion_brier:.4f}",
                        {"decision": "DEPLOY" if ok else "REJECT"})
        log.info("challenger brier=%.4f vs champion %.4f -> %s",
                 challenger_brier, self.champion_brier,
                 "DEPLOY" if ok else "REJECT")
        return ok

    def note_deployed(self, brier: float):
        self.champion_brier = brier
        self.level = 0
        self._level_streak = 0
        # the window judges the DEPLOYED model - a fresh champion must not
        # inherit its predecessor's rap sheet. Without this, the very next
        # record_close re-evaluated the stale window and re-convicted the
        # new model 0 -> 2 on evidence it never generated (observed live:
        # kelly_mult pinned at 0.7 through two deploys).
        self._records.clear()
        self._apply_level()
        self.flag_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    def status(self) -> dict:
        w = self._windows()
        out = {"level": self.level, "shrinkage": self.shrinkage,
               "drift_share": round(self.drift_share, 3),
               "drifting_features": self.drifting[:8],
               "kelly_mult": self.kelly_mult, "use_model": self.use_model,
               "edge_ratio_bump": self.edge_ratio_bump,
               "stop_widen": self.stop_widen,
               "causes": dict(self._cause_tally)}
        if w is not None:
            p, y = w
            out.update({
                "window_trades": len(y),
                "brier": round(brier_score(y, p), 4),
                "baseline_brier": round(brier_score(
                    y, np.full_like(p, np.clip(y.mean(), 0.05, 0.95))), 4),
                "calibration_gap": round(calibration_gap(y, p), 4),
                "hit_rate": round(float(y.mean()), 3),
                "hit_rate_lcb": round(wilson_lcb(int(y.sum()), len(y)), 3),
                "avg_p": round(float(p.mean()), 3),
            })
        return out

    # --- persistence hooks (keys are a superset of rev 1) ----------------
    def to_dict(self) -> dict:
        return {"records": list(self._records),
                "causes": dict(self._cause_tally),
                "causes_window": list(self._causes_window),
                "level": self.level, "champion_brier": self.champion_brier,
                "shrinkage": self.shrinkage, "kelly_mult": self.kelly_mult,
                "use_model": self.use_model,
                "edge_ratio_bump": self.edge_ratio_bump,
                "stop_widen": self.stop_widen,
                "last_retrain_request": self._last_retrain_request,
                "last_cause_ts": self._last_cause_ts}

    def restore(self, d: dict):
        if not d:
            return
        self._records = deque([tuple(r) for r in d.get("records", [])],
                              maxlen=self.window * 3)
        self._cause_tally = Counter(d.get("causes", {}))
        self._causes_window = deque(d.get("causes_window", []), maxlen=20)
        self.level = int(d.get("level", 0))
        self.champion_brier = float(d.get("champion_brier", 0.25))
        self.shrinkage = float(d.get("shrinkage", self.shrink_base))
        self.kelly_mult = float(d.get("kelly_mult", 1.0))
        self.use_model = bool(d.get("use_model", True))
        self.edge_ratio_bump = float(d.get("edge_ratio_bump", 0.0))
        self._last_cause_ts = float(d.get("last_cause_ts", 0.0))
        self.stop_widen = float(d.get("stop_widen", 1.0))
        self._last_retrain_request = float(d.get("last_retrain_request",
                                                 0.0))
