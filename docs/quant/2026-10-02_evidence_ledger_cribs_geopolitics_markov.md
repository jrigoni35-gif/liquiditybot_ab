# Evidence ledger, cribs, geopolitical influencers, randomized Markov ensemble, knowledge plan (2026-10-02)

**Class: SAFE** (measurement and shadow research only; no decision-module
file touched; decision fingerprint unchanged). Operator requests, in order:
Turing-style elimination with an edge-driven ledger; the 2026 institutional
versions of what we build; market influencers including geopolitics; and
"sets of unpredictable Markov chain analysis to provide the best possible
outcome for the bot's knowledge". AS-OF numbers; re-derive with the commands.

## 0. CORRECTION NOTICE (same day, after an independent code review)

A high-effort code review found ten defects in this session's research
code (record: commit `872ea3f45`; each fix pinned by a test written first).
The tables below were RE-RUN on the corrected code; superseded first-run
values are kept in brackets where they changed a conclusion.

| item | first run | corrected |
|---|---|---|
| ledger eliminations | 5 (P2, P3, P4, C1, C2) | **1 (C2)** - the first ledger used overlapping blocks and max(back, forward) terminal e-values (not an e-value); P2 and P4 now read +12.2 dB, P3 +8.0, C1 +9.5, below the 13.0 dB line |
| C2 funding settlement | none (+2.6 [−1.4, +7.8]) | entry now 1 h BEFORE settlement: **+2.4 [−0.3, +7.4] bps, Holm p 0.035 - a tiny real edge, eliminated for trips (+54.2 dB)** |
| M1 pre-FOMC | −31.2 [−102, +63] | window now ends AT the statement: **−27.0 [−126, +85]**, none |
| M2 FOMC vol | 1.09× | statement hour included: **1.13×** |
| G1 haven tilt | −3.6 | both legs drift-adjusted: **−3.3 [−390, +360]**, undecided |
| Markov family test | "none survive Holm" (Holm could not reject: 400 tests, 199 shifts) | exact Westfall-Young max-T, full rotation group (5.8% family-wise on 450 null sims): **smallest adjusted p 0.266, none survive; walk-forward pick p 0.906 out of sample** |
| MM viability | 622 post-only legs; 60-min adverse selection −8.8 | **443 maker ORDERS** (partials aggregated, CS-1 reconcile OK); 60-min −5.5 [−11.5, −0.4]; break-even half-spread 12-64 bps; viable 0 of 14 |

## 1. The ledger (Banburismus with anytime-valid guarantees)

`core/evidence.py` + `scripts/evidence_ledger.py` +
`docs/quant/hypothesis_registry.json` (21 hypotheses). Two betting
e-processes per hypothesis (Waudby-Smith & Ramdas; Ville-valid, may be
watched every step): e_exist (edge > 0) and e_dead (edge < 2c = 45 bps);
decibans; e-BH per family. **Registered asymmetric rule: the past may
eliminate, only data after `forward_from` may promote** (hindsight - a
paper's, the bot's, or the AI's that proposed an idea - inflates positives;
"Profit Mirage" 2025). Failure memory refuses an idea whose (signal,
horizon, use) is already eliminated. Status wording is trip-precise:
`ELIMINATED FOR TRIPS` says nothing about a smaller edge used as a tilt.

Ledger, corrected run (`python scripts/evidence_ledger.py`):
`reconcile: n=21 = scored 21 (UNDECIDED 20, ELIMINATED FOR TRIPS 1) [OK]`.
Eliminated for trips: C2 funding settlement (+54.2 dB). Nearest the line:
P2 daily TSMOM and P4 flow reversal (+12.2 dB each), C1 (+9.5), P3 (+8.0).
Forward n = 0 everywhere today: nothing can be promoted until data after
2026-10-02 exists.

## 2. Crib catalogue (structural flows, registered before data)

| crib | events | A (bps) | verdict |
|---|---|---|---|
| C1 quarter-hour opening imbalance (Kim & Hansen 2026 §6.1: continuation, 4-12 h) | 38,500 | **+5.7 [+0.5, +10.2]**, Holm p 0.04 | **edge exists, out of sample to the discovery** (2024-11..2026-08); far below a round trip |
| C2 funding-settlement exit (corrected window) | 74,219 | **+2.4 [−0.3, +7.4]**, Holm p 0.035 | tiny edge before settlement (+1.4 bps in the hour); eliminated for trips |

C1 instrument checks: 669 days per asset, no gap > 1 min, ms units; the
same rule at minute :07 (placebo) earns +0.5 bps vs +3.5 at the marks
(+3.0 difference), positive in 6/6 assets. Disclosed weakness: 1-minute
bars dilute their 10-second window.

## 3. Geopolitical and macro influencers (registered before data)

Sources: Caldara & Iacoviello daily Geopolitical Risk index (1985-2026-10-01);
the Federal Reserve's FOMC calendar (57 statements, 14:00 New York,
DST-aware). Gaps stated: influencer posts (X API paid), GDELT (rate-limited),
BLS (blocked).

| hypothesis | events | A (bps) | reading |
|---|---|---|---|
| G1 GPR spike → PAXG over crypto (tilt; exogenous driver of `regime/haven.py`) | 554 | −3.3 [−390, +360] | undecided - too few independent episodes (43 four-week blocks) |
| G2 GPR spike → crypto below drift | 10,779 | +20.3 [−313, +350] | undecided |
| M1 pre-FOMC 24 h drift (window ends at the statement) | 583 | −27.0 [−126, +85] | none; crypto weakens 6-12 h before statements (−15, −43 bps), opposite to equities |
| M2 FOMC volatility (report-only, statement hour included) | 57 | — | post-statement 24 h |ret| 1.13× normal: no need for FOMC de-risking |

Defect caught test-first: Stata `datetime64[s]` dates divided as ns loaded
every GPR date as ~1,790 s after 1970 - the signal would have been silently
empty and read as "no effect".

## 4. Randomized Markov ensemble (the "unpredictable sets")

`scripts/markov_ensemble.py`: K = 200 random partitions (seed 7) of 11
past-only variables (returns, vol ratio, relative strength, volume, taker
imbalance, funding, GPR, stablecoin supply, weekday) → states; does the state
predict the next 1-day / 7-day drift-adjusted return? Circular-shift null,
Holm over 400 tests, walk-forward selection.

**Instrument defect found and fixed first:** per-asset rotation erased the
common market move (states such as GPR and stablecoin supply are
market-wide), so 69% of 400 tests read p < 0.05; on a synthetic
common-factor null the old rotation rejected 45%, the corrected
same-offset rotation 3% (pinned).

Corrected result (`python scripts/markov_ensemble.py`, exact Westfall-Young
max-T over the full rotation group): 7.0% raw p < 0.05, **smallest
family-adjusted p 0.266 - none survive**; the walk-forward winner (volume
z, first-half z +2.03) **reads p 0.906 out of sample**. No state structure
in this universe predicts daily or weekly returns - consistent with the
earlier Markov memory tests (A11-A13). Disclosed: weekday is periodic, so
the rotation test is conservative for it.

## 5. Knowledge plan (Markov decision over the bot's beliefs)

`scripts/knowledge_plan.py`: per-hypothesis knowledge gradient (value of
one more independent block of forward data for that hypothesis's own
act-or-not decision) and expected time to a 13 dB decision at today's
estimate. Defect caught test-first: the textbook winner-take-all KG let
one wide hypothesis (L5) zero out every other's value.

| rank | hypothesis | KG | weeks to a decision |
|---|---|---|---|
| 1 | G1 geopolitical haven tilt | 9.41 | never at today's ≈0 estimate - needs more independent episodes, not time |
| 2 | G2 geopolitical risk → crypto | 2.26 | ~48,000 |
| 3 | B3 top-confidence timing, market-relative | 2.11 | ~2,800 |
| — | B3 top-confidence timing, raw | 0.00 | **~23** (already registered forward read) |
| — | C1, C2 | 0.00 | ~2 (decided: below a round trip) |

## 6. What the bot should do with its knowledge

1. **Trips:** nothing promotable; EDGE-1 stands. Exploration remains paper
   tuition (2026-09-28 ruling).
2. **Forward reads, in value order:** B3 timing raw (~23 weeks to decide);
   L5 stablecoin flow; C1 as a TILT (a new registration with `use: tilt`,
   allowed by the failure memory); G1 needs more independent geopolitical
   episodes - a daily news-tone series (GDELT, once reachable) or other
   haven assets, not more weeks.
3. **Stop spending research on:** state-partition mining (the ensemble
   says no), the eliminated five, FOMC timing.
4. **Holding book:** vol targeting remains the one lever with supported
   evidence (feature program record).
