# Red-team docket on the recording-leak fix — dispositions on the record (2026-09-15)

Subject, re-bound per OBJ-2: local commit **`41288059`** on `main` (`scripts/smoke_test.py`,
`tests/test_qa_isolation.py`; message amended once), plus the untracked
`docs/quant/2026-09-14_fill_hazard_l1.md` with its hand-added lines 50-52. Panel run `wf_53a6ada2-6ea`
(32 objections, 2 withdrawn, 18 surviving); docket verbatim in vault
`raw/audits/2026-09-15_session_f2f5d5cd/red_team_panel_recording_leak_fix.json`. The author must answer
each surviving cluster; below, each is CONCEDED or CONTESTED with what was done.

| # | OBJ | disposition | what was done / owed |
|---|---|---|---|
| 1 | OBJ-2 binding | **CONCEDED** — the panel template named a worktree that does not exist | Re-bound above. Every finding below maps onto `41288059` + the untracked page; nothing else changed in the tree. |
| 2 | OBJ-3 "fails safe" wrong sign | **CONCEDED, by injection** — planted `paused.on` + `entries_off.on` + a future-stamped queued `flatten_all` in a scratch cwd, ran the real `test_runtime_and_runner()`: both sentinels DELETED, the command consumed and never run | Commit message amended (the false "fails safe in direction" paragraph replaced with the measured mechanism). Fix owed, SAFE: route control dir + sentinel dir through config keys with today's defaults, redirect in `qa_redirect_paths`, pin both; interim mitigation `os.chdir(TMP)` around section [20]. Do NOT add a `root:` to `FORCE_DRY_SENTINEL` (weakens invariant 1). The measured DoD smoke gate rewrote the live `force_dry.on` at 23:39Z — that file's mtime has never been operator evidence. |
| 3 | OBJ-1 + OBJ-4 + OBJ-14 (YES arm unreachable) | **CONCEDED as information; demand accepted** | Generator must print the attainable ceiling and the LR-rejection count IN the verdict block and withhold "Recommend closing L2" when ceiling < `REL_MISSTATE_MAX`; nothing routed into `powered`; pin at ring magnitude on `run()` output. Owed 116 (folded). The "+11.2% first-poll" and "+73%/+129%" arms were dropped by the panel — not owed. |
| 4 | OBJ-12 + OBJ-16 (dead comparator) | **CONCEDED, verified by grep before propagation** — `config.json:399 passive_hazard_with_book: false`; sole `_passive_poll_prob` call gated at `order_manager.py:1360-1363`; live rule `_sim_maker_cross` `:1340` | Same-session callouts landed on: the report (addendum line 52), vault raw record, source page, index, `the-method` #21 (and a correction to #20), `owed-measurements` 116 (112-114 re-scoped). `core/codes.py:492` gloss and the generator's flag-read are owed (116). L2 returned to the docket. |
| 5 | OBJ-13 (T=5 polls ≠ 25 s) | **CONCEDED [I]** — read against the report text; not independently re-measured | Folded into 116 as a fourth invalidator; a wall-clock horizon is part of any re-posed L1. |
| 6 | OBJ-17 CRITICAL (effective events 4-6 < `E_MIN` 10) | **CONCEDED [I]** | Owed 113 re-scoped under 116: any re-posed L1 needs a clustered-n power gate. |
| 7 | OBJ-18 CRITICAL (REST books written only when WS is stale) | **CONCEDED [I]** — mechanism from `runner.py:256-259` and `kraken_max_book_age_sec 3.5 < poll 5`; not traced at runtime | Recording the WS book (owed, SAFE) is the only cure; until then the corpus is quiet-book-conditioned. |
| 8 | OBJ-5 + OBJ-6 + OBJ-15 (composition) | **CONCEDED**, with the panel's own narrowing (PAXG is in-universe; the "burst" mechanism for majors was wrong — real major tapes are sparse) | Addendum line 50 already carries the fixture-share disclosure; the polls-per-tape understatement stands as disclosed. |
| 9 | OBJ-7 (byte-identical referent; hardcoded "7 of 9 days") | **CONCEDED minor** | Generator fix owed with 116 (compute the overlap or drop the literal). |
| 10 | OBJ-8 + OBJ-9 (p_sim column) | **CONCEDED minor** — the level of a dead path; exp-of-mean vs mean-of-exp | Folded into 116. |
| 11 | OBJ-10 (frame lacking `t` stamped 0.0) | **NOTED latent**; 0 such frames today (full-range scan by the panel) | No action. |
| 12 | OBJ-11 (generator overwrites the addendum) | **CONCEDED** — the scheduled route fires only at 10:30Z on its own UTC date, so the 09-14 file is safe from re-fire; a future same-day re-run would destroy it | The durable copies are the vault raw record and this docket; the generator gaining a preserve-existing guard is owed with 116. |

**Contested: none.** Every surviving objection held on re-reading; the panel's own withdrawn arms
(lock, status.json, the pytest pin, the pre-emptive "vault got its callout" objection, the "no referent"
wording) are not re-argued.

**Push status:** `41288059` stays local until the operator has read this docket; the fix itself is
triple-verified (suite 25 green, mutation pair, injection both arms) and the live recording ring was
byte-identical through the real DoD smoke gate.
