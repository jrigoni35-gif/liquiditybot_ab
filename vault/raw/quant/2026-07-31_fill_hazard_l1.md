# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-07-31 02:29:19 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 61 session(s), 366 symbol-tape(s), 732 book frames, span 2026-07-26 .. 2026-07-31
- sim under test: `passive_base_prob=0.45` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Verdict

**L1 verdict: INSUFFICIENT_EVIDENCE** (`XV-052`)

All usable episodes were lost to the frame-gap guard: 366 of 366 tape(s) have a median intra-frame gap deviating from `polling_interval_sec` by more than 3x (burst re-reads, not engine polls — frame index would misstate poll age; see evidence limits), so the constant-vs-decreasing hazard question cannot be adjudicated. Accrue recordings (system.record_feeds) polled at the engine cadence with enough polls per session to cover the order timeout horizon (T=5 polls) and re-run.

## Evidence limits (read before acting)

- 61 session(s) / 366 tape(s) / 732 book frames, wall-clock span ~110.8 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.011 / 0.013 / 0.014 / 0.018 / 0.929 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 366 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (0 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~2.0 book polls per tape; longest observed episode = 0 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
