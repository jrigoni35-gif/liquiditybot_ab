# Raw: Fee-Wedge Feasibility + Adversarial Verification of the Closed-Book Decomposition (2026-08-16)

Five read-only agents (1 finder + 3 hostile refuters + 1 measurement), session
55a25968, evening 2026-08-16 UTC. All values as-of stamped reads of LIVE files
(fills.csv, signal_history.csv mutate mid-read; every number below carries its
read stamp in the agent reports). Analysis code preserved in the session
scratchpad: loss_slice.py / loss_slice2.py / verify_c1.py / stat_attack.py /
full_scan.py / pop_check.py / z_check.py / fee_wedge.py +
fills_snapshot_feewedge.csv (stamped 2026-08-16T23:08:54Z).

Window for every trip-level claim: closed round trips, close-ts <
2026-08-10T23:05:27Z (capital epoch, unix 1786403127). Era-4 accruing rows
independently counted (17 trips, net −$0.6023) and confirmed excluded — zero
leakage (max pre-epoch close 23:04:53.311Z < epoch ≤ min era-4 close
2026-08-12T03:14:40Z).

## 1. Closed-book decomposition — CONFIRMED by three routes

| population | n | net USD | gross USD | fees USD |
|---|---|---|---|---|
| entry-opened | 242 (eff_n 77.0) | −65.74 | −2.73 | 63.00 |
| hedge-opened | 159 | −325.70 | −9.97 | 315.72 |
| book total | 401 | **−391.43** | | |

(−391.44 in the finder's report was a sum-of-rounded artifact.)

- Route 1: instrumented re-run of the finder's mirror (fills.csv 1072 rows, ts
  1784583391.251–1786919610.856) — exact.
- Route 2: structurally different pairing (no dedup, no per-leg abort,
  first-leg classification) — identical.
- Route 3, independent of fills.csv: audit.jsonl PT-061 close records
  (runtime's own book; needles "PT-061", "net_usd", "RP-070"). Coverage starts
  2026-07-31T12:21Z → 216 pre-epoch trips inside coverage ALL match
  fills-derived net within $0.01, zero disagreements; hedge book exact to 4dp
  (PT-061 sum −325.6961 over the same 159 pids).
- Code audit: every hypothesized bug class inert on this data (dup-drop fired
  0×, 2%-tolerance drop 0× pre-epoch, 0 pids mixing entry+hedge legs, 0 trips
  spanning the epoch, 0 blank pids). Hedge classification unambiguous: needle
  purpose=="hedge" → 159 legs, all ADA/USD, all opened AND closed 2026-08-07
  UTC — the documented churn incident, fixed at cf454d5.
- UNRESOLVED loose end: the RP-070 weekly realized ledger (W30 −17.35 /
  W31 −14.88 / W32 −173.33, realized_total −208.31 @ 2026-08-10T00:00Z)
  reconciles with NEITHER book at weekly grain. Known confounds: main.py:1671
  excludes hedges from the perf ledger; RP-041 sweep false-loss; tier-partial
  timing. Does not touch trip-level claims (per-pid PT-061 agreement).

  > **CALLOUT, same session (2026-08-17):** RESOLVED by
  > `scripts/reconcile_weekly.py`, and the hedge-exclusion confound above was
  > WRONG for RP-070 — that guard shields only the rolling perf ledger; RP-070
  > books per exit leg HEDGE-INCLUSIVE, exit-fee-net. The weekly gap was the
  > OPENING-leg fee stack (W32 $161.48) plus the W33 capital-epoch rebase.
  > Waterfall residuals: W31/W32/W33 = 0.00; only W30 +$0.41 remains open.
  > See owed-measurements item 87 for the full resolution.

## 2. "Entry gross is zero" — AMENDED, conclusion survives

Reproduced exactly: gross mean −0.01871%/trip, sd 0.6008, eff_n 77.0
(cohort_effective_n = AFML average-uniqueness on trip holding spans —
independently re-implemented via sweep-line, matches), z_eff −0.273.

- Alternative treatments do not flip anything: z(nominal 242) −0.485;
  z(Kish ESS 175.8) −0.843. All |z| < 1.
- THE ONE REAL CRACK, then it closes: sign test 140 pos / 102 neg (57.9% gross
  win rate, median gross +0.0513%), exact p = 0.0172 at NOMINAL n — but eff-n
  deflated p = 0.17, Wilcoxon p = 0.55. The gross distribution is left-skewed:
  modal small winners, fat losing tail. Amendment: "statistically zero" holds
  for the MEAN under every overlap treatment; the book is not symmetric noise;
  a real +0.05% median would still be 13× below the wedge.
- Fee wedge per trip: mean 0.6694%, sd 0.0551, IQR 0.0025pp — bimodal
  (85.5% of trips ~0.650%, 14.5% > 0.75%), "near-constant" fair,
  "deterministic constant" overstates.
- Power: resolvable gross edge at this corpus ≈ 0.14%/trip at z=2. "Zero"
  means "below 0.14% resolution" — and a true +0.1% would still lose to the
  0.67% wedge.

## 3. "No entry-selection concentration" — AMENDED, conclusion survives a scan
##    the finder never ran

Finder claimed ~100 comparisons; its code ran 9. The refuter ran all 87
buckets × {gross, net} vs complement with eff-n both sides:

- FIVE buckets exceed |z|=3.3 — ALL outcome-conditioned tautologies:
  exit=stop_hit z −27.4, postmortem=alpha_wrong −11.2, exit=tier_1-3 +6.0,
  postmortem=not-in-pm +4.8. (These prove the instrument CAN fire — "0
  findings" and "broken scan" separated.)
- Among genuinely PRE-TRADE axes: global max AVAX +2.92 at n=3, hour-04-08
  +2.33 — nothing reaches 3.3 (exact 0.05/100 Bonferroni bar is z=3.48).
- BTC 0/33 net wins: exact binomial p 0.0431 nominal / 0.1026 at eff_n 23.9;
  P(≥1 all-loss bucket somewhere under iid null) ≈ 1.000. Decisive: BTC won
  15/33 = 45% on GROSS — the zero-cell is a fee/net phenomenon, not selection.

## 4. Provenance of the carried numbers — RESOLVED

- "z = −4.14 at h432": LOCATED. It is the LABEL-SPACE anti-predictive
  statistic from docs/quant/2026-08-16_boardroom_brief_money_path.md
  (260fa9f4 → verbatim in 260f5fa9: P(tb_pt|resolved)=0.258 vs gambler's-ruin
  null 0.429; "h24 z=−4.31, h432 z=−4.14"; candidate/simulated rows) — NOT a
  trade-book statistic, which is why no trade ledger reproduces it. And it was
  RETRACTED THE SAME DAY it was filed (ea259ca5; log.md:518): wrong null —
  vertical-barrier censoring removes PT-bound paths preferentially and
  manufactures the sign; corrected h432 value −1.47 (ns; pooled −0.63,
  p=0.53). The exact −4.14 is a dead snapshot of a gitignored, growing file
  (today's same-family value: 73 tb_pt / 194 tb_sl → z_nominal −5.12 before
  the null correction) — byte replay impossible in principle (standing blind
  spot, comparability-boundaries).
- "0.8% time-outs at h432": UNFINDABLE on disk (needles swept: vault, docs/,
  outputs/*.md, git log -S). Transcription garble; best documentary source:
  "~0.8–1.0 [sigma barrier width], giving an 87.8% time-out rate"
  (concepts/cost-to-volatility-ratio.md:33). Real h432 time-out shares:
  signal_history 209/476 = 43.91% (rising as rows mature: 29.7% @ 08-14);
  horizon_shadow 583/1518 = 38.41%; 08-09 loader snapshot 35.8%.

## 5. THE FEE-WEDGE FEASIBILITY TABLE (the decisive measurement)

True schedule: Kraken Tier-1 spot 40/80 bps maker/taker, CONFIRMED by fresh
fetch 2026-08-16 (kraken.com/features/fee-schedule: $0+ 40/80, $10k+ 22/38,
$50k+ 15/30, $100k+ 12/25, $250k+ 10/22, $500k+ 8/20, $1M+ 6/18) — agreeing
with the 08-07 triple fetch in session-20260807-institutional-review §C. The
sim books config.json:356-357 constants via execution/order_manager.py:511-512
— measured dollar-weighted empirical 25.00/39.83 bps = config restated, NOT a
venue measurement (cost-truth's tautological-instrument claim confirmed by
code path + 708-leg enumeration).

Leg mix (re-derived): entry legs 88.2% maker by count / 83.1% by notional;
trip-level all-entry-maker 200/242 = 82.6%; exits 94.4% taker by count
(98.7% by notional).

Round-trip wedge (mean %/trip, 242 trips) vs gross UCB +0.1182%
(mean −0.0187, sd 0.6008, eff_n 77.0, SE_eff 0.0685):

| schedule | wedge | ×UCB | maker-only variant |
|---|---|---|---|
| booked (actual) | 0.6694% | 5.7× BINDS | |
| shipped 25/40 | 0.6728% | 5.7× BINDS | 0.4999% |
| TRUE Tier-1 40/80 | 1.2610% | 10.7× BINDS | 0.7998% |
| T2 30/60 | 0.9457% | 8.0× BINDS | |
| T3 22/38 ($10k) | 0.6244% | 5.3× BINDS | 0.4399% |
| T5 15/30 ($50k) | 0.4729% | 4.0× BINDS | 0.2999% |
| $1M+ 6/18 | 0.2583% | 2.2× BINDS | 0.1200% = 1.02× |

**Every row of Kraken's spot ladder, at every leg mix achievable on it, binds.
The extreme corner — maker-only execution at the $1M+ tier — reaches parity
(1.02×), not profit. COST_BOUND is decided in feasibility terms on this
corpus regardless of the schedule dispute.** Conservative direction: 90.1% of
the corpus is pre-B2 fill-flattered (biases gross UP); fills.csv omits $6.24
(1.6%) of fees (biases wedge DOWN); spread/slippage excluded — vault records
86.17bp measured all-in vs 65 configured, so true cost is HIGHER. The era-4
gate remains the sole formal arbiter; this is feasibility arithmetic on the
pre-epoch closed book, not the readout, and says nothing about the accruing
era-4 cohort.

What would have to be true for the wedge NOT to bind: gross/trip must exceed
0.47–1.26% (4–11× the 2SE-optimistic edge) depending on tier; volume-tier
climb is insufficient alone at every rung; maker-only exits save 17–46bp and
only reach parity combined with $1M+ volume. At measured gross ≈ 0, no
holding structure crosses zero — turnover reduction multiplies a per-trip
edge that must first be positive.

## 6. Scope — what none of this saw

100% paper corpus (boundary #0); trip reconstruction conventions shared by
both derivation routes (validated against runtime PT-061, not exchange
truth); account's actual Kraken tier never read (TradeVolume dead in
DRY_RUN; Tier-1 inferred, fresh ~$5k account); bucket z's ignore cross-asset
covariance; sign-test eff-n deflation used a scalar global ratio, no block
bootstrap; fills.csv begins 2026-07-20T21:36Z; 185/242 entry trips predate
PT-061 audit coverage (per-pid verification covers 57 entry + all 159 hedge).
