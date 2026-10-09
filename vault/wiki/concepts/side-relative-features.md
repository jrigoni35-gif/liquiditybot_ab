---
title: "Side-Relative Features (a raw row is unreadable without knowing the trade's side)"
category: concept
summary: "The *_dir feature columns are computed relative to the trade's SIDE (ml/features.py:109-115, dir_sign applied at :342): a short row persists the sign-flipped derivative by construction, so any raw corpus read that does not condition on side prints 'backwards' derivatives for every short — and the _dir suffix compounds the hazard by suggesting a [-1,1] flag when the values are unbounded vol-normalized returns (±6 is normal). Type specimen: the 2026-08-11 backwards-derivative audit, where the operator's inversion claim decomposed entirely into this convention plus the fact that no candidate leaderboard exists to sort backwards (round-robin _entry_assets, main.py:3911-3921) — NO-INVERSION-FOUND, 0/3 adversarial refuters. The rule: condition on side before reading any side-relative column, and treat a deliberately anti-oriented pair (venue_disloc_dir vs basis_dir) as documented design, not evidence. Since 66744ed1 the pair's orientations are PINNED by subtraction order in tests/test_ofi_feature.py (basis_bps Kraken-cheap-positive, venue_disloc_bps Kraken-rich-positive) — harmonizing either sign is a feature-meaning change under the MODEL FREEZE requiring an adjudicated retrain, and both cosmetic cures (sign flip, _dir renames) were deliberately declined in the apply-batch's NOT-applied register"
tags: [features, conventions, reading-hazard, verification, ml]
sources: 2
updated: 2026-08-10
---

# Side-Relative Features

## The convention

The model's `*_dir` feature columns are **side-relative**: the raw market derivative is
multiplied by `dir_sign` (`ml/features.py:342`, features defined at `:109-115`), so the
persisted value answers *"is the market moving WITH this trade?"* — not *"which way is the
market moving?"* A **short** row therefore stores the **sign-flipped** derivative of what the
tape did. This is a deliberate modeling choice (the model learns one relation instead of two
mirrored ones), and it makes every raw row **unreadable without the `side` column in hand**.

## The two hazards it manufactures

1. **The pooled raw read.** Scan corpus rows without conditioning on side and every short
   prints a "backwards" derivative. Enough shorts in view and the whole feature bank looks
   inverted. *(This is [[concepts/pooled-populations]] operating in feature space — the
   pooled view shows a pattern that exists in neither sub-population.)*
2. **The name.** The `_dir` suffix reads as a direction flag in [−1, 1]; the values are
   **unbounded vol-normalized returns** — ±6 is a normal print, not a saturated flag. A
   reader who expects a flag sees "impossible" values and reaches for a bug that is not
   there. *(The naming half is [[synthesis/governance-doctrine]] rule 14's territory — a
   house term that does not mean what an unbiased reader would take it to mean.)*

## The type specimen: the backwards-derivative audit (2026-08-11)

([[sources/session-20260811-operator-audit]] §1.) The operator, reading raw rows, concluded
the derivatives were backwards — that the bot was sorting its candidates in reverse. Three
adversarial refuters (recompute, consumption, and data lenses) were instructed to **find the
inversion**; **0 of 3 succeeded** — **NO-INVERSION-FOUND at high confidence**. The claim
decomposed into exactly this page's two hazards **plus one architectural fact**: there is
**no candidate leaderboard to sort backwards** — asset selection is a round-robin over
`_entry_assets` (`main.py:3911-3921`), so no ranking exists whose order an inverted feature
could reverse.

> **The adjudication is binding** ([[concepts/evidence-grading-ladder]] discipline): an
> apparent inversion seen in raw corpus rows is not a finding until it survives conditioning
> on `side`. The killing citation is the 0/3 refuter record.

## The one deliberately anti-oriented pair

`venue_disloc_dir` is oriented **kraken-rich positive** while `basis_dir` is **kraken-cheap
positive** — the closest real thing to a backwards derivative in the codebase, and it is
**documented intended, model-input-only** (no decision path consumes the raw sign). A
sign-convention disagreement between two features is design as long as it is written down and
nothing but the model reads them; it becomes this page's hazard the moment a human quotes
either sign without the orientation note.

**Since `66744ed1` the orientations are PINNED, not just documented**
([[sources/session-20260811-apply-batch]] §3): `tests/test_ofi_feature.py` asserts
**`basis_bps` Kraken-cheap-positive** and **`venue_disloc_bps` Kraken-rich-positive** **by
subtraction order** — the pin holds the arithmetic, not a label, so a well-meaning
"harmonization" flips a test rather than silently flipping a meaning. **Harmonizing either
sign is a feature-meaning change under the MODEL FREEZE requiring an adjudicated retrain**:
the frozen model learned these orientations, and a flipped input feeds it mirrored data with
no error raised. The same batch **deliberately declined** both cosmetic cures — the
`venue_disloc` sign flip (frozen meaning) and the `_dir` column renames (corpus schema churn
under the freeze) — so the reading rule below, not a rename, remains the mitigation
([[sources/session-20260811-apply-batch]] §5).

## The rule

**Condition on side before reading any side-relative column; check the orientation note
before comparing any two `_dir` signs.** And when a raw read still looks inverted after both,
the next step is an adversarial refuter hunting FOR the inversion
([[concepts/adversarial-verification]]) — the 2026-08-11 audit is the worked example, and its
failed data-lens refuter is also the demonstration that a genuine refutation attempt pays
even when it fails: it surfaced the symmetric anti-momentum pattern
([[sources/session-20260811-operator-audit]] §2, owed 69 — since `66744ed1` instrumented in
`defensive_cadence_report.py` §2b **with this page's caveat printed on the report's face**,
still open pending clean-cohort accrual).

## Related
[[sources/session-20260811-operator-audit]] · [[sources/session-20260811-apply-batch]] ·
[[concepts/pooled-populations]] · [[concepts/adversarial-verification]] ·
[[concepts/evidence-grading-ladder]] · [[synthesis/governance-doctrine]] ·
[[entities/liquiditybot]]
