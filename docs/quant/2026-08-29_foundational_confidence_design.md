# Foundational Confidence (FC) — the non-emotional-trader confidence system

Operator directive 2026-08-29: "create a new logarithmic equation for
confidence — a more complex system than confidence, with real reasoning; that
creates compound improvement; with parameters for degradation to prevent
deadlock. The 'non-emotional trader' phases out individual wins and losses and
sticks to the foundation that led them to derive what a win/loss came from, how
it got documented, what it led to and why."

Delivered as `ml/foundational_confidence.py` — a **SHADOW instrument**
(measurement only, wired into no decision path; that would be model
development, frozen 2026-08-10), pinned by `tests/test_foundational_confidence.py`
(10 pins, mutation-killed).

## What it is, and why it is not just "confidence"

Ordinary confidence tracks an OUTCOME rate (win %). FC tracks a **FOUNDATION**
— the causal thesis that led into the trade — and asks whether that thesis is
*earning its keep*. The P&L sign alone never moves it. This is the non-emotional
trader made mechanical: you do not celebrate a win or mourn a loss; you ask
*was my reasoning validated, and why*, and you document it.

## The three coupled ideas (the equations)

**1. Log-odds — the logarithmic equation that compounds.** Confidence in a
foundation F is carried as log-odds `L = ln(P(F valid)/P(F invalid))`. Evidence
is Bayesian and **additive** in log space: `L ← L + w·llr`. Because updates
ADD, a foundation that keeps being validated **compounds** its confidence
linearly in the count of effective, attributed confirmations. Confidence is the
logistic `C = σ(L) = 1/(1+e^-L) ∈ (0,1)`.

**2. Attribution × independence — the real reasoning (the non-emotional core).**
The weight `w = attribution · independence`:
- **attribution `a ∈ [0,1]`** — how much this outcome was *caused by F's
  mechanism* vs external/noise/beta. `a=0` ⇒ the outcome is uninformative about
  F, so a loss *despite* the thesis does not tank it. This is the documented
  WHY.
- **independence `u ∈ (0,1]`** — the effective-n weight. Correlated/overlapping
  trips carry less evidence; you cannot compound confidence out of correlated
  observations (the n_eff ceiling the session measured — nominal is 12–16×
  optimistic).

**3. Degradation — the anti-deadlock parameters.** Absent fresh evidence, `L`
decays toward the prior 0 with a half-life τ (default 1 week):
`L ← L·exp(-Δt·ln2/τ)`, and `L` is clamped to `[L_FLOOR, L_CEIL] = [-4, +4]`.
Together these break the learning-paradox deadlock two ways:
- A once-*invalidated* foundation decays back UP toward "I don't know" → the
  system **re-tests** it instead of locking it out forever; a once-*validated*
  one decays back DOWN → it must **keep earning** instead of locking in stale
  over-confidence.
- The floor guarantees confidence never collapses to "never act" — it bottoms
  out at a small *willing-to-test* level (σ(-4)≈0.018), so an unprovable edge is
  probed at small size and left to compound *if it is real*, rather than vetoed
  into a deadlock.

## Unit safety (operator directive: context and proportion)

`observe()` takes `llr` in **nats**; the only sanctioned way to produce it is
`llr_binary(p_foundation, p_baseline, won)` — contextual (measured against a
baseline), proportional (a ratio), dimensionless. A raw return (%) or P&L ($)
must **never** be fed in — mixing units into a log-odds accumulator is
meaningless, and both probabilities are clamped off {0,1} so no single outcome
claims certainty.

## Where it fits the profit balance ("like a neural network")

FC is the honest-confidence layer the balance's SANITY plane must consume: it
supplies per-foundation confidence that is *earned, attributed, and degraded*,
so the gate admits on real (n_eff-honest, non-stale) conviction and never
deadlocks. It is a SHADOW score today; wiring it into sizing (fractional-Kelly
on `combine(...)`) is a COHORT-RESETTING change owed to the era-mint bundle,
not this SAFE instrument.
