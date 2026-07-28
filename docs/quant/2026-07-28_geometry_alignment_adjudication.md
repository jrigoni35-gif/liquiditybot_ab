# Geometry alignment — whole-feature battery + quant adjudication (Task 8)

Closes `docs/superpowers/specs/2026-07-27-geometry-alignment-design.md`
(T1-T8). This is the final task of the 8-task plan; it runs the full
Definition of Done battery, adjudicates the quant/overfit gates, and
records the measured facts the plan exists to prove — no new mechanism,
report-only closure.

## The feature, one line

Model-lane entries (conviction AND exploration probes) now trade the
SAME bet the label measures: `_bracket_for_entry` (`main.py`) computes
each entry's triple-barrier bracket via `barrier_geometry()`
(`ml/labeling.py`) — the identical pure helper `CandidateLabeler` calls
— from the entry's own σ_bar and post-clamp `est_cost_bps`, re-sizes
through `PositionSizer.size(bracket=...)` (risk-in-size: notional
shrinks as `sl_pct` widens so dollar-risk matches the legacy 2%-stop
trade), and PASS-1's pretrade-approved `decision.size_units` stays a
hard CEILING on that PASS-2 notional (T5 review fix — clamp
`rescale_ratio` at 1.0, downscale only). Exits route through the
existing maker-first / stop-escalation / vertical machinery and stamp
`tb_pt` / `tb_sl` / `tb_time` — the labeler's own barrier vocabulary —
instead of the old hardcoded `"realized"` tag. One bet, label to fill.

## Era-gap closure route (measured)

T1 (V1 verification, `docs/quant/2026-07-27_live_row_era_gap.md`)
measured the corpus (`outputs/signal_history.csv`, 4,989 rows) before
any code changed: of 242 live rows, 1 is `book=="long"` (out of
`load_training_data` scope entirely), leaving **241 in-scope live rows —
100% old-era, 0% carrying a `tb_*` barrier**. Every live close wrote
`barrier="realized"` (`HistoryStore.log_close`, hardcoded, independent
of which reason actually closed the position), which
`label_era_of`/`_EXIT_SIM_BARRIERS` route to `LABEL_ERA_EXIT_SIM` —
disjoint from `LABEL_ERA_TRIPLE_BARRIER` — so all 241 rows would be
excluded the instant `ml.era_exclusion` activates, and the live side of
the corpus would never refresh the tb-era training set no matter how
long the bot ran.

T5 closes that gap **without touching the era map**: bracket-traded
closes now pass `tb_pt` / `tb_sl` / `tb_time` as `barrier` to
`log_close` (the exact strings the labeler itself emits), so a live
bracket close joins `LABEL_ERA_TRIPLE_BARRIER` through the SAME,
unmodified, source-agnostic `label_era_of` / `_TRIPLE_BARRIER_BARRIERS`
partition T1 verified (`_TRIPLE_BARRIER_BARRIERS`/`_EXIT_SIM_BARRIERS`
in `ml/history.py` are byte-identical to before T1 — the era system
already had the guarantee, T5 just changes what a bracket-traded close
*emits*). Non-bracket / senior-overlay exits (ratchet, hard-stop DD,
flatten, force_dry, manip) are unaffected and keep their own reasons —
per the spec's own success criterion ("≥95% of model-lane closes emit
`tb_*`... rest = senior overlay exits").

## Floored-bracket bar (measured)

`ml.label_pt_cost_mult = 4.0` floors σ_bar so profit distance ≥ 4× the
entry's expected round-trip cost. At the shipped-config floor example
(cost ≈ 0.5%): `pt = 2.0%`, `sl = 1.5%` (`barrier_geometry()`,
`ml/labeling.py`). The sizer's worst-case (costs-included) breakeven at
that floor: `b_net = (2.0 − 0.65) / (1.5 + 0.65) = 0.628`, giving a
required-win-rate bar of `1 / (1 + 0.628) = 0.614` — the WORST case the
D5 probe-clearance interlock guards against
(`core/config_guard.py:2547`, "COMPUTED, never hardcoded"). The probe
synthetic `p_win = 0.64` (`ml.exploration.p_win`, shipped config) clears
that floored bar by **0.026** — guard-checked; WARN fires below 0.005
clearance. This margin is deliberately thin by design (the floor exists
to make costs bite, not to give probes headroom); it is the number to
re-check first if `ml.label_pt_cost_mult` or `ml.exploration.p_win` ever
move.

## Cost-truth finding (T7, measured — not corrected here)

`scripts/cost_truth_report.py` (spec D4: "measured, never assumed"),
run against the current corpus:

```
[2] ROUND-TRIP bps — source: postmortem cost_overrun_bps (outputs/postmortem_summary.csv)
    n=16 unique closed trades  (17 rows read, 1 duplicate position_id row(s) dropped)
    mean cost_overrun = +21.17 bps
    measured round-trip = 65.00 + +21.17 = 86.17 bps
    configured round-trip = 65.00 bps
    delta = +21.17 bps (+32.6%)
    VERDICT [XV-033]: DANGEROUS: configured UNDER measured (gate underprices real cost)
```

Measured round-trip cost (**86.17 bps**) exceeds the configured
`pretrade.maker_fee_bps + taker_fee_bps` baseline (**65.00 bps**) by
32.6%, past D4's ±20% tolerance, in the dangerous direction (a
configured cost floor that under-prices reality can let a net-losing
trade clear the pretrade EV gate). This corroborates an independent,
earlier measurement already noted in `config.json`'s own doc-string
(P1, 2026-07-23 P&L diagnosis: ~20.5bps overrun over 209 live closes) —
two separate derivations landing in the same neighborhood.

**Caveat, load-bearing**: n=16 is the *underperforming subset* by
construction — `postmortem_summary.csv` only contains trades whose
postmortem TRIGGERED (stopped out, or shortfall past
`ml/postmortem.py`'s `shortfall_ratio`), never the full closed-trade
population. A population-wide round-trip average would need either a
corpus source logging `cost_overrun` for *every* close, or the raw
fees/notional already present in `outputs/fills.csv` (out of scope for
T7 per its brief's two named data sources) — flagged as a backlog
companion measurement, not done here. The maker-leg side (OM-080
venue-measured fee tier) is **insufficient data, n=0** — no live Kraken
credentials on this corpus, fee_recon has never fired.

**No config change was made.** Per spec D4, a configured-fee edit is
the operator's own conscious commit, never an automatic correction from
a measurement script — this finding is surfaced, not acted on.
**Operator decision pending**: whether to raise `pretrade.maker_fee_bps`/
`taker_fee_bps` (and `order_manager`'s matching pair) toward the
measured ~86bps, on the current n=16 evidence or after the
population-wide `fills.csv` companion lands.

## Quant adjudication (Task 8, this task)

`.venv/bin/python scripts/quant_trials.py` at its default (CI-bound)
config — 200 paths × 1200 bars, seed 7 — verbatim:

```
quant trials: 200 paths x 1200 bars, seed 7 (4.3s)
                  baseline    protocol
median terminal      -0.67%      -1.37%
CVaR5 terminal      -6.17%      -4.57%
MaxDD median         2.84%       2.61%
MaxDD p95            6.50%       4.76%
ruin rate            0.00%       0.00%
gain capture          0.53        0.55

  ok    G1 tail drawdown   p95 4.76% vs cap 5.53%
  ok    G2 tail outcome    CVaR5 -4.57% vs -6.17%
  ok    G3 upside intact   median -1.37% vs floor -2.17%
  ok    G4 ruin rate       0.00% vs 0.00%
  ok    G5 capture         0.55 vs 0.53

ALL GATES PASS
```

This is **byte-identical** (every printed figure, both arms) to the
profitability-program baseline last recorded at commit `7f4ffc2`
(2026-07-23, "P4 COMPLETE"): G1 4.76 vs 5.53, G2 -4.57 vs -6.17, G3
-1.37 vs -2.17, G4 0.00, G5 0.55 vs 0.53 — ALL PASS. **No G-number
moved.** Since the script's own default IS the full 200×1200 scale (not
a separate smaller CI proxy), this single run satisfies both halves of
the plan's success criterion 4 at once: the default invocation and the
"full 200×1200" are the same run. Per instruction, a conscious
re-baseline is only warranted when a legitimate change moves a gate —
none did, so **no re-baseline, no gate widened**.
`tests/test_quant_trials.py` (the separate small-N, fixed-seed 80×1000
CI pin, used as an early-warning signal only — see its own file
docstring for why it is NOT a reliable substitute for the full-scale
run on geometry changes) is green as part of the full pytest run below.

## Overfit adjudication

`.venv/bin/python scripts/overfit_check.py` against the live corpus
(4,907 rows):

```
5 passed, 3 failed (85s)
FAIL gap[logistic]: train_auc=0.730 oof_auc=0.532 gap=+0.198
FAIL gap[gbt]:      train_auc=0.825 oof_auc=0.527 gap=+0.297
FAIL gap[mlp]:      train_auc=0.771 oof_auc=0.534 gap=+0.236
PASS shuffle:  mean_auc=0.487 z=2.0 (limit 3.0)
PASS pbo:      pbo=0.03 over 7 configs / 70 splits (deployed simplicity-ladder rule)
PASS purge:    unpurged=0.486 purged=0.492 leak_closed=-0.006
PASS dof (rows/feature): rows/feature=79.2 (4907 rows / 62 features)
PASS dof (dead-feature fraction): dead_frac=0.52
```

**5 passed / 3 failed**, matching the standing baseline held since the
Compounder program closed (2026-07-24, "PROGRAM FULLY CLOSED" ledger
entry) and reconfirmed unmoved through every geometry-alignment task
(T2-T5 ledger: "overfit 5/3 unmoved" / "unchanged"). The 3 failures are
the same documented family every prior task reconfirmed: OF-1 gap
(logistic/gbt/mlp all memorize past the OOF signal — a known
data-thinness characteristic of this corpus, not a regression this
plan's code introduced). No new failure, no recovered pass, no
adjudication action needed.

## Full battery (all green, this task's HEAD)

- `.venv/bin/python -m pytest tests/ -q` → **2742 passed** (356.37s).
- `.venv/bin/python scripts/smoke_test.py` → **219 passed, 0 failed**.
- `.venv/bin/python scripts/assurance_check.py` → **47 passed, 0 failed**.
- `.venv/bin/ruff check core data execution ml risk regime strategies
  sentiment api main.py runner.py tests scripts/quant_trials.py
  scripts/overfit_check.py scripts/cost_truth_report.py` → **All checks
  passed!**
- `/root/.local/bin/pyright core data execution ml risk regime strategies
  sentiment api main.py runner.py` → **0 errors, 0 warnings, 0
  informations**.
- `.venv/bin/bandit -c pyproject.toml -r . -x ./.venv,./tests -q` → exit
  0, 0 issues (only pre-existing informational `nosec` warnings on
  unrelated scripts, none touching this task's changes).
- `.venv/bin/python -m compileall -q . -x '.venv'` → exit 0.
- `.venv/bin/python -m pytest tests/test_import_integrity.py -q` → **1
  passed** (also covered inside the full suite above).

## T8 cleanups (carried from T5/T7 review nits)

- `main.py`: the direct-entry (`ENTRY ...`) and ladder (`ENTRY-LADDER
  ...`) INFO log lines printed the uncapped PASS-2 `sized.usd` while the
  order itself submits the pretrade-clamped `decision.size_units` —
  display-only dishonesty (T5 review nit). Both now print
  `decision.size_units * entry_price`, the same clamped-notional
  expression `_bracket_for_entry`'s caller already uses for the
  algo-parent log line (`notional_usd = decision.size_units *
  entry_price`).
- `tests/test_bracket_exits.py`:
  `test_bracket_for_entry_upward_rescale_is_clamped_to_pass1_ceiling`
  asserted only `decision.size_units <= sized1.units + 1e-9`; added the
  exact-equality companion assertion (`decision.size_units ==
  sized1.units`) for the clamped case, since `rescale_ratio` pins to
  EXACTLY 1.0 there, not merely "at or under" the ceiling.
- `core/codes.py`: the XV section header comment ("execution-truth
  harness ... replay gate + fill calibration") now also names "cost
  truth" (T7's `XV-030..033` live under that header).
- `tests/test_cost_truth_report.py`: replaced the
  `__import__('core.codes', ...)` runtime import with a normal
  top-level `from core.codes import Code`.

All four touched tests re-run 10x foreground, all green (see task-8
report for the per-file tails).

## Invariants

No hard invariant touched: `dry_run` road-to-live untouched, Kraken
remains the sole execution venue, the withdrawal deny-list is untouched,
entries stay limit-only (the bracket's pt leg is a maker limit, the sl
leg uses the existing escalation ladder — market only on the final
rung, unchanged), exits remain always-allowed (overlay exits are senior
to the bracket, unchanged). No config value was edited by this task —
the XV-033 finding is surfaced for a conscious operator decision, not
acted on.
