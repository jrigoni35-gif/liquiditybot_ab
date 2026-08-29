# TAIL-CONTROL-SIM — results (does capping the left tail flip net positive at real 60 bps?)

**Date:** 2026-08-29 · **Class:** SAFE (counterfactual estimate on realized
fills; reads history, writes docs/scripts/tests only; **no config, decision,
fill-sim, fee-booking, or order-lifecycle change; mints NO execution era**) ·
**Repo HEAD at run:** `1677a82a` · **Registration:**
`docs/quant/2026-08-29_tail_control_sim_registration.md`, committed STANDALONE
before any result at **`3d62e1ff2abf4818729427b64d0c954844cc7527`** (HEDGE-SIM
discipline: the registration names which decision becomes decidable; it never
decides). · **Harness:** `scripts/tail_control_sim.py` + `tests/test_tail_control_sim.py`
(shipped `127be69e`, 11 pins green). · **Snapshot:** `outputs/fills.csv`
sha256 `c0747a40…d49e`, 185789 bytes, **mtime 2026-08-29T06:27:45.096Z**, read
this session; the live file has not grown since registration (sha identical),
so this run **is** the registered snapshot.

---

## THE ANSWER (operator's question: focused on profit)

**Does controlling the left-tail losers flip net POSITIVE at real Tier-3
60 bps, and by how much?**

**As a POINT ESTIMATE: yes — the tightest stop-cap (−0.5%) flips the
equal-weighted cohort from −0.30%/trip to +0.51%/trip at 60 bps, and the
tail-reduction that does it is genuinely beyond concurrency noise (paired
improvement z=3.4). But the flipped-positive NET is NOT distinguishable from
zero at effective-n (z=1.44, 95% CI [−0.18%, +1.21%] spans zero, bootstrap
P(net≤0)≈5%), and its positive sign fully evaporates under either of the two
hazards the fills cannot see: the gap-through proxy reverts it to −0.28%, and
dropping the top-3 realized winners drops it to +0.17%.** So tail control is
the correctly-aimed lever — the fat-tail losers are exactly the controllable
stop-geometry class ALGO-5 operates on, not uncontrollable market gaps — but on
fills alone the +0.51% is an **UPPER BOUND that does not clear significance.**
The realistic prize requires the candle-store exit-geometry re-sim.

**Do not read "TAIL-CONTROL-PAYS" (the sim's frozen verdict label) as "a tight
stop is net-positive live."** The registered verdict fired because ∃ a policy
with positive mean AND distinguishable improvement — both true — but the label
conflates the paired *improvement* (distinguishable) with the resulting *policy
net* (not distinguishable from zero). Corrected reading below.

---

## THE NUMBERS (re-derived this run; primary = 60 bps, equal-weighted mean net/trip)

Cohort = the pre-registered era-4 verdict population, `cohort_eval.era4_trips`,
**n=63**, close-ts ≥ `max(B4_TS, CAPITAL_EPOCH_TS)` = 1786403127.0 =
2026-08-10T23:05:27Z, closes [2026-08-12T03:14:40Z, 2026-08-29T06:23:17Z] [K].
**Effective-n = 24.86** (mean uniqueness 0.395, SE inflation ×1.59) — every net
figure below is read at n_eff, never nominal 63 [K].

| bracket | null mean | best cap | cap mean | cap total $ | dMean (2·SE_eff) | improvement |
|---|---|---|---|---|---|---|
| **60 bps PRIMARY** | **−0.2986%** | −0.5% | **+0.5109%** | **+$7.79** | +0.8095 (0.4779) | **DISTINGUISHABLE** |
| 76 bps (all-taker) | −0.4586% | −0.5% | +0.4148% | +$6.66 | +0.8734 (0.5044) | DISTINGUISHABLE |
| 44 bps (both-maker) | −0.1386% | −0.5% | +0.6074% | +$8.93 | +0.7460 (0.4520) | DISTINGUISHABLE |

At the primary bracket, **all four caps** (−0.5/−1.0/−1.5/−2.0%) have a
distinguishable *improvement*, and three of four (all but −2.0%'s −0.089% at
76 bps) carry a positive *mean* at 60 bps. Median net at 60 bps is **+0.103%**
(unchanged by capping — caps touch only the left tail), net-positive fraction
**0.524**. The best mean is **double-derived**: pct-route +0.510918% == usd-route
+0.510918% (agree to 1e-9) [K].

---

## THE CORRECTION THAT MATTERS (two different claims, only one holds)

The sim reports the paired-improvement test (`dMean > 2·SE_eff(Δ)`). That is a
test of **"does capping change the net"** — and it passes decisively:

- **Paired improvement vs 0** (Δ = capped − null, per trip): dMean **+0.8095**,
  SE_eff 0.2390, **z=3.39** → distinguishable [K].

But the operator's profit question is **"is the resulting strategy net
positive"** — a test of the policy net against zero, which is a *different and
weaker* claim on this cohort:

- **Policy net vs 0** (cap −0.5% @ 60 bps): mean **+0.5109%**, sd 1.769,
  SE_eff **0.3548**, **z=1.44**, 95% CI **[−0.185%, +1.206%]** — **spans zero** [K].
- **Bootstrap** (eff-n-sized resample, k=25, B=20 000, seed 3):
  **P(net ≤ 0) = 0.049** [K].

**The headline is defensible only as "capping distinguishably IMPROVES the
net," never as "the tight-stop strategy is net-positive with confidence."** The
improvement is real; the level's positive sign is one melt-up's worth of tail
away from zero.

---

## WHY THE +0.51% IS A CEILING, NOT A LIVE PRIZE (the two hazards, quantified)

Both hazards are structural to a fills-only ledger (no intra-trip price path)
and both push the true prize **down**:

1. **Fill-at-cap / gap-through.** Truncating a −4.5% loser to −0.5% assumes the
   stop filled at exactly −0.5%; a candle that jumped the level fills worse.
   The sim's gap-through proxy denies the clean fill to the 21 deepest runners
   (null net < −2×cap): the −0.5% policy mean **reverts to −0.2796%** —
   **negative, and the improvement collapses to within-noise** [K]. That is the
   dominant driver: 21 of the 25 capped trips are gap-through candidates, so
   most of the +0.81% improvement rests on the optimistic assumption that deep
   losers stop cleanly.
2. **Winner truncation (unmeasurable here, the larger blind spot).** A −0.5%
   stop also fires on the intraday adverse excursion of trips that went on to
   WIN. This sim keeps every realized winner at full value because fills record
   only the close. Concretely, **dropping the top-3 realized winners drops the
   +0.51% to +0.17%; dropping even the top-1 halves it to +0.376%** [K] — the
   positive sign is carried by a handful of full-value winners that a live tight
   stop would have clipped. This cannot be corrected without the price path.

Either hazard alone removes the positive sign. **The true live prize is at or
below zero on this evidence, not the +0.51% ceiling.**

---

## THE TAIL IS CONTROLLABLE-CLASS (why ALGO-5 is aimed right, even so)

The lever is correctly aimed, which is the part that survives every deflation:

- **The worst-20% (13 of 63 trips) are all deep losers** clustered from −2.91%
  to −4.51% net at 60 bps [K] — a wall at the stop distance, not a smooth
  distribution.
- **Exit-reason join (cohort pids → exit legs):** of the worst 13, **9 carry an
  explicit `tb_sl` triple-barrier stop-out reason and the other 4 carry no
  exit-leg reason but sit at the same −2.9…−3.4% stop-distance cluster** [K].
  The companion descriptive lens classified all 13 as stop-outs (100% `tb_sl`,
  median 2.40% gross stop distance, zero classic gap-throughs, ~87% stop
  geometry / ~13% slippage) [I — that stronger label depends on an exit-reason
  join this run did not reproduce for the 4 unlabeled; the SHAPE, "worst tail is
  stop-outs at the stop distance," is confirmed here].
- **Concentration is extreme:** removing the worst 7 of 63 stop-outs flips the
  cohort net positive at **+10.8 bps equal-weight** (my re-derivation matches
  the companion figure exactly) / **≈+$3.5–4.1** (dollar figure convention-
  dependent: my per-trip-notional route gives +$3.53, the companion +$4.13) [K
  equal-weight / I dollar].

So the fat-tail losers are exactly the class ALGO-5 (stop widths + time-decay
exit ladder) operates on — **controllable geometry, not uncontrollable market
gaps.** That is the finding that licenses the ALGO-5 direction. But note the
gap between the two lenses: *removing* the worst stop-outs with perfect
foresight flips the cohort (+10.8 bps); *capping* them at a live stop level
does not clear significance (+0.51% ± CI spanning zero) — because you cannot
delete losers ex-ante, and a real stop-geometry change fires more often, fills
worse on gaps, and clips recoverable winners. The achievable prize is strictly
**below** both the perfect-foresight removal and the fill-at-cap ceiling.

## TIME-EXIT screen (SCREENING-ONLY — net deferred to candle re-sim)

Losers hold longer than winners, so the time-decay rung is worth the follow-up:
**<6h: 32/63 (50.8%) touched · <12h: 22/63 (34.9%) · <24h: 18/63 (28.6%)** [K]
vs the 36h barrier. Net improvement is un-estimable on fills (a time exit
re-prices the close at a price the ledger cannot supply) — DEFERRED to the
candle-store re-sim.

---

## VERDICT & era-mint status

- **Registered verdict (sim, frozen rule):** `TAIL-CONTROL-PAYS` — ∃ a policy
  with positive mean AND distinguishable improvement. Both clauses true;
  **read it as "capping distinguishably improves the net," not "the strategy is
  net-positive."**
- **Operator's profit question:** flips positive **as a point estimate only**
  (+0.51%/trip, −0.5% cap, 60 bps), improvement distinguishable (z=3.4), but the
  **net is not distinguishable from zero** (z=1.44, CI spans zero, P(net≤0)≈5%)
  and the sign does not survive either the gap-through proxy (−0.28%) or
  dropping 3 winners (+0.17%).
- **earns_era_mint = yes-but-needs-full-resim.** This is a promising, correctly-
  aimed ESTIMATE with a controllable tail — but it is the fill-at-cap UPPER
  BOUND, and the two hazards that would decide it (gap-through fills, winner
  truncation) are exactly the ones only the candle-store price paths can
  measure. A distinguishable *improvement* on an upper-bound net whose CI spans
  zero is a "run the heavier re-sim" result, not a "strong case."

**This finding is COHORT-RESETTING to ACT ON** (ALGO-5 = stop widths + time-
decay exit geometry; GB-1 give-back — pre-named in CLAUDE.md as the next
adjudication). Applying it **mints the next execution era and restarts accrual.**
This sim is the EVIDENCE for that decision, not the decision — the operator's
ARM is required and this SAFE counterfactual does not and cannot ship the change.

## NEXT STEP (concrete)

**Run the ALGO-5 candle-store exit-geometry re-sim** over `data/candle_store`
(coverage: `docs/quant/2026-08-29_candle_store_coverage.md`) on the ~30
uncensored paths, which turns both upper-bound hazards into measured effects:
(a) check whether each cap level was actually touched before the realized exit
and price gap-through at the next available bar, (b) apply the stop to the
intra-hold adverse excursion of realized winners (winner truncation), (c) score
the {6/12/24h} time-exit rungs at the forced-exit price. **Do NOT ARM a live
stop-geometry change on this fills-only estimate** — it is an upper bound whose
net CI spans zero; the re-sim is the gate between "aimed right" and "net-
positive," and only then does the operator's ARM decision (era mint) have its
evidence.

---

## PROVENANCE / CAVEATS (what this could not see)

- **Fee truth [I].** 22/38 Tier-3 is the operator screenshot (2026-08-29 14:58),
  not a venue-verified account row. OM-080 fee-recon has fired **n=0** (FEE-3
  open); every net figure inherits that one unproven assumption. The 60 bps
  primary is the maker-in/taker-out mix; 44/76 bracket it.
- **Effective-n [K].** n=63 nominal, n_eff 24.86 — every net and improvement is
  read at n_eff. A nominal-n interval would be ×1.59 too tight.
- **Single execution era by close-ts, not exec-era [K].** The cohort is the
  close-ts-selected verdict population (`era4_trips` classifies era report-only:
  60× `7-e7d5ca1a`, 1 blank, 1 mixed, 1 `8-ca55e2ba`). Not pooled across disjoint
  `label_era`.
- **Upper-bound by construction.** Fill-at-cap assumed (no gap-through) and
  winner truncation invisible — both optimistic, both resolvable only by the
  price path. On fills, the stop-cap prize is a ceiling.
- **Bootstrap seed 3, B=20 000; P(net≤0)=0.049** — seed-dependent at the third
  digit; the CI-spans-zero and z=1.44 conclusions are seed-independent.
