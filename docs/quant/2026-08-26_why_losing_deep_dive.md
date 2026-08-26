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
−$0.21 net — pure fee churn. The exit-asymmetry finding stands: median
loss exceeds worst adverse excursion, i.e. **cost, not stop placement**.

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
5. **$18 tickets** — a sizing/consolidation decision (CONC-1 territory,
   also cohort-resetting).

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
