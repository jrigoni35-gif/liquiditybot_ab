# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-09-23 10:36:29 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 59 session(s), 309 symbol-tape(s), 28874 book frames, span 2026-09-07 .. 2026-09-23
- sim under test: `passive_base_prob=0.048` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- **NO IS NOT 'THE SIM IS SOUND'.** NO means this test could not show the constant comparator misstates F(T) by more than the threshold, on this corpus, at this power. It is a failure to reject, not evidence of absence - reading it as a clean bill of health affirms the null (red-team OBJ-4, conceded: a commit message did exactly that). DEFERRED is the explicit underpowered verdict; NO carries power but still only BOUNDS the misstatement.
- **CONSECUTIVE RUNS ARE NOT INDEPENDENT.** These reports read a ROLLING WINDOW over one recording store: the 2026-09-08 and 2026-09-10 runs shared 7 of their 9 days. Two agreeing reports are close to one fit seen twice, and must not be cited as mutual corroboration.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.72 | y | 6238 | 128 | 0.004 | 0.023 | 0.021 | 0.021 | 0.0% | 0.001 | 4.02 | 4 | 0.403 | NO |
| 10 | 1.43 | y | 6238 | 66 | 0.002 | 0.011 | 0.011 | 0.011 | 0.0% | 0.001 | 5.04 | 4 | 0.283 | NO |
| 15 | 2.15 | n | 6238 | 42 | 0.001 | 0.006 | 0.007 | 0.007 | 0.0% | 0.001 | 8.98 | 4 | 0.0615 | NO |
| 20 | 2.87 | n | 6238 | 30 | 0.001 | 0.003 | 0.005 | 0.005 | 0.0% | 0.001 | 8.07 | 4 | 0.0891 | NO |
| 30 | 4.30 | n | 6238 | 21 | 0.001 | 0.001 | 0.003 | 0.003 | 0.0% | 0.000 | 3.53 | 4 | 0.474 | NO |
| 45 | 6.45 | n | 6238 | 13 | 0.000 | 0.000 | 0.002 | 0.002 | 0.0% | 0.000 | 2.20 | 4 | 0.699 | NO |
| 60 | 8.60 | n | 6238 | 8 | 0.000 | 0.000 | 0.001 | 0.001 | 0.0% | 0.000 | 0.80 | 4 | 0.939 | DEFERRED |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se | S(t) 95% CI |
|---|---|---|---|---|---|---|---|
| 1 | 6238 | 29 | 0.005 | [0.003, 0.007] | 0.995 | 0.0009 | [0.994, 0.997] |
| 2 | 6209 | 25 | 0.004 | [0.003, 0.006] | 0.991 | 0.0012 | [0.989, 0.994] |
| 3 | 6182 | 25 | 0.004 | [0.003, 0.006] | 0.987 | 0.0014 | [0.985, 0.990] |
| 4 | 6155 | 18 | 0.003 | [0.002, 0.005] | 0.984 | 0.0016 | [0.981, 0.988] |
| 5 | 6137 | 31 | 0.005 | [0.004, 0.007] | 0.979 | 0.0018 | [0.976, 0.983] |

## Verdict

**L1 verdict: NO** (`XV-050`)

On these recordings the constant-hazard shape stays within 10% relative of the fitted cumulative fill probability at the T=5 poll horizon. **Recommend closing L2** (no label-geometry change; re-open only if richer recordings contradict this).

## Evidence limits (read before acting)

- 59 session(s) / 309 tape(s) / 28874 book frames, wall-clock span ~384.3 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.018 / 0.022 / 0.138 / 3319.623 / 20854.024 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 302 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (7 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~93.4 book polls per tape; longest observed episode = 5 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
