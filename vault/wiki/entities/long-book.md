---
title: The Long Book
category: entity
summary: "A patient accumulation book resting bids for hours on a wider cadence, with a named-and-closed self-trade risk — and a by-design −50.0bps slip signature that must not be mistaken for fixture data. Second reading 2026-08-07: the orders are real, but in dry-run their FILLS were sim gifts — the per-poll hazard calibrated for 25s orders compounded to ≈1.0 over this book's 6h TTL. Third reading 2026-08-08: owed 40 LANDED (3cfe0710, execution-era boundary #3) — from the 11:10 boot every long-book order is priced by the TTL-normalized honest simulator; the compounding gift is dead, pre-boundary fills stay uncitable. FOURTH reading 2026-08-10 (aeeaae36, era boundary #4): the third reading's "conservative floor" clause is RETRACTED - the hazard ran only inside `if book:` and reproduced the measured crossing rate by itself, so stacking it on _sim_maker_cross spent that frequency twice (2f-f^2 = 21.96% vs an 11.66% target, ledger 22.30%, 1.88x at the touch). This book is the worst-affected population by construction because its design is to REST, and the distortion is worst exactly where orders rest. Every long-book fill in the corpus is pre-boundary-#4; the -50bps signature has now been read four ways in eight days, so treat this book's fill statistics as never yet measured under a simulator that survived its next audit. FIFTH note, the 2026-08-11 since-6am audit, on the RECORD axis: long-book live corpus rows are missing post-migration schema columns (owed 68), and the two long-book flatten closes (ETH d5513dd5 / BTC e35c0a59) had no thesis at close so postmortem undercounted them — fixed forward-only with degraded orphan_close path rows. Owed 68 CLOSED at the writer by 66744ed1 (apply-batch): the entry path computed _feature_extras and DISCARDED it, so every long-book live row shipped blank avail_*/quotes_frozen; meta[avail] now threads from the same extras dict the features were built from, pinned in test_long_book_integration.py — pre-fix rows stay blank and never-pooled."
tags: [subsystem, execution, compliance, paper-mode]
sources: 8
updated: 2026-08-10
---

# The Long Book

A slow accumulation book operating alongside the fast 5-minute book, resting bids for hours rather than
seconds.

## Cadence controls
Reprices at most once per ~30s pass per asset, and only once the bid has drifted past a **staleness
band** (~0.85% combined). Each resting bid carries a multi-hour TTL rather than the fast book's ~25s
timeout. Every reprice is audit-coded.

## The self-trade risk, named and closed
The long book can rest a same-pair BUY for hours while the fast book's exit-escalation ladder or a
marketable sell reaches down through the book — **a literal self-fill, or the venue's self-trade
prevention cancelling the escape leg instead of the entry**.

Fix: cancel our own resting bid **first** before any non-post-only sell, wired into **four call sites**.
A post-only maker exit is **deliberately exempt** — "a resting ask can never cross the book, so
passive-passive same-pair quoting is bona fide two-sided market making." **Cancel failure never blocks
the sell**; venue self-trade prevention is the documented backstop for the residual race.

## Standing obligation
> **"Any future book that rests entries for hours must be wired into the same guard before ARM LIVE."**

## The −50.0bps slip signature is design (classified benign 2026-08-03)
Fills-ledger entries with slip of **exactly −50.0bps** are this book's accumulation adds:
`add_offset_pct=0.5` **rests bids 0.5% below mark by design**, so a fill at the resting price
records an exact ref-multiple. The config's `_entry_doc` records the offset's **1.5 → 0.5 collar
history**. The 2026-08-03 bug sweep audit-verified the `order_id`s against the hash-chained
`audit.jsonl` — **NOT fixture data**, despite sharing the exact-ref×constant arithmetic shape
with the QA fixture fills ([[sources/session-20260803-bug-sweep]]). The citation hazard —
arithmetic shape alone cannot distinguish a resting offset from a fabrication; only the audit
chain can — is filed under [[concepts/iron-law-of-debugging]].

## The signature's second reading (2026-08-07) — the orders are real, the FILLS are gifts
The 08-03 classification stands at the layer it was made: the **orders** are genuine long-book
adds, not fixtures. What the 2026-08-07 fleet sweep added is the layer above
([[sources/session-20260807-fleet-findings]] §1): in dry-run, the **fill probability** of those
resting bids is manufactured — the per-poll `sf_base=0.048` hazard was **calibrated at n_bar=5
polls (25s orders)** and this book's bids live **6h ≈ 4,320 polls**, compounding to fill
probability **≈1.0**, stacked on a deterministic trade-through path with **no depth or queue
constraint**. Verified in the ledger: since 08-03 UTC, **22 of 41 entry fills at exactly
−50.0 bps** (+2 at −58.7), all `post_only=1`, **BTC 13 / ETH 9** — and those two assets are the
book's worst by expectancy *even so* (BTC 0/17, ETH 3/26). So: **benign as provenance, skewed
as evidence** — a long-book paper fill says nothing about real fill quality until owed item 40
(the TTL-aware hazard fix, [[synthesis/owed-measurements]]) lands. Both classifications are
correct; they answer different questions ([[concepts/paper-real-boundary]]).

## The third reading (2026-08-08) — owed 40 landed; the gift is dead

Commit `3cfe0710` (**execution-era boundary #3**, deployed on the 11:10 boot —
[[sources/session-20260808-morning-batch]] §1): `_passive_poll_prob` TTL-normalizes the
passive hazard — `p = 1−(1−sf_base·exp(−d/σ))^min(cal_life/ttl, 1.0)` — so this book's 6h bids
now carry the **same per-order fill probability the calibration measured at 25s**, not a
compounded certainty; per-poll hazard on a 6h order is ~864x smaller than before. The
calibrated F(25s) acts as a **conservative floor**; genuine trade-through
(`_sim_maker_cross` against the live book) still fills a resting bid whenever the market
actually crosses it — by design, that path stays. **Every long-book order placed from this
boot is priced by the honest simulator.** Two standing qualifications: (1) fills dated before
2026-08-08 were made under the compounding simulator and remain uncitable — cohort statistics
must cut at the boundary; (2) honest ≠ real — the fill is still simulated, only no longer
flattered ([[concepts/paper-real-boundary]] rule 4). Whether real 6h resting orders fill above
or below the F(25s) floor is XV-023 (owed 40b), open until `calibrate_fills` gains long-life
recordings.

## The fourth reading (2026-08-10) — the gift was not dead, it was half dead

`aeeaae36` (**execution-era boundary #4**, [[sources/session-20260810-fill-double-count]]) found
that the third reading above was **premature on one clause**. *"The calibrated F(25s) acts as a
conservative floor"* — the sentence directly above — **is retracted.**

The hazard was **not a floor**. It ran **only inside `if book:`**, so it modelled nothing the
observed snapshot could already show, and `invert_base_prob` had already solved `sf_base` so
**the hazard alone reproduces the measured crossing rate `f`**. Stacked on top of
`_sim_maker_cross` — which fires on **that same crossing** — it did not add conservatism; it
**spent the calibrated frequency twice**: `2f−f² = 21.96%` against an `f = 11.66%` target, against
a ledger-measured **22.30%**. **1.88x at the touch, approaching 2x as f falls.**

**This book is the worst-affected population by construction.** Its whole design is to **rest**
rather than cross — `add_offset_pct = 0.5` puts entries 50 bps back — and the distortion is
**worst exactly where orders rest**. The blast-radius figures say so: **57.2% of all 402
`post_only` fills rest within 5 bps**, and **154 of 401 positions (38.4%)** were opened by a
near-touch `post_only` leg.

> **The sequence for this page, stated plainly, because it is the useful part:** the −50 bps
> signature was read as **benign** (08-03), then as **sim-manufactured** (08-07), then as
> **repaired** (08-08), and is now **repaired for the second time** (08-10). Three of those four
> readings were filed with confidence. **The correct posture toward this book's fill statistics is
> that they have never yet been measured under a simulator that survived its next audit** — and
> the current one has not been audited yet either.

**Every long-book fill in the corpus is pre-boundary-#4.** The last ledger row predates the commit
(`2026-08-10T06:50:23.746Z` vs `2026-08-10T11:03:35Z`), so there is **no post-boundary sample**
to compare against; the runner bounced onto the corrected code at 06:06:01 local and the next fill
is the first honest one. And **owed 61** now applies here specifically: MP-7 queue gating is
**inert**, so `_sim_maker_cross` fills this book's full remaining **with no depth constraint** —
the one remaining way the simulator is kinder to a resting order than a venue would be.

## The record-keeping edge (2026-08-11 since-6am audit)

([[sources/session-20260811-operator-audit]] §6.) Two findings put this book on the
**corpus-hygiene** map as well as the fill-sim one:

- ~~**Long-book live rows are missing post-migration schema columns — OPEN, owed 68**~~
  **CLOSED at the writer, `66744ed1`** ([[sources/session-20260811-apply-batch]] §1,
  [[synthesis/owed-measurements]] item 68): the diagnosis sharpened — the long-book entry
  path **computed `_feature_extras` and discarded it**, so `meta` never carried `avail` and
  every long-book live row shipped **blank `avail_*`/`quotes_frozen`**. Fixed by threading
  `meta["avail"]` from the **same extras dict the features were built from**
  (feature-build-instant semantics), pinned in `tests/test_long_book_integration.py`. The
  audit's two blank ETH/BTC exhibit rows were **also** explained by entry-time tuple shape
  (registered before `avail` existed) — both true; the writer defect was real and current.
  **History is not rewritten:** rows predating `66744ed1` stay blank, so the never-pooled
  caution on the record axis still applies to the pre-fix population.
- **The two flatten closes were postmortem-invisible — FIXED.** The long-book flatten closes
  **ETH `d5513dd5`** and **BTC `e35c0a59`** carried no thesis at close, so the postmortem /
  trade-path writers produced no row at all ([[concepts/uncounted-exclusion]], orphan-close
  instance); `ml/postmortem.py` now writes **degraded `orphan_close` path rows** — named,
  not omitted.

## Its research dependency
The accumulation thesis is explicitly **not** supported by any reversion anomaly: "no robust
peer-reviewed multi-month result verifiable," so "the long book's accumulation thesis must rest on the
structural-context gates." And a hard behavioral rule applies: **"NEVER add a chase/urgency path to the
long book."**

## Related
[[sources/compliance-market-conduct]] · [[entities/config-guard]] ·
[[concepts/who-loses-to-us]] · [[sources/session-20260807-fleet-findings]] ·
[[sources/session-20260808-morning-batch]] · [[sources/session-20260810-fill-double-count]] ·
[[concepts/paper-real-boundary]] · [[comparisons/dormant-vs-inert-features]] ·
[[synthesis/owed-measurements]] · [[sources/session-20260811-operator-audit]] ·
[[sources/session-20260811-apply-batch]] · [[concepts/uncounted-exclusion]]
