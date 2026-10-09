---
title: "P&L Reconciliation (2026-08-07) — Four Numbers, Three Series, One Invisible Fee Channel"
category: source
summary: "CONFIRMED ground findings of the institutional review (read-only, every claim file:line-cited): the trading-desk 'NET P&L (ALL TIME)' tile is NOT realized_total — it is liquiditybot_perf_net_usd, a rolling last-200 NON-HEDGE window whose panel description ('cumulative realized P&L across every closed trade') is false on two axes; hedge/entry OPEN-leg fees are debited from cash via record_entry_fee and appear in NO P&L counter — the 147-lap churn was ~-$297 all fees of which only the exit-leg ~-$147 entered realized/daily/weekly and ~-$150 is visible only in equity and fees_total; the churn landed wholly in the 08-07 UTC daily bucket; realized_total is monotonic (-208.22); all four displayed numbers reconcile exactly once the three series are named. And the performance ring contains ZERO churn entries — WIN RATE 8.0% / WORST STREAK 57 is the ORGANIC picture, not incident contamination; the pre-incident baseline was WORSE (7.07%, PF 0.026)."
tags: [session, pnl, reconciliation, dashboards, fees, accounting, honesty, performance-ring]
sources: 2
source_path: none — session work product; structured evidence in the institutional-review task output (task wfgp8n380, ground phase)
source_date: 2026-08
authors: [claude]
ingested: 2026-08-07
updated: 2026-08-08
---

# P&L Reconciliation (2026-08-07)

## Provenance and scope

Ground phase of a multi-agent institutional review (task `wfgp8n380`): three **strictly
read-only** agents (`pnl-recon`, `perf-ring`, `panel-truth`), every factual claim cited to
file:line or a command plus its real output, anything unproven labeled UNVERIFIED. **This page
files the CONFIRMED P&L-reconciliation findings** (the first two ground reports). The third
ground report (a classification of every zero/No-data panel) and **four institutional lens
reviews** (execution-microstructure, screens-vs-books, ops/alerting, learning-loop) exist in the
same task output but are **pending a 5-master-judge adversarial panel — deliberately NOT filed
here**; their outcomes arrive in a follow-up ([[synthesis/owed-measurements]]; wiki rule:
hypotheses enter as owed measurements, never as facts).

**Key numbers spot-re-verified at filing time (status ts 23:02:02Z):** `realized_total` −208.22 ·
`fees_total` 382.28 · daily −164.38 · weekly −173.23 · monthly −175.55 · equity 4,615.18 ·
`perf.overall` {trades 200, net −56.91, win_rate 0.08} · `state.json
portfolio.realized_pnl_total` −208.21747270756777. Fill-window counts and fee splits below
re-derived independently from `outputs/fills.csv`.

---

## 1. The four displayed numbers are FOUR DIFFERENT QUANTITIES — and all reconcile once named

| Board number | What it actually is | Where it comes from |
|---|---|---|
| "P&L today" **−164.38** | `state.daily_realized_pnl` — exit-leg nets since the 00:00:30Z UTC reset | `state.py:202-209` counters → `runner.py` → `gc_pusher` `liquiditybot_daily_pnl` → `build_trading_dashboard.py:706`; **reproduced exactly** from per-leg exit nets in `fills.csv` |
| "Week" **−173.23** | same counter family, weekly; no W32 rollover yet, so = daily + Mon–Thu (−8.85) | `state.py:228-253` ISO-week reset; profit-pool skim cannot distort it (equity-neutral pool move, and losses skim nothing — `capital_manager.py:114-129`) |
| "NET P&L (ALL TIME)" **−56.91** | **NOT all-time.** `liquiditybot_perf_net_usd` = PerformanceTracker's **rolling last-200 NON-HEDGE closes** — window FULL and truncating (oldest entry 07-22 while `fills.csv` starts 07-20) | `core/performance.py:39-40` `deque(maxlen=200)`; hedge exclusion `main.py:1588`; `gc_pusher.py:347-352`; panel `build_trading_dashboard.py:717` |
| Equity cliff **−318** (4,933.68 → 4,615.33) | realized −164.38 **+ open-leg fees −157.84 (in NO P&L counter)** + ~+4 uPnL drift | equity identity exact: cash 4,604.31 + savings 1.47 + reserve 0.26 + uPnL 9.28 |

And the fifth number nothing displays: **`realized_pnl_total` −208.22 — monotonic** (resets touch
only daily/weekly/monthly; `state.py` `record_realized_pnl` only ever adds). It deepened from the
−186.78 mid-incident-#1 read and includes the churn's exit legs but **not** any open-leg fee.
`status.json ≡ state.json ≡ equity.csv` field-for-field at verification time.

> ⚠️ **The panel description is false on two axes.** `build_trading_dashboard.py:719` says
> *"Cumulative realized P&L across every closed trade"* — the metric is **window-truncated**
> (last 200) **and hedge-excluded**. An operator reads "down $57 lifetime" when the ledger says
> **−208.22, 3.7x worse**. The books are right; the screen's label is wrong. Filed as a citation
> hazard on [[synthesis/open-contradictions-register]] and as owed item 36(a).

## 2. The invisible fee channel — open-leg fees enter NO P&L series

**Mechanism, verified at source:** a hedge (or entry) fill goes through the entry branch
(`main.py:1767`) → `record_entry_fee` (`main.py:1936`) → `core/state.py:172-178`:
**`cash_balance -= amount` and nothing else** — no realized, no daily, no weekly, no monthly.
Exit legs settle via `record_realized_profit(net = gross − exit_fee)` (`main.py:1988` →
`state.py:202-209`) into all four realized counters. So every trade's **entry/hedge-leg fees are
real in equity and `fees_total` and invisible to every P&L panel**.

**The churn in these terms** (fills.csv, 00:50–02:00Z window, re-summed at filing):
**$296.93 fees** = open-leg **$149.83** (cash-only, no counter) + exit-leg **$147.10**
(entered realized/daily/weekly), gross price P&L ~~≈ 0~~ **−13.37 on 149 paired laps
(panel-corrected — §4.1; ~95.7% fees, not 100%)**. Whole 08-07 day to 21:20Z: 321 fills
(159 hedge + 162 exit), open-leg fees **157.84**, exit-leg **160.29** — which is exactly the
−318.35 equity bridge: **−164.38 realized − 157.84 invisible open-leg + ~+4 uPnL**.

**Bucketing checked and clean (F3):** the daily reset fired 00:00:30Z (`_last_pnl_reset_date`
2026-08-07); 08-06's own day closed at **+0.56**; the churn (01:09–01:34Z) sits **wholly** inside
the 08-07 bucket. The −154 gap between the cliff and the daily counter is the invisible fee
channel, **not** a bucketing artifact.

**Balance-sheet arithmetic, recorded without interpretation** (the interpretation belongs to the
pending lens adjudication): equity 4,615.18 against starting capital 5,000 = **−384.82**, while
`fees_total` = **382.28**. The near-equality of those two numbers is an observation about the
whole book's history, filed here as arithmetic only.

## 3. The performance ring is CLEAN of the churn — the desk's ugly stats are organic

`perf.record_close` has **one call site**, guarded by `if not pos.is_hedge:`
(`main.py:1585-1591` — *"rolling performance ledger — every full close, real positions only"*).
Verified against the persisted ring in `state.json`:

- **ZERO of the 200 ring entries fall in the churn window** (nearest neighbors: 08-06 21:22Z
  DOGE loss, 08-07 06:11Z XRP win). Ring win rate with vs without the window: **identical 8.00%**
  — there is nothing to exclude. The guard held under a 290-fill stress event with zero leakage.
- Board pipeline reproduces **digit-for-digit** from the ring: win rate **8.00%**, payoff
  **0.676**, PF **0.0588**, expectancy R **−0.3490**, worst streak **57** — matches the desk's
  8.0% / 0.68 / 0.06 / −0.35 / 57 exactly.
- **The pre-incident baseline was WORSE:** the 198 ring trades before 01:09Z run **7.07% win,
  PF 0.026, expR −0.355, streak 57, net −58.90**; the only two post-incident trades were both
  **wins** (XRP +0.06, ETH +1.92) and nudged the ring **up** to 8.0%.
- The **57-loss streak predates the incidents by two weeks** — it runs 2026-07-22T14:39Z →
  07-23T14:34Z (ring idx 51–107), entirely inside the pre-churn population.

> ⚠️ **Citation hazard (filed):** never attribute the desk's 8.0% win rate / 57-loss streak to
> the hedge-churn incidents — the ring **excludes hedges by construction** and contains zero
> churn entries. This is the **organic** net picture of the strategy, consistent with the
> standing [[concepts/payoff-asymmetry]] diagnosis; the churn is an *execution* incident living
> in fees/equity, not in these stats.

**PARTIAL (not adjudicated, owed 36(c)):** the ring is **stale-heavy** — 133/200 entries
(66.5%) are from 07-22/07-23 (that cohort: wr 6.0%, PF 0.031); the other 67 run wr 11.9%,
PF 0.078; the last 30 (08-01→08-07) run wr 20.0%, PF 0.180, net −10.74 — better, still losing.
Whether the July cluster is fully organic or partly residue of the since-fixed QA-harness output
pollution ([[sources/test-suite-outputs-contamination]]) is **UNVERIFIED** — adjudication owed
(read-only; label, never delete).

## 4. Panel adjudication arrived (2026-08-07, same day) — corrections that travel with this page

The 5-master-judge panel filed at [[sources/session-20260807-institutional-review]]
adjudicated everything §4 previously deferred (all six areas 5-0 APPROVED_WITH_CONDITIONS).
The core reconciliations above **held** — equity identity exact, daily reproduced to the cent,
ring recomputed digit-for-digit, hedge-exclusion guard zero-leakage. Five corrections bind:

1. **§2's "gross price P&L ≈ 0 / all fees" → gross −13.37 on 149 paired laps, fees 301.31**
   (~95.7% fees, ~4.3% spread/slippage crossing). "All fees" was inferred, never leg-paired.
2. **`fees_total` 382.28 was never reconciled to the fill ledger (376.04)** — $6.24 gap;
   quarantined 08-01/02 fills carry $7.21 (likely cause); −$0.97 residual open.
3. **Canonical churn window: 01:09:00–01:34:59Z = 294 fills = 147 laps** — this page's
   290/296-fill counts are envelope variants and must be mapped when cited. (And the window is
   the **same event** the 08-06 thrash page filed in local time — one event, double-filed;
   [[sources/session-20260807-institutional-review]] §B.)
4. **§3's verdict-word "organic" overreached** — "not an incident artifact" stands (zero churn
   entries in the ring); provenance of the 07-22/23 cluster remains **unadjudicated** (owed
   36(c)). Say "organic" nowhere until it closes.
5. **§1's two-axis taxonomy gains a third axis:** the perf ring's nets **include pro-rata
   entry fees** (`main.py:1955-1971`) while the realized counters do not — a fee-basis
   divergence between −56.91 and −208.22 beyond window + hedge-exclusion.

Two annotations from the adjudicated panel-truth report: the conviction funnel's honest 0/0 is
honest **for a seam that 1,100+ exploration admissions (ML-070/ML-072) bypass entirely**; and
the markout table is **sim-conditioned** — the DRY_RUN fill-at-limit RNG manufactures phantom
favorable maker markout by construction ([[concepts/paper-real-boundary]]), so nothing in it
is venue truth. The pytest-xdist experiment also resolved: 3423/1 in 413s at `-n 8` vs 623s
serial, identical results (second confirming run pending).

## Addendum (2026-08-07 evening) — the write topology under the three series, verified

The evening ops session ([[sources/session-20260807-evening-ops]] §4) verified the write
topology this reconciliation rests on, at file:line: **one** lifetime counter
(`state.fees_paid_total`, `core/state.py:168-170` → snapshot `fees_total`, `runner.py:1154` →
`gc_pusher.py:250`) with **exactly two writers** — entry/open legs at `main.py:1935` (paired
with the `record_entry_fee` cash-only debit at `:1936`, this page's invisible channel) and exit
legs at `main.py:1980` (netted into realized). So `fees_total` is structurally **the only
complete fee ledger** — every leg of both books — which is what makes this page's
equity-vs-daily gap decomposition, and the money-path fee identity, well-founded rather than
luckily right. Sim-side dollars throughout, as above.

## Second addendum (2026-08-07 night) — the panel condition SHIPPED as `486a6891` (boards v37)

Owed item 36(a) closed the same night ([[sources/session-20260807-closing-batch]] §6): the hero
tile now reads **`realized_total`**, the ring is retitled **"last 200 closes"**, and
**`fees_total` has its own tile** — §2's invisible open-leg channel is now the one number on
screen that sees an entry fee before the close. One correction travels back to §1: this page's
"realized_pnl_total is unexported" (echoed in item 36a) was **wrong** — the key has been in
`build_status` (`runner.py:1163`) since the initial commit and in the pusher's ship list since
`9b035996`; the true defect was **display and labeling only**, which is what `486a6891` fixed
(board-generator only, per the standing rule). 36(b)'s conscious counter decision and 36(c)'s
ring-provenance adjudication remain open.

## Addendum 2026-08-08 — the taxonomy's first operational test: the budget re-anchor

The weekly-budget lockout and its audited re-anchor
([[sources/session-20260808-budget-reanchor]]) exercised this page's three-series taxonomy
twice in one day. **(1) As a proof:** the re-anchor's no-ledger-touch guarantee was verified
*through* the series separation — the equity-anchored week anchor moved ($4,940.59 →
$4,617.00) while **`weekly_pnl` −173.36 stayed byte-identical**; only a taxonomy that names
the anchor and the realized counter as different series can even state that check. **(2) As a
correction:** the circulated attribution *"~$303 of churn fees vs weekly_pnl −173.36, so the
week was net positive without the bug"* **crosses two series** — per §2 of this page, only the
churn's exit-leg ~$150 lives in `weekly_pnl` (open legs are cash/equity-only), and on the
equity axis the week drop was $323.6 — so without the bug both axes read ≈ flat (−$21
equity / −$23 realized), not positive. The named-series translation hazard
([[synthesis/open-contradictions-register]]) fired on an *operator-circulated* number this
time, and the filing caught it. The lockout attribution itself was unaffected: frac 1.09 vs
≈ 0.07 without the bug — the taper-to-zero was 100% bug-attributable on the only axis the
budget reads (equity vs anchor).

## Related
[[sources/session-20260807-closing-batch]] ·
[[sources/session-20260807-evening-ops]] ·
[[sources/session-20260807-institutional-review]] · [[concepts/paper-real-boundary]] ·
[[sources/session-20260807-hedge-churn-guards]] · [[sources/session-20260806-hedge-thrash]] ·
[[concepts/payoff-asymmetry]] · [[concepts/cost-truth]] · [[concepts/zero-is-not-a-reading]] ·
[[synthesis/the-money-path-thesis]] · [[synthesis/risk-posture-doctrine]] ·
[[synthesis/open-contradictions-register]] · [[synthesis/owed-measurements]] ·
[[sources/test-suite-outputs-contamination]] · [[entities/liquiditybot]] ·
[[entities/observability-sidecars]] · [[entities/reason-code-registry]]
