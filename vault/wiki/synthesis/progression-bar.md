---
title: "The Progression Bar — poor → Prestige, the code as the 100% basis"
category: synthesis
status: SETTLED
summary: "Infinite maturity bar for the codebase: each execution era is a prestige cycle whose baseline (0%) is the code as measured at the boundary, whose 100% is that cycle's mapped-improvement set shipped AND verified, and whose prestige gate is operator adjudication. Tracks baseline, current %, attribution (operator WHAT / Claude HOW), and the hand-in-hand learning cycle that feeds each next bar. Percentages are derived-on-read, never settled. PRESTIGE #2 FIRED 2026-08-30T15:32:36Z — cut #9 the Tier-3 fee correction, exec_era 9-16ec821e (commit 59bdcf87), boundary #6: the era-8-ca55e2ba cycle's final block is archived ON THIS PAGE (it never got its own boundary doc) and the page is reset to the era-9-16ec821e baseline. NEW SHAPE RECORDED: a prestige cycle can be ended by its own BASELINE being falsified, not only by its map being completed — cut #8 lasted 2.0 days and accrued nothing before its founding fee constant was proved ~2x wrong. New map = QT-1 (drift narrowed to 2bps, re-baseline still owed) / MLSEC-1 / ERA6-COUNT-1 / CTRL-2 / GB-1 / ALGO-5 / asset discipline / CONC-1 + the 40-item long-term improvement map + owed register."
tags: [progression, maturity, method, learning-loop, meta]
sources: 3
updated: 2026-08-30
---

# The Progression Bar

**Operator directive 2026-08-27:** a metaphorical infinite progression bar,
poor → Prestige, with the CODE as the 100% basis — track the baseline, where
improvements stand, and both parties' share in them. A cycle of hand-in-hand
learning.

## The shape (why it is infinite)

The bar never ends because 100% is not perfection — it is **this cycle's
mapped improvements, shipped and verified**. Crossing it does not finish the
project; it **prestiges**: the operator adjudicates the boundary bundle, a
new execution era mints, the improved code becomes the new 0%, and the next
cycle's map becomes the next 100%. This is not invented for the metaphor —
it is how the repo already works: [[comparability-boundaries]] execution
eras ARE prestige cycles, and the era-boundary adjudication IS the prestige
gate. The bar just makes the progression visible.

```
poor ──────────────── Prestige 1 ──── … ──── Prestige N ──── ∞
      [era baseline 0% ▓▓▓▓▓▓░░░░ 100% = mapped set verified]
                     └ prestige gate: OPERATOR adjudication ┘
```

## The 100% basis (what the bar measures, exactly)

- **0% (baseline)** = the code at the current era boundary, as MEASURED —
  not as intended. Baseline artifacts: the era's opening commit, the boundary
  adjudication doc in `docs/quant/`, and the gate registration.
- **100%** = the cycle's improvement map fully shipped AND verified to the
  house bar (mutation/injection evidence, review, DoD — a merged-but-unpinned
  change does not move the bar). The map lives in exactly four places; the
  bar is DERIVED from them on read, never cached as a settled number:
  1. `docs/HANDOFF.md` OPEN DOCKET (boundary items — the prestige bundle)
  2. `.superpowers/sdd/progress.md` backlog + queue (session-scale items)
  3. `docs/research/*/0?_adoption_ranking.md` + `07_implementation_plan.md`
     (ranked adoptables)
  4. the owed-measurements register here in the vault ([[owed-measurements]])
- **Bar arithmetic** (re-derive, don't recall): % = verified-shipped items /
  total mapped items for the cycle, counted at read time from those four
  sources. An item added mid-cycle GROWS the denominator — the bar can move
  backward when learning reveals new work. That is the bar working, not
  failing: discovering the denominator is progress that temporarily reads
  as regression.

## Where it stands (AS-OF 2026-08-30 — PRESTIGE #2 FIRED, page reset — re-derive before citing)

**PRESTIGE #2 fired 2026-08-30T15:32:36Z** — **cut #9, the Tier-3 fee
correction, `exec_era` `9-16ec821e`**, boundary **#6** on the fill-axis
counter, minted under operator ARM scoped **"fee correction only"**.
Authoritative cut row: [[comparability-boundaries]] **table row 9**.

**Note the shape of this prestige, because it is not the shape of #1.**
Cut #8 was a bundle walked through the gate on evidence; **cut #9 is a
CORRECTION of cut #8 itself** — the era-`8-ca55e2ba` cycle was 2 days
old and had accrued nothing when the operator's Kraken screenshot proved
its founding constant was ~2x wrong. A prestige cycle can therefore be
ended by *its own baseline being falsified*, not only by its map being
completed. The bar moved forward on **truth**, not on shipped features,
and the page records that as movement because it is
([[the-method]] #1 recurrence, fired on the fee-truth epoch itself).

### The era-`8-ca55e2ba` cycle's final block, archived here (it never got its own boundary doc)

- Opened 2026-08-28T03:14:13Z; closed 2026-08-30T15:32:36Z (~2.0 days).
- 0% baseline was: commits `4e502478` + `9f0264c6`, DoD GREEN with corpus
  lines read, constants in-binary (fees **40/80**, bar **0.8335**),
  `dry_run` TRUE, SZ-023 ×42/162 cycles.
- **Movement achieved: the boundary itself, and nothing else.** Era-5
  accrual never reached its n=50 readout. Those rows stay citable **AS
  era-5** and are **SUPERSEDED** — accrued at the over-stated 40/80,
  poolable with nothing across the fee correction.
- **What the cycle actually taught** (the numerator that was not a
  feature): that a constant asserted as "conservative" and never checked
  against the account is an *instrument* claim, and the probe-dominated
  book cut #8 produced was an ARTIFACT of it, not a market fact.

### The new cycle

- **Cycle:** era-`9-16ec821e`, opened **2026-08-30T15:32:36Z** (control-plane
  `stop` 15:30:24Z, cid `1788103824.226997-67a8f6`; runner ack 15:30:25Z;
  pc_supervisor relaunch and new worker PID **7692** at 15:32:36Z; first
  RUNNING 15:32:37Z). **New 0% = this code as measured at the boundary**:
  commit **`59bdcf87`** (config write + era mint, SAME commit), fees
  **22/38** and bar **0.6772** proven in-binary from the new process's own
  startup log (`fees=22/38bps … net of 0.60% rt cost … p(win) bar=0.677
  (derived)`), `dry_run` **TRUE** untouched, full DoD green (4422 pytest /
  220 smoke / 51 assurance / 3 overfit on a **live 9468-row** corpus, not
  the synthetic fallback / ruff / bandit 0 / pyright 0-0 / compileall),
  **5 suite re-baselines, each runtime-verified, none widened**. Baseline
  artifacts: that commit, `docs/quant/2026-08-29_fee_tier_correction_adjudication.md`,
  and the **untouched** era-4 gate registration — `scripts/cohort_eval.py`
  was NOT modified by the cut, deliberately.
- **This cycle's movement so far** (all SAFE class, none touching the
  decision path):
  1. the boundary itself (operator WHAT; Claude HOW via the stager);
  2. **a 47-day silent pager outage found and FIXED, then delivery PROVEN
     end-to-end by an ORGANIC firing** (`8f27a326`) — see
     [[sources/session-20260830-audit-wave-and-external-data-atlas]] §1;
  3. the era-6 accrual count established at **4** by two independent
     routes plus a 10-case injection battery — *count only*, no
     gross/net/win-rate, per the moratorium;
  4. **new denominator, not numerator:** MLSEC-1 (the unkeyed
     `_record_hash`) is DOCKETED and unfixed, and the Grafana root-route
     trap is still armed. Both GREW the map.
- **New cycle's map (the denominator — count fresh from the four
  sources):** **QT-1** (owed 106 — its drift NARROWED to 2bps at this cut
  but the re-baseline is still owed, so G1–G5 greens are still not
  deployed-geometry evidence), **MLSEC-1** (owed 108, cohort-resetting),
  **ERA6-COUNT-1** (owed 107, SAFE), **CTRL-2**, **GB-1** (now arming
  inside an 82bps break-even buffer), **ALGO-5** (the tail-control problem
  cut #9 explicitly EXCLUDED — and the one the honest readout now points
  at), **asset discipline**, **CONC-1**; the adoption rankings
  (`docs/research/*/0?_adoption_ranking.md`); `docs/quant/2026-08-30_longterm_improvement_map.md`
  (40 ranked items, `9fdbc389`); and the owed register (104, 105, 106,
  107-111). Do NOT quote a percentage from this paragraph — count fresh;
  this stamp decays.

## Attribution — whose hand moved the bar (the hand-in-hand contract)

- **Operator owns WHAT and the gates:** directives, adjudications, boundary
  timing, prestige itself. No bar segment crosses a boundary without the
  operator's signature. Operator moves this session: the research directives,
  the divergence latitude that produced the control-arm, the sign-offs,
  auto-push, this bar.
- **Claude owns HOW inside the fences:** instruments, verification,
  SAFE-class shipping, the honest denominator. Claude's share is only
  countable in VERIFIED units — an unreviewed change is not a contribution
  yet.
- **The learning cycle** (each loop feeds the next): operator directive →
  Claude measures/builds → instruments surprise us → findings enlarge the
  map (denominator grows) → vault files the knowledge → next session starts
  smarter → operator adjudicates with better evidence → prestige → new
  baseline. The 2026-08-27 session ran this loop end-to-end: a veto-counter
  feature became an instrument-defect discovery, became a hardened guard,
  became the control-arm prototype, became a prestige-bundle item — each
  step filed, each step raising both the numerator and the denominator.

## Update contract (like HANDOFF's — the page is a router, not an archive)

At the end of any session that moves the bar: re-stamp the AS-OF section
(or delete what you did not verify), add one line to the movement list with
its commit/record, and file new denominator items in their proper source
(docket/ledger/rankings/owed) — never here. When a prestige fires, archive
the cycle's AS-OF block into the boundary's dated doc and reset this page
to the new baseline. Percentages are always derived-on-read; a number
written here is a pointer to a derivation, never a fact.
