# FLOW/USD vs ETH/USD, and the target decision — 2026-09-02

Two questions from the operator, answered by measurement. All read-only.

---

## PART 1 — THE TARGET DECISION: **REJECT**, and it is now decided by measurement

The operator asked for the decision to be taken "in a logical sense to increase
learning". Under a learning objective the question is not "will a magnitude target
make money" but "how much information does switching buy, per unit of cost". Both
halves are now measured, and the answer is that it buys **none**.

### The two measurements that decide it

**(a) Power — does a continuous target RESOLVE anything the 1-bit target cannot?**
Planting effects of known strength against the real `label_ret_pct` and the real
`label` on the *same* 6,071 rows over 11 day blocks (read 2026-09-02T21:39Z):

| planted effect | continuous (Spearman) | 1-bit (AUC) |
|---|---|---|
| 0.01 | 42% | 8% |
| 0.02 | 50% | 50% |
| **0.05** | **100%** | **100%** |
| 0.10 / 0.20 | 100% | 100% |

**Minimum detectable effect at 80% power: 0.05 for BOTH.** The continuous target
resolves the same effect size. It is a lateral move, not an upgrade.

**(b) Finding — does the continuous target FIND anything, on the same rows?**
All 64 stored features scored against `label_ret_pct`, day-block CI, and against a
**measured** null rather than a nominal one (read 21:40Z):

- Features whose 95% CI excludes zero: **5 of 63**
- Measured null exclusion rate (120 pure-noise features, same rows and blocks): **10.0%**, so **6.3 expected by chance**
- **Observed 5 against 6.3 expected — below chance**, exactly as the 1-bit target reads
- Largest |Spearman| anywhere: **0.1017** (`sent_dir`)

### The decision
**REJECT the target change.** Not defer — reject, on evidence:

1. It buys **no resolution** (both targets: MDE 0.05).
2. It finds **nothing** (5 vs 6.3 expected, below chance).
3. It costs a cohort reset from zero, one more trial added to N (lengthening MinBTL
   against a 0.065 yr sample), and months of wall-clock.

Expected information gain: measured at approximately zero. Cost: large and certain.
Under a learning objective that is not a close call.

### The general lesson, which is worth more than the decision
The question "should we deploy a different target to find out?" was answerable
**offline, in two scripts, at zero cohort cost**, because `label_ret_pct` was already
sitting on the rows. The learning-optimal move was never to deploy-and-see; it was to
measure the counterfactual first. **Before any future cohort-resetting proposal, ask
whether its central claim can be tested on data already in hand.** Here it could, and
the answer killed the proposal in an afternoon instead of a quarter.

The adjudication brief's recommendation moves from DEFER to REJECT, and the brief's
own stated trigger — "a power result on the continuous target showing it resolves
effects the 1-bit target cannot" — has now been run and came back negative.

---

## PART 2 — FLOW vs ETH: the premise is wrong, and the real answer is bigger

### The premise, corrected
Flow's multi-role pipelined architecture and Ethereum's monolithic execution do
differ enormously in on-chain speed and fees. **None of it reaches this code.** The
bot trades `FLOW/USD` and `ETH/USD` as **spot pairs on Kraken**. It never signs a
transaction, never pays gas, never waits for a block; fills settle in Kraken's
internal ledger. Kraken's fee tier is **account-level** (30-day volume, currently
22/38 bps), so both pay an identical schedule regardless of their chain economics.

**Applicability to the code: none.** No path in this repo is sensitive to either
protocol's throughput or gas market.

*(Instrument note: a first pass reported "FLOW-specific config PRESENT". That was my
own false positive — the grep matched `flow_tox`, `informed_flow` and `context.flow`,
which are ORDER-FLOW concepts. Confirmed by walking config keys: there is **no**
FLOW/USD-specific configuration anywhere.)*

### What DOES differ, and it matters far more
The two listings differ in microstructure, and that reaches everything (tape read
2026-09-02T21:42Z, 51 days):

| | FLOW | ETH | ratio |
|---|---|---|---|
| trades/hour | 15.0 | 985.6 | **66×** |
| median trade size | $17 | $107 | 6× |
| tape notional | $2.4M | $2.28B | 940× |
| median spread (signal rows) | 3.6 bps | 0.0 bps | — |
| median `manip_suspect` | **0.927** | 0.228 | — |
| SZ-045 refusals | **470 of 1,065 (44.1%)** | 1 of 3,919 (0.0%) | — |
| **fills, all time** | **0** | 225 | — |

### The finding this produces
**The manipulation gate is behaving as an illiquidity detector, and it has excluded
FLOW from trading entirely.** The veto fires at 0.90; FLOW's *median* signal scores
**0.927**, so the median FLOW opportunity is refused by construction. FLOW's
disposition histogram is led by SZ-045 (470), and across 14 traded assets **FLOW is
the only one with zero fills of any kind**.

This closes a loop from earlier today: MANIP-2 found that 735 of 744 manipulation
refusals were FLOW and MINA. The reason is now measured — it is not that those assets
are manipulated, it is that a thin book scores like a manipulated one. The detector
cannot separate "few participants" from "adversarial participants", which is the
observational-equivalence problem this repo already recorded for the spoof component,
now visible in a second place.

### What follows, and what does not
- **FLOW currently costs universe slots, gate cycles and tape-backfill bandwidth, and
  returns nothing.** Whether to keep it listed is an OPERATOR call — it touches the
  traded universe, which is decision-path.
- **Do not "fix" this by lowering the veto threshold.** That is gate-widening, and the
  refusals may be correct in the sense that a 15-trades-per-hour book genuinely is a
  bad place for a limit-entry strategy paying 22/38 bps against a 3.6 bps spread.
- **The honest reframe:** the gate may be reaching the right conclusion for the wrong
  stated reason. "Refused as manipulation" and "refused as too illiquid to trade" are
  the same action with very different meanings, and only the second is defensible from
  this evidence.
- Ticket MANIP-2's blast radius already covers the disposition staleness; this adds
  that the *score itself* is confounded with liquidity, which the standing SZ-045
  efficacy question in the vault must now account for.

### Where the Flow-vs-Ethereum comparison WOULD matter
Only if the bot ever settled on-chain — self-custody, a DEX venue, or an L2. It does
not, and Kraken is the sole execution venue by hard invariant. If that ever changed,
the relevant axes would be finality time against the position horizon, and gas as a
fixed per-trade cost against ticket size. At the current ~$18 modal ticket, a fixed
on-chain cost of even a few dollars would dominate the entire fee stack — which is an
argument against on-chain execution at this size, not for it.
