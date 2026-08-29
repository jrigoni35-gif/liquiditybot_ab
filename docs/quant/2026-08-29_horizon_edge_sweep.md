# Horizon edge sweep — is the liquidity-footprint thesis alive but mis-clocked?

**Class: SAFE** (reads `outputs/signal_history.csv`; writes only this doc,
`scripts/horizon_edge_sweep.py`, `tests/test_horizon_edge_sweep.py`). No
decision-path, config, order-lifecycle, or `outputs/` change. Does not touch
the accruing era-5 cohort.

**Decision it informs:** whether the data justifies opening an execution
adjudication for a horizon / label change (the bot was designed as a
multi-day whale-accumulation / smart-money-footprint follower; it runs as a
~24-bar directional predictor reading gross≈0, fee-dominated —
`2026-08-29_fee_dominance_diagnosis.md`, `2026-08-29_fee_anatomy.md`).

---

## VERDICT — UNDECIDABLE AT EFFECTIVE N at the design (24–72h) horizon; thesis NOT supported, and the apparent support is an effective-n artifact

Three findings, in decreasing order of confidence:

1. **No liquidity-footprint feature carries a deflated, fee-clearing forward
   edge at any horizon.** Of 18 features × 7 horizons (126–132 evaluable
   cells), **zero** clear the triple gate `|net-of-fee spread| > 0` **AND**
   `|z_eff| > 2` **AND** the two routes agree — in the pooled run. [K]

2. **The seductive "IC rises with horizon" pattern is a pure effective-n
   (autocorrelation) mirage.** Every feature whose *nominal* IC climbs with
   horizon — `flow_tox`, `liq_pocket_pull`, `th_grid`, `footprint_block`,
   `venue_disloc_dir` — has its *effective* (non-overlapping) IC **collapse
   or flip sign** at 24–72h. The nominal climb is consecutive forward
   windows overlapping ever more as H grows, not accumulating information.
   [K]

3. **At the design horizon the measurement is structurally underpowered, so
   the thesis cannot be confirmed or refuted here.** The priced history spans
   only ~24.7 days, giving **n_eff = 40 at 72h** (≤ 8 independent windows ×
   5 qualifying assets). Detecting a plausible IC≈0.05 needs n_eff ≈
   (2/0.05)² ≈ 1,600 [I]. We are 40× short. Where deflated significance *does*
   exist (15min–12h, n_eff 373–917) it is **intraday** — the opposite of the
   days-scale thesis — **sign-unstable across horizons**, and **never clears
   the 120 bps fee floor**. That signature is microstructure mean-reversion
   noise, not a coherent accumulation footprint.

**Consequence for the operator's question:** this measurement does **not**
justify an execution adjudication for a horizon/label change. There is no
deflated edge to chase, and the nominal edge that looks like one is an
artifact of the exact effective-n inflation the dispatch flagged as the #1
false-positive risk. Deciding the days-thesis on its own timescale would
require months more priced history (to lift 72h n_eff from ~40 toward ~1,000+)
or a denser, clock-sampled (not signal-triggered) price series per asset —
neither of which this corpus provides.

---

## Reconstruction (exact)

**Needle / source.** `outputs/signal_history.csv`. Per evaluated candidate the
row logs its feature vector and the quoted `entry_price` at that instant. Per
asset, the sorted `(asset, ts, entry_price)` triples ARE a sampled forward
price path; `ts` is unix **seconds**. For a row at `(asset, t0, p0)`, the
forward return at horizon H is `(p_H − p0)/p0` where `p_H` is that asset's
price sample **nearest `t0+H`, strictly forward, within tolerance
`0.5·H`** (else the row is discarded at that horizon). `fwd_ret` is
**market-absolute** (price up = positive) — independent of the side the bot
chose AND of the `label`/`net_pnl_usd`/`label_ret_pct` columns.

**Live-file snapshot.** `outputs/signal_history.csv`, mtime **2026-08-29
10:25:46 −0500** at first read; the live runner appends ~1 row / few minutes
(observed 19,246 → 19,247 → 19,248 data rows across reads). The pooled sweep
read the file at **2026-08-29T15:33:38Z** (n_total = 19,247 data rows,
n_priced = 9,889); the h432 cut at **2026-08-29T15:34:56Z** (n_priced =
8,923). All counts below are as-of those reads; ±2 rows in 19k does not move
any conclusion.

**Boundaries (inclusive, verbatim).**
- Full corpus `ts`: **1783946147 → 1788017146** = 2026-07-13T12:35:47Z →
  2026-08-29T15:25:46Z (47.12 days).
- **Priced** window (`entry_price` > 0, the only rows that yield a price
  sample): `ts` **1785878092 → 1788017146** = **2026-08-04T21:34:52Z →
  2026-08-29T15:25:46Z** (~24.7 days). Rows before 2026-08-04 carry
  `entry_price ≤ 0` (9,358 of 19,246 — no price sample) and are absent from
  the path. [K]
- Era filter needle (robustness cut): `label_era == "triple_barrier_h432"`.
  The priced window is **90.2% single-era** (8,922 of 9,888 h432; 922
  `triple_barrier`, 44 `exit_sim`) — so cross-era pooling of the price path is
  a near-non-issue here, and the `label_era`-confound class (which governs
  *label-derived* statistics) does not apply to this label-independent
  reconstruction at all. Confirmed by re-running restricted to h432.

**Feature sign — read from `ml/features.py`, not the dispatch grouping.**
Only `ofi_dir`, `imbalance_dir`, `imbalance_delta_dir`, `venue_disloc_dir`
carry `dir_sign` (side-relative); they are **un-signed to market-absolute**
on load (`value · (+1 long / −1 short)`; `side↔direction` is 100% consistent
in the data). `manip_suspect` is `clip(x,0,1)` — a **[0,1] magnitude, NOT
side-signed** (the dispatch listed it under "sign"; the code disagrees, code
wins). `poc_dist`/`va_pos` are signed to price *structure*, not trade side;
the other continuous features and all `th_*` are [0,1] magnitudes. `th_*` are
also reported as a `footprint_block` = mean of the five.

**Two routes, must agree (double-derive).** (1) IC = Spearman(feature_market,
fwd_ret). (2) Long-short quintile spread (per-asset quintiles, n-weighted
pooled) net of the **120 bps** true-fee round-trip. A cell where the IC sign
and the spread sign disagree is reported `agree=False`.

**Effective n.** The decisive IC is computed on a **non-overlapping**
subsample — one accepted observation per asset per H-length block, so the
kept `[t0, t0+H]` windows are pairwise disjoint — with `z_eff = IC ·
√(n_eff − 1)`. Nominal (overlapping) IC and n are reported alongside but are
NOT the significance basis. Stratified per-asset AND pooled.

---

## Evidence

### Per-feature best horizon by net-of-fee spread (pooled) — all fail the gate

The largest apparent spreads sit exactly where the independent data is
thinnest (72h, n_eff = 40; `venue_disloc_dir` n_eff = 16), and the effective
IC there is non-significant and frequently the WRONG sign. [K]

| feature | best H | spread | net−fee | ic_eff | z_eff | n_eff | gate |
|---|---|---|---|---|---|---|---|
| flow_tox | 72h | +0.0184 | +0.0064 | −0.0571 | −0.36 | 40 | fail |
| poc_dist | 24h | +0.0251 | +0.0131 | −0.0198 | −0.31 | 239 | fail |
| va_pos | 24h | +0.0159 | +0.0039 | −0.0623 | −0.96 | 239 | fail |
| liq_pocket_pull | 72h | +0.0476 | +0.0356 | **−0.2151** | −1.34 | 40 | fail |
| fvg_liq_confluence | 72h | +0.0140 | +0.0020 | −0.1499 | −0.94 | 40 | fail |
| manip_suspect | 72h | +0.0197 | +0.0077 | +0.0865 | +0.54 | 40 | fail |
| venue_disloc_dir | 72h | −0.1050 | +0.0930 | +0.0952 | +0.37 | **16** | fail |
| th_grid | 72h | +0.0607 | +0.0487 | **−0.0424** | −0.26 | 40 | fail |
| footprint_block | 72h | +0.0248 | +0.0128 | −0.1478 | −0.92 | 40 | fail |

(`depth_ratio`, `fvg_pull`, `book_touch_share`, `imbalance_dir`,
`imbalance_delta_dir`, `th_stopzone`, `th_barclose`, `ofi_dir` best cells also
fail; `th_metronome`/`th_clockwork` are too tie-heavy — 0.8% / 4.5% live — to
form quintiles.) **Bold** = effective IC sign contradicts the spread sign, so
the "profit" is not even self-consistent.

### Nominal IC rises with horizon; effective IC does not (the artifact)

Pooled, at the design horizons (24h / 48h / 72h): [K]

| feature | ic_nom 24/48/72 | ic_eff 24/48/72 |
|---|---|---|
| flow_tox | +0.040 / +0.041 / +0.070 | +0.062 / −0.042 / −0.057 |
| liq_pocket_pull | +0.034 / +0.074 / +0.121 | −0.116 / +0.017 / −0.215 |
| th_grid | +0.077 / +0.116 / +0.142 | −0.076 / −0.107 / −0.042 |
| footprint_block | +0.045 / +0.055 / +0.068 | +0.058 / −0.013 / −0.148 |
| venue_disloc_dir | −0.220 / −0.246 / −0.269 | −0.020 / −0.045 / **+0.095** |

Every monotone nominal climb evaporates or flips under non-overlapping
sampling. `venue_disloc_dir` is the sharpest trap: a nominal IC growing to
−0.27 with a +9.3% net spread — on 18%-live rows, n_eff = 16, effective IC
non-significant and sign-flipped.

### Most-significant effective IC per feature — all at 15min–12h, sign-unstable

The only real deflated significance is intraday and does not persist: [K]

- `va_pos` 15min ic_eff **+0.1234, z +3.73** (n_eff 917) → 6h **−0.101, z
  −2.21**. Sign flip.
- `imbalance_dir` 15min +0.092, z +2.77 → 6h **−0.140, z −3.05**. Sign flip.
- `fvg_liq_confluence` 1h −0.112, z −3.19 (binary feature — rank-biserial;
  never clears fee).
- `th_grid` 12h −0.143, z −2.75 (nominal IC is *positive* here — full
  nominal/effective disagreement).

None at 24h+; none clearing 120 bps.

### Multiple-testing accounting

Pooled: 132 evaluable cells, **14** with `|z_eff| > 2` vs **~6 expected by
chance** (α=0.0455). The excess is modest, **entirely at 15min–12h**, with
**mixed signs within the same feature across horizons**, and **none** in the
decisive `net>fee ∧ |z|>2 ∧ agree` set. That is the profile of noise plus
short-horizon microstructure, not a discovery. [K]

### Robustness — single-era (h432) cut

Restricting to `triple_barrier_h432` (n_priced 8,923): 113 cells, 11 with
`|z_eff|>2` vs ~5 expected. Exactly **one** cell clears the triple gate —
`footprint_block` 24h, net−fee **+0.0007** (7 bps over the floor), z 2.23,
n_eff 152 — which **does not replicate in the larger pooled run**
(footprint_block 24h pooled: net−fee −0.0037, z +0.90). A +7 bps hit that
appears in a sub-sample but not its superset, at 1 of 113 cells against ~5
expected false hits, is noise. [K]

---

## Instrument verification (the instrument is the first suspect)

The load-bearing numbers were re-derived by a second, independent polars
implementation (`scratchpad/xcheck.py`), not the sweep script:
- **n_eff @ 72h pooled = 40, exact match.** Route 2 also exposes the ceiling:
  only 5 assets (XRP, ETH, ARB, BTC, SUI) reach the 8-window minimum, each
  contributing **exactly 8** non-overlapping 72h windows (24.7 days / 3 days).
  [K, double-derived]
- `va_pos` @ 15min effective IC: sweep +0.1234 (n_eff 917) vs route-2 +0.1196
  (n_eff 918); the 0.004 gap is the `p0` source (row `entry_price` vs deduped
  path price), immaterial. [K, double-derived]

**Mutation-kill (`tests/test_horizon_edge_sweep.py`, 8 pins).** A synthetic
asset with `flow_tox` coupled to the realized 1h-forward return recovers
ic_eff **+0.51, z +2.88**; a `depth_ratio` control reads null; setting
coupling to 0 collapses ic_eff to +0.074. Proven both directions by
monkeypatch: kernel→`0.0` fails the recover assertion (ic_eff 0.0); kernel→
`0.9` fails the null assertion (ic_eff 0.9); restore reproduces +0.51 exactly.
Also pinned: forward-match tolerance, `_dir` un-signing (short row's stored
+0.5 → market −0.5), and `entry_price ≤ 0` drop.

---

## What this reconstruction could NOT see

- **Underpower at the design horizon is the binding limit.** 24.7 days of
  priced history ⇒ n_eff ≤ ~40 at 72h. The days-thesis is not testable to
  significance from this corpus regardless of method. This is why the verdict
  is *undecidable*, not *refuted*, at 24–72h.
- **Endogenous, irregular sampling.** Price samples exist only at
  candidate-evaluation instants (signal-triggered), not on a uniform clock;
  inter-sample gaps run median 600–5000 s with p95 up to ~35 h. The `0.5·H`
  tolerance smears the long horizons (a "72h" match is realized at a median
  ~260,641 s ≈ 72.4 h but individual matches range wide). A denser clock-
  sampled price series per asset would sharpen every long-horizon cell.
- **Survivorship — the *inverse* of the naive worry.** The path includes
  *vetoed* candidates (priced but blocked: SZ-021/022/023, `capped`), so it is
  NOT biased toward entered trades. What it cannot see is **assets/times where
  no candidate fired at all** — the path has holes exactly where the bot was
  silent. Whale accumulation in a book the bot ignored is unsampled.
- **Feature liveness / padding.** `ofi_dir` and `venue_disloc_dir` are only
  ~18% live; `th_metronome` 0.8%, `th_clockwork` 4.5%; `fvg_liq_confluence`
  is binary. Their ICs are tie/zero/tiny-n dominated and not interpretable —
  `venue_disloc_dir`'s dramatic nominal spread is one such artifact.
- **Price prediction ≠ P&L.** `fwd_ret` is close-to-close on sampled mids; it
  ignores real fills, slippage, and exit/give-back geometry. The 120 bps is a
  floor; a genuine long-short would pay ~240 bps (both legs). A positive IC
  here would still have to survive execution.
- **Marginal & linear.** Spearman/quintiles cannot see nonlinear or
  regime-conditional footprints (e.g. a signal that only predicts in a given
  regime). Pursuing those would require new features/meta-labeling, which the
  2026-08-10 model freeze forbids anyway.

---

## Reproduce

```
./.venv/Scripts/python.exe scripts/horizon_edge_sweep.py --json out.json
./.venv/Scripts/python.exe scripts/horizon_edge_sweep.py --era triple_barrier_h432
./.venv/Scripts/python.exe -m pytest tests/test_horizon_edge_sweep.py -q
```

Provenance tags: [K] measured from the sweep script / its JSON this session;
[I] inferred (the n_eff power target). All boundaries inclusive and exact; the
corpus is a live-appended file, counts stamped as-of the read times above.
