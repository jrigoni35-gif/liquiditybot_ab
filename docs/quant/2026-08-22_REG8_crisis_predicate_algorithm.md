# REG-8 v2 (pre-registered 2026-08-22): dissolve the crisis gate

*Supersedes REG-6 (momentum-sign split — discriminator falsified by its
own pre-registered evidence) and REG-8 v1 (three new gates — rejected by
operator directive 2026-08-22: "integrate it all into the system instead
of adding more gates; minimize additional complexity; make the
foundation we have more complex and consistent within its own
development"). Evidence: `2026-08-22_crisis_block_synthesis.md`.*

## 1. Root cause (unchanged from v1 — this part held)

> **A self-normalizing RANK is used as an ABSOLUTE threshold for a
> binary safety gate.**

`turbulence_pct` is a rank inside its own rolling 250-return window. A
rank always has a top 5%, so it can never say "calm" — measured firing
on stationary Gaussian returns with no regime change: **7.0%**. And
Mahalanobis distance measures **atypicality**, which is why a correlated
−3σ crash reads 80.0 and *never fires* while 6-up/6-down with zero net
move fires *100%*. The estimator is faithful (Spearman +0.970 vs
oracle). The predicate is wrong.

## 2. What v1 got wrong

v1 answered a bad predicate by adding three better ones. That is the
wrong instinct in a system whose own law warns against re-tangling what
is separated: it grows the gate count, adds a fourth place where
"should we trade" is decided, and leaves the defective path in place
beside its replacement. **The correct move is a deletion plus two
re-routings** into machinery that already exists and already does this
job continuously.

## 3. The design: one deletion, two re-routings, zero new gates

### 3.1 DELETE — the turbulence → crisis branch

`regime/macro_regime.py:441-442` currently reads:

```
crisis  if  own vol_percentile >= crisis_vol_pct
        OR  turbulence_pct     >= crisis_vol_pct     <-- DELETE this clause
```

Deleting the second clause removes, in one edit: the ~7%-by-construction
firing, the sign-blindness, the all-or-nothing broadcast, and the
one-constant-two-statistics conflation. Crisis reverts to what it can
honestly assert — *this asset's own volatility is extreme* — which is a
per-asset statement the label was always able to make.

**Complexity ledger: predicates −1, config keys −0, new modules 0.**

### 3.2 ROUTE — turbulence becomes governor UNCERTAINTY, not a veto

Atypical co-movement is not danger; it is **the covariance structure
being unlike the one the model was fitted on**. That is an epistemic
statement about model trust, and this repo already has the organ for it:
`ml/monitor.py`'s `shrinkage` (base 0.35, ceiling 0.70) and
`kelly_mult` (floor 0.40), consumed at `main.py:4585`.

```
turbulence high  ->  monitor.shrinkage ↑ toward its EXISTING ceiling
                 ->  kelly_mult ↓ toward its EXISTING floor
                 ->  sizing shrinks smoothly, everywhere, all at once
```

This is the "throughout the network" instruction taken literally: the
signal stops being a switch at one point in the pipeline and becomes a
**continuous confidence term that every sizing decision already reads**.
It also finally makes the drift/uncertainty machinery see a real
covariance-regime input, which it has never had.

**Complexity ledger: new consumers 0 — `shrinkage` already exists, is
already bounded, already logged, already on the board.**

### 3.3 ROUTE — real danger goes to the risk ladder, which already stops

The genuine crash signal (many assets falling together, in absolute
terms) does **not** need a new hard stop: the hard stops already exist
and are already hard — `capital_management.hard_stop_drawdown_pct`, the
daily loss limit, the circuit breaker, the FW kill switches, and
`RiskProtocolStack` (`risk/protocols.py:133`) with its CVaR / gap /
budget / heat protocols.

The defect is not a missing guard. **The defect is that breadth and
absolute stress never reach the guard that exists** — they get spent on
a regime *label* instead.

```
breadth of assets falling, in ABSOLUTE sigma terms
        ->  an input to RiskProtocolStack (a portfolio-risk fact,
            which is what that stack is for)
        ->  existing heat / CVaR / budget protocols respond with the
            responses they ALREADY implement, up to and including the
            hard stops they already own
```

A correlated crash then does what it never did before: it reaches the
risk ladder. Not because a new gate was built, but because the signal
was finally delivered to the right address.

**Complexity ledger: new gates 0, new hard stops 0, new stack members 0.**

### 3.4 KEEP — per-asset extremes stay where they are

Own-asset volatility already flows to per-asset sizing. Nothing to add.

### Net effect

| | before | after |
|---|---|---|
| places "should we trade" is gated on turbulence | 1 (binary, feed-wide) | **0** |
| new gates introduced | — | **0** |
| new modules / stack members | — | **0** |
| signals reaching machinery that already existed | 0 | 2 |
| predicate clauses in `_ensemble_label` | 2 | **1** |

The foundation gets deeper — the governor learns about covariance
regime, the risk stack learns about breadth — while the surface gets
simpler.

## 4. What stays invariant

- Exits ALWAYS allowed. Every path above restricts new risk only.
- `dry_run` default, `arm_live` never remote, Kraken sole venue,
  withdrawal deny-list: untouched.
- `force_dry` one-way. Hysteresis semantics unchanged for the labels
  that survive.
- One config key per statistic — the deletion in §3.1 ends
  `crisis_vol_pct` gating two unrelated statistics without adding a key.

## 5. No parameter values here — deliberately

The mapping curves (turbulence → shrinkage, breadth → protocol input)
carry no numbers in this document. Fitting them against the single
episode that motivated the rewrite is the OF-4 overfit the law forbids.
They must be config-lifted with `config_guard` bounds, derived from a
stated principle rather than this episode, and calibrated in shadow.

## 6. Pre-registered acceptance criteria (unchanged from v1 — still binding)

Executable against the injection harness the audit already built:

1. **Noise floor** — on stationary-Gaussian injection (today: 7.0%
   firing), turbulence-driven *entry suppression* < 0.5%.
2. **Crash sensitivity** — all-assets −3σ injection (today: reads 80.0,
   never fires) must now reach the risk ladder and reduce exposure.
3. **False-fire rejection** — 6-up/6-down zero-net-move (today: fires
   100%) must produce at most a shrinkage nudge, never a block.
4. **Broadcast elimination** — one asset at +5σ restricts at most that
   asset.
5. **No blind widening** — over the shadow window, entries admitted
   under REG-8 must not have worse counterfactual net expectancy than
   the admitted baseline, on **effective n**, not row count.
6. **Live agreement** — any period where REG-8 is *more* permissive
   during genuine drawdown is a BLOCKING finding.

## 7. Phase 0 — SAFE NOW, ships without adjudication

1. Export `turbulence_pct` (+ breadth) to the `status.json` schema —
   today `grep -rn "turbulence" core/ api/` returns nothing.
2. Stamp `CorrState` with timestamp / sample count / staleness flag and
   register a reason code for a held reading.
3. `config_guard` coverage for `regime.crisis_vol_pct` and the
   `correlation` block; collapse the duplicate `95` literal at
   `correlation.py:335` to a single config read.
4. **Shadow evaluator** — compute the REG-8 routing beside the live
   predicate every cycle, log both and their disagreement, **act on
   neither**. Measurement only; it converts Phase 1 from an argument
   into a dataset.

## 8. Phase 1 — BOUNDARY

The deletion and the two re-routings change which orders are placed:
operator adjudication, new execution era, accrual reset, full DoD
matrix, C++ diode era constants re-pinned. Batch with SWEEP-0/1
(CRITICAL), ALGO-5, REG-7, LS-1/LS-2 — one boundary, one docket.

## 9. Vault consistency (`llm-wiki`)

The vault is the knowledge brain; this repo holds code and dated
measurements. Entries this change touches, to keep the two consistent:

- `concepts/the-method` — **add the sixth recurrence**: a confident
  instrument, faithful in isolation, wrong at its consumer. Distinct
  from the prior five because the estimator was *correct* and the wiring
  was not. Also the first time the instrument was audited *before* the
  theory was built on it, and the audit inverted the conclusion.
- `concepts/observational-equivalence` — the sharpest example yet:
  "correlated crash" and "correlated melt-up" are byte-identical to a
  dispersion statistic, and 6-up/6-down with zero net move is
  indistinguishable from a real event.
- `concepts/referee-lattice` — this finding came from the lattice
  working as designed (three blind analysts, instrument-first ordering),
  and is its first inverted conclusion.
- **new** `concepts/rank-vs-absolute` — the general lesson: a
  self-normalizing statistic can never express "nothing is happening,"
  so it must never be the sole term in a binary safety gate. This
  generalizes beyond turbulence to every percentile-based threshold in
  the repo (`vol_percentile`, `turbulence_pct`, and any future rank).
- `sources/session-20260822-crisis-block` — the three agent reports and
  this design, cited by date.
