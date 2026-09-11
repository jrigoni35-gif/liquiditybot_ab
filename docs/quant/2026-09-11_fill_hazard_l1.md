# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-09-11 10:32:32 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 59 session(s), 348 symbol-tape(s), 29780 book frames, span 2026-09-04 .. 2026-09-11
- sim under test: `passive_base_prob=0.048` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.58 | y | 7644 | 337 | 0.009 | 0.027 | 0.044 | 0.044 | 0.1% | 0.002 | 3.32 | 4 | 0.505 | NO |
| 10 | 1.16 | y | 7644 | 233 | 0.006 | 0.015 | 0.030 | 0.030 | 0.1% | 0.003 | 13.72 | 4 | 0.00823 | NO |
| 15 | 1.74 | y | 7644 | 184 | 0.005 | 0.008 | 0.024 | 0.024 | 0.1% | 0.003 | 22.08 | 4 | 0.000193 | NO |
| 20 | 2.32 | n | 7644 | 110 | 0.003 | 0.005 | 0.014 | 0.014 | 0.1% | 0.002 | 15.28 | 4 | 0.00415 | NO |
| 30 | 3.48 | n | 7644 | 71 | 0.002 | 0.001 | 0.009 | 0.009 | 0.1% | 0.003 | 29.48 | 4 | 6.23e-06 | NO |
| 45 | 5.22 | n | 7644 | 37 | 0.001 | 0.000 | 0.005 | 0.005 | 0.1% | 0.001 | 11.47 | 4 | 0.0217 | NO |
| 60 | 6.96 | n | 7644 | 17 | 0.000 | 0.000 | 0.002 | 0.002 | 0.0% | 0.000 | 4.85 | 4 | 0.303 | NO |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se | S(t) 95% CI |
|---|---|---|---|---|---|---|---|
| 1 | 7644 | 57 | 0.007 | [0.006, 0.010] | 0.993 | 0.0010 | [0.991, 0.994] |
| 2 | 7585 | 68 | 0.009 | [0.007, 0.011] | 0.984 | 0.0015 | [0.981, 0.986] |
| 3 | 7517 | 73 | 0.010 | [0.008, 0.012] | 0.974 | 0.0018 | [0.971, 0.978] |
| 4 | 7444 | 74 | 0.010 | [0.008, 0.012] | 0.964 | 0.0021 | [0.960, 0.969] |
| 5 | 7368 | 65 | 0.009 | [0.007, 0.011] | 0.956 | 0.0023 | [0.951, 0.961] |

## Verdict

**L1 verdict: NO** (`XV-050`)

On these recordings the constant-hazard shape stays within 10% relative of the fitted cumulative fill probability at the T=5 poll horizon. **Recommend closing L2** (no label-geometry change; re-open only if richer recordings contradict this).

## Evidence limits (read before acting)

- 59 session(s) / 348 tape(s) / 29780 book frames, wall-clock span ~162.5 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.018 / 0.026 / 0.033 / 0.106 / 13616.061 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 345 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (3 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~85.6 book polls per tape; longest observed episode = 5 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
