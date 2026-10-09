---
title: "The Institutional Review Verdict (2026-08-07) — 5 Master Judges, 6 Areas, Unanimous APPROVED_WITH_CONDITIONS"
category: source
summary: "Final outcome of the multi-agent institutional review (task wq55239mp): ground evidence F1-F6, four institutional lenses (Citadel/Jane Street/Virtu/Two Sigma), and the week's decision record D1-D6 all went 5-0 APPROVED_WITH_CONDITIONS — zero rejections, zero unconditional approvals. Key adjudications: churn gross was -13.37 not 0.00 (149 paired laps, ~95.7% fees); TWO churn mechanisms confirmed (12 residual warm-correlation laps outlived the pair fix until cf454d5e); the 25/40 fee constant matches NO row of Kraken's current schedule but the naive fix is a disguised label-geometry retune sequenced behind the h432 verdict; cf454d5e's circulated record is false on four verified counts; the conviction funnel's 0/0 is honest for a seam that 1,100+ exploration admissions bypass; the DRY_RUN fill-at-limit RNG manufactures a phantom quoter edge (markout is sim-conditioned); and one item left unadjudicated — the era realized ledger reads 6/11 net winners against the recent-30 still-losing story. Plus this filing's own ledger verification: the two filed 147-lap hedge incidents are ONE ledger event under two clock conventions."
tags: [session, adjudication, judges, lenses, fees, churn, dashboards, markout, governance, paper-mode]
sources: 1
source_path: none — session work product; structured results in task wq55239mp.output (ground/lenses/judges round1+finals+tally)
source_date: 2026-08
authors: [claude, five-master-judge-panel]
ingested: 2026-08-07
updated: 2026-08-07
---

# The Institutional Review Verdict (2026-08-07)

## Provenance and verdict

Completion of the review whose ground phase was filed as
[[sources/session-20260807-pnl-reconciliation]]. Structure: 3 read-only ground reports (F1–F6
P&L reconciliation, perf-ring adjudication, zero/No-data panel classification) → 4 institutional
lens reviews (Citadel execution-microstructure, Jane Street screens-vs-books, Virtu
ops/alerting, Two Sigma learning-loop) → **5 master judges, two rounds** (independent round-1
verdicts with adversarial objections, then finals after deliberation). Every judge was
instructed to refute; several re-executed measurements (leg pairing, git archaeology, live
guard reproduction, parent-blob test runs).

**Final tally — all six areas, 5-0 APPROVED_WITH_CONDITIONS:** GROUND-EVIDENCE ·
CITADEL-LENS · JANESTREET-LENS · VIRTU-LENS · TWOSIGMA-LENS · DECISIONS-D1-D6. **Zero
REJECTED. Zero unconditional APPROVED** — round-1 outright approvals and one FATAL grading both
converged to conditions under deliberation. The shape of the outcome: **the ledgers and the
engineering survived adversarial audit; the records, labels, and instruments around them
accrued a defect list that GREW under scrutiny.**

---

## A. Corrections to the ground record (adjudicated)

1. **Churn gross was −13.37, not 0.00.** F2's "gross price P&L 0.00 / all fees" was inferred,
   not computed. A judge paired every churn `position_id` (00:40–02:30Z envelope): **149 fully
   closed laps, 0 unmatched, gross −13.37 USD, fees 301.31** — the churn was **~95.7% fees and
   ~4.3% spread/slippage crossing cost** (mean slip 1.87 bps over 296 fills). Cross-check:
   all-time gross = realized_total + all-time exit fees = −208.22 + 192.84 = −15.37.
   On ~$75k of churn notional that is **≈ −1.8 bps — i.e. the ADA markout cell (−2.6 bps@5s)
   was calibrating the simulator's taker sweep cost, not measuring entry quality.**
2. **Canonical churn window adopted:** **01:09:00–01:34:59Z = 294 fills = 147 laps.** The 290
   (tight epoch), 296 (00:50–02:00Z envelope), and 149-lap (00:40–02:30Z pairing) counts are
   windowing variants and must be mapped to the canonical window when cited.
3. **The fee ledger has an undeclared $6.24 gap.** `fees_total` 382.28 vs the fill ledger's
   376.04; the quarantined 08-01/02 fills carry **$7.21** (the likely cause), leaving
   **−$0.97 residual open**. Condition: close or declare it.
4. **GR2's verdict-word "organic" overreached.** "NOT an incident artifact" stands (the ring
   contains zero churn entries — that adjudication is untouched); "organic" as a *provenance*
   claim does not, because the 07-22/23 cluster (66.5% of the ring) is UNVERIFIED by GR2's own
   item 6. Corrected reading: **"not an incident artifact; provenance unadjudicated"** (owed
   36(c)).
5. **F1's divergence taxonomy misses a third axis.** Beyond window-truncation and
   hedge-exclusion, the perf ring's per-trade nets **include pro-rata entry fees**
   (`main.py:1955-1971`) while the realized counters do not (`main.py:1988`) — a
   **fee-basis** axis between the −56.91 tile and `realized_pnl_total`.

## B. TWO churn mechanisms confirmed (Judge 3's dissent, corroborated by Judge 4)

The single-mechanism historiography ("#1 was the pair mismatch, #2 was the cold flap, each
fixed by its own commit") is **refuted by the ledger**:

- **Mechanism 1 — wrong-pair + cold-0.0 sentinel** set the pathological ~10s lap **rate** of
  the main 147-lap event, which ran **entirely on pre-`5c111962` code**: D3 was committed
  **01:53:17Z 08-07 — nineteen minutes AFTER the churn ended** (01:34:19Z) — and deployed
  **02:08:09Z** (`auto_update.log`, verified at filing).
- **Mechanism 2 — open-on-delta vs unwind-on-correlation, no shared deadband** — **outlived
  the pair fix**: **12 residual ADA hedge laps ran 01:56Z–11:35Z** (hour buckets 02h:4, 05h:2,
  06h:4, 11h:1) with unwinds citing **correlation 0.34–0.55 below floor — warm, genuine
  readings, not the 0.00 artifact** — and only stopped inside `cf454d5e`'s
  cooldown/latch regime (deployed 19:04:16Z; last hedge fill 11:35:31Z, hours before, so
  "stopped by D4" is consistent-with, not proven-by). The opener judged the **delta cap**; the
  unwinder judged a **correlation floor**; nothing required the variable that opens to be the
  variable that closes. The exposure window was **~17 hours longer than the headline churn.**
  (Deploy nuance, verified: the 02:01Z laps predate D3's 02:08Z deploy; laps from 02:24Z on
  ran on deployed fixed-pair code.)

> ⚠️ **And beneath both: the corpus double-filed ONE event as two incidents.** This is this
> filing session's own measurement, building on a judge's record note ("the measured 08-06
> thrash is absent from this book's ledger — all 159 hedge fills are 08-07"). Verified at
> filing: `fills.csv` holds **159 lifetime hedge fills, every one on 2026-08-07 UTC**;
> `equity.csv` reads **4,933.68 at 08-06 23:59:50Z** — impossible if a −$303 churn had closed
> at "20:34 on 08-06"; and the two filed windows are the **same wall-clock window under two
> clocks**: 20:09:40–20:34:19 **local (UTC−5)** ≡ 01:09:40–01:34:19**Z**. The
> [[sources/session-20260806-hedge-thrash]] filing rendered the epochs in local time; the
> [[sources/session-20260807-hedge-churn-guards]] filing rendered the same epochs in UTC and
> called it a second incident "hours after #1's fix." **There was one 147-lap event
> (−$297, canonical window above) plus the 12-lap residual tail — not two 147-lap events.**
> Both mechanisms were live *during* the one event (pre-D3 code carried the wrong pair; the
> ~01:00Z restarts made the estimator cold), which is why both fixes were real fixes.
> Supersession banners placed on both source pages; register entry filed.

## C. The fee constants are falsified — and the fix is sequenced (the panel's sharpest ruling)

**Triple-confirmed by three independent fetches:** the modeled **25/40 bps maker/taker**
(`config.json:326-327, 354-355`; premise *"25/40 is the public spot floor"*) matches **no row
of Kraken's current schedule** — Tier 1 ($0+) **40/80**, Tier 2 ($2.5k+) 30/60, Tier 3 ($10k+)
22/38, Tier 5 ($50k+) **~15/30**, tiers keyed on best-of 30-day volume OR assets on platform.
The wiki's standing "Kraken's published 16/26" is **stale** ([[concepts/cost-truth]]
superseded). The bot's 30-day notional **$97,015** looks like Tier-5 territory — **but 77.6%
of that anchor is churn flow**, so the honest go-live premise is a fresh $5k account at
**Tier 1 (40/80): real fee drag ~1.6–2x the modeled constant, in the config's own "dangerous
direction" — the −384.67 drawdown is a FLOOR.** The one mechanism built to catch this,
`fee_recon` (OM-080), **fails silent in DRY_RUN without keys** — the entire paper campaign
runs on an unverified fee constant.

**HOWEVER — the panel ruled the naive fix is a disguised label-geometry retune.** Verified
coupling (`ml/labeling.py:45-52`): the fee constant feeds the labeler's **cost floor**
(`sigma_eff = max(sigma_bar, pt_cost_mult × cost/pt_mult)`), the floor **binds 100% of
brackets**, and **both the candidate labeler and the live bracket-exit engine call it**.
Changing the constant mid-hold **changes the label definition** — a geometry retune that
breaches the very 432-hold the house ordered. Judge 1's FATAL grading was downgraded to
MATERIAL on exactly this: the omission is an epistemic defect, and the remedy is **SEQUENCED
BEHIND the h432 verdict** (or a consciously minted era boundary). **Do not change the fee
constants now.** Do now (analysis-only, condition 3): stamp the fee assumption on the P&L
panels, give `fee_recon` a read-only-keys DRY_RUN path, and run the battery at 40/80 and
~15/30 to see which admits flip — deploy nothing until the era boundary.

## D. `cf454d5e`'s circulated record is false on four verified counts (owed follow-up)

The commit message itself is honest ("byte-identical behavior for restored snapshots"); the
**circulated record** — HANDOFF resolution notice and the incident filing's summary — is not:

1. **"Estimator sample counts ride the snapshot" — never shipped.** Triple-verified by
   independent greps: `regime/correlation.py` has no `to_dict`/`from_dict`;
   `core/persistence.py`'s hedger section (`:501-505`/`:891-894`) carries only guard clocks;
   `CorrelationEngine` is rebuilt at boot (`main.py:644`). (The wiki's own §6.1 correction is
   hereby panel-confirmed.)
2. **The guards gate TRIMS, contradicting their own "OPENS only, exits untouched" comment.**
   The warm check (`hedging.py:239-252`) and `_open_blocked` (`:253-256`) sit **above** the
   trim block (`:259-291`), so a cold estimator or an active cooldown suppresses the
   fee-cheap, delta-**reducing** partial exit that `main.py:2634-2646` itself classifies
   *"risk REDUCTION, never gated."* Reproduced live by a judge (cold → no trim; warm inside
   cooldown → no trim; warm outside → trim) and **re-verified at filing in the shipped
   source**. Fail-safe direction, but it contradicts the deadlock discipline's own taxonomy
   and arguably invariant 5 (a trim is a partial exit via `_submit_exit`).
3. **"12 ticks reachable well inside the 0.5h median uptime" — false at the floor.** Samples
   accrue from candle-refresh closes (`candle_refresh_sec = 150`, no `bar_ts` at
   `main.py:4041`): **12 × 150s = 30 min = exactly the median uptime.** Combined with (1),
   **roughly half of process lives never reach warm** — post-churn hedging (and, per (2),
   trimming) is structurally unavailable for an unquantified fraction of wall time.
4. **The deploy-gap timeline.** "Incident #2, hours after #1's fix" is false — see §B: the
   churn ran on pre-D3 code, D3 landed after it ended, and the residual laps ran ~17h until D4.
   Panel condition alongside: an **interim-containment rule** is owed — `hedging.enabled` was
   a one-line config toggle nobody flipped while a measured active control-loop failure had
   its fix in flight.

## E. The admission funnel's 0/0, explained — honest zero, hollow coverage

GR3[5]'s "no entry attempt has reached the conviction seam" is **refuted as stated**: the
conviction counters are wired and honestly zero **for a seam most traffic never touches**.
Judge audit-scans since boot: **ML-070 ≈1,146–1,166** ("conviction-scaled full-size
exploration" — a code literally named for conviction that never touches the conviction seam)
+ **39 ML-072** + 1,202 SZ-051, with **zero CV-\* rows**. The exploration admission path — the
dominant traffic — **bypasses the funnel entirely**. Condition: annotate the panel; adjudicate
whether exploration admissions should be counted (instrument-coverage decision, owed 37).

## F. The DRY_RUN "quoter edge" is simulator physics — all markout is sim-conditioned

Citadel's one bright spot (ETH +14.8 / BTC +11.2 bps maker markout) was killed in
deliberation, mechanism verified at `execution/order_manager.py:1237-1260`: **passive fills
are granted on an unconditioned RNG draw at the limit price — no trade-through condition — so
the resting distance is harvested as phantom favorable markout by construction.** Smoking gun:
the **flat-across-horizon signature** (BTC +11.21/+11.26/+11.28 @5/30/60s). Real maker fills
are conditioned on trade-through, which **is** the adverse selection the sim omits. The same
artifact symmetrically invalidates ARB's −14.5/−18.2 "clean red flag" (~5 independent events
with duplicates). **No markout conclusion from this book is venue truth**
([[concepts/paper-real-boundary]]).

## G. UNADJUDICATED — the panel's one unfinished item (do not let either number headline alone)

**`gate_stats` real_tot for `triple_barrier_h432` reads 6/11 net winners (54.5%)** — on a
**fully-net fee basis** (`main.py:1955-1971`) — while every lens and two judges repeated the
"recent-30: wr 20%, PF 0.18, net −10.74, still losing" story. **Both cannot headline the same
book.** The 6/11 is the era-keyed realized ledger of the h432 cohort — the very instrument
built to adjudicate label-vs-realized truth. No judge adjudicated the tension (different
populations? fee basis? denominator?). Filed as an UNRESOLVED contradiction and owed
adjudication: **display both, denominators declared, then reconcile.**

---

## The four lens verdicts, one line each (all 5-0 conditional)

- **Citadel (execution-microstructure):** fee-truth is the finding that survived everything —
  25/40 matches no Kraken row and the reconciler built to catch it is dead in DRY_RUN; the
  book's entire drawdown is fees (−384.67 vs `fees_total` 382.28) with the entry/hedge-leg
  half booked into **no** P&L series; hedges clear authority gates but **no EV/cost gate**;
  exits are 96.4% taker with **zero markout measurement of exit flow**; `maker_fill_p0` 0.45
  is 2–9x stale against the repo's own 0.048 calibration. (Its quoter-edge and $72-recoverable
  supporting numbers were stripped in deliberation — §F.)
- **Jane Street (screens vs books):** *the books are right and the screens lie* — an invisible
  **$157.84/day cash channel** no panel can explain; the all-time tile mislabeled on
  (now three) axes; a fixed bug's pre-fix 100% still rendering from a dead series; the
  two-paths class policed by comments, not construction (strengthened by §B's residual laps);
  which rolling windows survive a restart is an accident, not a policy; the ring is 66.5% one
  unadjudicated cluster; RTT 0ms is the worst possible sentinel. (Its "computed once"
  citation for the exposure helper failed verification — `_exposure_by_asset` is called at
  both `hedging.py:184` and `:230` — costing it its unconditional approval.)
- **Virtu (ops/alerting):** **the alert path exists end-to-end and is switched off**
  (`core/alerts.py` complete, `enabled: false`, webhook empty; zero money-side rules); the
  breaker that would have broken the loop was **sized to miss** (churn peak ≈3.9% — a judge's
  peak-semantics recount −4.65% — vs the 6%/15min trip; no page tier); **VITALS measures the
  process, not the book** (every tile truthfully green during a $12.7/min bleed); FW-070 is a
  silent breaker; the restart cadence shreds counter state with no boot accounting; the
  30/min rate limiter is scoped to fat fingers while the churn was a 12/min metronome. Its
  derived alerting spec (P&L-velocity page ~1%/15m, fee-velocity page $10/15m, unwind-rate,
  fill-rate, freshness, restart/version rules) is filed to owed item 37.
- **Two Sigma (learning loop):** **the labeler computes `ret_pct` and throws it away at the
  persistence seam** (`ml/history.py:2389` persists label, `0.0`, "candidate" — ~97% of the
  corpus is sign-only; no model can learn a payoff distribution that was never recorded);
  the champion is **indistinguishable from no model** (Brier 0.2478 ≈ coin-flip vs
  constant-baseline ≈0.164 — with Judge 4's population-splice caveat: deploy-time badge vs
  cross-era pool); the learned gate weights carry **~zero bits** (all ≈0.98 = the Wilson
  small-sample penalty, not discrimination; plus a verified union bug leaking the era name as
  a phantom exported gate weight, `signal_gates.py:454`); the evidence runway to the next
  ladder rung is **~3 months at the current live-clean rate** and no panel says so; and the
  new era is **literally unnameable** in the era panels (`gc_pusher.py:100-101` clamps
  `triple_barrier_h432` to era="other").

## What genuinely passed muster (the panel's positive record, kept)

The evidence-gated model ladder; era lineage done right (label-derived eras, immutable corpus,
load-time views); the reward-misspecification catch and era-keyed realized ledger; the append
gate and reason-code registry as defect-class kills; invariant-5 discipline applied uniformly
under incident pressure; the test-gated self-deploy worktree; the telemetry dead-man doctrine;
the deliberately honest fill-probability cut (0.45 → 0.048) *against* the track record; D5's
genuinely-red-first convergence test (re-executed by a judge against the parent blob: 4 RED);
and the ledgers reconciling **to the cent** under adversarial audit. The panel's summary
sentence, worth keeping verbatim: *"unusually good bones for a $5k single-box bot — and a
completely dark nervous system."*

## Conditions register (consolidated — filed as owed item 37, none are facts yet)

1. Correct the records (§A/§D — done in this filing for the wiki's copies).
2. Close or declare the $6.24 fee-ledger residual.
3. Open the **sequenced fee-economics decision** (stamp panels + `fee_recon` DRY_RUN path +
   40/80 and 15/30 analysis batteries now; constant change only at the h432 verdict/era mint).
4. Adopt a written **interim-containment rule** (measured active control-loop failure ⇒
   config-disable while the fix is in flight).
5. Adjudicate **6/11 vs recent-30** (§G) with denominators displayed.
6. Persist estimator samples per the HANDOFF's own rule; surface FW-070; emit warmth/uptime
   telemetry (extends owed 35).
7. The Virtu alerting spec; the Two Sigma seam items (`ret_pct` column, ESS export,
   evidence-runway panel, `_ERA_KNOWN` line, bracket-window persistence via the markout
   template); the exploration-path funnel-coverage decision.

## Also this session (logged, not adjudicated content)

**pytest-xdist adopted after its evidence gate:** parallel battery `-n 8` on the 5600X —
**3423 passed / 1 skipped in 413s vs 623s serial control, identical results**; second
confirming run pending before the serial default changes anywhere that matters.

## Related
[[sources/session-20260807-pnl-reconciliation]] ·
[[sources/session-20260807-hedge-churn-guards]] · [[sources/session-20260806-hedge-thrash]] ·
[[concepts/paper-real-boundary]] · [[concepts/cost-truth]] ·
[[concepts/two-paths-one-quantity]] · [[concepts/zero-is-not-a-reading]] ·
[[concepts/adoption-is-not-enforcement]] · [[concepts/deadlock-discipline]] ·
[[concepts/payoff-asymmetry]] · [[concepts/tautological-instrument]] ·
[[synthesis/the-money-path-thesis]] · [[synthesis/risk-posture-doctrine]] ·
[[synthesis/governance-doctrine]] · [[synthesis/open-contradictions-register]] ·
[[synthesis/owed-measurements]] · [[synthesis/documentation-drift-register]] ·
[[entities/liquiditybot]] · [[entities/kraken]] · [[entities/pretrade-gate]] ·
[[entities/reason-code-registry]] · [[comparisons/horizon-96-vs-24-bars]]
