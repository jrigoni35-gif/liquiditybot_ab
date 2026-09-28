# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-09-27 10:38:25 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 59 session(s), 311 symbol-tape(s), 41233 book frames, span 2026-09-07 .. 2026-09-27
- sim under test: `passive_base_prob=0.048` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- **NO IS NOT 'THE SIM IS SOUND'.** NO means this test could not show the constant comparator misstates F(T) by more than the threshold, on this corpus, at this power. It is a failure to reject, not evidence of absence - reading it as a clean bill of health affirms the null (red-team OBJ-4, conceded: a commit message did exactly that). DEFERRED is the explicit underpowered verdict; NO carries power but still only BOUNDS the misstatement.
- **CONSECUTIVE RUNS ARE NOT INDEPENDENT.** These reports read a ROLLING WINDOW over one recording store: the 2026-09-08 and 2026-09-10 runs shared 7 of their 9 days. Two agreeing reports are close to one fit seen twice, and must not be cited as mutual corroboration.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.70 | y | 9836 | 248 | 0.005 | 0.024 | 0.025 | 0.025 | 0.1% | 0.001 | 5.55 | 4 | 0.235 | NO |
| 10 | 1.40 | y | 9836 | 112 | 0.002 | 0.012 | 0.011 | 0.011 | 0.0% | 0.001 | 8.04 | 4 | 0.0901 | NO |
| 15 | 2.10 | n | 9836 | 62 | 0.001 | 0.006 | 0.006 | 0.006 | 0.0% | 0.001 | 13.15 | 4 | 0.0106 | NO |
| 20 | 2.80 | n | 9836 | 40 | 0.001 | 0.003 | 0.004 | 0.004 | 0.0% | 0.000 | 8.39 | 4 | 0.0784 | NO |
| 30 | 4.20 | n | 9836 | 25 | 0.001 | 0.001 | 0.003 | 0.003 | 0.0% | 0.000 | 2.06 | 4 | 0.726 | NO |
| 45 | 6.30 | n | 9836 | 14 | 0.000 | 0.000 | 0.001 | 0.001 | 0.0% | 0.000 | 2.71 | 4 | 0.607 | NO |
| 60 | 8.40 | n | 9836 | 8 | 0.000 | 0.000 | 0.001 | 0.001 | 0.0% | 0.000 | 0.80 | 4 | 0.939 | DEFERRED |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se | S(t) 95% CI |
|---|---|---|---|---|---|---|---|
| 1 | 9836 | 62 | 0.006 | [0.005, 0.008] | 0.994 | 0.0008 | [0.992, 0.995] |
| 2 | 9772 | 45 | 0.005 | [0.003, 0.006] | 0.989 | 0.0010 | [0.987, 0.991] |
| 3 | 9725 | 51 | 0.005 | [0.004, 0.007] | 0.984 | 0.0013 | [0.981, 0.986] |
| 4 | 9672 | 39 | 0.004 | [0.003, 0.006] | 0.980 | 0.0014 | [0.977, 0.983] |
| 5 | 9633 | 51 | 0.005 | [0.004, 0.007] | 0.975 | 0.0016 | [0.972, 0.978] |

## Verdict

**L1 verdict: NO** (`XV-050`)

On these recordings the constant-hazard shape stays within 10% relative of the fitted cumulative fill probability at the T=5 poll horizon. **Recommend closing L2** (no label-geometry change; re-open only if richer recordings contradict this).

## Evidence limits (read before acting)

- 59 session(s) / 311 tape(s) / 41233 book frames, wall-clock span ~475.1 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.018 / 0.022 / 0.139 / 3320.951 / 13428.050 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 303 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (8 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~132.6 book polls per tape; longest observed episode = 5 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
