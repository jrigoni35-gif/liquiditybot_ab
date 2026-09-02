# A resource-oriented labeling system — design, grounded in today's measured defects

**Status:** DESIGN for adjudication. The write-path changes here touch `ml/history.py`
(the disposition and candidate writers) and therefore the training corpus and the
model; under the era-6 moratorium and the 2026-08-10 model freeze they are
BOUNDARY and are NOT implemented. One piece is SAFE and is shipped alongside this
document: the **verification node** (`scripts/disposition_integrity_report.py`),
which audits the existing corpus read-only.

**Premise check, stated once.** Flow's node roles, Cadence's linear types, its
account model and its EVM bridge are blockchain features. None of them runs here;
the bot trades Kraken spot and never touches a chain. What transfers is not the
technology but **five design principles**, and each one maps onto a defect this
repository measured in the last 48 hours. That is why the comparison is worth
making: the principles are not analogies, they are prescriptions for bugs already
found.

I have not verified the market-history claims in the pasted text (the December 2025
exploit, the Korea delisting, the Forte schedule). The tape here confirms only that
FLOW traded at 0.0267 on 2026-07-13 and 0.0259 on 2026-09-02. The design does not
depend on any of those claims.

---

## 1. Resources, not mappings — the disposition is a linear type

**The Flow principle.** A Cadence resource has a UUID, exists in exactly one place,
cannot be copied, and *cannot be silently dropped* — the compiler rejects code that
loses it. An ERC-20 balance is a number in a mapping that any writer can overwrite.

**The measured defect it names (MANIP-2, 2026-09-02).** `ml/history.py:2460
mark_disposition` addresses a candidate by `(asset, direction)` and overwrites the
newest match — **a mapping write**. The candidate already carries a UUID
(`id = cand-<salt>-<seq>`, minted at `register`), and the writer ignores it. Two
consequences, both measured:

- **Last-wins overwrite.** ~10² veto evaluations per registration gap (p50 923 s
  against a 5 s cycle) can rewrite `disp` against one frozen feature snapshot. 204 of
  752 SZ-045 stamps sit below the threshold that supposedly produced them.
- **Silent drop.** When the candidate cap is hit, the newest pending candidate is
  evicted (`ml/history.py:2404`, deliberate, documented) — and its disposition, if any,
  vanishes with no record. A linear type would make that a write-time error.

**The design.**
1. `mark_disposition(candidate_id, code, evaluated_at, score_snapshot)` — the stamp is
   bound to the UUID it belongs to, not to the newest thing with the same name.
2. **Write-once.** A candidate's `disp` moves from `"confirmed"` to exactly one terminal
   value. A second write to a terminal stamp is refused and *counted* (a new SD-code in
   the digest), never silently applied. That is the linear-type constraint expressed
   in a language without one.
3. **Every stamp carries its own inputs.** `disp_evaluated_at` and `disp_score` ride
   with the row, so the seam between "when the features were frozen" and "when the
   verdict was reached" is visible per row rather than inferred from cadence
   statistics.
4. **No silent drop.** Eviction of a candidate that has been stamped writes a tombstone
   row (`disp = "evicted:<prior>"`). The corpus can then say how many verdicts it lost,
   which today it cannot.

**What this buys, in the currency of today's findings:** MANIP-2 becomes impossible by
construction; `gate_efficacy_report`'s regex-scrape of `disp` starts reading the verdict
that belonged to the row; and the `entered` arm — which I checked today and found *not*
mis-assigned, but only by a denominator argument — becomes provably bound.

## 2. Decouple ordering from computation — the three clocks

**The Flow principle.** Consensus nodes order and finalize; they *never execute*.
Execution nodes compute. Coupling them (Ethereum) makes every node pay the full cost
and ties ordering to whatever execution happened to finish.

**The measured defect it names.** The labeling pipeline runs on three clocks and
writes them into one row as if they were one: the feature snapshot is frozen at
*registration* (`register`, gated by the same-bar dedup and the SCS latch); the veto is
evaluated at *cycle* time (`main.py:4708`, every ~5 s); the label resolves at *barrier*
time (h432 bars later). Today's MANIP-2 is precisely the first two clocks colliding.
ML-080's inverse blind spot — the `triple_barrier → h432` horizon change moved
tb_time's share 62.2% → 16.7% and the drift alarm saw nothing — is the third clock
changing underneath a metric that only watches category names.

**The design.** Make the three clocks three explicit columns on every row —
`registered_at`, `disposed_at`, `resolved_at` — and make every instrument that reads
the corpus declare which clock it is keyed on. The decomposition report is keyed on
`resolved_at` (it needs barriers); the disposition audit is keyed on `disposed_at`; the
feature scan is keyed on `registered_at`. A row whose clocks disagree by more than a
cycle is not "stale", it is *measurable*, and the digest can count it.

## 3. A verification role that does not execute — SHIPPED (SAFE)

**The Flow principle.** Verification nodes re-check the execution nodes' work. They
have no stake in the result and run nothing else.

**What exists today.** Nothing checks that a `disp` stamp came from an evaluation whose
inputs match the row it landed on. The verification standard written yesterday says
"cross-implementation or it did not happen"; this is that standard applied to the
corpus itself.

**Shipped:** `scripts/disposition_integrity_report.py`. It joins every SZ-045 stamp in
`signal_history.csv` to the sizer's own veto log lines in `runner.log`
(`[ASSET] sizer veto: SZ-045: manip suspect X >= veto 0.90`, timestamped to the
millisecond, **415 lines from 2026-08-25T16:07Z to now** — the event log the earlier
memo pointed at carries **zero**, a correction of record). For each stamped row it
reports the nearest veto event for that asset, the lag between the row's registration
and the verdict that stamped it, and whether the row's stored `manip_suspect` agrees
with the score the sizer actually saw. It is read-only, it plants nothing, and its
first run is the first per-event measurement of the seam rather than a cadence
argument. **Coverage caveat by construction: the log begins 2026-08-25, so only stamps
after that date are auditable; the report says how many it could not reach.**

## 4. Do not import the attack surface with the tooling — one ledger, one vocabulary

**The Flow principle (from the pasted exploit account).** Adopting the EVM for
compatibility brought in mapping-based tokens and upgradeable proxies — the safety
model that applied to Cadence resources did not apply to the imported environment.

**The two measured defects it names.**
- **ML-080** fires because the drift baseline still holds **20.7% retired label
  vocabulary** from the 2026-07-26 schema change — a permanent TVD floor worth 69% of
  the threshold. Two label regimes share one file and one baseline.
- **Recurrence #11.** Two mutation-test rows landed in the production audit ledger
  because nothing typed the difference between a test write and a production write.

**The design.** Label vocabulary is *versioned per row* and the corpus loader refuses
to pool across versions unless told to — which it already does for `label_era` on the
training path but not on the drift-alarm path; extend the same refusal there. And the
audit trail gets a **write guard** that refuses any append whose caller is not the
registered `AuditTrail` writer (a process-level check, not a prompt-level one). The
verification standard's item 8 said "make prohibitions machine-enforced"; this is where.

## 5. Native scheduling — the label horizon as a first-class event

**The Flow principle.** Protocol-native scheduled transactions; no external keeper.

**What it maps to.** Triple-barrier resolution *is* a scheduled event (h432 bars after
registration) and it is implemented as a poll (`poll()` runs first each cycle). That is
Ethereum's keeper pattern. The design change is small and mostly conceptual: emit the
resolution as an explicit `resolved_at` event with its own audit row, so that a label
resolving late, early, or never is a *counted* outcome rather than an absence. Today
the only sign that labels are resolving strangely is the exit-mix alarm, which section
2 showed cannot see a horizon change.

## What does NOT transfer, said plainly
- **Multi-key accounts with weights and revocation** — the nearest thing here is the
  candidate/live/probe sample-weighting that already exists. No new design.
- **Parallel execution / sub-cent fees / gasless** — throughput is not this bot's
  constraint; the cycle is ~95% I/O wait on a rate-limited venue (measured, memory
  `perf-latency-work`), and fees are set by Kraken's account tier.
- **The EVM bridge and the FLOW/USD price** — the pasted account may well be right
  about why FLOW fell; it changes nothing about how this bot should label anything.
  What the tape *does* say about FLOW is that it prints ~15 trades an hour and the
  manipulation gate refuses its median signal — a liquidity fact, not a protocol one.

## Adjudication summary

| # | change | class | ships now? |
|---|---|---|---|
| 1 | UUID-bound, write-once disposition with tombstones | BOUNDARY (training corpus) | no — ALGO-5/GB-1 bundle |
| 2 | three explicit clocks per row | BOUNDARY (schema) | no — same bundle |
| 3 | verification node over the existing corpus | **SAFE** | **yes, shipped** |
| 4a | drift baseline scoped to live vocabulary | BOUNDARY (`ml/history.py`) | no |
| 4b | process-level audit write guard | SAFE (core/audit, additive) | proposed; not in this commit |
| 5 | `resolved_at` audit event | BOUNDARY (label path) | no |

The order matters: **3 first**, because it measures how large the problem that 1 and 2
fix actually is, per row, before anyone resets a cohort to fix it.
