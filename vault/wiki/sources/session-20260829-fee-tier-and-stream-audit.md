---
title: "Session 2026-08-29 — the fee-tier ground truth, a double-overturn, and the stream's n_eff ceiling"
category: sources
status: SETTLED
summary: "[UPD 2026-08-30: the ARM CAME — cut #9 executed 2026-08-30T15:32:36Z, exec_era 9-16ec821e, commit 59bdcf87; every correction below is now SHIPPED and the 'awaiting operator ARM' clause is discharged. See synthesis/comparability-boundaries row 9.] Operator's Kraken app screenshot proved the account is Tier 3 (22/38 bps), not the config's assumed Tier-1 40/80 — a ~2x fee over-statement, the-method #1 recurrence (a struck fee schedule asserting itself as truth). The correction re-derives the entry bar 0.8335 -> 0.6772 but does NOT flip the net sign positive: a walkforward re-run showed the +118bps WF-5 tolerance was a stale n=33 melt-up snapshot that decays to +41bps at completed n=61, so real ~60bps still yields net ~-19bps/trip (UNDETERMINED-leaning-NEGATIVE, COST_BOUND holds at both 120 and 60bps). This overturned an in-session adversarial-review claim that had itself overturned the original 'confidently negative' — a double-overturn, both of Claude's own confident claims. Parallel: a streaming data-quality audit found the corpus is CLEAN (DQS 95/100) but CANNOT yet yield precise per-execution-style probabilities because n_eff collapses (nominal n 12-16x too optimistic); the dominant recoverable structure is market beta, not execution style."
tags: [fee-truth, the-method, cost-bound, effective-n, data-quality, adversarial-verification, double-overturn]
sources: 4
updated: 2026-08-30
---

# Session 2026-08-29 — fee-tier ground truth + stream n_eff ceiling

Primary artifacts (all on `origin/main`):
`docs/quant/2026-08-29_fee_tier_correction_adjudication.md` (+ `scripts/fee_tier_rederive.py`, commit `16ec821e`);
`docs/quant/2026-08-29_stream_data_quality_audit.md` (`965cdce9`);
`docs/quant/2026-08-29_game_theory_adverse_selection.md` (`c1882728`).

## 1. The fee ground truth — the-method #1 recurrence, at full scale

Operator's Kraken app screenshot (2026-08-29 14:58): the account is **Tier 3 =
maker 0.22% / taker 0.38% (22/38 bps)** on $17,482 30-day spot volume. The live
config books **40/80** (assumed Tier-1) — a **~2x over-statement**. This is the
register's #1 recurrence — *"a struck fee schedule asserting itself the
conservative check"* ([[the-method]]) — fired on the cut-#8 fee-truth epoch
itself. The unheeded warnings were already on record: `fee_anatomy`'s BOOKED
median was ~65bps (≈ real 60, not config 120), and **OM-080 n=0** meant 40/80
was never verified against the account. Cross-check: the pre-cut 25/40 was
*closer* to real 22/38 than cut #8's 40/80 — cut #8 moved the config AWAY from
truth while asserting it as venue-true.

> [!warning] **CORRECTED 2026-08-30 (partial-identification audit) — the
> "OM-080 n=0" clause above is FALSE, and was false when the adjudication doc
> asserted it.** OM-080 has fired exactly ONCE: `outputs/audit.jsonl` seq 69754,
> ts 2026-08-29T15:47:07.123Z, XBTUSD **40/80 bps** — 4h40m58s BEFORE the
> adjudication commit `16ec821e` (20:28:05Z). Double-derived (full-range grep
> n=1; `scripts/cost_truth_report.py` `n_records=1`, verdict XV-033 "DANGEROUS:
> configured UNDER measured" vs the shipped 22/38), reproduced by an
> independent verification lane. The emit path requires a signed non-error
> `TradeVolume` response, so credentials existed on the box that day. **[COUNTER-CORRECTION 2026-08-31: OVERTURNED by operator testimony — "I've never put my keys into this bot." A signed non-error `TradeVolume` response is impossible without a valid HMAC (`data/kraken_feed.py:169-183`, re-read 2026-08-31: no stub, no dry-run synthetic, error→None), so the seq-69754 row was written by a DOCTORED-feed harness — a 62-second unredirected fork off the live audit tail (both lineages share parent seq 69742; see repo HANDOFF AUDIT-SEAM-0829). The 40/80 value is planted fixture data in the production audit, not a venue reading; the adjudication doc's original "n=0, no credentials" was RIGHT about production; tier evidence reverts to the operator screenshot alone. Both readings stay on this page per the both-sides rule.]** **Both
> sides:** this does NOT overturn the Tier-3 22/38 ground truth — Kraken may
> return the schedule-top `fee` for an untraded pair, which a Tier-3 account
> would faithfully read as 40/80 — it overturns the COUNT and the [K] tag. The
> honest object is a 2-element identified set until the FEE-3 reopen logs the
> full `TradeVolume` tier context (`minfee`/`maxfee`/`nextfee`/`nextvolume`/
> `tiervolume` + 30-day `volume`, today discarded at `data/kraken_feed.py:415-428`).
> See [[partial-identification]]; docketed as PI-1/FEE-3 in `docs/HANDOFF.md`.

**CURRENCY CALLOUT (both sides, same session):** `CLAUDE.md`'s "Accrual
moratorium — era-5 (cut #8, fee truth)" section asserts 40/80 as "venue-true
Kraken Tier-1." Ground truth contradicts it. The config correction (40/80 ->
22/38) is COHORT-RESETTING — it reverses an operator adjudication (cut #8) and
mints a new era — so the LAW file is NOT edited unilaterally; the contradiction
is filed here and in the adjudication doc, awaiting operator ARM.

> [!success] **[UPD 2026-08-30 — THE ARM CAME AND THE CUT EXECUTED. The
> "awaiting operator ARM" clause above is DISCHARGED, not deleted.]**
> Operator ARM 2026-08-30, scope **"fee correction only"** (`dry_run` STAYS
> true). **Cut #9 minted at the deploy instant `2026-08-30T15:32:36Z`**,
> `exec_era` **`9-16ec821e`** — commit **`59bdcf87`** carried the
> `fee_correction_stage.py --apply` config write AND the era bump in the
> SAME commit (cut #7's late-bump debt still not repeated). Anchor
> `16ec821e` is *this session's own adjudication commit* — the doc named at
> the top of this page is what DEFINES the cut. Everything §1 measured is
> now shipped: 40/80 → **22/38** on pricing and booking, PT break-even floor
> 80 → **38**, label round-trip cost 1.2% → **0.6%**,
> `allow_sub_floor_fees` → true (the 40/80 `KRAKEN_SPOT_FLOOR` tripwire
> STAYS, as the understated-fee guard). §2's re-derived bar
> **0.8335 → 0.6772** was runtime-verified in-binary (startup log
> `fees=22/38bps … p(win) bar=0.677 (derived)`); conviction resumes and
> cut #8's probe-dominated book is UNWOUND. **`CLAUDE.md` now carries an
> era-6 section, so the law-file contradiction this callout raised is
> closed at the source.** What did NOT change: §2's honest sign — net stays
> **UNDETERMINED-leaning-NEGATIVE** at real fees, the median trip clears the
> rake and the fat tail loses, which is an **ALGO-5** problem
> EXPLICITLY EXCLUDED from cut #9. Authoritative row:
> [[synthesis/comparability-boundaries]] **table row 9**; prestige record:
> [[synthesis/progression-bar]] PRESTIGE #2; session record:
> [[sources/session-20260830-audit-wave-and-external-data-atlas]].
> **Era-6 accrual starts at ZERO from 15:32:36Z — nothing on this page's
> era-5/era-4 side may be pooled with it.**

## 2. The double-overturn — both of Claude's confident claims were wrong

A three-step sequence, each step a confident claim, two of them Claude's:
1. **Original (Claude):** "gross ≈ 0, so net = −rake, confidently negative;
   only edge flips the sign; fee reduction only shrinks the loss."
2. **Adversarial-review overturn (Claude, /adversarial-reviewer):** "REFUTED —
   the WF-5 point-estimate breakeven is 118bps, so at real ~60bps the net
   point estimate is POSITIVE; the COST_BOUND verdict was a 2bps artifact of
   pricing at the wrong 120bps."
3. **Walkforward re-run (correction of #2):** the 118bps tolerance was a
   **stale n=33 melt-up snapshot**; reproduced at n=33 exactly, it decays
   monotonically to **+41.3bps by completed n=61**. Real ~60bps EXCEEDS the
   true tolerance -> net point estimate **−18.68bps/trip** (double-derived,
   agree). The pre-registered readout class is **COST_BOUND at BOTH 120 and
   60bps**. The fee error inflated the shortfall MAGNITUDE (−79 -> −19bps), not
   its sign CLASS. Honest sign: **UNDETERMINED-leaning-NEGATIVE** (CI spans
   zero, n_eff 25.83, P(net≤0)≈0.73).

The lesson is the register's, turned on the referee: a confident claim built on
a single snapshot number (118bps) is a hypothesis about the instrument. The
"60 < 118" arithmetic was valid only against the snapshot; the completed-cohort
property is "60 > 41." **Verify the number's provenance and its convergence,
not just its value** — the adversarial reviewer that overturned the original
made the SAME class of error it was invoked to catch.

**What survives:** the fee DEFECT is real; correcting it buys an *honest*
readout (removes the config-manufactured "confidently negative", moves net to
indistinguishable-from-zero) and re-derives the entry bar **0.8335 -> 0.6772**
(conviction resumes at real fees; below the pre-cut 0.690). But median trip
+72.6bps DOES clear 60bps — the shortfall is fat-tail losers, making this an
**ALGO-5 tail-control problem, the opposite lever from the fee fix**. Correcting
fees does not produce a winning strategy; it produces a truthful one.

## 3. The stream's n_eff ceiling — clean data, wrong shape

The streaming data-quality audit (corpus 19,343 rows, snapshot 2026-08-29
20:00:30Z) reframed the corpus as a non-terminating stream whose purpose is
precise per-execution-style probabilities. Finding: **finite-sample DQS 95/100
(genuinely clean** — 0 out-of-bounds, regime one-hot sums to exactly 1.0 on all
rows, refuting this session's earlier "0.000000 = active" mis-probe; `''` is
honest UNKNOWN and UNKNOWN rates FALL over the stream = no feed degradation),
**but the streaming verdict is RED: the stream cannot yet yield precise per-style
probabilities.** Every stratum's n_eff collapses 1-2 orders below nominal
(h432 8,988 -> n_eff 33; a nominal Wilson is optimistic by **12-16x** while
looking right). No non-directional execution style produced a straight,
n_eff-supported positive slope on the LOG scale; the dominant recoverable
structure is **market beta (direction), not execution style** (long +24.8 vs
short −11.2 cumlog, but h432 flips sign by ts-quartile — a melt-up, not an
edge). Non-stationary on three axes (5 label eras; 5 column onsets; market
path). **This is why "precise probabilities" on the [[progression-bar]]'s
infinite corpus is n_eff-BOUND, not row-bound** — the stream grows rows fast
but independent observations slowly. Top remediation (refine-existing): make
n_eff non-optional for every per-style read — the machinery already exists in
`scripts/cohort_eval.py` / `scripts/gate_efficacy_report.py`; a shared n_eff
helper belongs in `ml/corpus.py`.

Related: [[the-method]] · [[progression-bar]] · [[comparability-boundaries]] ·
[[observational-equivalence]] · [[owed-measurements]] (OM-080 arm makes the
tier [K]).
