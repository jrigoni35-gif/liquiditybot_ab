# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-09-20 10:34:46 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 59 session(s), 311 symbol-tape(s), 26809 book frames, span 2026-09-06 .. 2026-09-20
- sim under test: `passive_base_prob=0.048` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- **NO IS NOT 'THE SIM IS SOUND'.** NO means this test could not show the constant comparator misstates F(T) by more than the threshold, on this corpus, at this power. It is a failure to reject, not evidence of absence - reading it as a clean bill of health affirms the null (red-team OBJ-4, conceded: a commit message did exactly that). DEFERRED is the explicit underpowered verdict; NO carries power but still only BOUNDS the misstatement.
- **CONSECUTIVE RUNS ARE NOT INDEPENDENT.** These reports read a ROLLING WINDOW over one recording store: the 2026-09-08 and 2026-09-10 runs shared 7 of their 9 days. Two agreeing reports are close to one fit seen twice, and must not be cited as mutual corroboration.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 1.45 | y | 5476 | 78 | 0.003 | 0.011 | 0.014 | 0.014 | 0.1% | 0.001 | 7.09 | 4 | 0.131 | NO |
| 10 | 2.89 | n | 5476 | 45 | 0.002 | 0.003 | 0.008 | 0.008 | 0.0% | 0.001 | 2.26 | 4 | 0.689 | NO |
| 15 | 4.34 | n | 5476 | 31 | 0.001 | 0.001 | 0.006 | 0.006 | 0.0% | 0.001 | 7.53 | 4 | 0.11 | NO |
| 20 | 5.78 | n | 5476 | 23 | 0.001 | 0.000 | 0.004 | 0.004 | 0.0% | 0.001 | 9.19 | 4 | 0.0565 | NO |
| 30 | 8.67 | n | 5476 | 15 | 0.001 | 0.000 | 0.003 | 0.003 | 0.0% | 0.000 | 5.31 | 4 | 0.256 | NO |
| 45 | 13.01 | n | 5476 | 9 | 0.000 | 0.000 | 0.002 | 0.002 | 0.0% | 0.000 | 7.10 | 4 | 0.131 | DEFERRED |
| 60 | 17.34 | n | 5476 | 6 | 0.000 | 0.000 | 0.001 | 0.001 | 0.0% | 0.000 | 0.58 | 4 | 0.965 | DEFERRED |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se | S(t) 95% CI |
|---|---|---|---|---|---|---|---|
| 1 | 5476 | 23 | 0.004 | [0.003, 0.006] | 0.996 | 0.0009 | [0.994, 0.998] |
| 2 | 5453 | 15 | 0.003 | [0.002, 0.005] | 0.993 | 0.0011 | [0.991, 0.995] |
| 3 | 5436 | 13 | 0.002 | [0.001, 0.004] | 0.991 | 0.0013 | [0.988, 0.993] |
| 4 | 5421 | 9 | 0.002 | [0.001, 0.003] | 0.989 | 0.0014 | [0.986, 0.992] |
| 5 | 5412 | 18 | 0.003 | [0.002, 0.005] | 0.986 | 0.0016 | [0.983, 0.989] |

## Verdict

**L1 verdict: NO** (`XV-050`)

On these recordings the constant-hazard shape stays within 10% relative of the fitted cumulative fill probability at the T=5 poll horizon. **Recommend closing L2** (no label-geometry change; re-open only if richer recordings contradict this).

## Evidence limits (read before acting)

- 59 session(s) / 311 tape(s) / 26809 book frames, wall-clock span ~324.3 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.018 / 0.022 / 0.051 / 3318.266 / 13616.061 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 305 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (6 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~86.2 book polls per tape; longest observed episode = 5 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
