# 09-22 Boundary Runbook — execution rehearsal record (2026-09-19)

**Institutional handling of expedite request 09-19.** The operator
requested authorization to ship non-SAFE (cohort-resetting) changes
immediately. Ruled on the record: **DENIED-WITH-REASON** — era-9 is
40/50 with the 14-day minimum opening the same window; the requested
scope is entirely pre-staged; no change justifies killing the first
near-complete era in project history 3 days early. The denial is
recorded in HANDOFF. The remaining days go to execution rehearsal, as a
desk would spend them. If the operator overrules this on 09-22, the
decision record for that override is the R2 draft's ruling block.

## Rehearsal already executed (2026-09-19)

- **Merge rehearsal**: `main` merged into `fix/decisioning-coupling-r123`.
  One conflict found and resolved exactly as predicted —
  `tests/test_coupling_r123.py` (main carries the R1+R3-only test file;
  the branch carries the R1+R2+R3 superset; resolution takes the branch
  file, whose R1/R3 portions are byte-identical in semantics to main's —
  verified by 31 passed across coupling + fee_recon + tier guards).
- **Net branch state**: `git diff main...HEAD` now shows ONLY the R2
  delta (`core/state.py`, `core/persistence.py`, `risk/profit_tiers.py`
  + R2 test additions, +137/−9). The 09-22 merge is mechanical.
- **Unverified at rehearsal time** (verify on the day): full chunked
  battery on the merged result, pyright on the R2 files. See below.

## Environment drift check (added 2026-09-19, from a real failure)

Before step 1, machine-check the files whose silent corruption broke
tooling on 09-19 without touching the bot:

```
python -c "import json; [json.load(open(f, encoding='utf-8')) for f in ('.mcp.json', 'config.json')]; print('env JSON OK')"
```

On 09-19 an unescaped inner quote in `.mcp.json`'s GitHits `_doc`
(auth-lapse note) made the file unparseable — no test caught it because
no test loads it; the first symptom was an agent failing to dispatch.
A red here is a hard stop: fix the JSON before anything else, since
`config_guard` only validates `config.json` at bot start and nothing
validates `.mcp.json` at all.

## The window, in order (each step names its own verification)

1. **Read the lean.** `python scripts/era_readout.py`. The readout
   NAMES the decision; it never decides. Numbers to expect if the flip
   math held: net CI still excluding zero at n≥50. (If n<50 by 09-22,
   the lean is NOT decidable — the minimum opens, the read point does
   not move; read at n=50.)
2. **Rule on the docket, in queue order** (HANDOFF 09-22 PRE-STAGING):
   R2 (decision record at
   `docs/quant/2026-09-19_r2_frozen_tier_triggers_decision_record_draft.md`
   — ruling block A/B/C), long book (a)/(b), n=100 hole (tiebreaker or
   accept UNDETERMINED), duplicate-runner behavior fix, scaling governor
   (adopt/defer; SAFE report at `scripts/scaling_report.py` re-run for
   fresh inputs), ALGO-5 stays refused. Every ruling is written in its
   own decision record BEFORE any code moves — the moratorium's
   justification requirement applies per item.
3. **Merge R2 if ruled in.** The branch is rehearsed; merge to main,
   then run: chunked full battery (6 chunks, `-n 12`; ~25 min) · ruff ·
   `pyright core/state.py core/persistence.py risk/profit_tiers.py`.
   All green is part of the merge, not a follow-up.
4. **Apply the ruled config changes** (long book, scaling flag, fee
   tier re-read per the venue-constant rule if the operator's real
   trading moved the tier — fresh reading, three routes, named drift).
   `config_guard` re-validates on next start; a FATAL there means the
   bundle is incoherent and NOTHING restarts until it is.
5. **Restart and verify the boot line**: `fees=<maker>/<taker>bps` matches
   the booked tier; `exec_era` increments; era-N accrues from zero.
6. **Update HANDOFF** per its contract: settled items to RECENTLY
   SETTLED with records, remaining docket rows intact, the pre-staging
   section superseded with a dated pointer.

## Hard stops

- Any step red → stop, record, do not proceed to the next step. A
  boundary executed half-applied is worse than a boundary not taken.
- No config edit without its decision record signed in the same session.
- The n=100 hole decision precedes ANY n=100 reading, not the reverse.
