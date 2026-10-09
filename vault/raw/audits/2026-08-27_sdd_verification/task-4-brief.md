# Task 4 — verify the UNMERGED battery/trials branch `claude/remote-control-hds2hd` (tip 6f8b6315)

Read context-common.md in this directory FIRST — it is binding.

## What shipped there (verify, don't trust this summary)
~15 substantive commits over 3 days implementing TRIALS-1 (HANDOFF docket, SAFE class: trial ledger of how many strategy configs were evaluated, so DSR can be computed instead of tabulated) plus an "archetype null battery" (venue-coherent tape generator, eight entry-only rungs, test-only oracle, grid runner with determinism+cycles gate, activity floor, ledger) and OF-3/OF-5 fixes. Key SHAs, oldest→newest:
61166dc1 docs(spec) · e4c1469b docs(spec, SEV-1 tape defect second-route) · b48db57d docs(plan) · f40d298c feat(replay) mutate_bot injection seam · 594a2d43 feat(trials) ledger schema · aba170fb fix(trials) atomic append · d1184dad feat(trials) harvest mode absent-is-not-zero · ebbab4e2 fix(of3) _BASE_ORDER shadow · 77b15321 feat(of5) trial-count ratchet · 6b21b60c fix(of5) degrade-not-crash · b367e65c feat(battery) tape generator · 97a2edf2 feat(battery) eight rungs + oracle · 5dfa7b4f docs · 34f2e4b7 feat(battery) grid runner · 550e9011 fix(battery) all-in fee netting · 3ec6dbbc fix(qa) postmortem paths redirect · 69088a5d docs · 6f8b6315 fix(trials) durable_append.

## Setup
Do NOT check out the branch in the main worktree. Create your own:
`git worktree add <your-temp-dir>\hds2hd claude/remote-control-hds2hd`
Use the MAIN repo's venv interpreter (c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.venv\Scripts\python.exe) with cwd = your worktree. REMOVE the worktree when done (`git worktree remove --force <dir>`).

## Questions to answer, each with evidence
1. SUITE STATE: run the branch's test suite in your worktree: `<venv> -m pytest tests/ -q` (full; it's the DoD gate). Exact pass/fail/skip counts. If reds: are they the two KNOWN platform families from HANDOFF RECENTLY SETTLED (cmd.exe pins / rotation split — those are settled, do not re-litigate) or new?
2. MERGE STATE: `git merge-base`, does the branch rebase cleanly on main @ 5e785c16 (check with `git merge-tree` or a scratch merge in YOUR worktree only)? Conflicts = report files.
3. TRIALS-1 SEMANTICS: "absent-is-not-zero" — prove by asking the runtime: call the harvest/ledger reader on (a) an empty/missing ledger, (b) a populated temp ledger. Absent must yield "unknown N" (DSR tabulated against hypotheses), never N=0 or N=1 silently. Exact behavior with provenance.
4. OF-5 RATCHET: "reads the measured ledger, never relaxes" — MUTATION test: feed it a ledger with N=k, then a smaller N=k-1; the ratchet must hold at k. Show it.
5. OF-3 FIX (ebbab4e2): the _BASE_ORDER shadow — was the pre-fix behavior wrong in a way that affected published PBO numbers? Check whether model_space_pbo results shipped anywhere (reports/vault) while the shadow was live. If yes, flag: those numbers need re-derivation.
6. MORATORIUM CLASS: the branch claims SAFE throughout, but f40d298c adds a mutate_bot injection seam to REPLAY and 550e9011 touches fee netting in LEDGER rows. Establish: does anything on this branch alter the LIVE path (which orders are placed / how they fill / how fees are BOOKED in production accounting), or is it all test/measurement plane? File-by-file verdict for those two commits specifically.
7. SEV-1 TAPE DEFECT (e4c1469b claims second-route verification): read the spec doc; was the defect fixed on this branch, and does the coherence self-check (b367e65c) actually FAIL on the defective form? Injection: regenerate the defective tape shape and run the self-check.

## Report path
Write full report to: C:\Users\haird\AppData\Local\Temp\claude\c--Users-haird-Documents-liquiditybot-liquiditybot-ab\cdb03d59-62a4-41ee-8c1c-00feb1307464\scratchpad\sdd\task-4-report.md
