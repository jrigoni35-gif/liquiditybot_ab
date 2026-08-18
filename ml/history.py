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
import math
import os
import logging
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from core.codes import Code, tag
from core.runtime import durable_append
from ml.features import (FEATURE_NAMES, FEATURE_SCHEMA_VERSION,
                         REGIME_LABELS, REGIME_ONE_HOT_FEATURES)
from ml.labeling import barrier_geometry, simulate_exit_policy, triple_barrier
from ml.walkforward import BAR_SECONDS

log = logging.getLogger("liquiditybot.ml.history")

# Zombie eviction reasons about REAL elapsed time (now - bar_time), which
# is only meaningful when bar_time rides the same epoch clock as the
# engine's `now`. Test harnesses mint toy bar clocks (0, 1, 2, ...; e.g.
# scripts/smoke_test.py MockOKX candles) while driving cycles with
# time.time() - comparing those would compute a billion-second "age" and
# censor every candidate on sight. Any real candle time is far above this
# floor (1e9 = 2001-09-09 in epoch seconds; the config guard's own epoch
# band for ml.epoch.candidate_cutoff_ts starts at 1752000000); any toy
# clock is far below it. A candidate below the floor simply never arms
# eviction - identical to the pre-fix behavior.
_EPOCH_CLOCK_FLOOR = 1e9

# regime label -> its one-hot column's index in FEATURE_NAMES (Task 4,
# #103 regime-coverage hold). Built once from the shared mapping so a
# future FEATURE_NAMES reorder can't silently desync the decode from the
# encode (ml.features.build_features sets exactly one of these to 1.0).
_REGIME_FEATURE_IDX = {lbl: FEATURE_NAMES.index(feat) for lbl, feat in
                       zip(REGIME_LABELS, REGIME_ONE_HOT_FEATURES,
                          strict=True)}


def _empty_training_tuple(return_sig: bool, return_label_times: bool):
    """Missing-file shape for load_training_data: a fresh checkout has no
    signal_history.csv (outputs/ is gitignored), and every return arity
    must be honored - overfit_check unpacks 4 (return_sig), the retrain
    paths unpack 5 (return_label_times); only special-casing return_sig
    made the 5-way unpack a latent fresh-checkout crash (whole-phase
    review follow-up 2026-07-26)."""
    empty = (np.empty((0, len(FEATURE_NAMES))), np.empty(0), np.empty(0))
    if return_label_times:
        return (*empty, np.empty(0), np.empty(0))
    return (*empty, np.empty(0)) if return_sig else empty


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion; (0,1) when n=0.
    Module-level (not a HistoryStore method) so Task 6's report can reuse it
    without instantiating a store."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1.0 + z * z / n
    center = p + z * z / (2 * n)
    half = z * ((p * (1.0 - p) / n + z * z / (4.0 * n * n)) ** 0.5)
    return ((center - half) / denom, (center + half) / denom)


def sim_live_divergence(times, sources, labels,
                        window_sec: float) -> dict:
    """Weighted |mean(live label) - mean(candidate label)| over time
    buckets containing BOTH sources (weight = candidate count in bucket);
    coverage = candidate rows in such buckets / all candidate rows.
    Report-only: quantifies where the simulator's labels disagree with
    realized outcomes, only where realized outcomes exist to compare."""
    buckets: dict = {}
    n_cand = 0
    for t, s, y in zip(times, sources, labels, strict=True):
        b = buckets.setdefault(int(float(t) // window_sec),
                               [0.0, 0, 0.0, 0])
        if s == "live":
            b[0] += y
            b[1] += 1
        else:
            b[2] += y
            b[3] += 1
            n_cand += 1
    num = den = covered = 0.0
    windows_both = 0
    for b in buckets.values():
        if b[1] and b[3]:
            windows_both += 1
            covered += b[3]
            num += abs(b[0] / b[1] - b[2] / b[3]) * b[3]
            den += b[3]
    return {"score": (round(num / den, 4) if den else None),
            "coverage": round((covered / n_cand) if n_cand else 0.0, 4),
            "windows_both": windows_both, "n_cand": n_cand}


def _sim_divergence_stat(div_t: list, div_s: list, div_y: list,
                         tele_cfg: dict) -> dict:
    """Compute the T2.2a live-covered-window divergence stat over the
    rows captured by load_training_data's second pass and (when a score
    exists) emit the detection-only ML-078 log line. Split out of
    load_training_data purely to keep that method's mccabe complexity
    under the C901 ceiling (pyproject.toml) - no behavior difference
    from inlining it there."""
    dwh = float(tele_cfg.get("divergence_window_h", 24.0))
    div = sim_live_divergence(div_t, div_s, div_y, dwh * 3600.0)
    div["window_h"] = dwh
    if div["score"] is not None:
        log.info(tag(
            Code.ML_SIM_DIVERGENCE,
            f"sim-live divergence {div['score']:.3f} over "
            f"{div['windows_both']} shared window(s), coverage "
            f"{100 * div['coverage']:.0f}% of candidate rows - "
            f"detection only"))
    return div


def _epoch_cutoff(epoch_cfg: "dict | None") -> "float | None":
    """Resolves load_training_data's opt-in candidate-epoch filter (T3.6,
    config ml.epoch, SHIPPED OFF - exclude_old_candidates: false) to an
    active cutoff timestamp, or None (filter inactive). Active only when
    BOTH exclude_old_candidates is truthy AND candidate_cutoff_ts is a
    real number; core/config_guard.py FATALs any live config where the
    flag is true but the cutoff is missing/invalid, so this resolves to
    None defensively rather than trust an unchecked dict (e.g. a test or
    a caller that bypassed the guard) - fail open (filter off), never
    fail into an unbounded/garbage cutoff. Module-level so the resolution
    itself (several branches) doesn't count against load_training_data's
    mccabe complexity - see _row_epoch_excluded below for why the actual
    per-row check is split out too."""
    ec = epoch_cfg or {}
    if not ec.get("exclude_old_candidates"):
        return None
    cutoff = ec.get("candidate_cutoff_ts")
    if isinstance(cutoff, bool) or not isinstance(cutoff, (int, float)):
        return None
    return float(cutoff)


def _row_epoch_excluded(row: dict, cutoff: "float | None") -> bool:
    """True when `row` is a CANDIDATE-source row whose resolve `ts` is
    strictly before `cutoff` (None = filter inactive -> always False).
    Split to a module-level helper purely to keep load_training_data's
    mccabe complexity under the C901 ceiling (pyproject.toml) - same
    pattern as _sim_divergence_stat/_scan_live_dedup_keys, no behavior
    difference from inlining it there. The `source == "candidate"` test
    is repeated here as defense in depth, but the LOAD-BEARING guarantee
    (live rows structurally can never be excluded, in any era, for any
    reason) is the caller's: load_training_data only ever calls this from
    inside its own `row.get("source") == "candidate"` branch, so a live
    row's `continue` can never be reached through this function no matter
    what it returns. Malformed/missing ts fails OPEN (kept) - this filter
    only removes what it can positively place before the cutoff."""
    if cutoff is None or row.get("source") != "candidate":
        return False
    try:
        r_ts = float(row.get("ts") or "nan")
    except ValueError:
        return False
    return r_ts < cutoff


def _scan_live_dedup_keys(path: Path) -> tuple:
    """First-pass prescan for load_training_data's SYNTHETIC-vs-REAL clash
    guard (see the full rationale in that method's body): one read of
    every LIVE row (book=="long" and source=="candidate" rows excluded,
    exactly as that method's own second pass excludes them), building the
    lineage-match set (live_cand_ids), the legacy exact-vector fallback
    set (live_keys), and the per-candidate_id realized label the T2.2b
    twin-agreement stat pairs against (live_label_by_cid). Split to a
    module-level helper purely to keep load_training_data's mccabe
    complexity under the C901 ceiling (pyproject.toml) - no behavior
    difference from inlining it there."""
    live_keys = set()
    live_cand_ids = set()
    live_label_by_cid: dict = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("book") or "5m") == "long":
                continue
            if row.get("source") == "candidate":
                continue
            cid = (row.get("candidate_id") or "").strip()
            if cid:
                live_cand_ids.add(cid)
                try:
                    live_label_by_cid[cid] = float(row["label"])
                except (KeyError, ValueError):
                    pass
            try:
                live_keys.add((row["asset"], row["side"],
                              tuple(row[n] for n in FEATURE_NAMES)))
            except KeyError:
                continue
    return live_keys, live_cand_ids, live_label_by_cid


def _regime_of_feats(feats) -> "str | None":
    """Which of the 5 macro-regime one-hots a feature row marks, or None
    for an all-zero/ambiguous row (schema-migration padding, or a legacy
    row written before the regime one-hot existed). >0.5 threshold: the
    one-hot is exactly 0.0/1.0 by construction, never fractional."""
    best_lbl, best_v = None, 0.5
    for lbl, idx in _REGIME_FEATURE_IDX.items():
        v = float(feats[idx]) if idx < len(feats) else 0.0
        if v > best_v:
            best_lbl, best_v = lbl, v
    return best_lbl


def _regime_of_csv_row(row: dict) -> "str | None":
    """Same decode as _regime_of_feats, from a csv.DictReader row (string
    cells) - used by the load-time full-scan that seeds the per-regime
    live counter from rows a PRIOR process already wrote."""
    best_lbl, best_v = None, 0.5
    for lbl, feat in zip(REGIME_LABELS, REGIME_ONE_HOT_FEATURES, strict=True):
        try:
            v = float(row.get(feat) or 0.0)
        except ValueError:
            v = 0.0
        if v > best_v:
            best_lbl, best_v = lbl, v
    return best_lbl


# ---- label-era instrumentation (learnaccel: DEEP DIVE, progress.md) -------
# The training label silently pooled THREE incompatible definitions in one
# corpus with nothing recorded to tell them apart (barrier-alone AUC 0.769
# beat the 62-feature model's 0.597 - the label largely WAS the barrier).
# This block makes the era that produced each row's barrier value a first-
# class, persisted fact - never a label/weight/row change (task scope:
# tagging + accounting + a report-only drift alarm, nothing else).
LABEL_ERA_LEGACY = "legacy"                    # plain triple-barrier era
LABEL_ERA_EXIT_SIM = "exit_sim"                # simulate_exit_policy() replay
LABEL_ERA_TIME_STOP = "exit_sim_time_stop"     # + P2 time-stop rung
# 2026-07-26 signal-quality task (task-signalquality-brief.md): ml.label_mode
# flipped back to "triple_barrier" so the label measures signal quality, not
# exit policy (c36aa90's "train on the bet we trade" default is consciously
# overridden - see docs/quant/2026-07-26_label_signal_quality.md). Flipping
# the mode alone would have re-emitted the SAME bare "pt"/"sl"/"time" strings
# LABEL_ERA_LEGACY/_EXIT_SIM_BARRIERS already claim for the pre-instrumentation
# and exit-sim populations - a brand-new label era silently masquerading as
# two OLD ones. CandidateLabeler._label's triple_barrier dispatch (below)
# therefore prefixes its own vocabulary ("tb_pt"/"tb_sl"/"tb_time") so it is
# self-describing; this era claims exactly that prefixed vocabulary and
# nothing else. A value distinct from all of the above by construction (never
# "legacy"/"exit_sim"/"exit_sim_time_stop"/"unknown") - the July 13-19 legacy
# rows are a genuinely different population and must stay distinguishable.
LABEL_ERA_TRIPLE_BARRIER = "triple_barrier"
# the horizon the SHIPPED triple_barrier rows were labeled under, before
# the 2026-07-31 era-deadlock fix moved it to 24. Rows at this horizon
# keep the un-suffixed era name so nothing already on disk changes
# meaning; any other horizon self-identifies (triple_barrier_era).
_TB_LEGACY_MAX_BARS = 96
LABEL_ERA_UNKNOWN = "unknown"                  # unrecognized barrier string

# gate-truth instrumentation (2026-07-28): the informed-flow component
# vocabulary, ONE source of truth for capture (SignalResult.components),
# persistence (the sg_* trailing columns below) and the offline grader
# (scripts/gate_truth_report.py). Order IS the column order.
SG_COMPONENT_KEYS = ("flow", "delta", "accum", "burst", "trend",
                     "evidence", "conc")

# Corpus row shape, as counts rather than as literals repeated per use.
# _N_LEAD: position_id, asset, side. _N_TRAIL: label, net_pnl_usd, source,
# ts, signal_ts, barrier, probe, disp, candidate_id, book, label_era,
# pt_frac, sl_frac (13) + the 7 sg_* + entry_price, exit_price
# + the 4 avail_* flags (AVAIL_COLS) = 26.
# _append_row's width guard AND its warning message both derive from these,
# so the "expected feature count" they report can never disagree again -
# tests/test_durable_append.py pins the identity against the live header
# and tests/test_data_contracts.py pins the header itself.
_N_LEAD = 3

# Context-input availability flags persisted per row (input-feed audit
# 2026-08-07, owed 41b): which of the row's context features were built
# from a LIVE source vs a dark/frozen one. A dead feed's neutral zeros are
# byte-identical to genuine neutral AND to historical padding
# (CONTEXT_NEUTRAL), so without these flags no offline consumer can ever
# separate "options feed down" from "options flat" from "row predates the
# feature". Column order IS this tuple's order; values are "1"/"0" when
# recorded, "" on rows written before the flags existed or by paths that
# do not carry them (long-book rows, legacy pending tuples) - consumers
# must treat "" as UNKNOWN, never as false. BOOKKEEPING ONLY - never a
# feature (the 2026-08-08 DoF adjudication keeps the feature ledger
# closed); these exist so a FUTURE training decision can weight or filter
# degraded-context rows offline, deliberately.
AVAIL_COLS = ("avail_web", "avail_equity", "avail_options",
              "quotes_frozen")
_N_TRAIL = 13 + len(SG_COMPONENT_KEYS) + 2 + len(AVAIL_COLS)

# Cap on the candidate `disp` column. See CandidateLabeler.mark_disposition
# for the measurement that moved it off 40 (which amputated the bracket
# geometry on 3,666 of 9,692 rows).
DISPOSITION_MAX_CHARS = 200

# Vertical-barrier reasons: "price touched NEITHER profit nor stop inside the
# horizon". This is a POPULATION, not a spelling, and the sample-weight
# correction below (time_barrier_zero_weight) keys off it — a no-move is
# weaker evidence against the signal than a realized stop-out.
# Spelled two ways: "time" under label_mode="exit_policy", "tb_time" under
# "triple_barrier" (the era-disambiguating prefix, 2026-07-26). Matching the
# bare literal "time" silently dropped the correction for every row written
# under the new mode. "time_stop" is deliberately NOT here: a policy scratch
# is "we chose not to wait", not "the market did nothing".
_VERTICAL_BARRIER_REASONS = frozenset({"time", "tb_time"})

# Barrier strings simulate_exit_policy() (ml/labeling.py:180-360) can emit,
# MINUS "time_stop" (its own era below) and "pt" (triple_barrier() ONLY,
# ml/labeling.py:363-401 - never emitted by the exit-policy simulator).
# "realized" is neither labeler's own vocabulary - it is log_close()'s
# DEFAULT for its `barrier` parameter (geometry-alignment T5, spec D1):
# every non-bracket live close still threads it, byte-identical to the
# pre-T5 hardcoded tag. Post-T5, a live BRACKET position's close threads
# "tb_pt"/"tb_sl"/"tb_time" verbatim through that SAME parameter instead
# (main._finalize_position passes the close reason on; see
# HistoryStore.log_close's own docstring) - those three land in
# _TRIPLE_BARRIER_BARRIERS below, never here. "realized" groups in THIS
# set because a live row defaulting to it is always contemporary with
# whichever labeler is configured, never with the pre-instrumentation
# legacy window. "sl" and "time" are each producible by BOTH labelers in
# principle and so are not decisive standalone signatures - the DEEP DIVE
# measured the real corpus's legacy window as blank-barrier ONLY (1781
# rows, 07-13->07-19), so grouping them with exit_sim matches the
# measured era table exactly (task-label-brief.md), not a re-derivation.
# NEVER extend this set with the "tb_pt"/"tb_sl"/"tb_time" strings below -
# those are a disjoint vocabulary (LABEL_ERA_TRIPLE_BARRIER), not more
# spellings of the same bare "sl"/"time" this set already claims.
_EXIT_SIM_BARRIERS = frozenset({"trail", "realized", "tier", "floor",
                               "sl", "time"})

# The triple-barrier-mode-only vocabulary (2026-07-26 signal-quality task,
# extended 2026-07-27 geometry-alignment T5 spec D1): CandidateLabeler._label
# prefixes triple_barrier()'s own bare "pt"/"sl"/"time" with "tb_" at its
# call site in the persisted corpus (ml/history.py CandidateLabeler._label).
# Post-T5, a LIVE bracket position's close emits these SAME three strings
# too - main._finalize_position passes the close reason ("tb_pt"/"tb_sl"/
# "tb_time", verbatim, only when that literal string is what actually
# closed the position) into HistoryStore.log_close's `barrier` parameter,
# so this is no longer "the training corpus's vocabulary alone" - it is
# shared by the offline labeler AND the live bracket-exit engine, by
# construction (both call barrier_geometry(), T2). Any OTHER close reason
# (tier/stop/hard-stop/ratchet/flatten/...) still falls back to
# log_close's "realized" default and never lands here.
_TRIPLE_BARRIER_BARRIERS = frozenset({"tb_pt", "tb_sl", "tb_time"})


def triple_barrier_era(max_bars: int) -> str:
    """The `triple_barrier` era, QUALIFIED BY ITS HORIZON.

    2026-07-31 (era-deadlock fix, option E): `label_max_bars` moved
    96 -> 24 to end a clock inversion (the exit ladder's PT-060 scratch
    fires at bar 36, so the 96-bar vertical was unreachable and NO live
    row could ever carry a `tb_*` barrier -> every live label fell in an
    old era -> era exclusion dropped all of them -> `live_clean` 0 ->
    the model ladder was locked to `logistic` forever).

    The base era name is a pure function of the barrier STRING
    (label_era_of below), so a 96-bar row and a 24-bar row would both
    tag plain "triple_barrier" and mix two different label definitions
    inside one era - exactly what era separation exists to prevent.
    Rows written from here on persist this horizon-qualified name
    instead (`_row_label_era` prefers a row's own persisted tag), so the
    two generations stay separable forever with no migration and no
    rewritten history. The un-suffixed name is preserved for the
    shipped 96-bar rows so nothing already on disk changes meaning."""
    mb = int(max_bars)
    return (LABEL_ERA_TRIPLE_BARRIER if mb == _TB_LEGACY_MAX_BARS
            else f"{LABEL_ERA_TRIPLE_BARRIER}_h{mb}")


def label_era_of(barrier: "str | None") -> str:
    """Which LABEL DEFINITION produced a row, derived from its own
    `barrier` cell - the DEEP DIVE's (progress.md) measured era signature,
    never a calendar cutoff: a hardcoded date would silently mis-tag a
    backfill or a replay run under a DIFFERENT ml.label_mode/config than
    whatever was actually live on that historical date. Four known eras:
      legacy              - blank/absent barrier (pre-instrumentation
                            candidate rows - _emit_label only started
                            threading `out.barrier` once ml.label_mode's
                            default flipped to "exit_policy", commit
                            c36aa90), or "pt" (see _EXIT_SIM_BARRIERS'
                            comment: triple_barrier() is the ONLY labeler
                            that can ever emit it).
      exit_sim            - _EXIT_SIM_BARRIERS: simulate_exit_policy()
                            replaying the live exit ladder.
      exit_sim_time_stop  - "time_stop": same simulator, the P2 time-stop
                            rung (commit 5f26d3f, 2026-07-23).
      triple_barrier      - _TRIPLE_BARRIER_BARRIERS ("tb_pt"/"tb_sl"/
                            "tb_time"): ml.label_mode="triple_barrier"
                            (2026-07-26 signal-quality task) - a row whose
                            label measures signal quality (market/horizon-
                            determined barriers only), never which policy
                            exit fired. Pure function of THIS row's own
                            barrier string, same as every era above: a
                            re-simulated row tags correctly with no
                            knowledge of which config was live when it
                            was written."""
    b = (barrier or "").strip()
    if not b or b == "pt":
        return LABEL_ERA_LEGACY
    if b == "time_stop":
        return LABEL_ERA_TIME_STOP
    if b in _TRIPLE_BARRIER_BARRIERS:
        return LABEL_ERA_TRIPLE_BARRIER
    if b in _EXIT_SIM_BARRIERS:
        return LABEL_ERA_EXIT_SIM
    return LABEL_ERA_UNKNOWN


def _row_label_era(row: dict) -> str:
    """Prefer a row's OWN persisted `label_era` (every row written after
    this task carries one explicitly - HistoryStore._append_row); fall
    back to deriving it from `barrier` for a row written before the
    column existed, so an old corpus loads with no crash and no manual
    migration. Split to a module-level helper (single call site in
    load_training_data's per-row loop, no boolean operator there) purely
    to keep that method's mccabe complexity under the C901 ceiling
    (pyproject.toml) - no behavior difference from inlining it there."""
    persisted = (row.get("label_era") or "").strip()
    return persisted if persisted else label_era_of(row.get("barrier") or "")


def _reason_mix_tvd(baseline: dict, recent: dict) -> float:
    """Total-variation distance between two exit-reason mixes (each a
    {reason: count} dict over arbitrary, possibly-disjoint category
    sets): 0.5 * sum(|p_recent(r) - p_baseline(r)|), bounded [0, 1],
    symmetric, and - unlike ml.calibration.psi()'s log-ratio - needs no
    epsilon smoothing for a reason that is 0 in one window and >0 in the
    other, which is EXACTLY the DEEP DIVE's own failure mode (`trail`:
    49.5% -> 0.0% of daily rows). psi() also bakes in a FIXED uniform
    10-decile "expected" for a CONTINUOUS feature's deciles - not a fit
    for a handful of categorical exit-reason buckets compared against
    their own non-uniform trailing baseline - so TVD is the correct
    generalization of the same idea (a bounded distance between two
    proportion mixes) to this shape, not a different metric invented
    from scratch."""
    cats = set(baseline) | set(recent)
    nb, nr = sum(baseline.values()), sum(recent.values())
    if nb <= 0 or nr <= 0:
        return 0.0
    return 0.5 * sum(abs(recent.get(c, 0) / nr - baseline.get(c, 0) / nb)
                     for c in cats)


def _era_reason_stats(eras: list, meta: list, labels: list) -> dict:
    """Per-label-era, per-exit-reason row count and label rate over rows
    that SURVIVE into the trained corpus (same convention as
    sim_live_divergence/prior-skew: the corpus the model actually trains
    on, not the raw file). DEEP DIVE (progress.md) measured a 100x label-
    rate spread across exit reasons (time_stop 0.0071 .. trail 0.6867)
    that was invisible for six days; this is the missing instrument.
    Accounting only - never touches weights, labels, or which rows train.
    `meta` is load_training_data's own (asset, ts, source, barrier) tuple
    list; `eras[i]`/`meta[i]`/`labels[i]` line up by construction (all
    three are appended together, once per kept row, in that loop)."""
    eras_out: dict = {}
    for era, m, y in zip(eras, meta, labels, strict=True):
        reason = m[3] or ""
        eb = eras_out.setdefault(era, {"n": 0, "s": 0.0, "by_reason": {}})
        eb["n"] += 1
        eb["s"] += y
        rb = eb["by_reason"].setdefault(reason, {"n": 0, "s": 0.0})
        rb["n"] += 1
        rb["s"] += y
    out: dict = {}
    for era, eb in eras_out.items():
        out[era] = {
            "rows": eb["n"],
            "label_rate": round(eb["s"] / eb["n"], 4),
            "by_reason": {
                r: {"rows": rb["n"], "label_rate": round(rb["s"] / rb["n"], 4)}
                for r, rb in eb["by_reason"].items()
            },
        }
    return out


def _era_mix_drift_check(meta: list, tele_cfg: dict) -> dict:
    """Barrier/exit-reason MIX drift alarm (binding behaviour #3; DEEP
    DIVE finding #3: `trail` went 49.5% -> 0.0% of daily rows over six
    days while sl+time_stop went 27% -> 100% - a MIX SHIFT, not a market
    move, and nothing detected it). Compares the recent-window exit-
    reason mix against the mix over the WHOLE surviving corpus (same
    convention ML-074's prior-skew detector already uses: the baseline
    includes the recent rows too, softening rather than sharpening the
    signal) via total-variation distance (_reason_mix_tvd - see that
    docstring for why TVD over ml.calibration.psi()).

    Config-lifted (ml.telemetry.era_mix_drift_*, config_guard-bounded).
    Past the threshold: logs ONE warning + the registered ML-080 code.
    Report-only - never gates training, blocks a retrain, or touches a
    label/weight/row (mirrors ML-074's own restraint exactly).

    SILENT (fired=False, no log line at all) when the recent window has
    too few rows to trust its own mix - firing on a handful of rows would
    be worse noise than the blind spot this replaces."""
    win_h = float(tele_cfg.get("era_mix_drift_window_h", 24.0))
    min_rows = int(tele_cfg.get("era_mix_drift_min_rows", 30))
    thresh = float(tele_cfg.get("era_mix_drift_tvd_threshold", 0.3))
    out = {"tvd": None, "fired": False, "n_recent": 0, "n_total": len(meta)}
    if not meta:
        return out
    tmax = max(m[1] for m in meta)
    baseline: dict = {}
    recent: dict = {}
    n_recent = 0
    for m in meta:
        reason = m[3] or ""
        baseline[reason] = baseline.get(reason, 0) + 1
        if m[1] >= tmax - win_h * 3600.0:
            recent[reason] = recent.get(reason, 0) + 1
            n_recent += 1
    out["n_recent"] = n_recent
    if n_recent < min_rows:
        return out                    # SILENT: too few rows to trust the mix
    tvd = _reason_mix_tvd(baseline, recent)
    out["tvd"] = round(tvd, 4)
    if tvd > thresh:
        out["fired"] = True
        log.warning(tag(
            Code.ML_BARRIER_MIX_DRIFT,
            f"exit-reason mix drift tvd={tvd:.3f} over trailing "
            f"{win_h:.0f}h ({n_recent}/{len(meta)} rows) exceeds "
            f"{thresh:.2f} - recent-window reason mix diverges from the "
            f"trailing corpus; detection only, no label/weight/row-count "
            f"change"))
    return out


# ---- era-gated training exclusion (operator decision, 2026-07-26,
# docs/quant/2026-07-26_era_exclusion.md) ------------------------------------
# The label-era instrumentation above made the era that produced each row's
# barrier a first-class fact but never ACTED on it - every era still trained
# together. With the measured corpus in front of them (4,897 rows, 100%
# old-era: exit_sim/legacy/exit_sim_time_stop), the operator decided the OLD
# eras stop training the model once enough NEW-era (LABEL_ERA_TRIPLE_BARRIER)
# rows exist to be worth training on - and that the exclusion covers LIVE
# rows too (all 242 measured live rows are themselves old-era; keeping them
# would shrink the corpus without cleaning it - a conscious override of
# ml.epoch's "live rows never" rule below, a DIFFERENT mechanism: era-based,
# never a clock). THE BOUND: this is a LOAD-TIME VIEW ONLY, applied as the
# very LAST step of load_training_data (see _apply_era_exclusion's call
# site) - after every existing weight/stat computation, so it can never
# perturb the uniqueness/prior-skew/mix-drift/lineage/divergence math (those
# still see the full pre-exclusion corpus, exactly as before this task) and
# an inactive load (below threshold, or forced off) returns those four lists
# UNCHANGED. Nothing is ever removed from outputs/signal_history.csv -
# HistoryStore._append_row is untouched by this block.
ML_ERA_EXCLUSION_MIN_NEW_ERA_ROWS_DEFAULT = 150


def _era_exclusion_decide(new_era_count: int,
                          era_cfg: "dict | None") -> dict:
    """Resolves ml.era_exclusion to the armed/active decision for THIS
    load, from `new_era_count` (rows tagged LABEL_ERA_TRIPLE_BARRIER that
    already survived every OTHER admissibility check this loader applies -
    book/dirty/clash-dedup/epoch).

    `era_cfg is None` (load_training_data's new trailing kwarg's own
    default - the exact value any pre-existing call site passes with zero
    code change) means STRUCTURALLY INERT: armed=active=False no matter how
    large new_era_count is - mirrors _epoch_cutoff's `epoch_cfg is None` ->
    filter off, so an unmodified caller (an old test, a script not yet
    wired) keeps byte-identical behavior forever, never surprised by a
    corpus that happens to cross the threshold under it. An EXPLICIT dict
    (even {}) opts in to the threshold-arming logic with its documented
    defaults - deliberately NOT the same test _epoch_cutoff uses (which
    requires an explicit `exclude_old_candidates: true` even when the dict
    is present): this feature's whole point is to auto-activate on the
    DATA once a caller is wired, not wait for a human to flip a bit.

    armed = new_era_count >= min_new_era_rows (config_guard-bounded: a
    non-negative number, default ML_ERA_EXCLUSION_MIN_NEW_ERA_ROWS_DEFAULT
    = ml.min_train_rows = ml.model_selection.min_total_rows['gbt'/'blend'],
    docs/quant/2026-07-26_era_exclusion.md's threshold justification).
    active = the filter's real effect on THIS load: (armed OR forced_on)
    AND NOT forced_off. forced_off is the rollback path and always wins
    (config_guard forbids forced_on and forced_off both true - a
    contradictory operator intent). forced_on is a manual override lever,
    SHIPPED false: the threshold arms this feature, not an operator
    flipping a switch (config_guard FATALs forced_on while ml.label_mode
    isn't the mode that can ever produce the era this filter selects for).

    Module-level purely to keep load_training_data's mccabe complexity
    under the C901 ceiling (pyproject.toml) - same established pattern as
    _epoch_cutoff/_row_epoch_excluded above; no behavior difference from
    inlining it there."""
    if era_cfg is None:
        return {"armed": False, "active": False, "forced_off": False,
                "forced_on": False,
                "min_new_era_rows": ML_ERA_EXCLUSION_MIN_NEW_ERA_ROWS_DEFAULT,
                "new_era_rows": new_era_count}
    min_rows = era_cfg.get("min_new_era_rows",
                          ML_ERA_EXCLUSION_MIN_NEW_ERA_ROWS_DEFAULT)
    if isinstance(min_rows, bool) or not isinstance(min_rows, (int, float)) \
            or min_rows < 0:
        # config_guard is the enforcement point (FATAL on a live config);
        # this resolver only degrades safely for a caller that bypassed it
        # (a test, or a corrupt config write) - fail to the documented
        # default rather than crash a training load over a bad threshold.
        min_rows = ML_ERA_EXCLUSION_MIN_NEW_ERA_ROWS_DEFAULT
    min_rows = int(min_rows)
    forced_off = bool(era_cfg.get("forced_off", False))
    forced_on = bool(era_cfg.get("forced_on", False))
    armed = new_era_count >= min_rows
    active = (armed or forced_on) and not forced_off
    return {"armed": armed, "active": active, "forced_off": forced_off,
            "forced_on": forced_on, "min_new_era_rows": min_rows,
            "new_era_rows": new_era_count}


def _apply_era_exclusion(X: list, y: list, w: list, sig: list, meta: list,
                         era_tags: list, era_cfg: "dict | None",
                         current_era: str = LABEL_ERA_TRIPLE_BARRIER) -> tuple:
    """LOAD-TIME VIEW ONLY: when the resolved decision (_era_exclusion_decide)
    is active, subsets the fully-built (pre-numpy) row lists down to
    LABEL_ERA_TRIPLE_BARRIER rows only - INCLUDING dropping old-era LIVE
    rows (the operator's explicit override of ml.epoch's "live rows never"
    rule, docs/quant/2026-07-26_era_exclusion.md). Runs as the LAST step
    before load_training_data's numpy conversion, after every existing
    weight/stat computation (uniqueness, mass-preserving rescale,
    prior-skew, label_era/era_mix_drift telemetry, lineage/divergence
    stats) - none of that pre-existing math ever sees a different row set
    because of this filter. The inactive case (below threshold, or forced
    off) returns the five lists UNCHANGED (same objects), so a
    below-threshold or rolled-back load is byte-identical to a load with
    no era_cfg at all - the round-trip guarantee this task is bound by.

    Returns (X, y, w, sig, meta, stats) - `stats` is the exact dict this
    task adds to last_load_stats['era_exclusion'] (armed/active/forced_off/
    forced_on/new_era_rows/min_new_era_rows/excluded), always present
    regardless of whether anything was actually excluded.

    Module-level purely to keep load_training_data's mccabe complexity
    under the C901 ceiling (pyproject.toml) - same established pattern as
    every other _era_*/_epoch_* helper above; no behavior difference from
    inlining it there."""
    # `current_era` (2026-07-31): the era THIS config's labeler produces.
    # It was hardcoded to the un-qualified LABEL_ERA_TRIPLE_BARRIER, which
    # silently broke the moment the era name gained a horizon qualifier
    # (triple_barrier_h24 after label_max_bars 96 -> 24): the NEW rows -
    # including the first live tb_time rows the horizon fix finally
    # produced - were excluded as "not the new era" while the STALE
    # 96-bar rows were kept as if they were current. The kept era must be
    # the one the running config actually labels under, or the filter
    # preserves exactly the rows it exists to remove.
    n = len(era_tags)
    new_era_count = sum(1 for e in era_tags if e == current_era)
    stats = _era_exclusion_decide(new_era_count, era_cfg)
    if not stats["active"] or n == 0:
        stats["excluded"] = {"total": 0, "by_era_source": {}}
        return X, y, w, sig, meta, stats
    keep = []
    excluded_by_era_source: dict = {}
    for i in range(n):
        if era_tags[i] == current_era:
            keep.append(i)
            continue
        src = meta[i][2] or "unknown"
        bucket = excluded_by_era_source.setdefault(era_tags[i], {})
        bucket[src] = bucket.get(src, 0) + 1
    stats["excluded"] = {"total": n - len(keep),
                        "by_era_source": excluded_by_era_source}
    return ([X[i] for i in keep], [y[i] for i in keep], [w[i] for i in keep],
            [sig[i] for i in keep], [meta[i] for i in keep], stats)


# One-way marker (rollout hazard fix, task-rotation-report.md): when
# _ensure_schema rotates the corpus (old-header production file under new
# code), every consumer reading it - evidence-gate row floors, a scheduled
# retrain, status.json's row count - sees a near-empty file until
# scripts/corpus_sync.py's recover_local_baks() merges the fresh .bak_*
# back in. That normally waits for the supervisor's hourly corpus-sync
# cadence (scripts/pc_supervisor.py CORPUS_SYNC_SEC). Dropping a marker
# file next to the corpus - the SAME cross-process seam this codebase
# already uses (status.json, control/ command files) - lets the
# supervisor collapse that wait to its next ~30s tick instead, with NO
# import of scripts/ from here: this module writes a file, it does not
# know what a supervisor is. Written on rotation only; the supervisor
# owns clearing it (self-clearing + idempotent - see
# pc_supervisor._corpus_sync_due), so a write here is a cheap, best-effort
# touch, never a merge, never a git op.
CORPUS_ROTATION_MARKER_NAME = ".corpus_rotated"


class HistoryStore:
    def __init__(self, path: str = "outputs/signal_history.csv",
                 max_bars: int = _TB_LEGACY_MAX_BARS):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # ml.label_max_bars, threaded in so a NEW triple_barrier row can
        # persist a horizon-qualified era tag (see _row_era). Extend-
        # with-defaults: the default IS the shipped 96, so every existing
        # caller writes the same un-suffixed era it always did.
        self.max_bars = int(max_bars)
        self._pending: dict = {}      # position_id -> features
        # stats of the most recent load_training_data pass (clean live count
        # for the evidence gate, uniqueness mean, prior-skew flag)
        self.last_load_stats: dict = {}
        # geometry-alignment T6 (spec D6, ML-082): bounded rolling window of
        # {"agree": bool, "abs_delta_pct": float} — one entry per BRACKET
        # close (barrier in tb_pt/tb_sl/tb_time), appended incrementally by
        # log_close -> _record_bracket_divergence at CLOSE time (never at a
        # training load, unlike last_load_stats above — a close happens far
        # more often than a retrain and this instrument must not wait for
        # one). Process-local, never snapshotted: report-only telemetry, a
        # restart costs at most one window's worth of history (mirrors
        # last_load_stats' own non-persistence — the durable source of
        # truth is the CSV corpus itself). See bracket_divergence_summary().
        self._bracket_divergence: list = []
        # Task 4 (#103) regime-coverage hold: per-regime LIVE label counts,
        # O(1) at admission time via regime_live_count(). Load-time init
        # (first call runs ONE full-CSV scan, mtime/size-cached exactly
        # like source_counts below) + incremental maintenance at the same
        # place live rows are appended (_append_row) - never a per-cycle
        # re-scan. Pure derived cache, NEVER snapshotted: the CSV is the
        # durable source of truth and a cold process rebuilds this lazily
        # on first use, same as source_counts/asset_counts/row_count.
        self._regime_live_counts: dict = {}
        self._regime_counts_loaded = False
        self._regime_counts_key = None
        # SPB-R scarcity pricing (2026-07-30 spec §1.1): per-ASSET LIVE
        # label counts, O(1) at admission time via asset_live_counts().
        # Same design as the per-regime counter above - load-time init
        # ((mtime, size)-cached exactly like source_counts), incremental
        # maintenance at _append_row, pure derived cache, NEVER
        # snapshotted (the CSV is the durable source of truth).
        self._asset_live_counts: dict = {}
        self._asset_live_loaded = False
        self._asset_live_key = None
        # era-gated training exclusion (docs/quant/2026-07-26_era_exclusion.md):
        # edge-triggered per-INSTANCE flag so the ML-081 activation log fires
        # once per inactive->active transition, never once per load (binding
        # behaviour #4) - a long-lived process (the runner's self.history)
        # sees exactly one log line the moment the corpus crosses the
        # threshold; flipping back off (rollback) resets the edge so a later
        # re-crossing logs again, same edge-triggered convention as every
        # other transition log in this codebase.
        self._era_exclusion_active_seen = False
        # meta column named "side": FEATURE_NAMES also contains "direction",
        # and a duplicated CSV header made DictReader consumers silently read
        # whichever column came last.
        self._header = ["position_id", "asset", "side", *FEATURE_NAMES,
                        "label", "net_pnl_usd", "source", "ts", "signal_ts",
                        "barrier", "probe", "disp", "candidate_id", "book",
                        "label_era", "pt_frac", "sl_frac",
                        *[f"sg_{k}" for k in SG_COMPONENT_KEYS],
                        "entry_price", "exit_price", *AVAIL_COLS]
        # disp: the signal's final DISPOSITION - "entered", "confirmed"
        # (candidate never taken), or a veto code (capped / SZ-* / pretrade).
        # Closes the loop on the unbiased candidate sample: gate and
        # EV-threshold tuning can now be done OFFLINE against labeled
        # outcomes split by what the pipeline actually did with the signal.
        # Bookkeeping only - never a feature, never a weight.
        # probe: "1" = PT-050 exploration probe (profit-EV gate bypassed
        # to buy the label), "0" = conviction entry, "" = candidate row or
        # pre-2026-07-20 unknown. BOOKKEEPING ONLY - never a feature, and
        # probe rows keep FULL live training weight (a probe's outcome is
        # honest ground truth); OF-5 uses it to grade the conviction-only
        # sample while exploration still mixes EV-negative probes in.
        # candidate_id (W2-4, 2026-07-23): on a LIVE row, the position_id of
        # the "candidate" row this trade was registered as at signal time
        # (CandidateLabeler.open_candidate_id) - "" when no matching open
        # candidate was found, or on rows written before this field existed.
        # This is the twin-dedup JOIN KEY: funding_dist (ml/features.py) is
        # a continuous function of wall-clock ts, recomputed fresh every
        # cycle, so a deferred entry's live features can drift off its
        # candidate's by more than the exact-vector match's 6-decimal
        # precision. Lineage catches what the vector match cannot; the
        # vector match stays as the fallback for legacy rows with no
        # recorded lineage. BOOKKEEPING ONLY - never a feature.
        # book (Compounder Phase C, Task C1): which strategy book opened
        # this position - "5m" (existing scalping flow, the default for
        # every pre-C row and every caller that never heard of the long
        # book) or "long" (risk/long_book.py). BOOKKEEPING ONLY - never a
        # feature.
        # label_era (label-era instrumentation, DEEP DIVE progress.md):
        # which LABEL DEFINITION produced this row's barrier value -
        # "legacy" (plain triple-barrier, blank/absent barrier or
        # barrier=="pt"), "exit_sim" (simulate_exit_policy() replay:
        # trail/realized/sl/time/tier/floor), or "exit_sim_time_stop"
        # (barrier=="time_stop", the P2 rung, commit 5f26d3f). See
        # label_era_of (module-level, above) for the full derivation.
        # Computed and written EXPLICITLY at append time from this same
        # row's `barrier` argument (never left blank for a new row); a
        # row written before this column existed gets the IDENTICAL
        # derivation applied at LOAD time (load_training_data via
        # _row_label_era) - no migration, no rewritten history. LAST
        # column so every existing row/consumer is untouched but for
        # this one trailing field. BOOKKEEPING ONLY - never a feature,
        # and this task NEVER changes a label/weight/row (report-only).
        # pt_frac, sl_frac (geometry-alignment T3, 2026-07-27, spec D2/D6):
        # the barrier_geometry() (pt_frac, sl_frac) this row's label was
        # computed under, FRACTIONS of entry (0.02 = 2%) - every row becomes
        # self-describing so Task 6's live-vs-label comparator can read the
        # exact bet a row was labeled on without recomputing it from sigma/
        # cost at a possibly-different config. Written EXPLICITLY at append
        # time from CandidateLabeler._label's triple_barrier branch (the
        # ONLY call site whose output reaches the persisted corpus, see that
        # method's docstring); every other caller (live rows via log_close,
        # exit_policy-mode labels, pre-bump rows) defaults 0.0 = "unknown/
        # legacy geometry" - no migration derives a value for them, unlike
        # label_era above, because there is no single fixed bracket to back
        # out for an exit_policy replay. LAST two columns so every existing
        # row/consumer is untouched but for these two trailing fields.
        # BOOKKEEPING ONLY - never a feature.
        # entry_price, exit_price (2026-08-04): the absolute price the
        # row's bet was anchored at, and the price it resolved at. The
        # corpus carried pt_frac/sl_frac (FRACTIONS of entry) but no
        # price level anywhere, so a row could not be re-examined in
        # price space at all: re-deriving a label at a different horizon,
        # aligning a row against an external OHLC tape, or auditing a
        # realized return all need the anchor, and none of them were
        # possible. Found 2026-08-04 when a horizon change to 432 bars
        # made relabelling the 9,175 pre-existing rows the obvious move
        # and it turned out the data to do it had never been recorded.
        # 0.0 = unknown/legacy row - no migration can invent a price, so
        # old rows stay 0.0 forever and consumers must treat 0.0 as
        # "absent" rather than as a price. LAST two columns so every
        # existing row/consumer is untouched but for these two trailing
        # fields. BOOKKEEPING ONLY - never a feature: absolute price is
        # non-stationary and would leak level information into a model
        # that must generalize across regimes.
        # sg_flow..sg_conc (gate-truth instrumentation, 2026-07-28): the
        # informed-flow engine's RAW signed component scores at signal
        # time (positive = long evidence), the fused evidence Σw·s and
        # the normalized-HHI concentration — SG_COMPONENT_KEYS order.
        # 0.0 = pre-instrumentation row / legacy five_gate engine /
        # warmup. Direction alignment is derived at READ time
        # (scripts/gate_truth_report.py: s_i × direction), never baked
        # in. Non-finite values sanitize to 0.0 at append — telemetry
        # never drops a row. LAST seven columns so every existing
        # row/consumer is untouched. BOOKKEEPING ONLY — never a feature.

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
            # Invalidate the derived LIVE counters (2026-08-06). Both caches
            # key on the corpus's (mtime_ns, size) and are refreshed AFTER
            # each append - but a rotation here replaces the file wholesale
            # while the in-memory counts still describe the OLD corpus. The
            # next append then stamps the NEW file's key onto the STALE
            # counts, and _load_regime_counts/_load_asset_live_counts see a
            # matching key and refuse to re-scan. Reproduced as a 6x asset
            # overcount that the cache actively protected from correction.
            # These are not telemetry: asset_live_counts is n_a in SPB-R
            # scarcity pricing (position SIZING) and regime_live_count gates
            # the regime-coverage admission hold.
            self._regime_counts_loaded = False
            self._regime_counts_key = None
            self._asset_live_loaded = False
            self._asset_live_key = None
            self._mark_rotated()
        with open(self.path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(self._header)

    def _mark_rotated(self) -> None:
        """Drop CORPUS_ROTATION_MARKER_NAME next to the corpus so the
        supervisor's next tick runs corpus_sync (recovery) immediately
        instead of waiting out the hourly cadence - see the module-level
        comment above. Best-effort: an unwritable outputs/ (ACL, disk
        full) must never block the rotation itself, only lose the fast
        path (recovery still lands on the normal hourly cadence)."""
        try:
            (self.path.parent / CORPUS_ROTATION_MARKER_NAME).touch()
        except OSError:
            pass

    def log_entry(self, position_id: str, asset: str, direction: str,
                features: np.ndarray, probe: bool = False,
                candidate_id: "str | None" = None, book: str = "5m",
                gate_components: "dict | None" = None,
                avail: "dict | None" = None):
        # signal time captured HERE: rows are appended at label time, and
        # the purged walk-forward must order/purge by when the SIGNAL
        # happened, not when its barrier resolved. avail (41b) likewise:
        # the flags describe the feeds at the moment the features were
        # built, not at close. None is preserved (-> blank UNKNOWN
        # columns), never coerced to a dict of falses.
        self._pending[position_id] = (asset, direction, features.copy(),
                                      time.time(), bool(probe),
                                      candidate_id or "", book,
                                      dict(gate_components or {}),
                                      dict(avail) if avail else None)

    def _row_era(self, barrier: str) -> str:
        """The era tag persisted on a NEW row. Identical to
        label_era_of() for every era except triple_barrier, which is
        qualified by the horizon that produced it (see
        triple_barrier_era): the 2026-07-31 move of `label_max_bars`
        96 -> 24 changes what a `tb_*` label MEANS, and two label
        definitions must never share one era name. `label_max_bars` is
        read from the store's own config (self.max_bars, set at
        construction); a store built without one keeps the legacy 96 and
        therefore the un-suffixed name - byte-identical to the shipped
        behavior for every existing caller."""
        era = label_era_of(barrier)
        if era != LABEL_ERA_TRIPLE_BARRIER:
            return era
        return triple_barrier_era(getattr(self, "max_bars",
                                          _TB_LEGACY_MAX_BARS))

    def _append_row(self, position_id: str, asset: str, direction: str,
                    feats: np.ndarray, label: int, pnl_usd: float,
                    source: str, signal_ts: float | None = None,
                    barrier: str = "", probe: str = "", disp: str = "",
                    candidate_id: str = "", book: str = "5m",
                    pt_frac: float = 0.0, sl_frac: float = 0.0,
                    gate_components: "dict | None" = None,
                    entry_price: float = 0.0, exit_price: float = 0.0,
                    avail: "dict | None" = None):
        # avail (owed 41b): context-availability flags captured at SIGNAL
        # time (main._feature_extras "avail" dict, keys web/equity/options/
        # frozen). Falsy -> all AVAIL_COLS written blank = UNKNOWN (legacy
        # rows, paths that don't carry it); a recorded dict writes "1"/"0".
        self._ensure_schema()
        # width invariant: a row must have exactly as many fields as the
        # header. The header check above only guards the FILE's schema -
        # a stale feature vector (e.g. a candidate persisted before a
        # FEATURE_NAMES bump and restored after) would silently write a
        # short, misaligned row. Observed live 2026-07-12: 4 pre-SMC
        # 36-feature candidates labeled under the 43-feature header.
        # Both the guard and its message derive from ONE pair of constants
        # (_N_LEAD/_N_TRAIL). They used to be two independent literals - a
        # correct `22` in the test and a stale `20` in the message - and the
        # `20` silently drifted as sg_* (7) and entry_price/exit_price (2)
        # were appended, so the one line a human reads while debugging a
        # misaligned corpus reported a phantom 69-column schema against a
        # true 64. Derived, they cannot drift apart again.
        if _N_LEAD + len(feats) + _N_TRAIL != len(self._header):
            log.warning(tag(
                Code.ML_SCHEMA_MISMATCH,
                f"refusing to append row "
                f"{position_id[:12]} ({asset}): {len(feats)} features vs "
                f"schema {len(self._header) - _N_LEAD - _N_TRAIL} - stale "
                f"pre-rotation vector, row would misalign under the "
                f"current header"))
            return
        # finiteness invariant: a NaN/inf slips through float() silently
        # (float('nan') never raises) and poisons the corpus - one non-finite
        # feature NaNs an entire gradient/AUC/Brier downstream, and a NaN label
        # trains on garbage truth. Refuse at the store boundary so the
        # ground-truth dataset is clean BY CONSTRUCTION, not cleaned later. The
        # engine should never emit one; if it does, dropping the label is far
        # cheaper than silently corrupting every retrain that reads it.
        fa = np.asarray(feats, dtype=float)
        if (not np.all(np.isfinite(fa)) or not np.isfinite(float(pnl_usd))
                or not np.isfinite(float(pt_frac))
                or not np.isfinite(float(sl_frac))):
            bad = [FEATURE_NAMES[i] for i in np.flatnonzero(~np.isfinite(fa))
                   if i < len(FEATURE_NAMES)]
            log.warning(tag(
                Code.ML_DIRTY_LABEL,
                f"refusing non-finite {source} "
                f"row {position_id[:12]} ({asset}): "
                f"{bad or 'pnl/pt_frac/sl_frac'} not finite - label dropped, "
                f"corpus kept clean"))
            return
        sg = {}
        src_sg = gate_components if isinstance(gate_components, dict) else {}
        for k in SG_COMPONENT_KEYS:
            try:
                v = float(src_sg.get(k, 0.0))
            except (TypeError, ValueError):
                v = 0.0
            sg[k] = v if np.isfinite(v) else 0.0
        now = time.time()
        row = [position_id, asset, direction,
               *[f"{v:.6f}" for v in feats],
               label, f"{pnl_usd:.2f}", source,
               f"{now:.0f}",
               f"{signal_ts if signal_ts else now:.0f}",
               barrier, probe, disp, candidate_id, book,
               self._row_era(barrier),
               f"{pt_frac:.6f}", f"{sl_frac:.6f}",
               *[f"{sg[k]:.4f}" for k in SG_COMPONENT_KEYS],
               f"{entry_price:.10g}", f"{exit_price:.10g}",
               *(["", "", "", ""] if not avail else
                 [str(int(bool(avail.get(k, False))))
                  for k in ("web", "equity", "options", "frozen")])]
        # torn-tail heal + fsync (2026-08-06). This is the ground-truth
        # training corpus and the highest-value append-only file in the
        # repo: a kill mid-row welded the fragment to the NEXT row, and
        # load_training_data's `except (KeyError, ValueError): continue`
        # dropped the chimera with no counter and no log line - so the
        # corpus lost TWO labelled outcomes per kill, invisibly. The
        # header is already guaranteed by _ensure_schema above, so this
        # only needs the isolation write and the fsync.
        durable_append(self.path, lambda f: csv.writer(f).writerow(row))
        # Task 4 (#103): fold a LIVE row straight into the per-regime
        # counter incrementally - never wait for the next admission's
        # lazy re-scan. If the counter has never been loaded yet in this
        # process, skip: the eventual first regime_live_count() call runs
        # a full scan that already sees this row (it's on disk now), so
        # seeding a partial dict here would only risk drifting from a
        # scan that supersedes it anyway.
        if source == "live" and self._regime_counts_loaded:
            lbl = _regime_of_feats(fa)
            if lbl is not None:
                self._regime_live_counts[lbl] = \
                    self._regime_live_counts.get(lbl, 0) + 1
                try:
                    st = self.path.stat()
                    self._regime_counts_key = (st.st_mtime_ns, st.st_size)
                except OSError:
                    pass
        # SPB-R: same incremental fold for the per-ASSET live counter -
        # skip when never loaded (the eventual first asset_live_counts()
        # call runs a full scan that already sees this on-disk row).
        if source == "live" and self._asset_live_loaded:
            self._asset_live_counts[asset] = \
                self._asset_live_counts.get(asset, 0) + 1
            try:
                st = self.path.stat()
                self._asset_live_key = (st.st_mtime_ns, st.st_size)
            except OSError:
                pass

    def log_close(self, position_id: str, net_pnl_usd: float,
                 barrier: str = "realized", pt_frac: float = 0.0,
                 sl_frac: float = 0.0, entry_usd: float = 0.0,
                 cost_pct: float = 0.0, telemetry_cfg: "dict | None" = None,
                 entry_price: float = 0.0, exit_price: float = 0.0):
        """`barrier` (geometry-alignment T5, spec D1): defaults to
        "realized" - the exact legacy hardcoded tag, so every caller that
        predates T5's bracket-exit engine is byte-identical. A closed
        BRACKET position's caller (main._finalize_position) passes the
        VERBATIM close reason ("tb_pt"/"tb_sl"/"tb_time") only when that
        is what actually closed it - label_era_of then tags the row
        LABEL_ERA_TRIPLE_BARRIER, joining the live corpus to the era the
        model is trained on (V1's closure - see the geometry-alignment
        design doc). Any OTHER close reason (tier/stop/hard-stop/ratchet/
        flatten/...) still falls back to the "realized" default -
        deliberately never threaded verbatim (label_era_of's vocabulary
        would tag most of them LABEL_ERA_UNKNOWN).

        `pt_frac`/`sl_frac` (T5): the bracket geometry this position was
        entered under (0.0 = no bracket / legacy), threaded into the SAME
        persisted columns candidate rows already carry (T3) so every live
        row is self-describing regardless of which reason closed it.

        `entry_usd`/`cost_pct`/`telemetry_cfg` (T6, spec D6, ML-082): new,
        all default-inert (0.0 / {}) so every caller that predates the
        bracket-divergence comparator is byte-identical. Feed
        _record_bracket_divergence below - see that method's docstring for
        why the comparator uses the position's OWN stamped geometry instead
        of re-running triple_barrier() on recorded bars."""
        entry = self._pending.pop(position_id, None)
        if entry is None:
            # The ONLY unlogged exit in the write path until 2026-08-06.
            # A close with no pending vector writes no training row, and
            # silence here meant ground-truth attrition could only be
            # detected by reconstructing closes from fills.csv. Legitimate
            # causes exist (a FEATURE_SCHEMA_VERSION bump deliberately
            # drops pending vectors, core/persistence.py), so this is a
            # counter, not an alarm - but it must be VISIBLE.
            self.unlabeled_closes = getattr(self, "unlabeled_closes", 0) + 1
            log.warning(tag(
                Code.ML_UNLABELED_CLOSE,
                f"close "
                f"{position_id[:12]} had no pending feature vector - no "
                f"training row written ({self.unlabeled_closes} so far "
                f"this process)"))
            return
        probe = False
        cand_id = ""
        book = "5m"
        gate_comp = None
        avail = None
        if len(entry) == 9:
            (asset, direction, feats, sig_ts, probe, cand_id, book,
             gate_comp, avail) = entry
        elif len(entry) == 8:
            (asset, direction, feats, sig_ts, probe, cand_id, book,
             gate_comp) = entry
        elif len(entry) == 7:
            asset, direction, feats, sig_ts, probe, cand_id, book = entry
        elif len(entry) == 6:
            asset, direction, feats, sig_ts, probe, cand_id = entry
        elif len(entry) == 5:
            asset, direction, feats, sig_ts, probe = entry
        elif len(entry) == 4:
            asset, direction, feats, sig_ts = entry
        else:                                   # pre-upgrade snapshot shape
            asset, direction, feats = entry
            sig_ts = None
        label = int(net_pnl_usd > 0)
        self._append_row(position_id, asset, direction, feats, label,
                        net_pnl_usd, "live", signal_ts=sig_ts,
                        barrier=barrier or "realized",
                        probe="1" if probe else "0", disp="entered",
                        candidate_id=cand_id or "", book=book or "5m",
                        pt_frac=pt_frac, sl_frac=sl_frac,
                        gate_components=gate_comp, entry_price=entry_price,
                        exit_price=exit_price, avail=avail)
        log.info(f"labeled trade {position_id[:8]}: label={label} "
                f"pnl=${net_pnl_usd:,.2f}")
        if barrier in ("tb_pt", "tb_sl", "tb_time"):
            self._record_bracket_divergence(
                barrier, pt_frac, sl_frac, cost_pct, net_pnl_usd, entry_usd,
                telemetry_cfg or {})

    def _record_bracket_divergence(self, barrier: str, pt_frac: float,
                                   sl_frac: float, cost_pct: float,
                                   net_pnl_usd: float, entry_usd: float,
                                   tele_cfg: dict) -> None:
        """ML-082 (geometry-alignment T6, spec D6): labeled-vs-realized
        bracket comparator - "is the traded bet's outcome the labeled bet's
        outcome". Report-only PROOF instrument, never gates anything.

        APPROACH CHOSEN, and why: the spec's preferred approach re-runs
        triple_barrier() on the recorded bars spanning this position's
        entry, using the position's OWN stamped pt_frac/sl_frac. The live
        engine keeps no such bar history per position (Position/
        PortfolioState carry price/size/fractions, not an OHLC window; the
        vol engine's candle cache is a rolling per-ASSET snapshot, already
        overwritten by the time a position closes hours later) and adding
        one would be new data-collection infrastructure, not
        instrumentation - out of this task's scope (spec D6 lists this as
        a report-only proof instrument, not a data-pipeline task). This
        method therefore takes the spec's own documented fallback: the
        labeled counterfactual is derived ANALYTICALLY from the barrier
        that fired plus the position's own stamped geometry and entry cost
        estimate - the exact bet the label formula (ml/labeling.py's
        triple_barrier/BarrierOutcome) would have booked if bars had
        behaved exactly as the barrier distance implies:
          tb_pt   -> +pt_frac*100 - cost_pct   (profit barrier, net of cost)
          tb_sl   -> -sl_frac*100 - cost_pct   (stop barrier, net of cost)
          tb_time -> realized_ret_pct itself   (no fixed distance to a time
                     barrier - triple_barrier()'s own "time" branch prices
                     off the ACTUAL close at the horizon, i.e. exactly what
                     the live close realized, so there is no separate
                     counterfactual to diverge from; delta is 0 by
                     construction and every tb_time close "agrees")
        The comparator this produces answers "did live EXECUTION (fills,
        slippage, actual fees vs the entry's cost estimate) land where the
        label's own formula says a clean pt/sl bracket resolution should
        land" - divergence flags execution quality against the labeling
        assumption, which is exactly what feeds the cost model (D4).

        `entry_usd` <= 0 (unknown notional, e.g. a legacy/test caller that
        never threads it) skips recording entirely - never fabricate a
        return off a zero denominator (mirrors postmortem.on_close's own
        NaN-on-zero-notional guard)."""
        if entry_usd <= 1e-9:
            return
        realized_ret_pct = net_pnl_usd / entry_usd * 100.0
        if barrier == "tb_pt":
            counterfactual_ret_pct = pt_frac * 100.0 - cost_pct
        elif barrier == "tb_sl":
            counterfactual_ret_pct = -sl_frac * 100.0 - cost_pct
        else:                                    # tb_time
            counterfactual_ret_pct = realized_ret_pct
        delta = abs(realized_ret_pct - counterfactual_ret_pct)
        tol = float(tele_cfg.get("bracket_divergence_tolerance_pct", 0.15))
        win = max(int(tele_cfg.get("bracket_divergence_window_n", 100)), 10)
        agree = delta <= tol
        # `priced` marks the records where agreement was actually MEASURED.
        # tb_time's counterfactual IS realized_ret_pct (above), so its delta
        # is 0 by construction and it always "agrees" - it carries no
        # information about whether the traded bet resolved where the label
        # says it should. Measured 2026-08-06 over the instrument's whole
        # lifetime: 33 of 35 records (94.3%) were tb_time, so the published
        # agree_rate of 1.0000 was 94% arithmetically incapable of being
        # anything else. Keeping the tb_time rows (they are real closes)
        # but reporting the rate over the PRICED subset is the honest
        # version, and it matches how bracket_divergence_summary already
        # reports absence as None rather than as a flattering zero.
        self._bracket_divergence.append(
            {"agree": agree, "abs_delta_pct": delta,
             "priced": barrier in ("tb_pt", "tb_sl")})
        if len(self._bracket_divergence) > win:
            self._bracket_divergence = self._bracket_divergence[-win:]
        log.info(tag(
            Code.ML_BRACKET_DIVERGENCE,
            f"{barrier} realized="
            f"{realized_ret_pct:+.3f}% counterfactual="
            f"{counterfactual_ret_pct:+.3f}% delta={delta:.3f}pp "
            f"agree={agree}"))

    def bracket_divergence_summary(self) -> dict:
        """ML-082 status surface (T6): {"n", "n_priced", "agree_rate",
        "mean_abs_ret_delta_pct"} over the rolling window
        _record_bracket_divergence maintains. n=0/agree_rate=None/
        mean_abs_ret_delta_pct=None whenever no bracket close has been
        recorded yet - honest absence (DL-6), never a fabricated 0/0/0
        that would read as "perfect agreement" instead of "not measured".
        Read by runner.py's status build into status["ml"]["bracket_
        divergence"] and scripts/gc_pusher.py's gauge emission ONLY -
        report-only, never consumed by a decision path.

        `agree_rate` and `mean_abs_ret_delta_pct` are computed over the
        PRICED subset only (tb_pt/tb_sl) and are None until one exists:
        a tb_time record's delta is 0 by construction, so including them
        published a 1.0000 agreement gauge that was 94.3% definitional
        (2026-08-06 measurement over the instrument's full lifetime).
        `n` stays the count of ALL bracket closes so the two numbers
        together say "of N closes, only M could be measured" - which is
        the fact an operator needs, and which a single blended rate hid.
        """
        win = self._bracket_divergence
        n = len(win)
        priced = [w for w in win if w.get("priced")]
        if not priced:
            return {"n": n, "n_priced": 0, "agree_rate": None,
                    "mean_abs_ret_delta_pct": None}
        agree_rate = sum(1 for w in priced if w["agree"]) / len(priced)
        mean_abs = sum(w["abs_delta_pct"] for w in priced) / len(priced)
        return {"n": n, "n_priced": len(priced),
                "agree_rate": round(agree_rate, 4),
                "mean_abs_ret_delta_pct": round(mean_abs, 4)}

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

    def _load_regime_counts(self) -> None:
        """Load-time init pass for regime_live_count: one full CSV scan,
        gated on (mtime, size) exactly like source_counts - only re-scans
        when the file changed UNDER this process (e.g. an external
        migrate_history.py run), never per admission call. Live rows this
        process itself appends afterward are folded in incrementally by
        _append_row instead of re-triggering a scan."""
        try:
            st = self.path.stat()
            key = (st.st_mtime_ns, st.st_size)
        except OSError:
            self._regime_live_counts = {}
            self._regime_counts_loaded = True
            self._regime_counts_key = None
            return
        if self._regime_counts_loaded and self._regime_counts_key == key:
            return
        counts: dict = {}
        try:
            with open(self.path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("source") != "live":
                        continue
                    lbl = _regime_of_csv_row(row)
                    if lbl is not None:
                        counts[lbl] = counts.get(lbl, 0) + 1
        except (OSError, csv.Error):
            return
        self._regime_live_counts = counts
        self._regime_counts_loaded = True
        self._regime_counts_key = key

    def regime_live_count(self, regime_label: str) -> int:
        """O(1)-at-admission per-regime LIVE label count (Task 4, #103
        regime-coverage hold): rows with source=='live' whose regime
        one-hot marks `regime_label`. Always routes through
        _load_regime_counts, which is a cheap stat()-and-return once
        loaded (mirrors source_counts) - a full CSV re-scan only happens
        on the very first call, or if the file changed under this process
        (never a per-admission re-read)."""
        self._load_regime_counts()
        return self._regime_live_counts.get(regime_label, 0)

    def _load_asset_live_counts(self) -> None:
        """SPB-R (spec §1.1): load-time init pass for asset_live_counts -
        one full CSV scan, (mtime, size)-gated exactly like
        _load_regime_counts above; live rows this process appends
        afterward fold in incrementally via _append_row."""
        try:
            st = self.path.stat()
            key = (st.st_mtime_ns, st.st_size)
        except OSError:
            self._asset_live_counts = {}
            self._asset_live_loaded = True
            self._asset_live_key = None
            return
        if self._asset_live_loaded and self._asset_live_key == key:
            return
        counts: dict = {}
        try:
            with open(self.path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("source") != "live":
                        continue
                    asset = row.get("asset")
                    if asset:
                        counts[asset] = counts.get(asset, 0) + 1
        except (OSError, csv.Error):
            return
        self._asset_live_counts = counts
        self._asset_live_loaded = True
        self._asset_live_key = key

    def asset_live_counts(self) -> dict:
        """SPB-R scarcity pricing (2026-07-30 spec §1.1): per-asset LIVE
        (real closed-trade) label counts - the n_a term of w_asset =
        clip(sqrt(T_a/(1+n_a)), F, 1). O(1) at admission time: routes
        through _load_asset_live_counts (a cheap stat()-and-return once
        loaded, mirroring regime_live_count exactly); a full CSV re-scan
        only happens on the very first call or when the file changed
        under this process. NOT asset_counts() (all labeled rows,
        candidate-dominated) - scarcity is priced on LIVE labels only."""
        self._load_asset_live_counts()
        return dict(self._asset_live_counts)

    def load_training_data(self, half_life_days: float = 30.0,
                        candidate_weight: float = 0.4,
                        manip_discount: float = 0.5, return_sig: bool = False,
                        weights_cfg: dict | None = None,
                        return_label_times: bool = False,
                        telemetry_cfg: dict | None = None,
                        epoch_cfg: dict | None = None,
                        era_cfg: dict | None = None) -> tuple:
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
        evidence gate, uniqueness mean, prior-skew flag).

        `telemetry_cfg` (config ml.telemetry) gates only the ML-077 log
        line's threshold (lineage_min_pairs); the lineage-twin agreement
        stat itself (T2.2b) is always computed into
        self.last_load_stats["lineage_agreement"] regardless. It also
        supplies `divergence_window_h` (default 24.0), the bucket width for
        the T2.2a live-covered-window divergence score (ML-078), always
        computed into self.last_load_stats["sim_live_divergence"] over rows
        that survive into the trained corpus - detection only, never
        reweighting.

        `epoch_cfg` (config ml.epoch, T3.6 loader seam - SHIPPED OFF)
        gates an opt-in production-corpus filter: when
        epoch_cfg.get("exclude_old_candidates") is truthy AND
        candidate_cutoff_ts is a valid number (_epoch_cutoff), CANDIDATE
        rows whose resolve `ts` is strictly before the cutoff are
        excluded from training, counted into
        self.last_load_stats["epoch_excluded"]. This check runs AFTER the
        SYNTHETIC-vs-REAL clash-dedup below, so epoch_excluded counts only
        rows this filter itself removes (not rows dedup would have
        dropped anyway) and a pre-cutoff candidate that is a live row's
        lineage twin still reaches the dedup branch first, keeping the
        ML-077 lineage-agreement stat populated with the filter on. LIVE
        rows are NEVER
        excluded by this filter, structurally - the check only ever runs
        inside the `source == "candidate"` branch below, so no
        combination of config, malformed rows, or missing fields can
        reach a live row. Off by default (exclude_old_candidates: false):
        the production flip, if the Task 6 experiment verdict ever
        justifies it, is its own conscious commit, never a side effect
        of this default. This is a different consumer of the SAME
        ml.epoch.candidate_cutoff_ts than scripts/overfit_check.py's
        report-only --epoch-ab experiment arm (ml/overfit.py
        build_epoch_ab_mask) - that one measures the cutoff inside OF-3's
        PBO space without ever touching this loader; this one is the
        production-path seam that would apply it for real.

        `era_cfg` (config ml.era_exclusion, operator decision 2026-07-26,
        docs/quant/2026-07-26_era_exclusion.md - see _era_exclusion_decide/
        _apply_era_exclusion above for the full mechanism) gates a SECOND,
        DIFFERENT production-corpus filter: era-based (label_era_of), never
        a clock, so it is orthogonal to epoch_cfg above and both may be
        active together. Threshold-armed: once the corpus's new-era
        (LABEL_ERA_TRIPLE_BARRIER) row count reaches
        era_cfg["min_new_era_rows"], every OLD-era row - LEGACY/EXIT_SIM/
        TIME_STOP/UNKNOWN - is excluded from the training view, INCLUDING
        LIVE rows (a conscious operator override of epoch_cfg's
        live-rows-never rule: all measured live rows are themselves
        old-era, so keeping them would shrink the corpus without cleaning
        it). `era_cfg=None` (the default) is structurally inert - this is
        an opt-in kwarg, not a config default a caller inherits by
        accident. Applied as the LAST step before this method's return, so
        it never perturbs the uniqueness/prior-skew/mix-drift/lineage/
        divergence math above (all still computed over the full
        pre-exclusion corpus). Surfaced in full in
        self.last_load_stats["era_exclusion"] (armed/active/forced_off/
        forced_on/new_era_rows/min_new_era_rows/excluded by era and
        source); the activation transition (inactive -> active) logs
        Code.ML_ERA_EXCLUSION_ACTIVE once, never once per load.
        self.last_load_stats["rows"]/["live_clean"] ARE corrected to the
        post-exclusion count (unlike the other stats above) - they are the
        evidence-gate-facing "what actually trains" numbers (main.py's
        model_selection admission, scripts/overfit_check.py's and
        scripts/feature_stability.py's own n_live mirror, gc_pusher's
        Grafana export all read them), same convention epoch_cfg's
        exclusions already follow (baked in earlier, inside the per-row
        loop). LOAD-TIME VIEW ONLY - no row is ever removed from
        outputs/signal_history.csv; flipping era_cfg off (or the config's
        forced_off) restores the exact pre-exclusion training set,
        including these two counts."""
        self.last_load_stats = {}
        if not self.path.exists():
            return _empty_training_tuple(return_sig, return_label_times)
        # SYNTHETIC-vs-REAL clash guard. A taken trade is written TWICE: once
        # as a live row (realized close = REAL label, full weight) and once as
        # the candidate it was registered as at signal time (triple-barrier
        # counterfactual = SYNTHETIC label, candidate_weight). Possibly
        # CONTRADICTORY labels (a stop-out realizes 0 while the barrier said
        # 1). Training on both double-counts the taken signal and teaches
        # the model a coin-flip at that exact X. Ground truth wins: drop the
        # synthetic twin of any real row. Untaken-signal candidates (no live
        # twin) stay fully usable - the model still learns from all the
        # shadow data, it just never CLASHES with what actually happened.
        #
        # W2-4: matching used to be BY EXACT FEATURE VECTOR alone (6-decimal
        # string equality). funding_dist (ml/features.py) is a continuous
        # function of wall-clock ts, recomputed fresh every cycle - a signal
        # confirmed on cycle 1 (candidate row written with feats_A) whose
        # entry is deferred by a veto that clears on cycle 2+ gets a live
        # order whose features are recomputed later (feats_B != feats_A).
        # The exact-vector match then silently fails and BOTH rows survive
        # as a contradictory near-duplicate - precisely the failure this
        # guard exists to prevent. LINEAGE fixes it: the live row threads the
        # id of the candidate it descends from (candidate_id column,
        # CandidateLabeler.open_candidate_id); that id is definitive proof
        # of correlation regardless of feature drift, and is tried FIRST.
        # The exact-vector match remains as the fallback for legacy rows
        # written before candidate_id existed (no lineage recorded either
        # side) - never a numeric tolerance, which would risk merging
        # genuinely distinct signals.
        # Compounder Phase C (task C5): book=="long" rows are the
        # long-horizon accumulation book's own realized closes - a
        # completely different trading process (patient, ladder-gated
        # accumulation, no p(win)/edge signal) from the 5m scalping flow
        # this model trains for. EXCLUDED here, at the very first read of
        # every row this method ever makes, so they can influence NEITHER
        # the X/y arrays below NOR this clash-dedup prescan (a long-book
        # live row coincidentally sharing an (asset, side, feature-vector)
        # tuple with a 5m candidate must never spuriously mark that
        # candidate a "duplicate" of a real fill it has nothing to do
        # with). (row.get("book") or "5m") mirrors every other book-tag
        # read site's default (pre-C1 rows / any writer that never heard
        # of `book`). T2.2b: live_label_by_cid pairs a live row's
        # candidate_id against its REALIZED label so the lineage-match
        # drop branch below can pair the candidate's proxy label against
        # the live twin's without a second file read. Extracted to
        # _scan_live_dedup_keys (module-level) purely to keep this
        # method's mccabe complexity under the C901 ceiling - no
        # behavior difference from inlining it here.
        live_keys, live_cand_ids, live_label_by_cid = \
            _scan_live_dedup_keys(self.path)
        X, y, w, sig = [], [], [], []
        meta = []            # (asset, end_ts, source, barrier) per kept row
        now = time.time()
        dropped_clash = 0
        dropped_dirty = 0
        # T3.6 loader seam (config ml.epoch, SHIPPED OFF): resolved ONCE
        # here, not per-row, so the per-row check below is a single call.
        epoch_cutoff = _epoch_cutoff(epoch_cfg)
        epoch_excluded = 0
        # T2.2b: (proxy label, realized label) twin agreement flags, one per
        # lineage-match drop below (1 = agree, 0 = disagree). The exact-vector
        # fallback match has no defensible pairing and captures nothing.
        pair_flags: list = []
        # T2.2a: (signal_ts, "live"|"cand", label) per row that SURVIVES into
        # the dataset - the corpus the model actually trains on. Deduped
        # clash drops are NOT captured here (they're already covered by the
        # T2.2b lineage-pair stat above); this feeds sim_live_divergence
        # below, computed after the loop.
        _div_t: list = []
        _div_s: list = []
        _div_y: list = []
        # label-era instrumentation (DEEP DIVE, progress.md): which LABEL
        # DEFINITION produced each SURVIVING row, one tag per kept row -
        # lines up with meta/y by construction (appended together below,
        # once per row that reaches X/y/w). Feeds _era_reason_stats/
        # _era_mix_drift_check after the loop; never influences X/y/w.
        _era_tags: list = []
        with open(self.path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                # task C5: same book=="long" exclusion as the prescan
                # above - this is the ONE place that actually builds
                # X/y, so this line is the load-bearing half of the
                # contamination pin (the prescan's copy is defense in
                # depth for the dedup keys, this one is the real gate).
                if (row.get("book") or "5m") == "long":
                    continue
                # Clash-dedup runs BEFORE the epoch check (reordered - see
                # note below): this is the only branch that populates
                # pair_flags, so every candidate row - pre- or post-cutoff -
                # must reach it first, or the lineage-twin instrument
                # (last_load_stats["lineage_agreement"]) silently goes dark
                # whenever the epoch filter is on and a pre-cutoff candidate
                # happens to be the lineage twin of a live row.
                if row.get("source") == "candidate" and \
                        (live_keys or live_cand_ids):
                    self_id = (row.get("position_id") or "").strip()
                    if self_id and self_id in live_cand_ids:
                        dropped_clash += 1
                        lv = live_label_by_cid.get(self_id)
                        if lv is not None:
                            try:
                                pair_flags.append(
                                    1 if float(row["label"]) == lv else 0)
                            except (KeyError, ValueError):
                                pass
                        continue     # W2-4: lineage match - definitive
                    try:
                        if (row["asset"], row["side"],
                                tuple(row[n] for n in FEATURE_NAMES)) in live_keys:
                            dropped_clash += 1
                            continue     # legacy fallback: exact-vector match
                    except KeyError:
                        pass
                # T3.6 loader seam: structurally scoped to source==
                # "candidate" so a live row can never be reached by this
                # continue, no matter what config/row data says - see
                # _row_epoch_excluded's docstring for the full guarantee.
                # Runs AFTER clash-dedup (reordered, whole-phase review
                # Fix 2): with the epoch check first, a pre-cutoff candidate
                # that clash-dedup would have dropped anyway was instead
                # counted as epoch_excluded and never reached the dedup
                # branch, which (a) undercounted dropped_clash/pair_flags -
                # collapsing the ML-077 lineage instrument to n_pairs=0
                # whenever the epoch filter is on - and (b) overcounted
                # epoch_excluded with rows dedup would have removed anyway,
                # so it no longer equalled the true number of rows the
                # epoch filter itself removed. Ordering dedup first fixes
                # both: epoch_excluded now counts only rows THIS filter
                # actually removes. Flag OFF -> epoch_cutoff is None ->
                # _row_epoch_excluded is always False -> this continue never
                # fires either way, so the off-path (shipped default) is
                # byte-identical to before this reorder.
                if row.get("source") == "candidate" and \
                        _row_epoch_excluded(row, epoch_cutoff):
                    epoch_excluded += 1
                    continue
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
                _div_t.append(sr)
                _div_s.append("live" if row.get("source") == "live" else "cand")
                _div_y.append(yr)
                _era_tags.append(_row_label_era(row))
        if dropped_clash:
            log.info("training load: dropped %d synthetic candidate row(s) "
                     "that duplicated a real live trade (kept the realized "
                     "label; %d rows remain)", dropped_clash, len(X))
        if dropped_dirty:
            log.warning(tag(
                Code.ML_DIRTY_LABEL,
                f"training load skipped {dropped_dirty} row(s) with "
                f"non-finite features/label (legacy/imported dirty data) - "
                f"{len(X)} clean rows remain"))
        # ---- de Prado corrections (config ml.sample_weights; AFML ch.4) ----
        # KNOWN OMISSION vs the book (2026-07-29 literature audit):
        # sequential bootstrap (AFML sec. 4.5) is deliberately not
        # implemented — it only affects resampling-based families
        # (EnsembleMLP/AdaptiveGBT bags); logistic/GBT consume these
        # uniqueness weights directly, and the book's own experiments show
        # the accuracy effect is second-order. Revisit if mean uniqueness
        # stays < ~0.3 while a bagged family wins selection.
        wc = weights_cfg or {}
        _tele_cfg = telemetry_cfg or {}
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
                if y[i] == 0.0 and meta[i][3] in _VERTICAL_BARRIER_REASONS:
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
                    log.warning(tag(
                        Code.ML_PRIOR_SKEW,
                        f"trailing {win_h:.0f}h label prior {p_recent:.2f} "
                        f"skews from corpus prior {p_all:.2f} "
                        f"(>{thresh:.2f}) — one-sided batch; watch "
                        f"calibration (detection only, weights untouched)"))
        # Kish effective sample size over the FINAL weights (Debate-1
        # item D, report-only): ESS = (sum w)^2 / sum(w^2) - the honest
        # "how many independent rows is this really" figure beside
        # mean_uniqueness (Kish 1965; the rescale above preserves mass,
        # ESS measures the concentration that remains).
        _sw = float(sum(w))
        _sw2 = float(sum(x * x for x in w))
        ess_kish = (_sw * _sw / _sw2) if _sw2 > 0.0 else 0.0
        log.info("training load: %d rows, mean_uniqueness %.3f, "
                 "Kish ESS %.1f", len(w), uniq_mean, ess_kish)
        self.last_load_stats = {
            "rows": len(w), "dropped_dirty": dropped_dirty,
            "dropped_clash": dropped_clash,
            "live_clean": sum(1 for m in meta if m[2] == "live"),
            "mean_uniqueness": round(uniq_mean, 4),
            "ess_kish": round(ess_kish, 1),
            "prior_recent": p_recent, "prior_overall": p_all,
            "prior_skew": skew_flag,
            "epoch_excluded": epoch_excluded,
            # label-era instrumentation (DEEP DIVE, progress.md): per-era,
            # per-exit-reason row count + label rate (_era_reason_stats),
            # and the barrier/exit-reason MIX drift alarm (binding
            # behaviour #3, _era_mix_drift_check) - both report-only,
            # both computed over the same surviving-corpus rows as
            # prior_skew above, never touching X/y/w.
            "label_era": _era_reason_stats(_era_tags, meta, y),
            "era_mix_drift": _era_mix_drift_check(meta, _tele_cfg),
        }
        # lineage-pair agreement stat (T2.2b, ML-077): simulator-fidelity
        # telemetry over the dedup-discarded (proxy label, realized label)
        # twins captured above - report-only, never touches weights.
        n_pairs = len(pair_flags)
        if n_pairs:
            agree = sum(pair_flags) / n_pairs
            lo, hi = wilson_interval(sum(pair_flags), n_pairs)
            la = {"n_pairs": n_pairs, "agreement": round(agree, 4),
                  "wilson95": [round(lo, 4), round(hi, 4)]}
            if n_pairs >= int(_tele_cfg.get("lineage_min_pairs", 10)):
                log.info(tag(
                    Code.ML_LINEAGE_AGREEMENT,
                    f"lineage-twin agreement {100 * agree:.1f}% over "
                    f"{n_pairs} pairs (Wilson95 [{lo:.2f}, {hi:.2f}]) - "
                    f"gate-passing signals only; detection-only, weights "
                    f"untouched"))
        else:
            la = {"n_pairs": 0, "agreement": None, "wilson95": None}
        self.last_load_stats["lineage_agreement"] = la
        # live-covered-window divergence score (T2.2a, ML-078): candidate-
        # vs-live label-mean divergence inside windows where BOTH sources
        # appear in the surviving corpus, plus the coverage stat. Report-
        # only - no reweighting, no authority over what trains.
        self.last_load_stats["sim_live_divergence"] = _sim_divergence_stat(
            _div_t, _div_s, _div_y, _tele_cfg)
        # era-gated training exclusion (operator decision, 2026-07-26,
        # docs/quant/2026-07-26_era_exclusion.md): the LAST filter applied,
        # after every stat/weight computation above - see
        # _apply_era_exclusion's docstring for why that ordering is the
        # round-trip guarantee. ML-081 fires once per inactive->active
        # transition (edge-triggered on the instance, never per load).
        X, y, w, sig, meta, era_excl_stats = _apply_era_exclusion(
            X, y, w, sig, meta, _era_tags, era_cfg,
            current_era=triple_barrier_era(
                getattr(self, "max_bars", _TB_LEGACY_MAX_BARS)))
        if era_excl_stats["active"] and not self._era_exclusion_active_seen:
            log.info(tag(
                Code.ML_ERA_EXCLUSION_ACTIVE,
                f"era-gated training exclusion ACTIVATED - "
                f"{era_excl_stats['new_era_rows']} new-era row(s) "
                f"(>= threshold {era_excl_stats['min_new_era_rows']}) - "
                f"{era_excl_stats['excluded']['total']} old-era row(s) "
                f"excluded from the training view, including live rows "
                f"(operator decision, "
                f"docs/quant/2026-07-26_era_exclusion.md)"))
        self._era_exclusion_active_seen = era_excl_stats["active"]
        self.last_load_stats["era_exclusion"] = era_excl_stats
        # "rows"/"live_clean" describe what actually feeds the fit (the
        # SAME convention the epoch filter above already established -
        # its exclusions are baked into these two counts because they
        # happen earlier, inside the per-row loop). era-exclusion runs
        # AFTER these were first computed, so they must be corrected here
        # or a widely-read evidence-gate input (main.py's model_selection
        # ladder admission, scripts/overfit_check.py's and
        # scripts/feature_stability.py's own n_live mirror, gc_pusher's
        # Grafana export) would silently disagree with the training
        # arrays actually returned below the moment this filter goes
        # active - admitting a higher-capacity family (or reporting a
        # healthier corpus than exists) on stale pre-exclusion evidence.
        # A no-op when inactive: w/meta are the SAME objects, so these
        # recompute to the identical values already set above.
        self.last_load_stats["rows"] = len(w)
        self.last_load_stats["live_clean"] = sum(
            1 for m in meta if m[2] == "live")
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


# ---------------------------------------------------------------------------
# ONE loader seam for every OFFLINE consumer (2026-08-01 audit H12 + the
# sample-weight-kwargs drift). The five offline consumers (train_meta,
# overfit_check, learning_curve, feature_stability, interpret_report) each
# hand-rolled their own HistoryStore construction and load kwargs. Two
# knobs drifted as a result:
#
#   * max_bars was never passed, so `current_era` resolved to the legacy
#     triple_barrier_era(96) while main.py:714 passes ml.label_max_bars.
#     config_guard FATALs label_max_bars >= max_bars_no_progress (36), so a
#     valid LIVE config can never BE 96 - the offline default was
#     structurally guaranteed to disagree, and with era exclusion armed on
#     both sides the offline corpus was the exact COMPLEMENT of
#     production's (measured: 2141 rows/0 live vs 1090 rows/14 live).
#     train_meta then DEPLOYED the model fitted on that complement.
#   * half_life_days/candidate_weight/manip_discount were passed as
#     literals (or omitted), so retuning ml.sample_weights was honored by
#     the in-process retrain and silently ignored by the CLI.
#
# Routing every consumer through these two functions is what makes the
# next knob impossible to thread to one consumer and not the rest.
# Deliberately NOT resolved here: telemetry_cfg (ML-077/078 logging
# thresholds - runner-only telemetry) and epoch_cfg (an opt-in production
# corpus filter, shipped off; overfit_check measures that cutoff through
# its own report-only --epoch-ab arm and must not double-apply it).
# Callers that want them pass them explicitly through **overrides.
def store_for_config(ml_cfg: dict, path: "str | None" = None,
                     factory=HistoryStore):
    """HistoryStore built the way the ENGINE builds it (main.py:714-719):
    corpus path and label horizon both from config. `path` overrides
    ml.history_path for a caller with its own --history flag; `factory`
    exists for test doubles. Paths stay RELATIVE when config says so -
    scripts resolve the corpus cwd-relative and tests depend on it."""
    cfg = ml_cfg or {}
    # max_bars decides current_era (triple_barrier_h<N>), so reading it from
    # config is the WHOLE point of this seam: the bare constructor's legacy
    # 96 made every offline consumer keep the exact COMPLEMENT of the rows
    # the engine trains on. The legacy value stays the DEFAULT so a config
    # without the key is byte-identical to the old behavior.
    return factory(path or cfg.get("history_path",
                                   "outputs/signal_history.csv"),
                   max_bars=int(cfg.get("label_max_bars",
                                        _TB_LEGACY_MAX_BARS)))


def load_for_config(store, ml_cfg: dict, **overrides) -> tuple:
    """load_training_data with the SAME sample-weight and era kwargs
    main.py:5672-5677 uses. Every value defaults to the literal the
    consumers previously hardcoded, so with the shipped config this is
    behavior-preserving; it is the CONFIG that becomes authoritative.
    `overrides` passes through to load_training_data untouched (return
    arity, telemetry_cfg/epoch_cfg for the callers that own them)."""
    cfg = ml_cfg or {}
    sw = cfg.get("sample_weights", {}) or {}
    # sourced from config exactly as main.py:5871-5875 does; the literals are
    # only the DEFAULTS the consumers used to hardcode, so a config that omits
    # them is behavior-preserving while a retuned one is finally honored by
    # the CLI that ships the artifact, not just by the in-process retrain.
    kwargs = {
        "half_life_days": float(sw.get("half_life_days", 30.0)),
        "candidate_weight": float(sw.get("candidate_weight", 0.4)),
        "manip_discount": float(sw.get("manip_discount", 0.5)),
        "weights_cfg": sw,
        "era_cfg": cfg.get("era_exclusion", {}) or {},
    }
    kwargs.update(overrides)
    return store.load_training_data(**kwargs)


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

    # sigma_bar_pct / pt_frac / sl_frac added 2026-08-01. Without them this
    # file was ANALYTICALLY INERT: 23,826 recorded outcomes that could not be
    # related to the market state that produced them. The obvious join back
    # to signal_history.csv does not exist either - only 70 of 8,429 history
    # rows (0.83%) carry a candidate_id - so the horizon question this
    # recorder was built to answer ("does some asset pay over a longer hold")
    # was unanswerable from its own dataset. These three columns are exactly
    # what makes barrier/horizon-sigma computable per row, which is the
    # quantity that decides whether a horizon produces information at all.
    # UNITS. All three quantitative columns are FRACTIONS of entry price
    # (0.02 = 2%), deliberately the same unit, so
    #     ratio = pt_frac / (sigma_bar_frac * sqrt(horizon_bars))
    # is computable with NO conversion. The first draft of this schema named
    # the column sigma_bar_pct and wrote cand["sigma_bar"] into it - a 100x
    # error, because the FEATURE column of that name in signal_history.csv is
    # a PERCENT (median 0.1033 = 0.1033%) while cand["sigma_bar"] is a
    # FRACTION. Proven by reproducing barrier_geometry with the live config:
    # sigma=0.001033 yields pt_frac 0.020000 / sl_frac 0.015000, matching the
    # observed live minimums exactly; sigma=0.103292 yields 0.103292, which
    # matches nothing. Same failure class as the CSCV label_span bars-vs-
    # seconds bug (2026-07-31): a silent scale error in a research dataset
    # that parses cleanly and means something else. The column name now
    # states the unit and the unit is uniform across the row.
    HEADER = ["candidate_id", "asset", "direction", "horizon_bars",
              "label", "net_ret_pct", "exit_reason", "ts",
              "sigma_bar_frac", "pt_frac", "sl_frac"]

    def __init__(self, path: str = "outputs/horizon_shadow.csv"):
        self.path = Path(path)

    def _ensure(self):
        """Create the file, or ROTATE it when its header predates the
        current schema.

        Appending 11-column rows onto an 8-column file would silently
        mis-align every future read - the failure mode is a dataset that
        parses cleanly and means something else. Rotation follows
        HistoryStore's own .bak_<ts> convention: the old rows are RENAMED,
        never deleted (CLAUDE.md - learning data is never destroyed), and
        remain readable under their original header."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                with open(self.path, newline="", encoding="utf-8") as f:
                    have = next(csv.reader(f), [])
            except (OSError, StopIteration):
                have = []
            if have and have != self.HEADER:
                bak = self.path.with_name(
                    f"{self.path.stem}.bak_{int(time.time())}{self.path.suffix}")
                try:
                    self.path.rename(bak)
                    log.warning(
                        "horizon shadow schema changed (%d -> %d cols) - "
                        "rotated the old rows to %s; nothing deleted",
                        len(have), len(self.HEADER), bak.name)
                except OSError:
                    return          # keep appending in the old shape
        if not self.path.exists():
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(self.HEADER)

    @staticmethod
    def _frac(v) -> str:
        """Sanitize one FRACTION-valued field to CSV text, in four rounds.

        A research dataset's worst failure is a value that parses as a
        number and is wrong, so each round rejects to "" (absent, and
        visibly so) rather than substituting a plausible default:

          1. TYPE     - None, str, Decimal, numpy scalar -> float, or reject.
          2. FINITE   - NaN and +/-inf reject. numpy propagates both silently
                        through sigma estimators, and NaN compares false to
                        every bound, so it would survive a naive range check.
          3. DOMAIN   - a negative sigma or barrier distance is not a small
                        number, it is a sign error upstream; 0 likewise means
                        "no distance" and cannot be divided by. Both reject.
          4. PRECISION- fixed 8-significant-figure text, so a float repr can
                        never widen a row or emit '1e-05' into a CSV column
                        that downstream code parses positionally.
        """
        if v is None:
            return ""
        try:                                    # round 1: type
            x = float(v)
        except (TypeError, ValueError):
            return ""
        if not math.isfinite(x):                # round 2: finite
            return ""
        if x <= 0.0:                            # round 3: domain
            return ""
        return f"{x:.8g}"                       # round 4: precision

    def append(self, candidate_id: str, asset: str, direction: str,
               horizon_bars: int, label: int, net_ret_pct: float,
               exit_reason: str, sigma_bar_frac=None, pt_frac=None,
               sl_frac=None):
        """The three trailing args default to None so every pre-existing
        caller keeps working unchanged (CLAUDE.md extend-with-defaults); a
        row written without them is still valid, just not analysable.

        sigma_bar_frac/pt_frac/sl_frac are all FRACTIONS of entry price -
        see HEADER for why the unit is uniform and how the 100x error that
        motivated it was proven."""
        _n = self._frac
        try:
            self._ensure()
            row = [candidate_id, asset, direction, int(horizon_bars),
                   int(label), f"{net_ret_pct:.6f}", exit_reason,
                   f"{time.time():.0f}",
                   _n(sigma_bar_frac), _n(pt_frac), _n(sl_frac)]
            # durable_append heals a torn tail and re-writes the header on a
            # zero-length file. Both mattered here: _ensure's own creation
            # branch is `if not self.path.exists()`, which a size-0 file
            # passes THROUGH, so a kill in the create-to-first-flush window
            # left a headerless file that csv.DictReader then read with the
            # first RESEARCH ROW as its column names (2026-08-06 sweep).
            durable_append(self.path, lambda f: csv.writer(f).writerow(row),
                           header=",".join(self.HEADER) + "\r\n")
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
        # the SAME question a live trade poses - training on the bet we trade,
        # but the label then encodes WHICH EXIT FIRED (a risk-control choice)
        # rather than whether the signal itself was any good; "triple_barrier"
        # (the config default since the 2026-07-26 signal-quality task,
        # task-signalquality-brief.md) is the market/horizon-only symmetric
        # pt/sl barrier this measures instead - see _label below for the
        # tb_-prefixed vocabulary that keeps the two label populations
        # distinguishable in label_era_of. exit_policy needs a policy object
        # (built from config by the caller); absent one we fall back to the
        # barrier so this can never crash for a caller that didn't supply it.
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
        # cost-floored barrier geometry (spec D2, 2026-07-27,
        # geometry-alignment T2): floors the SIGMA INPUT to
        # barrier_geometry() so the profit distance is never < N round-trip
        # costs, one knob, pt:sl ratio preserved by construction. Code
        # default 0.0 = legacy (no floor); config.json ships 4.0.
        self.pt_cost_mult = float(cfg.get("label_pt_cost_mult", 0.0))
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
        # Pool capacity is CONFIG-OWNED (config.json ml.max_open_candidates)
        # and coherence-guarded in core/config_guard.py: the pool is a
        # Little's-law queue (slots = arrivals/h x residence), and with
        # multi_horizon shadows on every candidate holds its slot for the
        # FULL label horizon - so the cap must scale with label_max_bars.
        # The 200 fallback here is the 8h-era size, kept only as the
        # undeclared-key default; config_guard mirrors it (its capacity
        # check must size the cap that will actually run) and a test pins
        # the pair. Do not resize here: config.json carries the capacity.
        self.max_candidates = int(cfg.get("max_open_candidates", 200))
        # ZOMBIE-EVICTION margin (2026-08-16 defect-A fix, owed item 84):
        # grace bars past the label window end before an UNRESOLVABLE
        # candidate (stale/absent bars - _maybe_evict_zombie) is censored out
        # of the pool. A LIVENESS bound, not a signal threshold: eviction
        # additionally requires the data gate, so the margin only decides
        # how long a provably-dead candidate may keep its slot. 24 bars =
        # 2h at 5m, matching the measured zombie boundary (the 2026-08-16
        # audit classed slots older than horizon+2h as zombies: 32/187).
        # Config-owned (ml.candidate_evict_margin_bars, guarded in
        # core/config_guard.py); this literal is only the undeclared-key
        # default.
        self.evict_margin_bars = int(
            cfg.get("candidate_evict_margin_bars", 24))
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
                spread_bps: float = 0.0,
                confidence: "float | None" = None,
                gate_components: "dict | None" = None,
                avail: "dict | None" = None) -> bool:
        """Returns True when a candidate row was actually appended -
        the SCS latch must only be consumed by a REAL append (a dedup
        no-op would silently discard the state-change lesson the
        sampler exists to capture). Interface extended, not changed:
        legacy callers ignored the None return.

        `confidence` is the candidate's entry meta p(win); when present it lets
        the exit-policy labeler mirror the live conviction-runner trail (W2-1).
        None (the default) preserves every legacy caller and yields the
        full-leash label as before."""
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
        self._cands.append({"disp": "confirmed",
                            "id": f"cand-{self._id_salt}-{self._seq}",
                            "asset": asset,
                            "direction": direction,
                            # 41b: feed availability at SIGNAL time; None =
                            # unrecorded (legacy persisted candidates) ->
                            # blank UNKNOWN columns at label time
                            "avail": dict(avail) if avail else None,
                            "features": features.copy(),
                            "sigma_bar": float(max(sigma_bar, 1e-5)),
                            "bar_time": bar_time,
                            # asset's execution spread at signal time, folded
                            # into the label's round-trip cost at poll time
                            "spread_bps": float(max(spread_bps, 0.0)),
                            # entry meta p(win): threaded into the exit-policy
                            # label sim so a borderline-confidence candidate is
                            # labeled with the SAME trail the live runner gives
                            # it (W2-1). None -> full-leash label (unchanged).
                            "confidence": (float(confidence)
                                           if confidence is not None else None),
                            # which gates passed at signal time (JSON-safe
                            # bools); the labeled outcome feeds per-gate stats
                            "gates": {str(g): bool(v) for g, v in
                                      gates_passed.items()}
                            if isinstance(gates_passed, dict) else None,
                            # gate-truth instrumentation: the RAW signed
                            # component scores at signal time — persisted
                            # onto this candidate's labeled row so the
                            # realization path can grade the weights.
                            "gate_components": (dict(gate_components)
                                                if isinstance(
                                                    gate_components, dict)
                                                else None)})
        return True

    def open_candidate_id(self, asset: str, direction: str) -> "str | None":
        """Read-only peek at the id of the newest OPEN candidate for
        (asset, direction) - the same match mark_disposition uses, but
        non-mutating. Lets the caller thread the candidate's identity into
        the live order's meta BEFORE knowing whether the entry will
        actually succeed (a peek never stamps disposition; mark_disposition
        still does that, only on the confirmed outcome).

        This is the W2-4 lineage join key: the live row's candidate_id and
        the candidate row's own position_id let load_training_data
        correlate a taken signal's two rows even when its features drift
        across cycles (funding_dist is a clock function recomputed fresh
        every cycle - a deferred entry's live features can differ from its
        candidate's by more than an exact-vector match would tolerate)."""
        for cand in reversed(self._cands):
            if cand.get("asset") == asset and cand.get("direction") == direction:
                return cand.get("id")
        return None

    def mark_disposition(self, asset: str, direction: str, code: str):
        """Stamp the NEWEST open candidate for (asset, direction) with the
        pipeline's final verdict on that signal - entered, or the veto that
        stopped it. Best-effort: no matching open candidate (evicted,
        already labeled, sampler-thinned) is a silent no-op.

        The cap was 40 and it CUT THROUGH THE PAYLOAD (2026-08-06). A full
        SZ-023 disposition is 113 chars:
            'SZ-023: p 0.28 below bar 0.63 (net breakeven 0.594 + margin
             0.036, derived) [bracket pt=2.06% sl=1.54% b=0.983]'
        and 40 chars kept it only as far as '(net break'. Measured on the
        corpus: 2,614 SZ-023 rows lost the bracket geometry the sizer had
        just computed, 1,052 SZ-030 rows lost their net breakeven and
        b_net, and ZERO of 9,692 rows retained a '[bracket ...]' payload.
        That geometry is the whole reason a vetoed candidate is worth
        filing - it is the bet that WOULD have been traded, and
        scripts/gate_efficacy_report.py regex-scrapes this very field to
        recover the thresholded quantity. 200 clears the longest
        constructed disposition with headroom; a cap still exists because
        an unbounded free-text column in a 9,692-row corpus is its own
        hazard, and the veto strings are engine-generated, not user
        input."""
        for cand in reversed(self._cands):
            if cand.get("asset") == asset and cand.get("direction") == direction:
                cand["disp"] = str(code)[:DISPOSITION_MAX_CHARS]
                return

    def _cost_pct(self, cand: dict) -> float:
        """Round-trip cost for this candidate's label: the fee floor plus,
        when enabled, the asset's own (capped) execution spread."""
        cost = self.rt_cost_pct
        if self.label_include_spread:
            spread = min(float(cand.get("spread_bps", 0.0)),
                         self.spread_cap_bps)
            cost += spread / 100.0     # bps -> percent
        return cost

    def poll(self, now: "float | None" = None) -> int:
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
        written exactly once.

        `now` (epoch seconds, the engine's cycle clock - main.py passes
        its own `now` so replay stays deterministic) arms ZOMBIE EVICTION
        (2026-08-16 defect-A fix): a candidate whose age exceeds the
        label horizon plus ml.candidate_evict_margin_bars, and whose
        asset's cached bars provably cannot produce its label (see
        _is_zombie), is CENSORED - removed with ML-085, NO label row
        written. Age is measured against the engine clock, never bar
        arrival, so a dead feed cannot squat pool slots forever (the
        pre-fix state: the only unlabelable-drop rule was the bar-window
        slide, which itself needs new bars). None (the default, every
        legacy caller) disarms eviction - behavior identical to before
        this parameter existed."""
        written = 0
        evicted: dict = {}
        # per-asset array cache, ONE conversion per asset per poll: bars do
        # not mutate inside poll() (update_candles runs between cycles), and
        # rebuilding three ~horizon*5-element arrays per CANDIDATE made this
        # loop's cost scale with pool size x bar window - the 36h-horizon
        # capacity lift multiplies the pool several-fold, the bar window is
        # already 5x the horizon, and the outputs are bit-identical either
        # way.
        arrs: dict = {}
        for cand in list(self._cands):
            b = self._bars.get(cand["asset"])
            if not b or cand["bar_time"] not in b["t"]:
                # entry bar evicted or never cached: unlabelable, drop
                if b and b["t"] and cand["bar_time"] < b["t"][0]:
                    self._cands.remove(cand)
                else:
                    # bars absent, or the entry bar never arrived and the
                    # feed has since gone stale: the slide-drop above can
                    # never fire without new bars - censor if zombie
                    self._maybe_evict_zombie(cand, now, evicted)
                continue
            i = b["t"].index(cand["bar_time"])
            avail = len(b["t"]) - 1 - i
            if avail < 1:
                self._maybe_evict_zombie(cand, now, evicted)
                continue
            got = arrs.get(cand["asset"])
            if got is None:
                got = (np.array(b["c"], float), np.array(b["h"], float),
                       np.array(b["l"], float))
                arrs[cand["asset"]] = got
            closes, highs, lows = got
            side = 1 if cand["direction"] == "long" else -1
            cost = self._cost_pct(cand)
            if avail >= self.horizon:
                # full window: finish shadows, label if still unlabeled
                if not cand.get("labeled"):
                    out = self._label(closes, highs, lows, i, side,
                                      cand["sigma_bar"], cost,
                                      conviction=cand.get("confidence"))
                    written += self._emit_label(
                        cand, out, entry_price=float(closes[i]),
                        exit_price=float(closes[min(
                            i + max(int(out.bars_held), 1),
                            len(closes) - 1)]))
                self._record_shadow_horizons(cand, closes, highs, lows, i,
                                             side, cost)
                self._cands.remove(cand)
                continue
            if cand.get("labeled"):
                # waiting only for shadows now - but a frozen feed means
                # the shadow path can never complete either; the primary
                # row is already written, so censoring here loses only
                # the shadow record, never a label
                self._maybe_evict_zombie(cand, now, evicted)
                continue
            out = self._label(closes, highs, lows, i, side,
                              cand["sigma_bar"], cost,
                              conviction=cand.get("confidence"))
            if out.final:                   # resolved inside the window -> final
                written += self._emit_label(
                    cand, out, entry_price=float(closes[i]),
                    exit_price=float(closes[min(
                        i + max(int(out.bars_held), 1),
                        len(closes) - 1)]))
                cand["labeled"] = True
                if not self.horizons:
                    # no multi-horizon shadows to complete: a DECIDED
                    # candidate has no reason to hold a pool slot for the
                    # rest of its label horizon — at max_open_candidates that
                    # retention starved registration of NEW signals for
                    # hours (audit M-finding). Shadows enabled -> keep it
                    # until the full path is recorded, as before.
                    self._cands.remove(cand)
            else:
                # in-window but undecided (the label attempt above just
                # returned non-final): if the bars that could decide it
                # have stopped coming, re-running the same attempt can
                # never change the answer - censor if zombie
                self._maybe_evict_zombie(cand, now, evicted)
        if evicted:
            total = sum(n for n, _ in evicted.values())
            detail = ", ".join(f"{a} x{n} (oldest {h:.1f}h)"
                               for a, (n, h) in sorted(evicted.items()))
            # COUNT SEMANTICS: this tag() bumps ML-085 once per poll that
            # evicted anything — code_stats counts eviction EPISODES (one
            # aggregate line per poll, the ML_SCHEMA_MISMATCH precedent),
            # NOT censored candidates. The per-candidate figure lives in
            # `total`/`detail` on this line, never in the ledger.
            log.warning(tag(
                Code.ML_CAND_ZOMBIE_EVICT,
                f"censored {total} "
                f"unresolvable candidate(s) older than the label horizon "
                f"({self.horizon} bars) + margin ({self.evict_margin_bars} "
                f"bars) with stale/absent bars - no label row written "
                f"({detail})"))
        if written:
            log.info("labeled %d candidate signal(s) via %s",
                     written, self.label_mode)
        return written

    def _maybe_evict_zombie(self, cand: dict, now: "float | None",
                            evicted: dict) -> None:
        """Censor `cand` - remove it from the pool and fold it into
        poll()'s per-asset ML-085 tally (one aggregate log line per
        poll, the ML_SCHEMA_MISMATCH precedent, never per-candidate
        spam) - iff it has outlived its label window plus the configured
        margin AND can never resolve from the data on hand. Called only
        on poll()'s stuck paths (the resolution paths remove the
        candidate before this is ever reached), and built so eviction
        can never race resolution - THREE gates, all required:

        clock - `now` is not None (legacy callers disarm eviction) and
                bar_time is a real epoch timestamp (_EPOCH_CLOCK_FLOOR:
                toy test clocks must never be compared against wall
                time).
        age   - now >= bar_time + (horizon + margin) x 5m bars. Engine
                clock only: a dead feed cannot postpone its own eviction
                by not sending bars.
        data  - the cached bars provably cannot produce the label:
                the latest bar predates the candidate's full window end
                in TIME, and fewer than `horizon` bars follow the entry
                bar in INDEX terms (poll's own resolution arithmetic).
                If EITHER says the window is complete, poll() resolves
                the candidate normally and eviction stands down - a
                healthy at-horizon candidate with flowing bars is
                labeled, never censored.

        A candidate these gates admit is CENSORED: missing data, not an
        outcome. No label row is ever fabricated for it."""
        if now is None:
            return
        try:
            bar_time = float(cand["bar_time"])
        except (TypeError, ValueError):
            return   # corrupt bar_time: age unknowable - keep the exact
            #          pre-fix (squat) behavior rather than grow poll() a
            #          new crash surface; the schema guards own that row
        if bar_time < _EPOCH_CLOCK_FLOOR:
            return
        deadline = bar_time + \
            (self.horizon + self.evict_margin_bars) * BAR_SECONDS
        if float(now) < deadline:
            return
        b = self._bars.get(cand["asset"])
        if b and b["t"]:
            window_end = bar_time + self.horizon * BAR_SECONDS
            if float(b["t"][-1]) >= window_end:
                return              # full window on hand (time terms)
            if cand["bar_time"] in b["t"]:
                i = b["t"].index(cand["bar_time"])
                if len(b["t"]) - 1 - i >= self.horizon:
                    return          # full window on hand (index terms)
        self._cands.remove(cand)
        age_h = (float(now) - bar_time) / 3600.0
        n, oldest = evicted.get(cand["asset"], (0, 0.0))
        evicted[cand["asset"]] = (n + 1, max(oldest, age_h))

    def _label(self, closes, highs, lows, i, side, sigma_bar, cost,
               conviction=None):
        """Dispatch to the configured labeler. exit_policy replays the live
        exit engine (matches how the signal is actually traded); triple_barrier
        is the market/horizon-only symmetric pt/sl that measures SIGNAL
        QUALITY rather than which policy exit fired (2026-07-26 signal-
        quality task, task-signalquality-brief.md). Same signature, same
        BarrierOutcome shape either way.

        `conviction` (the candidate's entry meta p(win)) is threaded only into
        the exit-policy sim, where it mirrors the live conviction-runner trail
        (W2-1); triple_barrier has no such geometry and ignores it.

        `cost` (the candidate's own round-trip cost, from `_cost_pct`) is ALSO
        threaded into the tier-1 cost floor as `est_cost_bps = cost * 100.0`
        (pct -> bps, the exact inverse of the conversion `tier1_cost_floor_pct`
        applies) — the SAME cost basis that already drives the net-of-cost
        label now drives the floor too (Task 1, #103), closing the P3.5
        documented residual: this register-time estimate is a real caller
        that CAN supply est_cost_bps.

        THE ERA-COLLISION FIX: this is the ONLY call site whose
        triple_barrier() output reaches the persisted corpus (via
        _emit_label -> HistoryStore._append_row's `barrier` cell) - the
        shadow-horizon recorder and bootstrap_dataset each call
        triple_barrier() directly and never persist its `barrier` field.
        triple_barrier() itself stays untouched (its own bare "pt"/"sl"/
        "time" vocabulary is depended on directly by other tests/callers);
        prefixing here, once, keeps that single decision point intact
        instead of forking triple_barrier() into barrier-vocabulary
        variants. The "tb_" prefix makes the row self-describing so
        label_era_of (module-level, above) tags it LABEL_ERA_TRIPLE_BARRIER
        - never LABEL_ERA_LEGACY ("pt") or LABEL_ERA_EXIT_SIM ("sl"/"time"),
        which the bare strings would otherwise silently collide with even
        though this is a genuinely different label population."""
        if self.label_mode == "exit_policy" and self.exit_policy is not None:
            return simulate_exit_policy(closes, highs, lows, i, side, sigma_bar,
                                        self.exit_policy, max_bars=self.horizon,
                                        cost_pct=cost, conviction=conviction,
                                        est_cost_bps=cost * 100.0)
        # cost-floored geometry (spec D2): floor the SIGMA INPUT via the
        # shared barrier_geometry() helper (also consumed by the live
        # bracket-exit engine, Task 5), then back out the equivalent
        # sigma so triple_barrier()'s own pt_mult*sigma/sl_mult*sigma math
        # reproduces exactly the same (pt_frac, sl_frac) — the function's
        # signature does not change.
        pt_frac, sl_frac = barrier_geometry(sigma_bar, cost, self.pt,
                                            self.sl, self.pt_cost_mult)
        sigma_eff = pt_frac / self.pt if self.pt > 0 else sigma_bar
        out = triple_barrier(closes, highs, lows, i, side, sigma_eff,
                             self.pt, self.sl, self.horizon, cost_pct=cost)
        # (geometry-alignment T3) stamp the exact bracket this row's label
        # was decided under, so the persisted row is self-describing -
        # Task 6's comparator reads pt_frac/sl_frac straight off the row
        # instead of recomputing them from sigma/cost at a possibly-
        # different config.
        return replace(out, barrier=f"tb_{out.barrier}",
                       pt_frac=pt_frac, sl_frac=sl_frac)

    def _emit_label(self, cand: dict, out, entry_price: float = 0.0,
                    exit_price: float = 0.0) -> int:
        self.store._append_row(cand["id"], cand["asset"],
                            cand["direction"], cand["features"],
                            out.label, 0.0, "candidate",
                            signal_ts=float(cand["bar_time"]),
                            barrier=str(getattr(out, "barrier", "") or ""),
                            disp=str(cand.get("disp") or ""),
                            pt_frac=float(getattr(out, "pt_frac", 0.0) or 0.0),
                            sl_frac=float(getattr(out, "sl_frac", 0.0) or 0.0),
                            gate_components=cand.get("gate_components"),
                            entry_price=entry_price, exit_price=exit_price,
                            avail=cand.get("avail"))
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
            pt_frac, _sl_frac = barrier_geometry(cand["sigma_bar"], cost,
                                                 self.pt, self.sl,
                                                 self.pt_cost_mult)
            sigma_eff = pt_frac / self.pt if self.pt > 0 else cand["sigma_bar"]
            for h in self.horizons:
                if len(closes) - 1 - i < h:
                    continue
                o = triple_barrier(closes, highs, lows, i, side,
                                   sigma_eff, self.pt, self.sl,
                                   h, cost_pct=cost)
                # sigma and BOTH barrier fractions travel with the outcome:
                # barrier/(sigma*sqrt(h)) is the quantity that decides
                # whether a horizon can produce information, and it is not
                # reconstructable later - sigma_bar is a per-signal market
                # state, and the cost floor means pt_frac is NOT simply
                # pt * sigma_bar.
                self.shadow_store.append(
                    cand["id"], cand["asset"], cand["direction"], h,
                    o.label, o.ret_pct, o.barrier,
                    sigma_bar_frac=cand.get("sigma_bar"),
                    pt_frac=pt_frac, sl_frac=_sl_frac)
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
                log.warning(tag(
                    Code.ML_SCHEMA_MISMATCH,
                    f"dropped {n} restored "
                    f"candidate(s) from feature-schema v{ver} (current "
                    f"v{FEATURE_SCHEMA_VERSION}) - same width, different "
                    f"meaning; they re-register fresh"))
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
            log.warning(tag(Code.ML_SCHEMA_MISMATCH,
                            f"dropped {stale} "
                            f"restored "
                            f"candidate(s) with pre-rotation feature width "
                            f"(current schema: {want} features)"))
        self._cands = [c for c in cands if len(c["features"]) == want]
        # CAP-SHRINK enforcement (2026-08-16 defect-B fix, owed item 85):
        # register() only holds pool size CONSTANT at the cap (pop-then-
        # append), so a cap DECREASE in config was never enforced against
        # a larger restored pool - it stayed oversized until candidates
        # resolved. Truncate here, in the SAME eviction direction
        # register() uses at cap: drop the NEWEST (list tail; the head is
        # closest to resolving and has waited longest for its label).
        overflow = len(self._cands) - self.max_candidates
        if overflow > 0:
            self._cands = self._cands[:self.max_candidates]
            log.warning(tag(
                Code.ML_CAND_RESTORE_TRUNCATED,
                f"restored "
                f"candidate pool ({overflow + self.max_candidates}) "
                f"exceeds ml.max_open_candidates "
                f"({self.max_candidates}) - dropped the {overflow} "
                f"newest restored candidate(s) (register()'s own at-cap "
                f"eviction direction)"))
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
                    pt_cost_mult: float = 0.0,
                    label_mode: str = "triple_barrier", exit_policy=None,
                    return_sig: bool = False):
    """EMA-cross pseudo-signals -> labels over history.

    `return_sig` (default False = the historical 2-tuple, every existing
    caller unchanged) additionally returns the per-row ENTRY BAR timestamp
    (epoch seconds, `candles_5m[i]["time"]`), the same clock
    load_training_data's `sig` carries. scripts/train_meta.py's cold-start
    path vstacks one block PER SYMBOL over the same ~10-day window, so the
    concatenated matrix's clock RESTARTS at each block boundary and
    purged_walk_forward's row-count purge (documented "correct ONLY if rows
    are evenly spaced in time") trains on ETH labels contemporaneous with -
    in fact strictly LATER than - the BTC rows being tested. Measured OOF
    Brier optimism scaled monotonically with cross-asset return
    correlation (rho=0.85 -> -0.0138, 2.7x the deploy margin). With the
    timestamps in hand the caller can sort the blocks into ONE global clock
    and keep the leak-free TIME purge.

    label_mode "exit_policy" (with an exit_policy) replays the live exit engine
    so bootstrap labels match how a signal is actually traded, consistent with
    the candidate labeler; "triple_barrier" is the legacy symmetric pt/sl.
    Defaults to triple_barrier so existing callers are behavior-exact until
    they opt in.

    `pt_cost_mult` (default 0.0 = legacy, no floor) cost-floors the
    triple_barrier branch's SIGMA INPUT exactly like CandidateLabeler._label
    does post-88a7e09 (spec D2): via the shared barrier_geometry() helper,
    so the cold-start bootstrap corpus and the live candidate corpus that
    scripts/train_meta.py vstacks together are the same bet geometry. Only
    the triple_barrier branch is floored — barrier_geometry() is a
    triple-barrier concept; the exit_policy branch already replays the live
    exit engine's own (unrelated) tier-1 cost floor and is untouched.

    DOCUMENTED RESIDUAL (W2-1): these EMA-cross pseudo-signals carry no meta
    p(win), so no conviction is threaded into the exit-policy sim — bootstrap
    labels run on the FULL runner leash (conviction unavailable, not ignored).
    The live candidate path threads the real entry conviction; the bootstrap
    prior stays full-leash, an accepted 2nd-order approximation for a cold-start
    calibration set.

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
        empty = (np.empty((0, len(FEATURE_NAMES))), np.empty(0))
        return (*empty, np.empty(0)) if return_sig else empty

    fast, slow = _ema(closes, 9), _ema(closes, 21)
    rets = np.diff(np.log(np.maximum(closes, 1e-9)))
    X, y, sig = [], [], []
    name_idx = {n: k for k, n in enumerate(FEATURE_NAMES)}
    for i in range(60, len(closes) - max_bars - 1):
        crossed_up = fast[i] > slow[i] and fast[i - 1] <= slow[i - 1]
        crossed_dn = fast[i] < slow[i] and fast[i - 1] >= slow[i - 1]
        if not (crossed_up or crossed_dn):
            continue
        side = 1 if crossed_up else -1
        sigma_bar = float(rets[max(i - 60, 0):i].std() + 1e-6)
        # `exit_policy is not None` is implied by use_policy (line above);
        # restated inline so the type checker narrows the Optional. Same
        # cost basis threaded into the tier-1 floor as the candidate path
        # (Task 1, #103): est_cost_bps = cost_pct * 100.0 (pct -> bps).
        if use_policy and exit_policy is not None:
            out = simulate_exit_policy(closes, highs, lows, i, side, sigma_bar,
                                       exit_policy, max_bars=max_bars,
                                       cost_pct=cost_pct,
                                       est_cost_bps=cost_pct * 100.0)
        else:
            # cost-floored geometry (spec D2), mirrors CandidateLabeler._label:
            # floor the SIGMA INPUT via the shared barrier_geometry() helper,
            # then back out the equivalent sigma so triple_barrier()'s own
            # pt_mult*sigma/sl_mult*sigma math reproduces the same
            # (pt_frac, sl_frac) — the function's signature does not change.
            pt_frac, _sl_frac = barrier_geometry(sigma_bar, cost_pct, pt_mult,
                                                 sl_mult, pt_cost_mult)
            sigma_eff = pt_frac / pt_mult if pt_mult > 0 else sigma_bar
            out = triple_barrier(closes, highs, lows, i, side, sigma_eff,
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
        # NEUTRALS, not zero-corners (2026-07-29 unit audit): several
        # features define a non-zero "no information" point, and leaving
        # them at the zeros-init made every bootstrap row claim "settling
        # this instant / extreme fear / 0th vol percentile / zero depth"
        # — a systematic train/serve offset on the cold-start prior. Each
        # value is that feature's OWN documented neutral (ml/features.py).
        # depth_ratio (2026-08-01 audit): live default is 1.0 - "depth is at
        # its trailing median" (ml/features.py:404, regime/liquidity_regime
        # .py:47/266), NOT 0.0, which ml/contracts.py's (0, 3) band admits
        # silently as "zero depth / the book has evaporated". The 07-29
        # neutrals block above enumerated six features and missed this one.
        for name, neutral in (("book_touch_share", 0.2),
                              ("funding_dist", 0.5),
                              ("pd_zone", 0.5),
                              ("regime_age", 0.5),
                              ("fear_greed", 0.5),
                              ("vol_percentile", 0.5),
                              ("depth_ratio", 1.0)):
            if name in name_idx:
                setf(name, neutral)
        X.append(feats)
        y.append(float(out.label))
        # ENTRY bar time, matching load_training_data's `sig` (signal time),
        # not the resolution time - the purge compares signal clocks.
        sig.append(float(candles_5m[i].get("time", i)))
    Xa, ya = np.array(X, float), np.array(y, float)
    return (Xa, ya, np.array(sig, float)) if return_sig else (Xa, ya)
