# Edge-hunter mirror — operator report (2026-09-01)

**Objective (operator, verbatim intent):** know where the money comes from; costs from
fills not schedules; fill the empty offensive half; condense the 64-feature / 1-bit
model to the most concentrated solution; years of data across many assets against 50
loadable days; inspect our own human/LLM errors; do not assume; study manipulation
for detection only.

**Classification:** everything shipped here is SAFE-class (measurement, data plane,
tests, docs). Items 2 and 3 touch the decision path and are delivered as PROPOSALS
for the ALGO-5/GB-1 adjudication, not code. `dry_run` untouched. No keys. No
withdrawals. Manipulation: nothing built.

Every number below is as-of its read time and names its re-derivation. Nothing in
this file is a permanent claim; the HANDOFF EDGE-HUNTER MIRROR block and the vault
source page `sources/session-20260901-edge-hunter-mirror` carry the citations.

---

## 0. The one correction that reframes everything

The champion model is scored on **23.73 days** of rows (12,066 rows,
2026-08-09T01:00Z → 09-01T18:35Z after era exclusion and the `label_era` filter),
not the 50.1 d in commit `1d751e22`'s subject (that was the raw file span) and not
the project's age (months; the operator's correction stands).

Consequence: at true zero edge the standard error of an annualized Sharpe over
0.065 yr is ≈ 3.9. **No Sharpe this corpus can produce is distinguishable from zero.**
MinBTL at even N=2 trials (99 d) exceeds both spans. Every "edge" or "no edge"
statement below is therefore a statement about the INSTRUMENT and the SAMPLE, never
about the market. That is the honest frame for a pro edge-hunter with this much
data: the job right now is building instruments and accumulating tape, not
concluding.

Re-derive: `python scripts/champion_skill_report.py --json` → `corpus_span_days`.

## 1. Costs from fills, not schedules — DONE (measured)

| what | result | re-derive |
|---|---|---|
| Markout decomposition, 519 scored entry fills | arrival→fill **−15.1 bps** (maker −17.6, taker +1.0); fill→1h **−4.1 bps (−0.7 SE)**; fill→4h −2.8; time-shift placebos ±6h/±24h clean | `python scripts/markout_report.py` |
| Meaning | The adverse component is the limit distance the order was placed at — mechanical, fixed at fill, no forward information. **No measurable post-fill toxicity at candle horizons.** Tick horizons (1 s–5 m) now runnable against the local tape. | `--ticks` (network) or the tape store |
| Fee spend by purpose (1,201 fills) | entry $30.29 (n=534, 27.7 bps effective), exit $45.56, **hedge + unwind $313.51 = 80.5% of $389.36** — ALL from the 2026-08-07 ADA hedge churn (fixed `cf454d5e`, zero hedge fills since). Strategy fees era 7/8/9: $7.43 / $0.98 / $1.90. | `outputs/fills.csv` groupby purpose |
| Fill-conditioning (expired vs filled) | OM-040 expired n=463 vs filled 534, fill ratio 0.54. ≤4h gap < 1 SE. The 24h **+75 bps (+2.2 SE)** headline was killed by its own placebo (±24/48h shifts give the same order). Not measurable at this n. | scratch `unfilled_markout.py` |
| FEE-3 remedy | OM-080 now records full tier context (min/max/next fee, tier volumes, 30-day volume). Nothing here produces a venue reading until a read-only key is used — **operator security decision, unchanged.** | `scripts/cost_truth_report.py` |

**Where the money went:** one hedge incident, already fixed. The strategy's own rake
is small because the strategy barely trades. **Where the money is NOT coming from:**
there is no post-fill edge or toxicity to capture at candle resolution; the cost
of a trip is the spread distance plus 22/38 bps, and the median trip does not clear it.

## 2. The empty offensive half — what the data can and cannot say

"Offensive" = a signal that predicts the sign or size of the move BEFORE the trade.
Measured this session, all on the same corpus:

- Capacity ladder: every family rung scores negative skill; capacity is monotonically
  harmful (prior session, `--ladder`).
- Feature-concentration scan: **0/64 features above the null band; every family ≤ 0**.
  Greedy k=6 reaches +0.0034, which is inside the search-bias noise.
- Tape features (new): trade-count intensity `log n_60` scored AUC 0.52–0.58 across
  six pairs, 4/6 with a day-block CI excluding 0.5. **This looked like the session's
  one offensive signal and it is not one.** Decomposing the same feature on the same
  rows: it predicts whether the path RESOLVES at a barrier rather than timing out
  (mean AUC 0.616), and given resolution it does not predict WHICH barrier (mean
  0.510, zero of seven pairs significant). More trades in the last minute means more
  volatility means the path reaches a barrier; no direction. Refuted the same session
  it was found.

**Honest answer to "can we use my data to build the offensive half":** no — and now
with the tape included, not just the 64 stored features. The one candidate that
looked like it survived first contact was a barrier-geometry artifact. The offensive
half is still empty, and this is the second time a lead has died to that exact
decomposition (the T2 magnitude lead was the first, `2f8550de`). The rule earned:
**no feature is a signal against a triple-barrier label until its AUC is split into
resolution and direction.** What remains genuinely untested is whether a different
TARGET (item 3) makes a tape feature informative — a raw-label AUC cannot answer
that, because the label itself is what confounds it.

## 3. Condensation proposal (for adjudication — NOT shipped)

The feature list is not the lever: no subset beats a constant. The binding
constraint is the **target**: one bit of a real-valued outcome, at a barrier
geometry that makes the label mostly "did not reach +PT before −SL in h432 bars".

Proposal (cohort-resetting, bundle with ALGO-5/GB-1):

1. **Target → net expectancy**, not direction: regress or rank the cost-adjusted
   return at the exit policy's own horizon (label_ret_pct − round-trip cost), so a
   correct-sign-tiny-move stops counting as a win.
2. **Cost-aware label:** the barrier already knows the fee; the label should be
   "cleared cost" not "hit barrier".
3. **Feature set:** drop the structurally dead (`ofi_dir` for 13/15 assets,
   `sent_fear` 100% neutral per overfit battery) and the never-varying. The tape
   activity family is a candidate ONLY under a new target — it replicated across six
   pairs and still carried no direction under the current one.
4. **Pre-register the decomposition:** any candidate feature reports resolution AUC
   and direction AUC separately, before the raw-label number is quoted at all.
5. **Keep the freeze** until the pre-registered readout; register the new target's
   gate BEFORE looking at it (Dwork reusable-holdout is why).

What this proposal does not do: promise an edge. It changes the question the model
is asked to one the data can answer.

## 4. Years of data — the free path exists (tooled, running)

- **Discovery (measured, one call):** Kraken `/0/public/Trades` with `since=0` returns
  XBTUSD trade id 1 (2013-10-06) and every row carries aggressor side and order type.
  Free signed tape, all pairs. Deep-research #2 had this UNVERIFIED and assumed a
  tick rule; the call refuted both.
- **Tool:** `scripts/kraken_trades_backfill.py` (+11 tests). Sustained limit ≈ 1/s
  (3/s tripped after 66 calls). Window 2026-07-13→now = 8.56M trades ≈ 8.6k calls;
  lifetime ≈ 349M ≈ 4 days of walking. 12/14 pairs complete; ETH/BTC/FLOW in flight.
- **The deciding measurement, replicated on 6 pairs:** the stored L2 book feature is
  NOT reconstructable from the tape (Spearman ≈ 0 at 60 s, ≤ 0.19 at 1 h). So free
  history rebuilds the candle family and NEW tape features — not the book family.
  L2 history exists only paid (Tardis, Kraken since 2019-06-04, $450+/mo). Note the
  stored book feature itself scores AUC ≤ 0.50 against the label on all six pairs,
  so what cannot be rebuilt was not earning anything.
- What is unrecoverable at any price: sentiment / th_* / options-derived features.

## 5. Human/LLM error inspection — this session's own

| error | caught by | rule |
|---|---|---|
| +2.2 SE "winner's-curse signature" nearly shipped | its own placebo, one minute later | the-method 2 |
| "n_shared still owed" written without running the emitter | reading the emitter | backpack 4 |
| 50.1 d cited as project age | operator | corpus-span memory |
| 50.1 d cited as the champion's corpus | agent double-derivation (23.73 d) | rule g |
| research #2 assumed tick-rule direction and left reach unverified | one API call | the-method 2 |
| first detached backfill died silently (empty log) | coverage check | staleness protocol |
| `ofi_dir` treated as a live feature in the 64 | groupby asset | instrument first |
| the tape activity "lead" (6-pair replication, 4/6 CI-significant) written into three documents before being decomposed | the resolution-vs-direction split, run because the-method demands it of a surprising positive | the-method 2 + recurrence #10 |
| battery test "flaky" for weeks | measured live-writer race | instrument first |

Fixes completed this session: SD-012 era pooling warning + corpus-span line in the
digest; `champion_skill_report` corpus span keys; FEE-3 tier context; markout
promoted to `scripts/` with 8 mutation-verified pins; backfill tool; HANDOFF /
vault / memory corrections of record.

## 6. Manipulation (detection only)

Nothing built. Standing: SZ-045 efficacy unresolved in both directions
(`sources/session-20260821-manip-gate-and-live-readiness`); the tape now gives a
second, independent route to test the detector (aggressor-side runs vs the book-only
score) — a measurement, docketed, not started.

## Decision table under each gate readout (what the primary sources say)

| readout | act | cost of the wrong action |
|---|---|---|
| NO_GROSS_EDGE | keep freeze; change the TARGET (item 3) via adjudication; keep accumulating tape | retuning on the gate = Dwork 63%-from-noise; reading it repeatedly = Johari ~5× Type-I |
| COST_BOUND | execution geometry (ALGO-5/GB-1), never the model | Arnott–Harvey–Markowitz: tweaking a live model to its OOS is no longer an OOS test |
| CONTINUE | plan any positive at ≤ ⅓ of measured size | Suhonen: median 73% backtest→live Sharpe haircut; McLean–Pontiff 26%/58% |

## Owed (in order)
1. Tick-horizon markout (1 s / 10 s / 60 s / 5 m) against the local tape — the one
   item 1 measurement candle bars cannot answer. Tape-proxy replication is DONE (6
   pairs) and the activity lead is refuted; ETH/BTC still backfilling.
2. Deep-research #3 resume (angles 4–5: LLM-written-instrument reliability, SR 11-7).
3. Adjudication brief for the target change (item 3), bundled with ALGO-5/GB-1.
4. Battery-test live-writer race fix (redirected audit path).
