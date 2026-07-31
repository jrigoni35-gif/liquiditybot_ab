# The test suite was writing into the operator's live `outputs/` tree

**Date:** 2026-07-31 · **Status:** FIXED, with a structural guard
**Class:** data hygiene (TANK C3) · **Found by:** following a real-looking
`INTEGRITY FAIL` line in `outputs/corpus_sync.log` that turned out to be a
test fixture.

---

## How it surfaced

While looking for the freshest PC bundle I read `outputs/corpus_sync.log`
and found, twice on this date and repeatedly since 2026-07-18:

```
corpus_sync: bak signal_history.bak_111: recovered 3 stranded row(s)
corpus_sync: bundle peer refused: INTEGRITY FAIL: signal_history.csv
             sha256 mismatch (bundle tampered or corrupt)
```

That reads as a corrupted learning bundle — the highest-severity thing
that log can say. It is not. `sessions/peer/` has never existed on
`paper-telemetry`, on any branch, at any commit:

```
$ git ls-tree -r --name-only origin/paper-telemetry -- sessions | ...
sessions/cloud-mirror
sessions/pc-live
```

`peer` is the bundle label used by `tests/test_corpus_sync.py`. The line
is written by `test_tampered_bundle_refused`, which deliberately corrupts
a fixture to prove the importer refuses it — behaving exactly as designed,
into the wrong file.

**Reproduced directly:**

```
$ wc -l outputs/corpus_sync.log        → 850
$ pytest tests/test_corpus_sync.py -q  → 4 passed
$ wc -l outputs/corpus_sync.log        → 851
+ 2026-07-31 20:04:18 corpus_sync: bundle peer refused: INTEGRITY FAIL: ...
```

Four passing tests appended one fabricated corruption incident to the
operator's diagnostic log.

## Root cause

`scripts/corpus_sync.py` threads a `root` parameter through every entry
point precisely so a caller can operate on a throwaway tree — but `_log`
ignored it and always wrote to the module-level `OUT = ROOT / "outputs"`.
The data writes were correctly scoped; only the *record* of them leaked.

The same shape existed in `scripts/remote_control.py`.

## Scope: measured, not guessed

Rather than grep for the pattern, I snapshotted every file under
`outputs/` (460 files, sha256), ran the full suite, and diffed. **Six
files were being mutated by the suite**, and two of them are data, not
logs:

| File | Nature | Damage |
|---|---|---|
| `retrain_history.jsonl` | **learning ledger** | **305 of 306 records were test fixtures** |
| `session_digest.json` | **run summary** | overwritten by the suite |
| `corpus_sync.log` | forensics | fabricated `INTEGRITY FAIL` since 07-18 |
| `remote_control.log` | forensics | 356 copies of "runner down", paired same-second command ids |
| `auto_update.log` | forensics | deploy-gate noise |
| `pc_supervisor.log` | forensics | supervisor noise |

`retrain_history.jsonl` is the worst of these. Every fixture row is
identical (`rows: 60, live: 60, oof_brier: 0.24193, selected: gbt,
source: cli`), so the real learning curve — one genuine record — was
buried under a 305-row flat line.

**This had already cost real work.** `scripts/learning_curve.py`'s header
comment reads *"retrain_history.jsonl is degenerate at this corpus size"*
and the script exists to work around that degeneracy. The degeneracy was
never about corpus size; the file was 99.7% test output. A prior session
correctly observed the symptom and built a whole instrument on the wrong
diagnosis.

And it cost work again today: I spent the opening of this investigation
chasing a bundle that does not exist, because a log said it was corrupt.

## Fixes

**Per-source (behavior-preserving; production defaults unchanged):**

- `scripts/corpus_sync.py` — `_log(msg, root=ROOT)`; all 5 call sites
  thread `root`.
- `scripts/remote_control.py` — same, 4 call sites.
- `scripts/auto_update.py`, `scripts/pc_supervisor.py` — log destination
  lifted to a rebindable module attribute `LOG_PATH`.
- `scripts/pc_supervisor.py::_spawn` — a spawned child's stdout log is now
  a sibling of `LOG_PATH`, not of the module-level `OUT` (this was the
  `telemetry_backup.log` leak; `telemetry_backup._log` only prints).
- `ml/monitor.py` — `RETRAIN_FLAG_PATH_DEFAULT` module attribute. Only
  fires for configs omitting `ml.monitor.retrain_flag_path`, which in
  practice means the suite's minimal governor configs; `config.json` sets
  the key, so production is untouched.
- `ml/retrain_log.py` — `RETRAIN_HISTORY_PATH_DEFAULT`, referenced through
  the module by **both** callers (`main.py`'s auto path and
  `scripts/train_meta.py`'s CLI path) so one rebind covers both. Here the
  default *is* the production path — `config.json` does not set
  `ml.retrain_history_path`.

**Structural, so this cannot recur silently** (`tests/conftest.py`):

1. `_no_production_outputs_writes` — a `sys.addaudithook` watches every
   write-mode `open`/`rename`/`unlink` and **fails the offending test by
   name**, printing the exact path. The allowlist is empty on purpose.
2. `_sidecar_logs_to_tmp` — redirects any loaded module's production path
   attribute to the test's `tmp_path`. Matched **by value, not module
   name**: the suite imports the supervisor both as `pc_supervisor` and as
   `scripts.pc_supervisor` — two distinct module objects — and a name list
   silently missed one. Owners that are imported lazily *inside* the
   function under test are force-imported first, or the scan would find
   nothing to redirect and the write would land in the real tree.

### Known limit of the guard

The audit hook is in-process: it cannot see writes by a **subprocess**.
That is not theoretical — it is why the hook reported four paths while the
snapshot diff reported six. The snapshot method is the complete
instrument; the hook is the one that names the culprit. Both were used
here, and the snapshot diff is the acceptance check.

## What was NOT done

The contaminated history in the existing logs was **not rewritten**. The
files are the operator's record and editing them retroactively is worse
than a documented contamination window. Treat any `outputs/*.log` line
before commit `b459a90` — in particular any `INTEGRITY FAIL` in
`corpus_sync.log` — as suspect, and any `retrain_history.jsonl` row with
`oof_brier: 0.24193 / rows: 60 / source: cli` as a test fixture.

The PC's copies carry the same contamination: `auto_update.py` runs the
battery before every deploy, so each 15-minute update cycle with a new
commit added another round.
