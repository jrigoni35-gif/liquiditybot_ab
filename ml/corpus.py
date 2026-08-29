"""Canonical corpus accessor — the ONE place signal-history semantics live.

R1 of docs/quant/2026-08-28_data_computation_audit.md: 42 files carry a
bespoke CSV reader of outputs/signal_history.csv, each re-implementing type
coercion, era filtering and UNKNOWN handling — and the era-confound defect
class lived in exactly one such bespoke reader. New readers use THIS module;
existing readers converge opportunistically (do not big-bang migrate a
governed instrument without its own review).

The semantics enforced here (each carries a pin in
tests/test_corpus_accessor.py — change behavior only WITH its pin):

- UNKNOWN-as-'': an empty string in a bookkeeping column means "cannot
  know", never zero (the ml/history.py write-path column conventions,
  incl. the availability flags and the control-arm tag). Helpers return
  None, never 0.0, for unrecoverable values.
- Era of a row: the row's OWN persisted `label_era` tag wins; only rows
  written before the tag existed fall back to deriving from `barrier`
  (mirrors ml.history._row_label_era — the derivation without horizon
  knowledge is the documented era-mixing defect, so the persisted tag is
  always preferred).
- Gross return: side-adjusted percent from entry_price/exit_price — the
  route that survives label-time cost bases (validated against
  label_ret_pct on 2,130 dual-route rows, 2026-08-28 replay doc).
- Never pool statistics across disjoint label_era populations. This module
  gives you the filter; using it is the law (CONFOUNDED_BASELINE class).

Reads only — this module never writes the corpus (append stays in
ml.history; rotation stays write-path-only per the 2026-07-11 incident).

STDLIB-ONLY BY LAW: this module lives in engine scope (ml/), so it may not
import analysis tooling (polars/pandas/duckdb) even lazily — the engine-scope
dependency-hygiene gate (tests/test_dependency_hygiene.py) forbids it, and
the repo convention keeps any polars/parquet fast lane in scripts/, never in
an engine-scope module. A caller wanting the 12-36x parquet/polars speed
reads CORPUS_PATH directly from a script; the semantics helpers here are the
authority that fast lane mirrors, not a thing it imports.
"""
from __future__ import annotations

import csv
import math
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from ml.history import label_era_of

# Read-only default location of the live corpus (never written from here).
CORPUS_PATH = Path("outputs") / "signal_history.csv"


def is_unknown(value: object) -> bool:
    """'' and None are UNKNOWN — bookkeeping columns are never zero-filled."""
    return value is None or (isinstance(value, str) and value.strip() == "")


def row_era(row: Mapping[str, Any]) -> str:
    """A row's label era: its persisted tag first, barrier-derived fallback.

    The fallback exists only for rows written before the label_era column
    (2026-08); deriving without horizon knowledge is the documented
    era-mixing defect, so the persisted tag always wins.
    """
    persisted = str(row.get("label_era") or "").strip()
    if persisted:
        return persisted
    return label_era_of(str(row.get("barrier") or "") or None)


def _entry_exit(row: Mapping[str, Any]) -> "tuple[float, float] | None":
    """Parsed (entry, exit) prices, or None when either is unrecoverable.

    A NONPOSITIVE price on EITHER leg is UNKNOWN, never a real fill: a live
    row for a still-open position stores exit_price=0.0, and reading that as
    a -100% return is the exit<=0 hole (measured 2026-08-29, adverse-selection
    audit). Both legs are guarded so no consumer can mint a spurious ±100%.
    """
    e_raw, x_raw = row.get("entry_price"), row.get("exit_price")
    if is_unknown(e_raw) or is_unknown(x_raw):
        return None
    try:
        entry, exit_ = float(e_raw), float(x_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if entry <= 0.0 or exit_ <= 0.0 or not (math.isfinite(entry)
                                            and math.isfinite(exit_)):
        return None
    return entry, exit_


def _is_short(row: Mapping[str, Any]) -> bool:
    """A row's side is short. Case/whitespace-insensitive so 'SHORT'/'Short'
    do not silently read as long and flip the return sign the wrong way
    (adversarial review 2026-08-29). One home for the sign convention, used
    by both return helpers."""
    return str(row.get("side") or "long").strip().lower() == "short"


def gross_ret_pct(row: Mapping[str, Any]) -> "float | None":
    """Side-adjusted gross return in PERCENT (linear scale) from entry/exit.

    None when unrecoverable (missing/blank/nonpositive/non-finite either
    leg) — never 0, never a spurious ±100%.
    """
    ee = _entry_exit(row)
    if ee is None:
        return None
    entry, exit_ = ee
    raw = (exit_ - entry) / entry * 100.0
    return -raw if _is_short(row) else raw


def gross_log_ret(row: Mapping[str, Any]) -> "float | None":
    """Side-adjusted gross return on the LOG scale: ln(exit/entry), decimal
    (a +1% move ≈ +0.00995). Same UNKNOWN guards as gross_ret_pct.

    Log returns are the natural scale for a compounding process: they ADD
    across a sequence (Σ log_ret = the log of the cumulative multiple), so a
    persistent edge shows as a straight positive slope in the cumulative
    series where the linear-percent view curves and hides it. Provided
    alongside the linear helper so profit/edge patterns can be read on both
    scales without a second reader (operator directive 2026-08-29).
    """
    ee = _entry_exit(row)
    if ee is None:
        return None
    entry, exit_ = ee
    ratio = exit_ / entry
    # Both legs pass _entry_exit (positive, finite), but the RATIO can still
    # underflow to 0.0 (tiny exit / huge entry) or overflow to inf — and
    # math.log(0.0) RAISES, breaking the never-throw contract (adversarial
    # review 2026-08-29). A non-positive / non-finite ratio is UNKNOWN.
    if ratio <= 0.0 or not math.isfinite(ratio):
        return None
    lr = math.log(ratio)
    return -lr if _is_short(row) else lr


def net_ret_pct(row: Mapping[str, Any], cost_pct: float) -> "float | None":
    """Gross return minus an explicit round-trip cost. The caller NAMES the
    cost — this module never assumes an era's cost basis (that assumption
    is how labels went stale)."""
    g = gross_ret_pct(row)
    return None if g is None else g - cost_pct


def iter_rows(path: "Path | str" = CORPUS_PATH) -> Iterator[dict[str, str]]:
    """Stream corpus rows as dicts (stdlib route — always available)."""
    with open(path, encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)


def read_rows(path: "Path | str" = CORPUS_PATH,
              era: "str | None" = None) -> list[dict[str, str]]:
    """All rows (optionally one era) as dicts. Era filtering here means the
    caller cannot accidentally pool disjoint label populations."""
    rows = iter_rows(path)
    if era is None:
        return list(rows)
    return [r for r in rows if row_era(r) == era]


# --- CONCURRENCY / EFFECTIVE-N ------------------------------------------
# The ONE home for the corpus's effective-sample-size statistic and the
# Wilson interval evaluated on it. RELOCATED here (2026-08-29) from
# scripts/gate_truth_report.py, VERBATIM: the algorithm is unchanged, it
# simply now lives in the stdlib-legal canonical accessor so every route
# (gate_truth_report, gate_efficacy_report, and any new reader) computes
# it in ONE place instead of keeping a private copy that can silently
# disagree — the exact anti-pattern gate_efficacy_report's own header
# warned about. Both scripts now import from here.
#
# NOTE this is the de Prado CANDIDATE-ROW uniqueness (per-(asset, 5m-bar)
# concurrency over each row's [signal_ts, ts] label window). It is a
# DIFFERENT instrument from scripts/cohort_eval.cohort_effective_n
# (continuous-time uniqueness over realized TRIP spans [t_open, t_close])
# and from ml.history.ess_kish (Kish ESS of a WEIGHT vector) — they answer
# different questions on different inputs and are deliberately NOT merged.
# The matching instrument for a sample of candidate label rows is this one.

# Mirrors ml.history.load_training_data's uniqueness computation (config
# ml.sample_weights defaults): 5m concurrency grid, 14-day span cap
# against corrupt far-future timestamps. Report constants, not knobs.
_UNIQ_GRID_SEC = 300.0
_UNIQ_CAP_BARS = int(14 * 86400 // _UNIQ_GRID_SEC)


def _num(v: object, d: float = 0.0) -> float:
    """Finite float or default — the exact coercion the lifted effective_n
    relies on (NaN and ±inf both fall back to `d`, never propagate). Kept
    verbatim from the source instrument so relocation cannot shift a value."""
    try:
        x = float(v)  # type: ignore[arg-type]
        return x if x == x and abs(x) != float("inf") else d
    except (TypeError, ValueError):
        return d


def effective_n(rows: "list[Mapping[str, Any]]") -> "tuple[float, float]":
    """(n_eff, mean_uniqueness) of a row sample — the number of
    INDEPENDENT observations its statistics actually run on.

    De Prado average uniqueness (AFML ch.4), the loader's exact
    algorithm computed WITHIN this sample: per-(asset, 5m-bar)
    concurrency over each row's [signal_ts, ts] label lifespan; per-row
    uniqueness u_i = mean(1/concurrency) over its bars; n_eff = sum(u_i).
    N fully-concurrent same-asset rows contribute ~1.0 total; disjoint
    rows contribute 1.0 each; different assets never share a path. A
    missing/zero signal_ts falls back to ts (single-bar lifespan) rather
    than fabricating a [0, ts] mega-span that overlaps everything.
    Empty sample -> (0.0, 0.0)."""
    if not rows:
        return 0.0, 0.0
    conc: dict = {}
    spans = []
    for r in rows:
        ts = _num(r.get("ts"))
        sig = _num(r.get("signal_ts"))
        if sig <= 0.0:
            sig = ts
        b0 = int(sig // _UNIQ_GRID_SEC)
        b1 = min(int(max(ts, sig) // _UNIQ_GRID_SEC), b0 + _UNIQ_CAP_BARS)
        asset = r.get("asset") or ""
        spans.append((asset, b0, b1))
        for b in range(b0, b1 + 1):
            conc[(asset, b)] = conc.get((asset, b), 0) + 1
    uniqs = [sum(1.0 / conc[(a, b)] for b in range(b0, b1 + 1))
             / (b1 - b0 + 1) for a, b0, b1 in spans]
    return float(sum(uniqs)), float(sum(uniqs) / len(uniqs))


def wilson_interval(k: float, n: float, z: float = 1.96) -> "tuple[float, float]":
    """Wilson score interval (lo, hi) — correct near 0 and 1, where the
    normal approximation puts bounds outside [0,1].

    `k`/`n` are FLOATS, not ints, on purpose: the honest sample size here
    is EFFECTIVE n, and the interval is evaluated at k_eff = rate * n_eff
    out of n_eff trials, which keeps the point estimate exactly where the
    data put it and widens only the interval. Integer counts still work
    unchanged. Lifted verbatim from scripts/gate_efficacy_report.wilson."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    d = 1.0 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0))
    return ((c - m) / d, (c + m) / d)


def wilson_on_neff(rate: float, n_eff: float,
                   z: float = 1.96) -> "tuple[float, float]":
    """Wilson interval for an observed `rate` re-evaluated on EFFECTIVE n:
    Wilson(rate * n_eff successes out of n_eff trials). The point estimate
    is untouched; only the width reflects the independent-observation
    count. This is the one honest way to interval a per-stratum rate whose
    rows overlap — a nominal-n interval on the same rate is optimistic by
    sqrt(n / n_eff) and reads tight while straddling."""
    return wilson_interval(rate * n_eff, n_eff, z)
