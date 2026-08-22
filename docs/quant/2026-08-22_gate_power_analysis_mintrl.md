# Gate power analysis — MinTRL / PSR on the era-4 cohort

*Operator request 2026-08-22: backtest and walk-forward work using the
formulas that most improve edge measurement. This applies Bailey &
López de Prado's Probabilistic Sharpe Ratio and Minimum Track Record
Length to the accruing era-4 cohort. **Report-only. It does not decide
the gate and it does not move n=50** — `MIN_COHORT_N` is a measurement
standard, not a tunable (CLAUDE.md). It answers one question the project
has never asked: **is the pre-registered gate powered to detect the
effect it is testing for?***

## Formulas

Per-trade Sharpe `SR = mean/sd`, with skew `γ₃` and non-excess kurtosis
`γ₄` (the third and fourth moments matter: this return series is
positively skewed and fat-tailed, so a Gaussian SE understates the
sample size required).

```
PSR(SR*)  = Φ[ (SR − SR*)·√(n−1) / √(1 − γ₃·SR + (γ₄−1)/4·SR²) ]

MinTRL    = 1 + [1 − γ₃·SR + (γ₄−1)/4·SR²] · ( Z_α / (SR − SR*) )²
```

## Measured — era-4 cohort, n=33 entry-opened closed trips

| series | mean/trade | SR | skew | kurt | PSR(SR\*=0) | **MinTRL(95%)** |
|---|---:|---:|---:|---:|---:|---:|
| **GROSS** (pre-fee) | +1.1820% | +0.4339 | +1.25 | 4.51 | **0.9991** | **10 trades** |
| **NET** at *configured* fees | +0.5117% | +0.1876 | +1.26 | 4.48 | 0.8831 | **62 trades** |
| NET at true fees, maker/maker (×1.60) | +0.1094% | +0.0401 | — | — | 0.5919 | **1,603 trades** |
| NET at true fees, maker/taker (×1.85) | **−0.0556%** | −0.0204 | — | — | 0.4548 | **INFINITE** |

Booked round-trip cost reconstructs to **67.04 bps**, independently
confirming `cost_truth_report`'s measured 66.76 bps — the two routes
agree, so the fee arithmetic below rests on measurement, not assumption.
True-fee rows scale the booked fee by Kraken T1 (40/80) over configured
(25/40).

## What this says

**1. The gross edge is already statistically established.** MinTRL(95%)
for the gross series is **10 trades**; the cohort has 33. Gross
expectancy is not the open question — it is answered, and positive.
PSR 0.9991.

**2. The net edge is the entire question, and it is fee-determined.**
At configured fees the net series needs **62 trades** for 95%
confidence; the gate stops at **50**. At the venue's real bottom tier it
needs **1,603** — or, on the maker-in/taker-out mix, no sample size at
all, because the mean goes negative.

**3. This is the textbook shape of the pre-registered COST_BOUND
verdict.** The era-4 decision table defines it as: *"gross > 0, net ≤ 0
→ an edge exists and fees eat it."* Gross SR +0.43 with MinTRL 10
(satisfied), net at true fees ≈ 0 or below. **The tool does not declare
the verdict — the operator does, at the readout — but the arithmetic now
points at one arm rather than three.**

**4. The gate may be answerable earlier than n=50, and for a different
reason than expected.** Not because accrual is faster, but because the
*gross* leg cleared its power requirement at n=10 and the *net* leg is
decided by a constant (the fee) rather than by more samples.

## Caveats — every one of them cuts against the flattering reading

- **Nominal n, not effective n.** These use n=33 raw. Concurrency and
  overlapping label windows deflate that (this corpus has measured
  effective-n ratios as harsh as 1,485→11.89 elsewhere). Effective n
  makes every MinTRL **larger** and every PSR **smaller**. The numbers
  above are the optimistic bound.
- **SR is itself estimated from 33 trades.** MinTRL computed from an
  estimated SR is conditional on that estimate; if the true SR is lower,
  MinTRL rises steeply and non-linearly.
- **The cohort includes the 08-20 melt-up window**, whose base rate was
  0.613 vs 0.262 elsewhere. The +0.51% configured-fee net is
  compositionally flattered; the honest number is lower.
- **The true fee tier is UNVERIFIED.** 40/80 is Kraken's *published*
  bottom tier, not this account's measured row. `OM-080` reconciliation
  has never fired (FEE-3). The ×1.60 / ×1.85 multipliers are therefore
  bounds on an unconfirmed anchor.
- **DRY_RUN fees are simulated.** This measures whether the modelled
  strategy would survive live costs, not realised P&L.

## What it changes

Nothing in the engine, and nothing about n=50. What it changes is
**priority**: FEE-3 — one read-only `TradeVolume` call — is no longer
housekeeping. It is the single measurement that determines which of two
radically different worlds the cohort is in:

| if the true tier is… | net SR | MinTRL | likely readout arm |
|---|---:|---:|---|
| configured 25/40 | +0.19 | 62 | CONTINUE plausible |
| T1 maker/maker | +0.04 | 1,603 | COST_BOUND |
| T1 maker/taker | −0.02 | ∞ | COST_BOUND |

Two of three worlds are COST_BOUND, and the discriminator costs one API
call.

## Re-run protocol

Re-run at the readout on **effective n**, stratified by the crisis
stamp, and with the fee anchor replaced by the measured tier rather than
the published one. If the gross MinTRL still sits below the accrued n
and net does not, the COST_BOUND arm is the arithmetic answer and the
decision passes to the operator with the fee levers named in the
decision table.
