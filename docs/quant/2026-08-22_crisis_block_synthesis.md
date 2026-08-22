# The feed-wide crisis block — three-agent synthesis (2026-08-22)

*Parallel dispatch, three independent agents, one question each. Full
results: `2026-08-22_turbulence_instrument_verification.md`,
`2026-08-22_turbulence_episode_history.md`,
`2026-08-22_crisis_counterfactual_REG6_evidence.md`. This file is the
router and the decision surface; the three source docs carry the
evidence.*

## What happened

Since 2026-08-20 all 12 assets have been classified `macro=crisis`,
which sets `allow_new: False`. The bot has taken almost no entries for
48h+ and the era-4 gate has stalled at 33/50. Trigger: a single
cross-asset `turbulence_pct` scalar crossing 0.95, broadcast identically
to every asset (`main.py:6280` → `macro_regime.py:441`).

## The three findings, and how they fit

**1. The instrument is DEFECTIVE AS DEPLOYED.** The Kritzman-Li
estimator itself is faithful (Spearman +0.970 vs an oracle). What is
broken is how it is wired:

- `turbulence_pct` is a **rank within its own rolling 250-return
  window**, so ~5% of readings sit above the 95th line *by
  construction*. Injected into the shipped engine on stationary Gaussian
  returns — no vol clustering, no regime change, nothing to detect —
  P(fire) = **7.0%**. The threshold cannot report "this period is calm."
- It measures **atypicality of the co-movement pattern**, not stress,
  while its consumer treats it as a crash guard. Measured in-engine: all
  12 assets crashing −3σ *together* reads 80.0 and **never fires**;
  6 up / 6 down with zero net market move reads 99.6 and fires
  **100%**; one asset at +5σ with eleven flat reads 99.6 and blacks out
  the entire book. **The guard is inverted relative to its purpose.**
- No `config_guard` coverage; a second hardcoded copy of the 95
  threshold (`correlation.py:335`) silently desyncs the operator warning
  from the decision; one constant gates two unrelated statistics.

**2. The episode is unprecedented and unforecastable.** `turbulence_pct`
never crossed 0.95 in the 37 days before 08-20 (prior max 0.940).
Historical N = 1. `regime_crisis == 1` matches `turbulence_pct ≥ 0.95`
with **100% agreement** (n=1,485); only 6.6% of crisis rows also carry
own-asset vol ≥ 0.95. The current stretch is 30h+, open, 4–5× longer
than any completed prior excursion, pinned at the series ceiling 0.984.
No base rate exists to say when it ends.

**3. The block costs nothing measurable — and REG-6's discriminator is
falsified.** Crisis-window candidates won 61.3% nominal, but
**n_eff = 11.89** (mean uniqueness 0.0080; ESS on a 40-row subsample was
already 8.88 — the extra 1,445 rows bought ~3 units of information).
Honest Wilson: [34.3%, 82.8%]. Against a like-for-like h432 control:
+16.1pp, n.s. Against a time-matched rally control: **+0.7pp**. Net
expectancy at the measured 66.76 bps round trip: +0.10%/trade,
t_eff 0.14. And **`crisis_down` longs (91.3%) beat `crisis_up` longs
(78.4%)** — the momentum-sign split REG-6 proposed as its discriminator
runs backwards from its own premise. The apparent uplift lives in the
**low-vol rows the shared scalar swept in**, and win rate falls
monotonically as vol_percentile rises (74.0 → 49.7%).

## What this changes

- **REG-6 as written is superseded, not merely unsupported.** It
  proposed splitting a label on momentum sign. The data falsifies that
  discriminator, and the audit shows the real defect is *upstream* of
  the label: a sign-blind, saturation-prone, inverted trigger broadcast
  as one scalar. A directional rename would leave the mechanism intact.
- **REG-7's occupancy finding is explained.** Crisis occupancy is either
  ~0% or ~90% and never in between because the trigger is all-or-nothing
  across the universe by construction.
- **The gate stall is a one-number stall**, and that number is not
  measuring what its consumer believes.

## Disposition

**SAFE-NOW (moratorium-independent — observability only, no decision
reach):**
1. Export `turbulence_pct` to the `status.json` schema — it currently
   reaches no operator surface at all (`grep -rn "turbulence" core/ api/`
   → nothing). The single number that can sideline the whole book is
   invisible on the glass.
2. Stamp `CorrState` with timestamp + sample count + staleness flag, and
   register a reason code for a held reading (five early returns
   currently hold the prior value silently).
3. Add `config_guard` coverage for `regime.crisis_vol_pct` and the
   `correlation` block, and collapse the duplicated 95 literal to a
   single config-read.

**BOUNDARY (operator adjudication, cohort-resetting — do NOT ship):**
- Any change to the trigger, the broadcast, the threshold, or the
  crisis playbook. This now includes REG-6, whose scope must be rewritten
  before it is adjudicated.

**OPEN ITEM (measurement integrity, not this incident):** 2026-07-13 →
08-02 the daily statistic was not piecewise constant intraday (median
range 0.482, up to 50 direction reversals/day). The July-era
`turbulence_pct` **feature column feeds the training corpus** and should
be treated as suspect until explained.

## The method note

This is the sixth entry in the repo's "instrument is the first suspect"
ledger, and the first where the instrument was audited *before* a theory
was built on it — the audit was dispatched ahead of the analyses that
depended on it, and it inverted the conclusion. Yesterday's read of the
same data ("copious volatile data, rarest stratum filling for free")
was wrong in the way the law predicts: n_eff 11.89 against 1,485 rows.
The verifying agent also recorded that its own harness was wrong twice
before it was right, both times caught by disbelieving a suspiciously
clean null.
