# Task 1 — verify commit 8a9cc087 "feat(labels): stop destroying outcome magnitude at write time (schema 93->94)"

Read context-common.md in this directory FIRST — it is binding.

## What shipped (verify, don't trust this summary)
`git show 8a9cc087` — labels history schema bumped 93→94, claimed to preserve outcome magnitude at write time instead of destroying it.

## Questions to answer, each with evidence
1. WHAT exactly changed: which writer, which fields, before/after semantics. Needle: `git show 8a9cc087 --stat` then the diff.
2. MAGNITUDE PRESERVED — prove by asking the runtime: construct a label row through the new write path (temp dir) and show the magnitude survives where the old code destroyed it. If a test in the commit already does this, MUTATE the fix (in a temp copy of the module, or by asserting the old behavior) and show the test goes red.
3. LEGACY COMPAT: 372 live labeled rows exist at schema ≤93 (as-of the 2026-08-27 digest). Does every consumer (retrain loop, migrate_history.py if relevant, model feature builder) handle mixed 93/94 rows without crashing or silently zero-filling? Past incident: 2026-07-11 schema 36→43 bump lost ~87 live rows via init-time rotation (write-path-only rotation fix 930c914). Check the same failure shape: does the 93→94 bump trigger any rotation/quarantine of existing rows? Needle: grep for schema-version checks in the history writer/loader.
4. MORATORIUM CLASS: does this change which orders are placed or how they fill? Labels feed the model → retrain loop continues by design (model freeze allows retrain, forbids NEW features). Is the preserved magnitude a NEW FEATURE fed to the model, or a label-quality fix on an existing column? Answer with the feature list the trainer actually reads (needle: FEATURE_NAMES or equivalent).
5. Run the covering tests: name them, run them with ./.venv/Scripts/python.exe -m pytest <files> -q, report exact pass/fail counts.

## Report path
Write full report to: C:\Users\haird\AppData\Local\Temp\claude\c--Users-haird-Documents-liquiditybot-liquiditybot-ab\cdb03d59-62a4-41ee-8c1c-00feb1307464\scratchpad\sdd\task-1-report.md
