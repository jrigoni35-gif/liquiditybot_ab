# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-09-07 10:35:57 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 60 session(s), 458 symbol-tape(s), 64302 book frames, span 2026-08-30 .. 2026-09-07
- sim under test: `passive_base_prob=0.048` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.22 | y | 12102 | 800 | 0.014 | 0.038 | 0.066 | 0.066 | 0.0% | 0.001 | 3.11 | 4 | 0.54 | NO |
| 10 | 0.44 | y | 12102 | 665 | 0.011 | 0.031 | 0.055 | 0.055 | 0.0% | 0.001 | 4.90 | 4 | 0.298 | NO |
| 15 | 0.67 | y | 12102 | 598 | 0.010 | 0.025 | 0.049 | 0.049 | 0.0% | 0.001 | 6.21 | 4 | 0.184 | NO |
| 20 | 0.89 | y | 12102 | 183 | 0.003 | 0.020 | 0.015 | 0.015 | 0.1% | 0.001 | 8.56 | 4 | 0.0732 | NO |
| 30 | 1.33 | y | 12102 | 131 | 0.002 | 0.013 | 0.011 | 0.011 | 0.1% | 0.002 | 23.36 | 4 | 0.000107 | NO |
| 45 | 2.00 | n | 12102 | 82 | 0.001 | 0.006 | 0.007 | 0.007 | 0.1% | 0.001 | 10.35 | 4 | 0.0349 | NO |
| 60 | 2.67 | n | 12102 | 43 | 0.001 | 0.003 | 0.004 | 0.004 | 0.0% | 0.000 | 3.35 | 4 | 0.501 | NO |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se | S(t) 95% CI |
|---|---|---|---|---|---|---|---|
| 1 | 12102 | 157 | 0.013 | [0.011, 0.015] | 0.987 | 0.0010 | [0.985, 0.989] |
| 2 | 11943 | 175 | 0.015 | [0.013, 0.017] | 0.973 | 0.0015 | [0.970, 0.975] |
| 3 | 11765 | 171 | 0.015 | [0.013, 0.017] | 0.958 | 0.0018 | [0.955, 0.962] |
| 4 | 11593 | 153 | 0.013 | [0.011, 0.015] | 0.946 | 0.0021 | [0.942, 0.950] |
| 5 | 11438 | 144 | 0.013 | [0.011, 0.015] | 0.934 | 0.0023 | [0.929, 0.938] |

## Verdict

**L1 verdict: NO** (`XV-050`)

On these recordings the constant-hazard shape stays within 10% relative of the fitted cumulative fill probability at the T=5 poll horizon. **Recommend closing L2** (no label-geometry change; re-open only if richer recordings contradict this).

## Evidence limits (read before acting)

- 60 session(s) / 458 tape(s) / 64302 book frames, wall-clock span ~186.9 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.021 / 0.026 / 0.033 / 0.088 / 34663.577 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 449 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (9 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~140.4 book polls per tape; longest observed episode = 5 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
