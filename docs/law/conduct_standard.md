# Conduct standard: how this bot behaves on its venue, and how it keeps the venue honest

Written 2026-09-26. Replaces the CME-benchmarked market-conduct document
(deleted the same day; it is in git history, parent of this commit). That document borrowed CME Rules 575/534 as its
frame. This one starts from what the bot actually does. It has three layers:

1. **FLOOR.** A short list of things the bot never does. These are not
   negotiable, and a change that breaks one is refused.
2. **OPERATOR DECIDES.** Every rule stricter than the floor. The current
   value is the default. The operator keeps, loosens or drops each one.
   An agent does not decide these.
3. **VENUE INTEGRITY.** How we check that Kraken cannot overcharge us, pick
   us off, mislead us or hold us hostage. Existing mechanisms are listed,
   and each gap is a proposed follow-up with its era-9 class.

Citations are `file:line` at HEAD `7e9eb972` on branch
`claude/remote-control-enabled-noiwyj`. Line numbers drift, so re-derive a
citation before relying on it. Fill and audit numbers come from telemetry snapshot
`origin/paper-telemetry` @ `eb42ba93` (committed 2026-09-26T17:21:29-05:00):
`sessions/pc-live/fills.csv` has 1,444 rows and `sessions/pc-live/audit.jsonl`
has 91,353 records, spanning 2026-07-13T10:49:24Z to 2026-09-26T22:08:03Z.
Provenance tags: [K] means measured this session, [I] means inferred, and
[UNKNOWN] means not established.

## What the bot is (the focus this standard is built around)

- **Venue.** Kraken spot/margin is the only execution venue (CLAUDE.md
  invariant 3). The enforcement is the deny-list at `main.py:871-887`, which
  raises `VN-020` when the execution feed is a read-only venue class. OKX,
  Binance.US, ccxt, moomoo, web and dark-pool feeds are data only. Trading
  pairs are PAXG/USD, ETH/USD, BTC/USD and LINK/USD (`config.json`
  `exchanges.kraken.trading_pairs`), and the skimmer can widen the universe.
  `leverage.use_margin` is `true`, so the bot can hold margin shorts.
- **Posture.** `system.dry_run: true`. In dry-run, `OrderManager.submit`
  returns at `execution/order_manager.py:1158` before any `AddOrder` is built.
  Nothing reaches Kraken's order book. [K] The audit snapshot contains 490
  session-start `CG-000` records and all 490 have `dry_run: true`. The road
  to live has four steps (CLAUDE.md invariant 1): delete
  `outputs/force_dry.on`, set config `dry_run:false`, restart, then type
  `ARM LIVE`. While live but not armed, `main.py:7071-7081` blocks entries and
  hedges and still lets exits through.
- **Order style.** Entries are limit orders (`OM-011`, enforced at
  `execution/order_manager.py:1032-1038`), and a market order is allowed only
  as the last rung of the exit ladder. Entries are maker-first: they are
  `post_only` by default, and `oflags=post` is set on the wire at
  `execution/order_manager.py:1183-1184`. A marketable-limit ("taker") entry
  is allowed when urgency reaches `execution_tactics.taker_at_urgency` (0.88)
  and `allow_taker` is true. Thin books are forced to maker-only
  (`thin_book_maker_only: true`). [K] In era 9 (fills since 2026-09-08), 85 of
  100 entry fills were `post_only=1` and 15 were marketable limits. In this
  environment every one of these fills is simulated.
- **Signals.** Liquidity and flow features (book imbalance, spoof and
  manipulation labels, informed-flow and dark-pool context) choose *whether*
  and *where* to rest a limit order. The bot detects other traders'
  manipulation and reacts to it. It never uses those tactics itself (THALES
  boundary, `docs/THALES_FRAMEWORKS.md`). A `spoofy` liquidity label blocks
  new risk (`regime/liquidity_regime.py:10`).
- **Books.** The 5m book's orders live about 25s (`order_manager.
  order_timeout_sec`) and then expire. The long-horizon accumulation book
  (`risk/long_book.py`) rests one bid per asset for up to
  `long_book.order_ttl_hours` (6h). The grid ladder
  (`execution/grid_ladder.py`, `grid_ladder.enabled: true`, 3 rungs) can
  split one approved entry across several resting maker rungs.
- **Era 9.** Accrual runs under `docs/law/era9_moratorium.md`. Any change to
  entry decisioning, sizing, exit geometry, the fill sim, fee booking or the
  order lifecycle is COHORT-RESETTING. **Loosening or dropping almost every
  OPERATOR DECIDES row below is a COHORT-RESETTING change** and needs
  adjudication and a mint. Only the rows marked SAFE are free.

---

## 1. FLOOR: the minimal legal line (blocking)

The floor is these six items and nothing else. Each one-line definition is
the plain meaning, not a CME text.

| # | The bot never... | Enforcing mechanism | Pin |
|---|---|---|---|
| F1 | **Spoofs.** It never enters an order it intends to cancel instead of fill. | Every order has a fill purpose. Entries pass the sizer, the pretrade EV gate (`execution/pretrade.py`) and the risk firewall (`execution/order_manager.py:1052`) before submission. No code path submits an order in order to cancel it. Cancels only come from a timeout (`execution/order_manager.py:1266-1289` (live), `:1491` (dry)), a stale long-book reprice (`main.py:5511-5525`, `LB-021`), a self-cross clear (`LB-022`) or a risk-off preemption (`main.py:2539`). Every cancel carries an audited reason. Long-book cadence floors (`core/config_guard.py:348-379`, FATAL) stop config alone from turning the patient book into a flicker quoter. | Code cannot pin the absence of a spoof path. The flicker floors are pinned by `tests/test_config_guard_long_book.py`: [K] ttl-floor and band-floor mutations were each killed (1 red). |
| F2 | **Layers.** It never stacks orders at several prices to fake depth on one side while trading the other. | The only multi-order structure is the grid ladder. Its rung sizes sum exactly to the one sizer-approved entry (`execution/grid_ladder.py:128-135`). All rungs sit on the side the bot actually wants to trade. The ladder retracts on a `spoofy` book or a manipulation veto (`execution/grid_ladder.py:96-99`). A taker-urgent entry never ladders (`main.py:6002`). Only one 5m entry per asset may be open (`main.py:4690`). | `tests/test_grid_ladder.py` (`test_sizes_sum_exactly_to_the_approved_total` and others). [K] A mutation dropping the `/ wsum` normalisation was killed. |
| F3 | **Wash-trades or self-trades.** It never trades with itself to fake volume or dodge risk. | One account, one venue. Before any marketable (non-`post_only`) sell, `main._clear_long_book_bid_before_sell` (`main.py:2712-2757`, `LB-022`) cancels the bot's own resting long-book bid on that pair. It is wired at four sites: `main.py:1541` (algo child), `:2675` (exit ladder), `:3189` (hedge open) and `:5177` (taker entry). Exits only reduce held positions. **Residual:** see VG-8 and OD-9. | `tests/test_long_book_integration.py:1957-2033`. [K] A mutation that no-ops the guard was killed. |
| F4 | **Quote-stuffs.** It never floods the venue with messages. | Every REST call to Kraken goes through one global throttle: `rate_limit_per_sec: 3`, applied at `data/kraken_feed.py:171` and held under a lock at `data/_http.py:111-124`. The firewall budget is 30 accepted entries/hedges per 60s (`execution/risk_firewall.py:198-221`, `FW-020`), and identical entries inside 3s are rejected (`:238-259`, `FW-030`). No burst or batch-submit path exists. | `FW-030` is pinned by `tests/test_exit_safety_batch.py` [K, mutation killed]. The throttle and the `FW-020` budget: **pin not established this session.** |
| F5 | **Attempts momentum ignition.** It never fires aggressive orders to start a move and then trade into it. | Market orders are refused outside the last exit rung (`execution/order_manager.py:1032-1038`, `OM-011`). Taker entries are limit orders bounded by the 100bps entry collar (`execution/risk_firewall.py:266`, `FW-050`) and by the notional caps (`:290-305`). No path pairs an aggressive order with an opposing order meant to profit from the move it causes. | `tests/test_order_manager_lifecycle.py::test_om011_market_entry_refused_market_exit_accepted`. [K] Mutation killed. "No pairing path" is an absence claim and cannot be pinned. |
| F6 | **Fakes volume or activity.** It never places orders, fills or reports that misstate real interest. | Order size is the sizer's real approval, floored to venue precision (`execution/order_manager.py:1133`). Below-minimum and zero-after-format orders are refused rather than sent (`:1064-1116`, `OM-013`). In dry-run nothing is sent at all (`:1158`). The hash-chained audit (invariant 6) records why every order was placed and why it was removed. | Dry-run short-circuit: [K] a mutation disabling it was killed by `tests/test_order_manager_lifecycle.py` + `tests/test_hard_invariants.py`. |

**Why the audit trail is part of the floor.** Market-abuse standards read
intent from conduct. The hash-chained JSONL audit with a registered reason
code on every disposition (CLAUDE.md invariant 6) is the bot's intent record.
It lets us answer "why did the bot do X at time T" from a file.

---

## 2. OPERATOR DECIDES: rules stricter than the floor

Each row gives the current state, which is also the default. Options are
**keep / loosen / drop**. "Class" is the era-9 class of *changing* the rule.
Keeping a rule is always free.

| # | Rule | Current value / mechanism | What it protects | Class of a change |
|---|---|---|---|---|
| OD-1 | Long-book cadence floors | FATAL when `order_ttl_hours < 1.0`, `add_min_spacing_hours < 1.0`, `retry_backoff_minutes < 5.0`, or when `add_offset_pct+zone_tol_pct+zone_buffer_pct < 0.3%` (`core/config_guard.py:348-379`). Shipped values: 6h / 24h / 30min / 0.85%. | Keeps an hours-resting bid from becoming a flicker quoter through config alone. | Changing only the floor is SAFE. Changing the shipped values is COHORT-RESETTING. |
| OD-2 | 5m reprice cap | `order_manager.max_reprices: 1` and `reprice_max_slip_bps: 8`. **Both are dead knobs.** They are read at `execution/order_manager.py:188-189` and nothing consumes them. `ManagedOrder.reprices` is never incremented, and the 5m book has no reprice path at all: orders expire and a fresh decision follows. The deleted document cited this knob as the reprice bound, and that claim was false. | Nothing today. | Delete the keys or leave them inert: SAFE, provided behavior stays byte-identical. The guard at `core/config_guard.py:2429` reads the key. Wiring a real cap is COHORT-RESETTING. |
| OD-3 | 5m order lifetime and cancel footprint | `order_timeout_sec: 25` (`execution/order_manager.py:187`, terminator at `:1266`). [K] Era-9 terminals (≥2026-09-08T00:00Z; the exact cut-#12 instant was not derived): of 561 entry orders, 109 filled, 411 expired unfilled and 41 were cancelled unfilled. That is roughly 5.1 orders per filled entry. Of 90 exits, 88 filled. All of these are simulator outcomes. | A high order-to-fill ratio is not spoofing when every order is meant to fill. It is still the footprint a venue surveillance desk looks at first. | An order-to-fill monitor is SAFE. A cap is COHORT-RESETTING. |
| OD-4 | Grid ladder | `enabled: true`, `rungs: 3`, `min_spacing_bps: 8`, `size_decay: 0.7`, arm/disarm at p(win) 0.60/0.55 (`execution/grid_ladder.py`). Rungs are `post_only` and die on the roughly 25s timeout. | It sits next to layering, and it is bona fide only because of the sum-to-approved invariant and same-side placement (F2). | COHORT-RESETTING |
| OD-5 | Kraken REST throttle | 3 req/s (`data/kraken_feed.py:171`, `data/_http.py:111`). `candle_refresh_sec: 150`. | Message rate, and the risk of a venue rate-limit ban. | COHORT-RESETTING [I]. Throttle timing feeds order timing. |
| OD-6 | Firewall rate and dupe budget | 30 entries/min. Exits get 2x and override the budget (`FW-021`, invariant 5). Dupe window 3s (`execution/risk_firewall.py:198-259`). | Message rate and double-submits. | COHORT-RESETTING |
| OD-7 | Price collars | Entry 100bps, exit 500bps (`execution/risk_firewall.py:266`). A breach rejects entries and clamps exits. [K] In era 9 there were 222 `FW-050` entry rejects. | Stops fat-finger and stale-reference orders. | COHORT-RESETTING |
| OD-8 | Self-imposed position limits | `max_order_usd: 4000` and `max_order_pct_equity: 30` (`execution/risk_firewall.py:290-305`). Inventory soft/hard caps 15%/25% and 2 same-side positions per asset (`execution/inventory.py:59-63`). `capital_management.max_concurrent_positions: 5`. Heat cap and the CVaR/gap/budget stack. | Stands in for exchange position limits, which spot crypto does not have. | COHORT-RESETTING (sizing) |
| OD-9 | Self-cross guard scope, and the pre-live wiring item | `LB-022` covers **long-book bids only**. The deleted document required that "any future book that rests entries for hours must be wired into the same guard before ARM LIVE". [I] One path is not established: a resting 5m entry buy alongside a marketable 5m exit sell on the same pair, which `max_same_side_positions_per_asset: 2` allows. The deleted document said these "do not coexist on this timescale" and gave no measurement. No `stptype` is sent (`execution/order_manager.py:1167-1186`). | Keeps us out of self-trades (F3). | Extending the guard or sending `stptype` is COHORT-RESETTING (order lifecycle). Measuring it is SAFE (VG-8). |
| OD-10 | Dead-man switch | `deadman_timeout_sec: 60`, refreshed at half-interval (`execution/order_manager.py:447-470`, `data/kraken_feed.py:551`). `CancelAll` on clean shutdown (`runner.py:1813-1821`). Live only. | Nothing rests unmanaged if the bot dies. | COHORT-RESETTING (lifecycle) |
| OD-11 | Maker-first and taker allowance | `allow_taker: true`, `taker_at_urgency: 0.88`, `thin_book_maker_only: true` (`execution/tactics.py:55-71`). | Fewer aggressive orders means less ignition-shaped footprint and lower fees. | COHORT-RESETTING |
| OD-12 | Trading against predictable naive flow | Today the bot only detects it and reacts (THALES boundary). The floor does not forbid it. Raised as a governance question in `docs/thales/README.md` item 7. | A policy choice, not a legal floor. | Operator ruling. Any implementation would be COHORT-RESETTING. |

Not operator-discretionary: CLAUDE.md hard invariants 1-7 (dry-run default,
one-way `force_dry`, Kraken-only execution, no withdrawals, limit-only
entries with exits always allowed, the audit trail, stable interfaces). They
sit above this table.

---

## 3. VENUE INTEGRITY: Kraken can't exploit us

**Relationship with the venue.** Kraken is the sole execution venue
(invariant 3), and we deal with it at arm's length. We follow its terms and
the law. We verify everything it reports. We trust no venue number until our
own reconciliation has checked it. That runs both ways: `_check_equity_truth`
treats the venue's TradeBalance as the check on *our* ledger
(`main.py:6590-6618`), and the fee tooling treats the published schedule as
the check on the venue's charged fee.

| Vector | Existing mechanisms (file:line) | Gaps: proposed follow-ups (class) |
|---|---|---|
| **Fee schedule / tier drift vs booked fees** | Booked 15/30 bps = Tier 5 (the operator's app reading at cut #12, `config.json` `pretrade._fee_reading_doc`). Live fills book the venue's own `fee` field, and only fall back to the config bps when it is absent (`execution/order_manager.py:543-549`). A daily `TradeVolume` tier check emits `OM-080` on mismatch (`execution/order_manager.py:788`, `order_manager.fee_recon`, 1bps tolerance). Published-schedule tooling: `core/venue_fees.py` (`binding_row`, `fetch_page_schedule:239`), `scripts/fee_drift_report.py`, `scripts/cost_truth_report.py`. **Moratorium exemption:** a WRONG VENUE CONSTANT that makes the bot trade on a false cost may break the 14-day minimum (`docs/law/era9_moratorium.md:95-98`). Re-booking is still a mint and needs adjudication. | **VG-1 (SAFE).** Add a per-fill audit that checks the fee Kraken charged (`fees_delta_usd / notional`) against `venue_fees.binding_row` for that fill's maker/taker class. Today both live checks trust venue-reported numbers: the fill `fee` and `TradeVolume`. **Shipped 2026-09-27:** `scripts/venue_integrity_report.py` `fees` (`core/venue_integrity.py` `fee_check`, `trades_fee_check` on a TradesHistory export using the venue's own `maker` flag). Unknown volume gives VI-011 and never falls back to a default row. Codes VI-010/VI-011. |
| **Fill quality / adverse selection / slippage vs arrival** | `fills.csv` `slip_bps`: side-normalised with positive meaning adverse, measured against `arrival_ref` at submit (`core/fill_ledger.py:216-222`). Mark-outs at 5/30/60s (`execution/markout.py`, `config.json` `markout`). Report tools: `scripts/adverse_selection.py` (alpha vs spread-capture decomposition), `scripts/markout_report.py`, `scripts/kyle_lambda.py`. [K] Era-9 fills: 100 entries with slip_bps median −0.51, p90 2.24, max 6.42; 88 exits with median 0.46, p90 8.17, max 20.26. | **VG-2 (SAFE).** Every one of these fills is simulator output (dry-run), so no Kraken fill has been graded. Register live acceptance thresholds before arming: slip p90, 30s alpha mark-out and post-only fill share, each with an n-floor. Report-only. Acting on them would be COHORT-RESETTING. **Shipped 2026-09-27:** the registration `LIVE_FILL_ACCEPTANCE` (`core/venue_integrity.py`), mirrored and awaiting operator ratification in `docs/law/pre_live_checklist.md`. Bounds: slip p90 ≤ taker−maker bps, 30s alpha mark-out ≥ −maker bps, post-only share ≥ 0.5, with n=50 as the lean and n=100 as the verdict. Graded by `scripts/venue_integrity_report.py` `fill-accept` over live-posture fills only. Codes VI-020/VI-021. |
| **Stale / phantom book data, feed trust** | CRC32 checksum verification on the Kraken v2 WS book, with resubscribe backoff (`data/ws_feed.py:625`). `kraken_max_book_age_sec: 3.5`. Pretrade `PT-020` stale veto at 4000ms (`execution/pretrade.py:279`). Watchdog: stale-critical at 120s (`core/watchdog.py:152`), and cross-venue divergence of 150bps or more blocks entries, using the read-only venues as a check on Kraken (`core/watchdog.py:170`). `FW-080` stale bars. `spoofy` label (`regime/liquidity_regime.py`). | **VG-3 (SAFE).** The dry-run fill sim fills against Kraken's *displayed* depth, so phantom or flickering liquidity looks fillable. At the first live fills, measure the sim-vs-live fill-rate gap per liquidity label. **Shipped 2026-09-27:** `scripts/venue_integrity_report.py` `fill-gap` gives the per-pair fill rate split by session posture, taken from the `CG-000` `dry_run` of the governing session. Today it returns VI-001 (no live terminals). The per-label split is [UNKNOWN] from this corpus, because terminal records carry no liquidity label and unfilled orders have no position to join through. That is a registered follow-up. Code VI-030. |
| **Rate limits, rejections, post-only rejects** | Global throttle (F4). The `OM-021` venue-reject counter (`execution/order_manager.py:1189`). Exits keep the firewall rate override. | **VG-4 (SAFE).** `_private_post` collapses every Kraken error string to `None` plus a log line (`data/kraken_feed.py:278-280`). "Rate limit exceeded", "post-only would cross", "insufficient funds" and "invalid nonce" are indistinguishable. Add a registered-code counter, as telemetry only with no control-flow change. **Shipped 2026-09-27:** `data/kraken_feed.py` calls `core.venue_integrity.note_venue_errors` / `note_transport_failure` after the return value is decided. The call bumps `code_stats` (VI-040 rate limit, 041 post-only, 042 funds, 043 nonce, 044 permission, 045 unavailable, 046 other EOrder, 047 other, 048 transport) and never raises. The return value is pinned unchanged even when the classifier itself raises. Offline: `scripts/venue_integrity_report.py` `errors --log`. **VG-5 (SAFE).** A post-only order the venue cancels shows up as a generic "venue canceled" (`execution/order_manager.py:1261`). Count it separately. **Shipped 2026-09-27:** a `QueryOrders` result is scanned read-only, and a venue-cancelled post-only order is counted once per txid as VI-050. Offline: `scripts/venue_integrity_report.py` `post-only --closed <ClosedOrders.json>`. The reason text is matched on "post"+"only" [I], because Kraken's docs do not print it. |
| **Order-state drift / reconciliation** | Batched `QueryOrders` poll (`execution/order_manager.py:1219-1228`). Last look at cancel (`_final_reconcile:561`). Unconfirmed-cancel orphan warning (`_note_cancel_result:613`). Dead-man switch (OD-10). Resume balance cross-check (`main.py:1448`). Equity-truth drift over 2% blocks entries (`main.py:6590`, `:4676`). Internal ledger-vs-fills waterfall: `scripts/reconcile_weekly.py`. It compares our own books with each other, not with Kraken. | **VG-6 (SAFE).** `KrakenFeed.get_open_orders` (`data/kraken_feed.py:451`) has zero callers, so venue-side orders the bot does not know about (orphans or manual orders) are never listed. Add a read-only diff report. Auto-cancelling them would be COHORT-RESETTING. **Shipped 2026-09-27:** `scripts/venue_integrity_report.py` `orphans` (`--open` export or read-only `--fetch`). It joins on the order manager's `userref` derivation, and flags orphans (VI-060) and stranded orders (VI-061: the bot has recorded them terminal, but they are open at the venue). It never cancels. **VG-7 (SAFE).** Nothing reconciles `fills.csv` against Kraken's `TradesHistory`/`ClosedOrders`. Add a live-only report. **Shipped 2026-09-27:** `scripts/venue_integrity_report.py` `reconcile --closed --trades`. It joins order_id → userref → ClosedOrders txid → TradesHistory `ordertxid` and compares qty, VWAP and fee per order. Dry rows are excluded and counted. Codes VI-070/VI-071. |
| **Self-trade handling at the venue** | `LB-022` guard (F3). | **VG-8 (SAFE).** Two facts are not established. First, Kraken's default self-trade-prevention mode when `stptype` is omitted is [UNKNOWN]: it has not been verified here against Kraken docs. Second, the 5m resting-entry vs marketable-exit path (OD-9) is unmeasured. The simulator cannot self-match, so dry-run data proves nothing either way. Verify the venue docs, and add a live-only fill scan for same-pair opposite-side own fills. **Shipped 2026-09-27:** [K] the venue default is `stptype=cancel-newest` ("arriving order will be canceled"; https://docs.kraken.com/api-reference/trading/add-order, read 2026-09-27). On the OD-9 path that cancels the arriving **exit** [I] (see `docs/law/pre_live_checklist.md`). `scripts/venue_integrity_report.py` `self-cross` runs the live self-match scan (VI-080) plus an OD-9 coexistence scan over audit terminals, which uses fill time as the end of an order's life. [K] On telemetry `origin/paper-telemetry` @ `4dc5334a` (sim data, main chain), 715 exits with a recorded lifetime had 2 overlaps with an opposite-side resting entry. One was a long-book bid that LB-022 cleared. The other was one unguarded overlap of 0.224s with unknown book and marketability, bounded by terminal time. The self-match scan found 1 dry pair: two opposite-side exits on ETH/USD at the same instant and price. |
| **Unilateral terms changes / delisting** | Live `AssetPairs` metadata with a static fallback, verified 2026-07-17 (`data/kraken_feed.py:41-65`, `:584-617`). Zero-after-format guard (`OM-013`). The skimmer can rotate the universe. The fee schedule is re-read at readouts (`fee_drift_report.py`). | **VG-9 (SAFE).** Nothing reads the pair `status` field (`cancel_only` / `post_only` / `limit_only` / `reduce_only`) or `SystemStatus`. Add a report or alert. Gating entries on it is COHORT-RESETTING, unless the operator rules it a SAFETY INVARIANT. **Shipped 2026-09-27:** `scripts/venue_integrity_report.py` `venue-status` (exports or read-only public `--fetch`). It flags any traded pair, or SystemStatus, that is not `online`, and any missing pair. Code VI-090. Report only. |
| **Custody exposure** | Invariant 4: withdrawal and transfer verbs are refused before any network I/O, under any spelling (`data/kraken_feed.py:69-111`, `:253`; pinned by `tests/test_hard_invariants.py`, [K] mutation killed). **Never add withdrawal capability in any form.** Margin: `LeverageGovernor` scales entries below a 200% margin level and blocks them below 150% (`risk/leverage.py:75-79`), well above Kraken's roughly 40% liquidation level. `capital_management.savings_pct_of_profit` is internal accounting only: the money stays on Kraken. | **VG-10 (SAFE).** Report dollars held on Kraken against an operator-set off-venue target. Protection means keeping little on the venue, and the operator does that manually outside the bot. **Shipped 2026-09-27:** `scripts/venue_integrity_report.py` `custody --target-usd` (TradeBalance `eb` from an export, `--equity-usd`, or read-only `--fetch`). Code VI-100. **VG-11 (SAFE, pre-live checklist).** The operator confirms in the Kraken UI that the API key has no withdraw or funding permission. The bot cannot verify this without attempting a withdrawal. **Shipped 2026-09-27:** item 1 of `docs/law/pre_live_checklist.md`. The deny-list is untouched and pinned again by `tests/test_venue_integrity.py`. |

The SAFE follow-ups VG-1..VG-11 shipped on 2026-09-27 as measurement only.
The tool is `scripts/venue_integrity_report.py` over `core/venue_integrity.py`,
the codes are the VI family, the pins are in `tests/test_venue_integrity.py`,
and the operator list is `docs/law/pre_live_checklist.md`. Every acting
variant (auto-cancel, gating on status, sending `stptype`, acting on a
fill-acceptance breach) is COHORT-RESETTING and stays on the operator
docket.

---

## Corrections carried from the deleted document

The deleted document made four claims that do not hold at HEAD, so this
standard does not repeat them:

1. "each cancel/reprice is bounded (`order_manager.max_reprices`)". The knob is
   dead (OD-2).
2. "One resting order per position purpose". The grid ladder rests up to 3
   entry rungs for one approved entry (OD-4).
3. "the 5m book's own entries and exits do not coexist on this timescale".
   This was never measured (OD-9, VG-8).
4. "the venue's own STP remains the documented backstop". The bot sends no
   `stptype`, and the venue default has not been verified here (VG-8).

## Review contract

`.claude/agents/market-conduct-compliance.md` reviews diffs against this
document. A FLOOR breach is **blocking**. Any change to an OPERATOR DECIDES
row, or a new rule of that kind, is **reported for the operator** with the
row number and its class, and is never decided by the reviewer.
