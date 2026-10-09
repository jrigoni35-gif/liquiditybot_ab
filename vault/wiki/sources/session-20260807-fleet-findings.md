---
title: "The Fleet Night Sweep (2026-08-07 night) — Fill-Sim TTL Skew, the Losing-Even-With-Gifts Reframe, Frozen Inputs, Dead Latency Gates, First Coverage Baseline"
category: source
summary: "Eight findings, each re-verified against the box at filing. (1) FILL-SIM SKEW, CRITICAL: sf_base=0.048 was calibrated at n_bar=5 (25s life / 5s polls) but is drawn PER POLL, so a 6h long-book bid (~4,320 polls) compounds to fill prob ~1.0 — verified arithmetically against outputs/fill_calibration.json — on top of a deterministic _sim_maker_cross path that fills full remaining on the SAME trade-through predicate the calibrator measured (double-count), with no depth constraint; 22/41 post-08-03 entries at exactly -50.0bps (+2 deeper), all post-only BTC/ETH. (2) THE REFRAME: even WITH those phantom -50bps gifts, performance.by_asset shows every asset negative except AVAX (n=3) — BTC 0/17 exp -$0.83, ETH 3/26 exp -$0.64, PF 0.0-0.119 — the sim's optimism is one-directional, so real would be WORSE. (3) INPUT-FEED SKEW: moomoo re-appends frozen closed-market quotes (verified live: identical +3.60% basket for hours, z collapsed to 0.00), sentiment volume gate structurally dead (items=200 every poll, vol_z=0, spikes can never fire), opt_iv_skew pinned at the -3.00 clip bound (verified in live log), feed failure arithmetically identical to neutral on the ML path. (4) LATENCY: the pre-trade staleness veto is arithmetically dead (book_ts=now compared against the same now; 4000ms ceiling unreachable), marks_age_sec reads 0.0, no cycle-duration telemetry; the main fill path is verified look-ahead-free (single orders.poll site). (5-6) Transcript bug-sweep adjudicated: 3 claims registered as owed, 3 REFUTED against the current tree (registry hash chain EXISTS since 4799bfc7; SMC daily_candles IS passed; skim bleed CLOSED 30c). (7) Coverage baseline measured: 88% of 17,789 stmts — closes owed 38(c). (8) Financial-analyst verdict: the strategy is not making money on its own realized evidence; the fill-sim fix is the #1 P&L-integrity item."
tags: [session, fill-sim, calibration, paper-mode, feeds, latency, coverage, bug-sweep, adjudication]
sources: 4
source_path: none — session work product (overnight fleet sweep, multiple parallel agents, re-verified at filing)
source_date: 2026-08
authors: [claude-fleet]
ingested: 2026-08-07
updated: 2026-08-08
---

# The Fleet Night Sweep (2026-08-07 night)

## Provenance and boundary statement

Work product of tonight's multi-agent fleet (fill-sim auditor, feed auditor, latency auditor,
transcript bug-sweep x4, coverage runner, financial analyst). **Every headline claim below was
re-verified against the box at filing time** — file:line reads, `outputs/fill_calibration.json`,
`outputs/status.json`, `outputs/fills.csv`, the live `runner.log`, and the `.coverage` file —
except where explicitly marked *fleet-measured, not re-derived*. Three transcript claims
**failed** re-verification and are filed as refuted, not as findings (§6).

**Paper/real boundary** ([[concepts/paper-real-boundary]]): findings 1 and 2 are about the
**simulator itself** — they are sim-side by construction and are evidence about the *instrument*,
not the venue. Finding 3 is **input-plane** (real external feeds read wrongly — repo-side defect,
venue/data-side symptom). Finding 4 is **repo-side**. Findings 5–7 are repo-side. Finding 8 is a
verdict over sim-side dollars and states so.

---

## 1. FILL-SIM SKEW (CRITICAL) — calibrated at 25 seconds, applied for 6 hours

The sharpest instrument defect found since the fill-regime recalibration, and it sits **inside**
that recalibration.

**The horizon mismatch, verified arithmetically.** `outputs/fill_calibration.json`:
`sf_base* = 0.048` (band [0.046, 0.050]) was derived from n=22,854 resting-limit trials with
**f_hat = 0.131 trade-through over a life of n_bar = 5.0 polls** (25s order life / 5s polls —
`scripts/calibrate_fills.py:341` derives `n_bar = life_sec/poll_sec`). The identity checks
exactly: per-poll p = 0.048 × e^(−0.544) ≈ 0.028, and 1−(1−0.028)^5 = 0.131 = f_hat. But
`_poll_dry` (`execution/order_manager.py:1240` region) draws `self._rng.random() < p` **on every
poll for the order's whole life** — and the long book submits entries with
`ttl_sec = order_ttl_hours × 3600 = 6h` (`config.json long_book.order_ttl_hours: 6.0`,
`main.py:5371`). At ~4,320 polls, 1−(1−0.028)^4320 ≈ **1.0**: a patient long-book bid is
**guaranteed to fill in sim**, at whatever offset it rests.

**The double-count, verified structurally.** `_poll_dry` first calls `_sim_maker_cross`
(`order_manager.py:1085`, invoked at `:1220`) — a **deterministic** fill of the **full
`order.remaining` with no depth or queue constraint** whenever the opposite touch crosses the
resting price. That crossing condition is **the same trade-through predicate
`calibrate_fills.py` measured** (its own header: *"how often the MARKET actually crossed a
hypothetical resting limit"*, `:81-91`). The stochastic sf_base draw then runs **in addition**
whenever the book did not cross — so the calibrated trade-through frequency is spent twice: once
as the deterministic event itself, once as the RNG hazard calibrated from its frequency.

**The ledger signature, verified with one correction.** Since 2026-08-03 UTC the fills ledger
holds **41 entry fills; 22 at exactly −50.0 bps** = `long_book.add_offset_pct = 0.5`, **plus 2
at −58.7 bps** — so **24/41 at ≥50 bps of "price improvement," 22 of them exact** (the fleet's
"24/41 at exactly −50.0" conflated the two; corrected here per domain rule 2). All 22 are
`post_only=1`: **BTC 13, ETH 9** — the long book's sim-gifted fills, concentrated in the two
assets finding 2 shows losing worst.

**The markout signature** (*fleet-measured, not re-derived at filing*): pooled maker markout
**+3.58 bps @5s** (ETH +14.8, BTC +11.2) where real passive fills should mark out **negative**
(adverse selection: you get filled when the market comes through you). Direction and flatness
across horizons were already panel-adjudicated as simulator physics
([[sources/session-20260807-institutional-review]] §f); tonight adds the *mechanism*: the
compounded hazard hands the resting distance to the book as phantom capture.

**Consequence chain:** every long-book paper fill, every markout row derived from one, and every
per-asset stat containing one is conditioned on a fill probability that is wrong by construction
for any order living longer than 25s. The fix (time-normalized hazard, or per-TTL n_bar
recalibration) is **owed item 40** and will mint a **third execution-regime boundary** (after
`8e5455e8`) when it lands — [[synthesis/owed-measurements]].

> **CLOSED the next morning — `3cfe0710`, 2026-08-08, the time-normalized-hazard option,
> deployed 11:10 local** ([[sources/session-20260808-morning-batch]] §1). Era boundary #3
> minted as predicted; ~~the double-count (b) disposed by design (`_sim_maker_cross` retained as
> genuine trade-through, calibrated hazard as conservative floor)~~; residual = XV-023 per-TTL
> recalibration (owed 40b). This finding's embargo now applies to **pre-boundary** rows only.

> ✅ **VINDICATED 2026-08-10 — and this paragraph was RIGHT while the next morning's disposal of
> it was WRONG** ([[sources/session-20260810-fill-double-count]], owed 57, era boundary #4).
>
> **The sentence above — *"the calibrated trade-through frequency is spent twice"* — is the
> correct mechanism, filed here on 2026-08-07 and confirmed three independent ways two days
> later**: by first-principles derivation, by reading `calibrate_fills.py`'s own definition of
> what it measures, and by the ledger. `core.fill_calibration.invert_base_prob` solves `sf_base`
> so **the hazard ALONE reproduces `f`**, and the hazard **only ever ran inside `if book:`** — so
> it was **purely additive to an observed cross**, never the *"conservative floor"* the 08-08
> disposition called it. Combined `2f−f² = 21.96%` against an `f = 11.66%` target,
> ledger-measured **22.30%** — agreement to **0.34 pp**. **1.88x at the touch, approaching 2x as
> f falls.** Fixed by `aeeaae36`; the 08-08 (b) disposition is **RETRACTED**
> ([[synthesis/open-contradictions-register]] entry 25).
>
> **The filable lesson is not about fills.** This finding **survived discovery and was lost at
> the DISPOSITION step** — talked away the following morning, in the same session as a
> celebrated fix, by an author with a motive to close the docket. **It cost two days and left a
> 1.88x bias live.** Add *adjudications* to the surfaces [[concepts/self-flattery-gradient]] acts
> on, and treat a disposition written alongside a win as needing the same adversarial pass as the
> win itself ([[concepts/adversarial-verification]]).

## 2. THE REFRAME — losing even with the gifts

`outputs/status.json performance.by_asset`, read at filing (sim-side dollars):

| Asset | Trades | Wins | Expectancy/trade | Profit factor |
|---|---|---|---|---|
| BTC | 17 | **0** | **−$0.83** | 0.0 |
| ETH | 26 | 3 | **−$0.64** | 0.119 |
| SUI | 23 | 2 | −$0.35 | 0.01 |
| LTC | 5 | 0 | −$0.25 | 0.0 |
| SOL | 14 | 0 | −$0.20 | 0.0 |
| ...every other asset | | | negative | ≤0.108 |
| AVAX | **3** | 2 | +$0.11 | 8.771 |

**Every asset except AVAX (n=3, unreadable) has negative expectancy; profit factors 0.0–0.119.**
And BTC/ETH — the two assets receiving the −50 bps phantom entry gifts — are the **worst books
by expectancy**.

This kills a tempting misreading of finding 1 before it is ever filed: **the fill-sim skew is
not manufacturing a paper edge**. There is no paper edge. The skew's direction is one-way
optimism (guaranteed fills at full offset, no queue, no depth, positive markout), so the honest
statement is an inequality: **real execution would be worse than these numbers, and these
numbers already lose.** This is the [[synthesis/the-money-path-thesis]] sharpened, not
contradicted.

## 3. INPUT-FEED SKEW — three inputs that cannot say "I don't know"

- **moomoo re-appends frozen closed-market quotes.** `data/moomoo_feed.py:218-272`:
  `_ret_hist.append(basket)` runs unconditionally each ~5-min poll, with **no market-hours or
  staleness guard** — a closed market returns the same last/prev_close forever. **Verified
  live:** `runner.log` shows identical `basket +3.60%` every ~5 min for hours with
  **z collapsed to +0.00** (the fleet's observed decay +0.39 → +0.15 over 2h was the road
  there). Every duplicate dilutes the history toward the frozen value, so the equity-risk
  z-input decays to neutral *by repetition, not by evidence* — with ~62h of closed-market
  weekend ahead.
  > **CLOSED 2026-08-08, commit `01d59908` (owed 41a,
  > [[sources/session-20260808-battery-split-freeze-gate]] §2):** a full-basket
  > per-ticker-return repeat is treated as the closed-market signature — frozen polls no
  > longer append, z holds its last honest value, the snapshot carries additive
  > `quotes_frozen`, and DF-010/DF-011 latch the episode transitions. 41(b)-(e) remain
  > open; 41(c) persistence stays deliberately sequenced after this gate. *(Update, same
  > day evening: 41(b) `64724480` and 41(c) `e22df720` CLOSED —
  > [[sources/session-20260808-evening-availability-persistence]]; 41(d)/(e) — the
  > saturation and clip bullets below — remain open.)*
- **The sentiment volume gate is structurally dead.** `sentiment/scanner.py:275-292`: fear and
  euphoria spikes require `vol_z ≥ volume_spike_z (1.0)`; but volume = items scored, per-source
  caps (`[:15]` per figure, `[:25]` per news feed) saturate at exactly **200 — verified: every
  observed poll reads items=200** — so mu=200, vol_z ≡ 0, and **the spike gates can never
  fire**. The scanner's own cold-start comment says 0.0 is "the fail-safe direction"; at the
  cap it is the *permanent* direction.
- **opt_iv_skew is pinned at its clip bound.** `moomoo_feed.py:351-359` clips to [−3, 3];
  the live log reads `skew=-3.00` on every recent poll — a rail, not a reading.
- **Feed failure is arithmetically identical to neutral on the ML path.** The context feature
  dict (`main.py:5703-5718`) consults **no `.available` flags**, and a dead feed's zeros are
  **byte-identical to the historical padding neutrals** (`ml/features.py:50-57`
  `CONTEXT_NEUTRAL`: opt_pcr_z/opt_oi_pcr_z/opt_iv_skew/manip_suspect all 0.0). The model
  cannot distinguish "options feed down" from "options flat" from "row predates the feature."
  > **CLOSED at the record layer 2026-08-08 evening, commit `64724480` (owed 41b):**
  > every corpus row now carries `avail_web`/`avail_equity`/`avail_options`/
  > `quotes_frozen`, with `""` = UNKNOWN ≠ `"0"` = measured down — at zero model DoF;
  > the model input itself is deliberately unchanged
  > ([[sources/session-20260808-evening-availability-persistence]] §1).
- **Rolling windows rebuild empty every restart.** The one correct pattern —
  `data/context_engine.py:566 _warm_start`, which re-seeds prev-values from the PIT file's last
  line — is applied to **1 of ~6** in-memory windows (fleet inventory; moomoo `_ret_hist` and
  the sentiment volume history verified in-memory-only). At the measured restart cadence
  (median 0.5h) that is ~3.5h/day of fabricated-neutral context (*fleet-derived figure*).
  > **CLOSED 2026-08-08 evening, commit `e22df720` (owed 41c):** the moomoo z-windows +
  > freeze state persist via `MoomooFeed.to_dict/from_dict` + StateStore `"moomoo_state"`
  > (poll timestamps deliberately not persisted — immediate re-poll wanted), with the
  > 41a×41c composition pinned by test: a still-frozen market reads frozen on the first
  > post-restart poll, never re-seeded from the frozen quote. 5 tests in
  > `test_moomoo_persistence.py`
  > ([[sources/session-20260808-evening-availability-persistence]] §2). The sentiment
  > volume history stays in-memory-only but is moot while (d)'s saturation stands.

Filed into [[concepts/zero-is-not-a-reading]] (the class these all belong to) and owed item 41.

## 4. LATENCY — the veto that measures its own stamp

- **The pre-trade staleness veto is arithmetically dead.** `main.py:2420` stamps
  `self.book_ts[asset] = now` at book ingestion; `main.py:4403` computes
  `staleness_ms = (now − book_ts) × 1000` **with the same cycle-frozen `now`** — so the veto
  reads ~0ms always, against a `max_data_staleness_ms = 4000` ceiling
  (`execution/pretrade.py:96,236`) it can structurally never reach. A REST hang, a slow cycle,
  a stale cached book — all invisible to the one gate built to catch them.
- **`marks_age_sec` reads 0.0** (live status verified): `runner.py:1163` computes
  `now − _mark_ts.get(s, now)` while `main.py:2402/2438` re-stamp `_mark_ts` with the same
  per-cycle clock — same shape, and the `.get(s, now)` default makes a *missing* mark read as
  perfectly fresh. Filed with the dead veto into [[concepts/tautological-instrument]].
- **No cycle-duration telemetry exists.** `cycle_lifetime` (runner.py:1136) is a **counter**,
  not a duration; the runner's own comments document measured 50–88s stalls, but nothing
  emits how long a cycle took.
- **Candles up to ~450s old feed sizing with no bar-timestamp check** (*fleet-verified; not
  independently re-derived at filing*).
- **The main fill path is look-ahead-free — a positive finding.** Exactly **one**
  `orders.poll(...)` site in `main.py` (line 2459), with entries submitted after it in the
  cycle; verified by count. A **dormant** look-ahead seam exists in the exec-algos path
  (`execution/algos.py`) **if ever enabled** — it is not enabled (*fleet-flagged*).

## 5. REST `_deny` RST — already filed

Already registered as [[synthesis/owed-measurements]] **item 39** (verified present); nothing
new tonight.

## 6. The 20-transcript bug sweep — adjudicated against the current tree

Four agents ledgered ~200 distinct bugs across all 20 session transcripts. Per governance rule 8
only **verified** items enter the wiki as facts; tonight's re-verification of the flagged
"still-open" shortlist split it:

**Registered (verified still true on the box — owed item 43):**
- **CRLF bundle-transport port unconfirmed.** The Jul-18 zip carried the fix; the current
  `.gitattributes` (457B) holds only `* text=auto eol=lf` + `*.bat eol=crlf` — **no binary/-text
  pin for the telemetry bundle paths**, so byte-exact CSV transport through git line-ending
  conversion is unpinned on the current tree.
- **Registry `ok=None` acceptance.** `ml/registry.py:84,244` — a **never-registered** artifact
  loads with `ok=None` "unknown provenance — loudly logged, not blocked." (Not *silent*, as the
  transcript claimed — the log line exists; the acceptance is the residue.)
- **`min_corr` has no hysteresis.** `execution/hedging.py:44,208,294` — open and unwind compare
  against the identical 0.55; the cf454d5e guards added warmup and cooldown but no threshold
  band, so a pair oscillating at 0.55±ε still alternates verdicts on the raw reading.
- **The GBT default `l2=3.0` was hand-tuned against the overfit battery.**
  `ml/models.py:501,508-513` — the comment records that the rev-4 defaults "memorized" per the
  overfit check and the shipped defaults were chosen to pass it: OF-1 is **no longer
  independent evidence** for the GBT family ([[concepts/wrong-null-calibration]] adjacent —
  the judge helped pick the defendant's outfit).

**REFUTED against the current tree (transcript claims gone stale — do not re-file):**
- ~~"model registry has no actual hash chain"~~ — the chain **exists** since `4799bfc7`
  (2026-08-05): `prev` + `seq` + content hash, `verify_chain()` fails the load gate, 9 tests
  (owed 30a, closed; the in-code comment at `ml/registry.py:76-80` dates it).
- ~~"mtf_align daily_candles never passed (SMC MTF is a no-op)"~~ — `daily_candles` **is
  passed** at both `smc.compute` call sites (`main.py:4222, 5338`) and populated at
  `main.py:5885`.
- ~~"profit-pool skim per-leg bleed"~~ — **closed 2026-08-05** as owed 30c (`4799bfc7`,
  6 tests, equity-conservation pins).
- **funnel ML-070 bypass** — real, but **already owed** as item 37(e); not re-registered.

The refutations are themselves the finding: a transcript ledger is a **lead sheet, never a
verdict** ([[concepts/iron-law-of-debugging]]) — three of seven "still-open" flags were already
fixed by commits the transcripts predate.

## 7. First coverage baseline — closes owed 38(c)

Measured from the box's `.coverage` at filing: **TOTAL 17,789 statements, 88%** (fleet: 88.3%).
Least-covered shipped modules ≥50 stmts, verified per-module: `api/grpc_server.py` **26%**,
`data/kraken_feed.py` **49%**, `data/binanceus_feed.py` **59%**, `sentiment/scanner.py` **59%**,
`execution/algos.py` **60%**. The instrumented run's 3 failures were `overfit_check` subprocess
**120s timeouts under ~1.7x coverage overhead** — the same tests are green in today's clean
battery: an overhead artifact, not a regression (compare the load-starved 5s-timeout flake in
[[sources/session-20260807-capacity-sweep]]). Note the coverage map's cold spots include two of
tonight's finding sites (`scanner.py`, `algos.py`).

## 8. The financial-analyst verdict

On its own realized (sim-side) evidence **the strategy is not making money**: every asset
negative expectancy except a 3-trade AVAX blip, fee-dominated per the standing panel identity
(equity −384.67 ≈ fees_total 382.28). Tonight's contribution is ordering: the **fill-sim fix is
the #1 P&L-integrity item** — until the simulator stops gifting fills, no paper number can even
be trusted to be honestly pessimistic — and it **creates a new execution-era boundary when it
lands**, so it should land deliberately, not casually. The **fee constants stay HELD behind the
h432 verdict** per the sequencing rule (owed 37(a)); nothing tonight reopens that.

## Closure addendum (2026-08-07 night, [[sources/session-20260807-closing-batch]])

Filed hours after this page, verified against the box: **§4's docket moved** — latency tier 1
shipped as `915b362f` (42b/42c closed, 42d instrumented via FW-080 detection-only; 42a still
open, and both new instruments proved non-tautological live). **§6's register moved twice** —
owed **43(a) CLOSED**: the CRLF pin exists at `scripts/telemetry_backup.py:246` (`* -text`
written into the bundle worktree per push, since `4a42d2c2`, 2026-07-18 — this page's
registration had looked for a repo-level `.gitattributes` pin: right invariant, wrong layer);
and **July transcript-ledger item 70 RESOLVED** — `ml.adaptive_gbt.enabled: true` ships in
config. Both are the lead-sheet lesson of §6 working as designed: verification, not the
transcript, decides.

## Related
[[synthesis/the-money-path-thesis]] · [[concepts/paper-real-boundary]] ·
[[entities/long-book]] · [[concepts/zero-is-not-a-reading]] ·
[[concepts/tautological-instrument]] · [[synthesis/owed-measurements]] ·
[[synthesis/open-contradictions-register]] · [[sources/session-20260807-institutional-review]] ·
[[sources/session-20260802-digest]] · [[synthesis/risk-posture-doctrine]] ·
[[sources/session-20260807-closing-batch]]
