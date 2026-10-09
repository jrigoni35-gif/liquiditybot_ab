---
title: "The apply-batch (66744ed1, 2026-08-11) — owed 68 CLOSED at the writer, owed 69 INSTRUMENTED, orientation pins, the stale-fee note lands in config, and a NOT-applied register"
category: source
summary: "The disposition batch for the since-6am audit's findings (commit 66744ed1, battery 19 GREEN, 3602 tests, deployed, runner verified back). (1) OWED 68 CLOSED — the long-book entry path computed _feature_extras and DISCARDED it, so meta never carried avail and every long-book live row shipped blank avail_*/quotes_frozen; fixed by threading meta[\"avail\"] from the SAME extras dict the features were built from (main.py long-book entry, feature-build-instant semantics), pinned in tests/test_long_book_integration.py; the audit's two blank ETH/BTC rows were ALSO explained by entry-time tuple shape (registered before avail existed) but the writer defect was real and current. (2) OWED 69 INSTRUMENTED, still open — defensive_cadence_report.py §2b: momentum-alignment win rates with the side-relative caveat printed and lifetime-POOLED vs since-capital-epoch tables; first run (h432-only, pooled, context only): the anti-momentum gradient is MONOTONE both directions (longs with/flat/against 30.9%/35.3%/41.8% n=194/184/158; shorts 25.9%/37.1%/47.4% n=197/159/78), STEEPER than the audit's all-era numbers, and the post-epoch clean cohort (n=36) currently leans OPPOSITE (longs-with 81.8% n=11) — a LEAD until clean accrual is real. (3) Orientation pins in tests/test_ofi_feature.py: basis_bps Kraken-cheap-positive, venue_disloc_bps Kraken-rich-positive, pinned by subtraction order — harmonizing either sign is a feature-meaning change under the MODEL FREEZE requiring an adjudicated retrain. (4) The stale-fee note lands IN config.json market_maker: min_half_spread_bps=26 descends from the STRUCK 16/26 schedule; retuning is quote-pricing = cohort-resetting, HELD with the fee constants behind the h432 gate. (5) NOT-applied register, deliberate: _dir column renames (corpus schema churn under freeze), venue_disloc sign flip (frozen feature meaning), majors' cost-floor un-flattening (stop geometry — ALGO-5 amendment scope, owed 67)."
tags: [session, fix-batch, long-book, corpus-schema, instrumentation, features, fees, model-freeze, not-applied]
sources: 1
source_path: "commit 66744ed1 (battery 19 GREEN, 3602 tests, deployed, runner verified), main.py long-book entry, tests/test_long_book_integration.py, scripts/defensive_cadence_report.py §2b, tests/test_ofi_feature.py, config.json market_maker"
source_date: 2026-08
authors: [operator, session-agents]
ingested: 2026-08-10
updated: 2026-08-10
---

# The apply-batch (66744ed1, 2026-08-11)

**What this is.** The apply session for the since-6am audit's open items
([[sources/session-20260811-operator-audit]]): commit `66744ed1`, **battery 19 GREEN, 3602
tests**, deployed, **runner verified back**. Two docket movements (68 closed, 69
instrumented-still-open), two hardening moves (orientation pins, the stale-fee note at its
propagation source), and — filed with equal weight — a register of what was **deliberately
NOT applied** and why.

**Boundary statement** ([[concepts/paper-real-boundary]]): every change is **repo-side**
(writer code, tests, an instrument, a config annotation). The §2 win-rate numbers are
**sim-side label-space**, pooled across comparability cuts except where the post-epoch table
is named — nothing here is venue truth, and nothing here moves the freeze, the gate, or any
boundary ([[synthesis/comparability-boundaries]] unchanged).

## §1 — OWED 68 CLOSED: the long-book writer computed the answer and threw it away

The audit filed owed 68 as "long-book live rows missing post-migration schema columns." The
fix sharpened the diagnosis: **the long-book entry path computed `_feature_extras` and
DISCARDED it** — the extras dict holding availability context was built for the features and
never handed to the row writer, so `meta` never carried `avail` and **every long-book live
row shipped blank `avail_*`/`quotes_frozen`**. Not a missing schema source; a computed value
dropped on the floor between two call sites.

**The fix:** `meta["avail"]` now threads from the **SAME extras dict the features were built
from** (main.py long-book entry) — **feature-build-instant semantics**, so the row's
availability columns describe the exact instant its features describe, not a re-read.
**Pinned in `tests/test_long_book_integration.py`.**

**The audit's two exhibits were overdetermined, and that is worth keeping:** the two blank
ETH/BTC rows the audit found were **ALSO** explained by entry-time tuple shape — those
positions were registered **before `avail` existed** in the tuple at all. Both explanations
are true; the writer defect was **real and current** independent of the legacy rows, which is
why the audit's anomaly survived its first alternative explanation. (Cf.
[[concepts/adversarial-verification]] — the disposition got its own adversarial pass per
[[synthesis/governance-doctrine]] rule 16 before closing.)

History is **not rewritten**: existing blank rows stay blank (nothing-is-ever-deleted); only
the writer is fixed, exactly as the docket item's close terms specified. The long-book
population remains never-pooled on the record axis for rows predating this commit
([[entities/long-book]]).

## §2 — OWED 69 INSTRUMENTED, still open: the anti-momentum pattern gets its instrument

`defensive_cadence_report.py` **§2b** now reports momentum-alignment win rates with the two
audit caveats built into its output rather than left to the reader's discipline:

- the **side-relative caveat is printed** on the report's face
  ([[concepts/side-relative-features]] — no future reader consumes the split without the
  convention in view);
- **lifetime-POOLED and since-capital-epoch tables print separately**
  ([[concepts/pooled-populations]], [[synthesis/comparability-boundaries]] — the pooled
  number can never again be quoted without its clean-cohort neighbor).

**First-run numbers (h432-only, pooled across cuts — CONTEXT ONLY, not a finding):**

| cohort | with momentum | flat | against momentum |
|---|---|---|---|
| **longs** | 30.9% (n=194) | 35.3% (n=184) | 41.8% (n=158) |
| **shorts** | 25.9% (n=197) | 37.1% (n=159) | 47.4% (n=78) |

The anti-momentum gradient is **MONOTONE in both directions** — and **STEEPER** than the
audit verifier's all-era pooled numbers ([[sources/session-20260811-operator-audit]] §2:
21.8/22.6 longs, 17.5/21.4 shorts on the bigger pool). But the **post-epoch clean cohort
(n=36 total) currently leans OPPOSITE** — longs-with at **81.8% (n=11)** — which is exactly
why the docket item exists: the pooled gradient and the clean cohort disagree at
uninterpretable n, so **owed 69 stays OPEN and the pattern stays a LEAD** until clean accrual
is real. No consumer is authorized; the moratorium and
[[synthesis/evidence-closed-register]] checks stand as written on the docket item.

## §3 — Orientation pins: the anti-oriented pair is now held by tests, not prose

The audit's §4 recorded that `venue_disloc` and `basis` point opposite ways **by documented
design**. That documentation was prose; it is now **pinned in
`tests/test_ofi_feature.py`**:

- **`basis_bps` is Kraken-cheap-positive**, **`venue_disloc_bps` is Kraken-rich-positive**,
  and both are pinned **by subtraction order** — the tests assert the sign of the actual
  arithmetic, not a label, so a well-meaning "harmonization" flips a test, not just a
  meaning.
- **Harmonizing either sign is a feature-meaning change under the MODEL FREEZE** and
  requires an **adjudicated retrain** — the model learned these orientations; flipping one
  silently feeds the frozen model mirrored inputs
  ([[synthesis/governance-doctrine]] rule 17 territory, filed on
  [[concepts/side-relative-features]]).

## §4 — The stale-fee note lands where the propagation starts

The audit demonstrated that the **struck 16/26 Kraken schedule still propagates out of
`config.json`'s own rationale** — a fresh 7-agent audit reproduced it
([[concepts/cost-truth]], [[synthesis/documentation-drift-register]]). This batch puts the
flag **at the source**: a stale-fee note added to **`config.json` `market_maker`**, recording
that **`min_half_spread_bps=26` descends from the STRUCK 16/26 schedule** — a surface not
previously on the falsified-schedule map (the quote floor, not the fee constants).

**Deliberately NOT retuned:** changing `min_half_spread_bps` is **quote-pricing**, which is
**cohort-resetting** — it is **HELD with the fee constants behind the h432 gate**
([[concepts/cost-truth]]'s sequencing, owed 37; [[synthesis/governance-doctrine]] rule 17).
The note exists so the next reader of the config inherits the correction instead of the
falsified premise.

## §5 — The NOT-applied register (deliberate, with reasons)

Filed with the same weight as the fixes, so none is rediscovered as an omission:

| Not applied | Why |
|---|---|
| **`_dir` column renames** | **Corpus schema churn under the freeze** — renaming persisted feature columns rewrites the corpus's vocabulary mid-freeze for a readability gain the reading rule already covers ([[concepts/side-relative-features]]). |
| **`venue_disloc` sign flip** | **Frozen feature meaning** — the model learned the anti-orientation; flipping it is a feature-meaning change requiring an adjudicated retrain (§3). The pins now make the non-flip enforceable. |
| **Majors' cost-floor un-flattening** | **Stop geometry** — the audit's finding that the bracket cost floor flattens majors to identical 1.50/2.00 sl/pt is real, but changing it is geometry work: **ALGO-5 amendment scope (owed 67)**, the pre-named next boundary-minting adjudication — not this batch's. |

## Standing-question check

Does this batch move any of the five standing questions? **No — by design.** The freeze,
the gate, the nulls, the levers, and the boundaries are all untouched; §4 and §5 are this
batch declining to touch them, in writing.

## Related
[[sources/session-20260811-operator-audit]] · [[synthesis/owed-measurements]] ·
[[entities/long-book]] · [[concepts/side-relative-features]] · [[concepts/cost-truth]] ·
[[concepts/pooled-populations]] · [[concepts/adversarial-verification]] ·
[[synthesis/comparability-boundaries]] · [[synthesis/governance-doctrine]] ·
[[synthesis/documentation-drift-register]] · [[synthesis/evidence-closed-register]] ·
[[sources/session-20260811-cut7-geometry-epoch]]
