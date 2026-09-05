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
from typing import Optional

import numpy as np

from core.audit import get_audit
from core.codes import Code
from ml.calibration import brier_score, calibration_gap, psi
from ml.features import DRIFT_EXCLUDED_FEATURES

log = logging.getLogger("liquiditybot.ml.monitor")

# Retrain-request flag fallback, as a REBINDABLE module attribute
# (2026-07-31). config.json sets ml.monitor.retrain_flag_path, so this only
# fires for a config that omits it — which in practice means the suite's
# minimal governor configs, and every such test was dropping a real
# outputs/retrain_requested.flag into the operator's tree. Named here so
# tests/conftest.py can point it at tmp; production behavior is unchanged.
RETRAIN_FLAG_PATH_DEFAULT = "outputs/retrain_requested.flag"

# Brier of predicting the coin (0.5) forever — the champion_brier value that
# means "no real champion". should_deploy's no-champion clause lets any
# challenger better than this through, and the monitor initialises here.
_NO_CHAMPION = 0.25


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


def wilson_ucb(successes: int, n: int, z: float = 1.645) -> float:
    """One-sided 95% Wilson UPPER bound on a binomial proportion.

    The bound the hit-deficit test actually needs. Indicting a model for
    promising more than it delivered is a claim about the realized rate
    being too LOW, so the honest question is whether the promise clears
    even the most OPTIMISTIC reading of the outcomes. Using the lower
    bound for that (as this module did) is vacuous: lcb <= observed rate
    always, so `promised - lcb >= promised - observed` and the test can
    never bind - see tests/test_monitor_credibility.py.
    """
    if n <= 0:
        return 1.0
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = p + z2 / (2 * n)
    rad = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return min((center + rad) / denom, 1.0)


class ModelMonitor:
    def __init__(self, config: dict):
        cfg = config or {}
        self.window = int(cfg.get("window_trades", 30))
        self.min_trades = int(cfg.get("min_trades_to_judge", 15))
        # ML-075 shadow-recovery: a KILLED model records model_scored=False on
        # every close (main.py), so the model-scored window can never refill and
        # only a retrained challenger can re-arm - a long stall on a young
        # corpus. When enabled, the champion is scored in the background
        # (telemetry-only, never traded) and the governor re-arms 2->1 on a
        # clean shadow window that beats baseline on the IDENTICAL bar. 1->0 is
        # still earned live. Default on; set false to keep the old kill lock.
        self.shadow_recovery = bool(cfg.get("shadow_recovery", True))
        self.brier_margin = float(cfg.get("brier_margin", 0.01))
        self.calib_gap_max = float(cfg.get("calibration_gap_max", 0.15))
        self.hit_shortfall_max = float(cfg.get("hit_shortfall_max", 0.08))
        self.retrain_cooldown_s = float(
            cfg.get("retrain_cooldown_hours", 6)) * 3600
        self.retrain_min_new_rows = int(cfg.get("retrain_min_new_rows", 25))
        self.retrain_min_rows = int(cfg.get("retrain_min_rows", 60))
        self.deploy_margin = float(cfg.get("challenger_brier_margin", 0.005))
        self.deploy_min_oof = int(cfg.get("deploy_min_oof", 30))
        self.flag_path = Path(cfg.get("retrain_flag_path",
                                      RETRAIN_FLAG_PATH_DEFAULT))
        self.shrink_base = float(cfg.get("shrinkage_base", 0.35))
        self.cause_stale_sec = float(
            cfg.get("cause_stale_hours", 4.0)) * 3600.0
        self.shrink_max = float(cfg.get("shrinkage_max", 0.70))
        self.kelly_mult_min = float(cfg.get("kelly_mult_min", 0.40))
        self.edge_ratio_bump_max = float(cfg.get("edge_ratio_bump_max", 0.4))
        self.stop_widen_max = float(cfg.get("stop_widen_max", 1.5))

        self.drift_psi_threshold = float(cfg.get("drift_psi_threshold",
                                                 0.25))
        # 10-decile PSI needs ~10 samples/bin to be stable; a 40-row window
        # (4/bin) fabricates 19% mean / 28% p95 "drift" from an IN-DISTRIBUTION
        # sample (null-tested), nearly tripping the 30% retrain vote on pure
        # sampling noise. 100 rows drops that noise floor below 5%, so a fired
        # ML-031 means a real shift, not a small-window artifact.
        self.drift_min_rows = int(cfg.get("drift_min_rows", 100))
        self.drift_frac_features = float(cfg.get("drift_frac_features",
                                                 0.30))
        self._feat_buffer: deque = deque(maxlen=300)
        self.drift_share = 0.0
        self.drifting: list = []
        # DENOMINATOR PROVENANCE (2026-09-05). drift_share divides by every
        # VOTING feature, but psi() returns exactly 0.0 for any feature whose
        # decile edges are tied - deliberately, since a degenerate feature
        # otherwise reports enormous PSI on an identical distribution. Those
        # features therefore CANNOT contribute to the numerator while still
        # inflating the denominator. Measured on the live artifact the same
        # day: 34 of 60 voting features are degenerate (56.7%), so drift_share
        # is capped at 0.4333 forever against a 0.30 threshold - tripping it
        # needs 19 of the 26 MEASURABLE features (73%), not the "30% of market
        # features" the config doc promises.
        #
        # Report-only, and deliberately so: drift_share and its trigger are
        # UNCHANGED here because moving them changes when ML-032 fires and
        # therefore when the retrain loop runs. These fields make the
        # denominator visible so the threshold can be adjudicated on evidence.
        self.drift_measurable = 0
        self.drift_degenerate = 0
        self.drift_share_measurable = 0.0
        self._records: deque = deque(maxlen=self.window * 3)
        # champion shadow scores (p, label) recorded ONLY while killed; used
        # solely by _try_shadow_recovery, never by the kill path.
        self._shadow_records: deque = deque(maxlen=self.window * 3)
        self._cause_tally: Counter = Counter()
        self._causes_window: deque = deque(maxlen=20)
        self._last_cause_ts = 0.0
        self.level = 0
        self._level_streak = 0
        # W2-17: de-escalation deadband. Brier hovering within noise of
        # baseline+brier_margin flips degraded on/off from pure window churn,
        # so a single healthy evaluation dropping the level immediately
        # flapped kelly_mult/shrinkage every other trade. Escalation
        # (_level_streak, above) already had streak discipline; this is the
        # matching guard for the downward direction only - fail toward
        # caution stays immediate.
        self.deescalate_healthy_windows = int(
            cfg.get("deescalate_healthy_windows", 3))
        self._healthy_streak = 0
        self._last_retrain_request = 0.0
        self._rows_at_last_request = 0
        self.champion_brier: float = 0.25

        # live overrides consumed by main/meta/sizer (bounded, ASYMMETRIC
        # HYSTERESIS - not one-way: escalation toward caution is immediate,
        # de-escalation waits deescalate_healthy_windows CONSECUTIVE healthy
        # windows for the level, and edge_ratio_bump/stop_widen decay back
        # toward neutral when their trigger clears; see the level ladder and
        # bump-decay logic below)
        self.shrinkage = self.shrink_base
        self.kelly_mult = 1.0
        self.use_model = True
        self.edge_ratio_bump = 0.0
        self.stop_widen = 1.0

    # ------------------------------------------------------------------
    def record_close(self, p_predicted: float, label: int,
                     model_scored: bool, cause: str = "",
                     now: Optional[float] = None):
        self._records.append((float(p_predicted), int(label),
                              bool(model_scored)))
        if cause:
            self._cause_tally[cause] += 1
            self._causes_window.append(cause)
            # W2-18: stamp the caller's own clock when it has one (replay
            # parity) - decay_stale_causes(now) always compares against
            # the engine's injected `now`, so sampling time.time() here
            # under replay never converges with it and the stale-cause
            # decay this method exists to unblock (see decay_stale_causes)
            # never fires. Falls back to wall clock for every existing
            # caller that doesn't pass one (behaviour-preserving).
            self._last_cause_ts = now if now is not None else time.time()
        # exactly ONCE per close, after the causes window is updated and
        # independent of the Brier window: _evaluate() used to call this a
        # SECOND time, so once >= min_trades model-scored closes existed a
        # cost_overrun raised edge_ratio_bump +0.2/close (max in 2 not 4) -
        # doubling the entry-suppression the decay was built to relieve.
        # It also must run in cold start (where _evaluate early-returns),
        # or a clean close never decays a raised bump before the model
        # trains. Placed here, not in _evaluate, it is level-independent.
        self._apply_cause_adjustments()
        self._evaluate()

    def _prior_base_rate(self) -> float:
        """Base rate from history that PREDATES the judged window.

        The baseline a model must beat has to be knowable in advance,
        otherwise the comparison is against a clairvoyant (see _judge).
        Rows older than the current window are legitimate prior evidence;
        when there are none, fall back to a neutral 0.5 rather than to the
        window's own mean - a neutral prior is the honest statement of "no
        information", and it is the weakest baseline, so cold start never
        convicts on baseline grounds alone.
        """
        scored = [r for r in self._records if r[2]]
        older = scored[:-self.window] if len(scored) > self.window else []
        if not older:
            # no pre-window history: use everything scored EXCEPT the
            # current window's own rows when possible, else neutral
            return 0.5
        return float(sum(r[1] for r in older) / len(older))

    def _windows(self):
        recs = [r for r in self._records if r[2]][-self.window:]
        if len(recs) < self.min_trades:
            return None
        p = np.array([r[0] for r in recs])
        y = np.array([r[1] for r in recs])
        return p, y

    # ------------------------------------------------------------------
    def _judge(self, p, y):
        """Grade a (prediction, outcome) window against the base-rate baseline.
        The SINGLE source of the degraded/failing verdict — _evaluate (live
        model-scored window) and _try_shadow_recovery (killed champion shadow
        window) both call it, so the re-arm bar is byte-identical to the kill
        bar. Returns (degraded, failing, detail, model_brier, baseline_brier,
        lcb, promised)."""
        n = len(y)
        # BASELINE FROM A PRIOR, NOT AN ORACLE (round-2 fix 2026-08-05).
        # This used to score a constant equal to the window's OWN realized
        # mean - information no live model could have at prediction time.
        # An all-loss 15-close window (ordinary luck at this corpus's base
        # rates) handed the baseline a clairvoyant 0.05 and convicted an
        # honestly-calibrated model on its first evaluation. _prior_base_rate
        # uses only history that predates the window. This makes the
        # baseline WEAKER and therefore the governor slower to convict -
        # the correct direction for an instrument whose false positive is
        # killing a working model, with the Brier margin, calibration gap
        # and hit-deficit tests all still binding.
        base_rate = float(np.clip(self._prior_base_rate(), 0.05, 0.95))
        model_brier = brier_score(y, p)
        baseline_brier = brier_score(y, np.full_like(p, base_rate))
        gap = calibration_gap(y, p)
        lcb = wilson_lcb(int(y.sum()), n)
        promised = float(p.mean())
        # HIT DEFICIT, on the UPPER bound (round-2 fix 2026-08-05). The old
        # form ANDed the raw gap with `promised - lcb > allow`, which is
        # implied by the raw-gap clause (lcb <= observed rate always), so
        # the "statistically credible" half was dead code - and it loosened
        # as n fell, inverting the small-n protection it was added for.
        # Against the UPPER bound the test means what it says: the promise
        # must clear even the most optimistic reading of the outcomes by
        # the allowance, which is strictly harder at small n because the
        # interval is wider. It also implies the raw-gap condition (ucb >=
        # observed rate), so one clause is the whole test.
        ucb = wilson_ucb(int(y.sum()), n)
        hit_deficit = (promised - ucb) > self.hit_shortfall_max

        degraded = (model_brier > baseline_brier + self.brier_margin) or \
            (gap > self.calib_gap_max) or hit_deficit
        failing = model_brier > baseline_brier + 3 * self.brier_margin or \
            (hit_deficit and gap > self.calib_gap_max)
        detail = {"brier": round(model_brier, 4),
                  "baseline": round(baseline_brier, 4),
                  "calib_gap": round(gap, 4),
                  "hit_lcb": round(lcb, 3),
                  "promised_p": round(promised, 3), "n": n}
        return degraded, failing, detail, model_brier, baseline_brier, \
            lcb, promised

    def _evaluate(self):
        w = self._windows()
        if w is None:
            return
        p, y = w
        degraded, failing, detail, model_brier, baseline_brier, lcb, promised \
            = self._judge(p, y)

        prev = self.level
        if failing:
            self._level_streak = self._level_streak + 1 if prev >= 1 else 1
            self.level = 2 if (prev >= 1 or self._level_streak >= 2) else 1
            self._healthy_streak = 0
        elif degraded:
            self.level = max(1, min(prev, 2)) if prev >= 1 else 1
            self._level_streak = 0
            self._healthy_streak = 0
        else:
            self._level_streak = 0
            # W2-17 deadband: a downward step (de-escalation) only fires
            # after `deescalate_healthy_windows` CONSECUTIVE healthy
            # evaluations - one healthy trade no longer unwinds a level
            # gained on real evidence. prev==0 has nothing to de-escalate
            # from and never needs the streak.
            if prev == 0:
                self.level = 0
                self._healthy_streak = 0
            else:
                self._healthy_streak += 1
                if self._healthy_streak >= self.deescalate_healthy_windows:
                    self.level = prev - 1
                    self._healthy_streak = 0
                else:
                    self.level = prev

        self._apply_level()
        # NOTE: cause adjustments are applied once in record_close, NOT here
        # (calling it here too double-applied the bump once the Brier window
        # filled - see record_close).
        if self.level != prev:
            log.warning("ML-030: governor level %d -> %d | %s | "
                        "shrinkage=%.2f kelly_mult=%.2f use_model=%s",
                        prev, self.level, detail, self.shrinkage,
                        self.kelly_mult, self.use_model)
            get_audit().log("ml_governor",
                            Code.ML_KILL_SWITCH if self.level >= 2
                            else Code.ML_LEVEL_CHANGE,
                            f"level {prev} -> {self.level}", detail)
            # a FRESH kill resets the shadow evidence so recovery is judged only
            # on trades that happened AFTER the model was disabled (stale
            # pre-kill shadow scores must not instantly re-arm it).
            if prev < 2 and self.level >= 2:
                self._shadow_records.clear()
        if self.level >= 2:
            self.request_retrain(f"brier {model_brier:.3f} vs baseline "
                                 f"{baseline_brier:.3f}, hit LCB {lcb:.2f} "
                                 f"vs promised {promised:.2f}")

    # ---------------------------------------- ML-075 shadow-recovery -------
    def record_shadow_close(self, shadow_p: float, label: int) -> None:
        """Record the champion's telemetry-only score for a closed trade while
        the model is KILLED. The champion is NEVER traded here (the position ran
        on the prior); this only lets the governor observe whether the champion
        WOULD have beaten baseline on the trades that actually happened, so it
        can re-arm 2->1 on evidence instead of staying locked until a retrain.
        No-op unless killed and shadow_recovery is enabled."""
        if not self.shadow_recovery:
            return
        self._shadow_records.append((float(shadow_p), int(label)))
        if self.level >= 2:
            self._try_shadow_recovery()

    def _shadow_window(self):
        recs = list(self._shadow_records)[-self.window:]
        if len(recs) < self.min_trades:
            return None
        p = np.array([r[0] for r in recs])
        y = np.array([r[1] for r in recs])
        return p, y

    def _try_shadow_recovery(self):
        """Re-arm a KILLED model one throttled step (2->1) when the champion's
        shadow window cleanly beats baseline on the SAME bar the kill used.
        Recovery-only: never raises the level, never steps below 1, never fires
        below level 2. 1->0 is still earned live on model-scored trades."""
        w = self._shadow_window()
        if w is None:
            return
        p, y = w
        degraded, _failing, detail, *_ = self._judge(p, y)
        if degraded:
            return                       # champion still not beating baseline
        prev = self.level
        self.level = 1                   # half-step: throttled, never to 0
        self._level_streak = 0
        # fresh probation window: the stale pre-kill model-scored records must
        # not re-convict the re-armed model on its very next live close (same
        # rationale as note_deployed clearing the window on a deploy).
        self._records.clear()
        self._shadow_records.clear()
        self._apply_level()
        log.warning("ML-075: shadow-recovery re-armed governor %d -> 1 | %s | "
                    "kelly_mult=%.2f (champion beat baseline in shadow; "
                    "probation - full trust earned live)",
                    prev, detail, self.kelly_mult)
        get_audit().log("ml_governor", Code.ML_SHADOW_RECOVER,
                        f"shadow-recovery {prev} -> 1", detail)

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
        # only MARKET features vote: clock/counter features (hour_sin/cos,
        # funding_dist, regime_age) drift on any finite window by construction
        # (their PSI reads window phase, not market state), so counting them
        # kept the share pinned above the retrain trigger on clean data.
        drifting, n_voting = [], 0
        n_degenerate = 0
        for j, edges in enumerate(train_deciles):
            name = feature_names[j] if j < len(feature_names) else f"f{j}"
            if name in DRIFT_EXCLUDED_FEATURES:
                continue
            n_voting += 1
            # A tied-edge feature can never reach the threshold (psi returns
            # 0.0 by construction), so it is counted for provenance rather
            # than silently diluting the share.
            if np.unique(np.asarray(edges, dtype=float)).size < len(edges):
                n_degenerate += 1
            if psi(edges, X[:, j]) >= self.drift_psi_threshold:
                drifting.append(name)
        self.drifting = drifting
        self.drift_share = len(drifting) / max(n_voting, 1)
        self.drift_degenerate = n_degenerate
        self.drift_measurable = n_voting - n_degenerate
        self.drift_share_measurable = (
            len(drifting) / self.drift_measurable if self.drift_measurable
            else 0.0)
        if self.drift_share >= self.drift_frac_features:
            log.warning("ML-031: feature drift %d/%d shifted "
                        "(PSI>=%.2f): %s", len(drifting),
                        n_voting, self.drift_psi_threshold,
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

    @staticmethod
    def rescore_frozen(model, calibrator, X, y, oof_idx,
                       seen_rows: int, min_n: int):
        """Brier of a FROZEN incumbent on the fresh OOF rows it never
        trained on. None = not enough fresh evidence (keep the stored
        badge). PURE and fail-safe: any error returns None.

        WHY: the champion's stored oof_brier is its birth certificate
        from an OLDER corpus era. Gating challengers against it lets an
        aging champion squat forever — measured live 2026-07-18: badge
        0.1887 vs 0.27-0.33 for every honestly-scored candidate on the
        current corpus, so no future challenger could ever win.
        `seen_rows` (corpus size at the champion's training, on the
        sig-sorted ordering) approximates its training horizon; only
        rows past it count as unseen — merged peer rows can interleave
        below that index, so this is a conservative approximation, never
        an in-sample flatter of more than the interleave."""
        try:
            import numpy as _np
            if model is None:
                return None
            idx = _np.asarray(oof_idx, int)
            fresh = idx[idx >= int(seen_rows)]
            if len(fresh) < int(min_n):
                return None
            p = _np.asarray(model.predict_proba(X[fresh]),
                            float).reshape(-1)
            if calibrator is not None and getattr(calibrator, "fitted",
                                                  False):
                p = _np.asarray(calibrator.transform(p), float).reshape(-1)
            p = _np.clip(p, 1e-6, 1 - 1e-6)
            if not _np.all(_np.isfinite(p)):
                return None
            return float(_np.mean((p - _np.asarray(y, float)[fresh]) ** 2))
        except Exception:                        # noqa: BLE001 - fail-safe
            return None

    @staticmethod
    def shared_challenger_brier(oof_idx, seen_rows: int, min_n: int,
                                challenger_oof_p, y) -> tuple[float, int] | None:
        """Challenger Brier restricted to the SAME fresh rows (oof_idx >=
        seen_rows) that rescore_frozen scores the frozen champion on — the
        row set the two scores must share before should_deploy may compare
        them at all.

        WHY: rescore_frozen already scores the champion on this fresh
        slice, so its base rate is whatever the fresh tail's is (measured
        live: 0.0841). Before this existed, should_deploy compared that
        fresh-tail score against the challenger's Brier over the FULL
        oof_idx span instead — a population with a materially different
        label base rate (measured live: 0.1508, a ~79% relative gap).
        Brier is not comparable across differing base rates, so the
        champion won by population, not merit (four days, 68/68 REJECT;
        on the SAME rows the challenger actually wins). This restricts the
        challenger to the IDENTICAL physical rows the champion was scored
        on, so should_deploy compares like for like.

        challenger_oof_p must be POSITION-ALIGNED with oof_idx:
        ml.walkforward.evaluate_and_select builds oof_idx and every
        candidate's oof_p/oof_y by concatenating the SAME fold list in the
        SAME order, so position i in both always names the same physical
        training row.

        Returns (challenger_brier, n_shared) on a shared set of >= min_n
        finite-scored rows, else None — fail-closed: an incomparable pair
        (too few shared rows, a length mismatch, non-finite output) must
        never silently fall back to comparing mismatched populations."""
        try:
            idx = np.asarray(oof_idx, int)
            p = np.asarray(challenger_oof_p, float).reshape(-1)
            if len(p) != len(idx):
                return None
            mask = idx >= int(seen_rows)
            n_shared = int(mask.sum())
            if n_shared < int(min_n):
                return None
            p_shared = p[mask]
            if not np.all(np.isfinite(p_shared)):
                return None
            y_shared = np.asarray(y, float)[idx[mask]]
            return float(np.mean((p_shared - y_shared) ** 2)), n_shared
        except Exception:                        # noqa: BLE001 - fail-safe
            return None

    def should_deploy(self, challenger_brier: float,
                      n_oof: int | None = None,
                      ignore_champion: bool = False) -> bool:
        """Champion/challenger deployment gate.

        `ignore_champion` (default False — every existing caller
        unchanged, invariant 7): True applies the pure COLD-START
        standard (beat a coin: Brier < 0.25, plus the deploy_min_oof
        evidence floor) with the stored badge set aside entirely. The
        one legitimate caller is the ML-083 era-orphan branch
        (main.py): when era exclusion rebuilt the corpus population
        under the champion's trained_rows watermark, the badge is a
        Brier measured against a DIFFERENT label base rate (measured
        live: 0.1237 on a 0.169-base population vs a 0.30-base current
        corpus whose naive base-rate Brier is ~0.21) — comparing across
        base rates is exactly what the like-for-like gate exists to
        refuse, and consulting the badge here kept the deadlock alive
        in a softer form (2026-07-29 wave-4/5 adversarial verification:
        the no-champion disjunct below only frees the bar when the
        badge is >= 0.25). Same doctrine as reconcile_champion_badge's
        ghost-badge reset (ML-076): an unfalsifiable badge may not
        gate."""
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
        if ignore_champion:
            ok = challenger_brier < 0.25
            get_audit().log("ml_governor",
                            Code.ML_DEPLOY if ok else Code.ML_DEPLOY_REJECT,
                            f"challenger brier {challenger_brier:.4f} vs "
                            f"COLD-START bar 0.25 (badge set aside: "
                            f"era-orphaned, see ML-083)",
                            {"decision": "DEPLOY" if ok else "REJECT",
                             "ignore_champion": True})
            log.info("challenger brier=%.4f vs cold-start bar 0.25 "
                     "(era-orphaned badge set aside) -> %s",
                     challenger_brier, "DEPLOY" if ok else "REJECT")
            return ok
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

    def reconcile_champion_badge(self, loaded_oof_brier,
                                 model_loaded: bool = True) -> bool:
        """Force the champion badge to track the model actually loaded (ML-076).

        A restored monitor snapshot can outlive its model — a newer artifact was
        saved without a matching note_deployed, a restart restored an older
        snapshot than the model on disk, or (measured live 2026-07-21) the
        deployed champion is a 58-feature logistic that fails the v8 width guard
        and never loads at all. The badge then claims a Brier no loaded model can
        back up, and should_deploy gates every challenger against that ghost —
        the model stays KILLED forever (badge 0.1441, every honest challenger
        rejected). Two repairs, keyed on whether a champion is actually loaded:

          * NO backing model (`model_loaded` False): the badge is a ghost with
            nothing behind it. Reset it to the no-champion default so a fresh,
            current-schema challenger can deploy (should_deploy's no-champion
            clause). This is what breaks the schema-mismatch deadlock.
          * model loaded but badge better than its own OOF: realign the badge UP
            to that honest score (never DOWN — that would re-open the squat).

        NEVER touches level/kelly/use_model/records — a startup badge fix must
        not silently un-kill a governed model. Returns True if the badge moved."""
        try:
            b = float(loaded_oof_brier)
            b = b if (0.0 < b < 1.0) else None
        except (TypeError, ValueError):
            b = None
        # Case A: no champion actually loaded (schema-rejected / missing /
        # untrained). Discard a ghost badge to the no-champion default.
        if not model_loaded:
            if self.champion_brier < _NO_CHAMPION - 1e-9:
                old = self.champion_brier
                self.champion_brier = _NO_CHAMPION
                log.warning("ML-076: champion badge discarded %.4f -> %.2f — no "
                            "backing model loaded (schema-rejected/missing); the "
                            "ghost badge was squatting and rejecting every "
                            "current-schema challenger", old, _NO_CHAMPION)
                get_audit().log("ml_governor", Code.ML_CHAMP_BADGE_SYNC,
                                f"badge discarded {old:.4f} -> {_NO_CHAMPION:.2f} "
                                f"(no backing model)",
                                {"old": round(old, 4), "new": _NO_CHAMPION,
                                 "reason": "no_backing_model"})
                return True
            log.info("ML-076 reconcile: no-op (no backing model; badge %.4f "
                     ">= no-champion default)", self.champion_brier)
            return False
        # Case B: model loaded but its honest OOF is unavailable -> stay
        # conservative (do not invent a realignment from a missing number).
        if b is None:
            log.info("ML-076 reconcile: no-op (model loaded, oof unavailable; "
                     "badge %.4f kept)", self.champion_brier)
            return False
        # Case C: model loaded, badge claims better than it can back up -> up.
        if self.champion_brier < b - 1e-9:
            old = self.champion_brier
            self.champion_brier = b
            log.warning("ML-076: champion badge realigned to the loaded model "
                        "%.4f -> %.4f (stale snapshot outlived its model; the "
                        "old badge could squat and reject every challenger)",
                        old, b)
            get_audit().log("ml_governor", Code.ML_CHAMP_BADGE_SYNC,
                            f"badge realigned {old:.4f} -> {b:.4f} "
                            f"(loaded-model sync)",
                            {"old": round(old, 4), "new": round(b, 4)})
            return True
        log.info("ML-076 reconcile: no-op (badge %.4f consistent with loaded "
                 "model oof %.4f)", self.champion_brier, b)
        return False

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
        self._shadow_records.clear()
        self._apply_level()
        self.flag_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    def status(self) -> dict:
        w = self._windows()
        out = {"level": self.level, "shrinkage": self.shrinkage,
               "drift_share": round(self.drift_share, 3),
               # The denominator drift_share is computed over, split so a
               # reader can tell a real 30% from a ceiling of 43%.
               "drift_measurable": self.drift_measurable,
               "drift_degenerate": self.drift_degenerate,
               "drift_share_measurable": round(self.drift_share_measurable, 3),
               "drifting_features": self.drifting[:8],
               "kelly_mult": self.kelly_mult, "use_model": self.use_model,
               "edge_ratio_bump": self.edge_ratio_bump,
               "stop_widen": self.stop_widen,
               "champion_brier": round(self.champion_brier, 4),
               "causes": dict(self._cause_tally)}
        if w is not None:
            p, y = w
            out.update({
                "window_trades": len(y),
                "brier": round(brier_score(y, p), 4),
                # The PUBLISHED baseline must be the SAME quantity _judge
                # decides on (_prior_base_rate, see :251-253). It used to be
                # clip(y.mean()) — the in-window ORACLE base rate, which no
                # forecaster could have known in advance. That made the gauge
                # and the kill line two different numbers, and the Grafana rule
                # (docs/grafana/liquiditybot_brier_alert.yaml:72) pages "the
                # governor has moved to kill it" off the gauge while the
                # governor is still at level 0. Same clip bounds, so a genuine
                # brier-vs-baseline crossing reads identically; only the
                # phantom page goes away.
                "baseline_brier": round(brier_score(
                    y, np.full_like(p, np.clip(self._prior_base_rate(),
                                               0.05, 0.95))), 4),
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
