# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-09-10 10:32:59 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 59 session(s), 409 symbol-tape(s), 45792 book frames, span 2026-09-02 .. 2026-09-10
- sim under test: `passive_base_prob=0.048` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.24 | y | 8346 | 448 | 0.011 | 0.038 | 0.054 | 0.054 | 0.0% | 0.001 | 2.39 | 4 | 0.664 | NO |
| 10 | 0.47 | y | 8346 | 313 | 0.008 | 0.030 | 0.038 | 0.037 | 0.1% | 0.003 | 10.87 | 4 | 0.0281 | NO |
| 15 | 0.71 | y | 8346 | 246 | 0.006 | 0.024 | 0.029 | 0.029 | 0.1% | 0.002 | 15.05 | 4 | 0.00461 | NO |
| 20 | 0.95 | y | 8346 | 166 | 0.004 | 0.019 | 0.020 | 0.020 | 0.1% | 0.001 | 7.27 | 4 | 0.122 | NO |
| 30 | 1.42 | y | 8346 | 114 | 0.003 | 0.012 | 0.014 | 0.014 | 0.1% | 0.003 | 24.87 | 4 | 5.35e-05 | NO |
| 45 | 2.13 | n | 8346 | 67 | 0.002 | 0.006 | 0.008 | 0.008 | 0.1% | 0.001 | 10.82 | 4 | 0.0287 | NO |
| 60 | 2.84 | n | 8346 | 39 | 0.001 | 0.003 | 0.005 | 0.005 | 0.0% | 0.000 | 2.54 | 4 | 0.637 | NO |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se | S(t) 95% CI |
|---|---|---|---|---|---|---|---|
| 1 | 8346 | 81 | 0.010 | [0.008, 0.012] | 0.990 | 0.0011 | [0.988, 0.992] |
| 2 | 8263 | 93 | 0.011 | [0.009, 0.014] | 0.979 | 0.0016 | [0.976, 0.982] |
| 3 | 8169 | 98 | 0.012 | [0.010, 0.015] | 0.967 | 0.0019 | [0.964, 0.971] |
| 4 | 8070 | 92 | 0.011 | [0.009, 0.014] | 0.956 | 0.0022 | [0.952, 0.961] |
| 5 | 7976 | 84 | 0.011 | [0.009, 0.013] | 0.946 | 0.0025 | [0.941, 0.951] |

## Verdict

**L1 verdict: NO** (`XV-050`)

On these recordings the constant-hazard shape stays within 10% relative of the fitted cumulative fill probability at the T=5 poll horizon. **Recommend closing L2** (no label-geometry change; re-open only if richer recordings contradict this).

## Evidence limits (read before acting)

- 59 session(s) / 409 tape(s) / 45792 book frames, wall-clock span ~201.8 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.021 / 0.029 / 0.034 / 0.329 / 34663.577 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 401 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (8 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~112.0 book polls per tape; longest observed episode = 5 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
