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

from core.codes import Code
from ml.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from ml.labeling import simulate_exit_policy, triple_barrier

log = logging.getLogger("liquiditybot.ml.history")


class HistoryStore:
    def __init__(self, path: str = "outputs/signal_history.csv"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._pending: dict = {}      # position_id -> features
        # stats of the most recent load_training_data pass (clean live count
        # for the evidence gate, uniqueness mean, prior-skew flag)
        self.last_load_stats: dict = {}
        # meta column named "side": FEATURE_NAMES also contains "direction",
        # and a duplicated CSV header made DictReader consumers silently read
        # whichever column came last.
        self._header = ["position_id", "asset", "side", *FEATURE_NAMES,
                        "label", "net_pnl_usd", "source", "ts", "signal_ts",
                        "barrier", "probe"]
        # probe: "1" = PT-050 exploration probe (profit-EV gate bypassed
        # to buy the label), "0" = conviction entry, "" = candidate row or
        # pre-2026-07-20 unknown. BOOKKEEPING ONLY - never a feature, and
        # probe rows keep FULL live training weight (a probe's outcome is
        # honest ground truth); OF-5 uses it to grade the conviction-only
        # sample while exploration still mixes EV-negative probes in.

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
                features: np.ndarray, probe: bool = False):
        # signal time captured HERE: rows are appended at label time, and
        # the purged walk-forward must order/purge by when the SIGNAL
        # happened, not when its barrier resolved
        self._pending[position_id] = (asset, direction, features.copy(),
                                      time.time(), bool(probe))

    def _append_row(self, position_id: str, asset: str, direction: str,
                    feats: np.ndarray, label: int, pnl_usd: float,
                    source: str, signal_ts: float | None = None,
                    barrier: str = "", probe: str = ""):
        self._ensure_schema()
        # width invariant: a row must have exactly as many fields as the
        # header. The header check above only guards the FILE's schema -
        # a stale feature vector (e.g. a candidate persisted before a
        # FEATURE_NAMES bump and restored after) would silently write a
        # short, misaligned row. Observed live 2026-07-12: 4 pre-SMC
        # 36-feature candidates labeled under the 43-feature header.
        if 3 + len(feats) + 7 != len(self._header):
            log.warning(
                f"{Code.ML_SCHEMA_MISMATCH.value}: refusing to append row "
                f"{position_id[:12]} ({asset}): {len(feats)} features vs "
                f"schema {len(self._header) - 9} - stale pre-rotation "
                f"vector, row would misalign under the current header")
            return
        # finiteness invariant: a NaN/inf slips through float() silently
        # (float('nan') never raises) and poisons the corpus - one non-finite
        # feature NaNs an entire gradient/AUC/Brier downstream, and a NaN label
        # trains on garbage truth. Refuse at the store boundary so the
        # ground-truth dataset is clean BY CONSTRUCTION, not cleaned later. The
        # engine should never emit one; if it does, dropping the label is far
        # cheaper than silently corrupting every retrain that reads it.
        fa = np.asarray(feats, dtype=float)
        if not np.all(np.isfinite(fa)) or not np.isfinite(float(pnl_usd)):
            bad = [FEATURE_NAMES[i] for i in np.flatnonzero(~np.isfinite(fa))
                   if i < len(FEATURE_NAMES)]
            log.warning(
                f"{Code.ML_DIRTY_LABEL.value}: refusing non-finite {source} "
                f"row {position_id[:12]} ({asset}): "
                f"{bad or 'pnl'} not finite - label dropped, corpus kept clean")
            return
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            now = time.time()
            csv.writer(f).writerow([position_id, asset, direction,
                                    *[f"{v:.6f}" for v in feats],
                                    label, f"{pnl_usd:.2f}", source,
                                    f"{now:.0f}",
                                    f"{signal_ts if signal_ts else now:.0f}",
                                    barrier, probe])

    def log_close(self, position_id: str, net_pnl_usd: float):
        entry = self._pending.pop(position_id, None)
        if entry is None:
            return
        probe = False
        if len(entry) == 5:
            asset, direction, feats, sig_ts, probe = entry
        elif len(entry) == 4:
            asset, direction, feats, sig_ts = entry
        else:                                   # pre-upgrade snapshot shape
            asset, direction, feats = entry
            sig_ts = None
        label = int(net_pnl_usd > 0)
        self._append_row(position_id, asset, direction, feats, label,
                        net_pnl_usd, "live", signal_ts=sig_ts,
                        barrier="realized",
                        probe="1" if probe else "0")
        log.info(f"labeled trade {position_id[:8]}: label={label} "
                f"pnl=${net_pnl_usd:,.2f}")

    def row_count(self) -> int:
        if not self.path.exists():
            return 0
        with open(self.path, encoding="utf-8") as f:
            return max(sum(1 for _ in f) - 1, 0)

    def source_counts(self) -> dict:
        """Labeled rows per source ('live' vs 'candidate') — the learning-
        velocity split: live labels are ground truth, candidate labels are
        the triple-barrier proxy.

        Called from the runner's per-loop status build (~2s), so the scan is
        CACHED on (mtime, size) and only re-runs when the file actually
        changed — labels land hours apart, not per cycle. The column index
        comes from the FILE'S OWN header (never a hardcoded position), so a
        future schema change can't silently count the wrong column; a header
        without 'source' returns {} rather than a fabricated split."""
        try:
            st = self.path.stat()
            key = (st.st_mtime_ns, st.st_size)
        except OSError:
            return {}
        if getattr(self, "_src_cache_key", None) == key:
            return dict(self._src_cache)
        counts: dict = {}
        try:
            with open(self.path, encoding="utf-8") as f:
                rdr = csv.reader(f)
                hdr = next(rdr, None) or []
                if "source" not in hdr:
                    return {}
                idx = hdr.index("source")
                for r in rdr:
                    if len(r) > idx:
                        src = r[idx] or "unknown"
                        counts[src] = counts.get(src, 0) + 1
        except (OSError, csv.Error):
            return {}
        self._src_cache_key, self._src_cache = key, counts
        return dict(counts)

    def asset_counts(self) -> dict:
        """Labeled rows per asset (row layout: position_id, asset, ...).
        Full-file scan, but callers only hit it on the rare exploration
        rolls - same cost class as row_count."""
        if not self.path.exists():
            return {}
        counts: dict = {}
        with open(self.path, encoding="utf-8") as f:
            next(f, None)                       # header
            for line in f:
                parts = line.split(",", 2)
                if len(parts) >= 2 and parts[1]:
                    counts[parts[1]] = counts.get(parts[1], 0) + 1
        return counts

    def load_training_data(self, half_life_days: float = 30.0,
                        candidate_weight: float = 0.4,
                        manip_discount: float = 0.5, return_sig: bool = False,
                        weights_cfg: dict | None = None,
                        return_label_times: bool = False):
        """Returns X, y, w (and the sorted signal-time array `sig` when
        return_sig=True, for the TIME-based walk-forward purge). Sample
        weights encode the honest priors:
        recent rows matter more (markets are non-stationary; exponential
        recency decay with a config half-life), live-fill rows carry
        real execution costs while candidate rows are barrier
        counterfactuals (down-weighted, not discarded), and rows labeled
        under manipulation-suspect data (manip_suspect feature) are
        discounted in proportion - a lesson learned from a painted book
        may be the manipulator's lesson, not the market's:
        w *= (1 - manip_discount * manip_suspect).

        `weights_cfg` (config ml.sample_weights) adds the de Prado
        corrections (AFML ch.4, "Sample Weights"): overlapping labels on
        the same asset share the same underlying return path and are NOT
        independent evidence, so each row is scaled by its AVERAGE
        UNIQUENESS mean(1/concurrency) over its [signal_ts, ts] lifespan —
        197 overlapping quiet-weekend candidates stop counting as 197
        independent facts. A time-barrier zero (barrier=="time": price
        touched NEITHER profit nor stop inside the horizon) is a "no move",
        weaker evidence against the signal than a realized stop-out, and
        takes time_barrier_zero_weight. A trailing window whose label
        prior skews hard from the corpus prior (the all-zeros weekend
        batch) is DETECTED and logged (ML-074) so calibration drift is
        visible - detection only, never silent reweighting. Stats of the
        last load land in self.last_load_stats (clean live count for the
        evidence gate, uniqueness mean, prior-skew flag)."""
        empty = (np.empty((0, len(FEATURE_NAMES))), np.empty(0), np.empty(0))
        self.last_load_stats = {}
        if not self.path.exists():
            # honor return_sig on the empty path too: a fresh checkout has no
            # signal_history.csv (outputs/ is gitignored), and the DoD's
            # `python scripts/overfit_check.py` unpacks 4 values
            return (*empty, np.empty(0)) if return_sig else empty
        # SYNTHETIC-vs-REAL clash guard. A taken trade is written TWICE: once
        # as a live row (realized close = REAL label, full weight) and once as
        # the candidate it was registered as at signal time (triple-barrier
        # counterfactual = SYNTHETIC label, candidate_weight). Identical
        # features (same feats object flows to both), possibly CONTRADICTORY
        # labels (a stop-out realizes 0 while the barrier said 1). Training on
        # both double-counts the taken signal and teaches the model a
        # coin-flip at that exact X. Ground truth wins: drop the synthetic
        # twin of any real row. Untaken-signal candidates (no live twin) stay
        # fully usable - the model still learns from all the shadow data, it
        # just never CLASHES with what actually happened.
        live_keys = set()
        with open(self.path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("source") == "candidate":
                    continue
                try:
                    live_keys.add((row["asset"], row["side"],
                                   tuple(row[n] for n in FEATURE_NAMES)))
                except KeyError:
                    continue
        X, y, w, sig = [], [], [], []
        meta = []            # (asset, end_ts, source, barrier) per kept row
        now = time.time()
        dropped_clash = 0
        dropped_dirty = 0
        with open(self.path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("source") == "candidate" and live_keys:
                    try:
                        if (row["asset"], row["side"],
                                tuple(row[n] for n in FEATURE_NAMES)) in live_keys:
                            dropped_clash += 1
                            continue     # synthetic twin of a real trade
                    except KeyError:
                        pass
                # ATOMIC per row: build every column into a local first, and
                # only extend the four parallel lists once ALL parse. A bare
                # X.append() before a later ValueError (e.g. an empty label
                # cell from a truncated write or a hand edit) left X one longer
                # than y/sig/w, and the argsort(sig) reindex below then paired
                # X row i with y row j for every row past the bad one - silent
                # feature/label misalignment across the whole tail.
                try:
                    xr = [float(row[n]) for n in FEATURE_NAMES]
                    yr = float(row["label"])
                    # signal-time ordering for the purged walk-forward;
                    # pre-upgrade rows fall back to label time (ts)
                    sr = float(row.get("signal_ts") or row.get("ts") or now)
                    age_d = max(now - float(row.get("ts") or now), 0.0) / 86400.0
                    wr = 0.5 ** (age_d / max(half_life_days, 1e-6))
                    if row.get("source") == "candidate":
                        wr *= candidate_weight
                    suspect = min(max(float(
                        row.get("manip_suspect") or 0.0), 0.0), 1.0)
                    wr *= 1.0 - min(max(manip_discount, 0.0), 1.0) * suspect
                except (KeyError, ValueError):
                    continue
                # LOAD-PATH BACKSTOP: float('nan')/float('inf') parse cleanly,
                # so the try above never catches a dirty cell. The write guard
                # (ML-015) keeps NEW rows clean, but a bundle imported from an
                # older build, a hand edit, or a legacy pre-guard row can still
                # carry a non-finite feature/label. One NaN row NaNs the whole
                # fit; drop it here rather than train on poison.
                if not all(map(np.isfinite, xr)) or not np.isfinite(yr):
                    dropped_dirty += 1
                    continue
                # weight/order cells sit outside the feature/label finiteness
                # net: a corrupt ts yields a NaN weight that NaNs the whole
                # sklearn fit exactly like a NaN feature would. Same drop.
                if not (np.isfinite(wr) and np.isfinite(sr)):
                    dropped_dirty += 1
                    continue
                X.append(xr)
                y.append(yr)
                sig.append(sr)
                w.append(wr)
                meta.append((row.get("asset") or "", float(row.get("ts") or now),
                             row.get("source") or "", row.get("barrier") or ""))
        if dropped_clash:
            log.info("training load: dropped %d synthetic candidate row(s) "
                     "that duplicated a real live trade (kept the realized "
                     "label; %d rows remain)", dropped_clash, len(X))
        if dropped_dirty:
            log.warning("%s: training load skipped %d row(s) with non-finite "
                        "features/label (legacy/imported dirty data) - %d "
                        "clean rows remain", Code.ML_DIRTY_LABEL.value,
                        dropped_dirty, len(X))
        # ---- de Prado corrections (config ml.sample_weights; AFML ch.4) ----
        wc = weights_cfg or {}
        uniq_mean = 1.0
        pre_mass = sum(w)          # for mass-preserving rescale below
        if w and bool(wc.get("uniqueness_enabled", False)):
            # AVERAGE UNIQUENESS: overlapping labels on the same asset share
            # the same underlying return path — N concurrent labels are ~one
            # fact, not N. Count per-(asset, grid-bar) concurrency over each
            # row's [signal_ts, ts] lifespan; scale w by mean(1/concurrency).
            grid = max(float(wc.get("uniqueness_grid_sec", 300.0)), 1.0)
            floor = min(max(float(wc.get("uniqueness_floor", 0.0)), 0.0), 1.0)
            cap = int(14 * 86400 // grid)   # corrupt far-future ts: bound span
            conc: dict = {}
            spans = []
            for i in range(len(w)):
                b0 = int(sig[i] // grid)
                b1 = min(int(max(meta[i][1], sig[i]) // grid), b0 + cap)
                spans.append((meta[i][0], b0, b1))
                for b in range(b0, b1 + 1):
                    conc[(meta[i][0], b)] = conc.get((meta[i][0], b), 0) + 1
            uniqs = []
            for i, (a, b0, b1) in enumerate(spans):
                u = sum(1.0 / conc[(a, b)] for b in range(b0, b1 + 1)) \
                    / (b1 - b0 + 1)
                uniqs.append(u)
                w[i] *= max(u, floor)
            uniq_mean = sum(uniqs) / len(uniqs)
        # time-barrier zeros: "price touched NEITHER barrier" is weaker
        # evidence against the signal than a realized stop-out; do not pool
        # them at full weight (1.0 = no distinction, legacy rows barrier="")
        tbw = min(max(float(wc.get("time_barrier_zero_weight", 1.0)), 0.0), 1.0)
        if w and tbw < 1.0:
            for i in range(len(w)):
                if y[i] == 0.0 and meta[i][3] == "time":
                    w[i] *= tbw
        # mass-preserving rescale: uniqueness/barrier corrections REDISTRIBUTE
        # evidence between rows; they must not shrink the total loss weight
        # (sklearn's fixed-C L2 balances loss against penalty, so a global
        # 10x weight shrink would silently over-regularize every model).
        # Scale-invariant quantities (weight ratios, Kish ESS) are untouched.
        post_mass = sum(w)
        if w and post_mass > 0.0 and pre_mass > 0.0:
            scale = pre_mass / post_mass
            if abs(scale - 1.0) > 1e-12:
                for i in range(len(w)):
                    w[i] *= scale
        # one-sided-batch prior-skew DETECTOR (ML-074): a trailing window
        # whose label prior diverges hard from the corpus prior (the all-zero
        # quiet-weekend batch) shifts calibration. Detection only — visible,
        # never silently reweighted.
        skew_flag, p_recent, p_all = False, None, None
        if y and wc:
            win_h = float(wc.get("prior_skew_window_h", 24.0))
            min_rows = int(wc.get("prior_skew_min_rows", 30))
            thresh = float(wc.get("prior_skew_threshold", 0.25))
            ends = [m[1] for m in meta]
            tmax = max(ends)
            recent = [y[i] for i in range(len(y))
                      if ends[i] >= tmax - win_h * 3600.0]
            if len(recent) >= min_rows and len(y) > len(recent):
                p_recent = sum(recent) / len(recent)
                p_all = sum(y) / len(y)
                if abs(p_recent - p_all) > thresh:
                    skew_flag = True
                    log.warning(
                        "%s: trailing %.0fh label prior %.2f skews from "
                        "corpus prior %.2f (>%.2f) — one-sided batch; watch "
                        "calibration (detection only, weights untouched)",
                        Code.ML_PRIOR_SKEW.value, win_h, p_recent, p_all,
                        thresh)
        self.last_load_stats = {
            "rows": len(w), "dropped_dirty": dropped_dirty,
            "dropped_clash": dropped_clash,
            "live_clean": sum(1 for m in meta if m[2] == "live"),
            "mean_uniqueness": round(uniq_mean, 4),
            "prior_recent": p_recent, "prior_overall": p_all,
            "prior_skew": skew_flag,
        }
        X, y, w = (np.array(X, float), np.array(y, float),
                   np.array(w, float))
        sig = np.array(sig, float)
        # label RESOLUTION times (row append ts): live rows can resolve
        # far past signal+label_span (full-window holds), so the time
        # purge must know when each label actually landed, not assume
        # the fixed horizon (LP-1: under-purged live-label leakage)
        res = np.array([m[1] for m in meta], float)
        if len(sig):
            order = np.argsort(sig, kind="mergesort")
            X, y, w, sig, res = (X[order], y[order], w[order],
                                 sig[order], res[order])
        if return_label_times:
            return X, y, w, sig, res
        if return_sig:
            return X, y, w, sig
        return X, y, w


class HorizonShadowStore:
    """Append-only, FIXED-schema shadow log of multi-horizon barrier
    outcomes. Deliberately NOT signal_history.csv: writing per-horizon
    labels there would change the training header and trigger the schema
    rotation that once lost live rows ([[history-schema-loss-incident]]).
    One row per (candidate, horizon) in long format so the header never
    depends on how many horizons are configured. This is EVIDENCE, not
    training data - it answers "which holding horizon actually pays for
    which asset" so a horizon feature can later be promoted on data, not
    on a guess."""

    HEADER = ["candidate_id", "asset", "direction", "horizon_bars",
              "label", "net_ret_pct", "exit_reason", "ts"]

    def __init__(self, path: str = "outputs/horizon_shadow.csv"):
        self.path = Path(path)

    def _ensure(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(self.HEADER)

    def append(self, candidate_id: str, asset: str, direction: str,
               horizon_bars: int, label: int, net_ret_pct: float,
               exit_reason: str):
        try:
            self._ensure()
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    candidate_id, asset, direction, int(horizon_bars),
                    int(label), f"{net_ret_pct:.6f}", exit_reason,
                    f"{time.time():.0f}"])
        except OSError:
            self.dropped = getattr(self, "dropped", 0) + 1
            if self.dropped == 1 or self.dropped % 20 == 0:
                log.warning("horizon shadow append failed (%d dropped) - "
                            "research dataset truncating", self.dropped)
            else:
                log.debug("horizon shadow append failed (non-fatal)",
                          exc_info=True)


class CandidateLabeler:
    """Labels EVERY gate-confirmed signal - taken or vetoed - via
    triple-barrier on the subsequent price path. This is the dataset
    multiplier: the model otherwise only ever sees the few, selection-
    biased trades that survived every veto. Candidate rows are written
    with source="candidate" so training can weight or inspect them
    separately from live fills.
    """

    def __init__(self, store: HistoryStore, ml_cfg: dict, on_label=None,
                 shadow_store: "HorizonShadowStore | None" = None,
                 exit_policy=None):
        cfg = ml_cfg or {}
        self.store = store
        # LABEL MODE: "exit_policy" replays the live exit engine (hard stop +
        # tiered scale-outs + give-back/trailing) so a candidate is labeled by
        # the SAME question a live trade poses; "triple_barrier" is the legacy
        # symmetric pt/sl barrier. exit_policy needs a policy object (built from
        # config by the caller); absent one we fall back to the barrier so this
        # can never crash for a caller that didn't supply it.
        self.exit_policy = exit_policy
        mode = str(cfg.get("label_mode", "exit_policy"))
        self.label_mode = mode if (mode == "triple_barrier"
                                   or exit_policy is not None) \
            else "triple_barrier"
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
        # INTENTIONALLY distinct from the sizer's rt_cost (maker+taker, worst
        # case for Kelly): the labeler models the EXPECTED realized cost (maker
        # entry OM-011 + maker-first exit, which fills maker most of the time)
        # PLUS the asset's own spread below - accurate per-trade outcome. The
        # sizer's worst-case exit is the conservative sizing margin on top. Do
        # NOT collapse the two: label realistically, size defensively.
        self.rt_cost_pct = float(cfg.get("label_round_trip_cost_pct", 0.5))
        # per-asset accuracy: add the asset's own execution spread on top of
        # the fee floor so a wide-spread small cap's scalps are labeled at
        # their REAL cost (the fee floor alone under-charges them and teaches
        # the model to over-trade illiquid pairs). Capped so one blown-out
        # book can't poison a label. Off -> old flat-cost behavior.
        self.label_include_spread = bool(cfg.get("label_include_spread", True))
        self.spread_cap_bps = float(cfg.get("label_spread_cap_bps", 60.0))
        # multi-horizon SHADOW: also score each candidate at shorter/longer
        # horizons and log the outcome (never touches the live label/model).
        mh = cfg.get("multi_horizon", {}) or {}
        self._mh_enabled = bool(mh.get("enabled", False))
        self.horizons = sorted({int(h) for h in mh.get("horizons_bars", [])
                                if 0 < int(h) <= self.horizon}) \
            if self._mh_enabled else []
        self.shadow_store = shadow_store
        self.max_candidates = int(cfg.get("max_open_candidates", 200))
        self._bars: dict = {}          # asset -> {"t":[], "c":[], "h":[], "l":[]}
        self._cands: list = []
        self._seq = 0
        # per-instance salt in the candidate id. _seq is persisted and
        # restored, but a filesystem rollback (lived 2026-07-14) reverts
        # state.json to an OLDER seq while signal_history.csv keeps the ids it
        # already wrote - so a bare cand-{seq} gets REUSED and the training
        # file collects duplicate position_ids for two distinct signals. A
        # fresh random salt per labeler (NOT persisted) makes a reset seq
        # unable to collide with a previously-written id, with no dependence
        # on clock resolution or process timing.
        self._id_salt = os.urandom(4).hex()
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
                sigma_bar: float, bar_time, gates_passed=None,
                spread_bps: float = 0.0) -> bool:
        """Returns True when a candidate row was actually appended -
        the SCS latch must only be consumed by a REAL append (a dedup
        no-op would silently discard the state-change lesson the
        sampler exists to capture). Interface extended, not changed:
        legacy callers ignored the None return."""
        if self._last_reg.get((asset, direction)) == bar_time:
            return False                # same signal, same candle: no duplicate
        self._last_reg[(asset, direction)] = bar_time
        if len(self._cands) >= self.max_candidates:
            # evict the NEWEST pending candidate, never index 0: poll()
            # runs first each cycle, so the head of the list is the
            # candidate closest to its label horizon — evicting it (old
            # behavior) killed the about-to-ripen row exactly when
            # signal flow was busiest, biasing labels toward quiet hours
            self._cands.pop()
        self._seq += 1
        self._cands.append({"id": f"cand-{self._id_salt}-{self._seq}",
                            "asset": asset,
                            "direction": direction,
                            "features": features.copy(),
                            "sigma_bar": float(max(sigma_bar, 1e-5)),
                            "bar_time": bar_time,
                            # asset's execution spread at signal time, folded
                            # into the label's round-trip cost at poll time
                            "spread_bps": float(max(spread_bps, 0.0)),
                            # which gates passed at signal time (JSON-safe
                            # bools); the labeled outcome feeds per-gate stats
                            "gates": {str(g): bool(v) for g, v in
                                      gates_passed.items()}
                            if isinstance(gates_passed, dict) else None})
        return True

    def _cost_pct(self, cand: dict) -> float:
        """Round-trip cost for this candidate's label: the fee floor plus,
        when enabled, the asset's own (capped) execution spread."""
        cost = self.rt_cost_pct
        if self.label_include_spread:
            spread = min(float(cand.get("spread_bps", 0.0)),
                         self.spread_cap_bps)
            cost += spread / 100.0     # bps -> percent
        return cost

    def poll(self) -> int:
        """Label candidates. Returns rows written.

        EARLY DECIDABILITY: a pt/sl barrier hit inside the available
        candle window is FINAL - triple_barrier scans chronologically
        and stops at the first touch, so later bars cannot change the
        outcome. Only the 'time' label must wait for the full horizon.
        Waiting for all 96 bars regardless (old behavior) delayed every
        label by 8h even when it was decided in minutes, and turned any
        registration gap into an equal-width label drought 8h later.
        Early-labeled candidates STAY in the pool (labeled=True) until
        the full horizon so the multi-horizon shadow record - which
        needs the complete path - stays whole; the primary row is
        written exactly once."""
        written = 0
        for cand in list(self._cands):
            b = self._bars.get(cand["asset"])
            if not b or cand["bar_time"] not in b["t"]:
                # entry bar evicted or never cached: unlabelable, drop
                if b and b["t"] and cand["bar_time"] < b["t"][0]:
                    self._cands.remove(cand)
                continue
            i = b["t"].index(cand["bar_time"])
            avail = len(b["t"]) - 1 - i
            if avail < 1:
                continue
            closes = np.array(b["c"], float)
            highs = np.array(b["h"], float)
            lows = np.array(b["l"], float)
            side = 1 if cand["direction"] == "long" else -1
            cost = self._cost_pct(cand)
            if avail >= self.horizon:
                # full window: finish shadows, label if still unlabeled
                if not cand.get("labeled"):
                    out = self._label(closes, highs, lows, i, side,
                                      cand["sigma_bar"], cost)
                    written += self._emit_label(cand, out)
                self._record_shadow_horizons(cand, closes, highs, lows, i,
                                             side, cost)
                self._cands.remove(cand)
                continue
            if cand.get("labeled"):
                continue                    # waiting only for shadows now
            out = self._label(closes, highs, lows, i, side,
                              cand["sigma_bar"], cost)
            if out.final:                   # resolved inside the window -> final
                written += self._emit_label(cand, out)
                cand["labeled"] = True
                if not self.horizons:
                    # no multi-horizon shadows to complete: a DECIDED
                    # candidate has no reason to hold a pool slot for the
                    # rest of its 8h horizon — at max_open_candidates that
                    # retention starved registration of NEW signals for
                    # hours (audit M-finding). Shadows enabled -> keep it
                    # until the full path is recorded, as before.
                    self._cands.remove(cand)
        if written:
            log.info("labeled %d candidate signal(s) via %s",
                     written, self.label_mode)
        return written

    def _label(self, closes, highs, lows, i, side, sigma_bar, cost):
        """Dispatch to the configured labeler. exit_policy replays the live
        exit engine (matches how the signal is actually traded); triple_barrier
        is the legacy symmetric pt/sl. Same signature, same BarrierOutcome."""
        if self.label_mode == "exit_policy" and self.exit_policy is not None:
            return simulate_exit_policy(closes, highs, lows, i, side, sigma_bar,
                                        self.exit_policy, max_bars=self.horizon,
                                        cost_pct=cost)
        return triple_barrier(closes, highs, lows, i, side, sigma_bar,
                              self.pt, self.sl, self.horizon, cost_pct=cost)

    def _emit_label(self, cand: dict, out) -> int:
        self.store._append_row(cand["id"], cand["asset"],
                            cand["direction"], cand["features"],
                            out.label, 0.0, "candidate",
                            signal_ts=float(cand["bar_time"]),
                            barrier=str(getattr(out, "barrier", "") or ""))
        if self._on_label is not None:
            try:
                self._on_label(cand.get("gates"), out.label)
            except Exception:
                log.exception("on_label callback failed - gate stats "
                              "skipped for this candidate")
        return 1

    def _record_shadow_horizons(self, cand, closes, highs, lows, i, side,
                                cost):
        """Score this candidate at each configured shadow horizon and log
        the outcome. Pure evidence: never affects the primary label, the
        model, or any live decision. All horizons are <= the primary
        horizon (guarded), so the data is already available when the
        primary label fires. Failure here must never break labeling."""
        if not self.horizons or self.shadow_store is None:
            return
        try:
            for h in self.horizons:
                if len(closes) - 1 - i < h:
                    continue
                o = triple_barrier(closes, highs, lows, i, side,
                                   cand["sigma_bar"], self.pt, self.sl,
                                   h, cost_pct=cost)
                self.shadow_store.append(
                    cand["id"], cand["asset"], cand["direction"], h,
                    o.label, o.ret_pct, o.barrier)
        except Exception:
            if self.shadow_store is not None:
                self.shadow_store.dropped = getattr(
                    self.shadow_store, "dropped", 0) + 1
            log.debug("shadow horizon recording failed (non-fatal)",
                      exc_info=True)

    # --- persistence hooks ---
    def to_dict(self) -> dict:
        return {"bars": self._bars, "seq": self._seq,
                "schema_version": FEATURE_SCHEMA_VERSION,
                "cands": [{**c, "features": c["features"].tolist()}
                        for c in self._cands],
                # JSON keys must be strings: "asset|direction" -> bar_time
                "last_reg": {f"{a}|{d}": t
                             for (a, d), t in self._last_reg.items()}}

    def restore(self, d: dict):
        if not d:
            return
        # SEMANTIC guard: a version bump means same-width vectors changed
        # meaning (v2: side-relative encoding) - the width check below
        # cannot see that, and labeling a stale-semantics vector would
        # append a silently-poisoned row under the current header.
        ver = int(d.get("schema_version", 1) or 1)
        if ver != FEATURE_SCHEMA_VERSION:
            n = len(d.get("cands", []))
            if n:
                log.warning(
                    f"{Code.ML_SCHEMA_MISMATCH.value}: dropped {n} restored "
                    f"candidate(s) from feature-schema v{ver} (current "
                    f"v{FEATURE_SCHEMA_VERSION}) - same width, different "
                    f"meaning; they re-register fresh")
            d = {**d, "cands": []}
        self._bars = {a: {k: list(v) for k, v in bb.items()}
                    for a, bb in d.get("bars", {}).items()}
        self._seq = int(d.get("seq", 0))
        cands = [{**c, "features": np.array(c["features"], float)}
                 for c in d.get("cands", [])]
        # a candidate persisted before a FEATURE_NAMES bump is unlabelable
        # after it: its vector can't be mapped onto the new schema, and
        # labeling it would write a misaligned short row (see _append_row)
        want = len(FEATURE_NAMES)
        stale = sum(1 for c in cands if len(c["features"]) != want)
        if stale:
            log.warning(f"{Code.ML_SCHEMA_MISMATCH.value}: dropped {stale} "
                        f"restored "
                        f"candidate(s) with pre-rotation feature width "
                        f"(current schema: {want} features)")
        self._cands = [c for c in cands if len(c["features"]) == want]
        # RE-MINT restored ids onto THIS launch's salt. A candidate persisted
        # by an earlier process carries either a bare `cand-{seq}` id (pre-salt
        # builds) or a FOREIGN salt; when it finally labels it writes that id
        # as the row's position_id, which can already exist in
        # signal_history.csv - the filesystem-rollback collision the salt
        # exists to kill (lived 2026-07-14: seq reset -> reused bare id). The
        # per-launch salt is unique, so re-minting every restored id under it
        # is collision-proof against the file; advancing the shared _seq keeps
        # new registrations disjoint from the re-minted ones too.
        for c in self._cands:
            self._seq += 1
            c["id"] = f"cand-{self._id_salt}-{self._seq}"
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
                    max_bars: int = 96, cost_pct: float = 0.5,
                    label_mode: str = "triple_barrier", exit_policy=None):
    """EMA-cross pseudo-signals -> labels over history.

    label_mode "exit_policy" (with an exit_policy) replays the live exit engine
    so bootstrap labels match how a signal is actually traded, consistent with
    the candidate labeler; "triple_barrier" is the legacy symmetric pt/sl.
    Defaults to triple_barrier so existing callers are behavior-exact until
    they opt in.

    Microstructure/regime/sentiment features are unavailable historically
    and set to neutral; only price/vol/momentum features vary. Good
    enough for a calibrated prior, not a substitute for live history.
    """
    use_policy = label_mode == "exit_policy" and exit_policy is not None
    closes = np.array([c["close"] for c in candles_5m], float)
    highs = np.array([c["high"] for c in candles_5m], float)
    lows = np.array([c["low"] for c in candles_5m], float)
    vols = np.array([c["volume"] for c in candles_5m], float)
    if len(closes) < 300:
        return np.empty((0, len(FEATURE_NAMES))), np.empty(0)

    fast, slow = _ema(closes, 9), _ema(closes, 21)
    rets = np.diff(np.log(np.maximum(closes, 1e-9)))
    X, y = [], []
    name_idx = {n: k for k, n in enumerate(FEATURE_NAMES)}
    for i in range(60, len(closes) - max_bars - 1):
        crossed_up = fast[i] > slow[i] and fast[i - 1] <= slow[i - 1]
        crossed_dn = fast[i] < slow[i] and fast[i - 1] >= slow[i - 1]
        if not (crossed_up or crossed_dn):
            continue
        side = 1 if crossed_up else -1
        sigma_bar = float(rets[max(i - 60, 0):i].std() + 1e-6)
        out = simulate_exit_policy(closes, highs, lows, i, side, sigma_bar,
                                   exit_policy, max_bars=max_bars,
                                   cost_pct=cost_pct) if use_policy \
            else triple_barrier(closes, highs, lows, i, side, sigma_bar,
                                pt_mult, sl_mult, max_bars, cost_pct=cost_pct)
        feats = np.zeros(len(FEATURE_NAMES))

        def setf(name, val, _feats=feats):
            _feats[name_idx[name]] = val

        # *_dir features are SIDE-RELATIVE (features.py): the market-absolute
        # signed value times side, so "positive = with my trade". The bootstrap
        # wrote RAW returns under the pre-v2 names ret_1/6/12/48 & mom_score,
        # which (a) KeyError'd - those names no longer exist in FEATURE_NAMES,
        # crashing the whole cold-start bootstrap on the first EMA cross - and
        # (b) even renamed would carry a LONG-biased sign, so every short-side
        # bootstrap row disagreed with how live rows encode the same drift.
        for name, k in (("ret_1_dir", 1), ("ret_6_dir", 6),
                        ("ret_12_dir", 12), ("ret_48_dir", 48)):
            if i - k >= 0 and closes[i - k] > 0:
                r = np.log(closes[i] / closes[i - k])
                z = float(np.clip(r / (sigma_bar * np.sqrt(k) + 1e-9), -6, 6))
                setf(name, side * z)             # side-relative, matches live
        setf("sigma_bar_pct", float(np.clip(sigma_bar * 100, 0, 5)))
        vwin = vols[max(i - 48, 0):i]
        if len(vwin) > 2:
            setf("volume_z", float(np.clip((vols[i] - vwin.mean()) / (vwin.std() + 1e-9), -5, 5)))
        mom = np.sign(closes[i] - closes[max(i - 288, 0)])
        setf("mom_dir", float(side * mom))       # side-relative, matches live
        setf("regime_range", 1.0)
        setf("turbulence_pct", 0.5)
        setf("direction", float(side))
        setf("gate_confidence", 1.0)
        X.append(feats)
        y.append(float(out.label))
    return np.array(X, float), np.array(y, float)
