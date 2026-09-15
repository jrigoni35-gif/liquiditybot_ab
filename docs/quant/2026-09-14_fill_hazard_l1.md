# L1 — maker-fill hazard time-consistency (Debate-1, report-only)

- generated: 2026-09-14 10:33:33 UTC by `scripts/fill_hazard_report.py`
- mode: **book-frame synthesis** — recordings contain order-book snapshots only (no order events, no trade prints), so resting-maker episodes are synthesized by replaying book frames against a hypothetical resting level; a fill opportunity = opposite best quote at-or-through the level.
- recordings: 59 session(s), 282 symbol-tape(s), 40436 book frames, span 2026-09-04 .. 2026-09-14
- sim under test: `passive_base_prob=0.048` x exp(-dist/sigma), constant per poll; `order_timeout_sec=25.0`, `polling_interval_sec=5.0` -> horizon T=5 polls; `queue_aware=True`.
- **NO IS NOT 'THE SIM IS SOUND'.** NO means this test could not show the constant comparator misstates F(T) by more than the threshold, on this corpus, at this power. It is a failure to reject, not evidence of absence - reading it as a clean bill of health affirms the null (red-team OBJ-4, conceded: a commit message did exactly that). DEFERRED is the explicit underpowered verdict; NO carries power but still only BOUNDS the misstatement.
- **CONSECUTIVE RUNS ARE NOT INDEPENDENT.** These reports read a ROLLING WINDOW over one recording store: the 2026-09-08 and 2026-09-10 runs shared 7 of their 9 days. Two agreeing reports are close to one fit seen twice, and must not be cited as mutual corroboration.
- verdict rule: YES iff rel misstatement of F(T) > 10% AND LR p < 0.05; the constant comparator is the BEST-FIT constant hazard (shape test — the LEVEL belongs to scripts/calibrate_fills.py).

## Constant vs fitted, per distance bucket

| dist bps | d_bar | near-touch | episodes | events | h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) | rel misstate | KS | LR | dof | p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.55 | y | 10744 | 389 | 0.007 | 0.028 | 0.036 | 0.036 | 0.0% | 0.001 | 1.38 | 4 | 0.847 | NO |
| 10 | 1.09 | y | 10744 | 260 | 0.005 | 0.016 | 0.024 | 0.024 | 0.1% | 0.002 | 15.67 | 4 | 0.00349 | NO |
| 15 | 1.64 | y | 10744 | 202 | 0.004 | 0.009 | 0.019 | 0.019 | 0.1% | 0.002 | 26.27 | 4 | 2.79e-05 | NO |
| 20 | 2.19 | n | 10744 | 125 | 0.002 | 0.005 | 0.012 | 0.012 | 0.1% | 0.002 | 16.77 | 4 | 0.00214 | NO |
| 30 | 3.28 | n | 10744 | 80 | 0.001 | 0.002 | 0.007 | 0.007 | 0.1% | 0.002 | 32.27 | 4 | 1.68e-06 | NO |
| 45 | 4.92 | n | 10744 | 42 | 0.001 | 0.000 | 0.004 | 0.004 | 0.1% | 0.001 | 11.05 | 4 | 0.0261 | NO |
| 60 | 6.56 | n | 10744 | 20 | 0.000 | 0.000 | 0.002 | 0.002 | 0.0% | 0.000 | 3.79 | 4 | 0.435 | NO |

`p_sim (config)` = passive_base_prob * exp(-d_bar): the configured LEVEL, shown for context only — the verdict compares shapes, not levels.

## Fitted hazard h(t) — primary bucket (5 bps, most events among near-touch)

| poll t | at-risk n_t | hits d_t | h(t) | Wilson 95% | S(t) | Greenwood se | S(t) 95% CI |
|---|---|---|---|---|---|---|---|
| 1 | 10744 | 71 | 0.007 | [0.005, 0.008] | 0.993 | 0.0008 | [0.992, 0.995] |
| 2 | 10671 | 77 | 0.007 | [0.006, 0.009] | 0.986 | 0.0011 | [0.984, 0.988] |
| 3 | 10593 | 83 | 0.008 | [0.006, 0.010] | 0.978 | 0.0014 | [0.976, 0.981] |
| 4 | 10510 | 81 | 0.008 | [0.006, 0.010] | 0.971 | 0.0016 | [0.968, 0.974] |
| 5 | 10427 | 77 | 0.007 | [0.006, 0.009] | 0.964 | 0.0018 | [0.960, 0.967] |

## Verdict

**L1 verdict: NO** (`XV-050`)

On these recordings the constant-hazard shape stays within 10% relative of the fitted cumulative fill probability at the T=5 poll horizon. **Recommend closing L2** (no label-geometry change; re-open only if richer recordings contradict this).

## Evidence limits (read before acting)

- 59 session(s) / 282 tape(s) / 40436 book frames, wall-clock span ~234.5 h — but hazard resolution is bounded by CONSECUTIVE polls per tape, not wall-clock span.
- Frame-gap vs poll-interval: per-tape median intra-frame gap (min/p25/p50/p75/max) = 0.018 / 0.021 / 0.030 / 0.073 / 13616.061 s against `polling_interval_sec=5` s. Poll AGE is only identified when frames are engine polls, so the 277 tape(s) whose median gap deviates by more than 3x (disclosure threshold, not a fitted knob) were EXCLUDED from hazard-age fitting (5 tape(s) fitted). Burst re-read tapes measure intra-second book flicker, not the per-poll hazard the sim applies.
- ~143.4 book polls per tape; longest observed episode = 5 poll(s) vs horizon T=5 — poll ages beyond that are structurally UNOBSERVABLE in these recordings regardless of session count.
- Episodes are SYNTHESIZED from book snapshots (no recorded order events or trade prints): a best-quote touch is a fill OPPORTUNITY, not a guaranteed fill — queue position is not observable, so this measures the market-side arrival hazard the sim's constant-p term models.
- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until the modeled queue clears, then constant — the constant-hazard assumption under test is the post-queue-clear phase.
- Buy and sell placements are pooled per bucket; per-bucket fits avoid cross-DISTANCE pooling, but residual heterogeneity (symbol/session/side) biases a pooled hazard toward DECREASING (frailty artifact) — a YES that leans on a single bucket or a thin tape should be re-confirmed on richer recordings.
- Poll bins with fewer than 20 at-risk episodes are unresolved; a verdict needs >= 2 resolved bins, 80 episodes and 10 hits per bucket (horizon T=5 polls).
- **AUDIT ADDENDUM (hand-added 2026-09-14, NOT generator output; re-derive every count, none is written here).** The session and tape counts above are not all market data. `scripts/smoke_test.py`'s `qa_redirect_paths` did not redirect `system.recording_dir` (fixed 2026-09-14), and its runner section constructs a real `BotRunner` on the production config, so every QA smoke boot wrote a short MockKraken fixture session into `outputs/recordings`. Most of the retained session slots and most of the symbol-tape count are such fixtures; they are a negligible share of the BOOK FRAMES, and every one of them is removed by the frame-gap guard before episode synthesis — verified by ablation: removing every fixture session leaves each bucket row and the overall verdict byte-identical, while removing one real fitted session moves all of them. No fixture episode reaches any fit, `d_bar`, statistic or verdict on this page. Two consequences for reading it: the `book polls per tape` figure above divides real frames by a fixture-inflated tape count and UNDERSTATES real per-tape depth by several times, and the exclusion sentence above attributes every excluded tape to burst re-reads when most of them were never market data at all. The store is a FIFO ring at `system.recording.retain_files` and sat at that cap, so each QA boot evicted a real recording and both the counts and the fixture split moved every boot until the fix — re-derive with a classifier over `outputs/recordings` (MockKraken quotes every non-ETH symbol off one BTC price and books 15 levels; real Kraken tapes book 20; fixture sidecars carry `start.equity == 10000.0` and no `end` key).
- **THE `rel misstate` ARM WAS BOUNDED BELOW ITS OWN THRESHOLD BEFORE ANY DATA WAS READ.** `hazard_verdict` evaluates the misstatement at exactly one point, the timeout horizon, against a constant hazard fitted on the same exposure; two models calibrated to the same event total agree at that endpoint by construction, so the residual scales with F(T) and, at the fill rate and the near-absence of censoring in these recordings, the maximum attainable over ANY hazard shape is far below the 10% YES threshold — the arm only becomes reachable at cumulative fill probabilities several times the observed. The `powered` gate tests episode, event and resolved-bin COUNTS only; it never tests whether the threshold is attainable. So this NO BOUNDS the endpoint misstatement rather than testing the hazard's shape, which is why it can sit beside LR p-values that reject constancy in most buckets, and why the same fitted shape misstates cumulative fill by more than 10% at the FIRST poll while reading 0.0% at the horizon. Re-derive the attainable ceiling by injecting this bucket's own episode and event counts into `hazard_verdict` with the hits redistributed across polls. Audit record: vault `raw/audits/2026-09-14_fill_hazard_l1_instrument_audit.md`.
- **CORRECTION (hand-added 2026-09-15, red-team panel; verified by grep) — THE COMPARATOR IS RETIRED CODE.** The "sim under test" named at line 6 (constant per-poll hazard `passive_base_prob x exp(-dist/sigma)`, `queue_aware`) has been OFF since execution-era boundary #4 (`aeeaae36`, 2026-08-10T11:03:35Z): `config.json` `order_manager.sim_fill.passive_hazard_with_book` is `false`, and the only call of `_passive_poll_prob` (`execution/order_manager.py`, inside `if ... and self.sf_hazard_with_book:`) is gated on it. The live dry-run fill rule is `_sim_maker_cross`, which fills on the same event this report counts as a fill OPPORTUNITY — so the fitted hazard and the "constant comparator" are two descriptions of one recorded event, and the NO above grades a model that decides nothing. The `config.json` `_passive_hazard_with_book_doc` has said so since the boundary. Also from the panel: the power gate counts NOMINAL episodes — 5 tapes from 3 sessions with buy+sell doubled per placement — and two design-effect routes put effective EVENTS at 4-6 per bucket against `E_MIN=10`, so every row above is DEFERRED under any clustered n; the fitted frames are REST `get_order_book` snapshots, which the recorder writes only when the WS book is stale, a quiet-book sample of a book the sim never fills on; and the "T=5 poll" horizon is not 25 s of wall clock inside these tapes (hit-conditional wall age is minutes). **Read every verdict on this page, and on the nine before it, as unproven about the deployed fill simulator.** Do not act on "Recommend closing L2"; L2 is returned to the docket. Vault: `synthesis/owed-measurements` 116, `concepts/the-method` #21.
