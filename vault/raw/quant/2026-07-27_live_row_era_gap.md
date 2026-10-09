# Live-row era gap (2026-07-27) — geometry-alignment plan, Task 1 (V1)

Verification task, spec `docs/superpowers/specs/2026-07-27-geometry-alignment-design.md`
§D6 ("V1 (verification item, first implementation task)"). Confirms the
era-mapping foundation the rest of the geometry-alignment plan (Tasks 2-8)
builds on, and quantifies the live-row exclusion gap V1 exists to measure.

## What was verified

`ml.history.label_era_of` is a pure function of a row's own `barrier`
string — never its `source` column. Two properties, both now pinned in
`tests/test_label_era.py`:

```python
def test_tb_realized_reasons_join_the_triple_barrier_era():
    for b in ("tb_pt", "tb_sl", "tb_time"):
        assert label_era_of(b) == LABEL_ERA_TRIPLE_BARRIER

def test_tier_policy_realized_reasons_stay_out_of_the_tb_era():
    for b in ("tier", "trail", "floor", "realized", "time_stop"):
        assert label_era_of(b) != LABEL_ERA_TRIPLE_BARRIER
```

Both PASSED immediately, ten runs of ten (20 executions total, all green,
0 flakes) — **no code change to `ml/history.py` was needed.**
`_TRIPLE_BARRIER_BARRIERS = frozenset({"tb_pt", "tb_sl", "tb_time"})`
already routes to `LABEL_ERA_TRIPLE_BARRIER` regardless of which row wrote
it (live bracket close or candidate replay), and `_EXIT_SIM_BARRIERS =
frozenset({"trail", "realized", "tier", "floor", "sl", "time"})` already
keeps every tier-policy/realized reason in `LABEL_ERA_EXIT_SIM`, disjoint
from the tb era. The map is source-agnostic by construction — the
guarantee later tasks (5 in particular) rely on was already true, this
task proves it rather than assumes it.

## The V1 hole, quantified

Corpus measured: `outputs/signal_history.csv`, 4,989 rows (4,747
candidate + 242 live) as of this task.

### Raw file scan (brief's Step 3 script, unfiltered)

```
live rows: 242; excluded from tb-era training: 242
excluded barrier mix: [('realized', 195), ('blank', 47)]
```

Every live row's `barrier` is either the hardcoded `"realized"` tag
`HistoryStore.log_close` writes for every live close (`ml/history.py`,
`log_close` → `_append_row(..., barrier="realized", ...)`) or blank
(pre-instrumentation rows, `LABEL_ERA_LEGACY`). **Zero live rows carry a
`tb_*` barrier today** — `label_era_of("realized") ==
LABEL_ERA_EXIT_SIM`, `label_era_of("") == LABEL_ERA_LEGACY`, neither
equals `LABEL_ERA_TRIPLE_BARRIER`.

### Authoritative loader view (`HistoryStore.load_training_data`, matches production)

One of the 242 live rows is `book == "long"` and is out of scope of
`load_training_data` entirely (separate long-book accounting, excluded
before era classification even runs — same convention
`_scan_live_dedup_keys` already applies). Of the remaining 241 in-scope
live rows, measured with `era_cfg` forced active for this measurement
only (not shipped — `ml.era_exclusion` stays exactly as configured,
`forced_on: false`, in `config.json`):

| era | source | rows |
|---|---|---|
| `exit_sim` (`realized`) | live | 194 |
| `legacy` (blank) | live | 47 |
| `exit_sim` | candidate | 2,436 |
| `legacy` | candidate | 1,715 |
| `exit_sim_time_stop` | candidate | 457 |
| `triple_barrier` (`tb_pt`/`tb_sl`) | candidate | 58 |

**All 241 in-scope live rows (100%) are old-era** — none carry a `tb_*`
barrier, so all 241 would be excluded the moment `ml.era_exclusion`
activates. New-era rows measured today: 58, entirely from the candidate
side (`tb_pt`: 36, `tb_sl`: 22 — no `tb_time` yet). Against
`ml.era_exclusion.min_new_era_rows = 150` (`config.json`), the filter is
currently **`armed: false, active: false`** (58 < 150) — inactive on the
live production config, this task changes nothing about that state. This
number will keep climbing on the candidate side alone (triple-barrier
replay of every new signal), but the live-row count will stay pinned at
0 until something changes what a live bracket close *emits*.

### Mechanism

Live closes are labeled by `HistoryStore.log_close`, which always writes
`barrier="realized"` — a fixed string, not the exit reason (tier/trail/
floor/stop) that actually closed the position, and never one of the
labeler's own `tb_*` strings regardless of which `ml.label_mode` is
configured. `_EXIT_SIM_BARRIERS`'s comment (`ml/history.py`) documents
this explicitly: `"realized"` groups with `exit_sim` because "a live fill
has no barrier vocabulary of its own." So today, *every* live close — no
matter how it actually exited (tier take-profit, trailing stop, floor
stop, time-based) — is tagged `exit_sim` and lands outside the
`triple_barrier` era. This is the exact gap `docs/quant/2026-07-26_era_exclusion.md`
already flagged as an accepted, conscious tradeoff ("all 242 measured
live rows are themselves old-era; keeping them would shrink the corpus
without cleaning it") — V1's job was to confirm the mechanism precisely
and put a number on it, not to change the tradeoff.

### Closure route

Task 5 of this plan changes what live bracket closes **emit** — routing
a bracket-traded position's realized close through the label's own
`tb_pt`/`tb_sl`/`tb_time` vocabulary instead of the hardcoded
`"realized"` tag — so that a live tb-era close joins `LABEL_ERA_TRIPLE_BARRIER`
via the *exact same, unmodified* `label_era_of`/`_TRIPLE_BARRIER_BARRIERS`
this task just verified. The era map itself is not touched by that
closure (and must not be — `_TRIPLE_BARRIER_BARRIERS`/`_EXIT_SIM_BARRIERS`
are a disjoint-vocabulary partition, not a per-source rule); only the
value `log_close` passes as `barrier` changes, for bracket-traded closes
specifically (non-bracket / senior-overlay exits are out of scope per the
spec's success criteria — "≥95% of model-lane closes emit `tb_*`... rest
= senior overlay exits").

## What did NOT change

- `ml/history.py`: no code changed. `_TRIPLE_BARRIER_BARRIERS`,
  `_EXIT_SIM_BARRIERS`, and `label_era_of` are byte-identical to before
  this task — the map already had the guarantee later tasks need.
- `outputs/signal_history.csv`: read-only measurement, no row written,
  reweighted, or reordered.
- `ml.era_exclusion` (`config.json`): unchanged (`min_new_era_rows: 150`,
  `forced_off: false`, `forced_on: false`); the `forced_on: true`
  measurement above was an in-process, throwaway `load_training_data`
  call for this report only, never written to disk or committed.
- No label/weight/reason code, gate, or invariant touched.

## Task / spec reference

`.superpowers/sdd/task-1-brief.md`,
`docs/superpowers/specs/2026-07-27-geometry-alignment-design.md` §D6,
`docs/quant/2026-07-26_era_exclusion.md` (the exclusion mechanism this
task measures against), `tests/test_label_era.py` (verification tests).
