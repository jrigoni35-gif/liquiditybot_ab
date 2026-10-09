---
title: "Session 2026-09-12/13 — the guards that failed open, and the gauge that could not be read"
category: source
summary: "Six measured findings from a 50-commit session. TWO GUARD CLASSES FAILED OPEN: a non-finite config value passed every range bound and approved an entry with cost=nan (measured on a live PreTradeGate), and the four hard vetoes did the same on a non-finite THRESHOLD in the exploring lane — the lane era-9 entries actually use. A third crashed the validator outright on a 400-digit int, losing every other finding with it. OF-3 (pbo) measured DISCONTINUOUS in the corpus size — 0.1857 at 18,018 rows, 0.9000 at 18,017, deterministic — and the BAND itself decays with T. The multi-horizon corpus doubled to 52,402 rows and re-read: 45 of 45 asset×horizon cells negative, best-horizon split 5/6/4 across three horizons = noise. The shadow-labelling lane's 'SAFE by construction' premise is REFUTED on four measured leak channels. SS8 (added same session): four verification helpers built, and every one found a defect in work written hours earlier and believed correct - including THE HARNESS MUTATING THE TREE ANOTHER SUITE WAS MEASURING (a failure indistinguishable from a real regression, now locked), git NORMALISING a whole-file CRLF rewrite out of its own diff, the same boundary-untested pin twice, and a docstring naming the WRONG MECHANISM for why its pin passed. Two DoD gates - the skip ratchet and bandit - were found ALREADY RED on main under an earlier 'suite green' claim."
tags: [guards, fail-open, overfit-battery, gauge, horizon, measurement-plane, nan, mutation-testing, verification-helpers]
sources: 1
updated: 2026-09-13
---

# Session 2026-09-12/13 — the guards that failed open, and the gauge that could not be read

Raw: `raw/2026-09-13_session_guard_and_gauge_findings.md`.
Repo state at filing: `main` = `2dec30a3`, 50 commits since cut #12 (`feea9612`),
suite 5236 passed / 0 failed, bot pid 14112 DRY_RUN with `force_dry.on` present.

---

## 1. TWO GUARD CLASSES FAILED OPEN, AND A THIRD CRASHED

### 1a. A non-finite config value passed every range bound

`val < lo or val > hi` is **False for NaN**, so every bound in
`core/config_guard._cost_stack_range_checks`'s list was permeable. Injected: all
five keys took a NaN with **zero findings**.

Consequence, measured on a live `PreTradeGate` built from the shipped config:

| config | approved | cost |
|---|---|---|
| baseline | False | 54.300 |
| `pretrade.impact_eta = NaN` | **TRUE** | nan |
| `adverse_selection_kappa = NaN` | **TRUE** | nan |

PT-041 is `edge < ratio * cost`, **False on NaN**, so the gate never fires and
the entry is approved with an **unknown cost**. Same shape as **RP-052**
(cut #10 B3, "NaN flowed `max(nan,0)->nan` through") one subsystem over.

**Reachable by the repo's own tooling:** `json.loads` accepts a bare `NaN`
**and `json.dumps` emits one**, and the era-cut stagers write config with
`json.dumps`.

### 1b. The four hard vetoes failed open on a non-finite THRESHOLD

The 1a fix guarded the derived `cost`/`edge`. The hard vetoes compare against
**thresholds** and run *before* it. Each is `value > threshold`, False when the
THRESHOLD is NaN — the guard stops guarding while the config still reads as
configured.

Measured **in the exploring lane**, which is the lane era-9 entries use
(`ml.exploration.enabled = True`, `bypass_pretrade_ev = True`, and
`pretrade.py` reads `if edge < ratio*cost and not exploring`, so PT-041/PT-040
are bypassed **by design** there and these vetoes are the LAST line):

```
stale 1e6 ms, threshold OK              -> refused (PT-020)
stale 1e6 ms, max_data_staleness_ms=NaN -> APPROVED
$0.01 order, min_order_usd=NaN          -> APPROVED
```

A non-finite participation cap is **verdict-invisible**: it approves nothing by
itself, it silently drops the size clamp (500 units unclamped vs 150).

**Correction carried:** a NaN in the *fallback* `pretrade.max_spread_bps` is
**INERT** at a mapped tier, because
`tier_max_spread_bps.get(ctx.tier, max_spread_bps)` and the shipped map covers
`{core, mid, micro}`. Only the tier's OWN entry opens PT-021.

### 1c. The validator crashed instead of reporting

`float()` raises **OverflowError** on an int too large to convert, and a
400-digit JSON integer literal parses to exactly that (only `1e400` yields inf).
Three coercion guards caught `(TypeError, ValueError)` only, so `validate()`
**raised** and **every other finding in the run was lost with it**.

This regressed the property commit `1d7e9e5f` shipped by name — *"stop a typo
crashing the validator"* — and was found only by an adversarial review of the
1a/1b fixes.

**The standing lesson:** all three are the same defect shape —
*a comparison silently answering False on a value nobody checked* — and all
three were closed as a CLASS, not as instances, because the 2026-09-11
`miss_cost_bps` fix had already enumerated four of five keys and left the fifth.

---

## 2. OF-3 (pbo) IS DISCONTINUOUS IN THE CORPUS SIZE

Calling `ml.overfit.model_space_pbo` at truncated T, determinism control first
(same array twice → identical pbo, so this is discontinuity, not RNG):

| rows | pbo |
|---|---|
| 18,020 / 18,019 / 18,018 | **0.1857** |
| **18,017** | **0.9000** |
| 18,010 | 0.6286 |

**Band 0.714 over ten rows**, three of six readings each side of the `<=0.5`
gate. Re-measured the same evening at **T=18,043: band 0.186, 0 of 6 RED**.

**THE BAND IS ITSELF A FUNCTION OF T.** So quote neither the point nor the band
— run `scripts/pbo_row_sensitivity.py`, committed this session precisely
because the previous study's four harnesses were lost to a session-scoped temp
directory and could not be re-run.

Neither the red nor the green is evidence about the strategy.

---

## 3. THE HORIZON LEVER IS DEAD ON ITS OWN EVIDENCE

`outputs/horizon_shadow.csv` reached **52,402 rows** (17,404 candidates × 3
horizons) against the **23,826** `config.json` cites as the evidence for the
24 → 432 `label_max_bars` migration. It had more than doubled and nobody had
re-read it. Re-run `scripts/horizon_report.py` (note: it WRITES
`outputs/horizon_report.txt` — gitignored, but it is not read-only):

- **45 of 45 asset×horizon cells negative.** Best per asset ranges −0.267%
  (DOT@432) to −0.864% (FLOW@108).
- Best-horizon wins split **5 / 6 / 4** across 108/216/432 over 15 assets —
  against a 33% null. H=216's aggregate "advantage" (−0.5111 vs −0.5832) is a
  **pooling artifact**; per asset it is noise.

Independently, the n_eff arithmetic says a 4× horizon cut buys only **1.47×**
(median observed lifespan is already 116.5 bars) and is cohort-resetting.
**Two independent routes agree the lever is not worth a boundary.**

---

## 4. THE SHADOW-LABELLING LANE IS NOT "SAFE BY CONSTRUCTION"

Proposed as the top data lever: score and label off-universe assets, never
admitted to the entry path, claimed SAFE by construction. **Refuted on four
measured channels:**

1. `mkt_ret_6` (`main.py:6167`) — runtime-proven.
2. **GateStats is live and shading right now** — `main.py:1006` wires
   `on_label=self.gate_stats.note_label`; `weighted_confidence` is applied on
   the entry path at `main.py:4620`; eight of nine published weights are off
   1.0. Keyed by geometry era only, never by asset.
3. `HistoryStore.asset_counts()` — no filter on book, source or era, feeding
   the probe-admission taper.
4. Shared candidate pool overflows at **~17–19 assets**, far below the proposed
   45, and on overflow drops the **newest pending** candidate — a real one.

The order path **is** closed: all six `submit(` sites resolve through a
`symbol_map` built once and never mutated. So isolation reduces to *never touch
`trading_pairs`*.

**But admitting one watch row into the training corpus is COHORT-RESETTING on
the day it happens** — it changes the corpus that trains the model that decides
entries. The genuinely SAFE version is weaker and honest about it: a
data-accrual investment that pays at the NEXT cut and buys nothing before then.
**OPERATOR DECISION, not taken.**

---

## 5. MEASUREMENT-PLANE DEFECTS THAT WERE SILENT

- **Panel 43 "Which gate is red"** shipped as `max(metric{job=...})` with
  legend `{{rung}}`. PromQL drops every label through a bare aggregation, so the
  tile rendered **one anonymous bar at 1.0** while `dsr=0` was invisible — the
  tile built to stop a second failure hiding behind the first was hiding the
  first. **The only defect this session whose wrong output an operator was
  looking at.** Blast radius verified twice: the first scan used the flat panel
  list and missed 9 panels nested in collapsed rows.
- **The era-currency scan could not see its own defect class.**
  `docs/HANDOFF.md` read *"Era-6 … is what accrues now"* across three cuts while
  the suite passed 14/14. Two root causes: the marker list carried the
  participle *accruing* but not *accrues*, **and every one of its four markers
  was lifted verbatim from the single sentence that motivated the file**; and
  `ERA_LITERAL` matched only the stamp form, so a claim naming the era by its
  **ordinal** had nothing to compare and was invisible however worded.
- **HANDOFF's STANDING FENCES published SIX cohort-resetting axes where
  CLAUDE.md publishes TEN**, omitting the universe, the hedger, the probe ticket
  and the heat cap — cut #11's own levers — while asserting "the TERMS below are
  unchanged". A session reading the fence where the session-bridge sends it
  could have restarted era-9 believing it SAFE.
- **C6** (the rung parser dropping bracketed families) was **latent**: the
  parser landed 2026-09-12, the only bracketed reports on disk are stamped
  2026-07-08..07-18, and today's report emits five unbracketed rungs. **No
  published number was ever wrong** — established by measurement, because the
  instruction was to treat every downstream number as wrong until re-derived.

---

## 6. TWO FALSE POSITIVES IN THE SESSION'S OWN HARNESSES

Recorded because the harness is an instrument and gets the same suspicion.

- A mutation run reported **"CAUGHT"** that was **pytest exit 5 — no tests
  collected**, because `-k` selected pins that did not yet exist (an earlier
  patch had aborted on a bad assert). Every mutation afterwards carries an
  exit-5 pre-check. `[[concepts/the-method]]` already holds this shape.
- A blast-radius scan used the flat `panels` list and missed panels nested in
  collapsed rows. Re-scanned with the file's own `_all_panels()` over 120
  panels; the conclusion held, but it was not *proven* until then.

Also: **two of three findings in the adversarial review of this session's own
fixes were MISATTRIBUTED** on first pass — the crash blamed on the new sweep was
in pre-existing code, and a "veto reordering" WARNING was moot because the gate
cannot be constructed at all with the malformed input.

---

## 7. TOOLING: DERIVE, DO NOT RECITE

`scripts/agent_brief.py` was added after four hand-typed briefing blocks drifted
from each other and from the truth — one carried "~18,020 rows /
mean_uniqueness 0.0868" while the live loader read 18,052 / 0.0867 **within the
hour**. It re-derives every value at call time, snapshot-stamps every live read,
**parses the ten-axis fence from CLAUDE.md rather than restating it** (degrading
CLOSED if the parse fails), and publishes n_eff as **competing routes with a
note that they disagree** rather than one scalar that silently picks a side.

Related: [[concepts/the-method]], [[concepts/overfit-battery]],
[[concepts/payoff-asymmetry]], [[synthesis/comparability-boundaries]].

## 8. THE VERIFICATION HELPERS, AND WHAT THEY FOUND ON THEIR AUTHOR

Added after §7, same session. Four helpers now exist to mechanise the checks
this session kept re-learning by hand. Every one of them found a defect in
work written HOURS EARLIER and believed correct — which is the finding, more
than the tools are.

**`scripts/checked.py`** — three-way green/red/no-tests, so pytest's exit 5
(nothing collected) can never read as a pass. It earned its keep the same day:
a background full-suite run reported "exited with code 0" — that was the
PIPE's code — while `checked.py` on the same run printed `rc=1 verdict=red`.
The laundering it exists to catch, caught on its own author, within hours.

**`scripts/verify_readonly.py`** — a filesystem census diff, not a source
grep, because the grep method had already failed on a script that writes under
`outputs/`.

**`scripts/mutation_sweep.py`** — generic mutation operators over the modules
a test file imports. Three defects in the tool itself, all found by RUNNING
it, none by reading it:
  (a) it mutated PROSE inside docstrings;
  (b) it invented SUBJECTS from paths merely NAMED in strings;
  (c) it classified by LINE, not by COLUMN, so English inside a comment or a
      string on an otherwise-real code line was still in reach — `# key -> ts`
      rewritten to `>=`, `# Friday == weekday() 4`, `"long" or "short"` in a
      type comment. Each would have been reported as a SURVIVOR, i.e. as a
      blind spot that is not there.

  Related, same root and worth carrying forward: **on Python 3.12+ an f-string
  is NOT a `STRING` token.** It tokenises as `FSTRING_START` /
  `FSTRING_MIDDLE` / `FSTRING_END`, so any tool filtering on `STRING` alone
  lets f-string prose through. This box runs 3.14.

  And a correction filed against the tool's own docstring: it claimed the
  `STRING` filter was what protected docstring interiors. Mutation testing
  refuted that — a multi-line docstring is ONE token whose start is its FIRST
  line, so interior lines carry no token start and are excluded by tokenize's
  STRUCTURE. Two mechanisms, not one. Both now pinned separately, because one
  pin across both cannot say which broke.

**`scripts/claim_check.py`** — reads commit messages back. Run over its
author's seven most recent commits it reported three failures and ALL THREE
were its own false positives (gitignored `outputs/` paths; a test FILE name
read as a test FUNCTION name). Both are now held by NEGATIVE pins. It cannot
check a measurement and says so, flagging bare counts as UNRUN and asking for
a re-derive pointer instead.

### 8b. THE SAME BOUNDARY MISS, TWICE, IN ONE SESSION

Two pins written this session passed for the wrong reason in the identical
shape: **a comparison tested away from its boundary.** A throttle pin ticked
inside and outside its window but never AT it; a line-range pin used line 12
against a 40-line file. Both survived `<` → `<=` / `>` → `>=`. Neither was
found by reading. Generic mutation found both.

The lesson generalises past these two files: **hand-picked mutants test what
the author was thinking about; a generic sweep tests what they were not.**

### 8c. THE HARNESS MUTATES THE WORKING TREE, AND NOTHING SAID SO

`scripts/mutate.py` edits repo files in place and restores them. A full
`pytest tests/` run and a sweep overlapped for a few seconds here. One test
failed on a mutant planted in `core/audit.py`, the suite reported a failure,
and that test passed in isolation immediately afterwards. **Neither tool said
a word, and the result was indistinguishable from a real regression.**

A silent corruption that looks exactly like a real failure is the worst
artifact this repo can produce. There is now a lock (`outputs/.mutating`) that
the harness takes and `tests/conftest.py` refuses to run against; both fail
OPEN on a stale lock, because a guard that can wedge the whole battery on a
leftover file is worse than the bug.

Same harness, second defect, same shape as everything above: it planted a
needle that matched TWICE at the first hit. Injecting a watched pair into
`config.json` landed in the skimmer's candidate list instead of the watch
lane's — the same string, two blocks apart — and reported SURVIVED for a pin
whose input had never changed. Now refused outright.

### 8d. TWO GATES WERE ALREADY RED ON `main`, AND NOTHING HAD NOTICED

Found only because the full definition-of-done matrix was re-run rather than
assumed:

  * **`tests/test_skip_census.py`** — a `pytest.skip` added earlier in the day
    took the static skip ratchet past its ceiling without the ratchet being
    raised in the same commit, which is what that gate's own rule requires.
  * **`bandit`** — findings in the verification helpers themselves (LOW
    severity, HIGH confidence; read the two columns separately per CLAUDE.md
    7(a)).

Both are now green. Neither was caused by the work being done at the time they
were found; both had shipped hours earlier under a "suite green" claim that
was true of a corpus that no longer existed. **A green is only as big as its
corpus, and the corpus moves.**

### 8e. NOT FIXED, RECORDED

`scripts/overfit_check.py` exits non-zero on OF-5 (DSR). That is the
**operator-adjudicated SETTLED state** — see `docs/HANDOFF.md`, the OF-5 row —
not a regression and not this session's to touch. Recorded here so the next
reader does not "fix" it.

CRLF drift: the source tree is `eol=lf` by `.gitattributes`, but a census this
session found tracked `.py` files carrying CRLF on disk. Git normalises on
commit, so **every diff hides it**. Cause is `Path.write_text` on Windows.
Byte-exact read/write is the fix and `scripts/mutate.py` already encodes it.
Count decays — re-derive; do not ship a repo-wide LF pin until the existing
drift is cleared, because a gate that ships red is worse than no gate.
