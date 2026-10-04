# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-10-03 10:40:43 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 59 session(s), 377 symbol-tape(s), 50627 book frames, span 2026-09-10 .. 2026-10-03
- sim under test: `passive_base_prob=0.048` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- **NO IS NOT 'THE SIM IS SOUND'.** NO means this test could not show the constant comparator misstates F(T) by more than the threshold, on this corpus, at this power. It is a failure to reject, not evidence of absence - reading it as a clean bill of health affirms the null (red-team OBJ-4, conceded: a commit message did exactly that). DEFERRED is the explicit underpowered verdict; NO carries power but still only BOUNDS the misstatement.
- **CONSECUTIVE RUNS ARE NOT INDEPENDENT.** These reports read a ROLLING WINDOW over one recording store: the 2026-09-08 and 2026-09-10 runs shared 7 of their 9 days. Two agreeing reports are close to one fit seen twice, and must not be cited as mutual corroboration.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.59 | y | 11680 | 296 | 0.005 | 0.027 | 0.025 | 0.025 | 0.1% | 0.002 | 8.73 | 4 | 0.0681 | NO |
| 10 | 1.19 | y | 11680 | 146 | 0.003 | 0.015 | 0.013 | 0.013 | 0.0% | 0.001 | 10.77 | 4 | 0.0293 | NO |
| 15 | 1.78 | y | 11680 | 84 | 0.001 | 0.008 | 0.007 | 0.007 | 0.0% | 0.001 | 9.85 | 4 | 0.0431 | NO |
| 20 | 2.37 | n | 11680 | 57 | 0.001 | 0.004 | 0.005 | 0.005 | 0.0% | 0.000 | 8.17 | 4 | 0.0855 | NO |
| 30 | 3.56 | n | 11680 | 40 | 0.001 | 0.001 | 0.003 | 0.003 | 0.0% | 0.000 | 1.05 | 4 | 0.902 | NO |
| 45 | 5.33 | n | 11680 | 25 | 0.000 | 0.000 | 0.002 | 0.002 | 0.0% | 0.000 | 2.06 | 4 | 0.726 | NO |
| 60 | 7.11 | n | 11680 | 14 | 0.000 | 0.000 | 0.001 | 0.001 | 0.0% | 0.000 | 2.04 | 4 | 0.728 | NO |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se | S(t) 95% CI |
|---|---|---|---|---|---|---|---|
| 1 | 11680 | 75 | 0.006 | [0.005, 0.008] | 0.994 | 0.0007 | [0.992, 0.995] |
| 2 | 11605 | 64 | 0.006 | [0.004, 0.007] | 0.988 | 0.0010 | [0.986, 0.990] |
| 3 | 11534 | 57 | 0.005 | [0.004, 0.006] | 0.983 | 0.0012 | [0.981, 0.986] |
| 4 | 11475 | 43 | 0.004 | [0.003, 0.005] | 0.980 | 0.0013 | [0.977, 0.982] |
| 5 | 11432 | 57 | 0.005 | [0.004, 0.006] | 0.975 | 0.0015 | [0.972, 0.977] |

## Verdict

**L1 verdict: NO** (`XV-050`)

On these recordings the constant-hazard shape stays within 10% relative of the fitted cumulative fill probability at the T=5 poll horizon. **Recommend closing L2** (no label-geometry change; re-open only if richer recordings contradict this).

## Evidence limits (read before acting)

- 59 session(s) / 377 tape(s) / 50627 book frames, wall-clock span ~556.8 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.018 / 0.027 / 960.819 / 3322.334 / 20728.449 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 365 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (12 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~134.3 book polls per tape; longest observed episode = 5 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
