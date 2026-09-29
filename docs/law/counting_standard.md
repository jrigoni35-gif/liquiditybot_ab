# Counting standard — CS-1 (operator request, 2026-09-28)

**Why this exists.** Five readers (`scripts/era_readout.py`, `scripts/cohort_eval.py`,
`scripts/discard_ledger.py`, `scripts/gate_ecology.py`, `core/session_digest.py`) each
reconstructed trips and attributed them with their own rules. When cohorts moved from
the hand-minted `EXEC_ERA` to decision fingerprints (cut #13), one reader was updated
and four silently kept pooling forked trips into "era-9" — found by adversarial review,
not by any test. A rule that lives in five places changes in one. This standard puts the
rules in one place and makes every count prove it lost nothing.

## 1. Units — say which one you are counting

| unit | source | one of it is |
|---|---|---|
| **leg** | `outputs/fills.csv` | one row (one fill) |
| **trip** | `outputs/fills.csv` | all legs sharing a `position_id` |
| **label row** | `outputs/signal_history.csv` | one row |
| **event** | `outputs/audit.jsonl` | one record **on the main hash chain** (`core.audit.read_main_chain`) |

A number without its unit is not reported. "70" is not a count; "70 closed trips" is.

## 2. Attribution rules — implemented ONCE, in `core/cohort.py`

| question | rule | function |
|---|---|---|
| a leg's decision cohort | its own `decision_fp` stamp; blank/absent = `legacy` | `cohort_of` |
| a trip's decision cohort | its **ENTRY** (earliest) leg's stamp — a trip opened under cohort A and closed by cohort B's process is A's | `cohort_of(entry_leg["decision_fp"])` |
| a label row's / event's cohort | no stamp of its own: the cohort whose process was running at its timestamp, from `CG-000` boot records on the **main chain only** | `fp_timeline` + `fp_at` |
| the running cohort | `status.json` `decision_fp`, **as-of the read**; `""` = unknown, never guessed | `running_fp` |
| pooling two cohorts | only via an evidenced entry in `docs/law/cohort_equivalence.json` | `load_equivalence` + `canonical` |
| a trip's era | stamp purity over **all** legs (a straddler belongs to no era) | per registration |
| a trip's book | `long` if ANY leg says `long`, else `5m` | per reader, same rule |

**No reader re-implements a row in this table.** A file that reads `decision_fp` must use
`core.cohort` to interpret it (pinned: `test_every_decision_fp_reader_uses_core_cohort`).

## 3. Reconciliation — every count proves it dropped nothing

A report that classifies a population into buckets calls `core.cohort.reconcile(n, buckets)`
and prints its line: `counting CS-1: n=<N> = <bucket>=<k> + ... [OK|MISMATCH]`. Buckets are
exhaustive and named (e.g. member / straddler / unstamped / partial / open / excluded-with-
reason). A MISMATCH is printed, never raised: a report must still render, and the mismatch
is the finding.

## 4. Selection is NOT governed here

Pre-registered populations keep their own predicates — the era-4 population in
`cohort_eval.era4_trips`, the registered era read in `era_readout` (stamp-pure, 5m book,
hedges excluded, size-tolerance). Changing which trips a registration selects after it
accrues is what pre-registration forbids. CS-1 governs **attribution and reconciliation
only**: given a selected population, how it is labelled and proven complete.

## 5. Versioning

Reports state `counting CS-1`. A change to §1–§3 bumps the version here and in
`core.cohort.COUNTING_STANDARD`, in the same commit, so two numbers are comparable iff they
carry the same version.

## Conformance (2026-09-28)

| reader | cohort attribution | reconciliation line |
|---|---|---|
| `scripts/era_readout.py` | entry leg via `core.cohort` | yes |
| `scripts/cohort_eval.py` | entry leg via `core.cohort` | yes (homogeneity buckets) |
| `scripts/discard_ledger.py` | entry leg via `core.cohort` | yes |
| `scripts/gate_ecology.py` §5 | leg stamps, pooled ON PURPOSE (exposure is the book) — disclosed as `decision_cohorts_pooled` | n/a (not a classification) |
| `core/session_digest.py` | label rows via timeline; legs via stamp | n/a (counts per key) |
