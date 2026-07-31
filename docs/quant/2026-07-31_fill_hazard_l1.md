# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-07-31 02:04:31 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 61 session(s), 366 symbol-tape(s), 732 book frames, span 2026-07-26 .. 2026-07-31
- sim under test: `passive_base_prob=0.45` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.17 | y | 732 | 0 | 0.000 | 0.381 | 0.000 | 0.000 | - | 0.000 | 0.00 | 0 | - | DEFERRED |
| 10 | 0.33 | y | 732 | 0 | 0.000 | 0.322 | 0.000 | 0.000 | - | 0.000 | 0.00 | 0 | - | DEFERRED |
| 15 | 0.50 | y | 732 | 0 | 0.000 | 0.273 | 0.000 | 0.000 | - | 0.000 | 0.00 | 0 | - | DEFERRED |
| 20 | 0.67 | y | 732 | 0 | 0.000 | 0.231 | 0.000 | 0.000 | - | 0.000 | 0.00 | 0 | - | DEFERRED |
| 30 | 1.00 | y | 732 | 0 | 0.000 | 0.166 | 0.000 | 0.000 | - | 0.000 | 0.00 | 0 | - | DEFERRED |
| 45 | 1.50 | y | 732 | 0 | 0.000 | 0.100 | 0.000 | 0.000 | - | 0.000 | 0.00 | 0 | - | DEFERRED |
| 60 | 2.00 | y | 732 | 0 | 0.000 | 0.061 | 0.000 | 0.000 | - | 0.000 | 0.00 | 0 | - | DEFERRED |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se |
|---|---|---|---|---|---|---|
| 1 | 732 | 0 | 0.000 | [0.000, 0.005] | 1.000 | 0.0000 |
| 2 | 0 | 0 | 0.000 | [0.000, 0.000] | 1.000 | 0.0000 |
| 3 | 0 | 0 | 0.000 | [0.000, 0.000] | 1.000 | 0.0000 |
| 4 | 0 | 0 | 0.000 | [0.000, 0.000] | 1.000 | 0.0000 |
| 5 | 0 | 0 | 0.000 | [0.000, 0.000] | 1.000 | 0.0000 |

## Verdict

**L1 verdict: INSUFFICIENT_EVIDENCE** (`XV-052`)

The recordings cannot resolve the constant-vs-decreasing hazard question (see evidence limits). **L2 stays unadjudicated** — do not spend the 200x1200 re-baseline on this evidence; accrue longer recordings first.

## Evidence limits (read before acting)

- 61 session(s) / 366 tape(s) / 732 book frames, wall-clock span ~111.1 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- ~2.0 book polls per tape; longest observed episode = 1 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
