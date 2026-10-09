# Common context — verification session 2026-08-27

Repo: c:\Users\haird\Documents\liquiditybot\liquiditybot_ab (branch claude/claude-rc-f3heik == origin/main @ 5e785c16)
Interpreter: ALWAYS `./.venv/Scripts/python.exe` (system python lacks deps). Windows box; the live bot runner may be RUNNING on this machine.

## Binding law (excerpts you must apply)
- Era-4 moratorium: changes to entry decisioning, sizing, stop/exit geometry, fill simulator, fee booking, or order lifecycle are COHORT-RESETTING and forbidden without operator adjudication. SAFE: measurement/report tools, dashboards, tests, wiki, telemetry, bug fixes that do not alter which orders are placed or how they fill. Part of your job: classify the change you verify as SAFE or cohort-resetting AS SHIPPED (not as intended).
- State of play: era-4 gate READ OUT at n=54 (2026-08-26 why-losing deep dive, docs/quant/2026-08-26_why_losing_deep_dive.md): gross +$8.23, fees $6.87 booked/$13.59 true, net +$1.36/−$5.36. COST_BOUND shape. Remedies staged (boundary #5 fee-truth cut) but NOT armed.
- Hard invariants: dry_run default true; Kraken sole execution venue; withdrawals impossible; exits always allowed; audit chain + registered reason codes.

## Verification method (mandatory, in preference order)
Static reading of code is NEARLY ALWAYS VACUOUS. Prefer:
1. MUTATION — break the thing, watch a test/pin go red, restore (in a TEMP COPY, never the tracked tree)
2. INJECTION — plant the exact bad form, watch the guard fire
3. ASK THE RUNTIME — call the real function on the real artifact
4. EXHAUSTIVE ENUMERATION when the domain is finite
"0 findings" and "my check is broken" are the SAME OBSERVATION until separated — state which you established.

## Measurement contract (every number you report)
a. Exact boundaries, no "~". State the commit SHAs / line ranges / row bounds you used.
b. Name the needle: exact grep string / command for every claim.
c. Snapshot-stamp any live file you read (status.json, logs): include read time; values are as-of.
d. Provenance per claim: file + filter + value, tagged [K] read / [I] inferred / [UNKNOWN]. Never estimate silently.
e. Load-bearing counts get double-derived by two routes; report both if they disagree.

## Constraints
- READ-ONLY on the tracked tree: no edits, no commits, no `git checkout`/`reset` in the main worktree. Scratch experiments go in your own temp dir.
- pytest on targeted test files is allowed and encouraged. Do NOT run scripts that write to outputs/ production files (audit chain pollution was a real incident); tests that use tmp_path are fine.
- Do not kill or restart any running process.

## Report contract
Write your FULL report to the report path given in your task brief. Return to the controller ONLY: STATUS (VERIFIED_CLEAN | DEFECT_FOUND | CANNOT_VERIFY), a 1–3 line summary, and concerns. STATUS definitions: VERIFIED_CLEAN = every claim checked by a non-static route came back clean; DEFECT_FOUND = at least one confirmed defect (list them); CANNOT_VERIFY = name exactly what blocked you and what you did establish.
