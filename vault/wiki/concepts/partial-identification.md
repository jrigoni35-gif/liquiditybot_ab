---
title: "Partial Identification (report the identified set; a point estimate transfers the uncertainty to a decision nobody signed for)"
category: concept
status: SETTLED
summary: "The Manski lens, named as the general form of an instinct this vault already applied piecewise: when the evidence pins a parameter only to a SET, reporting a point does not remove the uncertainty — it moves it downstream into a decision (a veto, a ticket size, a verdict) where nobody signs for it. Law of Decreasing Credibility: credibility falls as assumptions strengthen, so the honest deliverable is a LADDER (assumption-free bounds -> progressively stronger assumptions -> point), never one number. Founding measurement 2026-08-30/31: the fee tier is a 2-element set {40/80 [K, the ONE OM-080 venue reading, audit seq 69754], 22/38 [I, operator app screenshot]} making the derived entry bar a set [0.6772, 0.8335] reported everywhere as a point; the deployed calibrator's ceiling 0.6446 sits below every element of that set (0 of 21,047 corpus rows clear — mutation-verified, not a dead scan); the exploration ticket's identified set spans $0.00-$153.14 jointly (rung-3: $50.44-$113.51) against a shipped point of $81.97; and the shipped point is the minimax-regret action at NO rung of the ladder. Same instinct as effective-n, PBO-on-the-deployed-rule, DSR trial deflation, and the CONFOUNDED_BASELINE refusal — this page names what they share."
tags: [identification, manski, uncertainty, effective-n, fee-truth, decision-theory, defect-class]
sources: 1
updated: 2026-08-31
---

# Partial Identification — the set, the ladder, and where the point hides the risk

## Definition

A parameter is **point-identified** when the data plus the maintained assumptions
pin it to one value; it is **partially identified** when they pin it only to a
**set**. Reporting a point where the evidence supports a set does not remove the
uncertainty — it **transfers** it into whatever decision consumes the number,
where it is invisible and unsigned. The honest object is the **identified set**;
the honest deliverable is a **ladder** (Manski's Law of Decreasing Credibility:
credibility falls as assumptions strengthen), from assumption-free bounds down
to the point, each rung naming what it buys and what it assumes.

The operational rule this page adds to [[the-method]]'s stage 7: **when the
identified set straddles a decision boundary, the DECISION is unidentified** —
the correct output is the refusal-with-reasons that
`scripts/gate_efficacy_report.py` already renders (CONFOUNDED_BASELINE /
PARTIAL_OVERLAP, see [[label-era]]), not the point's side of the bar.

## This vault already had the instinct — this page names its general form

Prior art, confirmed by the 2026-08-30 audit, none of it novel to this page:

- **Effective n** ([[average-uniqueness-and-ess]]): `ml/corpus.py:200-259`
  `effective_n`/`wilson_on_neff`; applied by `scripts/gate_truth_report.py`
  (since 2026-07-29) and `scripts/cohort_eval.py` (since 2026-08-15). Nominal-n
  SE is a point pretending; n_eff widens it to the defensible interval.
- **PBO on the DEPLOYED rule, never argmax** ([[pbo-and-cscv]]), and **DSR
  deflated by trial count** ([[overfit-battery]], `scripts/overfit_check.py`):
  both refuse the flattering point the un-deflated statistic offers.
- **The verdict refusal**: `scripts/gate_efficacy_report.py:184-243` refuses to
  render selective/anti-selective under CONFOUNDED_BASELINE / PARTIAL_OVERLAP —
  the template for "the set straddles the bar, so no verdict".
- **POWER-1** (`docs/HANDOFF.md`, MinTRL/PSR, tracked in [[owed-measurements]]):
  "62 trades at configured fees, 1,603 or INFINITE at true T1" — already a
  partial-identification statement over fee worlds.
- **LS-2** (`docs/HANDOFF.md`): Bayesian uncertainty-aware sizing,
  spec-on-paper — the sizing-side answer. The audit CONFIRMS it and prices it;
  it does not rebuild it.
- The single place an interval already **binds a decision**: `ml/monitor.py:271-272`
  — `wilson_ucb` consumed by `hit_deficit` (with the documented 2026-08-05
  wrong-bound fix). One consumer, out of every interval the system computes.

## Founding measurement — the 2026-08-30/31 point-vs-set audit (two lanes, verified)

All runs against the live repo, document-only (era-6 moratorium respected;
runner PID 7692 untouched; `system.dry_run=true` throughout). Lane A runs
2026-08-31T00:38-00:46Z; independent verification lane 01:08-01:15Z reproduced
every load-bearing number, most to the cent; minimax-regret computed
2026-08-31T02:23:13Z (`.venv` numpy, scratchpad `minimax_regret.py` — closed
form recorded here, re-derive rather than cite the dollars).

**F1 — the fee tier is a SET and the record was misread as empty.**
`fee_tier ∈ {T1 40/80 [K — venue API via OM-080, `outputs/audit.jsonl` seq
69754, ts 2026-08-29T15:47:07.123Z, hash-chained, re-rendered by
`scripts/cost_truth_report.py` as XV-033 "DANGEROUS: configured UNDER
measured"], T3 22/38 [I — operator Kraken-app screenshot 2026-08-29, not
reproducible from the repo]}`. Cut #9 shipped 22/38; the decision record
(`docs/quant/2026-08-29_fee_tier_correction_adjudication.md:84-90`) asserts
`[K] OM-080 n=0 — never ran, no credentials`. **Both clauses are false, and
were false AT AUTHORSHIP**: the OM-080 record predates the adjudication commit
`16ec821e` (2026-08-29T20:28:05Z) by 4h40m58s, and the emit path
(`execution/order_manager.py:807-829` → `data/kraken_feed.py:406-429`) requires
a signed non-error `TradeVolume` response — so credentials existed on the box
that day. Honest deflation, both sides: the venue reading is ONE reading of ONE
pair (XBTUSD), and if Kraken returns the schedule-top `fee` for an untraded
pair, a Tier-3 account would faithfully read 40/80 — the set is UNRESOLVED, not
resolved in 40/80's favor. The cheap collapse exists and is discarded at the
boundary: `data/kraken_feed.py:415-428` keeps only `fee`, dropping
`minfee`/`maxfee`/`nextfee`/`nextvolume`/`tiervolume` — exactly the fields that
distinguish "account rate" from "schedule top". Consequence: the derived entry
bar (`risk/position_sizer.py:189-195`) is a set **[0.6772, 0.8335]** (width
0.1563) over the real Kraken candidates, reported everywhere as the point
0.6772.

**F2 — the model path is closed at every element of the set, invisibly.**
Deployed champion `1ee3ae68c0df` over all 21,047 corpus rows: raw logistic
range [0.0196, 0.9832] but the isotonic calibrator collapses it to
**[0.3992, 0.6446]**; post-shrink live ceiling (L1, shrinkage 0.5250)
**0.5687**. Ceiling < bar at every fee world → **0 of 21,047 rows clear**.
Mutation-verified (verification lane, 01:15:47Z): identity calibrator → 1,956
rows clear (9.3%) — the scan is live, the zero is real, and **the calibrator,
not the raw model, closes the path**. Recurrence, not discovery:
`config.json`'s `_label_max_bars_migration_doc` records the identical shape at
an earlier geometry (ceiling 0.2164 vs bar 0.63). Every live entry is therefore
a synthetic-p probe (exploration 0.85 / aggressive 0.72) — what the era-6
readout reads is the probe lane. And the veto that closes the path leaves no
record: `main.py:4152-4160` logs non-exploration sizer vetoes at DEBUG,
`system.log_level` is INFO, zero DEBUG lines persist, and a 70,409-line
full-range `audit.jsonl` scan holds **0** SZ-023/SZ-030 events.

**F3 — the ticket ladder and the minimax-regret result.** Exploration ticket
(p=0.85, equity $795.51, `kelly_mult` 0.70), driven through the REAL
`PositionSizer.size()`, shipped point **$81.97**:

| rung | maintained assumptions | p-object | ticket set | minimax-regret ticket |
|---|---|---|---|---|
| 0 | model range ∪ realized rate on n_eff=2.46 | [0.066, 0.837] | $0 – $153.14 | **$26.30** |
| 1 | + trades independent (nominal n=24 Wilson) | [0.2116, 0.5729] | — (all below every bar) | **$0.00** |
| 2 | + live ECE 0.1648 transports onto p | [0.685, 1.000] | $0.00 – $153.14 | **$105.02** |
| 3 | + OOF ECE 0.06647 instead, shipped tier | [0.784, 0.917] | $50.44 – $113.51 | **$153.14** ($121.21 joint-tier) |
| 4 | + p_win exact ← SHIPPED | 0.85 | $81.97 | $81.97 by construction |

The shipped $81.97 is the minimax-regret action at **no rung**; under the
realized-data rung its worst-case regret is 0.0814 log-growth/trip. The two
measured calibration errors disagree 2.48× (`ml.retrain_calib_gap` 0.06647 OOF
vs `monitor.calibration_gap` 0.1648 live, `outputs/status.json` read
00:38:47Z), the sign is the dangerous one (avg_p 0.470 vs hit_rate 0.375 —
over-promising), and the live window's n_eff is **2.46** (Wilson [0.066,
0.837]) — so the L1 governor state itself is a verdict rendered on ~2.5
independent observations. **No rung carries a point-credible number; the honest
statement is the ladder itself.**

**F4 — uncertainty computed, then discarded.** `ml/monitor.py:259/291/340`
`lcb`: computed, returned, consumed only by a log string. `:797` `hit_rate_lcb`:
Grafana display only. All model uncertainty reaches sizing as the 3-valued
`kelly_mult ∈ {1.0, 0.7, 0.40}` applied AFTER the p-bar veto and AFTER `f_star`
— the interval can shrink the ticket but can never move admission. Ensemble
member spread (`ml/models.py`, k=3/k=4 means) is averaged away at source
(latent today — deployed champion is `logistic`).

## Contradiction callouts (both sides, same session)

> [!warning] **This page contradicts the "OM-080 n=0" clause** carried by
> `docs/quant/2026-08-29_fee_tier_correction_adjudication.md:84-90` [K-tagged
> there], by [[session-20260829-fee-tier-and-stream-audit]] §1, and by
> HANDOFF's POWER-2 row ("OM-080 n_records=0", true when written 2026-08-22,
> inherited uncorrected). Measured n=1, double-derived (full-range grep of
> `outputs/audit.jsonl` = 1; `scripts/cost_truth_report.py` `n_records=1`),
> reproduced independently by the verification lane. The mirror callout is
> filed on the source page; the repo-side correction is docketed (PI-1), not
> applied — the adjudication record is operator-owned. **What does NOT change:**
> the 22/38 ground truth may still be right; the correction is to the COUNT and
> to the [K] tag, not (yet) to the tier.

> [!warning] **Held against this page's own interest:** the audit's joint
> $0.00–$153.14 headline is arithmetic through the real sizer, but its
> endpoints transport ECE onto the exploration constant p=0.85 — a config
> constant, not a model output — and p+ECE=1.0 exceeds anything the deployed
> system can emit (calibrated ceiling 0.6446). ECE is a bin-weighted mean, not
> a bound. Prefer the rung-1 and rung-3 statements. The verification lane
> flagged the headline as "overstated at both endpoints" and named three
> secondary overstatements; its transcript reached this filing TRUNCATED
> mid-sentence, so only the headline one is fully recorded here.

## What the audit could not see

No Kraken call was possible (no credentials in config or environment, checked
00:40Z) — the fee set stays a set. The schedule-top-for-untraded-pairs
hypothesis is untested. `events.jsonl` covered an 83-minute tail — no onset
claims. n_eff transport of corpus uniqueness 0.1026 onto the 24-trade window is
[I]; `scripts/cohort_eval.py:484-533` `cohort_effective_n` is the right
instrument and was not run (owed). Whether PID 7692 currently holds credentials
was not established — only that a predecessor process did on 2026-08-29.
Minimax-regret uses per-trip log growth with the sizer-reachable action range
[0, $153.14]; a different utility moves the dollars, not the ordering.

Related: [[the-method]] · [[average-uniqueness-and-ess]] · [[pbo-and-cscv]] ·
[[overfit-battery]] · [[label-era]] · [[owed-measurements]] ·
[[observational-equivalence]] · [[zero-is-not-a-reading]] ·
[[exact-or-refuse]] · [[cost-truth]]
