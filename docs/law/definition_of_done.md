*(`./outputs` was added to bandit's exclusion on 2026-09-09: it is
gitignored runtime state and agent scratch â€” that day six High-confidence
findings, all in a measurement study's scratch scripts under
`outputs/reports/`, reddened the gate on a cut whose shipped code was
clean. A gate that reads a corpus nothing ships measures the wrong thing;
`tests/test_ofi_feature.py` and `tests/test_bracket_divergence.py` skip
`outputs` for the same reason.)*
*(`.claude` is excluded because agent worktrees live under
`.claude/worktrees/` and are checkouts of OTHER branches: measured
2026-09-05, the old `-x '.venv'` form compiled **510** files out of a
15-day-stale branch on every run, so a syntax error on a branch nobody
is deploying could redden this gate. `bandit` already excludes it. Use
`-f` when you actually want to see SyntaxWarnings â€” `compileall` skips
files with a current `.pyc`, which is how an invalid escape sequence
sat green in `tests/` until 2026-09-05.)*
**A GREEN IS ONLY AS BIG AS ITS CORPUS â€” read what each gate actually
measured, not just its exit code.** Several gates degrade *honestly* rather
than failing, and the degraded form answers a **different question** than this
checklist implies. A passing line is not evidence until you have read what it
ran on.

- `overfit_check.py` substitutes a **planted-signal SYNTHETIC benchmark**
  whenever loaded rows fall under `len(FEATURE_NAMES)*10`. Its green then
  validates the **overfit machinery, not the market**, and is NOT evidence the
  deployed strategy is un-overfit. **The corpus prints on the summary line â€”
  read it every run.**
- Inside that battery, **FOUR of the seven rungs can fail to arm â€” not two.**
  Mirror of `scripts/overfit_check.py`'s own summary block (read it there, it
  is the authority): **OF-1** is informational under exploration; **OF-3** is
  evidence-gated to a single family, which makes "PBO measures the deployed
  selection rule" *vacuous* while only one family qualifies; **OF-4** plateau
  is inert whenever the replay recording opens no positions (a plateau test
  with zero entries cannot tell a plateau from a cliff); **OF-5** DSR â€”
  the era-12 sub-sentinel DEFERS below its conviction-trade floor, but the
  pooled-conviction DSR (nâ‰ˆ33) ARMS and is RED (dsrâ‰ˆ0.003), and that red
  is the operator-SETTLED state (vault, 2026-09-13) â€” a green elsewhere
  never lifts it. None of the four arming conditions is a failure; all
  four are gates that could not fire. **The number to read is the ARMED
  count, never the exit
  code** â€” `passed 3, failed 0` reads identically whether seven gates fired
  and three passed or three fired and four were dark.
- Any statistic over **concurrent** trips or overlapping label windows must
  report **effective n**, not row count â€” `scripts/gate_truth_report.py` has
  applied that standard since 2026-07-29 and `scripts/cohort_eval.py` since
  2026-08-15. An SE computed on nominal n is optimistic by `sqrt(n/n_eff)`.

**DO NOT "fix" any of these by lowering a floor.** The overfit row floor,
`SG_MIN_ROWS`, and the cohort gate's `n=50` are **measurement standards, not
tunables** â€” `gate_truth_report`'s own docstring says so in as many words.
Moving one so a gate reads "real" is the widening this file forbids. The
correct response to a degraded gate is to say so out loud and treat what it
was meant to prove as **unproven**.

*(Dated measurements for each of the above live in the vault â€”
`concepts/overfit-battery` and `sources/session-20260814-cohort-instruments` â€”
deliberately NOT here: this file is loaded every session and a number written
into law decays into a false claim.)*

Every module must import in isolation (`tests/test_import_integrity.py`
enforces; optional third-party deps may be absent, our names may not).
New behavior gets a test in the same commit. Windows is the target
runtime (VS Code, Ryzen CPU, UTF-8 enforced via batch scripts) â€” keep
paths `pathlib`, encodings explicit, and suites green under
`.\test_windows.bat`.

