# Building the boundary around the most consistent edge

*Operator directive 2026-08-22: "build the boundaries around the most
consistent edge." This document answers, from measurement, WHICH edge is
most consistent — and derives the boundary design from that answer
rather than from preference.*

## 1. The trap this document nearly walked into

Re-running `scripts/gate_efficacy_report.py` today produces a headline
that did not exist four days ago:

```
2026-08-18:  baseline 26.5%  admitted 24.7% (n=2100)  separation -1.9%  "selects AGAINST itself"
2026-08-22:  baseline 26.5%  admitted 35.8% (n=3101)  separation +9.3%  "selects WINNERS" (significant)
```

Read naively: the entry gate became good. **It did not.** The admitted
pool grew by 1,001 rows *through the melt-up*, and the melt-up made
almost everything a winner (window base rate 0.613 vs 0.262 elsewhere).
The same compositional effect that inflated the crisis rows to a false
+34.8pp — dismantled at n_eff 11.89 in
`2026-08-22_crisis_counterfactual_REG6_evidence.md` — inflated the
admitted pool too. `SZ-021: regime crisis` now prints **ANTI-SELECTIVE
+34.8%** in the same table, which is the *identical* artifact wearing
the opposite sign.

A four-day flip from "selects against itself" to "selects winners,
significant" is not a strategy improving. It is a measurement moving.

## 2. The actual test of consistency: invariance under the shock

The melt-up is a natural experiment. A statistic that means something
should hold its value when the market changes underneath it; a
statistic that is an artifact of composition should move. Comparing the
two runs across the event:

| disposition | 08-18 | 08-22 | verdict |
|---|---|---|---|
| **SZ-030 net-Kelly f\* ≤ 0** | 6.0%, n=1052, −20.6pp | **6.0%, n=1052, −20.6pp** | **INVARIANT** |
| **SZ-046** | 16.0%, n=487, −10.5pp | **16.0%, n=487, −10.5pp** | **INVARIANT** |
| SZ-023 low-p rungs (0.69 bar) | 5.9–19.8%, −6.7..−20.7pp | 5.9–19.8%, −6.7..−20.7pp | **INVARIANT** |
| baseline | 26.5%, n=2061 | 26.5%, n=2061 | invariant (reference) |
| SZ-020 cooldown | 15.3%, n=288 | 19.1%, n=309 | moved |
| SZ-022 bear-blocks-long | 22.0%, n=1657 | 30.0%, n=1900 | **moved a lot** |
| SZ-045 | 30.6%, n=333 | 40.1%, n=469 | **moved a lot** |
| **admitted** | 24.7%, n=2100 | **35.8%, n=3101** | **moved most** |

The pattern is unambiguous. **The cost-aware rejection stack did not
move at all** — same n, same rate, same separation, through a 20%
two-day move in the majors. Not one new row entered SZ-030 or SZ-046.
Everything on the admission side moved, and moved in the direction the
tape moved.

## 3. The most consistent edge, named

> **The bot's demonstrated, regime-invariant skill is knowing what NOT
> to trade — specifically the cost-aware vetoes: net-Kelly f\* ≤ 0
> (SZ-030) and the low-p rungs against the derived breakeven bar
> (SZ-023).**

Those rules reject trades that go on to win ~6% of the time against a
26.5% baseline — a −20.6pp separation that survived a regime shock
without shifting a decimal. Nothing on the entry-selection side has ever
demonstrated that stability; its apparent quality tracks the tape.

This is consistent with every other measurement on file: the geometry
has no gross edge (target hit 22.6% vs 42.9% breakeven), the champion
loses to the base-rate null OOF, and 97% of the corpus is
counterfactual. The system's competence is **exclusion**, and it always
has been.

## 4. The boundary design that follows

A boundary should be drawn so the invariant thing is preserved and the
volatile thing is what changes. Concretely, for execution-era boundary
#6:

**PROTECTED — do not touch, do not "improve", do not re-tune:**
- `SZ-030` net-Kelly f\* ≤ 0 and its inputs (the net-Kelly computation,
  the fee/cost stack it reads).
- `SZ-023` and the DERIVED p-bar (`p_bar_mode: derived`, pinned to
  geometry rather than an absolute literal — the 2026-07-27
  de-phantomization). Its derivation is why the rungs are invariant;
  an absolute bar would drift with the tape.
- `SZ-046`.
Any docket item that would alter these must state so explicitly and
carry its own justification. None currently does.

**ELIGIBLE — this is where boundary #6 spends its budget:**
- **REG-8 v2** — deletes the turbulence clause, which the evidence shows
  measures atypicality rather than danger. It touches *no* protected
  rule: SZ-030/023/046 are untouched by construction.
- **REG-7** — taxonomy/occupancy (labels and strata, not cost vetoes).
- **SWEEP-0/1** (CRITICAL) — hedge de-risk coordination, margin-health
  fail-open. Correctness fixes, orthogonal to the veto stack.
- **ALGO-5** — stop widths / time-decay ladder (exit geometry).
- **LS-1/LS-2** — feature-importance verification, uncertainty sizing.

**The ordering principle:** changes that *remove a rule shown to measure
the wrong thing* (REG-8) rank above changes that *add* anything, and
both rank above anything that would perturb an invariant rule.

## 5. Why REG-8 v2 is the right first cut

It satisfies the principle exactly: it is a **deletion**, it touches
nothing in the protected set, and the rule it removes is the only veto
in the table that is measurably *anti*-selective for a reason we have
mechanically explained (a rank that cannot say "calm", firing at 7% on
pure noise, measuring co-movement atypicality rather than stress). It
also *returns* the two useful signals — turbulence-as-uncertainty and
breadth-as-danger — to organs that already exist (`monitor.shrinkage`,
`RiskProtocolStack`), so the foundation deepens while the surface
shrinks.

## 6. The standing caution

`SZ-022 regime bear blocks long` moved from −4.6pp to **+3.5pp** across
the event — it now reads as mildly *anti*-selective. Do not act on that.
It is the same compositional artifact as the admitted pool, and REG-7
already holds the honest version of that question (the label is
misnamed: 38–52% occupancy at the 8th percentile of volatility is quiet
drift, not bear tape). Re-measure it at the readout on a
regime-stratified basis, with effective n.

## 7. Re-measurement protocol (so this document does not decay)

Every claim above is a comparison of two runs of the same tool across
one event. It must be re-run at the era-4 readout, stratified by the
crisis stamp, on effective n. If SZ-030 and SZ-046 remain invariant
across a *second* independent regime change, the protected set is
confirmed. If they move, this document's central claim is falsified and
the boundary design must be redrawn — say so out loud rather than
quietly keeping the conclusion.
