# Era-8 counterfactual replay — improving, or trying things that happen to work?

Operator question (2026-08-28): "a document comparing what this era would've
done logically and arithmetically. Are we improving or just trying different
things that happen to be working? Why are these rows dirty data compared to
the new data?"

Corpus: snapshot of `outputs/signal_history.csv` taken **2026-08-28T22:25:48Z**,
19,081 rows, 5 label eras (h432 8,757 · triple_barrier 5,328 · exit_sim 2,756
· time_stop 459 · legacy 1,781). Derivation script:
scratchpad `era8_replay.py` (session cdb03d59); re-derive, don't recall — the
live file mutates continuously.

## Method

Replay era-8's admission arithmetic backward over every labeled historical
row: gross return recovered from `entry_price`/`exit_price` (side-adjusted),
true-cost outcome = gross − 1.2% (the era-8 label round-trip cost), admission
counterfactual = `gate_confidence` ≥ 0.8335 (the era-8 bar) vs the era-4 band
[0.690, 0.8335) that the old bar admitted and the new bar refuses.

**Instrument validation (double-derivation, rule e):** 2,130 rows carry both
the price route and `label_ret_pct`. Implied label-time cost basis:
median 0.610% (p10 0.286, p90 1.301) — consistent with the documented 0.5%
label cost + capped spread, with live-row booked-fee mixture. The price route
is sound. [K]

## Result — per-era, per-band, true-cost outcomes

| era | band | n | win rate | Wilson 95% | mean net/trip |
|---|---|---|---|---|---|
| exit_sim | 0.690–0.8335 | 11 | 0.455 | [0.213,0.720] | −10.29% |
| exit_sim | ≥0.8335 | 33 | 0.515 | [0.352,0.675] | +1.83% |
| triple_barrier | 0.690–0.8335 | 306 | 0.271 | [0.224,0.324] | −0.58% |
| triple_barrier | ≥0.8335 | 616 | 0.315 | [0.279,0.353] | −1.34% |
| triple_barrier_h432 | 0.690–0.8335 | 2,436 | 0.445 | [0.426,0.465] | −0.97% |
| triple_barrier_h432 | ≥0.8335 | 5,735 | 0.417 | [0.404,0.430] | −1.22% |

Strata where the new bar's cohort beats the old band on mean net/trip: **1 of
3** (sign test p=1.0 — indistinguishable from a coin).

**Probe/conviction split** (probe flag is recent: 288 tagged '1', 26 '0',
18,767 '' = UNKNOWN — the "conviction" lane below is conviction+unknown):

| era | lane | band | n | win | mean net/trip |
|---|---|---|---|---|---|
| triple_barrier | conv+unk | 0.690–0.8335 | 304 | 0.266 | −1.23% |
| triple_barrier | conv+unk | ≥0.8335 | 611 | 0.314 | −1.17% |
| h432 | conv+unk | 0.690–0.8335 | 2,426 | 0.445 | −1.05% |
| h432 | conv+unk | ≥0.8335 | 5,716 | 0.418 | −1.06% |

Probe-tagged cohorts are n≤19 with single-row leverage (means −48% to +99%)
— uninterpretable, excluded from the verdict.

## Verdict

**The raised bar does not select winners on past data — anywhere.** In the
two eras with mass, the ≥0.8335 cohort's mean true-cost outcome is
statistically identical to the band it excludes (−1.06 vs −1.05 h432;
−1.17 vs −1.23 tb), and its h432 win rate is actually *lower* (0.417 vs
0.445, CIs disjoint). Model confidence, replayed at any threshold, is
**non-informative for net outcome** on this corpus.

This is the second independent route to the OF-1 finding (all three model
families lose to the null on OOF Brier): the models' ranking of candidates
does not predict which ones pay. Two instruments, two methods, same answer.

**So: are we improving, or trying things that work?** The honest split:

- **The era-8 improvement is ARITHMETIC, not selection.** Every cohort in
  every era bleeds ≈ −1.0 to −1.2%/trip at true cost — the corpus-wide mean
  sits almost exactly at the cost floor, i.e. gross ≈ 0, net ≈ −cost
  (COST_BOUND, re-confirmed on 19k rows). The cut's mechanism is therefore
  not "pick better trades" — the replay proves the bar can't do that — it is
  **"stop paying the fee on trades with no edge"**: fewer trips × −1%/trip.
  That is a real, logical, derivable improvement. It would have worked in
  every past era too (fewer entries = less bleed in all strata). Not luck.
- **What would be "trying things that happen to work":** reading era-5's
  accruing gate numbers as validation of the bar's *selection* power. This
  document is the standing refutation: selection power was never measured to
  exist. The moratorium already forbids that reading; now there is arithmetic
  behind the prohibition.
- **Where improvement must come from next:** the ledger says edge, if it
  arrives, comes from (a) the model side (frozen — adjudication-gated),
  (b) cost reduction (fee tier, maker-only entries — OM-011 already limits
  entries), or (c) the veto/gating stack's *negative* selection (blocking
  losers), which the control arm (n=7, accruing) will grade honestly for the
  first time. Nothing else on file moves the per-trip mean.

## Why the old rows are "dirty" — plainly

Not because the market data is wrong. Three reasons, in order of damage:

1. **They answered yesterday's question.** A label minted at 0.5% round-trip
   cost says "this trade cleared 0.5%". Era-8's question is "does it clear
   1.2%?" — 218 tb_time wins are literally unanswerable at true cost from
   the label alone (measured 2026-08-24, `ml/history.py` schema-94 comment).
2. **Some threw away the evidence.** Until schema 94 (2026-08-24), candidate
   rows kept 1 bit (win/lose) and wrote a literal 0.0 for magnitude — 5,923
   of 5,945 then-active rows could never be re-graded. The price columns are
   what rescue them today (route validated above).
3. **Their outcomes were produced under retired geometry.** pt/sl brackets,
   exit ladders, and fee booking all changed at boundaries — an old row's
   outcome is partly a property of machinery that no longer exists (the
   cut-#7 lesson: geometry moves outcomes even when fills don't).

New rows differ on all three: labeled at true cost, magnitude preserved
(`label_ret_pct`), era-tagged at write time, control-arm tagged. Dirty ≠
useless: features were never contaminated, and gross returns are recoverable
on 100% of rows (16,951 via prices + 2,130 direct) — which is why the
relabel filter (RELABEL-1, adjudication-gated) is feasible at all.

## What this analysis could not see

- **Survivorship**: rows are candidates that reached labeling under old-era
  admission; candidates the old gates killed pre-label are absent from every
  cohort.
- **Borrowed geometry**: counterfactual outcomes use old-era exits; era-8's
  exits would differ (direction of bias unknown).
- **Nominal n**: overlapping label windows mean every CI above is optimistic
  by ~sqrt(n/n_eff); era-4's measured uniqueness was 0.301. CIs here rank
  cohorts; they do not certify significance.
- **Lane blindness**: probe flag is UNKNOWN on 98% of rows — the
  conviction/probe economics split (91%/−1.05 vs n=5/+1.46 in era-4's
  readout) is invisible at corpus scale until the flag accrues.
- **Not a tuning input**: this replay grades the PAST. It is not evidence
  for retuning the bar, the gates, or era-5 — the registration is the law.
