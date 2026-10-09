---
title: "Evening Session (2026-08-05) — Boards Redesign, Adversarial Round 1 Review, Debug Round 2 (27 findings / 5 HIGH fixed), PAXG and the Tangible-Value Gradient, and the Ten-Item Item-30 Closure"
category: source
summary: "Four battery-green commits to head = remote = 717b2e39: bc198aa5 operator-ordered trading-desk board redesign (audit-chain health finally boarded — closes owed item 26); 46cdc19a three residual edges found by an ADVERSARIAL review of the same day's own fixes (round-1 verdict: all seven HOLD); f3253f0d the five HIGH findings of debug round 2 (27 findings across 5 parallel area agents + an adversarial pass) — acked-but-never-run emergency commands, a documented drain with zero production callers, silent GTC venue orphans (new code OM-090), an in-sample CLI deploy gate, and a deploy-seam race that permanently rejected a good model; 717b2e39 PAXG opened as a tangible investment plus regime/haven.py, the report-only gold > BTC > ETH > alts ladder whose falsifiable vol-ordering prediction was measured and held. Round-2's unfixed medium/low findings filed as owed item 30 with file:line and mechanism — then closed in a fifth commit, 4799bfc7, ALL TEN FIXED with tests written red-first, which also surfaced an eleventh bug (the registry ledger's torn-append fusion, third instance of that class)"
tags: [session, boards, adversarial-review, debugging, defect-docket, haven, paxg, regime, deploy-gate, durability, provenance]
sources: 1
source_path: none — session work product (see Provenance)
source_date: 2026-08
authors: [claude]
ingested: 2026-08-05
updated: 2026-08-05
---

# Evening Session (2026-08-05)

## Provenance

Session work product — no `raw/` snapshot. **Five** commits on the working checkout
`liquiditybot_ab`, **head = remote = `4799bfc7`**. Every commit battery-green in sequence
(**3310/1 → 3312/1 → 3320/1 → 3332/1 → 3376/1**); the closing battery is **pytest 3376 passed /
1 skipped, smoke 219, assurance 49, ruff + compileall clean**.

This session follows and does not supersede the two report-only filings earlier the same day
([[sources/telemetry-stack-audit]], [[sources/session-20260805-debug-sweep]]) — it *discharges*
consequences of both.

---

## 1. `bc198aa5` — the boards redesign (operator-ordered)

Operator directive, verbatim: *"trash the old boards except the Apple glass and neat look… use
professional stock trading exchanges as reference… crypto/stock trading, specifically spot and
margin positions… still see depth of geometry, asset screening, problems/solutions… learning
brain… neat and professional."*

**The authorization matters.** The 2026-08-01 HIG pass had recorded *"Panel removal: not done,
on purpose — needs operator judgement."* That judgement was now given; the removal is authorized,
not improvised.

**What moved, by reading intent:**

| Board | Becomes | Gains | Loses |
|---|---|---|---|
| command | **"trading desk"** — exchange-style daily driver | money / positions & risk / geometry economics | learning brain, trajectory, conviction, context, THALES rows |
| execution | **"models · learning · execution"** | LEARNING BRAIN + LEARNING TRAJECTORY + conviction admission bargauges | the INVENTORY & POSITIONING row (duplicated the desk's positions row panel-for-panel) |
| problem_solution | unchanged name | **AUDIT & TELEMETRY INTEGRITY row** | — |
| screening | **"screening & market"** | CONTEXT (cycle & macro) + THALES rows | — |

The desk answers *"am I making money and what is at risk"*; it does not answer *"is the model
calibrated."* Conviction rows were **relocated, not dropped** — the CV decode contract still holds,
repointed in tests.

**Geometry economics stays on the desk where the money is,** and the payoff-ratio tile now carries
its **own** threshold: green only at **0.75**, the measured break-even at the observed win rate and
fee stack, instead of borrowing the profit-factor scale. The villain number
([[concepts/payoff-asymmetry]]) is now the first thing that colors red.

**The AUDIT & TELEMETRY INTEGRITY row closes owed item 26.** The telemetry audit's dark metrics are
finally rendered: `audit_dropped_writes`, `audit_tail_truncations`, `gauges_dropped_nonfinite` as
PROBLEM tiles, and `gate_divergence` — the `07d38a51` reward-misspecification watch, the
**KNOWN-GAP instrument that had never been displayed** — as a trend panel
([[sources/telemetry-stack-audit]] finding 2).

> **The fixture gap, in reverse.** The synthetic status fixture predated the `gate_divergence`
> instrument, so `test_every_query_hits_an_emitted_metric` read the metric as *never emitted* and
> did not protect it. The fixture now carries a gate-divergence entry. This is the
> **phantom-ghost lesson inverted**: there, a static scan invented metrics that existed; here, a
> stale fixture erased a metric that existed ([[concepts/iron-law-of-debugging]]).

**Preserved deliberately:** the glass skin, Apple palette, HIG post-passes, panel primitives, USD
non-scaling unit, `SPAN_NULLS_MS` honesty, `CODE_LABELS` decoding — and **UIDs unchanged**, so
links, bookmarks and the supervisor auto-import fingerprint contract all survive. Mechanically the
learning-brain mega-function was split at row boundaries
(`_edge_row`/`_context_row`/`_longbook_row`/`_thales_row`/`_risk_row`) and the boards recompose by
call order. 40/40 dashboard tests green. All of it through the **board generator** — the JSON is
generated output, never hand-edited.

---

## 2. `46cdc19a` — three residual edges, found by adversarial review of the same day's own fixes

A second sweep ran an **adversarial pass over `e7ebbf60`, `b409a24b` and `bc198aa5`** — all code
written earlier the same day.

> **Verdict on round 1: all seven fixes HOLD under adversarial review.**
> ([[sources/session-20260805-debug-sweep]] fix disposition.)

It then found three residual edges, **each narrower than the bug it neighbors**:

1. **`fills.csv` could still be born HEADERLESS.** The 29h heal covers a **torn final row**, but
   not the **create-to-first-flush window**: a kill there leaves a 0-byte file; the next append saw
   `path.exists() == True`, skipped the header, and wrote a data row first. `csv.DictReader` then
   silently **adopts that FILL as the header**, and every consumer (`breakeven_test`,
   `cost_attribution`, `calibrate_fills`, `provenance_audit`, `random_entry_control`,
   `geometry_search`) misparses the whole ledger **with no error raised** — the same book of record
   behind the historical **27x** error. Fixed: `new_file` now counts **size 0 as new**
   (`core/fill_ledger.py`).
2. **`gc_log_pusher` saved new-generation offsets under the OLD inode.** `tick()` stat'd the file
   once, then `_drain_rotated` (the 29g fix) spends **seconds of network time** before the main
   file is opened; a rotation inside that window persisted this read's offsets against the
   *previous* inode — so the **next** tick's drain seeked the `.1` file at a **foreign offset and
   skipped its head**. A smaller instance of the very hole 29g closed, and one **invisible to 29g's
   own provenance check**. Fixed: provenance now comes from `os.fstat` on the **opened handle**.
3. **The brand-new `gate_divergence` panel collapsed its per-gate series.** `M()` wraps a bare
   `max()`, while `gc_pusher` emits `liquiditybot_gate_divergence` **per gate with a `{gate}`
   label** — one gate trending to −0.4 while another sits at +0.05 plots the **+0.05 flatline**.
   The panel **hid exactly the sustained trend its own description tells the operator to watch
   for**, one commit after being created. Fixed: `max by (gate)` with a `{{gate}}` legend, pinned by
   a test so a bare `max()` cannot come back.

2 new tests, both red against the code above. Battery **3312 passed / 1 skipped**.

> **The lesson this commit is:** a fix's *neighborhood* is where the next bug lives. Each of these
> three sits one window, one handle, or one aggregation away from a fix that was itself correct —
> and finding them required reviewing **today's own work with hostile eyes**, not tomorrow's.

---

## 3. `f3253f0d` — the five HIGH findings from debug round 2

**Method:** a second read-only sweep — **five parallel area agents** (data · risk · ml ·
runner/deploy · order_manager) **plus A = an adversarial pass** over the session's own commits and
**H = the board restructure** — returning **27 findings total**. These are the five HIGH ones. Each
fix has a test written **red against the unfixed code** first.

### R2-1 · `scripts/remote_control.py` — an acked emergency command that never ran
`_runner_alive` treated a `status.json` younger than 120s as **alive** — but the **clean-shutdown
path writes a FINAL status carrying `runner_state=STOPPED` with a FRESH `written_at`**. So for
**~2 minutes after every deploy bounce** (and after every crash), the bridge forwarded a remote
command into `outputs/control/`, ledgered it **"applied" (at-most-once, never retried)**, and the
next runner's boot purge discarded it as **predating `_PROC_START`**.

A remote `flatten_all`/`stop` issued in a deploy window was **acked and silently dropped** — the
exact **C-F3 class** this gate exists to prevent. The earlier **H6** fix covered commands sent
**DURING a boot**, not commands sent in the **dead gap before one**. **Fixed:** a terminal
`runner_state` means **DOWN regardless of freshness**, so the queue is retained and retried.

### R2-2 · `main.py` — the documented drain that was never wired
`cancel_order`'s last look recovers a fill landed since the previous poll into `order.filled` and
**queues its `FillEvent` for the next poll**. `OrderManager.take_deferred` exists precisely so
`_submit_exit` can observe that fill **before sizing the replacement escape off `pos.size`** — and
its docstring names `main._submit_exit` as that caller. It had **ZERO production callers** (tests
only).

Live: a 100% close after a **fully-filled preempted maker take** sells the position **TWICE —
flips short** — and the deferred fill then drives `pos.size` into the **zero-clamp with the extra
units unaccounted**. **Fixed:** `_submit_exit` drains and applies through the **same `_handle_fill`
path** `poll()` would use (the single-application invariant holds), and **returns early if the
recovered fill already flattened the position**.

### R2-3 · `execution/order_manager.py` + `core/codes.py` — silent GTC orphans at the venue
Kraken orders carry **no `expiretm`**, and `feed._private_post` **never raises**: on a rate limit, a
5xx, or an error payload it returns **`None`**. **Both cancel paths discarded that result** and
forced local state terminal — so the order **left `open_orders()` and was never queried again while
the real order kept resting at the venue**. And because the bot is otherwise healthy it keeps
**re-arming `CancelAllOrdersAfter` every ~30s — so the deadman meant to back this up never fires.**
The healthy bot defeats its own venue backstop.

A later venue fill is invisible: an orphaned **ENTRY** is untracked inventory with no stop; an
orphaned **EXIT** means the venue is flat while the book says open, and the ladder's next rung
**double-sells**.

**Fixed:** the terminal transition **still happens** (a blocked escape is the worse failure —
[[comparisons/stated-invariants-vs-audited-reality]]), but the residue is now **AUDIBLE**: new
registered code **OM-090**, a **`cancel_unconfirmed` counter** in the status readout, and a
**hash-chained audit record** naming txid, path, symbol and remaining. **Dry-run posts nothing, so
it never flags.**

### R2-4 · `scripts/train_meta.py` — the CLI deploy gate was biased toward deploying
It fit the isotonic calibrator on the **very OOF vector it then scored** (in-sample), while the
champion is rescored **strictly out-of-sample** by `rescore_frozen`. `main.py`'s auto lane fixed
exactly this in **H13** — **measured optimism +0.0032..+0.0066, i.e. 25–150% of the 0.005 deploy
margin, always pro-challenger, never averaging out** — and **this lane never got it**. A manual
retrain could therefore deploy a **strictly worse model** *and* stamp the optimistic number into the
artifact as the **next champion's badge**. **Fixed:** the CLI now scores through the same
`cross_fitted_calibrated_oof` helper — **one gate, one standard**. The shipped artifact keeps its
full-pool calibrator, unchanged.

### R2-5 · `ml/meta_model.py` — a good model rejected as tampered, permanently
`save_model` publishes the artifact atomically and appends its `"registered"` ledger row **a beat
later**. A reload landing in that gap hashes **NEW bytes** against the **PREVIOUS champion's row**,
fails verification, logs **ML-011**, and **drops to the cold-start prior** — and **never retries**,
because `_loaded_mtime` is stamped **before** the verify (deliberately, so rejects don't re-trigger
every cycle). A millisecond race became a **persistent model outage** until the next deploy or a
restart. **Fixed:** rejection **un-stamps the mtime** — the next cycle re-verifies, so a deploy-seam
race **self-heals** while a genuine tamper **re-rejects, once per cycle, loudly**.

Battery **3320 passed / 1 skipped**.

### Clean areas (good news for the corpus)
`ml/labeling.py` and `ml/walkforward.py` came back **CLEAN — no reportable bugs**; so did
`data/_http.py` and `data/recording.py`.

### Near-misses — investigated, verified OK
Walkforward boundary purge · labeling edge cases · `rescore_frozen` watermark · `_close_periods` vs
fills snapshot · exit-price fallback vs firewall · the 29h heal's `\r\n` vs strict readers ·
`SingleInstanceLock` livelock bound · Kraken forming-bar cut · OKX pagination cursor · torn bundle
materialization · status/equity atomicity.

### Not fixed here, deliberately
Round 2's medium/low findings were **filed as owed items rather than batched into a fix commit that
would stop being reviewable** — [[synthesis/owed-measurements]] **item 30**, each with file:line and
named mechanism. **They were then closed as their own commit later the same session — see §5.** The
filing was not a deferral; it was a boundary between two reviewable diffs.

---

## 4. `717b2e39` — PAXG and the tangible-value gradient

Operator directive: *"open the bot up to paxg and treat gold as a tangible investment. make it
understand the psycological aspects between the value of gold > bitcoin > Eth > alt coins."*

New module **`regime/haven.py`** encodes the ladder. Full doctrine on
[[synthesis/tangible-value-doctrine]]; the session-level facts:

- **The ladder:** PAXG (a bar in a vault, value independent of adoption) > BTC (digital gold: fixed
  supply + deepest security budget, but a claim on a **NETWORK** — the tangible anchor **OF** crypto,
  a risk asset **TO** everything else) > ETH (productive infrastructure, contingent on usage) > ALTS
  (venture bets).
- **Mechanism, not mood:** fear travels **DOWN** the ladder and greed **UP** it, in order, because
  under stress the question stops being *"what could this become"* and becomes *"what is this,
  actually."* Therefore **adjacent-rung spreads** read regime better than any single asset's return.
- **The falsifiable prediction, measured at commit time on live Kraken bars — and it held.** Realized
  5m volatility ranks **exactly down the ladder**: **PAXG 0.075% < BTC 0.093% < ETH 0.120% ~ SUI
  0.116% < ARB 0.160%.** The tangibility ordering **IS** the volatility ordering.
- **The first live gradient read:** `flight_to_quality` **+2.00** (PAXG **+4.7%** / BTC **+0.8%** /
  ETH **+2.1%** / ALT **−1.3%** over 24h) — **but `BTC-ETH` came out NEGATIVE in the same reading.**
  The ladder is a **tendency, not a law**, which is why the instrument reports **per-rung detail
  instead of a verdict**.
- **Report-only by construction:** no imports of `execution`/`risk`/`main`, **pinned by a parsed-AST
  test, not a prose scan** — a text search would match the docstring promising the very restraint it
  checks.
- **Wiring:** `status.json` gains a guarded `haven` block (a failure there must never cost a status
  write); `gc_pusher` exports gradient, `rungs_seen`, per-rung returns and the state label; the
  screening board gains a **TANGIBLE-VALUE LADDER** row whose trend panel answers *"is fear
  travelling down the ladder?"* rather than printing a number. The **synthetic status fixture carries
  the block too** — the same fixture gap that had hidden `gate_divergence`, closed at birth this
  time.

### Two real consequences the battery caught

**(a) Gold costs one DISCRETIONARY skimmer slot.** [[entities/config-guard]] **FATALs at 13 pairs**:
with the WS feed down, the REST book poll at **3 req/s** sustains a **12-pair envelope**, and
base(7) + extra(6) = 13 would starve it. So `skimmer.max_extra` **6 → 5** — a permanent tangible-value
anchor in place of a rotating candidate, which is the trade the operator asked for. **Raising it again
requires raising the envelope first.** The REST-fallback envelope is a **real capacity limit, not a
preference**.

**(b) PAXG needed AssetPairs-verified fallback meta.** `data/kraken_feed.py`:
`PAXGUSD {price_decimals: 2, lot_decimals: 8, ordermin: 0.001}` with `costmin 0.50`. **ordermin
0.001 oz ≈ $4.25 at a $4,250 spot — the smallest ticket in the universe by dollar value**, so gold is
**genuinely reachable by the sizer at this account size**, not a listing it can never fill. Kraken
quotes PAXG/USD at a **2.86bps spread with 20 levels a side**.

### Deliberate non-goals
- **No feature-vector change.** The model schema is **frozen mid-migration** (the 432-bar cohort);
  widening it for a signal with **zero track record** would invalidate the in-flight experiment
  ([[comparisons/horizon-96-vs-24-bars]]).
- **No gold-specific bracket geometry.** PAXG's low vol flows through the **same vol-scaled
  brackets, sizer and labeler** as everything else — sigma-scaled geometry tightens on its own,
  which is the entire point of scaling by sigma rather than by hardcoded percentages.
- **Spot only, everywhere.** The bot holds **no margin on any venue** — and **no margin panel or
  metric was invented to imply otherwise**, despite the operator's brief naming "spot and margin
  positions." A board that showed margin would be a board that lied.

Battery **3332 passed / 1 skipped**.

---

## 5. `4799bfc7` — owed item 30 closed, all ten, each with a red-first test

The findings §3 deliberately did **not** batch were closed as their own commit — the same
reviewability discipline applied in the other direction. Battery **3376 passed / 1 skipped**, smoke
219, assurance 49, ruff + compileall clean. **Every one of the ten carries a test written red
against the unfixed code first.** Per-sub-item detail lives on
[[synthesis/owed-measurements]] item 30; the four that change something the wiki already believed:

### MONEY — the profit-pool skim (30c), flagged to the operator as the most important
`risk/capital_manager.py` + `main.py`. The skim ran **once per exit LEG** on `net` — and `net` is
**gross minus that leg's exit fee, NOT minus the slice's pro-rata entry fees**. Two defects fused:
it skimmed an **overstated base**, *and* it fired on **winning legs of trades that ended up
losing**. A **+$16 tier take on a trade netting −$80 still moved ~$4.80 into locked
savings/reserve — and savings is never clawed back.** With **tiered exits the normal trade shape**,
trading cash **bled monotonically into locked pools as a function of gross winning legs**: the pools
filled *from losing trades*.

**Fix — separate the fused concerns.** Cash still settles **per LEG** via
`record_realized_profit(net, state, skim=False)`, which is correct because **entry fees already left
cash at fill time** through `record_entry_fee`. The **three-way split now runs ONCE per closed
trade** on the fully-net `total_net`, through new **`CapitalManager.skim_trade()`**, called in
`_finalize_position` and **guarded like every other close-path step**.
`tests/test_pool_skim_per_trade.py` (**6 tests**) including **equity-conservation** and
**no-double-booking** pins.

> This is the second independent bleed on the same account that
> [[concepts/payoff-asymmetry]] describes. The payoff ratio says the average loser is ~1.8x the
> average winner; this said the winners' *legs* were also being taken out of the sizer's reach on
> the way down. Fixing it does not move the payoff ratio — it stops the book from **paying twice**
> for the same shape.

### EVIDENCE — `ml/monitor.py::_judge` (30b), two defects, one of them a retraction
1. **The Wilson credibility guard was ALGEBRAICALLY DEAD.** `lcb ≤ observed` always, so
   `promised − lcb > allow` is **implied** by the raw-gap clause — it could **never veto**, and it
   grew **MORE permissive as n fell**, inverting its own purpose. Fixed with a new **`wilson_ucb()`**:
   the promise must clear **even the most optimistic reading of outcomes** — which implies the
   raw-gap condition and is correctly **HARDER at small n**.
2. **`baseline_brier` was an in-window oracle** — a constant equal to the window's **own** realized
   mean. An **all-loss 15-close window handed the baseline a clairvoyant 0.05** and convicted an
   honestly-calibrated model on its **first** evaluation. Fixed with new **`_prior_base_rate()`**,
   using only rows **PREDATING** the window, neutral **0.5** at cold start — a **weaker** baseline,
   therefore **slower to convict**, the right direction when the false positive is killing a working
   model. `tests/test_monitor_credibility.py` (**9 tests**).

> ⚠️ **Correction worth filing: the first test premise was WRONG.** It asserted that 15 straight
> losses against a **promised 0.30** should not convict — but that is `0.70^15 ≈ **0.5%**` under the
> model's **own** claim, so **convicting is correct**. The test was rewritten to pin the actual
> mechanism: an honest **~0.18** promise **survives** an unlucky streak, and the same shortfall is
> **harder to indict at small n**. Also: `tests/test_monitor_deescalate_deadband.py` needed a new
> `_seeded()` helper, because **its fixture had been depending on the old oracle baseline** — a
> green test standing on the defect.

### PROVENANCE — `ml/registry.py` (30a), and an ELEVENTH bug nobody was looking for
The registry is now **genuinely hash-chained** — `prev` + `seq` + content hash, **matching
`core/audit.py`'s construction** — `verify_chain()` walks the links, and **a broken chain now FAILS
the load gate instead of authorizing it**. `tests/test_registry_chain.py` (**9 tests**): edited row ·
deleted row · reordered rows · **a rewritten row minting provenance for a swapped artifact**. This
**closes the citation hazard** the last filing caught
([[comparisons/stated-invariants-vs-audited-reality]],
[[synthesis/open-contradictions-register]]) — *hash-chained* is now true of both files.

> **The eleventh bug.** Writing the **torn-row** test surfaced a defect **no one was hunting**: the
> registry ledger had the **SAME torn-row fusion defect as the fills ledger** — a crash mid-append
> leaves a fragment, the next write **welds onto it**, taking a good record down with the bad one.
> Same heal applied. This is the **THIRD instance** of the torn-append class (`fills.csv` 29h ·
> the fills create-window in `46cdc19a` · the registry here), and it is now its own page:
> **[[concepts/torn-append-fusion]]**. Two lessons filed there: append-only JSONL/CSV writers in
> this repo need the **terminate-torn-tail + fsync** pattern as a **standing rule**, and **the way
> it was found — a test for a DIFFERENT property — is itself the lesson.** Five parallel area
> agents read `ml/` in round 2 and did not see it; constructing the state as test *input* did.

### FEEDS, DEPLOY/RESTART, CORPUS/CONTROL — the remaining seven
- **`data/okx_feed.py` (30d)** — deep history was silently truncated to **2000 bars** by
  `clean_candles`' **live-fetch cap**: `train_meta`'s bootstrap **asked ~10 days of 5m bars and got
  ~7, with no log line**. Fixed with `max_n=len(raw)` for **deliberate paginated** requests.
  `tests/test_deep_history_not_truncated.py` (3 tests).
- **`data/ws_feed.py` (30e)** — the Kraken book was published to the live cache **BEFORE checksum
  verification**, so during the **post-mismatch resubscribe backoff** every update frame rebuilt
  from empty and republished, serving a **phantom 1-5-level book stamped fresh** to stop and
  imbalance logic **on every frame**. `_verify_checksum` now returns **bool** and the caller
  publishes **only on True**; unverifiable frames (no checksum, or depth < 10) publish as before.
  `tests/test_ws_verify_before_publish.py` (6 tests).
- **`scripts/auto_update.py` (30f)** — force-kill grace **45s → 150s**. `runner.py` documents
  **MEASURED** stalls of **88.1s / 55.5s / 50.2s** — **every one exceeded the grace**, so deploys
  `taskkill`ed **HEALTHY** runners mid-cycle. **The likely origin of the `audit_tail_truncations`
  counter** boarded three commits earlier ([[entities/observability-sidecars]],
  [[entities/auto-update]]).
- **`core/skimmer.py` (30g)** — replace-hysteresis was **void after every restart**: scores were
  **persisted but never read back**, so **every incumbent compared as 0.0** and a **0.55 candidate
  evicted a 0.90 incumbent, every 15-minute deploy**.
  `tests/test_skimmer_hysteresis_restart.py` (6 tests).
- **`runner.py` (30j)** — a boot hang **held the lock forever** (the heartbeat refreshed
  unconditionally while `_last_progress_ts is None`). Now a **bounded boot grace measured from
  process start**, config key **`lock_boot_max_stall_sec`** defaulting to **2x the running stall
  bound**.
- **`scripts/session_import.py` (30h)** — within-bundle duplicates merged **twice**: the seen-set was
  **never updated with accepted keys**, the corpus is **append-only so nothing heals it**, and
  `corpus_sync --apply` runs **hourly, unattended**. `tests/test_session_import_dedupe.py` (4 tests).
- **`scripts/remote_control.py` (30i)** — a transient `git show` failure **permanently REJECTED a
  valid command** through the exactly-once ledger. Read failures are now **left unledgered and
  retried**, bounded by the command's **own 30-minute expiry**. New test in `test_remote_control.py`.

> **The shape of this commit:** three of the ten (30f, 30g, 30j) are **restart-fragile invariants**
> failing continuously because the deploy chain bounces the runner every ~15 minutes. Two (30a, 30c)
> are **fused concerns** — one function doing two jobs on one number. And the eleventh bug says the
> **torn-append class is a repo-wide writer rule**, not a per-file fix.

## What this session changes elsewhere in the wiki

- **Owed item 26 CLOSED** — dark metrics boarded, including the `07d38a51` KNOWN-GAP instrument
  ([[sources/telemetry-stack-audit]], [[entities/observability-sidecars]]).
- **Owed item 29's residual mediums CLOSED** — `core/fill_ledger` create-window and
  `gc_log_pusher` inode capture, both fixed in `46cdc19a`.
- **Owed item 30 OPENED AND CLOSED, same session** — round 2's unfixed findings were filed with
  file:line and mechanism, then **all ten fixed** in `4799bfc7`, each with a red-first test.
- **New concept page** — [[concepts/torn-append-fusion]], the third instance of the class plus the
  found-by-accident lesson.
- **The `registry.jsonl` citation hazard is RESOLVED** — struck in both
  [[comparisons/stated-invariants-vs-audited-reality]] and
  [[synthesis/open-contradictions-register]]; the general form survives the fix (*a shared adjective
  is not a shared property*).
- **A new citation hazard opened and immediately answered** — the "15-loss streak" example filed
  with item 30b was **retracted**; cite the mechanism, never the worked example.
- **New registered code OM-090** ([[entities/reason-code-registry]]) — 182 → 183 codes.
- **New doctrine page** — [[synthesis/tangible-value-doctrine]], ground truth for the ladder.
- [[comparisons/stated-invariants-vs-audited-reality]] gains R2-1 and R2-3.
- [[concepts/default-path-fallback-writes]] gains the headerless-ledger edge — **same book of
  record, a different way to lose it**.
- [[concepts/iron-law-of-debugging]] gains the adversarial-on-own-work pass and the
  fixture-gap inversion.

## Related
[[sources/session-20260805-debug-sweep]] · [[sources/telemetry-stack-audit]] ·
[[synthesis/tangible-value-doctrine]] · [[synthesis/owed-measurements]] ·
[[entities/liquiditybot]] · [[entities/observability-sidecars]] ·
[[entities/reason-code-registry]] · [[entities/config-guard]] · [[entities/kraken]] ·
[[concepts/payoff-asymmetry]] · [[comparisons/horizon-96-vs-24-bars]] ·
[[concepts/torn-append-fusion]] · [[entities/ml-governor]] · [[entities/auto-update]] ·
[[comparisons/stated-invariants-vs-audited-reality]] ·
[[synthesis/open-contradictions-register]] · [[concepts/wrong-null-calibration]] ·
[[concepts/default-path-fallback-writes]]
