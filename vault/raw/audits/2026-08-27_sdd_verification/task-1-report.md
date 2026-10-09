# Task 1 verification report — commit 8a9cc087 "feat(labels): stop destroying outcome magnitude at write time (schema 93->94)"

Repo: c:\Users\haird\Documents\liquiditybot\liquiditybot_ab, HEAD 5e785c16 (branch claude/claude-rc-f3heik == origin/main). Tree clean, read-only throughout — no edits/commits/checkouts made to the tracked tree. All mutation/injection experiments ran against in-memory monkeypatches or scratch temp files under `C:\Users\haird\AppData\Local\Temp\claude\...\scratchpad\`.

## STATUS: DEFECT_FOUND (narrow — documentation/provenance only, not functional)

Every functional claim in the commit (magnitude preservation, UNKNOWN convention, legacy-schema compat, rotation safety, moratorium classification) was independently verified clean via non-static routes (mutation, injection, ask-the-runtime, live production-log corroboration). The one confirmed defect is in the commit message itself: its self-reported "Verification" tallies are inaccurate (both off by exactly +1), and one of the six/seven named test-files it claims to have updated was never touched. Per this repo's own CLAUDE.md ("Never ship a claim you have not run. Commit messages, docstrings and comments are claims. A false one there outlives the code."), a false verification claim in a permanent commit message is itself a defect, even though it does not affect runtime behavior.

---

## Q1 — WHAT exactly changed

Needle: `git show 8a9cc087 --stat` then `git diff 8a9cc087~1 8a9cc087 -- <file>` per file. [K] read directly.

9 files, 396 insertions / 17 deletions:

- **ml/history.py** (+58/-2, the core change):
  - `_N_TRAIL` grows by `+1` (line ~113) to account for the new trailing column.
  - `HistoryStore._append_row` gains `label_ret_pct: float | None = None` kwarg (line ~968); written as `f"{float(label_ret_pct):.6f}"` if `label_ret_pct is not None and np.isfinite(float(label_ret_pct))`, else `""` (lines ~146-148).
  - `HistoryStore.log_close` (live rows, line ~1148): computes `_ret_pct = net_pnl_usd / entry_usd * 100.0 if entry_usd and entry_usd > 0 else None` — percent, net of BOOKED fees; guarded to `None` (→ "") when `entry_usd` is the pre-upgrade 0.0 default.
  - `CandidateLabeler._emit_label` (line ~2611): now passes `label_ret_pct=getattr(out, "ret_pct", None)` — the labeler's own `BarrierOutcome.ret_pct`, written verbatim. `net_pnl_usd` for candidates stays the honest literal `0.0` (dollars genuinely unknown for a candidate) — unchanged; only the new column carries the real-valued return.
  - Header list gains `"label_ret_pct"` appended LAST after `AVAIL_COLS` (both in `_header` construction and the row-write order) — append-at-end discipline preserves positional compatibility for every consumer keyed to the OLD tail.
- **scripts/migrate_history.py** (+10/-1): `migrate_rows` appends `r.get("label_ret_pct") or ""` — passes a migrated row's real value through unchanged; pads `""` (never `"0"`) for rows that predate the column.
- **scripts/ledger_continuity.py** (+42/-3): adds a "ghost position" check — cross-references `fills.csv` (entry+exit purpose rows) against `signal_history.csv` position_ids; a position closed >48h with both an entry and exit fill but no corpus row under any source is reported (never repaired — report-only, same class as the rest of the file).
- **tests/test_label_ret_persistence.py**: new file, 252 lines, 12 test functions (see Q5).
- **tests/test_availability_wiring.py, test_book_tag.py, test_data_contracts.py, test_history_migration.py, test_sample_weights.py**: existing header/row-width assertions updated from hardcoded `h[-4:]` / `header[-4:]` slices (avail cols were the old tail) to `h[-1] == "label_ret_pct"` + `h[-5:-1] == [avail cols]` (new tail is one column later). Mechanical, matches the stated "append-at-end" discipline.

## Q2 — MAGNITUDE PRESERVED (ask-the-runtime + independent mutation)

Method: rule 2 in context-common.md (MUTATION preferred over trusting the shipped test). I did **not** just run the shipped pin — I wrote an independent script (`scratchpad/mutation_test_8a9cc087.py`) that:
1. Imports the REAL `CandidateLabeler._emit_label` from the tracked `ml/history.py` (unmodified on disk) and runs it through a real `HistoryStore` in a temp dir with `BarrierOutcome(1, -0.83, 12, "tb_time")` → confirms `label_ret_pct == "-0.830000"` written to the CSV. [K] measured.
2. Re-plants the **exact historical defect** described in the commit (`getattr(out, "ret", None)` instead of `getattr(out, "ret_pct", None)`) via `inspect.getsource` + string substitution + `exec()` into a fresh bound method (in-memory only, tracked file never touched), and re-runs the same scenario → confirms `label_ret_pct == ""` (UNKNOWN) — the defect reproduces exactly as described.

Output (verbatim):
```
[REAL/current (ret_pct)] PASS (assertion held): label_ret_pct='-0.830000'
[MUTATED (re-planted ret defect)] FAIL (assertion RED): ... got label_ret_pct=''
current code assertion held (magnitude preserved): True
mutated/defect code assertion held: False (expect False = went RED)
RESULT: MUTATION KILLED CLEANLY.
```
Also independently confirmed `ml/labeling.py:BarrierOutcome` has a field named `ret_pct` and **no** field named `ret` (`class BarrierOutcome` dataclass, line 56-65 read directly) — so `getattr(out, "ret", None)` is provably always `None`, corroborating the commit's claim about its own first-cut bug.

Conclusion: magnitude preservation is real, independently re-derived by a route the commit did not author. [K] measured via mutation, not read from the commit's own test.

## Q3 — LEGACY COMPAT (mixed 93/94 rows)

Needle for schema-version checks: `_ensure_schema` in `ml/history.py` (line 874-911). [K] read.

**Rotation-hazard shape check (2026-07-11 recurrence risk):** `_ensure_schema` is called from `_append_row` (WRITE PATH) — never from `__init__` or any read path — confirmed by direct code read of both `_ensure_schema`'s own docstring (explicitly documents the July incident and the 930c914 fix) and `_append_row`'s call site. This means merely *constructing* a `HistoryStore` (as `load_training_data`, `overfit_check.py`, or any read-only QA script does) cannot trigger a rotation as a side effect — the specific failure shape from 2026-07-11 does not recur here. [K] read + corroborated by design comment.

**Production corpus, snapshot-stamped:** `outputs/signal_history.csv`, read at **2026-08-27T21:35:47Z** (local shell clock) via `ls -la` + `date -u`, size 14.0M — read in streaming (csv.reader row-by-row), never loaded whole per USAGE.md rule 6. Independently re-derived (script `scratchpad/check_schema_mix.py`), double route (row-width distribution + per-row label_ret_pct blank/non-blank):
- header width = 94 cols; **every one of 18,453 data rows is already width-94** (`{94: 18453}`) — the corpus has already been through one live rotation+recovery cycle since the bump (930c914-style write-path rotation, not a read-path sweep).
- 372 rows with `source == "live"` total — **matches the brief's stated 372 exactly**, independently re-derived (not taken on trust) [K] measured.
- of those 372: 361 have `label_ret_pct == ""` (pre-bump legacy rows, padded UNKNOWN by the rotation/migration path, never a fabricated value); 11 carry a real numeric value (written live since the bump went live 2026-08-24).

**Direct runtime test on a genuinely mixed-width file (not the shipped rotation test — a separate scenario I constructed):** `scratchpad/mixed_schema_load_test.py` writes a corpus file with a 94-col header but 3 rows at 93-col width (straggler legacy shape, bypassing the rotation/recovery path entirely) interleaved with 3 rows at 94-col width, then calls `HistoryStore.load_training_data()` directly.
```
load_training_data() OK: X.shape=(6, 64), y.shape=(6,), w.shape=(6,)
last_load_stats: rows=6, live_clean=6
PASS: no crash, all 6 mixed-width rows loaded, feature matrix width correct.
```
Root cause confirmed by code read: the loader parses via `csv.DictReader` keyed by column **name** (`row[n] for n in FEATURE_NAMES`, `row["label"]`) — never positional/width-based — and never reads `label_ret_pct` at all. A short (93-col) row simply gets `None` for the DictReader's `label_ret_pct` key (Python stdlib default `restval=None`), which nothing reads. No crash, no silent zero-fill of features or labels observed under mutation.

**Migration path:** `scripts/migrate_history.py`'s `r.get("label_ret_pct") or ""` — `.get()` on a `DictReader` row missing the key returns `None` → `""`, never crashes, never fabricates `0`.

**Live corroboration the ghost-position half of this commit is actually running in production**, not just tested: `outputs/ledger_continuity.jsonl`, snapshot-stamped — 98 lines total, last entry `read_at: "2026-08-27T16:09:57"` (local time; file mtime **2026-08-27T21:09:57Z** UTC, consistent with the repo's UTC-5 commit-author offset — the two clocks reconcile). The last several hourly entries (09:09 through 16:09 local) all read `"ghost_positions": 3` — stable, matching the commit's own claim ("First live run found 3 more from the same incident window... Historical and bounded"). This is corroboration by a second, independent route (the live production log), not just the shipped unit test. [K] measured, snapshot-stamped.

Conclusion: legacy 93-row / 94-row mixing does not crash any inspected consumer and does not silently zero-fill; the specific 2026-07-11 rotation-hazard shape (read-path-triggered rotation) is structurally absent from this code.

## Q4 — MORATORIUM CLASS: SAFE (confirmed, not just asserted)

- `'label_ret_pct' in ml.features.FEATURE_NAMES` → **False** (measured via `./.venv/Scripts/python.exe -c "..."`, `len(FEATURE_NAMES) == 64`). [K] measured directly against the runtime, not grepped.
- Feature extraction in `load_training_data` is an explicit named list (`[float(row[n]) for n in FEATURE_NAMES]`) — grepped for any wildcard/dynamic column enumeration pattern (`META_COLS`, `reader.fieldnames`, `row.keys()`) in `ml/history.py`: **no matches**. There is no code path by which `label_ret_pct` could leak into the trained feature matrix `X` short of a future, separate, conscious change.
- Full-repo grep for `label_ret_pct`: appears only in `ml/history.py`, `scripts/migrate_history.py`, the 6 modified/new test files, and `docs/quant/2026-08-25_boundary5_adjudication.md` — no trainer file (`ml/train*.py`), no `main.py`/`runner.py`, reads it.
- `scripts/ledger_continuity.py`'s ghost-position check: confirmed report-only by its own code (`res` dict returned, nothing written back to fills/corpus) and by its caller — `scripts/pc_supervisor.py` (line ~835) spawns it as a **subprocess** (`_spawn([PY, "scripts/ledger_continuity.py"], ...)`), with the adjacent comment explicitly stating "Report-only: appends one verdict line to outputs/ledger_continuity.jsonl, repairs nothing." Not referenced anywhere in `main.py` or `runner.py` (the engine/runner decision path) — confirmed by grep (5 hits total, all scripts/tests, zero in engine files).
- `docs/quant/2026-08-25_boundary5_adjudication.md` (a separate, later, **STAGED — NOT APPLIED** doc, dated the day after this commit) states explicitly: "rows since [2026-08-24] carry `label_ret_pct` and CAN be repriced" — i.e. its intended future use is **relabeling** (recomputing the win/loss sign `y` at a corrected cost constant), not adding a new model input `X` feature. This is consistent with the "bookkeeping, not feature" framing and satisfies the no-orphan-claims check (a dated downstream reference corroborates the claim rather than leaving it unsupported).
- No change touches `net_pnl_usd` (dollars, used for real accounting), entry decisioning, sizing, stop/exit geometry, the fill simulator, fee booking, or order lifecycle — confirmed by direct diff read (Q1); the only new write is an additional column computed FROM already-existing values (`out.ret_pct`, `net_pnl_usd/entry_usd`), never fed back into any decision path.

Conclusion: SAFE class as shipped, not merely as claimed. Era-4 cohort not reset by this change.

## Q5 — Covering tests, exact counts

Interpreter: `./.venv/Scripts/python.exe` per context-common.md. Ran each file individually, then combined:

| file | result |
|---|---|
| tests/test_label_ret_persistence.py | 12 passed |
| tests/test_availability_wiring.py | 9 passed |
| tests/test_book_tag.py | 13 passed |
| tests/test_data_contracts.py | 8 passed |
| tests/test_history_migration.py | 4 passed |
| tests/test_sample_weights.py | 15 passed |
| tests/test_migrate_history.py | 7 passed |
| tests/test_ledger_continuity.py | 9 passed |
| **combined single run (all 8 files)** | **77 passed, 0 failed, 0 skipped** (3.73s) |

Command used (needle): `./.venv/Scripts/python.exe -m pytest tests/test_label_ret_persistence.py tests/test_availability_wiring.py tests/test_book_tag.py tests/test_data_contracts.py tests/test_history_migration.py tests/test_sample_weights.py tests/test_migrate_history.py tests/test_ledger_continuity.py -q`

Additional spot-checks against the commit's DoD claims, run directly (not trusted from the message):
- `ruff check ml/history.py scripts/ledger_continuity.py scripts/migrate_history.py` → **All checks passed!** [K]
- `pyright ml/history.py` → **0 errors, 0 warnings, 0 informations** [K]

**Not reproduced (explicitly out of scope for this task per brief's "covering tests" ask, noted rather than silently skipped):** the commit's whole-suite claim "4031 passed / 9 skipped / 0 failed" as of 8a9cc087 itself. Current HEAD (5e785c16, several commits later) collects **4056 tests** via `pytest tests/ -q --collect-only` (not executed) — order-of-magnitude consistent with a handful of intervening commits adding tests, but this is a plausibility check only, not a reproduction of the commit's own number.

## DEFECT — commit message verification-count inaccuracy (confirmed, double-derived)

The commit's own "Verification" block makes two self-reported tallies; both are wrong, both off by exactly +1 in the same direction:

**(a) "13 new pins"** — actual: `tests/test_label_ret_persistence.py` has **12** test functions, confirmed two ways: (i) direct enumeration by reading the file (listed in Q5 area above / in the file itself), (ii) `pytest -q` on that file alone reports "**12 passed**", not 13.

**(b) "Seven pre-existing schema-contract pins went red and were updated - ... test_data_contracts, test_availability_wiring, test_book_tag x2, test_sample_weights, test_history_migration, test_migrate_history"** — this names 7 pin-slots (1+1+2+1+1+1) across 6 distinct files. Actual: `git show 8a9cc087 --stat` and `git diff 8a9cc087~1 8a9cc087 -- <file>` show only **5** other test files touched: `test_availability_wiring.py`, `test_book_tag.py` (2 assertions), `test_data_contracts.py`, `test_history_migration.py`, `test_sample_weights.py`. **`tests/test_migrate_history.py` has zero diff in this commit** — confirmed by `git diff 8a9cc087~1 8a9cc087 -- tests/test_migrate_history.py` (empty) and by `git log --oneline -- tests/test_migrate_history.py` (last touched by an unrelated prior commit, `3c0debd7`). Read the file's own assertions to rule out a false negative: none of its 7 test functions hardcode header width or trailing-column position — they use `store._header.index("label_era")` (dynamic) and set-comparisons over `FEATURE_NAMES` (unrelated to the meta-column tail) — so a trailing-column schema bump structurally **cannot** make this file's tests fail. It could not have "gone red."

Most likely explanation: name confusion between `tests/test_history_migration.py` (which genuinely was updated — 1 assertion) and the near-identically-named `tests/test_migrate_history.py` (which was not touched at all), causing both the file-count and the pin-count to overstate by one. This is exactly the class of near-identical-name confusion this repo's own CLAUDE.md flags as a recurring hazard ("Whiplash + audit pollution", "History schema-loss incident" in MEMORY.md are unrelated instances of the same *shape*: confident claims about which artifact did what).

**Scope of this defect:** narrow. It is a false claim in a permanent artifact (the commit message), not a functional or runtime defect — every actual behavior claim in the commit (magnitude preservation, UNKNOWN convention, legacy-row handling, rotation safety, moratorium classification) was independently verified clean above via mutation, injection, and live-log corroboration. Per this repo's own law ("Never ship a claim you have not run... A false one there outlives the code"), it is still a defect worth recording, since the commit message will be read by future sessions as settled provenance.

## What this verification could not see

- Did not re-derive the commit's *historical* prose numbers (5,923/5,945 rows destroyed; 218 tb_time wins; 26/42 live wins flipping; the x1.979 fee-understatement figure) — those describe a pre-fix corpus state that has since been migrated forward and is no longer reconstructable from the current production file. Treated as [I] inferred/stated-by-commit, not independently re-measured; flagging rather than silently trusting.
- Did not execute the full 4056-test suite, `scripts/smoke_test.py`, `scripts/assurance_check.py`, `scripts/overfit_check.py`, or `bandit` — out of scope for "covering tests" per the brief; the ruff/pyright spot-checks above are the only DoD-adjacent checks I ran myself.
- Did not attempt to reproduce the live `corpus_sync.recover_local_baks` 6/6-row rotation pin myself beyond running the shipped test (`test_old_schema_file_rotates_and_recovers_without_row_loss`, part of the 12/12 passing count) — I built a *different* mixed-width scenario myself (Q3) rather than re-running the identical shipped fixture, to get a genuinely independent check rather than re-executing the author's own test.
