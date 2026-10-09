# Task 2 — verify commit ca55e2ba "feat(quant): boundary #5 staged - the fee-truth cut, ready but inert (owed 88)"

Read context-common.md in this directory FIRST — it is binding.

## What shipped (verify, don't trust this summary)
`git show ca55e2ba` — boundary #5 (the fee-truth cut: correcting configured fees 25/40 to Kraken true tier 40/80) is STAGED but claimed INERT. Arming it is an OPERATOR decision (HANDOFF FEE-1/FEE-2: writing true fees produces a config_guard FATAL because exploration p_win 0.700 falls below net-Kelly breakeven 0.833 — the bot will not start).

## Questions to answer, each with evidence
1. WHAT is the staging mechanism: a config block? a script? a flag? Exact files/keys. Needle: `git show ca55e2ba`.
2. INERTNESS — the load-bearing claim. Prove by asking the runtime, minimum two routes:
   a. Show the deployed decision path reads the OLD fee constants with the staged artifact present. Ask the runtime: import the relevant config/module in a scratch process and print the fee values the sizing/veto path actually receives NOW.
   b. INJECTION/MUTATION: in a temp copy, arm the staged cut the way the operator would, and show the behavior WOULD change (config_guard FATAL or bar moving p 0.690→0.834) — proving the stage is wired to something real, not dead code. Then confirm the unarmed state produces none of that.
3. NO PARTIAL LEAK: grep every consumer of the staged keys/files — does anything read the staged values today (telemetry excepted; report if telemetry reads them and labels them as staged vs live)? Needle: the exact key names from the diff.
4. MORATORIUM CLASS: inert staging = SAFE only if truly inert. Your verdict.
5. Covering tests: name, run with ./.venv/Scripts/python.exe -m pytest <files> -q, exact counts.

## Report path
Write full report to: C:\Users\haird\AppData\Local\Temp\claude\c--Users-haird-Documents-liquiditybot-liquiditybot-ab\cdb03d59-62a4-41ee-8c1c-00feb1307464\scratchpad\sdd\task-2-report.md
