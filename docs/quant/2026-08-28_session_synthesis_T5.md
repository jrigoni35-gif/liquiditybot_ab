# T5 — session synthesis: are we still progressing toward profitable trades, often and precisely?

Session cdb03d59, 2026-08-27/28. Question as posed by the operator at session
start. Every number below fresh-derived this synthesis (commands inline);
scrollback totals were NOT reused (four stale variants existed — see §3).

## 1. Verdict

**On the only axis the era-4 moratorium permits movement — measurement
fidelity and staged remedies — YES, and materially.** On the strategy axis
the answer is unchanged from the WHY-1 readout and no session may move it
without operator adjudication: gross edge precisely undetermined (n_eff
9.92), net −$5.36 at true fees, COST_BOUND shape. "Often" is currently
suppressed by a veto stack whose grading instrument this session proved
un-groundable against its fossil baseline; "precisely" lives in the
conviction lane (n=5, +1.46%/trip at TRUE fees) while 91% of trades are
tuition. The remedies for both are STAGED (boundary #5 fee-truth cut;
control-arm tag; give_back arm re-anchor; asset discipline) and wait at the
prestige gate. The session's core contribution: the next era will be able to
MEASURE whether its vetoes earn their keep — the current one structurally
cannot.

## 2. What moved (all verified, chain of commits local at write time)

- `a94b5751` era-confound refusal; `62ab10c0` hardened weighted guard (the
  honest consequence: EVERY veto row + the headline now reads
  CONFOUNDED/PARTIAL — max weighted overlap 0.159 against the frozen
  baseline; the instrument now refuses what it cannot know).
- Corpus sanitization (18,096 rows, 5 eras): deployed era holds ZERO
  baseline rows; the frozen baseline can speak only to exit_sim (its
  exit_sim slice n_eff 11.88). Second-route corroboration found WITHOUT the
  fossil baseline: SZ-021 vetoed candidates win-rate sits disjointly above
  SZ-020's within the same era — REG-6's anti-selectivity DIRECTION
  reproduces; magnitude/significance remain unresolvable until a
  contemporaneous comparator exists.
- Control-arm sandbox BUILT (`sandbox/control-arm-shadow-weights` @
  `11eafb97`+`f0f3c370`): deterministic 5% stratification tag
  (metadata-only, schema 94→95) + shadow gate-weight learner. **Adjudication
  clause: base is a94b5751 — REBASE + FULL RETEST required before merge;
  its 107/107 greens do not transfer.** Projected accrual once live:
  usable n=30 in 0.85–1.6 days (measured 385–709 candidates/day).
- Suite integrity: 4 main-inherited defects fixed (`0257fd59` — stamp
  leak-class #10, fresh-checkout fixture, stager pins, flake triple-checked
  unreproducible); config audit 758 keys → SAFE class applied (`cd84c2aa`,
  runtime A/B byte-equal); five citation-verified research folders + agent
  definition (`f17e28b5`).
- Boundary docket ADDITIONS this session: give_back.arm_gain_pct=0.6 arms
  inside the 86bps break-even buffer and boundary #5 does not touch it
  (docket with ALGO-5); config BOUNDARY items (fee stack — flagged never
  fixed; use_margin value); CONF-BASELINE redesign (live comparator) is the
  control-arm's docket entry.

## 3. Suite-outcome reconciliation (the four stale scrollback totals, settled)

| environment | result | explains |
|---|---|---|
| live repo @ `cd84c2aa` (committed tree) | 4073 passed / 9 skipped / 0 failed | authoritative for this HEAD |
| collected @ `f17e28b5` (fresh, this synthesis) | 4082 collected = 4073+9 ✓ | `pytest --collect-only -q` |
| live repo @ `62ab10c0` | 4060/9/0 | +13 to cd84c2aa = fixer-2 pins (4) + knob-lift pins (9) |
| fresh worktree, branch hds2hd tip | 4085p/2f/9s/1e | branch adds tests; its 3 reds were the main-inherited defects, FIXED in `0257fd59` |
| **caveat on every live-repo green** | — | host-state-dependent (vault `concepts/host-state-dependent-green`): fresh-worktree CI leg is the queued honest environment |

## 4. hds2hd merge recommendation (re-derived at f17e28b5)

merge-base `5e785c16` (diverged, no longer ff) but `git merge-tree` shows a
**clean 3-way merge — 0 conflict markers** onto current HEAD. The branch's
own content was verified clean (Task 4 + runtime). Recommendation: merge
AFTER this session's push, as an ordinary merge commit, then run the full
matrix on the merged tree before the next push. TRIALS-1 (its cargo) is
SAFE-class and docketed.

## 5. What this synthesis could not see

Diode pins: 8 skips on this box are now PERMANENT under Smart App Control
(locally-built unsigned binaries blocked; signed-compiler route exhausted
2026-08-28) — diode verification moves to the CI leg or an operator SAC
decision (irreversible, not recommended lightly). overfit_check ran last on
pre-cd84c2aa trees this session; full DoD (incl. overfit corpus line) runs
at the final-review gate after this doc. The 9 suite skips were not diffed
against a pre-session baseline (platform class). WiFi/hardware lens still
in flight at write time — files separately.
