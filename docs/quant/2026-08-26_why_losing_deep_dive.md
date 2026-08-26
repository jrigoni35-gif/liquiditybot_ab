# Why it's still losing money — the era-4 dollar decomposition (n=54)

*Operator question 2026-08-26: "deep dive on why it's still losing money —
what are we doing wrong?" Measured on the live `outputs/fills.csv` at the
moment the era-4 gate crossed its pre-registered n=50 (54 entry-opened
closes). Every number below re-derives from the commands cited; quote the
tools, not this file, after more fills accrue.*

## The one-sentence answer

The strategy's real trades are profitable and its learning is not: **91% of
the cohort is probe trades whose gross edge (+0.28%/trip) is smaller than
the round-trip cost (0.65% booked, ~1.29% true)** — so the book pays full
fee-tuition on ten trades for every one that can actually earn, in a fee
world the config understates by ×1.979, on $18 median tickets that no edge
of this size can carry.

## The decomposition (dollars, era-4 cohort)

**Totals:** gross **+$8.23**, booked fees **$6.87** → net **+$1.36**
booked, **−$5.36** at true fees. Fees consume 83% of gross at the
configured schedule and 165% of it at the venue's real Tier-1 row.

### Probe vs conviction — the load-bearing split

| | n | gross/trip | net (booked) | net (true ×1.979) |
|---|---:|---:|---:|---:|
| conviction | 5 | +2.815% | **+2.132%** | **+1.463%** |
| probe | 49 | +0.283% | **−0.392%** | **−1.052%** |

The five conviction entries clear the full true cost stack. The
forty-nine probes cannot clear even the booked one — their gross is
*structurally* below the round trip. This is the P3 finding of 2026-07-23
(probes 69% of closes, −$22.87 of −$31.68) still true a month later: the
throttles bounded the volume, not the shape. **Caveat: n=5 is not evidence
the conviction edge is real** (a Wilson interval at n=5 spans nearly
everything); it is evidence the losses are not coming from there.

### By asset

BTC/ETH/LINK: **+$4.56** net booked on 18 trips — the entire edge.
DOGE/ARB/LTC/ADA/SUI: **−$3.67** on 27 trips — half the cohort's trades,
net-negative *before* fee truth. SUI and ADA gross positive but fee-eaten
(fees $1.50 vs gross $1.01 on SUI).

### By exit reason

`tb_sl` stops: −$6.23 on 14 trips (the loss channel). `tier trail`:
+$4.04 on 24 (the earn channel). `tb_time` timeouts: +$1.11 gross →
−$0.21 net — fee churn on 19% of trips. **Amended by the same-day
validation (rows 6b/6c below):** the stop channel's dollars are 78%
genuine adverse price movement, so "cost, not stop placement" was too
strong — the correct statement is that BOTH are true: stops fire on real
moves, AND 79% of losers (Wilson [60%,91%]) still lose more than the
worst the price ever went against them, because the ~0.65% fee rides on
top of every loss and MAE's poll-cadence sampling understates depth.

### Ticket size

Median entry notional **$18.00** (min $7.42). At $18 a booked round trip
is ~$0.12 and a typical gross move ~$0.09. Kraken minimum tickets on an
$800 book with concurrency caps force this; **no per-trade edge this
strategy has shown can outrun the fee floor at $18 tickets.**

### Concurrency

Effective n 21.5 of 54 (uniqueness 0.399): the book pays 54 tuitions for
~21 independent lessons.

## What we are doing wrong, ranked by measured dollars

1. **Booking half the true fee** (config 25/40 vs Tier-1 40/80): flips the
   cohort from +$1.36 to −$5.36. Fix fully staged as **boundary #5**
   (`scripts/boundary5_stage.py --apply`), awaiting operator.
2. **Letting probes trade at a mispriced tuition**: exploration EV was
   computed against the understated fee, so 49 trades ran whose ceiling
   was below their cost. Boundary #5's `p_win 0.85` + derived entry bar
   0.8335 fixes the pricing; whether ~$0.19/trip true tuition is worth the
   labels is then a conscious learning budget, not a leak.
3. **Trading the alt tail with real size**: half the trades, negative even
   at booked fees. Asset selection is entry decisioning → cohort-resetting
   → boundary adjudication, batched with #5.
4. **Geometry sized to the false fee world**: 2% targets vs 1.2% true
   round trip = cost is 60% of a gross win. ALGO-5 (pre-named) widens to
   4.8%; the power analysis independently demands gross ≥2.37%/trip for a
   significant CONTINUE at true fees — only wider geometry gets there.
5. ~~**$18 tickets** — the fee floor eats them alive~~ **WITHDRAWN
   (same-day statistical validation).** Kraken fees are proportional:
   median booked round trip is 65.2 bps on <$20 tickets vs 64.8 bps on
   larger — there is no fee floor penalizing small tickets. And the
   small-vs-large net split is 100% confounded with probe/conviction
   (the ≥$20 trips ARE the 5 conviction trades). The true ticket-size
   issue is economic — absolute dollars too small to compound or to buy
   labels quickly — not a per-trade loss mechanism. The dive's original
   #5 was a plausible mechanism stated without a measurement; the
   measurement refuted it.

## Statistical validation (same day, bootstrap B=20k, seed 7)

| claim | test | verdict |
|---|---|---|
| 1 fee constant | none needed — arithmetic on a measured ×1.979 | REAL, conditional on the tier row (FEE-3 unverified) |
| 2 probe tuition | probe net at TRUE fees −1.051% CI[−1.65,−0.40], p≈0.001 raw, **p≈0.027 after ×1.58 concurrency deflation** | REAL at true fees (conditional on claim 1); NOT yet resolvable at booked fees alone (p=0.11) |
| 2b conviction>probe | +2.52%/trip, d=1.03 (large), CI[−0.59,+5.80], p=0.062 | UNDERPOWERED — needs ~16 conviction trades for 80% power, have 5. Directional only |
| 3 alt tail | majors−alts +1.69% CI[+0.20,+3.36], d=0.70; but the grouping was chosen AFTER seeing the data, and deflated p≈0.08 | POST-HOC — pre-register the split for the next era; do not act on this p |
| 4 geometry | TRUE cost = 68% of mean gross win, CI[48%,103%] | direction solid; magnitude uncertain by 2× |
| 5 ticket size | fee bps size-invariant (65.2 vs 64.8); split confounded with probe/conviction | **REFUTED as stated** (see above) |
| 6 exits: stops-vs-trail split | none possible — grouping by exit reason selects on the outcome (stopped trades lose by definition) | DESCRIPTIVE only, no causal content |
| 6b stop-channel composition | pooled tb_sl loss = 78% price movement, 22% fees | **AMENDS the "cost, not placement" line**: stops fire on real adverse moves; cost is the minority of that channel's dollars |
| 6c loss > own MAE | 19/24 joined losers (79%, Wilson [60%,91%]) lost more than the worst the price ever went; median excess +0.742% | REAL — every loser pays ~fee (0.65%) on top of its price move, plus MAE poll-cadence under-sampling; consistent with 6b, both are true at once |
| 6d timeout churn | n=10 (19% of trips), mean net −0.624% CI[−1.06,−0.11], p=0.009 raw / ≈0.07 deflated | semi-mechanical (tb_time selects small-move trades, so net≈−fee by construction); the actionable number is the 19% RATE |

Five claims at α=0.05 ⇒ Bonferroni bar 0.01: only the arithmetic claims
(1, 4's direction) and claim 2-at-raw-SE clear it; claim 2 after honest
concurrency deflation clears 0.05, not 0.01. The ranking's spine — fees
plus probe tuition — stands; the asset and ticket stories were weaker
than the prose implied.

## What is NOT wrong

The verdict machinery worked exactly as pre-registered: gross > 0, net ≤ 0
at the honest constant is the **COST_BOUND** arm, and the old postmortem
gate independently printed **STAND DOWN** (−1.007% vs the −1.0% floor).
The system detected that this configuration cannot pay its costs — that is
the instrument doing its job, not the strategy mysteriously decaying. The
market is allowed to be boring; the apparatus was mispriced.

## Provenance

`scripts/cohort_eval.py` (gate + effective n), `scripts/cost_attribution.py`
(§1b dispersion, §2 schedules), per-trip decomposition via
`scripts.cohort_eval.era4_trips` joined to `outputs/signal_history.csv`
`probe` column (54/54 joined), fee truth ×1.979 from `fee_reprice.py`'s
exact leg count (dc107ce3). All SAFE/report-only; nothing here changed any
decision path.
