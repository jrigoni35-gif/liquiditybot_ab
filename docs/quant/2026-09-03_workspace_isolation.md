# Isolation from any other workspace — GAP-1 closed, and a live second writer

**Date:** 2026-09-03 · **Class:** SAFE (tests + measurement only; no order
placement, sizing, geometry, fill sim, fee booking or order-lifecycle code
touched) · **Branch:** `claude/workspace-isolation-a5xr5z` · **Base:** `db7a12a4`

Two directions were measured, because "isolation" has two of them:

| direction | question | verdict |
|---|---|---|
| INBOUND | does this workspace's result depend on state accumulated in another? | **YES — and it was worse than host-state: the suite could not run AT ALL** |
| OUTBOUND | does this workspace write into another's state? | **YES — a second cloud workspace shares the `cloud-mirror` bundle label, last-writer-wins** |

---

## 0. First: the `core.worktree` redirect did NOT reproduce

OWED-VERIFY's **GAP-1** was recorded as *"FAILED, no findings. Died on a git
`core.worktree` redirect — the isolation worktree resolved to a path outside
itself."* Re-run here on a plain `git worktree add --detach`:

```
core.worktree                      (unset)
extensions.worktreeConfig          (unset)
rev-parse --show-toplevel          <WT>          # inside itself
rev-parse --git-common-dir         <repo>/.git
outputs/                           ABSENT (clean)
import main -> <WT>/main.py                      # code resolves from the worktree
```

**The redirect was the previous orchestration harness's own scratch dir, not a
repo defect.** A detached worktree is a sound isolation environment here. GAP-1
was blocked on its harness, and the finding it was meant to produce was
therefore never produced — for eight days.

---

## 1. INBOUND — the suite ran ZERO tests, in every workspace without pandas

Measured on a plain `pytest tests/` at `db7a12a4`, in BOTH the isolated
worktree and the live main tree — **identical**:

```
ERROR tests/test_kraken_trades_backfill.py
ERROR tests/test_markout_report.py
ERROR tests/test_tape_to_candles.py
!!!!!! Interrupted: 3 errors during collection !!!!!!
4541 tests collected, 3 errors        rc=2       2 skipped, 0 RUN
```

pytest aborts the **entire run** when any test module raises at import time.
So one unguarded `import pandas` does not cost that file — it costs the whole
definition-of-done matrix. `requirements.txt` pins only
`requests` / `numpy` / `defusedxml`; pandas and the rest of the analysis stack
are absent from this container.

### Why nothing flagged it — the structural half

The SessionStart hook's readiness probe is `python -c "import main"`
(`.claude/hooks/session-start.sh:30`). It printed
`dependencies already present - skipping pip` and moved on.

That probe **cannot ever detect this condition**, and the reason is a rule this
repo enforces on purpose: `tests/test_dependency_hygiene.py` forbids pandas at
engine scope, so `import main` is *guaranteed* not to touch it. The hygiene
rule and the readiness probe are each correct; jointly they guarantee the probe
is blind to the dependency whose absence bricks the battery. Re-installing from
`requirements.txt` would not have helped either — pandas is not in it.

*the-method #1, again: a confident instrument, wrong, with nothing flagging it.*

### Regression window

| when | commit | what |
|---|---|---|
| 2026-08-29 | `62d8811e` | `test_feed_freeze_gate.py` + `test_moomoo_persistence.py` guard pandas **correctly** with `pytest.importorskip` — the pattern was known and in use |
| 2026-09-01 | `e15787b3` | `test_kraken_trades_backfill.py`, `test_markout_report.py` added — **unguarded** |
| 2026-09-02 | `0593a659` | `test_tape_to_candles.py` added — **unguarded** |

Both offending commits are labelled `(SAFE)`. They were. The defect is not in
what they changed but in what their own gate could no longer measure.

### Fix — the repo's existing pattern, not a new one

`pytest.importorskip("pandas")` at module scope, **before** the import that
pulls it (directly or transitively — two of the three pull it through
`scripts/`, which is why a static import scan over the test file cannot see
them):

- `tests/test_markout_report.py` — direct `import pandas as pd`
- `tests/test_kraken_trades_backfill.py` — via `scripts/kraken_trades_backfill.py:67`
- `tests/test_tape_to_candles.py` — via `tape_to_candles` → `kraken_trades_backfill`
- `tests/test_label_decomposition_report.py` — **function-level** guard: the pandas
  import in `join_extra_csv` is lazy, so it failed at RUNTIME, not collection;
  guarded inside the one test that reaches it so the file's other pins still run

### Regression pin — property, not pattern

`tests/test_dependency_hygiene.py::test_suite_collects_without_optional_analysis_stack`
spawns `pytest --collect-only` in a child whose `PYTHONPATH` holds stub modules
that raise `ModuleNotFoundError` for all 14 unpinned optional deps. It asserts
rc==0 and names the offending files when not.

Absence is **simulated**, deliberately: on the PC the whole analysis stack IS
installed, so a real absence can never be observed there and a pin that only
worked on pandas-less boxes would protect nobody.

**Mutation-verified (positive control).** Guard removed from
`test_tape_to_candles.py` → pin FAILS, naming `ERROR tests/test_tape_to_candles.py`
and reproducing `Interrupted: 1 error during collection`. Restored → 3 passed.
The pin provably moves.

---

## 2. INBOUND — two host-dependent reds, the known "wrong OS" class

With the 3 pandas modules excluded, the isolated worktree at `db7a12a4` ran
**3 failed, 4521 passed, 17 skipped, 2 xfailed in 434.31s**. One failure was the
lazy-pandas one above. The other two:

- `test_champion_skill_report.py::test_corpus_span_survives_millisecond_epoch`
- `test_session_digest.py::test_millisecond_epoch_signal_ts_degrades_not_raises`

Both assert `corpus_last_ts is None` for a millisecond-epoch cell. The first
one's own docstring says why: *"Windows gmtime raises on a ms epoch."* On POSIX
`gmtime` formats year 58501 happily, so the value is `'58501-01-01T20:23:20Z'`,
not `None`. Same shape as the 2026-08-22 **"wrong OS, not wrong code"** finding.

Fixed by **platform split, not skip** — the blessed precedent. The invariants
that carry the defect (no raise, first stamp intact, span arithmetic still
reported, markdown still ascii-renderable) are asserted **everywhere**; only the
far-future stamp branches on `os.name`. The Windows arm is byte-identical to
what was there before, so PC behaviour is unchanged.

---

## 3. OUTBOUND — a second cloud workspace shares the `cloud-mirror` label

`sessions/cloud-mirror/` on `paper-telemetry` received **three** pushes in ten
minutes. This container's sidecar made exactly **one** of them.

```
b7511171 04:52:02Z  sidecar backup @ db7a12a4 (23429 rows, cloud-mirror)   <- NOT us
70be3a58 04:44:02Z  sidecar backup @ db7a12a4 (23429 rows, cloud-mirror)   <- us
3d69b617 04:42:43Z  sidecar backup @ 11b27e36 (23429 rows, cloud-mirror)   <- NOT us
```

Verified two independent ways:

1. **Process/log accounting.** Exactly one `telemetry_backup.py` here (PID 1772,
   started 04:43:59). Its loop is `_log(backup_once()); sleep(1800)` — *every*
   push is logged. The log holds one push, 04:44:03; the next is not due until
   ~05:14. At 05:02:53 the branch already had three.
2. **Stamp provenance.** The 04:42:43 bundle is stamped `@ 11b27e36`. This
   container's HEAD has been `db7a12a4` since before its sidecar started, and the
   sidecar stamps `HEAD`. No process here could have written that bundle.

All three commit as `Claude <noreply@anthropic.com>`; the PC commits as
`jrigoni35-gif` under the separate `pc-live` label. So the co-writer is **another
cloud session**, not the PC.

### Why this is the exact hazard the label separation was created to prevent

`telemetry_backup.py`'s own docstring: *"LAST-WRITER-WINS on the bundle."* The
`cloud-mirror` / `pc-live` split exists because of the 2026-07-18 incident where a
mirror *"shadowed the real corpus with a stale copy stamped fresh, hiding a
639-row durability gap"*. That split separates **cloud from PC**. It does not
separate **cloud from cloud** — every cloud container hardcodes the same default
label (`session-start.sh:182`, `LB_BACKUP_LABEL:-cloud-mirror`).

And the traffic is not one-way. This session's own SessionStart log records it
**adopting** the other workspace's artifacts at boot:

```
bundle 'cloud-mirror' created 2026-09-03T04:42:40Z @ git 11b27e363f1e
  meta_model.json adopted + registered locally (1ee3ae68c0df)
  skimmer_active.json adopted (promotions apply at next boot)
```

A model and a skimmer config from another ephemeral workspace, adopted here.

**No row damage today** — both bundles are 23,429-row reconstructions of the same
imported corpus, and the row merge is an append-only union deduped by
`position_id`. The exposure is structural, and the repo has already paid for it
once: `tests/test_telemetry_backup.py:288` documents the 2026-07-27 *"cloud-mirror
corruption"*, an internally-inconsistent bundle *"every future restore refuses"*,
caused by two writes landing in the same wall-clock second.

### NOT fixed here — deliberately

Making the label unique per workspace changes what lands on the shared branch and
what the PC imports. That is a cross-machine data-plane decision with another live
session on the other end of it, so it is **registered, not executed**. Options, in
increasing order of blast radius: leave it (accept last-writer-wins between cloud
containers); suffix the label per container; or set `LB_BACKUP_DISABLED=1` in
dev-bench containers whose `outputs/` is a pure reconstruction and whose bundle
therefore adds nothing the PC does not already have.

---

## 4. Result — and what this workspace's green actually is

Isolated worktree, `LB_OUTPUTS` unset, no `outputs/`, code resolving from the
worktree, all fixes applied:

```
4524 passed, 21 skipped, 2 xfailed in 436.09s (0:07:16)      rc=0
```

**Zero failures, zero collection errors.** Reconciles exactly against the
pre-fix baseline (`3 failed, 4521 passed, 17 skipped, 2 xfailed`, with the three
pandas modules `--ignore`d):

| delta | why |
|---|---|
| passed 4521 → 4524 | +2 the platform-split tests now pass on POSIX, +1 the new collectability pin |
| failed 3 → 0 | 2 platform-split, 1 became a function-level pandas skip |
| skipped 17 → 21 | +1 function-level pandas skip, +3 module-level skips for the files that were `--ignore`d in the baseline |

### Read the skip count carefully — 21 is not 21 tests

A module-level `importorskip` skips the **module during collection**, so it
reports as **ONE** skip entry, not one per test. The 4 new skip entries stand for
**51 tests** actually not run here (10 + 26 + 14 module-level, + 1
function-level), on top of 9 pre-existing pandas-gated tests in
`test_moomoo_persistence.py` / `test_feed_freeze_gate.py`.

**So this workspace's green is smaller than the PC's — by ~51 tests — and that
is now VISIBLE rather than silent.** Before this change those tests did not
skip; they took all 4,541 down with them. A green here is not a green there, and
the DoD matrix run on a pandas-less container should be read as the degraded
form. *(CLAUDE.md: "A GREEN IS ONLY AS BIG AS ITS CORPUS.")*

### Rest of the DoD matrix, this container, same tree

| gate | result | corpus / note |
|---|---|---|
| `pytest tests/` (isolated worktree) | **4524 passed, 21 skipped, 2 xfailed, rc=0** | 436.09s |
| `smoke_test.py` | **220 passed, 0 failed** | rc=0 |
| `assurance_check.py` | **50 passed, 1 FAILED** | pre-existing, see below |
| `overfit_check.py` | **passed 3, failed 0** (48 informational) | **corpus: live history 13,042 rows** — real market, NOT the planted-signal synthetic (floor 640) |
| `ruff` (CLAUDE.md scope) | clean | rc=0 |
| `pyright` (shipped scope) | **0 errors, 0 warnings, 0 informations** | ratchet held |
| `bandit -x ./.venv,./tests` | **0 issues** | rc=0, re-derived without a pipe |
| `compileall` | clean | rc=0 |

*(Method note against my own work: the first `bandit` and the first isolated
pytest run both had their `$?` read through a `| tail`, which returns the
FILTER's status — CLAUDE.md reading-discipline 7(d). The first such run reported
"exit code 0" for a pytest that had actually exited **2**. Both were re-derived
writing rc to a file. The trap is live in this repo's own tooling habits.)*

**Pre-existing red, NOT mine, NOT fixed:** `scripts/assurance_check.py` reports
`FAIL every --self-test has a negative arm and reports a rate ->
null-arm-only self-tests: rpe_factor.py`. Reproduced on a **pristine detached
checkout of `db7a12a4`** with no modifications: `49 passed, 1 failed`. (The main
tree reads `50 passed, 1 failed`; the one-check delta is the corpus section going
VACUOUS in a bare worktree — exactly the documented behaviour, and an incidental
confirmation that the mechanism still works.) `rpe_factor.py` arrived in
`62d8811e` (2026-08-29). Registered, not silently absorbed into this change.
