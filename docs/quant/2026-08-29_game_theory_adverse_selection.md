# Game-theoretic adverse selection — is the bot the sucker, or just edge-less?

**Date:** 2026-08-29 · **Class:** SAFE (pure measurement; reads
`outputs/fills.csv` + the read-only candle store; writes only docs/scripts/
tests; no decision path, feature, veto, sizing rule, fill sim or order
lifecycle touched or imported) · **Repo HEAD:** `933859f4` ·
**Instrument:** `scripts/adverse_selection.py` (new, this doc) +
`tests/test_adverse_selection.py` (mutation-killed) · **Interpreter:**
`./.venv/Scripts/python.exe`.

## The one-paragraph answer

The bot is **NEUTRAL / edge-less — NOT adversely selected.** The
already-established fact that gross edge ≈ 0
(`docs/quant/2026-08-29_fee_anatomy.md`: clustered t=0.51, G=35 days) had two
possible shapes, and this decomposition tells them apart: the ~0 gross is a
**symmetric null**, not a negative alpha masked by a maker rebate. On the
bot's core fills — the 451 maker entries — the side-signed mid-to-mid **alpha
is indistinguishable from zero** (kraken/USD 4h: −7.6 bps, n_eff 80, t=−0.72,
CI95 [−28, 13]; okx/USDT 1h: −3.0 bps, t=−0.61) and the **spread capture is
also ≈ zero** (−0.3 / −0.2 bps) because the traded pairs are too tight
(median spread 1.3 bps, `fee_dominance_diagnosis`) to earn a maker rebate.
gross ≈ alpha(≈0) + spread(≈0): a genuine efficient-market null, corroborated
by a day-cluster bootstrap (CI95 [−19, +5], P(mean<0)=0.876 — a mild negative
lean, not significance) and by the entry-alpha **sign FLIPPING across
execution eras** (era-4 −10.7 bps, era-7 +18.7 bps) — a robustly picked-off
player would be negative in every era. The **maker's winner's curse is NOT
observed**: maker entries are no worse than taker entries (at okx, takers are
*more* adverse). There is **one genuine adverse pocket** — taker *buy*
crossings (crossing the spread on urgency): significantly negative on both
venues (kraken 4h −35.8 bps SIG, okx 1h −21.5 bps SIG, n=38) — but it is ~13%
of entries and economically negligible ($7.58 go-forward, `fee_anatomy` §5.2).
The loss is **entirely the rake**, and the rake is **2.5–4.4× a typical
holding-window price move**. Equilibrium implication: the correct response to
a no-edge negative-sum game is to *not play / play less* — precisely what cut
#8's probe-dominated 0.8335 entry bar does.

## Population & provenance (contract: exact bounds, named needles, stamps)

- **Fills:** `outputs/fills.csv` (`core/fill_ledger.py` COLS). Snapshot
  **mtime 2026-08-29T06:27:45Z**, read **2026-08-29T20:01:13Z**. Values are
  as-of that snapshot (LIVE RUNNER RUNNING; file read-only). **n = 1173**
  data rows, `ts` ∈ **[1784583391.251, 1787984864.635]** =
  **[2026-07-20T21:36:31Z, 2026-08-29T06:27:44Z]** [K] (parsed with
  `csv.DictReader`, NOT shell `cut` — the `reason` column carries embedded
  commas that shift naive splits; this is the instrument-discipline trap the
  dispatch named).
- **Needles:** maker/taker = `post_only` (`'1'`→maker, `'0'`→taker; leg =
  `purpose` ∈ {entry, exit, hedge}; side-sign from `side` (buy=+1, sell=−1),
  `execution/markout.py`'s convention verbatim.
- **Composition** [K]: 469 maker / 704 taker; 656 buy / 517 sell; **entry
  maker 451 / taker 70; exit maker 18 / taker 475; hedge 159 taker (100%)**;
  all 1173 `ordertype=limit`. 14 symbols (ADA 390, ETH 218, BTC 148 dominant).
- **exec_era mix** [K]: 1024 blank + 6 absent (pre-stamp era-4-and-earlier),
  **133 `7-e7d5ca1a`**, 6 `8-ca55e2ba`, 4 `4-aeeaae36`. **The file pools ≥5
  execution eras** — the same caveat `fee_anatomy` carries.
- **Forward price** = the candle store (`data/candle_journal.py`,
  `docs/quant/2026-08-29_candle_store_coverage.md`), reused not reinvented.
  Per that doc's recommendation, **kraken/USD @ 4h** (execution venue at the
  traded quote, full-coverage over the fills window) is PRIMARY and
  **okx/USDT @ 1h** (finer, but a ~+9 bps USDT/USD quote confound) is the
  CROSS-CHECK; a conclusion is drawn only where the two **agree in sign**.

## The measure (reused from execution/markout.py, not invented)

    markout_bps = side_sign * (mark - fill_price) / fill_price * 1e4
    side_sign   = +1 for a BUY fill, -1 for a SELL fill

POSITIVE = market moved in the trade's favour after the fill (favourable);
NEGATIVE = market moved against it (adverse selection / picked off). Per
`markout.py`'s own decomposition note, raw markout = **spread capture**
(fill-vs-mid, fixed at fill, carries no forward info) + **alpha** (mid-to-mid,
the half worth watching). This study reports all three; **alpha is the
decisive adverse-selection signal**. `mark` is a candle CLOSE, so alpha equals
`candle_journal.forward_return(...) × 100` by construction — the validated
instrument.

**Sign convention PROVEN, not assumed.** A markout sign error inverts the
whole conclusion, so `self_test()` plants 7 cases (buy+up→+, buy+down→−,
sell mirror, magnitude, alpha, spread-capture) and the CLI aborts if any
fail. Mutation evidence (this session): negating `raw_markout_bps` reds 5
test pins; defeating `effective_n` reds the overlap pin; both restore green
(`tests/test_adverse_selection.py`, 10/10).

**Effective-n** is pooled cross-asset **concurrency uniqueness** (Lopez de
Prado form: `u_i = 1/‖{j : windows overlap}‖`, `n_eff = Σ u_i`), the honest
denominator for the SE — crypto co-moves, so overlapping fills are not
independent draws. Deflation is severe and horizon-driven: n=1173 →
**n_eff 214 @1h, 93 @4h, 19 @24h** (5.5×–60×). At 24h nothing is resolvable;
the verdict rests on 1h/4h.

## 1. ADVERSE SELECTION / MARKOUT — the entry leg [K]

Side-signed alpha (bps), the adverse-selection meter. NEW-risk **entry** fills
answer "after I entered, did the market move against my position?"

| cohort | lane | horizon | n | n_eff | mean alpha | CI95 | t_eff | verdict |
|---|---|---|---:|---:|---:|---|---:|---|
| **entry (all)** | kraken/USD | 4h | 521 | 93.5 | **−6.96** | [−26.0, +12.1] | −0.72 | **ns (neutral)** |
| **entry (all)** | okx/USDT | 1h | 521 | 158 | **−4.12** | [−12.9, +4.7] | −0.91 | **ns (neutral)** |
| entry (all) | okx/USDT | 4h | 521 | 93.5 | −3.78 | [−27.0, +19.5] | −0.32 | ns |
| entry (all) | kraken/USD | 24h | 520 | 19.7 | −20.1 | [−135, +95] | −0.34 | ns (n_eff too low) |
| overall (all legs) | kraken/USD | 4h | 1173 | 93.3 | −4.34 | [−26.2, +17.5] | −0.39 | ns |

**Double-derive of the headline** (kraken/USD 4h entry alpha, two independent
SE routes): concurrency-deflated CI95 [−26.0, +12.1]; **day-cluster bootstrap**
(resample 36 UTC days w/ replacement, matching `cost_attribution`'s G=35)
CI95 **[−19.2, +5.4]**, mean −6.96, **P(mean<0)=0.876**. Both straddle zero;
the point estimate leans mildly negative but does not clear significance.

**Era-invariance check** (kraken/USD 4h entry alpha): era-4/pre-stamp
**−10.70 bps** (n=444, n_eff 51) vs era-7 **+18.74 bps** (n=73, n_eff 39) —
**the sign flips**. A structurally picked-off player is negative in every era;
this is noise around zero, and pooling it is era-mixing (descriptive of the
whole realized book, not any single era).

**Decisive:** mean entry markout is **indistinguishable from zero**
(neutral), NOT significantly negative (adverse). To measurement precision the
bot's entries are drawn from a **zero-alpha** distribution.

## 2. THE MAKER'S WINNER'S CURSE — refuted (the core), plus one leak [K]

Game theory predicts maker fills are adversely selected (a resting order fills
only when the market is about to run past it). **Not observed on the entries
that matter:**

| entry cohort | lane | horizon | n | n_eff | alpha | spread cap | verdict |
|---|---|---|---:|---:|---:|---:|---|
| **maker** | kraken/USD | 4h | 451 | 80 | **−7.56** | **−0.27** | ns |
| **taker** | kraken/USD | 4h | 70 | 32 | −3.15 | −15.9 | ns |
| **maker** | okx/USDT | 1h | 451 | 136 | **−3.00** | **−0.16** | ns |
| **taker** | okx/USDT | 1h | 70 | 43 | −11.32 | −2.27 | ns (t=−1.55) |

- **Maker entry alpha is NOT worse than taker's.** On okx it is *better*
  (takers −11.3 vs makers −3.0). The winner's-curse prediction fails.
- **Spread capture on maker entries ≈ 0** (−0.27 / −0.16 bps). The pairs are
  too tight to earn a rebate (`fee_dominance`: median spread 1.3 bps), so
  there is **no spread-capture masking a hidden negative alpha** — the crux
  that turns "gross≈0" into a genuine null rather than adverse-masked-by-rebate.

**The one genuine adverse pocket — taker BUY crossings** (crossing the spread
to buy on urgency, `execution_tactics.allow_taker`):

| cohort | lane | horizon | n | n_eff | alpha | CI95 | t_eff |
|---|---|---|---:|---:|---:|---|---:|
| entry taker **buy** | kraken/USD | 4h | 38 | 19 | **−35.8** | [−69.6, −2.1] | **−2.08 SIG** |
| entry taker **buy** | okx/USDT | 1h | 38 | 24 | **−21.5** | [−40.1, −2.9] | **−2.27 SIG** |
| entry taker **buy** | okx/USDT | 24h | 38 | 11 | **−99.0** | [−184, −14] | **−2.29 SIG** |
| entry taker sell | kraken/USD | 4h | 32 | 20 | +35.7 | [−6.7, +78] | +1.65 ns |

Taker *buys* are significantly adverse on **both venues** (sign-agreement);
taker *sells* are not. This is momentum-chasing crossing flow getting picked
off — a real but small (13% of entries) and economically trivial leak
(`fee_anatomy` §5.2: forcing them maker is worth **$7.58** total).

**Non-entry legs, reported and NOT over-read.** EXIT alpha is positive/SIG
(kraken 4h +34.9 bps, t=2.77) — but exits are side-signed by the *closing*
order, so this is **exit-timing** (the move continues in the exit's favour
after a stop/scratch), not position adverse selection. HEDGE alpha is strongly
negative (kraken 4h −117 bps) but **n_eff = 2.75** (≈1–3 churn episodes; the
apparatus prints "SIG" on an effective sample of ~2 — an instrument caution,
not a finding) and is structurally the *cost of insurance* (a hedge loses when
the position it protects wins), never adverse selection.

## 3. TOXICITY CONDITIONING — no informed-flow gradient [K]

376 closed live trips, realized net = `net_pnl_usd` (BOOKED fees; the venue
rake is a near-constant per-trip offset, so a net gradient across toxicity
buckets reflects the gross gradient — a valid adverse-selection test). *(GROSS
per trip is deliberately NOT used: live corpus rows store `exit_price=0.0`
= "absent" per `ml/history.py`, and `ml.corpus.gross_ret_pct` guards only
`entry<=0`, so it returns a spurious ±100% for every live row — verified this
session, the instrument-is-first-suspect trap, would have been misread #6.)*

| flow_tox quantile | range | n | n_eff | mean net | win rate |
|---|---|---:|---:|---:|---:|
| Q1 (low) | [0.00, 0.41] | 94 | 30.9 | −$0.172 | 0.351 |
| Q2 | [0.41, 0.59] | 94 | 46.1 | **−$0.249** | 0.149 |
| Q3 | [0.59, 0.69] | 94 | 40.8 | −$0.111 | 0.213 |
| Q4 (high) | [0.69, 0.92] | 94 | 30.9 | −$0.148 | 0.106 |

- **No monotone loss-worsening with toxicity** (Q2 is worst, Q4 is middle).
  The loss is roughly **toxicity-invariant** — the fee-domination signature,
  not informed-flow selection. A weak hint (win rate falls Q1 0.351 → Q4
  0.106) does not carry into net, because both wins and losses are fee-capped
  small tickets.
- **manip_suspect split:** manip==0 −$0.144 (win 0.228, n=114) vs manip>0
  −$0.181 (win 0.195, n=262) — marginally worse under suspicion, within
  n_eff noise. Not a gradient.

## 4. THE RAKE AS HOUSE EDGE — 2.5–4.4× a typical move [K]

Rake = venue-true median round-trip **120.8 bps** (`fee_anatomy` §2, cited).
"Typical move" = median **|alpha|** over entry fills at the ~holding horizon
(clean candle-store measure of the game's natural volatility):

| lane / horizon | typical \|move\| | **house edge = rake / move** |
|---|---:|---:|
| **kraken/USD 4h** (primary) | 48.5 bps | **2.49×** |
| okx/USDT 4h | 41.3 bps | 2.93× |
| okx/USDT 1h | 27.5 bps | 4.39× |

**The house takes 2.5–4.4× a typical price move over the holding window.** For
a trade to net positive it must catch a move several times larger than typical
*just to clear the rake*. This is the structural, one-number statement of
"fee-dominated" and it is exactly why `fee_dominance_diagnosis` finds no
economic mode that clears at Tier-1 fees on liquid pairs.

## THE OUTCOME, in game-theoretic terms

**NEUTRAL / edge-less — NOT adversely selected.** The bot is not the "sucker"
being systematically picked off by informed flow; its fills are, to
measurement precision, drawn from a **zero-alpha efficient-market
distribution**, and the near-zero spread capture means there is no maker
rebate hiding a negative alpha. It is simply a **no-edge player in a
negative-sum game** whose rake (2.5–4.4× a typical move) it cannot overcome.
Providing liquidity is not being exploited — but the spreads are too thin to
earn from it either, so there is no maker-side escape. The single exploitable
leak (taker-buy crossings) is small and economically trivial.

**Equilibrium strategy.** Against a negative-sum game with no measurable edge
and no adverse-selection signal to trade *against*, the dominant strategy is
**not to play, or to play only where a rare large move can clear the rake** —
which is precisely cut #8's probe-dominated 0.8335 entry bar and the
GB-1/ALGO-5 "let winners run" lever (`fee_dominance` Phase 4.4). This
corroborates `fee_dominance_diagnosis` and *sharpens* it: the ~0 gross is a
genuine null, **the market is boring and efficient and the rake is real** —
the-method's preferred explanation (ordinary market, fallible-but-here-sound
apparatus), vindicated again.

## What the analysis could NOT see (a green is only as big as its corpus)

1. **Sub-hour pickoff is INVISIBLE.** The finest stored candle grid is 1h
   (`candle_store_coverage` §7.5: 5m not fetched). Classic HFT adverse
   selection — fill, then the market runs past in *seconds* — cannot be
   measured here. These horizons (1h/4h/24h) measure drift over the bot's
   ~2h holding period. "Not adversely selected" holds at the ≥1h scale; a
   faster pickoff could exist below it and would not show.
2. **Reconstructed, not true, forward prices.** `mark` is a public-OHLC
   CLOSE, floor-anchored; the anchor close post-dates the fill by up to one
   interval (up to 4h on kraken), so the alpha window starts up to `iv` after
   the fill and *under-counts* the most immediate post-fill drift
   (conservative for the adverse hypothesis). It is not the true mid/quote the
   bot faced, and okx carries a ~+9 bps (range 26 bps) USDT/USD quote confound
   — a bias, not noise (hence the sign-agreement requirement).
3. **Effective-n limits.** n_eff is 19–214 (12×–60× deflation); at 24h
   (n_eff≈19) nothing resolves and those rows are read as ns-by-power, not as
   nulls. The verdict rests on 1h/4h. n_eff is pooled cross-asset
   (conservative); a per-asset n_eff would be larger.
4. **Era pooling.** ≥5 cost/geometry eras; the entry-alpha sign flips across
   them. The pooled markout is descriptive of the whole realized book, never a
   single-era result (fee re-pricing would be era-invariant; forward *drift*
   is not).
5. **Survivorship / censoring.** fills.csv is the book of record (OM-085
   dedups restart replays); 2 fills are right-censored at H=24h
   (`forward_BEYOND_RIGHT_EDGE`), and the kraken 1h left-edge gap is avoided
   by using kraken **4h** (full-coverage). Trips that never closed are not in
   the corpus net.
6. **Leg semantics.** Exit and hedge markouts are side-signed by the *order*
   side, so they measure exit-timing and insurance cost, not position adverse
   selection — the entry leg is the only clean adverse-selection read.
7. **Venue truth.** 40/80 is the published Tier-1 schedule; OM-080 has never
   fired (n=0, FEE-3), so the rake magnitude inherits that one unproven
   assumption.

## Re-derive

```
./.venv/Scripts/python.exe scripts/adverse_selection.py            # full report
./.venv/Scripts/python.exe scripts/adverse_selection.py --self-test # sign proof
./.venv/Scripts/python.exe -m pytest tests/test_adverse_selection.py -q
```
No number here is durable; each is stamped in the sections above and
re-derivable with the commands. Where a later run disagrees, the later run is
right.
