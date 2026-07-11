# SMC — Smart Money Concepts structural features

`strategies/smc.py`, wired into `ml/features.py`'s feature vector via
`SMCEngine` (constructed in `main.py`, config block `config.json:smc`).

## What this is (and isn't)

ICT/Smart-Money-Concepts-style structural context, computed fresh from
candle history every cycle and handed to the meta-model as seven extra
feature columns. Same role as `fv_state`/`vol_state`/`liq_state`:
**pure feature computation** — it never gates, sizes, or times an
order, and it never touches `direction` or `all_confirmed`. The
5-gate/informed-flow engines still decide whether a trade fires; SMC
only shades what the meta-model believes `p(win)` is once one does.

Stateless by design: every feature is recomputed from `view["candles"]`
(and, for MTF, the daily candles `main.py` already fetches for the
macro regime engine) on each call. No new per-asset accumulator to
keep in sync with the feed, no train/serve skew, and short/garbage
history degrades to a neutral value rather than raising — the same
fail-safe contract as `strategies/thales.py`.

## The seven features

| Feature | Range | Concept |
|---|---|---|
| `mtf_align` | [-1, 1] | Multi-timeframe context |
| `pd_zone` | [0, 1] | Premium vs. discount zone |
| `liq_pocket_pull` | [0, 1] | Liquidity pockets |
| `fvg_pull` | [0, 1] | Fair Value Gaps |
| `fvg_liq_confluence` | [0, 1] | FVG × liquidity-pocket confluence |
| `poc_dist` | [-1, 1] | Volume Profile: distance to POC |
| `va_pos` | [-1, 1] | Volume Profile: position vs. Value Area |

### `mtf_align` — multi-timeframe context
EMA fast/slow cross computed independently on the LTF view candles
(5m, `smc.mtf.ltf_fast_period`/`ltf_slow_period`) and on genuine HTF
daily candles (`smc.mtf.htf_fast_period`/`htf_slow_period`) — **not**
a resample of the same short window, which the live feed's ~100-200
bar default candle limit can never grow into a meaningful multi-day
higher timeframe. Each timeframe with a defined trend casts one vote
for/against the candidate direction; a timeframe with insufficient
history simply drops its vote rather than forcing a tie. `+1` = every
available timeframe agrees with the trade, `-1` = every one disagrees.

### `pd_zone` — premium vs. discount
Price's position inside the swing range (`swing_high_low` over
`smc.pd_zone.lookback` bars, shared primitive — see below): `0` sits
on the discount extreme (swing low), `1` on the premium extreme (swing
high). The model learns the bias itself (longs favor discount, shorts
favor premium) via its interaction with the existing `direction`
feature; this module does not hardcode that bias.

### `liq_pocket_pull` — liquidity pockets
Magnetism toward the resting stop-loss/order cluster beyond the swing
extreme, in the trade's own direction: for a long, the target is the
swing high (buy-side liquidity resting above it); for a short, the
swing low. `1` = price already sits on top of the pocket; decays to
`0` past `smc.liquidity.pull_max_pct` away.

**Shares `strategies/swing_points.swing_high_low` with
`strategies/thales.py` TH-013.** Both modules read "where the recent
extremes are" off the exact same primitive rather than maintaining two
drifting definitions of "swing" — thales uses it defensively (shade
down when OUR order would rest in the herd's cluster); smc uses it as
a target (shade the model's belief when price is being drawn toward
one).

### `fvg_pull` + `fvg_liq_confluence` — Fair Value Gaps
Classic 3-candle imbalance: bar `i-1`'s high/low doesn't overlap bar
`i+1`'s low/high, leaving a gap most of bar `i`'s range covers. A gap
is "unfilled" if no later bar's range has traded back into it since
formation. `fvg_pull` is the same proximity curve as `liq_pocket_pull`
but toward the nearest **unfilled** gap ahead of price in the trade's
direction. `fvg_liq_confluence` (request item 5 — correlating gaps and
pockets) scores how closely the nearest such gap overlaps the
liquidity-pocket target from `liq_pocket_pull`, within
`smc.fvg.confluence_tol_pct` of the target price: overlapping zones
score `1`, distant ones decay to `0`. High confluence marks a
higher-probability zone precisely because two independent SMC readings
agree on it.

### `poc_dist` + `va_pos` — Volume Profile
A lightweight volume histogram over `smc.volume_profile.lookback_bars`
(`n_bins` price buckets, each bar's volume assigned to its typical
price `(h+l+c)/3`). POC = highest-volume bin's midpoint. Value Area =
bins expanded outward from POC, greedily by volume, until
`value_area_pct` of total volume is captured (standard TPO/volume
profile construction). `poc_dist` is signed, clipped distance from
price to POC; `va_pos` is `0` inside the Value Area, signed and
clipped outside it (support/resistance/target reading).

## Config (`config.json:smc`)

Every window/threshold is config-driven and validated by
`core/config_guard.py` (FATAL on incoherent combinations — inverted
EMA periods, non-positive percentage knobs, `value_area_pct` outside
`(0, 1]`, lookback windows below `strategies/swing_points.MIN_BARS`).
`smc.enabled: false` disables the whole module; every feature then
reports its neutral value (`strategies/smc.NEUTRAL`) and the config
guard skips its checks.

## Schema

Adds 7 columns to `ml/features.FEATURE_NAMES` (bumping
`ml/contracts.SCHEMA_VERSION` to 3). `ml/history.HistoryStore` rotates
the training CSV automatically on a header/schema change (old file
archived with a `.bak_<ts>` suffix); `ml/meta_model.MetaModelService`
falls back to the cold-start prior (`ML-020`) on any feature-vector
length mismatch, so a model trained on the old 34-column schema
degrades safely rather than crashing until the next retrain picks up
the new columns.
