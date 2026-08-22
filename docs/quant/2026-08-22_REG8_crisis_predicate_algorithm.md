# REG-8 (pre-registered 2026-08-22): the crisis predicate, rebuilt

*Supersedes REG-6 (momentum-sign split — its discriminator was falsified
by its own pre-registered evidence). Derived from the three-agent audit:
`2026-08-22_crisis_block_synthesis.md`. Phase 0 is SAFE and shippable
now; Phase 1 is BOUNDARY class and adjudicated at the era-4 readout with
Phase 0's evidence in hand. Parameter VALUES are deliberately absent —
see §5.*

## 1. The root cause, stated once

Every measured defect is one category error:

> **A self-normalizing RANK is being used as an ABSOLUTE threshold for a
> binary safety gate.**

`turbulence_pct` is a rank within its own rolling 250-return window. A
rank always has a top 5%. It therefore *cannot* express "this period is
calm" — measured firing rate on stationary Gaussian returns with no
regime change at all: **7.0%**. Everything else follows:

| observed defect | consequence of the category error |
|---|---|
| fires ~7% on pure noise | a rank has no absolute zero |
| correlated −3σ crash reads 80.0, **never fires** | Mahalanobis distance measures *atypicality*, and a correlated crash is the *typical* covariance direction |
| 6 up / 6 down, zero net move, fires 100% | maximal atypicality, zero danger |
| one asset +5σ blacks out 12 assets | a market-wide scalar answering a per-asset question |
| PAXG (10th pct vol, +0.03%) marked crisis | same |

The estimator is fine (Spearman +0.970 vs oracle). The **predicate**
built on it is wrong.

## 2. The algorithm

Decompose the single conflated question into three orthogonal ones and
give each its proportionate authority.

```
INPUTS
  per asset a:   ret_a      recent return
                 sigma_a    own realized vol (absolute)
                 volpct_a   own vol rank
  market-wide:   turb_pct   Mahalanobis rank  (estimator UNCHANGED)

DERIVED
  stress   = median_a( |ret_a| / sigma_ref_a )     # ABSOLUTE, scale-free
  breadth− = frac_a( ret_a < -k * sigma_a )        # how many actually fall
  breadth+ = frac_a( ret_a > +k * sigma_a )

GATE 1 — the real crash guard  (currently MISSING; a correlated crash
                                does not fire today)
  CRISIS_DOWN := breadth− >= B_down  AND  stress >= S_crisis
    -> allow_new = False              # block new risk, exits unaffected

GATE 2 — turbulence is a MODIFIER, never a gate
  TURBULENT   := turb_pct >= T_hi    AND  stress >= S_floor
    -> size_mult *= shrink_turb ; require higher conviction
    -> NEVER sets allow_new = False on its own
    # the stress floor is what kills "6 up / 6 down, zero net move"

GATE 3 — per-asset extremes stay PER ASSET (no broadcast)
  for each a:  if volpct_a >= V_hi:  size_mult_a *= shrink_a
```

**Invariants this must preserve** (non-negotiable, inherited):
- Exits are ALWAYS allowed. Every gate above restricts new risk only.
- `force_dry`, `arm_live`, the withdrawal deny-list, Kraken-sole-venue:
  untouched.
- One config key per statistic. Today `crisis_vol_pct` gates *two
  unrelated statistics* (per-asset Parkinson rank AND cross-asset
  Mahalanobis rank); REG-8 splits them permanently.

## 3. Why this resolves each finding

| finding | resolved by |
|---|---|
| fires ~7% on noise | Gate 1 requires ABSOLUTE stress; a rank alone can no longer fire anything |
| crash never fires | Gate 1 keys on breadth− + magnitude, which is exactly a crash |
| zero-net-move false fire | Gate 2's `S_floor` |
| one asset blacks out twelve | Gate 3 is per-asset; Gate 2 only shrinks size |
| sign-blindness | Gate 1 is explicitly directional (breadth−), and it is directional on *realized returns*, not on the `mom_dir` feature REG-6 proposed — which the evidence falsified |
| duplicated 95 literal | one key per statistic, config-lifted, guard-bounded |

## 4. Phase 0 — SAFE NOW (no decision reach, ship without adjudication)

1. **Export `turbulence_pct` to the `status.json` schema.** Today
   `grep -rn "turbulence" core/ api/` returns nothing: the one number
   that can sideline the entire book reaches no operator surface.
2. **Stamp `CorrState`** with timestamp, sample count, staleness flag;
   register a reason code for a held reading (five early returns
   currently hold the prior value silently).
3. **`config_guard` coverage** for `regime.crisis_vol_pct` and the
   `correlation` block; collapse the duplicated `95` at
   `correlation.py:335` to a single config read.
4. **SHADOW EVALUATOR (the load-bearing one).** Compute the REG-8
   predicate every cycle *alongside* the live one, log both verdicts and
   their disagreements, and **act on neither**. This is measurement, not
   decisioning — it is moratorium-independent, and it converts Phase 1
   from an argument into a dataset.

## 5. Parameters are NOT specified here — deliberately

No values for `B_down`, `S_crisis`, `T_hi`, `S_floor`, `V_hi`,
`shrink_*` appear in this document. Choosing them now, against the one
episode that motivated the rewrite, is precisely the overfit this repo
forbids (OF-4: never tune to a backtest peak). They must be:

- config-lifted with `config_guard` bounds (FATAL on incoherent
  combinations), never literals in a decision path;
- derived from a stated principle (e.g. `S_crisis` from the drawdown the
  risk ladder already treats as material), not fitted to 2026-08-20;
- calibrated in SHADOW mode across at least one non-crisis regime and
  one genuine stress episode.

## 6. Pre-registered acceptance criteria for Phase 1

REG-8 ships only if, on shadow data collected before the decision:

1. **Noise floor**: on the stationary-Gaussian injection harness that
   measured today's 7.0%, REG-8's `CRISIS_DOWN` fires **< 0.5%**.
2. **Crash sensitivity**: on the all-assets −3σ injection that today
   reads 80.0 and never fires, REG-8 **does** fire.
3. **False-fire rejection**: on the 6-up/6-down zero-net-move injection
   that today fires 100%, REG-8 **does not** fire.
4. **Broadcast elimination**: on the one-asset +5σ injection, at most
   that asset is restricted; the other eleven stay tradeable.
5. **No blind widening**: over the shadow window, REG-8 must not admit
   entries whose counterfactual net expectancy is worse than the
   admitted baseline, measured on **effective n**, not row count.
6. **Live agreement**: disagreement between live and shadow predicates
   is reported per regime, and any period where REG-8 is *more*
   permissive during genuine drawdown is a BLOCKING finding.

Criteria 1–4 are executable against the injection harness the audit
already built (`/tmp/turb/`, to be re-homed under `tests/` as part of
Phase 0). They are pass/fail, decided before the data.

## 7. Cost of Phase 1, named

New execution era, accrual resets, full DoD matrix, and the C++ diode's
era constants re-pinned. Batch with the standing docket (SWEEP-0/1
CRITICAL, ALGO-5, LS-1/LS-2) — one boundary, one docket, per the
generational rule.

## 8. What the evidence says about urgency

The block costs **+0.7pp against a time-matched control at n_eff 11.89**
— i.e. nothing measurable. So the case for REG-8 is **not** "we are
losing money while blocked." It is that **the crash guard does not guard
against crashes**, and that a rank-based gate will re-fire on noise
roughly 7% of the time forever. Phase 0 is urgent (the number is
invisible); Phase 1 is important but not rushed.
