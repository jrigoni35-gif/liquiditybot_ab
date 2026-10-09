---
title: The Tangible-Value Doctrine (the haven gradient — gold > BTC > ETH > alts)
category: synthesis
summary: "The ladder of how tangible an asset's claim on value is — PAXG > BTC > ETH > ALTS — encoded as measurement rather than mood: fear travels down the ladder and greed up it, in order, so adjacent-rung spreads read regime better than any single return. Carries its own falsifiable prediction (tangibility ordering = volatility ordering), which was measured on live Kraken bars at commit time and HELD; and its own restraint (report-only, pinned by a parsed-AST test) with the evidence that would earn it decision wiring named in advance"
tags: [doctrine, regime, haven, paxg, gold, psychology, report-only, instrument-first]
sources: 1
updated: 2026-08-05
---

# The Tangible-Value Doctrine

Shipped 2026-08-05 as `regime/haven.py` (commit `717b2e39`, battery **3332 passed / 1 skipped**)
on an operator directive: *"open the bot up to paxg and treat gold as a tangible investment. make
it understand the psycological aspects between the value of gold > bitcoin > Eth > alt coins."*
([[sources/session-20260805-evening]])

This page is the **ground truth for the ladder**. The instrument is downstream of it.

---

## 1. The ladder

Crypto assets are not one asset class wearing different tickers. They sit on a ladder of **how
tangible their claim on value is**, and capital's movement **along** that ladder is itself
information.

| Rung | What the claim actually is |
|---|---|
| **PAXG** | Gold, redeemable for an **allocated bar in a vault**. Its value is a physical thing that exists whether or not any chain, exchange or counterparty does. Five thousand years of monetary history, near-zero correlation to crypto beta — **the only universe member whose story does not depend on adoption**, and whose drawdowns are not the others' drawdowns. |
| **BTC** | **Digital gold**: fixed supply and the deepest, oldest security budget in crypto — but a claim on a **NETWORK**, not on a bar. It is the tangible anchor **OF** crypto while remaining a risk asset **TO** everything else. That dual role is exactly why it sits *below* gold and *above* everything else. |
| **ETH** | **Productive infrastructure**: cash-flow-like fee burn and staking yield, but value **contingent on people actually using the platform**. A claim on future usage. |
| **ALTS** | **Venture bets.** High beta, thin books, and a value proposition that is mostly narrative until proven — the pump-and-dump surface [[entities/long-book]] already refuses to touch. |

Position in the list **is** the claim about tangibility. Everything not gold and not one of the two
majors classifies as ALT — the honest default: *an unknown ticker on a thin book is an alt until
proven otherwise.*

---

## 2. The psychology, stated as mechanism

This is the part the operator asked for, and it is stated as a **mechanism** rather than as a mood,
because a mood cannot be measured and a mechanism can:

> **Fear travels DOWN the ladder and greed travels UP it — and both travel in a specific order.**
> Under stress, capital abandons the **least tangible claim first** (alts bleed before ETH, ETH
> before BTC, BTC before gold) because in a drawdown the question stops being **"what could this
> become"** and becomes **"what is this, actually."** In froth the same ladder runs in reverse:
> money that has already won in gold and BTC reaches down for beta, and alts outrun everything on
> the way up.

**The measurement follows from the mechanism, not the other way round.** If the ordering is the
claim, then the *ordering* is what to measure — so the instrument computes **adjacent-rung
spreads**, not levels and not a top-to-bottom difference:

- **Why spreads and not returns.** *BTC up 2% is ambiguous. BTC up 2% while alts are down 4% is a
  flight to quality already in progress.* The relative spread down the ladder is a cleaner read on
  regime than any single asset's return.
- **Why adjacent-only.** Comparing PAXG to alts directly would let **one blown-out microcap dominate
  a reading about gold**. The ladder's claim is about **order**, so the measurement is about order
  too.
- **Why the rung is averaged, not represented.** One alt ripping is a coin story; the **whole rung
  moving together** is a regime.

The gradient is signed so that **positive = capital moving down the ladder toward what is real**
(fear); negative = the reach for beta is on. States: `flight_to_quality` / `neutral` / `risk_on`, and
**`unknown` whenever the evidence is insufficient** — a state, never a guessed number, keeping the
context engine's rule.

**The band is a convention, not a fitted constant.** `DEFAULT_BAND_PCT = 1.0` — 1% of relative move
per rung over the lookback (288 5m bars = 24h) is the scale at which the ladder's own ordering is
visible above a normal session's chop. Deliberately round: *a fitted threshold on an unvalidated
instrument would be a curve-fit dressed as a discovery.* This is the same discipline that keeps
fitted literals out of decision paths ([[entities/liquiditybot]] overfit discipline).

---

## 3. The falsifiable prediction — and its first measurement

A doctrine that cannot be wrong is not doctrine, it is decoration. This one carries an explicit,
pre-stated prediction:

> **If tangibility is real and ordered, then realized volatility must rank down the same ladder.**

**Measured at commit time on live Kraken bars — and it HELD:**

| Rung | Asset | Realized 5m volatility |
|---|---|---|
| PAXG | PAXG | **0.075%** |
| BTC | BTC | **0.093%** |
| ETH | ETH | **0.120%** |
| ALT | SUI | **0.116%** |
| ALT | ARB | **0.160%** |

**PAXG 0.075% < BTC 0.093% < ETH 0.120% ~ SUI 0.116% < ARB 0.160%** — the **tangibility ordering IS
the volatility ordering**. This is the thesis's own falsifiable prediction, tested against the bot's
own venue-grounded data, and it survived.

### The first live gradient read — and the honest asterisk on it

`flight_to_quality`, gradient **+2.00**: **PAXG +4.7% / BTC +0.8% / ETH +2.1% / ALT −1.3%** over 24h.

> ⚠️ **`BTC-ETH` came out NEGATIVE in that same reading.** ETH (+2.1%) outperformed BTC (+0.8%) —
> the ladder inverted on one rung while the overall gradient read strongly toward tangibility.
>
> **The ladder is a TENDENCY, not a law.** This is recorded on the first reading, in the doctrine
> itself, deliberately: it is exactly the kind of qualifier that gets lost once a number starts
> appearing on a board. It is also **why the instrument reports per-rung detail instead of a
> verdict** — a single state label would have hidden the inversion that the per-rung view shows on
> its face.

This is the corpus's standing habit applied at birth: **record what refutes you in the same document
that states the claim** ([[synthesis/open-contradictions-register]], and the
*claimed → refuted → stands* pattern the vault's schema requires).

---

## 4. The restraint, and how it is enforced

**Report-only by construction.** `regime/haven.py` sizes nothing, gates nothing, vetoes nothing,
times nothing. It measures where capital sits on the ladder right now, from the bot's **own
venue-grounded Kraken candles** — no new feed, no new dependency, no external "sentiment" vendor.

**The restraint is pinned by a parsed-AST test, not a prose scan.** This detail is doctrine, not
trivia:

> A text search for `import execution` would **match the module's own docstring** — the docstring
> that promises the very restraint the test is checking. The check therefore parses the AST and
> inspects real import nodes.

That is [[concepts/iron-law-of-debugging]]'s discriminator rule applied prospectively: **match on
the identifying structure, never on a string that merely correlates with it**. A prose-scanning
guard here would have been green forever and worth nothing — the same shape as the substring path
filter that bricked the deploy gate, and the static metric scan that invented 92 phantom ghosts
([[sources/telemetry-stack-audit]]).

**Two further non-goals, both deliberate:**

- **No feature-vector change.** The model schema is **frozen mid-migration** — the 432-bar cohort is
  a pre-registered experiment in flight, and widening the vector for a signal with **zero track
  record** would invalidate it. The standing order is **hold, do not retune**
  ([[comparisons/horizon-96-vs-24-bars]]).
- **No gold-specific bracket geometry.** PAXG's low vol flows through the **same** vol-scaled
  brackets, sizer and labeler as everything else — sigma-scaled geometry tightens on its own, which
  is the entire point of scaling by sigma rather than by hardcoded percentages. **PAXG needs no
  special case**; a special case would have been the tell that the abstraction was wrong.

**Spot only, everywhere.** The bot holds no margin on any venue — and when the operator's brief
named *"spot and margin positions,"* **no margin panel or metric was invented to imply otherwise**.
A board that showed margin would be a board that lied ([[entities/observability-sidecars]]).

---

## 5. What it costs, and what it buys

**It costs one discretionary skimmer slot.** [[entities/config-guard]] **FATALs at 13 pairs**: with
the WS feed down, the REST book poll at **3 req/s** sustains a **12-pair envelope**, so base(7) +
extra(6) = 13 would starve it. `skimmer.max_extra` moved **6 → 5** — a **permanent tangible-value
anchor in place of a rotating candidate**, which is the trade the operator asked for. Raising it
again **requires raising the envelope first**. The envelope is a **measured capacity limit, not a
preference**.

> **Second-order note.** With one fewer discretionary slot, each remaining rotating slot matters
> more — which sharpens an open defect: `core/skimmer.py:251`'s replace-hysteresis **voids on every
> restart** (scores are not restored, so a 0.55 candidate can evict a 0.90 incumbent, and deploys
> restart the runner every ~15 minutes). Filed as [[synthesis/owed-measurements]] item 30g; the
> PAXG change did not create it, but it raises its cost.

**It is genuinely reachable, not a listing.** AssetPairs-verified fallback meta
(`data/kraken_feed.py`): `PAXGUSD` **price_decimals 2, lot_decimals 8, ordermin 0.001**, costmin
**$0.50**. **ordermin 0.001 oz ≈ $4.25 at a $4,250 spot — the smallest ticket in the universe by
dollar value**, so gold is reachable by the sizer *at this account size*. Kraken quotes PAXG/USD at
a **2.86bps spread with 20 levels a side**.

**What it buys, honestly stated:** so far, **one instrument and one surviving prediction** — not
edge. It does not touch the standing problem. The binding defect remains **payoff asymmetry**
(0.561 observed vs **0.750** needed at 57.1% win rate, n=217 — [[concepts/payoff-asymmetry]],
[[synthesis/the-money-path-thesis]]), and **a regime read does not move that term**: it could only
ever raise `p` or select *when* to trade, and both decisive nulls of 2026-08-02 bound how much that
can be worth. **Cost was not the binding constraint; a better regime signal is not the first move
either.** Gold's genuine contribution to the book is **near-zero crypto beta** — a diversification
property, not an alpha claim.

---

## 6. What would earn it decision wiring

The house pattern is explicit: **the skimmer, the conviction formula and the context engine all
shipped as instruments first and earned their decision wiring later with measured evidence**
([[concepts/shadow-first-adoption]]).

> **A dial that has never been watched is not evidence — it is a guess with a number on it.**

Named in advance, so it cannot be moved later:

1. **A track record against realized outcomes.** The gradient's state at entry, joined to realized
   P&L, over enough closes to say something. The instrument now exports gradient, `rungs_seen`,
   per-rung returns and the state label to Prometheus, and the screening board's **TANGIBLE-VALUE
   LADDER** trend panel answers *"is fear travelling down the ladder?"* rather than printing a
   number — so the record accrues from today.
2. **Not before the 432-bar cohort's verdict.** The cohort holds at 17/50 and
   `scripts/cohort_eval.py` refuses a reading below 50; wiring a new input mid-experiment resets the
   era clock in three places at once ([[comparisons/horizon-96-vs-24-bars]]).
3. **Veto rights before alpha rights, if ever.** Any influence a slow contextual layer earns is
   **shade-down only** under [[concepts/asymmetry-law]], and admissible on a real-time loop only with
   a bound that holds **before the data arrives** ([[concepts/certificate-hierarchy]]).
4. **Graded, with the killing citation if rejected.** [[concepts/evidence-grading-ladder]] —
   a rejection without its reason gets re-litigated.
5. **And the honest possibility of a null.** If the gradient shows no relationship to realized
   outcomes, that is a result to file ([[concepts/honest-null-result]]), not a reason to keep
   tuning until it shows one.

Until then: **the ladder is a lens the operator can watch, and nothing else.**

---

## 7. Provenance discipline for this instrument

Two hazards this corpus has already paid for apply directly here, and are noted so a future session
does not rediscover them:

- **The status/board seam.** The `haven` block in `status.json` is **guarded** — a failure there must
  never cost a status write — and the **synthetic status fixture carries the block**, so the
  dashboard coverage test genuinely protects those panels. This is the exact fixture gap that had
  hidden the `gate_divergence` instrument from its own coverage test until 2026-08-05
  ([[sources/session-20260805-evening]], [[sources/telemetry-stack-audit]]).
- **Read-only means read-only.** The gradient consumes candles and writes nothing to `outputs/`
  beyond the status block and the metrics export. Any future QA entrypoint or replay path that
  exercises it must walk the one redirect — the enumeration that never joined the fixed one is an
  **eight-time-recurring class** ([[concepts/default-path-fallback-writes]]).
- **A stated restraint is a design intent until something measures it.** The AST test is what makes
  this page's "report-only" claim a measured property rather than an aspiration
  ([[comparisons/stated-invariants-vs-audited-reality]]). Every new registered disposition it might
  someday emit needs a registered code, never a bare string
  ([[entities/reason-code-registry]]).

## Related
[[sources/session-20260805-evening]] · [[sources/session-20260805-debug-sweep]] ·
[[sources/telemetry-stack-audit]] · [[entities/liquiditybot]] · [[entities/kraken]] ·
[[entities/config-guard]] · [[entities/observability-sidecars]] ·
[[entities/reason-code-registry]] · [[concepts/payoff-asymmetry]] ·
[[concepts/shadow-first-adoption]] · [[concepts/iron-law-of-debugging]] ·
[[concepts/default-path-fallback-writes]] ·
[[comparisons/horizon-96-vs-24-bars]] · [[comparisons/stated-invariants-vs-audited-reality]] ·
[[synthesis/the-money-path-thesis]] · [[synthesis/owed-measurements]] ·
[[synthesis/risk-posture-doctrine]]
