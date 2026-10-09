# Task 2 report — verify commit ca55e2ba (boundary #5 fee-truth cut, staged/inert)

Repo: c:\Users\haird\Documents\liquiditybot\liquiditybot_ab, branch claude/claude-rc-f3heik
Commit under review: `ca55e2ba6785a0eab1d8c59eeb4ce56659ae5889` (2026-08-25T16:19:44-05:00)
Verification performed: 2026-08-27 (local session clock; all "current config.json" reads are as-of this session, git status clean, no concurrent edits observed).

## STATUS: VERIFIED_CLEAN

All load-bearing claims in the commit message, the staged doc
(`docs/quant/2026-08-25_boundary5_adjudication.md`), and the brief were
checked by a non-static route (runtime instantiation, mutation, injection)
and matched exactly. One documentation-currency concern found (docket
numbering staleness in `docs/HANDOFF.md`), not a code defect.

---

## 1. What the staging mechanism is [K]

Two new files, zero other diffs (`git show --stat ca55e2ba`):
- `docs/quant/2026-08-25_boundary5_adjudication.md` (95 lines, decision record)
- `scripts/boundary5_stage.py` (143 lines, the stager)

`scripts/boundary5_stage.py` is a standalone CLI script (not imported by
`main.py`, `runner.py`, or any other production module — confirmed by
`grep -rn "boundary5_stage" scripts/ core/ execution/ ml/ risk/ regime/
strategies/ sentiment/ api/ main.py runner.py` → 0 hits outside itself).

Mechanism: a table `EDITS = [(dotted_key, FROM, TO), ...]` of 7 keys:

| key | FROM | TO |
|---|---|---|
| `pretrade.maker_fee_bps` | 25.0 | 40.0 |
| `pretrade.taker_fee_bps` | 40.0 | 80.0 |
| `order_manager.maker_fee_bps` | 25.0 | 40.0 |
| `order_manager.taker_fee_bps` | 40.0 | 80.0 |
| `profit_taking.est_fee_bps` | 40 | 80 |
| `ml.label_round_trip_cost_pct` | 0.5 | 1.2 |
| `ml.exploration.p_win` | 0.7 | 0.85 |

`main()`: dry-run by default (prints diff + guard sweep, writes nothing,
exit 0); `--apply` (1) re-reads `config.json` fresh, (2) refuses (rc=2, no
write) if ANY current value != its expected FROM ("drift" guard), (3)
builds a deep-copied candidate with all 7 edits applied, (4) runs
`core.config_guard.validate(candidate)` and refuses (rc=2, no write) on
any FATAL, (5) only then backs up `config.json` to
`config.json.pre-boundary5-<timestamp>` and writes the candidate.

## 2. Inertness — proved via two independent runtime routes

**Route (a) — ask the runtime, live decision-path classes, real
config.json, staged artifact present in the tree.** [K, this session]

```
PreTradeGate.maker_fee_bps  = 25.0     PreTradeGate.taker_fee_bps  = 40.0
OrderManager.maker_fee_bps  = 25.0     OrderManager.taker_fee_bps  = 40.0
OrderManager.pretrade_maker_fee_bps = 25.0 (no pretrade_fee_bps arg -> fallback = own value)
OrderManager.pretrade_taker_fee_bps = 40.0
ProfitTierEngine.est_fee_bps = 40.0
CandidateLabeler.rt_cost_pct = 0.5
explore_p_win (main.py:1039 formula, min(max(cfg.exploration.p_win,0),0.95)) = 0.7
```
Every one of these is instantiated directly from the real, tracked
`config.json` (main.py:797,849,882,978,1039 wire these exact sub-blocks)
with `scripts/boundary5_stage.py` present on disk — none of them read the
TO values. `git status --short` / `git diff --stat` on the live tree:
clean, before and after all probing.

Also confirmed at the era-stamp layer: `core/fill_ledger.py:46` —
`EXEC_ERA = "7-e7d5ca1a"` — is a **hardcoded constant** the file's own
comment says must be "bump[ped] ... in the SAME commit as any future
execution-era boundary." ca55e2ba's diff never touches this file, so the
fill-ledger era stamp is untouched — an independent confirmation that no
execution-era boundary was minted by this commit.

**Route (b) — injection/mutation in an isolated temp copy** (`git archive
HEAD | tar -x` into a scratch dir under the session temp path; never the
tracked tree — confirmed byte-identical `config.json` via `diff` before
mutating, and `git status --short` / `git diff --stat` clean on the
tracked tree after):

1. Dry-run on the untouched temp copy: prints the diff, `0 FATAL / 4 WARN`
   on the full 7-key candidate, writes nothing (`diff` after run: temp
   `config.json` byte-identical to before). Matches commit's "0 FATAL"
   claim for the full package.
2. **Mutation — fees-only candidate (p_win left at 0.70), the exact
   scenario the commit message calls "1 FATAL":** ran
   `core.config_guard.validate()` directly →
   **`1 FATAL, 5 WARN`**, FATAL text: `"ml.exploration.p_win=0.700 is
   at/below the net-Kelly breakeven 0.833 (maker+taker round-trip cost) -
   every exploration entry SZ-030-vetoes..."` — verbatim match to the
   commit message and `docs/quant/2026-08-25_boundary5_adjudication.md`.
3. **The p_bar move, computed live via the real
   `risk.position_sizer.PositionSizer` / `payoff_ratio_from_config`:**
   - unarmed (current config): `b_net=0.4488`, breakeven
     `1/(1+b_net)=0.6902`, `p_bar_base=0.6902` (mode `derived`).
   - armed, fees-only: `b_net=0.1998`, breakeven **`0.8335`**,
     `p_bar_base=0.8335`.
   Exactly reproduces the brief's "p 0.690 → 0.834" and the doc's "b_net
   0.4488 -> 0.1998", "breakeven 0.690 -> 0.8335".
4. **Injection — drift refusal:** hand-edited `pretrade.maker_fee_bps` to
   30.0 (neither FROM=25.0 nor TO=40.0) in the temp copy, ran
   `--apply`: **exit code 2**, `REFUSING: 1 key(s) do not match the
   staged FROM values`, no backup file created, `config.json`
   post-refusal still reads the drifted 30.0 (not silently forced to
   40.0, not reverted) — reproduces the commit message's
   "mutation-verified: hand-editing one fee key -> rc=2, config
   untouched even under --apply" exactly.
5. **Apply, clean case:** restored a clean temp copy (re-diffed
   byte-identical to live), ran `--apply`: exit 0, all 7 keys written to
   their TO values, backup `config.json.pre-boundary5-20260827-163659`
   created beside it. Confirms the stager IS wired to something real —
   not dead code — and that its write path behaves as documented.

All of steps 1–5 ran only inside the scratch temp copy
(`AppData\Local\Temp\claude\...\scratchpad\b5test`, deleted after use);
the tracked tree's `config.json` was re-verified unchanged
(`pretrade.maker_fee_bps=25`, `ml.exploration.p_win=0.7`) and `git
status`/`git diff --stat` clean immediately afterward.

**Conclusion: INERT is TRUE**, on both the "what the decision path reads
today" axis and the "the staged mechanism is real and correctly wired,
not decorative" axis.

## 3. No partial leak [K]

Grepped every one of the 7 staged key names (`maker_fee_bps`,
`taker_fee_bps`, `est_fee_bps`, `label_round_trip_cost_pct`,
`ml.exploration.p_win`/`p_win`) across `*.py`. Every production consumer
(`execution/pretrade.py:79-80`, `execution/order_manager.py:176-177`,
`risk/profit_tiers.py:218`, `ml/history.py:2175`, `main.py:1039`) reads
from `config.get(...)` against the live tracked `config.json` — none
import or reference `scripts/boundary5_stage.py` or its `EDITS` table.
`core/config_guard.py` only ever validates a *candidate* dict passed to
it by the stager (or by tests) — it does not itself hold or leak state.

**Telemetry exception, confirmed correctly labeled:** `scripts/
fee_reprice.py` hardcodes its OWN `TRUE_MAKER_BPS=40.0` /
`TRUE_TAKER_BPS=80.0` (sourced from `cost_attribution.py:82-90`, predates
and is independent of the stager) purely for reporting, and explicitly
prints both the labeled comparison (`"BOOKED (25/40)"` vs true) and the
disclaimer `"the live pretrade EV gate still admits trades priced at
25/40"` (fee_reprice.py:208). This is measurement-only, correctly
distinguishes staged/true from live/booked, and does not feed back into
any decision path.

No other consumer (tests, docs, dashboards) reads the staged TO values as
if live.

## 4. Moratorium classification: SAFE, as shipped [K + reasoning]

CLAUDE.md's era-4 moratorium lists fee-booking changes as
COHORT-RESETTING. What actually shipped in ca55e2ba is: (1) one
documentation file, (2) one script that — by construction, confirmed
above — refuses to write anything without an explicit `--apply` flag,
refuses to write on any drift, refuses to write on any guard FATAL,
and touches nothing at import time or module load. `config.json` is
byte-unchanged; `core/fill_ledger.py:EXEC_ERA` is byte-unchanged; no
production module imports the script. **This is SAFE class as shipped**
— exactly the "measurement/report tools, dashboards, ... bug fixes that
do not alter which orders are placed or how they fill" carve-out, and
exactly what the commit message itself claims. The COHORT-RESETTING act
is `--apply` + restart, which is still an unexercised, operator-gated
future action, not part of what this commit did.

## 5. Covering tests

**No dedicated test file exists for `scripts/boundary5_stage.py` itself**
— `grep -rln "boundary5_stage"` under `tests/` → 0 files, and no test
does `import scripts.boundary5_stage`. This is a real gap relative to
this repo's own convention (`tests/test_cost_truth_report.py`,
`test_ground_truth_metrics.py`, `test_gate_truth_report.py`, etc. all
directly unit-test their corresponding `scripts/*.py` module) — the
commit's own "mutation-verified" claims in its message were, per the
repo's test suite, never captured as a regression test. Not a defect
(script is correct, per my independent mutation/injection reproduction
above), but a coverage gap worth the operator's attention if this stager
is going to be re-run at readout.

Ran the tests that DO cover the underlying mechanisms the stager depends
on (`core/config_guard.py`'s FATAL/WARN logic and
`risk/position_sizer.py`'s `p_bar_mode=derived` breakeven math):

```
./.venv/Scripts/python.exe -m pytest tests/test_config_guard_fee_recon.py \
  tests/test_config_guard_coherence.py tests/test_config_guard_min_pwin.py \
  tests/test_config_guard_exploration.py tests/test_sizer_derived_bar.py -q
40 passed in 6.76s
```

Broader sweep, all config_guard + sizer_derived_bar tests in the suite:
```
./.venv/Scripts/python.exe -m pytest tests/ -k "config_guard or sizer_derived_bar" -q
321 passed, 3735 deselected in 4.01s
```

Hygiene on the new file (not part of the DoD gate for `scripts/`, run
anyway):
```
./.venv/Scripts/python.exe -m ruff check scripts/boundary5_stage.py   -> All checks passed!
./.venv/Scripts/python.exe -m compileall -q scripts/boundary5_stage.py -> OK
```

**Exact test counts this session:** 40 passed (targeted 5 files) + 321
passed / 3735 deselected (broader `-k` sweep). No failures, no errors, no
skips encountered in either run.

## Concerns

1. **Docket-numbering staleness (documentation only, not a code
   defect).** `docs/HANDOFF.md`'s "OPEN DOCKET" section (stamped
   AS OF 2026-08-22, lines 76-95) calls the FEE-1+FEE-2 bundle
   **"Boundary #6"** ("Boundary #6 order: FEE-1+FEE-2 bundled FIRST, then
   REG-8 v2, then SWEEP-0/1"). By 2026-08-25/26, the commit under review
   and `HANDOFF.md`'s own later WHY-1 entry (line 115, 2026-08-26) call
   the fee-truth cut **"boundary #5"** and list it alongside (not
   bundled with) `ALGO-5`/`CONC-1` — while `scripts/fee_reprice.py`'s
   docstring separately describes owed-88 as "BATCH AT READOUT with
   ALGO-5 as one boundary #5" (ALGO-5 *inside* boundary #5). Three
   documents in the same live tree currently disagree on (a) the
   boundary's number and (b) what's bundled inside it. This does not
   affect the mechanism verified above (the stager's `EDITS` table only
   ever encodes the 7 fee/label/p_win keys — ALGO-5 is stop/time-decay
   geometry, touched by nothing in this commit), but the OPEN DOCKET
   section is stale relative to the newer WHY-1 entry in the same file
   and should be reconciled before the operator acts at readout, per
   CLAUDE.md's own "currency counts as correctness" rule.
2. **Coverage gap** noted in §5 — no direct unit test for
   `scripts/boundary5_stage.py`'s drift-refusal / guard-refusal /
   apply-and-backup logic, only my one-off mutation/injection
   reproduction in a scratch copy this session (not persisted as a
   regression test — out of scope for a read-only verification task,
   flagging for the operator to consider before `--apply` at readout).
