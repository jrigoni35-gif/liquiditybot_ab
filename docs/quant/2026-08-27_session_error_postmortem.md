# Session error postmortem — why the misreads happened, and what shipped
**2026-08-27 · operator directive: "narrow down why you are making these
mistakes and implement fixes" · SAFE-class (labels, hooks, docs, tests)**

Census: seven misreads in one session, all caught by adversarial review
or self-check, none reaching a decision path. Full dockets live in the
session record; this file is the root-cause narrowing and the fix
ledger.

## The five failure shapes (every misread is one of these)

| # | shape | instances (same day) |
|---|---|---|
| 1 | **Secondary-source read** — quoting a derived field without opening the authority it summarizes | `signed_continue_n` read as "accrual continues to n=100" when the signed table's fired arm is 2D; HANDOFF "best on record 0.0138" repeated, then "corrected" wrongly |
| 2 | **Denominator/netting blindness** — using a statistic without reading how it is computed | digest `spoofy_frac` (non-liquid-only denominator) ranked as risk #1; "fees 1.7x realized" from a post-close-fee accumulator vs both-legs fees; bandit confidence rollup read as severity |
| 3 | **Cross-era comparison** — treating a ledger with a schema change + corpus reset as one series | calib-gap "best 0.0082" was family `blend` on the pre-reset corpus; in-family best is 0.0129 |
| 4 | **Exit-code/pipe hygiene** — a filter's rc mistaken for the tool's; implausible runtime unquestioned | `pytest \| tail` reported rc=0 on a collection failure; "2 errors in 5.22s" briefly accepted for a 4,000-test suite |
| 5 | **Asymmetric standards** — deflation applied to the doubted claim, not the liked one | net-per-trip negativity called "measured" at t≈−0.29 while gross at t≈0.96 was called unresolved |

## The narrowing — why THIS codebase produces these

1. **Derived-lens density.** This repo wraps its primaries in an
   unusual number of cheap lenses (digest headlines, pc_status fields,
   HANDOFF as-of rows). Cheap reads are the rational first move — and
   every shape-1/2 failure is a cheap read treated as an authority.
   The lenses themselves were mislabeled in three places (spoofy
   denominator, realized netting, digest header) — fixed below.
2. **The CLAUDE.md asymmetry applies to session analysis itself.** The
   law says the measurement plane is the least-governed code; a
   session's ad-hoc extraction snippets are less governed still (no
   review, no tests, no second route). Both wrong-key extraction
   bugs and the cross-era comparison came from exactly there.
3. **Guards existed but were never incorporated.** `pytest_pipe_guard`
   was written after the 2026-08-24 rc-masking incidents and never
   registered in `.claude/settings.json` (only SessionStart is wired);
   `ruff_on_edit` additionally hardcoded the Windows venv path, so it
   was doubly inert on cloud boxes. The operator's forbidden chain —
   add, never incorporate, forgot — in the tooling meant to protect
   the sessions.

## Fix ledger

| fix | state |
|---|---|
| digest spoofy line names its NON-LIQUID denominator everywhere it renders; `liq_lens` key added; SD-003 detail says how to get absolute prevalence | SHIPPED `core/session_digest.py` + pinned in `tests/test_session_digest.py::test_lens_labels_are_display_honest` |
| digest headline labels netting: "realized PnL (post-close-fee)" / "fees (all legs)"; comment documents the runner accumulator | SHIPPED, same files |
| `ruff_on_edit.py` cross-platform venv path (was nt-only, silently inert on POSIX) | SHIPPED `.claude/hooks/ruff_on_edit.py` |
| `docs/INDEX.md` KNOWN TRAPS section — every misread above becomes a labeled tripwire in the affordable-reading layer | SHIPPED |
| CLAUDE.md mindset rule 7 (reading discipline, five clauses, dated) | SHIPPED |
| **Hook wiring in `.claude/settings.json`** (PreToolUse -> pytest_pipe_guard on Bash; PostToolUse -> ruff_on_edit on Edit\|Write) | **BLOCKED — the permission classifier denies model edits to hook config (correctly). Operator applies the snippet below.** |

### Operator snippet — add inside the existing `"hooks"` object of `.claude/settings.json`

```json
"PreToolUse": [
  { "matcher": "Bash", "hooks": [ { "type": "command",
    "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/pytest_pipe_guard.py\" || python \"$CLAUDE_PROJECT_DIR/.claude/hooks/pytest_pipe_guard.py\"" } ] }
],
"PostToolUse": [
  { "matcher": "Edit|Write", "hooks": [ { "type": "command",
    "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/ruff_on_edit.py\" || python \"$CLAUDE_PROJECT_DIR/.claude/hooks/ruff_on_edit.py\"" } ] }
]
```

## What was already right

Every misread above was caught before it reached a decision, by the
process the repo prescribes: adversarial review with a refute mandate,
second-route derivation, and reading the corpus line. The failure rate
is the argument FOR the process, and the fixes move the catches from
review-time to read-time (labels) and to tool-time (hooks).
