# Gate-Truth Instrumentation — Design Spec

**Date:** 2026-07-28 · **Status:** approved (operator: "Build it")
**Motivation:** the 2026-07-28 gate-weight audit (ledger + docs below):
gate_confidence is ANTI-calibrated on realized triple-barrier outcomes
(win 0.359 → 0.321 → 0.297 as confidence rises; AUC 0.469), the weight
ordering contradicts measured discrimination (flow w=1.0 AUC 0.464 anti;
delta w=0.6 AUC 0.524), and the champion model spends 34% of importance
on hour-of-day. The structural root: informed_flow's five component
scores (s_flow/s_delta/s_accum/s_burst/s_trend), the fused evidence and
the concentration are computed every cycle and DISCARDED — only the
collapsed gate_confidence reaches the persisted row, so the realization
path cannot grade WHICH evidence was right. The weights are
unfalsifiable as wired.

**Goal:** every persisted training row carries the exact gate-component
evidence that admitted it, and a report grades each component against
realized outcomes — so re-weighting becomes an evidence-gated decision
(same doctrine as the fee re-tune: measured, never assumed).

## Decisions

**D1 — Capture at the signal.** `SignalResult` (strategies/signal_gates.py)
gains `components: dict = field(default_factory=dict)` (extend-with-
defaults, invariant 7). informed_flow's `_evaluate` populates it:
`{"flow": s_flow, "delta": s_delta, "accum": s_accum, "burst": s_burst,
"trend": s_trend, "evidence": evidence, "conc": concentration}` — the
RAW signed scores the weights act on (positive = long evidence), the
fused Σw·s, and the normalized-HHI concentration already computed for
TH-021. The legacy five_gate engine is untouched (empty dict → zeros
downstream). Non-finite values are sanitized to 0.0 at capture.

**D2 — Schema: 7 trailing telemetry columns.** `sg_flow, sg_delta,
sg_accum, sg_burst, sg_trend, sg_evidence, sg_conc` appended after
`sl_frac` in HistoryStore._header. Trailing-meta count 13 → 20 (the
width assert in _append_row updates). Written `%.4f`; default 0.0 =
"pre-instrumentation / unknown / legacy engine" (same convention as
pt_frac). BOOKKEEPING ONLY — never features: FEATURE_NAMES is untouched,
model dimensionality does not change, no overfit surface is added.
Non-finite components sanitize to 0.0 (telemetry never drops a row —
unlike pnl/pt_frac, they are not label-bearing).

**D3 — Candidate path.** The one register call site (main.py ~:3324)
adds `gate_components=signal.components`. `CandidateTracker.register`
gains kwarg `gate_components: "dict | None" = None`, stores a sanitized
float dict on the candidate; `_emit_label` threads
`gate_components=cand.get("gate_components")` into `_append_row`.

**D4 — Live path.** The three entry-meta blocks (direct submit, ladder
rungs, algo parent) add `"gate_components": signal.components`.
`_handle_fill`'s `log_entry` call passes
`gate_components=order.meta.get("gate_components")`; `log_entry` appends
it as the 8th `_pending` tuple element; `log_close` unpacks the len==8
shape (existing versioned-tuple pattern, len 7/6/5/4/3 all preserved)
and threads to `_append_row`. Rows store RAW signed scores — direction
alignment is derived at read time (report), never baked in.

**D5 — Report.** `scripts/gate_truth_report.py`, report-only (never
mutates). Sections: [1] instrumentation coverage (instrumented = any
|sg_*| > 0, era = triple_barrier); [2] per-component realized win-rate
aligned-vs-opposed + rank AUC of `s_i × direction` vs label; [3]
weight-vs-data table (config `strategies.weights` vs measured AUC
ranks); [4] gate_confidence calibration buckets. Verdict: XV-040
ALIGNED / XV-041 MISALIGNED (weight rank order vs AUC rank order,
Spearman ≥ 0 on the five components = aligned) / XV-042 INSUFFICIENT
(< 100 instrumented era rows — documented floor, cost-truth precedent).

**D6 — Codes.** core/codes.py: `XV_GATE_TRUTH_ALIGNED = "XV-040"`,
`XV_GATE_TRUTH_MISALIGNED = "XV-041"`, `XV_GATE_TRUTH_THIN = "XV-042"`
(XV header comment mentions gate truth).

**D7 — Non-goals.** NO weight changes (OF-4: 868 rows is peak-tuning
territory); NO new model features; NO config knobs (report constants
documented in-file, T7 precedent); five_gate engine untouched;
re-weighting is a future, separately-gated decision requiring the full
gate battery (net-profit smoke, G3/G5, simplicity ladder OOS).

## Consequences
- Rows before this ship read 0.0 in all sg_* columns and are excluded
  from the report's instrumented sample (never guessed at).
- The schema bump rotates/migrates exactly as T3's did (+2 columns then,
  +7 now) — session-start alignment pads legacy bundles.
- When enough instrumented rows accrue, the weight decision runs on
  evidence; the report is the standing measurement.
