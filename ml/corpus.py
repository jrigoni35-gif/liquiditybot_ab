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


def gross_ret_pct(row: Mapping[str, Any]) -> "float | None":
    """Side-adjusted gross return in percent from entry/exit prices.

    None when unrecoverable (missing/blank/nonpositive entry) — never 0.
    """
    e_raw, x_raw = row.get("entry_price"), row.get("exit_price")
    if is_unknown(e_raw) or is_unknown(x_raw):
        return None
    try:
        entry, exit_ = float(e_raw), float(x_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if entry <= 0.0:
        return None
    raw = (exit_ - entry) / entry * 100.0
    return -raw if str(row.get("side") or "long") == "short" else raw


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
