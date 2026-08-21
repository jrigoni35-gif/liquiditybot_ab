# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-08-19 10:33:53 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 61 session(s), 641 symbol-tape(s), 148987 book frames, span 2026-08-08 .. 2026-08-19
- sim under test: `passive_base_prob=0.048` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.59 | y | 37760 | 1579 | 0.009 | 0.027 | 0.042 | 0.042 | 0.1% | 0.001 | 7.71 | 4 | 0.103 | NO |
| 10 | 1.17 | y | 37760 | 1256 | 0.007 | 0.015 | 0.033 | 0.033 | 0.1% | 0.001 | 7.41 | 4 | 0.116 | NO |
| 15 | 1.76 | y | 37760 | 1083 | 0.006 | 0.008 | 0.029 | 0.029 | 0.1% | 0.001 | 9.85 | 4 | 0.0431 | NO |
| 20 | 2.35 | n | 37760 | 190 | 0.001 | 0.005 | 0.005 | 0.005 | 0.0% | 0.000 | 11.25 | 4 | 0.0239 | NO |
| 30 | 3.52 | n | 37760 | 137 | 0.001 | 0.001 | 0.004 | 0.004 | 0.0% | 0.000 | 11.23 | 4 | 0.0241 | NO |
| 45 | 5.28 | n | 37760 | 98 | 0.001 | 0.000 | 0.003 | 0.003 | 0.0% | 0.000 | 8.79 | 4 | 0.0666 | NO |
| 60 | 7.04 | n | 37760 | 32 | 0.000 | 0.000 | 0.001 | 0.001 | 0.0% | 0.000 | 6.63 | 4 | 0.156 | NO |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

[^sigma]: `d_bar` divides by each tape's `scripts/calibrate_fills.estimate_sigma_bps`; on 1 of 85 fitted tape(s) that estimator fell back to its default 30 bps (too few clean frames or timestamps) — `d_bar` (and the near-touch flag) on those parts is nominal, not measured.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se | S(t) 95% CI |
|---|---|---|---|---|---|---|---|
| 1 | 37760 | 335 | 0.009 | [0.008, 0.010] | 0.991 | 0.0005 | [0.990, 0.992] |
| 2 | 37414 | 343 | 0.009 | [0.008, 0.010] | 0.982 | 0.0007 | [0.981, 0.983] |
| 3 | 37046 | 316 | 0.009 | [0.008, 0.010] | 0.974 | 0.0008 | [0.972, 0.975] |
| 4 | 36683 | 315 | 0.009 | [0.008, 0.010] | 0.965 | 0.0009 | [0.963, 0.967] |
| 5 | 36334 | 270 | 0.007 | [0.007, 0.008] | 0.958 | 0.0010 | [0.956, 0.960] |

## Verdict

**L1 verdict: NO** (`XV-050`)

On these recordings the constant-hazard shape stays within 10% relative of the fitted cumulative fill probability at the T=5 poll horizon. **Recommend closing L2** (no label-geometry change; re-open only if richer recordings contradict this).

## Evidence limits (read before acting)

- 61 session(s) / 641 tape(s) / 148987 book frames, wall-clock span ~255.2 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.022 / 0.071 / 50.007 / 333.582 / 33839.307 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 556 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (85 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~232.4 book polls per tape; longest observed episode = 5 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
