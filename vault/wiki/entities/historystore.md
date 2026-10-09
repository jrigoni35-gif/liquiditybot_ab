---
title: HistoryStore / ml.history
category: entity
summary: "The corpus layer: appends every labeled row, applies uniqueness weighting and era filtering at load, and owns the label-era map — audited end-to-end at the FILING layer 2026-08-06 (write path sound; four honesty defects fixed, one of them feeding position sizing). FIRST CORPUS CORRUPTION 2026-08-08/09: a MIGRATOR, not an appender, destroyed 2,729 label_era cells by re-deriving a column the writer persists; repaired from backups, zero rows lost — the corpus's integrity machinery all protected the RECORD and none of it protected the MEANING. THIRD INSTANCE OF THAT SHAPE 2026-08-09: the corpus carries net_pnl_usd and NO gross and NO per-row fee column (live 93-col header), so no row distinguishes 'the signal was wrong' from 'the signal was right and costs ate it', gross-edge-by-subpopulation is unaskable, postmortem's fallback bucket absorbs 202/264 = 76% of trades, and the binary label conflates the two cases where the MODEL learns — a gap no amount of corpus growth can close"
tags: [module, corpus, ml, durability, filing, incident, schema-gap]
sources: 15
updated: 2026-08-09
---

# HistoryStore / ml.history

The module that owns the training corpus and everything that happens to it between disk and the fit.

## Responsibilities
- **Append** every labeled row with its barrier, source, and era tag.
- **Load** the training view, applying in strict order: admissibility checks, epoch filter, clash-dedup,
  uniqueness correction, mass-preserving rescale, prior-skew detection, lineage/divergence stats, and
  **finally** [[concepts/era-exclusion]].
- **Own the era map** — `label_era_of` is a pure function of the row's own barrier string.

## Load-order significance
Era exclusion runs **last**, so every statistic above it is computed over the **full pre-exclusion
corpus**. This is what makes rollback byte-for-byte identical — and it is also the source of a carried
defect where uniqueness/ESS are reported pre-exclusion alongside post-exclusion row counts.

## The defect it hosted
`log_close` **always wrote a fixed barrier string** regardless of label mode — "a live fill has no
barrier vocabulary of its own." Locally reasonable; globally it meant **no live row could ever join the
current label era**, the root of [[sources/live-label-era-deadlock]].

## Data hygiene invariants
Non-finite values never reach the corpus — finiteness enforced at the **write** boundary with a
load-time backstop: "clean ground truth by construction, not by later cleanup." The CSV is archived
with a timestamped suffix on any schema change.

## Corpus trajectory
1,741 rows (07-19) -> 3,628 -> 4,642 -> 4,907 -> **1,516 post-exclusion** -> **379 after the horizon
re-alignment** -> 606 (08-01). Non-monotone by design: exclusion is a **view**, and every row remains
on disk. **9,358 rows on disk at the 08-04 schema migration** (disk count, not the training view).

## Schema migration 2026-08-04 — price anchors (87 → 89 cols)
The externally-authored price-anchor commits (`4d56d0e0`, `c66fa836`) added
**`entry_price`/`exit_price` at the tail** of the corpus schema. The other session *claimed*
the migration done, but the production corpus was **still 87 cols** when checked — it became
true when the **idempotent migrator** ran post-battery on 2026-08-04: **9,358 rows, 87 → 89
cols, zero features padded** ([[sources/session-20260804-deploy-gate]]). The new columns are
price *anchors* (provenance for P&L reconstruction), not features.

Live from deploy `242568fb`: **every new labeled row carries its `entry_price`/`exit_price`**;
the **9,358 legacy rows are padded 0 = absent-forever** — the pad is a bookkeeping marker, and
the anchors stay **bookkeeping, never a feature** (raw price levels are non-stationary).

**Proven live 2026-08-04 late** ([[sources/session-20260804-deploy-gate]] §6): **27 new corpus
rows carry real `entry_price`/`exit_price`** (newest **0.8442 → 0.8636**) — the anchor claim is
backed by data on disk, not just code inspection. Corpus at **9,385 rows and growing anchored**.
*08-05:* corpus **9,422 rows, 64 price-anchored** — the anchored fraction keeps accruing at the
honest-fills cadence. *08-06:* **9,692 rows on disk** (filing-layer audit count, below), with
**13 `.bak` generations all fully recovered and 0 rows missing** — rotation is not a leak.

## Schema migration 2026-08-08 evening — availability bookkeeping (+4 trailing cols)

Commit `64724480` (owed 41b, [[sources/session-20260808-evening-availability-persistence]]
§1) adds **4 trailing bookkeeping columns** —
`avail_web` / `avail_equity` / `avail_options` / `quotes_frozen` — recording, per row,
whether each context feed was actually alive at feature capture. **Semantics: `""` =
UNKNOWN, strictly distinguished from `"0"` = measured down** — same
never-fabricate-bookkeeping rule as the price-anchor pads
([[concepts/zero-is-not-a-reading]] at the schema level). `migrate_history.py` **pads the
4 columns blank** on legacy rows. Like the anchors: **bookkeeping, never features — zero
model DoF, the closed ledger untouched** ([[concepts/dof-budget]]). With the trailing
block at 26, the width invariant derives as **3 + 64 + 26 = 93**, and the derive-don't-restate
rule reached the last stale literal: `test_session_import_migrate`'s hardcoded 22 now
**derives from `_N_LEAD`/`_N_TRAIL`**.

**The plumbing rode `gate_components`' proven path** — candidate dict, all three
order-meta stashes (incl. ladder rungs via threaded `feat_avail`), and the pending tuple
grown **8 → 9**. **The battery's first red run caught the restart-eater:**
`core/persistence.py`'s pending-tuple rebuild was **FIXED-SHAPE** and would have
**silently dropped the 9th slot on every restart** — the exact class that ate
`gate_components` pre-T4 — fixed + pinned in the same commit. Three red batteries were
all legitimate downstream schema pins (`test_book_tag`, `test_history_migration`,
`test_gate_components` 8→9, `test_long_book_integration`, `test_sample_weights` ×2,
`test_session_import_migrate`) — the deliberate-schema-change ritual working as designed.
The **header change rotates the production file on deploy**; `recover_local_baks`
**merges via marker** — the established rotation/recovery flow, not an incident.
The 08-05 debug sweep ([[sources/session-20260805-debug-sweep]], finding 4, MEDIUM ·
probable): with `multi_horizon.enabled: true` a **decided** candidate keeps its `_cands` slot
until the **full** horizon so shadow horizons complete (`ml/history.py:2211-2218` — early
removal only `if not self.horizons`). The 432-bar migration silently grew that retention
**~2h → 36h (18x)** against a fixed `max_open_candidates: 200`; a saturated pool evicts the
**newest** pending candidate (`ml/history.py:2075-2081`, `self._cands.pop()`), capping
candidate throughput at **≈ 200/36h ≈ 5.5/h** and biasing label sourcing toward quiet hours —
an unpriced throttle on the corpus's dataset multiplier, distinct from the documented 18x
live-label slowdown. **No retune mid-cohort** per the standing hold
([[comparisons/horizon-96-vs-24-bars]]); fix adjudication owed
([[synthesis/owed-measurements]] item 29d).

## The filing-layer audit (2026-08-06, commit `ee0ac4ad`)

The deep dive that asked *how is trade geometry actually filed?*
([[sources/session-20260806-geometry-filing]]) landed almost entirely in this module.

### The write path came back SOUND — file the null
- **Rotation loses nothing** — all **13 `.bak` generations** fully recovered, **0 rows missing**.
- **The pending-vector dict round-trips through `state.json`** — a restart does not orphan a
  feature vector waiting for its close.
- **The width invariant `3 + 64 + 22 = 89` is exactly right.** *(As of the 08-06 audit;
  the 08-08 availability migration grows the trailing block to 26 — see the schema
  section above.)*
- **The live `pt_frac`/`sl_frac` threaded into `log_close` IS the traded geometry** — **no
  recompute anywhere on the path.** The corpus records the bracket that was *placed*, not a
  reconstruction of it. This is the fact that makes the corpus usable as ground truth for
  geometry work at all ([[comparisons/horizon-96-vs-24-bars]]).
- **A suspected 10.9% hole in the ground-truth sample is not a hole** — **34 quarantined
  QA-harness fills** plus **3 documented `FEATURE_SCHEMA_VERSION` drops**, and the drops are an
  **identity, not a rate**: at the instant of the v8→v9 bump **exactly 3 positions were open, and
  they are precisely the 3 unlabeled closes, by position id**. **Nothing was bleeding.**

### Four defects in what it wrote DOWN

**1. `mark_disposition` amputated the bracket geometry — the largest by row count.** The `disp`
column was capped at **40 chars**; a full SZ-023 disposition is **113**, and 40 kept it as far as
`'(net break'`. Measured: **2,614 SZ-023 rows** lost their `[bracket pt=..% sl=..% b=..]`
payload, **1,052 SZ-030 rows** lost their net breakeven and `b_net`, and **ZERO of 9,692 rows
retained a bracket payload** — not few, none. That geometry is **the whole reason a vetoed
candidate is worth filing** (it is the bet that *would* have been traded), and
`scripts/gate_efficacy_report.py` **regex-scrapes this very field**. Cap → **200**
(`DISPOSITION_MAX_CHARS`); `main.py` stops **pre-truncating to 40** at three call sites before the
store's own cap. A cap still exists on purpose — the strings are engine-generated, but an
unbounded free-text column in a 9,692-row corpus is its own hazard.

**2. The bracket-divergence gauge published a tautology.** `bracket_divergence_summary` (ML-082)
blended `tb_time` records whose delta is **0 by construction**; **33 of 35 lifetime records
(94.3%) were `tb_time`**, so the published `1.0000` was **94% arithmetically incapable of reading
anything else**. Now computed over the **priced subset** (`tb_pt`/`tb_sl`) with a new `n_priced`
beside `n`, and **`None` until a priced record exists**. Full treatment:
[[concepts/tautological-instrument]].

**3. A rotation stamped a fresh cache key onto stale counters — and they feed SIZING.**
`_ensure_schema` rotates the corpus wholesale, but `_regime_counts` and `_asset_live_counts` key
on the file's **`(mtime_ns, size)`** and refresh **after each append** — so the next append
stamped the **NEW** file's key onto counts describing the **OLD** corpus, and the loaders saw a
matching key and **refused to re-scan**. **Reproduced as a 6x asset overcount that the cache
actively protected from correction.** **This is not telemetry:** `asset_live_counts` is **`n_a` in
SPB-R scarcity pricing — position SIZING** — and `regime_live_count` **gates the regime-coverage
admission hold**. Fixed by explicit invalidation of both caches at rotation.

**4. `log_close`'s `if entry is None: return` was the ONLY unlogged exit in the entire write
path.** A close with no pending feature vector wrote **no row, silently** — which is exactly why
proving that *nothing was wrong* (above) needed forensic reconstruction from `fills.csv` **that
the corpus itself should have made unnecessary**. Now **`ML-084`** (`ML_UNLABELED_CLOSE`) plus a
per-process `unlabeled_closes` counter. Deliberately **a counter, not an alarm** — a
`FEATURE_SCHEMA_VERSION` bump **legitimately** drops pending vectors — **but it must be visible.**

### And a guard that was right while its message lied
`_append_row`'s width guard used a correct `22`; its **warning message** used a stale `20` that
drifted as `sg_*` (7) and `entry_price`/`exit_price` (2) were appended — so it **reported a
phantom 69-column schema against a true 64**, in **the one line a human reads while debugging a
misaligned corpus**. Both now derive from `_N_LEAD = 3` / `_N_TRAIL = 22`, **pinned against the
live header by a test**.

> **A correct guard with a wrong message is worse than two wrong ones:** the code does the right
> thing while **actively misdirecting the person sent to investigate**.

### Durability
`_append_row` and `HorizonShadowStore` both moved to **`core/runtime.durable_append`**. The
corpus is **the highest-value append-only file in the repo** — a fused row destroys **two**
labelled outcomes and their 64-feature vectors, and `load_training_data`'s
`except (KeyError, ValueError): continue` **dropped the chimera with no counter**.

**The corpus has THREE independent appenders, not two** (corrected 2026-08-06, `0e30ca09`):

| Appender | Cadence | Healed |
|---|---|---|
| `HistoryStore._append_row` | per labelled close, supervised | `ee0ac4ad` |
| `scripts/corpus_sync.py` (recovery merge) | per recovery batch | `ee0ac4ad` |
| `scripts/session_import.py:366` | **HOURLY, UNATTENDED** under `corpus_sync --apply` | **`0e30ca09`** — missed by the sweep, found by the gate's first run |

The third was the **worst-placed**: a kill mid-import fuses two labelled outcomes with nobody
watching, and its `if exists()` header branch left a **zero-length corpus headerless** so
`csv.DictReader` would **adopt the first TRAINING ROW as its column names**. **Three concurrent
unhealed writers on one file is the seam that produced SD-007 on the audit chain**
([[concepts/torn-append-fusion]], [[sources/session-20260806-append-gate]]).

> **`scripts/corpus_sync.py` remains the corpus's one durability blind spot in the new gate** —
> it is allowlisted wholesale for its human-readable log, and is **absent from the positive
> `durable_append` assertion list**, so replacing its data append with a bare one would leave the
> battery green ([[synthesis/owed-measurements]] item 31).

## The fourth writer class — MIGRATORS (the 2026-08-08/09 corruption)

The three-appender table above is about **appends**. The corpus's first actual corruption
came from a **fourth class of writer nobody had inventoried: code that REWRITES existing
rows** ([[sources/session-20260809-corpus-corruption]]).

`scripts/migrate_history.py:125` re-derived `label_era` on every pass —
`label_era_of(r.get("barrier") or "")` — the **only non-idempotent trailing column** in
`migrate_rows`. Because `label_era_of()` has no horizon knowledge while the writer
(`_row_era` → `triple_barrier_era(label_max_bars)`) persists the qualified value, every pass
**collapsed qualified eras into the pooled bucket**: **2,729 rows** across two rotations
(h24→pooled **2,077**, h432→pooled **652**), leaving one bucket holding **three incompatible
label definitions** ([[concepts/label-era]], [[concepts/migration-idempotence]]).

**The same defect was in `scripts/session_import.py:244`** — the same hourly, unattended
path that the append gate caught as the corpus's third appender. **That file has now been
the worst-placed writer twice.** A path that runs hourly with nobody watching deserves to be
read first, not last.

**Trigger — a schema change is a migration trigger.** `64724480` added 4 columns →
`_ensure_schema` **rotated** the corpus at 20:01:30 → `corpus_sync`'s `recover_local_baks`
merged the `.bak` back **through `migrate_rows`** at 20:01:46. Sixteen seconds.

### Why every existing corpus defense missed it

| Defense | What it guarantees | Held? |
|---|---|---|
| `durable_append` / AST append gate | no torn or fused records | ✅ held — every write was clean |
| atomic write + rotation `.bak` | the file is never lost | ✅ held — **and the backups made repair possible** |
| schema width invariants (3+64+22=89 class) | no column drift | ✅ held — width exactly right |
| row-count / `position_id` integrity | no rows lost | ✅ held — **zero rows lost** |
| era exclusion | training never pools eras | ❌ **read the corrupted column and disarmed itself** |

**Every guarantee this module has protects the RECORD; none of them protected the MEANING.**
That is the distinction the corpus layer now has to carry explicitly.

### The repair (box-side)

**2,729 `label_era` cells restored** from `.bak_1785879005.recovered` and
`.bak_1786237290.recovered` by **`position_id` join**, **most-qualified-wins**, **0
conflicts**, **0 rows added / removed / reordered**, **no other cell touched**,
**concurrent-append-safe** (the live runner was appending throughout), pre-repair backup
`signal_history.csv.prerepair_1786253662` retained. Verified after: era `armed=True` /
`active=True`, load **9,746 → 690**, `live_clean` **299 → 6**.

**Re-corruption risk closed:** `pc_supervisor` **spawns `corpus_sync` as a fresh process**
(`_spawn` at `:657`), so the next unattended run picks the fixed migrator off disk — no
stale in-memory code hazard.

**Now gated** by `tests/test_migrate_history.py` (red-first): persisted-era preserved ·
**migration is a fixed point** · legacy row still derives. The middle one is the class
gate — the same escalation from adoption to enforcement the append invariant made
([[concepts/adoption-is-not-enforcement]]).

## THE CORPUS CANNOT SEE ITS OWN COSTS (2026-08-09) — structural, HIGH

([[sources/session-20260809-unbiased-economics]] §3; [[synthesis/owed-measurements]] item **50**.)

Verified against the live **93-column** header: `signal_history.csv` carries **`net_pnl_usd`**
(column 69) and **no gross column** and **no per-row fee column**. `net_pnl_usd` is the only
fee-adjacent field in the file.

**Four consequences, in ascending order of severity:**

1. **No row can distinguish "the signal was wrong" from "the signal was right and costs ate
   it."** Those are opposite diagnoses with opposite fixes, and the corpus records them
   identically.
2. **No offline analysis can compute gross edge by subpopulation** — asset, regime, horizon,
   signal strength. That is **the single most decision-relevant question currently open**, and it
   is not merely unanswered but **unaskable** from this file.
3. **`ml/postmortem.py` cannot decompose either.** Its terminal fallback
   (`postmortem.py:334`, `return "underperformance"` — *"closed below expectation without a single
   dominant cause"*) absorbs **202 of 264 postmortems — 76% of trades die undiagnosed.** The
   taxonomy's other buckets (`cost_overrun`, `alpha_wrong`, `regime_shift`, `fear_event`) are
   sound; **the inputs required to reach them are missing.** The 76% is not a weak taxonomy, it is
   a starved one.
4. **The binary win/loss label conflates the two cases at the point where the MODEL learns.** The
   learner is therefore **structurally incapable of learning the distinction no matter how many
   rows accrue** — which is why *"the corpus needs to grow"* cannot be the answer to this
   particular gap ([[concepts/dof-budget]], [[concepts/unfalsifiable-explanation]]).

> **The pattern this store keeps producing.** The 08-06 filing audit found the write path sound
> while four things were **written down other than what they meant**; the 08-08/09 incident found
> every integrity mechanism protecting the **record** and none protecting the **meaning**. This is
> the third instance of the same shape: the corpus is **complete, durable, well-formed — and
> missing the column that would make it decisive.**

**Proposed fix (own change, own battery — explicitly NOT bundled):** add **`gross_pnl_usd`** and
**`fees_usd`** as **trailing** columns via the established extend-with-defaults ritual (header +
`migrate_history` pad + the downstream pins), backfilled offline from `outputs/fills.csv`, which
carries per-fill `fees_delta_usd` keyed by `position_id`. The idempotence fix (`3c0debd7`) makes
the resulting rotation safe — *the exact path that corrupted this corpus is now fixed and tested*
([[concepts/migration-idempotence]]).

⚠️ **The backfill inherits a known 1.6% optimism:** `fills.csv` sums **376.35** against
`fees_paid_total` **382.59** — **6.24 of fees never reach the ledger**
([[synthesis/open-contradictions-register]] item 18). Backfilled `fees_usd` must be reconciled or
declared short.

## Related
[[concepts/label-era]] · [[concepts/migration-idempotence]] ·
[[sources/session-20260809-unbiased-economics]] · [[concepts/unfalsifiable-explanation]] ·
[[concepts/two-paths-one-quantity]] · [[concepts/era-exclusion]] ·
[[concepts/evidence-floors]] · [[concepts/average-uniqueness-and-ess]] ·
[[concepts/honest-data-framing]] ·
[[concepts/torn-append-fusion]] · [[concepts/adoption-is-not-enforcement]] ·
[[concepts/tautological-instrument]] · [[sources/session-20260806-geometry-filing]] ·
[[sources/session-20260806-append-gate]] ·
[[sources/session-20260809-corpus-corruption]] · [[entities/reason-code-registry]] ·
[[comparisons/horizon-96-vs-24-bars]]
