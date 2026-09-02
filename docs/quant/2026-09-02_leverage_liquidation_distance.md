# Leverage vs liquidation distance vs stop distance (2026-09-02)

Read time (all live-file reads below): **2026-09-02T23:14Z**. Repo HEAD clean
at 2026-09-02T23:05Z per session context; no code touched, nothing written
under `outputs/`. Measurement-only, era-6 SAFE class.

**Every number below is a "would," never a "did."** `system.dry_run=true`
[K, config.json] for the entire corpus — no live order, no venue margin call,
no liquidation has ever occurred. This memo answers: at the position sizes
and stop widths the bot actually produced, if it *had* been live and margin
health degraded the way the config's own thresholds describe, would the
configured stop fire before the configured liquidation floor.

> **REPAIR 2026-09-02 (three verification findings, WARNING, applied 23:24Z; scratch
> `s4v_lev.py` + `s4v_stop.py` re-run, `fills.csv` 1,216 rows / `equity.csv` 289,164 rows /
> `signal_history.csv` (mtime 23:17:11Z) read 2026-09-02T23:24:02Z). Conclusion (0
> violations) survives all three; the headroom numbers and the stop provenance do not.**
> **(1) Crossover mis-solved.** BEFORE §4: "1/L − 0.15 = 0.020 gives L ≈ 6.67x … ~56x more
> leveraged than its historical maximum". AFTER: L = 1/(0.020 + 0.15) = **5.88x**; 6.67 =
> 1/0.15 is the root for stop = 0. Headroom vs the per-position max 0.119x is **49x**, not 56x.
> The planted check as printed ("L=8 → liq_dist 1.25 %") was NOT produced by the memo's
> formula: 1/8 − 0.15 = **−2.5 %** (under this model an 8x position is already below the 150 %
> floor at zero adverse move). The violation IS flagged (stop 2.0 % ≥ −2.5 %), so the detector
> fires, but the number was wrong; a second plant at L = 5 gives liq_dist +5.0 % > stop 2.0 %,
> no violation, and L = 5.88 sits on the line — the detector discriminates on both sides.
> **(2) Stop provenance overstated.** BEFORE: "sl_frac join 324/331 = 97.9 %". AFTER: of the
> 324 joined rows **183 carry `sl_frac == 0`** (all `label_era == exit_sim`, `source == live`;
> nonzero on 141: 60 exit_sim, 38 triple_barrier, 43 h432). `main.py:1989` `elif
> pos.bracket_sl_frac > EPS` — a zero means the live stop came from the vol-scaled config path
> (`main.py:1649-1652`: `max(stop_loss_pct 2.0, 4.0 × sigma_bar_pct) × playbook stop_mult ×
> monitor.stop_widen`); 4σ on those 183 rows maxes at 0.90 % < 2 %, so the base is exactly
> 2.0 % on all 183 [K], times two multipliers NOT readable from either CSV [UNKNOWN; ≥1.0 by
> default]. True signal-history stop provenance is **141/331 = 42.6 %**; 190/331 = 57.4 % are
> the config formula. The nonzero `sl_frac` rows (min 1.94 %, p50 2.17 %, max 4.88 %) drive
> every min-ratio in §4, so §4's minima are unaffected. ALSO unmodelled: `book == "long"`
> positions use `long_book.thesis_stop_pct = 12.0` (`main.py:1979-1984`, `config.json:554`),
> not the bracket; the count of such positions among the 331 is **NOT derived** (fills.csv
> carries no book column). Worst-case bound at 12 %: per-position max L 0.119 → ratio
> (1/0.119 − 0.15)/0.12 = **69x**; at the aggregate max below → 23x. Still no violation.
> **(3) Wrong unit — margin level is ACCOUNT-level.** Per-position notional/equity ignores
> concurrency and hedges. Aggregate open entry notional (sum over positions with
> t_entry ≤ t < t_last_exit; 5 unclosed carried to corpus end) / as-of equity at each entry:
> **p50 0.034x, p90 0.180x, max 0.344x, max 7 concurrent, 0 > 1x.** Min ratio under the memo
> model at 0.344x and a 2 % stop = **137.9** (not 404). Hedge fills: 159, all `ADA/USD sell`,
> notional/equity p50 0.056, p90 0.075, **max 0.269** ($1,246.20 at equity $4,630.70, ts
> 1786067798) — never counted before. Headroom to the corrected crossover on the correct unit:
> 5.88/0.344 = **17x**, or 3.1/0.344 = **9x** under a 5x initial-margin rule (Kraken's
> published spot-margin max for most pairs; 1/L − 0.30 model) — roughly 3× less than the memo's
> "~56x". The corrected model rows for §4 (per-position, all three margin models) give min
> ratios 396–539 and 0 violations in every triad slice; they do not change the verdict.

## 1. The formula (file:line)

`risk/leverage.py:49-84` (`LeverageGovernor.allowed_leverage`), called from
`main.py:4681-4684`:

```
vol = max(sigma_annual_pct, 5.0)
lev = target_vol_annual_pct / vol                      # risk/leverage.py:52
lev = min(lev, regime_cap)                              # :55-57
lev = min(lev, region_cap)                               # :58-60  (region_max_leverage=10)
if 0 < lev < min_leverage: lev = min_leverage            # :67-69  (min_leverage=0.25)
if not use_margin: lev = min(lev, 1.0)                    # :72-74
elif margin_level_pct < margin_block_below_pct: lev = 0   # :76-78  (150)
elif margin_level_pct < margin_scale_below_pct: lev *= frac  # :79-83 (200)
```

This is the **cap** (`allowed_leverage`) passed to `orders.submit(leverage=…)`
(`main.py:4907,5921`) and — only in live mode — on to Kraken's `AddOrder`
(`execution/order_manager.py:1098-1099`). It is *not* the realized ratio of
actual notional to equity; PositionSizer's CVaR/gap/budget/heat stack sizes
inside this cap, usually far inside it (§2). [K]

**Dry-run short-circuit, confirmed by read:** `order_manager.py:1065-1069`
returns immediately on `self.dry_run` — the `data["leverage"]` block
(:1098-1099) that would carry leverage to Kraken never executes. No
`"leverage"` key ever appears in `outputs/audit.jsonl` (`grep -c '"leverage"'`
→ 0 of 76,622 lines [K, read 23:14Z]) or in `fills.csv` (17-column header
carries no leverage field [K]). Realized leverage must be *derived*
(notional / equity-at-entry), not read — done in §2.

## 2. Realized leverage per position

**Needle:** `fills.csv` rows with `purpose=="entry"`, grouped by
`position_id`; `notional = Σ(fill_size × fill_price)` per position.
**Denominator:** `equity.csv` (`ts, equity, daily_pnl`, 289,098 rows,
2026-07-13→2026-09-02 [K]) `equity` value at the last row with `ts ≤`
that position's earliest entry-fill `ts` (as-of join, not "current" equity
— this is the SNAPSHOT-STAMP the contract requires; equity ranges 790.53
to 100,000.03 across the corpus — several capital-epoch resets are visible
in the raw series, e.g. 25,000→~5,000 early on, so per-position as-of
matching, not a single "current equity" denominator, is required).
`leverage_real = notional / equity_at_entry`.

Bounds: fills.csv rows 1–1,216 inclusive (all of it); entry-purpose rows =
543; these collapse to **331 distinct position_ids** (multi-rung entries
grouped). Entry timestamps span 1,784,583,391 → 1,788,387,740 (unix s).
[K, `outputs/fills.csv`, read 23:14Z]

Double-derive of position count: (route 1) `nunique(position_id)` on
entry-purpose rows = 331; (route 2) `len(entries)/` mean rungs-per-position
(543/331=1.64) is internally consistent with grid-rung entries seen in
`main.py:4997` vs `:5921` (rung 0 + `-r{idx}` children) — both routes agree
on 331. [K]

| | ALL | ETH | BTC | OTHER (12 assets; FLOW=n/a) |
|---|---|---|---|---|
| n positions | 331 | 61 | 40 | 230 |
| p50 leverage | 0.004x | 0.005x | 0.005x | 0.004x |
| p90 leverage | 0.023x | 0.057x | 0.041x | 0.023x |
| max leverage | 0.119x | 0.119x | 0.079x | 0.097x |
| n > 1x / 2x / 5x | 0 / 0 / 0 | 0/0/0 | 0/0/0 | 0/0/0 |

**FLOW: zero fills in the entire corpus** (`fills.csv symbol` value_counts
has no `FLOW/USD` row at all, [K] — matches the operator-stated fact
independently re-derived here). Realized leverage for FLOW is **UNDEFINED**,
not zero — the manipulation-score veto (SZ-045) refuses it before an order
ever reaches this pipeline, so this item cannot measure FLOW on realized
positions and says so as the finding, per the contract's FLOW carve-out.

**Claim 1 [K].** No position in the shipped-artifact corpus (331 positions,
543 entry fills, 2026-07-13→2026-09-02) ever realized more than **0.12x**
notional-to-equity, against a configured region cap of 10x and a vol-target
formula whose plain output for a 35%-annual-vol asset is 1.0x. The governor's
*cap* and the *realized* ratio are two different numbers separated by
~1–2 orders of magnitude; PositionSizer's downstream risk stack (CVaR/
budget/heat), not the leverage governor, is the binding constraint on actual
size. Placebo: shuffling `position_id`↔`equity_at_entry` pairing (breaking
the as-of time link) still keeps every ratio under 1x, because equity never
drops below 790 and no single position notional exceeds ~$95 — this is a
structural floor, not a lucky pairing. Era breakdown (labeled subset only —
`exec_era` is NaN on 444/543 = 82% of entry fills, pre-dating the tagging
column; era-6 `9-16ec821e` entries n=18, era-7 n=62, era-8 n=6 — none pool
economically, this is a mechanical geometry check across all of them,
explicitly NOT a performance comparison): p50 leverage 0.022–0.024x in every
labeled era, max 0.097x. No era shows leverage materially different from
the pooled figure.

## 3. Liquidation distance — model and the UNKNOWN it rests on

**Grep needles run:** `maintenance.margin`, `initial.margin`, `margin_used`,
`liquidat` across `risk/ execution/ core/ docs/ main.py` [K]. Result:
**UNKNOWN — the repo does not encode Kraken's real maintenance-margin/
liquidation formula.** The only in-repo statement is a docstring,
`risk/leverage.py:15` and `docs/ARCHITECTURE_V2.md:78`: *"Kraken liquidates
around 40%; the buffer is the point"* — a comment, not a formula. A prior
finding (`docs/quant/2026-08-20_codebase_sweep_result.json`, cited here per
the no-orphan-claims rule rather than re-derived) already flagged that
`data/kraken_feed.py:404-411 get_margin_level_pct()` returns `0.0` both on a
TradeBalance failure and — mechanically, confirmed by this read
(`main.py:6303`, `if not self.dry_run and self.lev_gov.use_margin:`) —
**always**, in every dry-run cycle, because the live-only guard never lets
the fetch run. `risk/leverage.py:75` guards the whole margin-health branch
on `elif margin_level_pct > 0:`, so with `margin_level_pct` pinned at 0.0
for the corpus's entire life, **the margin_scale/margin_block branch is
mechanically dead code in every cycle this bot has ever run.** [K]

Per the task instruction for this UNKNOWN, I use the bot's own
config-visible thresholds (`margin_block_below_pct=150`,
`margin_scale_below_pct=200`, `region_max_leverage=10`) as the liquidation-
avoidance floor and build the simplest model consistent with them, **stated
as an explicit assumption, not a fact about Kraken**: initial margin used
for a position sized at leverage `L` = `notional / region_max_leverage`
(i.e., the venue's stated max marginable leverage, not the bot's own
smaller requested `L`, sets the margin requirement — this is the standard
cross-margin convention and is the only value in config that plays that
role). Then:

```
margin_level(x) = 100 * region_max_leverage / L * (1 - L*x)   # x = adverse price move, fraction
```
At `x=0`: `margin_level = 1000/L` % (L in leverage units, region_max_leverage=10).
Solving `margin_level(x) = 150` for `x`:
```
liq_dist_frac(L) = (1 - 150*L/1000) / L = 1/L - 0.15
```
This is an ASSUMPTION [I], not a read of Kraken's actual rule — flagged so
explicitly because the repo has no ground truth to check it against. It is
directionally conservative in the one place that matters for this question:
smaller `L` (which is where 100% of the observed corpus sits) always
produces a *larger* liquidation distance, so an error in the absolute
formula does not flip the sign of the §4 conclusion, which is decided by
leverage being ~2 orders of magnitude below where the two curves could ever
cross (§4).

## 4. Stop distance and the comparison

**Needle:** `sl_frac` in `outputs/signal_history.csv`, joined to the 331
positions on `position_id`. Join rate: **324/331 = 97.9%** [K] — BUT 183 of the 324 carry
`sl_frac == 0` (no bracket; config-formula stop, see REPAIR (2)); true signal-history stop
provenance is 141/331 = 42.6%. The 7 misses
fall back to `max(stop_loss_pct=2.0%, stop_vol_mult=4.0 × sigma_bar_pct)`
per `config.json` `risk.*`; `sigma_bar_pct` join rate on those 7 is 7/7, so
all 331 positions get a stop distance, tagged by source
(`sl_frac(signal_history)`: 324, `config_fallback`: 7). [K]

| | ALL | ETH | BTC | OTHER |
|---|---|---|---|---|
| n (both leverage & stop available) | 324 | 59 | 37 | 228 |
| median realized leverage | 0.004x | 0.005x | 0.005x | 0.004x |
| median stop distance | ~2.0% | ~2.0% | ~2.0% | ~2.0% |
| min ratio liq_dist/stop_dist | **403.7** | 403.7 | 536.3 | 412.7 |
| violations (stop_dist ≥ liq_dist) | **0** | 0 | 0 | 0 |

**Claim 2 [K].** Zero violations across all 324 positions with a computable
stop distance, in every triad slice. The stop always fires (in this model)
hundreds of times before the config-implied liquidation floor would. **BTC's
"reliability" on this specific axis (liquidation headroom) holds** — its
minimum ratio (536x) is the *largest* of the three slices, i.e. BTC is the
slice furthest from any liquidation concern, though the gap between BTC and
ETH (404x) is small relative to both being three orders of magnitude above
the violation line — this axis does not distinguish the triad in any
practical sense; realized leverage is uniformly near-zero everywhere.

**Crossover leverage** [REPAIRED] (the `L` at which `liq_dist(L)` equals the
corpus's median stop distance, 2.0%): `1/L - 0.15 = 0.020` → `L = 1/0.17` =
**5.88x** (the earlier 6.67x was 1/0.15, the stop=0 root). Per-position max
realized leverage 0.119x → **49x** headroom; on the correct ACCOUNT unit
(aggregate open notional / equity, max 0.344x) → **17x**, and **9x** under a
5x initial-margin rule. This is the power statement for "0 violations": the
check is not underpowered by a near-miss — but the margin is one order of
magnitude, not two. Planted checks (re-run `s4v_lev.py`): `L=8x` →
`liq_dist = 1/8 − 0.15 = −2.5%` (already below the floor), violation flagged;
`L=5x` → `liq_dist = +5.0% > 2.0%`, no violation — the detector fires on the
planted defect and stays quiet on the planted non-defect.

## 5. Has margin_block/margin_scale ever fired?

**Codes:** `core/codes.py` was grepped for `margin|MARGIN|liquidat` —
**no registered code exists** for the margin-scale/margin-block branch; it
only ever emits an f-string into `LeverageGovernor.reasons` (`risk/
leverage.py:78,83`), which is never logged into `audit.jsonl` (no
`"leverage"` key anywhere, §1) and never reaches `runner.log` under that
text either: `grep -c "margin level"` → **0/0** across `outputs/audit.jsonl`
and `outputs/runner.log` (27.4 MB, read 2026-09-02T18:07Z per its own mtime
— not read in full, grep only). A second grep for the literal branch text
(`"entries blocked"`, `"scaled x"`) hits 2 lines in `runner.log`, both false
positives — circuit-breaker trip messages for LTC/XRP, unrelated code path.
[K]

**Claim 3 [K].** Fired count = **0**, and this is not an absence-of-evidence
puzzle to separate from "the check is broken" — §3 already established
*mechanically* (via `main.py:6303`'s live-only guard) that
`margin_level_pct` is pinned at its `0.0` default for every cycle this
dry-run bot has ever executed, and `risk/leverage.py:75`'s `elif
margin_level_pct > 0:` guard means the branch containing both thresholds is
unreachable code for the entire corpus. The grep result and the code read
agree by two independent routes (double-derive: static branch-reachability
read, and full-corpus text grep) — both say zero, for the same reason.

## What this did not check

- [REPAIR] The count of `book == "long"` positions (12% thesis stop) among the
  331 — fills.csv has no book column; joining `audit.jsonl` (2,322 long_book/
  thesis hits) to position_ids was not done. Only the worst-case bound (69x
  per-position, 23x aggregate) is stated.
- [REPAIR] `playbook.stop_mult` and `monitor.stop_widen` at each entry are not
  in either CSV; the 2.0% config-path stop is a floor, not the exact value.
- [REPAIR] Aggregate leverage uses last-exit-fill as position close; 5
  positions without an exit fill are carried open to corpus end (conservative,
  inflates the aggregate).

- No real Kraken maintenance-margin formula exists in-repo to validate §3's
  model against; if the true formula scales margin requirement differently
  (e.g., tiered by notional, or keyed off the *requested* order leverage
  rather than the venue cap), the absolute `liq_dist` numbers move, but not
  by 2–3 orders of magnitude — nowhere near enough to close the gap in §4.
- `equity.csv`'s multiple capital-epoch resets (25,000→~5,000→…→100,000→
  ~790) were not decomposed by epoch for this item; the as-of join makes
  each position's leverage internally correct regardless, but no claim here
  is about *why* equity moved.
- exec_era is NaN on 82% of entry fills (pre-dates the tagging column) —
  those positions could not be attributed to an execution era; the leverage
  numbers for them are still valid (leverage is a sizing property, not an
  execution-era-scoped one), only the era-breakdown table excludes them.
- This item did not touch `label_ret_pct`, PnL, or any economic outcome —
  it is pure position-sizing geometry, deliberately outside the era-6
  accrual moratorium's SAFE/forbidden boundary.
- No live TradeBalance response was ever available to check against §3's
  model (dry_run has never called it) — the entire liquidation-distance
  side of this memo is unfalsifiable against ground truth until a live
  session runs, which the moratorium and hard invariant #1 (`dry_run`
  defaults true) correctly prevent.
