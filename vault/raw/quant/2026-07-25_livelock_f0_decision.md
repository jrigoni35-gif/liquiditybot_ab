# T1.1 decision memo: livelock repair road (2026-07-25)

Operator decision: **F0b — structural drought-scoped probe floor.**
Chosen over F0a (config lever), F0a+F0b, and report-first, with the
bleed priced (probes -$22.87 of -$31.68 net over the P3 window; paper
mode, so the bleed is simulated while the labels are real learning).

Binding conditions (C2 grill verdict, all eight): activates only when
zero admissions of ANY kind for >= configured spans (ML-073
_last_entry_admit_ts drought clock) AND the share cap is the binding
denial; span/count-keyed, never wall-clock; rate/threshold in
config.json with config_guard derivation tied to the 8h label horizon;
new registered SZ-* code recorded into the window; non-drought behavior
byte-identical (test-pinned); conviction never throttled; all existing
probe bounds intact. Rejected variants: window time-decay (replay
determinism), denial-counting denominator (widens in all states).

Companions in Phase 1: snapshot-restore semantics decided + tested
(empty window = 14 free probes), test-harness audit-event hygiene.
Spec: docs/superpowers/specs/2026-07-25-learning-acceleration-design.md
