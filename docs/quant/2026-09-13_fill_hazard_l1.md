# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-09-13 10:31:48 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 59 session(s), 294 symbol-tape(s), 39526 book frames, span 2026-09-04 .. 2026-09-13
- sim under test: `passive_base_prob=0.048` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- **NO IS NOT 'THE SIM IS SOUND'.** NO means this test could not show the constant comparator misstates F(T) by more than the threshold, on this corpus, at this power. It is a failure to reject, not evidence of absence - reading it as a clean bill of health affirms the null (red-team OBJ-4, conceded: a commit message did exactly that). DEFERRED is the explicit underpowered verdict; NO carries power but still only BOUNDS the misstatement.
- **CONSECUTIVE RUNS ARE NOT INDEPENDENT.** These reports read a ROLLING WINDOW over one recording store: the 2026-09-08 and 2026-09-10 runs shared 7 of their 9 days. Two agreeing reports are close to one fit seen twice, and must not be cited as mutual corroboration.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.87 | y | 10516 | 360 | 0.007 | 0.020 | 0.034 | 0.034 | 0.1% | 0.001 | 2.55 | 4 | 0.635 | NO |
| 10 | 1.74 | y | 10516 | 248 | 0.005 | 0.008 | 0.024 | 0.024 | 0.1% | 0.002 | 15.98 | 4 | 0.00305 | NO |
| 15 | 2.61 | n | 10516 | 195 | 0.004 | 0.004 | 0.019 | 0.019 | 0.1% | 0.002 | 24.48 | 4 | 6.4e-05 | NO |
| 20 | 3.48 | n | 10516 | 121 | 0.002 | 0.001 | 0.012 | 0.011 | 0.1% | 0.002 | 16.58 | 4 | 0.00233 | NO |
| 30 | 5.21 | n | 10516 | 79 | 0.002 | 0.000 | 0.008 | 0.008 | 0.1% | 0.002 | 31.58 | 4 | 2.33e-06 | NO |
| 45 | 7.82 | n | 10516 | 42 | 0.001 | 0.000 | 0.004 | 0.004 | 0.1% | 0.001 | 11.05 | 4 | 0.026 | NO |
| 60 | 10.43 | n | 10516 | 20 | 0.000 | 0.000 | 0.002 | 0.002 | 0.0% | 0.000 | 3.79 | 4 | 0.435 | NO |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se | S(t) 95% CI |
|---|---|---|---|---|---|---|---|
| 1 | 10516 | 63 | 0.006 | [0.005, 0.008] | 0.994 | 0.0008 | [0.993, 0.995] |
| 2 | 10451 | 71 | 0.007 | [0.005, 0.009] | 0.987 | 0.0011 | [0.985, 0.989] |
| 3 | 10378 | 78 | 0.008 | [0.006, 0.009] | 0.980 | 0.0014 | [0.977, 0.983] |
| 4 | 10300 | 78 | 0.008 | [0.006, 0.009] | 0.972 | 0.0016 | [0.969, 0.976] |
| 5 | 10220 | 70 | 0.007 | [0.005, 0.009] | 0.966 | 0.0018 | [0.962, 0.969] |

## Verdict

**L1 verdict: NO** (`XV-050`)

On these recordings the constant-hazard shape stays within 10% relative of the fitted cumulative fill probability at the T=5 poll horizon. **Recommend closing L2** (no label-geometry change; re-open only if richer recordings contradict this).

## Evidence limits (read before acting)

- 59 session(s) / 294 tape(s) / 39526 book frames, wall-clock span ~210.5 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.018 / 0.023 / 0.031 / 0.150 / 13616.061 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 289 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (5 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~134.4 book polls per tape; longest observed episode = 5 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
