# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-09-04 22:49:33 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 61 session(s), 533 symbol-tape(s), 149813 book frames, span 2026-08-18 .. 2026-09-04
- sim under test: `passive_base_prob=0.048` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.18 | y | 32180 | 2411 | 0.015 | 0.040 | 0.075 | 0.075 | 0.2% | 0.003 | 15.91 | 4 | 0.00314 | NO |
| 10 | 0.36 | y | 32180 | 2063 | 0.013 | 0.034 | 0.064 | 0.064 | 0.1% | 0.002 | 9.87 | 4 | 0.0426 | NO |
| 15 | 0.54 | y | 32180 | 1892 | 0.012 | 0.028 | 0.059 | 0.059 | 0.1% | 0.002 | 8.82 | 4 | 0.0658 | NO |
| 20 | 0.72 | y | 32180 | 482 | 0.003 | 0.023 | 0.015 | 0.015 | 0.0% | 0.000 | 0.79 | 4 | 0.94 | NO |
| 30 | 1.08 | y | 32180 | 347 | 0.002 | 0.016 | 0.011 | 0.011 | 0.0% | 0.001 | 5.83 | 4 | 0.212 | NO |
| 45 | 1.62 | y | 32180 | 232 | 0.001 | 0.010 | 0.007 | 0.007 | 0.0% | 0.001 | 6.15 | 4 | 0.188 | NO |
| 60 | 2.16 | n | 32180 | 137 | 0.001 | 0.006 | 0.004 | 0.004 | 0.0% | 0.000 | 1.42 | 4 | 0.841 | NO |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se | S(t) 95% CI |
|---|---|---|---|---|---|---|---|
| 1 | 32180 | 549 | 0.017 | [0.016, 0.019] | 0.983 | 0.0007 | [0.982, 0.984] |
| 2 | 31625 | 527 | 0.017 | [0.015, 0.018] | 0.967 | 0.0010 | [0.965, 0.969] |
| 3 | 31085 | 448 | 0.014 | [0.013, 0.016] | 0.953 | 0.0012 | [0.950, 0.955] |
| 4 | 30625 | 470 | 0.015 | [0.014, 0.017] | 0.938 | 0.0013 | [0.935, 0.941] |
| 5 | 30142 | 417 | 0.014 | [0.013, 0.015] | 0.925 | 0.0015 | [0.922, 0.928] |

## Verdict

**L1 verdict: NO** (`XV-050`)

On these recordings the constant-hazard shape stays within 10% relative of the fitted cumulative fill probability at the T=5 poll horizon. **Recommend closing L2** (no label-geometry change; re-open only if richer recordings contradict this).

## Evidence limits (read before acting)

- 61 session(s) / 533 tape(s) / 149813 book frames, wall-clock span ~407.8 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.021 / 0.024 / 0.050 / 167.412 / 34663.577 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 492 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (41 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~281.1 book polls per tape; longest observed episode = 5 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
