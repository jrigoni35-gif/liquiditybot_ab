# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-09-12 10:32:43 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 59 session(s), 315 symbol-tape(s), 31502 book frames, span 2026-09-04 .. 2026-09-12
- sim under test: `passive_base_prob=0.048` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- **NO IS NOT 'THE SIM IS SOUND'.** NO means this test could not show the constant comparator misstates F(T) by more than the threshold, on this corpus, at this power. It is a failure to reject, not evidence of absence - reading it as a clean bill of health affirms the null (red-team OBJ-4, conceded: a commit message did exactly that). DEFERRED is the explicit underpowered verdict; NO carries power but still only BOUNDS the misstatement.
- **CONSECUTIVE RUNS ARE NOT INDEPENDENT.** These reports read a ROLLING WINDOW over one recording store: the 2026-09-08 and 2026-09-10 runs shared 7 of their 9 days. Two agreeing reports are close to one fit seen twice, and must not be cited as mutual corroboration.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.49 | y | 8206 | 358 | 0.009 | 0.029 | 0.044 | 0.044 | 0.1% | 0.001 | 2.52 | 4 | 0.641 | NO |
| 10 | 0.98 | y | 8206 | 248 | 0.006 | 0.018 | 0.030 | 0.030 | 0.1% | 0.003 | 16.14 | 4 | 0.00284 | NO |
| 15 | 1.46 | y | 8206 | 195 | 0.005 | 0.011 | 0.024 | 0.024 | 0.1% | 0.003 | 24.60 | 4 | 6.05e-05 | NO |
| 20 | 1.95 | y | 8206 | 121 | 0.003 | 0.007 | 0.015 | 0.015 | 0.1% | 0.002 | 16.64 | 4 | 0.00227 | NO |
| 30 | 2.93 | n | 8206 | 79 | 0.002 | 0.003 | 0.010 | 0.010 | 0.1% | 0.003 | 31.63 | 4 | 2.28e-06 | NO |
| 45 | 4.39 | n | 8206 | 42 | 0.001 | 0.001 | 0.005 | 0.005 | 0.1% | 0.001 | 11.06 | 4 | 0.0259 | NO |
| 60 | 5.85 | n | 8206 | 20 | 0.000 | 0.000 | 0.002 | 0.002 | 0.0% | 0.000 | 3.79 | 4 | 0.435 | NO |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se | S(t) 95% CI |
|---|---|---|---|---|---|---|---|
| 1 | 8206 | 63 | 0.008 | [0.006, 0.010] | 0.992 | 0.0010 | [0.990, 0.994] |
| 2 | 8141 | 71 | 0.009 | [0.007, 0.011] | 0.984 | 0.0014 | [0.981, 0.986] |
| 3 | 8068 | 78 | 0.010 | [0.008, 0.012] | 0.974 | 0.0018 | [0.971, 0.978] |
| 4 | 7990 | 77 | 0.010 | [0.008, 0.012] | 0.965 | 0.0020 | [0.961, 0.969] |
| 5 | 7911 | 69 | 0.009 | [0.007, 0.011] | 0.956 | 0.0023 | [0.952, 0.961] |

## Verdict

**L1 verdict: NO** (`XV-050`)

On these recordings the constant-hazard shape stays within 10% relative of the fitted cumulative fill probability at the T=5 poll horizon. **Recommend closing L2** (no label-geometry change; re-open only if richer recordings contradict this).

## Evidence limits (read before acting)

- 59 session(s) / 315 tape(s) / 31502 book frames, wall-clock span ~186.5 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.018 / 0.026 / 0.032 / 0.063 / 13616.061 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 311 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (4 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~100.0 book polls per tape; longest observed episode = 5 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
