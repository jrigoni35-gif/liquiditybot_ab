# Isolation from any other workspace — GAP-1 closed, and a live second writer

**Date:** 2026-09-03 · **Class:** SAFE (tests + measurement only; no order
placement, sizing, geometry, fill sim, fee booking or order-lifecycle code
touched) · **Branch:** `claude/workspace-isolation-a5xr5z` · **Base:** `db7a12a4`

Two directions were measured, because "isolation" has two of them:

| direction | question | verdict |
|---|---|---|
| INBOUND | does this workspace's result depend on state accumulated in another? | **YES — and it was worse than host-state: the suite could not run AT ALL** |
| OUTBOUND | does this workspace write into another's state? | **YES — a second cloud workspace shared the `cloud-mirror` bundle label, last-writer-wins. FIXED: the sidecar now follows the runner flag, and opted-in boxes get a per-container label** |

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

### FIXED 2026-09-03 (second pass, on operator "fix this")

The remedy is not a bigger label — it is **one writer per bundle label**, plus
deleting the writer that had nothing to write.

The sidecar exists to protect rows *this box generated*. Since the 2026-07-17
one-bot directive the cloud launches no runner, so it generates **none**.
Measured this session, three ways agreeing: the local corpus, the `pc-live`
bundle and the `cloud-mirror` bundle are **all exactly 23,586 rows**, and the
`pc-live` import reports `0 new, 23586 duplicate`. The mirror carried **zero
rows the PC lacked** — it was re-exporting the PC's own corpus back to the
branch under a second name. It bought no durability and cost isolation.

`.claude/hooks/session-start.sh` §6 now gates the sidecar on the same flag as
the runner it exists to protect:

| condition | behaviour |
|---|---|
| default (one-bot, no cloud runner) | **retired — no push at all** |
| `LB_CLOUD_RUNNER=1` or `LB_BACKUP_FORCE=1` | launches under a **per-container** label |
| `LB_BACKUP_DISABLED=1` | off, as before |
| sidecar already alive | left alone, no double launch |

The per-container label is `cloud-<8 hex>`, persisted at
`~/.liquiditybot/backup-label` — outside the repo and outside the bundle
allow-list, so it survives a container PAUSE and stays *one label per box*. An
unreadable id file falls back to `cloud-$$` rather than silently becoming the
old shared constant. This matters because `hostname` is **`vm`** in every one
of these containers: there was no natural discriminator, which is a large part
of why N writers stayed invisible.

Pinned by `tests/test_session_start_hook.py` (7 pins), which executes the
**real** block out of the shipped hook under stubbed `log`/`pgrep`/`setsid`
rather than a copy. **Mutation-verified**: restoring the old unconditional
launch turns all 7 red; restoring the fix turns them green, hook byte-identical.

**Immediate remediation:** this container's live sidecar (PID 1437, last push
13:04:35Z) was stopped, so it no longer writes to the shared branch. The hook
change only takes effect at another container's next boot — **the other
workspace is still pushing `cloud-mirror` until it restarts and picks this up**
(it was at `11b27e36` as recently as 13:00:05Z). That is expected, not a
residual defect; the existing `sessions/cloud-mirror/` directory is left in
place and de-prioritises itself naturally, because bundles are imported
newest-first by `created_at_utc` and a frozen one stops advancing.

### A contamination I caused, and cleaned

Writing that pin, an early version ran the hook block with the **repo root as
cwd**, so the block's own `>> outputs/telemetry_backup.log` appended **8
fabricated `LAUNCH:` lines to the operator's real forensics log** — precisely
the 2026-07-31 test-suite-contamination class this repo already has a
postmortem for. Caught by reading the file rather than by any guard
(`conftest`'s `_no_production_outputs_writes` watches module-level path
constants, not a child process's shell redirect).

Handled per the standing rule — **quarantine, not delete**: the contaminated
file is preserved as
`outputs/telemetry_backup.log.CONTAMINATED-by-test-20260903T131000Z` and the
live log restored to its 7 genuine records. Every injected line contained
`/bin/echo`, which the real sidecar never writes, so they were unambiguously
separable. Blast radius was this container only: `telemetry_backup.log` is
**not** in `session_export.py`'s bundle allow-list, so it had no route to the
shared branch. The pin now runs with `cwd=tmp_path`, which also gave it a
*better* observable — the redirect target is the only real evidence a launch
happened, since the launch line sends the child's stdout straight into it.

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
| `pytest tests/` (isolated worktree, §1-2 fixes) | **4524 passed, 21 skipped, 2 xfailed, rc=0** | 436.09s |
| `pytest tests/` (final, all fixes incl. §3+§5) | **4535 passed, 21 skipped, 2 xfailed, rc=0** | 655.12s; +7 hook pins +4 contract pins |
| `smoke_test.py` | **220 passed, 0 failed** | rc=0 |
| `assurance_check.py` | **51 passed, 0 failed** | was 50/1; the 1 was a MISDIAGNOSIS, see §5 |
| `overfit_check.py` | **passed 3, failed 0** (48 informational) | **corpus: live history 13,199 rows** — real market, NOT the planted-signal synthetic (floor 640) |
| `ruff` (CLAUDE.md scope) | clean | rc=0 |
| `pyright` (shipped scope) | **0 errors, 0 warnings, 0 informations** | ratchet held |
| `bandit -x ./.venv,./tests` | **0 issues** | rc=0, re-derived without a pipe |
| `compileall` | clean | rc=0 |

*(Method note against my own work: the first `bandit` and the first isolated
pytest run both had their `$?` read through a `| tail`, which returns the
FILTER's status — CLAUDE.md reading-discipline 7(d). The first such run reported
"exit code 0" for a pytest that had actually exited **2**. Both were re-derived
writing rc to a file. The trap is live in this repo's own tooling habits.)*

---

## 5. ISO-2 — I reported this wrong, and the correction is the finding

**What I said first (WRONG):** *"`scripts/rpe_factor.py`'s `--self-test` has
only a null arm."* I took `assurance_check`'s own words for it:

```
FAIL  every --self-test has a negative arm and reports a rate
      null-arm-only self-tests: rpe_factor.py
```

**What is actually true.** `rpe_factor.py` carries a power arm *in its own
source* — it prints `POWER ARM planted over-claim -> recovered ... (1/1
recovered)` and checks the recovered MAGNITUDE against an analytically
computable planted value, not merely the sign. It is one of the better
self-tests in the repo. Run it and you get:

```
$ python scripts/rpe_factor.py --self-test
ModuleNotFoundError: No module named 'pandas'          rc=1
```

`check_self_tests` required `returncode == 0`, so on any box without the
optional analysis stack the self-test **never ran** — and the clause then
printed a confident, specific and false diagnosis of an instrument that is
fine. **A third instance of the same pandas absence, wearing a completely
different mask.**

This is CLAUDE.md mindset rule 3 verbatim — *"'0 findings' and 'the scan is
broken' are the SAME OBSERVATION until separated"* — and the rule was already
written down **in the same function's own file**: `assurance_check`'s C1 branch
forty lines earlier says *"TOOL UNAVAILABLE IS NOT A FINDING about the incoming
code. Treating it as one is how the replay gate bricked deploys
(2026-07-21/22)."* The C2 clause simply never got the same treatment. And I
repeated the error one level up by relaying the label instead of running the
instrument — rule 4: *confident tone is not provenance.*

### Fixed, without weakening the gate

`check_self_tests` now separates **UNVERIFIED** from **WEAK**: an exit caused by
an absent THIRD-PARTY module is recorded as `could_not_run` and excluded from
the verdict; the clause reports it by name so the degraded form cannot read as
a clean pass. A missing **repo** module stays a hard failure — that asymmetry is
the whole point, and it is the same rule `test_import_integrity` already applies.

```
ok    every --self-test has a negative arm and reports a rate
      self-tests UNVERIFIED, could not run: rpe_factor.py (no pandas)
      (advisory, not a finding - their power is UNPROVEN here, not disproven)

51 passed, 0 failed        (was 50 passed, 1 failed)
```

**Mutation-verified in BOTH directions** — the gate keeps its teeth:

| injected probe | verdict | meaning |
|---|---|---|
| self-test that RUNS with no negative arm | **50 passed, 1 failed** | still caught |
| self-test dying on a missing **repo** module | **50 passed, 1 failed** | not excused |
| absent **third-party** dep | reported UNVERIFIED, clause green | the fix |
| real power arm | passes | no false positive |

Pinned by 4 new cases in `tests/test_instrument_contract.py` (17 passed).

**So ISO-2 as originally written is withdrawn.** There was never a null-arm
self-test; there was an instrument that could not run and said something else.
