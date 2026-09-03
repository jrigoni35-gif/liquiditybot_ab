# Full diagnostic scan — codes, procedures, probes, strategies, aggression, and the unexpected formulas

**Read 2026-09-02T23:58Z.** This is a synthesis of everything measured across this
session plus three targeted checks run specifically for this document (the reason-code
registry, the aggressive-exploration feature, and whether the disposition bug touches
training). It is not a new fan-out — nearly everything below was already measured and
verified this session; this document's job is to connect it into one prioritized answer.

**The honest headline, stated first because it should not be buried under detail:**
every edge-generation channel tested this session — spread, volume growth, stop
reversal, target design, feature list, tape microstructure — came back **null at a
real, measured power floor**. The rapid-impact opportunities below are almost all
**integrity fixes** (audit trail, observability, safety), not edge-generation, because
edge-generation was tested and did not survive. Reporting this as anything more upbeat
would be exactly the overclaiming this repo's own method exists to catch.

---

## 1. Diagnostics — instrument defects (the measurement was wrong)

| # | defect | measured value | status |
|---|---|---|---|
| 1 | Champion skill verdict was a bare sign test, no power | resolved only \|skill\|>0.0146 against an estimate of −0.0036 (4× too coarse) | **fixed** |
| 2 | Skill score carries an undocumented negative bias | ≈ −1/n: −0.0052 at n=200 → −0.00005 at n=20,000 | **fixed, documented** |
| 3 | Chance baseline for feature significance was nominal (5%), not measured | realized rate 12.5% on this corpus — 2.5× higher | **fixed** |
| 4 | `gate_truth_report`'s power figure was **wrong**, not merely stale | old "~0.17 AUC" was 0.405× the correct value (0.42 at its own sample) | **fixed, now computed live** |
| 5 | Corpus span conflated three ways | champion-scored 23.73 d ≠ raw file 50.25 d ≠ project age (months) | **fixed, both corrections of record** |
| 6 | Harvey–Liu 86.9% Type-II cited as a general excuse for nulls | it is the power of a **joint** test over ~3,000 funds; does not transfer to one pre-registered test | **struck at source, twice** |
| 7 | Leverage crossover mis-solved | stated 6.67×, correct 5.88× | **fixed** |
| 8 | Stop-provenance join rate overstated | stated 97.9%, true 42.6% (183 of 324 joined rows carry `sl_frac==0`) | **fixed** |
| 9 | Pooled volume-growth quintiles were an asset selector, not a pure sort | top quintile was 47% ARB+PAXG+MINA | **fixed, repaired to within-asset** |
| 10 | Pooled bear-vs-bull spread gap was asset-mix composition | reproduced by a regime-blind placebo; within-asset real gap 0.147 bps | **fixed, repaired** |
| 11 | "BTC has the highest reversal-above-placebo" was placebo-design-dependent | a second placebo design flips the sign | **caught by the verifier, not reproduced; struck** |
| 12 | 44 of the 5-minute stop-hunt memo's rows carry no power floor | k=3/12/48/96/288, several volume-quintile diffs | **named, not fixed — read those rows as unresolved, not null** |
| 13 | My own diagnostic check for this document flagged 50 "orphan" reason codes | false positive: regex caught `SHA-256`, and the SD-family and stub-adapter codes are a **deliberately separate, already test-pinned** allowlist (`tests/test_code_registry.py`, 4/4 passing) | **checked, no defect — my instrument was the suspect, correctly** |

Item 13 is included on purpose: it is a real-time demonstration of the method this
whole scan is applying — verify the instrument before trusting its alarm, including
mine, in the same document that is asking the question.

## 2. Diagnostics — code and procedure defects (the bot's own logic)

| # | defect | mechanism | scope |
|---|---|---|---|
| 14 | **The disposition field is a mapping write, not a resource write** | `ml/history.py:2460 mark_disposition` overwrites the newest open candidate for `(asset, direction)` with **no candidate-id match, no recency bound** — a verdict from ~10² cycles later can land on a stale feature snapshot. Every `disp` value in the corpus inherits it (capped 5,607, SZ-021 2,664, `entered` 383, …) | corpus-wide; confirmed at the row level (24.3% seam rate at a 24 h window, per-event) |
| 15 | The manipulation gate is an illiquidity detector | FLOW median `manip_suspect` 0.927 against a veto at 0.90; 470/1,065 signals refused; **zero fills ever** | measured; may be a defensible refusal for an indefensible stated reason |
| 16 | SZ-045 refusals have no audit-trail record | join rate 0/752 to `outputs/audit.jsonl`; the event log (`runner.log`) does carry them, the hash chain does not | confirmed |
| 17 | `ofi_dir` is structurally zero for 13 of 15 assets | its inputs are external venue books, and only ETH/BTC are configured on OKX/Binance.US | dead-by-design, not a bug, but silently so |
| 18 | The exit-mix drift alarm (ML-080) is uninformative | 20.7% of its baseline is retired label vocabulary from a July schema change — a permanent floor at 69% of the 0.30 threshold; 72.4% of historical windows already exceed it | boundary-adjacent fix described, not made |
| 19 | Kraken's real maintenance-margin/liquidation formula is encoded **nowhere** in the repo | every headroom figure this session used the bot's own 150% floor as the boundary | not yet fixed; recommended SAFE addition |
| 20 | The margin-block/margin-scale branches have never fired and have no audit code | invisible if they ever do | not yet fixed; recommended SAFE addition |
| 21 | `test_archetype_battery` flakiness | a live-writer race against the runner's own audit appends, not order dependence | not yet fixed |
| 22 | **[found and fixed this session, during its own adversarial review]** an uncaught exception on one asset in `scripts/tape_to_candles.py` killed the entire multi-asset batch, discarding visibility of bars already committed for prior assets | reproduced by execution (a NaN row); now caught per-asset, printed incrementally, mutation-verified | **fixed, 14 pins, 4 mutants all red** |

Item 14 is the one worth sitting with. It was found while chasing a manipulation-gate
ticket and turned out to be a defect in the **audit annotation layer itself** — the
mechanism by which the bot records what happened to a decision, not the decision
mechanism. Checked specifically for this document: `disp` is written to the training
corpus purely as a descriptive string (`ml/history.py:2766`) and is not read back by
any training filter or weight — fixing its write semantics (bind to the candidate's
existing UUID, write-once, tombstone on eviction) would very likely touch **only**
the audit trail, not what the model trains on or how orders are placed. It still lives
inside `ml/history.py`, which every standing rule this session has used blankets as
BOUNDARY, and I have not verified every reader of the `disp` column across the whole
repo — only the training path. **Recommend a scoped adjudication, not a unilateral
fix**, given the file it lives in.

## 3. Diagnostics — process errors (mine)

Named because "what we are doing wrong" includes the instrument-builder, not just the
instrument:

- Four laundered exit codes this session — a piped command's exit status tested
  instead of the command that mattered (`pytest | tail && …`).
- The audit-ledger pollution incident: a delegated agent wrote two mutation-test rows
  into the production hash-chained trail because one prompt carried both a general
  prohibition and a specific instruction that violated it. Repaired by excision;
  chain verified clean afterward.
- My own denominator error: nearly reported 383 `entered` stamps against 541 fills as
  a shortfall, before checking that those fills are 329 distinct positions (partial
  fills), which makes stamps exceed positions rather than fall short.
- Two candle-journal contract landmines learned the hard way: `ingest()` takes its own
  non-re-entrant lock (wrapping it deadlocks every call against your own process), and
  its `note` field is a frozen vocabulary, not free text.
- Item 13 above, this document's own false-positive registry alarm.

## 4. What is actually learnable — the edge-hunting summary

- **The barrier-geometry rule, now proven at scale.** A feature scored against the
  triple-barrier label mixes two channels: does the path resolve at all (loaded by
  volatility, no edge) and which way it resolves (the only real channel). Measured on
  every population tested this session — the stored 64 features, 20 tape-derived
  features, and the continuous target — **zero features clear a 0.05 SD detectable
  effect on the direction channel.** The instrument that proves this (`--power-calibration`)
  detects a real 0.05 SD effect 100% of the time, so "nothing found" is a finding, not
  an underpowered silence.
- **Every standard channel is null at real power, not merely unmeasured:** spread by
  regime, volume growth into a stop, stop-reversal-after-hunt (confirmed twice, at
  1-hour and 5-minute resolution), and leverage-driven liquidation risk.
- **The one channel that is not null:** net expectancy is **negative in every
  environment**, most precisely measured on BTC (−0.82% [−1.05, −0.56], the tightest
  interval of the triad). "BTC is reliable" is earned only in the sense that the
  absence of edge is measured most precisely there.
- **The target-change proposal was rejected on measurement**, not on the moratorium
  alone: a continuous target resolves the identical 0.05 SD effect as the 1-bit
  target and finds nothing extra (5 significant features against 6.3 expected by
  chance — below chance).
- **Condensation's lever is the target, not the feature list.** The list has already
  been tested at zero information gain; a magnitude- or cost-aware target is a real
  open question, but it is a research question, not a fix.
- **The free tape (Kraken trades back to 2013, all pairs) adds no directional
  information either** — same null, same power, checked on both the stored and the
  tape-built feature families.

## 5. "Aggression in learning" — what already exists, measured, and what to read this as

This phrase is read here as **exploration aggressiveness**, not market manipulation.
Manipulation stays fenced to detection-only per every standing instruction this
session; nothing below builds or recommends manipulative trading behavior.

**A conviction-scaled aggressive-exploration feature already exists and is enabled**
(`config.json` `ml.exploration.aggressive`): with probability 0.15, when model
conviction ≥ 0.55 and the manipulation score ≤ 0.6 outside crisis regime, the bot takes
a **full-size** paper ticket instead of the usual min-sized exploration trade, so the
model learns from confident calls at real size rather than only from timid marginal
ones. This is precisely the "learn faster from previous operations" idea, already
shipped.

**Measured its actual usage** (needle `"ML-070"` / `"ML-072"` in `outputs/audit.jsonl`,
read 2026-09-02T23:57Z, 25.0 MB, grepped not read whole): **23,897 normal exploration
entries** against **333 aggressive entries** — aggressive exploration is about 1.4% of
exploration volume, active since at least 2026-07-19 (first `ML-072` timestamp). This
is a real, current number; its **outcome** (does the aggressive arm's real-size bet
actually resolve better or worse than the normal arm) is **not yet measured** — the
audit lines carry asset/side/timestamp but no position id, so joining to
`signal_history.csv`/`fills.csv` outcomes needs a timestamp-tolerance join, not a key
join. This is a cheap, concrete, owed measurement, not a gap in this document by
oversight.

**There is also a second, larger exploration-cadence system already live**: the
scarcity-priced probe budget (`ml.exploration.admission.mode = 'budget'`, flipped from
the legacy share-cap on 2026-07-31), which prices probe admission by how scarce that
(asset, regime) combination is in the live corpus rather than a flat share cap. It
exists specifically to solve the F0b livelock this repo has already fixed once.

**What "more aggressive" should NOT mean, given section 4:** every measured channel
argues against sizing up, loosening stops, or overriding the manipulation gate — this
session quantified the fee/spread/hedge-churn cost of exactly that class of behavior
earlier (the 2026-08-07 hedge-churn incident was 80.5% of lifetime fees). The
productive reading of "aggression" here is **aggression in measurement and
exploration-data-collection** — take more confident real-size paper trades to generate
richer labels faster (already shipped, underused at 1.4%), and test target/feature
changes offline before ever considering a live change (the target-change decision this
session made in an afternoon rather than a quarter, because the data to test it was
already in hand).

## 6. The unexpected formulas

The surprising quantitative facts worth carrying forward, several of which reversed a
belief that had already been written into a document once:

1. **Skill-score bias ≈ −1/n.** A perfectly calibrated constant predictor scores
   negative because the oracle baseline is refit per window while the predictor is
   fixed — not a flaw in the metric's direction, but a magnitude nobody had measured.
2. **Annualized-Sharpe SE = 1/√y (years).** At this corpus's true span, y = 0.065 yr,
   SE ≈ 3.9 — no Sharpe this corpus can produce is distinguishable from zero, in either
   direction.
3. **Harvey–Liu's 86.9% Type-II rate does not transfer** from a joint cross-sectional
   test over thousands of funds to a single pre-registered strategy test — a citation
   trap this repo fell into twice before catching it.
4. **The triple-penance stop-out rule assumes IID-Normal cashflows, and its own
   authors' data refutes that assumption in 21 of 26 real indices** — the rule is
   mathematically clean and empirically shaky on the exact kind of series it is meant
   to govern.
5. **The realized null-exclusion rate (12.5%) is 2.5× the nominal rate (5%)** at this
   corpus's day-block count — every multiple-comparison argument in this repo now
   quotes the measured rate, never the textbook one.
6. **Crossover leverage (5.88×) sits ~17× above the realized maximum (0.344×)** — a
   stop hunt literally cannot reach the liquidation boundary at any leverage this bot
   has ever actually used.
7. **A design effect of ρ=0.7 over 10 correlated assets buys ~1.37× the effective
   sample, not 10×** — panel pooling across assets is not a free multiplier.
8. **Kraken's public trade endpoint reaches back to trade id 1 (2013) for every pair,
   free, with the aggressor side included** — a fact the first research pass on this
   question got wrong by assuming it needed the tick rule.
9. **A manipulation score and a liquidity score are observationally identical from a
   book-shape detector** — FLOW's median score exceeds the veto not because it is
   manipulated more, but because it trades 66× less often than ETH on the same venue.

## 7. Prioritized fixes — ranked for rapid, safe impact

**Tier 1 — SAFE, ready to ship without adjudication:**

1. Register an audit code for the margin-block/margin-scale branches (additive).
2. Encode Kraken's real maintenance-margin/liquidation formula in the repo (additive;
   removes the "every headroom number uses our own floor" caveat from every future
   leverage measurement).
3. Fix `test_archetype_battery`'s live-writer race (test-only).
4. Measure the aggressive-exploration outcome join (timestamp-tolerance join,
   `ML-072` vs `ML-070` vs normal conviction entries) — cheap, and it is the one
   concrete "aggression" question this document could not close today.
5. Add an audit emission at the SZ-045 veto call site so manipulation refusals join to
   the hash chain (closes MANIP-3; almost certainly additive observability, not a
   decision-path change, but worth a fast scope check before shipping given it touches
   the sizer's call site).

**Tier 2 — likely SAFE, needs a scope check before shipping (not shipped today):**

6. The disposition write-semantics fix (item 14) — checked and very likely
   training-inert, but lives in `ml/history.py` and deserves the same scope
   confirmation the fan-out gave the ML-080 baseline fix rather than a unilateral
   change.
7. Scope and fix the ML-080 baseline to exclude retired label vocabulary — already
   flagged boundary-adjacent by the agent that found it; respecting that call here.

**Tier 3 — BOUNDARY, operator adjudication required, no measured motive found yet:**

- Stop/exit geometry changes (ALGO-5/GB-1): both the hourly and 5-minute stop-hunt
  passes found the reversal rate equal to the volatility base rate. No measured reason
  to touch stop placement.
- Any spread-, volume-, or manipulation-score-conditioned entry rule: all three
  premises this session set out to test were refuted at real power.
- The target change: rejected on measurement; would need a new positive result on the
  continuous target's power to reopen.
- The FLOW listing: a liquidity, not a manipulation, fact — the traded-universe
  decision is the operator's.

## 8. What this document did not do

It did not run a new large-scale measurement fan-out — it synthesized what this
session already measured plus three cheap, targeted checks (registry health,
aggressive-exploration counts, disposition training-inertness). The aggressive-
exploration **outcome** comparison, the ML-080 baseline scope check, and the SZ-045
audit-emission scope check are named as owed, not silently skipped.
