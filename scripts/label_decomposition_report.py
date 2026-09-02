"""Resolution/direction decomposition of every feature's label AUC (read-only).

WHY THIS EXISTS (2026-09-01, the-method recurrence #10, the BARRIER-GEOMETRY
RULE). A feature scored against the triple-barrier label mixes two channels:

  RESOLUTION - did the path touch tb_pt/tb_sl at all (vs tb_time)?
  DIRECTION  - given that it resolved, tb_pt (profit) or tb_sl (stop)?

Volatility loads the first channel and the first channel carries no edge
(a wider path resolves the barrier either way). A raw-label AUC alone is
therefore NOT a finding: a "magnitude lead" measured 2026-09-01 was a
barrier-geometry tautology once split. This instrument makes the split the
default reading, on the SAME rows, for EVERY stored feature, with a
day-block bootstrap CI (calendar days are the effective-n proxy: rows inside
a day share the path and are not independent evidence).

Three AUCs per feature (rank AUC, ties averaged; features are stored
with-my-trade signed by the corpus - never re-signed here):

  RAW        feature vs label                  (all tb_* rows)
  RESOLUTION feature vs barrier in {tb_pt,tb_sl} against tb_time  (all rows)
  DIRECTION  feature vs tb_pt against tb_sl    (RESOLVED rows only)

Flags: DIRECTIONAL (DIRECTION CI excludes 0.5), RESOLUTION-ONLY (DIRECTION
CI includes 0.5 while the RESOLUTION *or* the RAW CI excludes it - the
resolution channel is the loud one in this corpus and a flag column that
reads its loaders as NULL is backwards for a barrier-geometry instrument),
NULL (neither), UNDEFINED (degenerate, or fewer than MIN_CI_DAYS blocks
backing the intervals). Every row also carries `flag_stable`: the same
bootstrap draws split in half must produce the same flag twice, so a flag
that is one realization's noise is marked (`*` in the printed table).

READ THE CHANCE BASELINE OFF THE CORPUS, NOT OFF 5%. At 64 features a
NOMINAL 95% CI would exclude 0.5 ~3.2 times per channel by chance, but a
percentile day-block bootstrap over a few dozen blocks is anti-conservative
and the realized rate is HIGHER. `--null-calibration N` measures it on THIS
corpus (N random features against the real targets and the real day blocks)
and prints the realized rate; the printed nominal number is labelled as
nominal and is not the multiple-comparison baseline.

CORPUS: the PRODUCTION view, loaded by calling
scripts/champion_skill_report._load_live() unchanged (HistoryStore.
load_training_data with config ml.era_exclusion / ml.epoch / sample_weights,
then the feature-contract keep mask). That loader discards each row's
barrier, so the two functions that see it (ml.history._apply_era_exclusion
and the contract's check_matrix) are wrapped for the duration of ONE call to
capture row metadata; alignment is then asserted exactly (signal times must
match element-wise) or the report refuses to run.

SAFE / measurement-plane: reads only, writes nothing, alters no order.

    python scripts/label_decomposition_report.py [--json] [--top N]
    python scripts/label_decomposition_report.py --extra-csv f.csv \
        --key-cols asset,signal_ts        # score external (tape) features
    python scripts/label_decomposition_report.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TB_BARRIERS = ("tb_pt", "tb_sl", "tb_time")
RESOLVED_BARRIERS = ("tb_pt", "tb_sl")
DEFAULT_REPS = 400
DEFAULT_SEED = 20260901
DAY_S = 86400.0
FLAG_RES_ONLY = "RESOLUTION-ONLY"
FLAG_DIR = "DIRECTIONAL"
FLAG_NULL = "NULL"
FLAG_UNDEF = "UNDEFINED"
# self-test negative arm: per-CI false-exclusion rate at nominal 95% should
# sit near 0.05; above this the CI is anti-conservative (or the scramble
# never happened - the "negative arm always passes" defect class)
NEG_ARM_MAX_FALSE_RATE = 0.15
# A percentile day-block bootstrap needs blocks. Below this many DISTINCT
# DAYS every draw repeats the same handful of blocks, the interval collapses
# (at 1 day it has zero width and flags pure noise DIRECTIONAL), so the flag
# is refused as UNDEFINED rather than manufactured. A measurement standard,
# not a tunable: do not lower it to make a thin slice "read real".
MIN_CI_DAYS = 5


# ---------------------------------------------------------------------------
# rank AUC under integer row weights (bootstrap multiplicities)
# ---------------------------------------------------------------------------
def tie_groups(x: np.ndarray) -> tuple[np.ndarray, int]:
    """Dense ascending tie-group id per row of a FINITE vector. Group g
    holds every row whose value is the g-th smallest distinct value, so
    'strictly smaller' == 'lower group' and 'tied' == 'same group'."""
    uniq, inv = np.unique(np.asarray(x, float), return_inverse=True)
    return inv.reshape(-1), int(uniq.size)


def weighted_auc(gid: np.ndarray, ngroups: int, pos: np.ndarray,
                 w: np.ndarray) -> float | None:
    """P(x_pos > x_neg) + 0.5 P(tie) with each row counted `w` times.

    A day-block bootstrap draw is a multiset of rows; the multiplicity
    vector IS that multiset, so this equals the plain AUC of the explicitly
    resampled index array (tests/test_label_decomposition_report.py pins the
    equivalence). O(n) per draw via bincount over tie groups. None when
    either class has zero weight (undefined, never 0.5)."""
    pos = np.asarray(pos, bool)
    w = np.asarray(w, float)
    wp = w * pos
    wn = w * (~pos)
    w1 = float(wp.sum())
    w0 = float(wn.sum())
    if w1 <= 0.0 or w0 <= 0.0:
        return None
    p1 = np.bincount(gid, weights=wp, minlength=ngroups)
    n0 = np.bincount(gid, weights=wn, minlength=ngroups)
    below = np.cumsum(n0) - n0
    return float((p1 * (below + 0.5 * n0)).sum() / (w1 * w0))


def plain_auc(x: np.ndarray, pos: np.ndarray) -> float | None:
    """Unweighted rank AUC (the point estimate); NaN feature rows excluded."""
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    if not ok.any():
        return None
    gid, ng = tie_groups(x[ok])
    return weighted_auc(gid, ng, np.asarray(pos, bool)[ok], np.ones(int(ok.sum())))


def percentile_ci(boots: np.ndarray, alpha: float = 0.05) -> tuple[float, float] | None:
    """Index-based percentile interval of a bootstrap array: sort once, read
    the alpha/2 and 1-alpha/2 quantiles (linear interpolation between order
    statistics). No distributional assumption. None when empty."""
    b = np.asarray([v for v in boots if v is not None], float)
    b = b[np.isfinite(b)]
    if b.size == 0:
        return None
    s = np.sort(b)
    lo, hi = np.quantile(s, [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(lo), float(hi)


def ci_excludes_half(ci: tuple[float, float] | None) -> bool | None:
    if ci is None:
        return None
    lo, hi = ci
    return bool(lo > 0.5 or hi < 0.5)


def classify(raw_ci, dir_ci, res_ci=None, ndays: int | None = None) -> str:
    """The flag rule (docstring). A CI that merely TOUCHES 0.5 includes it.

    RESOLUTION-ONLY fires on the RESOLUTION CI as well as the RAW one: a
    feature can load the resolution channel hard while its raw AUC sits on
    0.5 (the two targets differ), and reading such a feature as NULL is
    backwards for an instrument whose whole purpose is to name resolution
    loaders. `res_ci=None` keeps the old raw-only rule for callers that do
    not have it.

    `ndays` (when given) is the block count backing the intervals: under
    MIN_CI_DAYS the flag is UNDEFINED, because a percentile bootstrap over
    that few blocks manufactures exclusions (see MIN_CI_DAYS)."""
    r = ci_excludes_half(raw_ci)
    d = ci_excludes_half(dir_ci)
    if r is None or d is None:
        return FLAG_UNDEF
    if ndays is not None and ndays < MIN_CI_DAYS:
        return FLAG_UNDEF
    if d:
        return FLAG_DIR
    if r or ci_excludes_half(res_ci):
        return FLAG_RES_ONLY
    return FLAG_NULL


# ---------------------------------------------------------------------------
# day-block bootstrap draws
# ---------------------------------------------------------------------------
def day_index(sig: np.ndarray) -> tuple[np.ndarray, int]:
    """Per-row calendar-day id (UTC, floor(signal_ts/86400)), densified ONCE.
    Rows are never split by day again after this; every draw is a vector of
    day multiplicities looked up through this index."""
    days = np.floor(np.asarray(sig, float) / DAY_S).astype(np.int64)
    uniq, inv = np.unique(days, return_inverse=True)
    return inv.reshape(-1), int(uniq.size)


def draw_day_weights(row_day: np.ndarray, ndays: int, reps: int,
                     seed: int) -> np.ndarray:
    """(reps, n_rows) integer multiplicities: each rep draws `ndays` DAYS with
    replacement and every row inherits its day's count. Shared across all
    features/channels of a run so their intervals are paired."""
    rng = np.random.default_rng(seed)
    out = np.empty((reps, row_day.size), dtype=np.int64)
    for r in range(reps):
        draws = rng.integers(0, ndays, size=ndays)
        counts = np.bincount(draws, minlength=ndays)
        out[r] = counts[row_day]
    return out


# ---------------------------------------------------------------------------
# the decomposition
# ---------------------------------------------------------------------------
def channel_targets(barrier: np.ndarray, y: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """(row mask, positive mask) per channel over the tb_* rows. DIRECTION is
    restricted to RESOLVED rows - scoring it on all rows re-mixes the
    resolution channel back in, which is the exact confound this exists to
    remove."""
    b = np.asarray(barrier).astype(str)
    tb = np.isin(b, TB_BARRIERS)
    resolved = np.isin(b, RESOLVED_BARRIERS)
    return {
        "raw": (tb, np.asarray(y, float) > 0.5),
        "resolution": (tb, resolved),
        "direction": (tb & resolved, b == "tb_pt"),
    }


def decompose(features: dict[str, np.ndarray], y: np.ndarray, barrier: np.ndarray,
              sig: np.ndarray, reps: int = DEFAULT_REPS,
              seed: int = DEFAULT_SEED) -> list[dict[str, Any]]:
    """One row per feature: the three AUCs, their day-block CIs, n,
    n_resolved, distinct days, flag. Sorted by |DIRECTION-0.5| descending
    (undefined last). Pure: no I/O."""
    y = np.asarray(y, float).reshape(-1)
    n = y.size
    targets = channel_targets(barrier, y)
    row_day, ndays = day_index(sig)
    W = draw_day_weights(row_day, ndays, reps, seed)
    rows: list[dict[str, Any]] = []
    for name, x in features.items():
        x = np.asarray(x, float).reshape(-1)
        if x.size != n:
            raise ValueError(f"feature {name!r} has {x.size} rows, corpus has {n}")
        finite = np.isfinite(x)
        rec: dict[str, Any] = {"feature": name}
        if finite.any():
            gid_f, ng = tie_groups(x[finite])
        else:
            gid_f, ng = np.zeros(0, np.int64), 0
        halves: dict[str, tuple[Any, Any]] = {}
        for ch, (mask, pos) in targets.items():
            m = mask & finite
            sub = m[finite]                       # rows of this channel within the finite set
            gid = gid_f[sub]
            p = pos[m]
            idx = np.flatnonzero(m)
            point = weighted_auc(gid, ng, p, np.ones(idx.size)) if idx.size else None
            boots = [weighted_auc(gid, ng, p, W[r, idx]) for r in range(reps)] if idx.size else []
            barr = np.asarray([b if b is not None else np.nan for b in boots], float)
            ci = percentile_ci(barr)
            # SAME draws, split in two: a flag only one half reproduces is a
            # bootstrap REALIZATION, not a result (costs nothing extra).
            cut = barr.size // 2
            halves[ch] = (percentile_ci(barr[:cut]), percentile_ci(barr[cut:]))
            rec[f"{ch}_auc"] = None if point is None else round(point, 4)
            rec[f"{ch}_ci"] = None if ci is None else [round(ci[0], 4), round(ci[1], 4)]
            rec[f"{ch}_n"] = int(idx.size)
            rec[f"{ch}_pos"] = int(p.sum())
            rec[f"{ch}_days"] = int(np.unique(row_day[idx]).size)
            rec[f"{ch}_boot_valid"] = int(sum(1 for b in boots if b is not None))
        rec["n"] = rec["raw_n"]
        rec["n_resolved"] = rec["direction_n"]
        rec["days"] = rec["raw_days"]
        rec["days_resolved"] = rec["direction_days"]
        rec["resolution_ci_excludes_half"] = ci_excludes_half(rec["resolution_ci"])
        backing = [d for d in (rec["raw_days"], rec["direction_days"]) if d > 0]
        rec["ci_blocks"] = int(min(backing)) if backing else 0
        rec["few_blocks"] = bool(rec["ci_blocks"] < MIN_CI_DAYS)
        rec["flag"] = classify(rec["raw_ci"], rec["direction_ci"],
                               rec["resolution_ci"], rec["ci_blocks"])
        fa = classify(halves["raw"][0], halves["direction"][0],
                      halves["resolution"][0], rec["ci_blocks"])
        fb = classify(halves["raw"][1], halves["direction"][1],
                      halves["resolution"][1], rec["ci_blocks"])
        rec["flag_halves"] = [fa, fb]
        rec["flag_stable"] = bool(fa == fb == rec["flag"])
        rows.append(rec)
    rows.sort(key=lambda r: (r["direction_auc"] is None,
                             -abs(r["direction_auc"] - 0.5)
                             if r["direction_auc"] is not None else 0.0))
    return rows


def null_calibration(y: np.ndarray, barrier: np.ndarray, sig: np.ndarray,
                     n_features: int, reps: int = DEFAULT_REPS,
                     seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """REALIZED false-exclusion rate of these CIs ON THIS CORPUS.

    `n_features` i.i.d. N(0,1) features - independent of everything by
    construction - are scored through the SAME `decompose` against the REAL
    targets, the REAL rows and the REAL day blocks, so the only thing being
    measured is how often the interval excludes 0.5 when nothing is there.
    The self-test's negative arm measures this on the SYNTHETIC corpus (30
    uniform days, no within-day clustering); that rate does NOT transfer -
    quote this one for any multiple-comparison argument about the real
    report, and quote the nominal 5% for neither."""
    rng = np.random.default_rng(seed + 1)
    feats = {f"null{i:03d}": rng.normal(size=int(np.asarray(y).size))
             for i in range(int(n_features))}
    rows = decompose(feats, y, barrier, sig, reps=reps, seed=seed)
    out: dict[str, Any] = {"n_features": int(n_features), "reps": reps, "seed": seed,
                           "basis": "N(0,1) features vs the real targets/rows/day blocks"}
    for ch in ("raw", "resolution", "direction"):
        ex = [ci_excludes_half(r[f"{ch}_ci"]) for r in rows]
        checked = [e for e in ex if e is not None]
        out[ch] = {"checked": len(checked), "excluding_half": int(sum(checked)),
                   "rate": round(sum(checked) / len(checked), 4) if checked else None}
    out["flag_counts"] = {f: sum(1 for r in rows if r["flag"] == f)
                          for f in (FLAG_DIR, FLAG_RES_ONLY, FLAG_NULL, FLAG_UNDEF)}
    out["unstable_flags"] = int(sum(1 for r in rows if not r["flag_stable"]))
    return out


DEFAULT_POWER_GRID = (0.02, 0.05, 0.10, 0.20, 0.40)
POWER_TARGET = 0.80


def power_calibration(y: np.ndarray, barrier: np.ndarray, sig: np.ndarray,
                      grid=DEFAULT_POWER_GRID, per_size: int = 20,
                      reps: int = DEFAULT_REPS,
                      seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """REALIZED DETECTION RATE of these CIs ON THIS CORPUS - the mirror of
    null_calibration, and the half this instrument was missing.

    null_calibration asks "how often do I flag something when nothing is
    there" (the false-POSITIVE rate). This asks the question that decides
    whether a null MEANS anything: "if a real directional effect of size d
    WERE there, how often would I catch it?" Without it, DIRECTIONAL 6 of 84
    against a chance expectation of 10.5 is compatible both with "no feature
    carries direction" and with "this corpus cannot see direction at all",
    and those are different findings. Harvey & Liu (J. Finance 2020) measure
    that second world at a Type II error of 86.9% even when the true
    performers earn ~10.66%/yr alpha, which is why the mirror is not
    optional.

    Method, deliberately identical to null_calibration except for the plant:
    `per_size` features per grid point are built as
    `N(0,1) + d * (+1 on tb_pt, -1 on tb_sl, 0 on tb_time)` - a pure
    DIRECTION channel of known size d - and scored through the SAME
    `decompose` against the REAL targets, the REAL rows and the REAL day
    blocks. `detection_rate` is the share flagged DIRECTIONAL. `mde` is the
    smallest grid size whose detection rate reaches POWER_TARGET; it is None
    when the grid never reaches it, and None means the corpus cannot resolve
    ANY effect on this grid - report that as the finding, never as a null.

    Effect size d is in units of the feature's own SD (the noise is N(0,1)),
    so d=0.10 is "a feature whose mean shifts a tenth of a standard deviation
    between winners and losers".
    """
    y = np.asarray(y, float).reshape(-1)
    barrier = np.asarray(barrier, dtype=object).reshape(-1)
    n = y.size
    resolved = np.isin(barrier, RESOLVED_BARRIERS)
    up = (barrier == RESOLVED_BARRIERS[0])   # tb_pt = the profit barrier
    lift = np.where(resolved, np.where(up, 1.0, -1.0), 0.0)
    rng = np.random.default_rng(seed + 2)
    out: dict[str, Any] = {
        "per_size": int(per_size), "reps": reps, "seed": seed,
        "power_target": POWER_TARGET,
        "basis": "planted DIRECTION effect vs the real targets/rows/day blocks",
        "n_resolved": int(resolved.sum()), "grid": []}
    for d in grid:
        feats = {f"eff{d:g}_{i:03d}": rng.normal(size=n) + float(d) * lift
                 for i in range(int(per_size))}
        rows = decompose(feats, y, barrier, sig, reps=reps, seed=seed)
        hit = sum(1 for r in rows if r["flag"] == FLAG_DIR)
        # a DIRECTIONAL flag pointing the WRONG way is not a detection
        right = sum(1 for r in rows if r["flag"] == FLAG_DIR
                    and r["direction_auc"] is not None
                    and r["direction_auc"] > 0.5)
        out["grid"].append({
            "effect_sd": float(d), "features": len(rows),
            "flagged_directional": int(hit),
            "detected_with_correct_sign": int(right),
            "detection_rate": round(right / len(rows), 4) if rows else None})
    reached = [g for g in out["grid"]
               if g["detection_rate"] is not None
               and g["detection_rate"] >= POWER_TARGET]
    out["mde"] = reached[0]["effect_sd"] if reached else None
    out["note"] = ("mde = smallest planted effect (in feature SDs) detected "
                   "at >= %.0f%% with the correct sign. None means the grid "
                   "never reached it: the corpus cannot resolve any effect "
                   "on this grid, which is a statement about the TEST, not "
                   "about the market." % (100 * POWER_TARGET))
    return out


# ---------------------------------------------------------------------------
# production corpus (the champion_skill_report loader, metadata captured)
# ---------------------------------------------------------------------------
def load_production_corpus() -> dict[str, Any]:
    """Calls scripts.champion_skill_report._load_live() VERBATIM and captures
    the per-row (asset, ts, source, barrier) metadata that
    HistoryStore.load_training_data builds and then discards.

    Capture points, both restored in `finally`:
      ml.history._apply_era_exclusion - the loader's LAST row filter (era
        exclusion, config ml.era_exclusion); its return carries the
        surviving pre-sort lists, from which load_training_data derives the
        signal-sorted arrays it returns.
      the feature contract's check_matrix - _load_live's keep mask.
    Alignment is then asserted: captured sig, sorted with the loader's own
    mergesort argsort and masked by keep, must equal the returned sig
    element-wise. Requires the repo root as CWD (config.json is read
    relatively by the loader); main() chdirs, importers must."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import ml.history as hist_mod
    from ml.contracts import get_contract
    from scripts.champion_skill_report import _load_live

    cap: dict[str, Any] = {}
    orig_apply = hist_mod._apply_era_exclusion
    contract = get_contract()
    orig_check = contract.check_matrix

    def spy_apply(*a, **k):
        out = orig_apply(*a, **k)
        cap["sig"] = np.asarray(out[3], float)
        cap["meta"] = list(out[4])
        cap["era_stats"] = dict(out[5])
        cap["current_era"] = k.get("current_era")
        return out

    def spy_check(X):
        res = orig_check(X)
        cap["keep"] = np.asarray(res["keep"], bool)
        return res

    hist_mod._apply_era_exclusion = spy_apply
    contract.check_matrix = spy_check          # type: ignore[method-assign]
    try:
        live = _load_live()
    finally:
        hist_mod._apply_era_exclusion = orig_apply
        contract.check_matrix = orig_check     # type: ignore[method-assign]
    if "meta" not in cap or "keep" not in cap:
        raise RuntimeError("loader capture failed: the champion_skill_report "
                           "loader no longer routes through the wrapped seams")
    order = np.argsort(cap["sig"], kind="mergesort")
    meta_sorted = [cap["meta"][i] for i in order]
    keep = cap["keep"]
    meta_kept = [m for m, k in zip(meta_sorted, keep, strict=True) if k]
    sig_chk = cap["sig"][order][keep]
    if sig_chk.size != live["sig"].size or not np.array_equal(sig_chk, live["sig"]):
        raise RuntimeError("row alignment check FAILED: captured metadata does "
                           "not line up with the loader's returned rows - refusing "
                           "to score misaligned barriers")
    from ml.features import FEATURE_NAMES
    X = np.asarray(live["X"], float)
    if X.shape[1] != len(FEATURE_NAMES):
        raise RuntimeError(f"X has {X.shape[1]} columns, FEATURE_NAMES has "
                           f"{len(FEATURE_NAMES)}")
    return {
        "X": X, "y": np.asarray(live["y"], float), "sig": np.asarray(live["sig"], float),
        "asset": np.asarray([m[0] for m in meta_kept], dtype=object),
        "resolve_ts": np.asarray([m[1] for m in meta_kept], float),
        "source": np.asarray([m[2] for m in meta_kept], dtype=object),
        "barrier": np.asarray([m[3] for m in meta_kept], dtype=object),
        "feature_names": list(FEATURE_NAMES),
        "era_stats": cap.get("era_stats"),
        "current_era": cap.get("current_era"),
        "contract_dropped": int((~keep).sum()),
    }


def join_extra_csv(path: Path, key_cols: list[str], asset: np.ndarray,
                   sig: np.ndarray) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Numeric non-key columns of `path`, aligned to the corpus rows by an
    exact match on ALL key columns (asset as string, signal_ts as float
    rounded to 3 dp). Unmatched corpus rows get NaN (they drop out of that
    feature's AUCs and its n reports it). Duplicate keys in the CSV keep the
    first occurrence and are counted."""
    import pandas as pd
    df = pd.read_csv(path)
    missing = [c for c in key_cols if c not in df.columns]
    if missing:
        raise ValueError(f"--extra-csv lacks key column(s) {missing}")

    def _key_from(cols: list[Any]) -> tuple:
        out = []
        for c, v in zip(key_cols, cols, strict=True):
            out.append(round(float(v), 3) if c == "signal_ts" else str(v))
        return tuple(out)

    n = len(df)
    df = df.drop_duplicates(subset=key_cols, keep="first")
    dups = n - len(df)
    lookup: dict[tuple, int] = {}
    for i, row in enumerate(df[key_cols].itertuples(index=False, name=None)):
        lookup[_key_from(list(row))] = i
    corpus_keys = []
    for a, t in zip(asset, sig, strict=True):
        vals = {"asset": a, "signal_ts": t}
        corpus_keys.append(_key_from([vals[c] if c in vals else np.nan for c in key_cols]))
    pos = np.array([lookup.get(k, -1) for k in corpus_keys], dtype=np.int64)
    matched = pos >= 0
    feats: dict[str, np.ndarray] = {}
    for col in df.columns:
        if col in key_cols:
            continue
        vals = pd.to_numeric(df[col], errors="coerce").to_numpy(float)
        if not np.isfinite(vals).any():
            continue
        out = np.full(len(pos), np.nan)
        out[matched] = vals[pos[matched]]
        feats[col] = out
    corpus_dups = len(corpus_keys) - len(set(corpus_keys))
    return feats, {"extra_csv": str(path), "key_cols": key_cols, "csv_rows": int(n),
                   "csv_duplicate_keys": int(dups), "corpus_rows_matched": int(matched.sum()),
                   "corpus_rows_unmatched": int((~matched).sum()),
                   # READ THIS: the key is NOT unique in the production corpus
                   # (same asset, same signal_ts, both sides / repeated cycle),
                   # so one CSV row can legitimately match several corpus rows
                   # and the rate can exceed csv_rows/corpus_rows.
                   "corpus_duplicate_keys": int(corpus_dups),
                   "corpus_join_rate": round(float(matched.mean()), 4) if len(pos) else None,
                   "extra_features": sorted(feats)}


# ---------------------------------------------------------------------------
# self-test: planted channels
# ---------------------------------------------------------------------------
def synth_corpus(seed: int, days: int = 30, per_day: int = 40,
                 effect: float = 1.0) -> dict[str, Any]:
    """A: PURE RESOLUTION (shifted by resolution, symmetric on direction).
    B: PURE DIRECTION (shifted by tb_pt-vs-tb_sl on resolved rows only,
    noise on tb_time rows). C: null. Label = tb_pt."""
    rng = np.random.default_rng(seed)
    n = days * per_day
    sig = np.repeat(np.arange(days), per_day) * DAY_S + rng.uniform(0, DAY_S, n)
    resolved = rng.random(n) < 0.6
    up = rng.random(n) < 0.5
    barrier = np.where(~resolved, "tb_time", np.where(up, "tb_pt", "tb_sl")).astype(object)
    y = (barrier == "tb_pt").astype(float)
    a = rng.normal(size=n) + effect * np.where(resolved, 1.0, -1.0)
    b = rng.normal(size=n) + effect * np.where(resolved, np.where(up, 1.0, -1.0), 0.0)
    c = rng.normal(size=n)
    return {"features": {"A": a, "B": b, "C": c}, "y": y, "barrier": barrier,
            "sig": sig}


# The exact triple (A RESOLUTION-ONLY, B DIRECTIONAL, C NULL) needs ~4 null
# CIs to include 0.5 at once, so it holds at ~0.95**4 = 0.81 of seeds by
# construction of a 95% interval; 13/20 is the 2% binomial tail below that.
# The planted effects themselves (orientation AND exclusion) are HARD 20/20.
POS_ARM_MIN_EXACT = 13


def positive_arm(seeds, reps: int = DEFAULT_REPS) -> dict[str, Any]:
    """A must load RESOLUTION with the planted sign (AUC>0.5, CI lo>0.5),
    B must load DIRECTION with the planted sign (AUC>0.5, CI lo>0.5) and be
    flagged DIRECTIONAL - every seed. The exact triple flag is a rate."""
    want = {"A": FLAG_RES_ONLY, "B": FLAG_DIR, "C": FLAG_NULL}
    seeds = list(seeds)
    exact = 0
    hard = 0
    fails = []
    for s in seeds:
        c = synth_corpus(s)
        rows = {r["feature"]: r for r in
                decompose(c["features"], c["y"], c["barrier"], c["sig"], reps=reps, seed=s)}
        got = {k: r["flag"] for k, r in rows.items()}
        a, b = rows["A"], rows["B"]
        hard_ok = (a["resolution_ci"] is not None and a["resolution_ci"][0] > 0.5
                   and a["raw_ci"] is not None and a["raw_ci"][0] > 0.5
                   and b["direction_ci"] is not None and b["direction_ci"][0] > 0.5
                   and b["flag"] == FLAG_DIR)
        hard += int(hard_ok)
        if got == want:
            exact += 1
        if not hard_ok or got != want:
            fails.append({"seed": int(s), "got": got, "hard_ok": hard_ok})
    return {"seeds": len(seeds), "hard_correct": hard, "exact_correct": exact,
            "min_exact": POS_ARM_MIN_EXACT, "fails": fails,
            "ok": hard == len(seeds) and exact >= POS_ARM_MIN_EXACT}


def negative_arm(seeds, reps: int = DEFAULT_REPS, scramble: bool = True) -> dict[str, Any]:
    """CONTROL: the barrier/label are PERMUTED across rows (scramble=True),
    severing every feature from every channel; all three must read NULL and
    the per-CI false-exclusion rate must sit near the nominal 5%.
    `scramble=False` is the test hook that PROVES this arm can fail: with
    the planted effects intact the arm must report NOT ok.

    READ THE PRINTED RATE. A percentile bootstrap over a few dozen day
    blocks is somewhat anti-conservative (its realized null exclusion rate
    sits above the nominal 5%; measured on this synthetic across 30-200
    days when the instrument shipped - re-derive with --self-test, do not
    quote). The multiple-comparison expectation on the real report should
    use the realized rate, not the nominal one."""
    n_ci = 0
    n_false = 0
    null_all = 0
    seeds = list(seeds)
    for s in seeds:
        c = synth_corpus(s)
        barrier, y = c["barrier"], c["y"]
        if scramble:
            perm = np.random.default_rng(10_000 + s).permutation(y.size)
            barrier, y = barrier[perm], y[perm]
        rows = decompose(c["features"], y, barrier, c["sig"], reps=reps, seed=s)
        if all(r["flag"] == FLAG_NULL for r in rows):
            null_all += 1
        for r in rows:
            for ch in ("raw", "resolution", "direction"):
                ex = ci_excludes_half(r[f"{ch}_ci"])
                if ex is None:
                    continue
                n_ci += 1
                n_false += int(ex)
    rate = (n_false / n_ci) if n_ci else 1.0
    return {"seeds": len(seeds), "all_null_seeds": null_all, "ci_checked": n_ci,
            "ci_falsely_excluding_half": n_false, "false_rate": round(rate, 4),
            "max_false_rate": NEG_ARM_MAX_FALSE_RATE, "scrambled": scramble,
            "ok": rate <= NEG_ARM_MAX_FALSE_RATE}


def run_self_test(n_seeds: int = 20, reps: int = DEFAULT_REPS) -> tuple[int, list[str]]:
    seeds = range(n_seeds)
    pos = positive_arm(seeds, reps=reps)
    neg = negative_arm(seeds, reps=reps, scramble=True)
    lines = ["== LABEL-DECOMPOSITION SELF-TEST ==",
             f"  positive arm: planted channels found with the planted sign on "
             f"{pos['hard_correct']}/{pos['seeds']} seeds (must be all); exact triple "
             f"A=RESOLUTION-ONLY, B=DIRECTIONAL, C=NULL on {pos['exact_correct']}/"
             f"{pos['seeds']} seeds (need >= {pos['min_exact']}; ~0.95^4 of seeds "
             f"by construction of a 95% CI) ({reps} reps each)"]
    for f in pos["fails"]:
        lines.append(f"   - seed {f['seed']}: {f['got']} hard_ok={f['hard_ok']}")
    lines.append(f"  negative arm (control, scrambled barrier): "
                 f"{neg['all_null_seeds']}/{neg['seeds']} seeds NULL on all three; "
                 f"per-CI false-exclusion rate {neg['ci_falsely_excluding_half']}/"
                 f"{neg['ci_checked']} = {neg['false_rate'] * 100:.1f}% "
                 f"(nominal 5%, must not fire above {NEG_ARM_MAX_FALSE_RATE * 100:.0f}%)")
    ok = pos["ok"] and neg["ok"]
    lines.append("  PASS" if ok else "  FAIL")
    return (0 if ok else 1), lines


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def _fmt_ci(ci) -> str:
    return "     n/a     " if ci is None else f"[{ci[0]:.3f},{ci[1]:.3f}]"


def _fmt_row(r: dict[str, Any]) -> str:
    def a(v):
        return "  n/a " if v is None else f"{v:.3f} "
    return (f"  {r['feature']:<22} {r['n']:>6} {r['n_resolved']:>6} {r['days']:>4}  "
            f"{a(r['raw_auc'])}{_fmt_ci(r['raw_ci'])}  "
            f"{a(r['resolution_auc'])}{_fmt_ci(r['resolution_ci'])}  "
            f"{a(r['direction_auc'])}{_fmt_ci(r['direction_ci'])}  {r['flag']}"
            f"{'' if r.get('flag_stable', True) else '*'}")


def build_report(corpus: dict[str, Any], reps: int, seed: int,
                 extra: tuple[dict[str, np.ndarray], dict[str, Any]] | None = None,
                 null_features: int = 0,
                 power_per_size: int = 0) -> dict[str, Any]:
    b = corpus["barrier"].astype(str)
    tb = np.isin(b, TB_BARRIERS)
    feats = {nm: corpus["X"][:, i] for i, nm in enumerate(corpus["feature_names"])}
    extra_meta = None
    if extra is not None:
        ef, extra_meta = extra
        for k, v in ef.items():
            feats[f"extra:{k}" if k in feats else k] = v
    feats_tb = {k: v[tb] for k, v in feats.items()}
    rows = decompose(feats_tb, corpus["y"][tb], b[tb], corpus["sig"][tb], reps=reps, seed=seed)
    counts = {k: int((b == k).sum()) for k in np.unique(b)}
    ytb = corpus["y"][tb]
    xtab = {k: {"n": int((b[tb] == k).sum()), "label_rate": round(float(ytb[b[tb] == k].mean()), 4)}
            for k in TB_BARRIERS if (b[tb] == k).any()}
    n_flag = {f: sum(1 for r in rows if r["flag"] == f)
              for f in (FLAG_DIR, FLAG_RES_ONLY, FLAG_NULL, FLAG_UNDEF)}
    days_all = day_index(corpus["sig"][tb])[1] if tb.any() else 0
    s = corpus["sig"][tb]
    return {
        "read_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "loader": "scripts.champion_skill_report._load_live -> "
                  "ml.history.HistoryStore.load_training_data(era_cfg=config ml.era_exclusion, "
                  "epoch_cfg=config ml.epoch, weights_cfg=config ml.sample_weights) "
                  "+ ml.contracts.get_contract().check_matrix keep mask",
        "era_exclusion": corpus.get("era_stats"),
        "kept_label_era": corpus.get("current_era"),
        "contract_dropped_rows": corpus.get("contract_dropped"),
        "corpus_rows_loaded": int(b.size),
        "barrier_counts_loaded": counts,
        "tb_rows": int(tb.sum()),
        "tb_rows_dropped_other_barrier": int((~tb).sum()),
        "tb_first_ts": None if not tb.any() else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(s.min()))),
        "tb_last_ts": None if not tb.any() else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(s.max()))),
        "tb_distinct_days": int(days_all),
        "label_by_barrier": xtab,
        "reps": reps, "seed": seed, "ci": "day-block bootstrap percentile 95%",
        "min_ci_days": MIN_CI_DAYS,
        "features_scanned": len(rows),
        # NOMINAL, and the realized rate at this block count is higher: read
        # null_calibration (--null-calibration N), never this, as the
        # multiple-comparison baseline.
        "expected_false_exclusions_at_95_NOMINAL": round(0.05 * len(rows), 1),
        "null_calibration": (null_calibration(corpus["y"][tb], b[tb], corpus["sig"][tb],
                                              null_features, reps=reps, seed=seed)
                             if null_features > 0 else None),
        "power_calibration": (power_calibration(corpus["y"][tb], b[tb],
                                                corpus["sig"][tb],
                                                per_size=power_per_size,
                                                reps=reps, seed=seed)
                              if power_per_size > 0 else None),
        "flag_counts": n_flag,
        "unstable_flags": [r["feature"] for r in rows if not r["flag_stable"]],
        "extra": extra_meta,
        "rows": rows,
    }


def print_report(rep: dict[str, Any], top: int | None) -> None:
    print(f"== LABEL DECOMPOSITION (read {rep['read_time_utc']}) ==")
    print(f"  loader: {rep['loader']}")
    print(f"  era_exclusion: {rep['era_exclusion']}  kept era: {rep['kept_label_era']}  "
          f"contract-dropped: {rep['contract_dropped_rows']}")
    print(f"  rows loaded {rep['corpus_rows_loaded']}  barriers {rep['barrier_counts_loaded']}")
    print(f"  tb rows {rep['tb_rows']} ({rep['tb_rows_dropped_other_barrier']} non-tb dropped)  "
          f"{rep['tb_first_ts']} -> {rep['tb_last_ts']}  distinct days {rep['tb_distinct_days']}")
    print(f"  label rate by barrier: {rep['label_by_barrier']}")
    print(f"  {rep['ci']}, {rep['reps']} reps, seed {rep['seed']}; features scanned "
          f"{rep['features_scanned']} -> NOMINAL "
          f"~{rep['expected_false_exclusions_at_95_NOMINAL']} CIs exclude 0.5 per channel "
          f"by chance. NOMINAL IS NOT THE BASELINE: the realized rate at this block "
          f"count is higher - measure it with --null-calibration N")
    pc = rep.get("power_calibration")
    if pc:
        _cells = "  ".join(f"{g['effect_sd']:g}sd:{g['detection_rate']:.0%}"
                           for g in pc["grid"])
        print(f"  POWER on THIS corpus ({pc['per_size']} planted-direction "
              f"features per grid point, {pc['n_resolved']} resolved rows): "
              f"{_cells}")
        if pc["mde"] is None:
            print("  -> NO grid effect reached "
                  f"{pc['power_target']:.0%} detection: this corpus cannot "
                  "resolve ANY of them. A NULL HERE IS A STATEMENT ABOUT THE "
                  "TEST, NOT THE MARKET.")
        else:
            print(f"  -> minimum detectable effect {pc['mde']:g} SD at "
                  f"{pc['power_target']:.0%}. A null means 'no effect above "
                  f"{pc['mde']:g} SD', never 'no effect'.")
    nc = rep.get("null_calibration")
    if nc:
        rates = {ch: nc[ch]["rate"] for ch in ("raw", "resolution", "direction")}
        print(f"  null calibration on THIS corpus ({nc['n_features']} N(0,1) features, "
              f"{nc['basis']}): realized exclusion rate {rates} -> at "
              f"{rep['features_scanned']} features expect "
              f"{round((rates['direction'] or 0.0) * rep['features_scanned'], 1)} DIRECTION "
              f"exclusions by chance; null-run flags {nc['flag_counts']}")
    if rep.get("extra"):
        print(f"  extra: {rep['extra']}")
    print(f"  flags: {rep['flag_counts']}  (flag UNDEFINED below {rep['min_ci_days']} day "
          f"blocks); * = flag not reproduced by both bootstrap halves: "
          f"{rep['unstable_flags'] or '-'}")
    print(f"  {'feature':<22} {'n':>6} {'n_res':>6} {'days':>4}  "
          f"{'RAW  ':<21}  {'RESOLUTION':<21}  {'DIRECTION':<21}  flag")
    rows = rep["rows"] if top is None else rep["rows"][:top]
    for r in rows:
        print(_fmt_row(r))
    res_only = [r["feature"] for r in rep["rows"] if r["flag"] == FLAG_RES_ONLY]
    print(f"  RESOLUTION-ONLY ({len(res_only)}): {', '.join(res_only) or '-'}")
    dirs = [r["feature"] for r in rep["rows"] if r["flag"] == FLAG_DIR]
    print(f"  DIRECTIONAL ({len(dirs)}): {', '.join(dirs) or '-'}")
    # the flag column alone hides the channel this instrument exists to
    # measure: print the resolution loaders whatever their flag says.
    loaders = sorted((r for r in rep["rows"] if r["resolution_ci_excludes_half"]),
                     key=lambda r: -abs((r["resolution_auc"] or 0.5) - 0.5))
    print(f"  RESOLUTION CI excludes 0.5 ({len(loaders)}): "
          + (", ".join(f"{r['feature']} {r['resolution_auc']:.3f}" for r in loaders[:12])
             or "-") + (" ..." if len(loaders) > 12 else ""))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="machine-readable, all rows")
    ap.add_argument("--top", type=int, default=None, help="print only the top N rows")
    ap.add_argument("--reps", type=int, default=DEFAULT_REPS)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--extra-csv", type=Path, default=None,
                    help="CSV of additional feature columns joined on --key-cols")
    ap.add_argument("--key-cols", default="asset,signal_ts")
    ap.add_argument("--power-calibration", type=int, default=0, metavar="K",
                    help="K planted-effect features per grid point: the "
                         "DETECTION rate (mirror of --null-calibration). "
                         "Without it a null verdict has no resolution.")
    ap.add_argument("--null-calibration", type=int, default=0, metavar="N",
                    help="score N random N(0,1) features against the real targets and "
                         "day blocks to MEASURE this corpus's false-exclusion rate "
                         "(the nominal 5%% is not the baseline at this block count)")
    ap.add_argument("--self-test", action="store_true",
                    help="planted-channel corpus: A RESOLUTION-ONLY, B DIRECTIONAL, "
                         "C NULL on 20 seeds + a scrambled-label negative arm")
    args = ap.parse_args(argv)
    if args.reps < 1:
        ap.error("--reps must be >= 1")
    if args.self_test:
        rc, lines = run_self_test(reps=min(args.reps, DEFAULT_REPS))
        print("\n".join(lines))
        return rc
    os.chdir(ROOT)
    corpus = load_production_corpus()
    extra = None
    if args.extra_csv is not None:
        keys = [k.strip() for k in args.key_cols.split(",") if k.strip()]
        extra = join_extra_csv(args.extra_csv, keys, corpus["asset"], corpus["sig"])
    if args.null_calibration < 0:
        ap.error("--null-calibration must be >= 0")
    if args.power_calibration < 0:
        ap.error("--power-calibration must be >= 0")
    rep = build_report(corpus, args.reps, args.seed, extra,
                       null_features=args.null_calibration,
                       power_per_size=args.power_calibration)
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        print_report(rep, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
