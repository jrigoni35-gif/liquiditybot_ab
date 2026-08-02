# Board design rules — 2026-08-01 HIG pass

The boards are **generated**. Never hand-edit the JSON in this directory;
edit `scripts/build_trading_dashboard.py` and regenerate. A test
(`test_generator_matches_shipped_json`) fails if the two drift, which is how
this pass caught its own first attempt editing the output instead of the
source.

Rules live in `_hig_pass()` next to `_apple_palette()` — both are recursive
post-passes, so a rule is stated once rather than remembered at 179 call
sites. Output properties are pinned by `tests/test_dashboard_hig.py`, which
asserts the *result*, not the implementation.

## What was measured

A first audit claimed **65 panels missing units**. That was wrong by roughly
10×, and worth recording because the failure mode is generic: a metric that
is easy to count is not automatically a defect count.

| Bucket | n | Verdict |
|---|---:|---|
| Integer counts, no unit | 29 | **Correct.** `short` renders `1000` as `1 K` — strictly worse |
| Ratios / multipliers (Kelly, PF, Brier) | 18 | **Correct.** A multiplier has no unit |
| Unit smuggled into the title | 3 | **Defect** |
| True shares rendered as bare decimals | 5 | **Defect** |

Two further claims dissolved on measurement:

- **"Sparkline usage is inconsistent"** — 55 `graphMode: area` vs 42 `none`
  tracks *exactly* whether the panel's query is a range or instant query. 42
  tiles physically cannot draw a sparkline. Correct engineering.
- **"Colors need a design-system pass"** — the vocabulary was already Apple
  system colors with zero drift, save one hand-picked teal (below).

## The rules

1. **No dead thresholds.** Steps declared with `color.mode` unset rely on a
   Grafana default that varies by panel type. Be explicit. (18 panels)

2. **Units belong on the value, not the title.** `Unlock ETA (days)` renders
   the number dimensionless into tooltips, legends, CSV exports and alert
   notifications — every context that reads `fieldConfig` rather than the
   title. (3 panels)

3. **`percentunit` only for genuine proportions.** A manipulation-suspicion
   of `0.42` is not "42%" of anything; percentunit would assert a
   part-of-whole that does not exist. Scores stay bare. (5 panels converted,
   ~9 deliberately not)

4. **Count axes anchor at zero.** An axis autoscaled to `[270, 274]` turns
   four units of noise into a mountain range.

5. **One legend shape.** Table with `last/min/max` — the point of plotting a
   trend you intend to act on is reading the number beside the shape.

6. **Apple system colors only.** The lone outlier was `#2596AB`, a
   hand-picked teal predating the palette work: 5.37:1 on the dark canvas
   against 9.65:1 for the palette's own `#40CBE0`. Same hue family, nearly
   double the contrast, one fewer vocabulary item.

7. **`percent` vs `percentunit` must match the query.** Grafana's `percent`
   treats the value as *already* a percentage; only `percentunit` multiplies
   a fraction by 100. A panel carrying `percent` must either scale in its
   query (`*100`) or plot something genuinely already in percent units.

## The one live bug this pass found

The execution board's **Calibration gap** gauge inherited `unit="percent"`
from the `gauge()` default while plotting `liquiditybot_ml_calibration_gap`
— which is Expected Calibration Error, `|predicted p − realized rate|`, a
**fraction** in [0,1]. That is why its `mx` was `0.2` and not `20`.

The needle sat in the right place, because the scale was fraction-correct.
Only the printed number was wrong: a real gap of `0.05` rendered as
**`0.050%`** on execution and **`5.0%`** on command — the same metric, the
same query, two readings 100× apart on two boards.

The needle being right is what made it survive: a gauge pinned at zero gets
noticed, a gauge pointing correctly with a mislabeled number does not.
`test_percent_scale_matches_the_query` now fails any panel with `percent` on
an unscaled field whose `max <= 1`.

## The structural fix

Before this pass: **8 timeseries against 171 state panels** (~21:1). State
tiles answer *"is it healthy"* well, and that is most of what these boards
do — that part was never broken.

But *"is it learning"* is a **trajectory** question, and a tile shows a
number, never a direction. `live_clean` sat pinned at 0 for thirteen days and
the board could not distinguish that from a value that had merely touched 0
on the current scrape, because a tile has no memory.

`📈 LEARNING TRAJECTORY` adds four charts, each plotting the **pair whose
divergence is the signal** so the reading needs no arithmetic across two
tiles:

| Panel | Series | The tell |
|---|---|---|
| Label supply | `live_clean`, `live`, `candidate` | flat is the alarm |
| Era exclusion | `new_rows` vs `min_rows` | the gap is the quantity |
| Calibration quality | `calibration_gap`, `mean_uniqueness` | gap widening while labels accumulate = learning the wrong thing |
| Admission funnel | `evaluated` vs `admitted` | admitted flat while evaluated climbs = the gate selecting against itself |

Ratio after: **12 timeseries, ~13.9:1**.

## Not done, on purpose

- **Grid rhythm.** Nine distinct panel heights read as ragged, but some of
  that is intentional column-spanning (one tall panel beside two stacked
  short ones), and the two cases are not distinguishable from the JSON
  alone. Changing `h` forces a `y`-reflow of everything below, so a wrong
  guess silently scrambles a board. Noted, not fixed.

- **Panel removal.** All 161 metrics referenced by panels are verified
  present in the exporter — there are no dead panels to cut. Distinguishing
  *populated* from *useful* needs live board data, which is an operator
  judgement, not a static one.
