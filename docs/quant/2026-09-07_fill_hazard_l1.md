# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-09-07 00:10:43 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 60 session(s), 465 symbol-tape(s), 95809 book frames, span 2026-08-28 .. 2026-09-07
- sim under test: `passive_base_prob=0.048` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.20 | y | 21200 | 1417 | 0.014 | 0.039 | 0.067 | 0.067 | 0.0% | 0.001 | 2.40 | 4 | 0.662 | NO |
| 10 | 0.40 | y | 21200 | 1089 | 0.010 | 0.032 | 0.051 | 0.051 | 0.0% | 0.001 | 5.53 | 4 | 0.237 | NO |
| 15 | 0.60 | y | 21200 | 946 | 0.009 | 0.026 | 0.045 | 0.045 | 0.0% | 0.001 | 4.70 | 4 | 0.319 | NO |
| 20 | 0.81 | y | 21200 | 349 | 0.003 | 0.021 | 0.016 | 0.016 | 0.0% | 0.001 | 4.96 | 4 | 0.291 | NO |
| 30 | 1.21 | y | 21200 | 227 | 0.002 | 0.014 | 0.011 | 0.011 | 0.1% | 0.002 | 21.30 | 4 | 0.000276 | NO |
| 45 | 1.81 | y | 21200 | 134 | 0.001 | 0.008 | 0.006 | 0.006 | 0.1% | 0.001 | 13.59 | 4 | 0.00873 | NO |
| 60 | 2.42 | n | 21200 | 75 | 0.001 | 0.004 | 0.004 | 0.004 | 0.0% | 0.000 | 2.24 | 4 | 0.692 | NO |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se | S(t) 95% CI |
|---|---|---|---|---|---|---|---|
| 1 | 21200 | 292 | 0.014 | [0.012, 0.015] | 0.986 | 0.0008 | [0.985, 0.988] |
| 2 | 20906 | 303 | 0.014 | [0.013, 0.016] | 0.972 | 0.0011 | [0.970, 0.974] |
| 3 | 20598 | 272 | 0.013 | [0.012, 0.015] | 0.959 | 0.0014 | [0.956, 0.962] |
| 4 | 20323 | 289 | 0.014 | [0.013, 0.016] | 0.945 | 0.0016 | [0.942, 0.949] |
| 5 | 20032 | 261 | 0.013 | [0.012, 0.015] | 0.933 | 0.0017 | [0.930, 0.937] |

## Verdict

**L1 verdict: NO** (`XV-050`)

On these recordings the constant-hazard shape stays within 10% relative of the fitted cumulative fill probability at the T=5 poll horizon. **Recommend closing L2** (no label-geometry change; re-open only if richer recordings contradict this).

## Evidence limits (read before acting)

- 60 session(s) / 465 tape(s) / 95809 book frames, wall-clock span ~236.9 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.021 / 0.026 / 0.033 / 0.088 / 34663.577 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 453 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (12 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~206.0 book polls per tape; longest observed episode = 5 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
