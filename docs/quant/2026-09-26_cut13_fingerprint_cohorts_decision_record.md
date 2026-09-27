# Cut #13 — decision-fingerprint cohorts + the Kimi-review decision batch

- date: 2026-09-26 (operator ruling, in chat) · recorder: Claude Code session "Claude RC"
- authority: operator, verbatim: "Ignore the cohort resetting restrictions for this
  big change … if we go in and reconfigure what 'cohort resetting' actually means
  within the bot this time, it will be more effective then not." and, on the held
  list, "Yes" (items 1–5, one restart). Hard invariants 1–7: untouched, and stated
  as out of scope to the operator before any edit ("porcelain mindset").

## 1. What changed in the LAW

The era-9 moratorium's "COHORT-RESETTING — forbidden without adjudication" rule and
its 14-day minimum are replaced by **COHORT-FORKING** (CLAUDE.md, AGENTS.md mirror;
`docs/law/era9_moratorium.md` carries a SUPERSEDED-IN-PART banner, history kept).

A cohort is now the set of trips whose entry leg carries the same **decision
fingerprint** (`core/cohort.py`): sha256 of the decision-relevant config (fail-closed)
+ docstring-stripped AST of the decision-path code, derived at boot, stamped on every
fill (`fills.csv` `decision_fp`), in the `CG-000` session record and in `status.json`.
The price the moratorium measured for a mint (accrual to zero for everything; ~78% of
banked trips leaving the gate; 1 of 6 eras ever reaching n=50) no longer applies: a
change forks a NEW cohort, banked trips keep their own read.

`scripts/era_readout.py` keeps the registered era-9 read on the **legacy** cohort
(blank fingerprint) plus evidenced equivalents (`docs/law/cohort_equivalence.json`,
empty at this cut) and reads every fork on its own. Proven output-identical on a frozen
fills snapshot (all registered sections byte-equal, old vs new).

## 2. What changed in the BOT (all forks of the decision cohort)

| item | change | evidence | expected effect |
|---|---|---|---|
| F1 | `darkpool.max_data_age_days: 35` — stale mirror served unavailable | real-mirror copy: armed → available False, dp_* 0.0; ungated → hhi 0.1252, 155 d old | served p_win +2.2pp mean on v10 rows, 0 threshold crossings (reviewer) |
| R3 | fee proposal carries all 6 fee keys; self-clears; honest note | pins; planted 40/80 applied → 0 FATAL | report-only; no order path |
| R2 | Kimi's frozen tiers 2–4, redesigned: freeze the measured SIGMA at the first fire of the preceding tier (not the trigger), keep-first, never freeze an unmeasured sigma, tolerant restore | 23 pins; 3/3 guard mutants caught | era-9: 0 of 84 exits were tier fills — near-zero exposure until tier 1 fires on a bracket position |
| SAFE batch | model no longer saturates on training-constant columns; darkpool lifecycle; DE-010 honesty; hourly isolation (commit 831900fea) | corpus replay max|d| 0.0 | no normal-path change |

## 3. Deferred, with reason

- **C5** (in-process auto-retrain blocks the stop loop 21–28 s/hour, n=20): training,
  champion comparison, save and `meta.reload()` are interleaved and `self.meta` serves
  every inference. Threading it unsplit risks a mid-inference model swap. Design: train
  on a snapshot in a worker; promote on the main thread at the next hourly via the
  existing external-adopt path. Own change, own review.
- **Probe lane** (item 6): every era-9 5m entry was an exploration probe admitted at a
  forced p_win 0.85 while the model said 0.39–0.51. Fair-game arithmetic at PT 180 /
  SL 135: break-even p* = (b+C0)/(a+b) = 0.571 (fees 45 bps) / 0.619 (+15 bps adverse);
  driftless V = −C0. Operator choice, presented separately.
- **C3** (slow-head fault skips the entry sweep): left as-is — fail-safe under invariant 5.

## 4. How to read the result

Run `python scripts/era_readout.py` and read DECISION-FINGERPRINT COHORTS. The first
post-restart fingerprint is its own cohort (n from zero, same registered read points).
Pool it with legacy ONLY by an evidenced equivalence entry — this cut changes decisions
(F1, R2), so no such entry is justified for it.
