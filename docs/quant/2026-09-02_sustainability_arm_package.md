# Sustainability — what the evidence lets you ARM, and what it does not

**Operator ask (2026-09-02):** make the bot sustainable across spreads in bull and bear,
across rising volume (with the worry that rising volume brings stop hunts and fakeouts
that could liquidate positions), and consistent in value across trades and environments;
connect it to the FLOW/ETH difference; include BTC as the reliable reference.

**What this document is.** The measured answer to each concern, with its power floor,
followed by the specific change set the evidence supports for a typed ARM. Stop
geometry, sizing and entry decisioning are cohort-resetting under the era-6 moratorium,
so nothing here is implemented; it is the package you decide on. Five read-only
measurements (`wf_f66a5b27-2c7`, 12 agents, 0 errors), each with a placebo, a power
floor, a FLOW/ETH/BTC breakdown, and an independent verifier that re-derived its
headline; 10 verifier findings repaired in the memos before this was written.

**The headline, stated once.** None of the three named concerns is what threatens this
bot. All three premises are refuted at measured power. What the data shows instead is in
section 5: negative net expectancy in every environment, tightest on BTC, with no cell
anywhere clearing its own floor. Sustainability is not a spread, stop, or volume problem
here. It is an expectancy problem, and that was already the standing finding.

---

## 1. Spreads, bull vs bear — REFUTED on materiality

| | FLOW | ETH | BTC |
|---|---|---|---|
| median spread at signal, any regime | 33–38 bps | 0.04–0.05 | 0.01–0.02 |
| bear minus bull_quiet, within asset | **+3.22 bps** (the only real gap) | +0.001 | +0.003 |
| entries ever | **0** | 157 | 40 |

- The pooled "bear spreads are wider" result (−1.0 bps, CI [−1.5, −0.34]) was **fully
  reproduced by a placebo carrying no regime information** — a within-asset time-shift of
  the regime labels. It is asset-mix composition: FLOW is 34% bear rows, ETH 7%. Within
  asset the median gap across nine assets is **0.147 bps**.
- Spread is **1–5% of a 44–76 bps fee round trip** on every filled position; it never
  exceeded the fee round trip on any fill, in any era.
- **The gate already refuses wide-spread signals**: entered rows p90 2.3–4.2 bps against
  candidates 11.7–22.4; the share ≥10 bps falls from 0.28 to 0.00 in bull_quiet.
- Power: pooled MDE ~2× the median; FLOW ~1.2× (4–7 bps); ETH/BTC tick-pinned, so no
  sub-tick regime effect is measurable there at all.
- Instrument note: `spread_bps` is stored as clip(raw, 0, 60)/10; 151 FLOW/MINA rows are
  censored at the cap. Decode verified against live status and a planted ×1 defect.

**Connection to the triad:** the spread story *is* the FLOW story. ETH and BTC have no
spread to speak of in any regime; FLOW carries a ~35 bps spread against a 22/38 bps fee
schedule, which is why its cost floor is dominated by spread (share 0.43–0.46) while
ETH's and BTC's are dominated by the fee (≤0.005, 0.000).

## 2. Stop hunts and fakeouts — REFUTED at the 1-hour lane; 5-minute re-run pending

Population: 5,457 candidate stop-outs (barrier `tb_sl`, h432 era), 1,739 clusters, 22
day blocks. Placebo: random timestamps, same assets, same geometry, same count.

| reversal through entry within… | real | placebo | diff (CI) |
|---|---|---|---|
| 30 min | 2.7% | 3.5% | −0.8 pp [−3.4, +1.7] |
| 2 h | 13.5% | 13.1% | +0.4 pp [−6.8, +8.2] |
| 24 h | — | — | +6.8 pp [−12.5, +23.9] |

- **The reversal rate equals the volatility base rate at every horizon** from 5 minutes
  to 24 hours. Power floor: +4 pp at 30 min pooled, +15 pp at 2 h.
- **Rising volume into the stop does not raise reversal** (top growth quintile 8.5% vs
  placebo 10.8%); volatility raises reversal *and* the profit-barrier rate together —
  RESOLUTION, not DIRECTION, the barrier-geometry rule again.
- Triad at 30 min: FLOW +1.6 pp [−3.1, +8.4], ETH −2.0 [−5.6, +1.2], BTC +3.0 [−0.3,
  +7.5]. **"BTC is reliable" (lowest reversal above placebo): NOT earned** — BTC is the
  least-null of the three and its per-asset MDE is ~10 pp, so nothing is resolved.
- Cut-#7 (round-number widen-beyond, 2026-08-11): **UNDETERMINED** — 2 day blocks after,
  below the 5-block floor — and **vacuous on candidate rows by construction**, because
  the nudge applies to live stop prices only (`main.py:1630`), never to the labeler's
  `sl_frac`. It can only ever be measured on live stops, of which there are 27 after.
- Verifier corrections carried into the memo: the reversal window had included the stop
  bar itself; the BTC MDE was 4 pp, re-derived at 10 pp; the "volume-driven stops look
  like genuine breaks" gloss was unsupported and struck.
- Instrument verified: stop hour agrees 99.0% with the venue lane (n=3,704); injection
  entry:=stop → 0.94, side-flip → 1.00.

**Resolution caveat, and why a re-run is queued:** this pass could time a stop only to
the hour. Sub-hour lanes did not exist when it started; they do now (5 m and 15 m for
all 15 assets, built from the tape). The 5-minute pass (`wf_f4033e09-41f`) adds the one
measurement the hour cannot make — the **depth and duration of the sweep beyond the
stop**, which is what separates a hunt (shallow, short, reverses) from a break. **Slot:
`[5m]` — to be filled when it lands.**

## 3. Rising volume and outcomes — REFUTED at power floor

- Top-minus-bottom quintile of 1-hour trade-count growth on realized return: **+0.19%
  [−0.05, +0.36]** — the *opposite* sign to the worry, and null. Stop rate beyond what
  resolution explains: **−0.027 [−0.065, +0.017]** — null. Stop rate sits at 0.52–0.56 in
  all five bins.
- Through the shipped decomposition instrument: **every volume feature NULL**; its own
  power calibration detects 0.05 SD 100% of the time.
- Power: pooled return MDE ~0.4%, stop-rate MDE 0.05 absolute; per-asset floors 2–4×
  wider (FLOW ~1.3%, ETH/BTC ~0.8%), so the triad refutes only large effects.
- **"BTC is reliable" as lowest stop rate: ordered as hypothesized (BTC 0.508, ETH
  0.577, FLOW 0.602) but all CIs overlap — not earned at this n.** And BTC has the
  *lowest* cost-clearance rate of the three (0.269).
- Verifier correction: the pooled volume quintiles were an asset selector (the top
  quintile was 47% ARB+PAXG+MINA); repaired to within-asset sorts.

## 4. Leverage and liquidation — REFUTED, with the formula flagged UNKNOWN

- Realized leverage per position: p50 0.004×, p90 0.023×, max **0.119×**; **account-level
  aggregate max 0.344×** (verifier correction: margin level is account-level, and ADA
  short hedges at 0.269× of equity had not been counted). Region cap 10×.
- Config-derived liquidation floor (margin_block at 150%) sits **~138× further away**
  than the configured stop at the aggregate max (per-position headroom 404–536×);
  **zero stop/liquidation violations in 324 positions**; crossover leverage where the
  two would meet: **5.88×** (verifier-corrected from 6.67×), ~17× above the aggregate
  maximum ever observed.
- The margin-block and margin-scale branches have **never fired** (two routes agree).
- Stop provenance from signal rows is **141/331 = 42.6%**, not the 97.9% first reported
  (183 joined rows carry `sl_frac == 0`); the rest use the config fallback.
- **UNKNOWN and load-bearing:** Kraken's real maintenance-margin/liquidation formula is
  encoded nowhere in the repo. Every headroom number above uses the bot's *own* 150%
  floor as the boundary. This is dry-run; no liquidation can have occurred.

**So: at 0.34× a stop hunt cannot liquidate this bot. It can only stop it out**, and
section 2 says it is not doing that above the base rate either.

## 5. Consistency of value across environments — REFUTED, and this is the real finding

| net of 0.6% cost, candidate h432 rows | mean | CI | MDE |
|---|---|---|---|
| POOL (n=6,042, 10 blocks) | **−0.71%** | [−1.03, −0.39] | 0.48 |
| FLOW (n=348) | −1.53% | [−2.15, −0.95] | 0.84 |
| ETH (n=602) | −1.10% | [−1.52, −0.69] | 0.59 |
| BTC (n=290) | −0.82% | [−1.05, −0.56] | **0.35** |

- **No regime, side, asset or era cell has positive net expectancy clearing its floor.**
- Between-regime spread of cell means sits inside the shuffled-label null in every slice
  (pooled p=0.18; BTC p=0.09, and p=0.043 only when cells the memo refuses for CI are
  admitted). The environments do not differ; they are all negative.
- **Shorts lose less than longs** — pooled −0.55% vs −0.83%, spread 0.28 pp, p=0.000
  against a shuffled null of 0.19; FLOW 1.84 pp, BTC 0.71 pp, ETH not significant. A
  difference in the *size of the loss*, not a positive cell: the pooled short upper CI
  bound is −0.08%.
- Live trips (326, cross-implementation exact): **no era clears its floor** — era 7
  −21.9 bps against a floor of 97.5; era 9 −146.2 bps on 4 days, no CI; era 8 refused.
- **"BTC is reliable" as tightest CI: EARNED — and the tight interval is reliably
  negative.** That is the honest reading of "reliable" on this data: BTC is the asset on
  which the absence of edge is measured most precisely.
- **FLOW cannot be measured on realized trades at all**: 472 of 1,067 signals refused
  as SZ-045 (the illiquidity-detector finding), zero fill legs ever. Its candidate cells
  are the worst of the three (bull_quiet long −3.86% [−4.06, −3.62]).

---

## The change set the evidence supports — for a typed ARM

| # | change | class | verdict from the measurements |
|---|---|---|---|
| A | Any spread-conditioned entry or regime-conditioned spread rule | cohort-resetting | **Do not arm.** Spread is 1–5% of cost, tick-pinned on ETH/BTC, and the gate already refuses wide spreads. FLOW's spread is the listing, not a regime. |
| B | Stop widening, time-decay ladder, or anti-hunt logic (ALGO-5 bundle) | cohort-resetting | **Do not arm on this evidence.** Reversal equals the base rate at every horizon at the hourly lane. Hold for the 5-minute excursion result `[5m]`; if that is also null, ALGO-5's anti-hunt half has no measured motive. |
| C | A volume-growth veto or sizing term | cohort-resetting | **Do not arm.** Effect null with the opposite sign; every volume feature NULL through the instrument. |
| D | Encode Kraken's maintenance-margin / liquidation formula in the repo | **SAFE**, additive | **Arm this** before any live arm ever happens. Every headroom number today uses the bot's own floor because the venue's rule is not in the code. |
| E | Register an audit code for the margin-block / margin-scale branch and log it through the audit trail | **SAFE**, additive | **Arm this.** A branch that has never fired is currently invisible if it does. |
| F | FLOW listing | traded universe (operator) | The data says FLOW is a spread and liquidity cost with zero fills; keeping it costs gate cycles and yields nothing measurable. Yours. |
| G | The "shorts lose less" difference | none — measurement lead | Pre-register a look at whether side asymmetry survives the next cohort. Not a change; a question. |

**What would change this package:** the 5-minute stop-hunt result showing shallow,
short excursions beyond the stop that reverse at a rate above placebo — that would put B
back on the table with a measured motive. Nothing else in these five memos points at a
decision-path change.

## Provenance
`docs/quant/2026-09-02_spread_by_regime.md` · `…_stop_hunt_fakeout_signature.md` ·
`…_volume_growth_outcomes.md` · `…_leverage_liquidation_distance.md` ·
`…_expectancy_by_environment.md` — each with as-of stamps, block counts, placebo tables
and power floors; verifier findings repaired in place. Sub-hour lanes: HANDOFF item 17.
