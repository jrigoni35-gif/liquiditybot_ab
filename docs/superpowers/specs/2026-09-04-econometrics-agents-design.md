# Econometrics measurement plane + two analyst agents — design

**Date:** 2026-09-04 · **Status:** design approved (agent roster approved
explicitly; sections 2–4 presented, no objection raised before the operator
redirected to a whole-bot review) · **Class:** SAFE — scripts/, tests/ and
`.claude/agents/` only. No order placement, no fill, no sizing, no geometry,
no fee booking, no order lifecycle. Mints no execution era.

---

## 1. Why

The bot's decision path is the most-governed code in the repo. The
measurement plane that observes it is the least-governed — and CLAUDE.md's
mindset section is a register of what that asymmetry has cost. This design
adds estimation capability *only* to the measurement plane, and spends it on
questions the repo has already proven it cannot currently answer.

Three constraints bound everything below, and none of them is mine to lift:

1. **Model freeze** (2026-08-10 operator adjudication) — no new families,
   features, or meta-labeling.
2. **Era-6 accrual moratorium** — entry decisioning, sizing, stop/exit
   geometry, the fill simulator, fee booking and the order lifecycle are
   COHORT-RESETTING.
3. **Engine-scope dependency hygiene** — `tests/test_dependency_hygiene.py`
   forbids `pandas`, `polars`, `duckdb`, `matplotlib`, `seaborn`, `plotly`,
   `statsmodels`, `pyarrow` at engine scope, and the test passes today.

So: libraries live in `scripts/`, agents read and write documents, and
nothing here can change what the bot trades.

### What the review of 2026-09-04 established

The whole-bot review produced the numbers this design must serve. They are
recorded here because they set the *requirements*, not as decoration:

- Label geometry gross expectancy **+0.1698%** per barrier-resolved path,
  pre-cost (n=13,763; target-hit 0.468 vs breakeven 0.429).
- Round-trip cost **0.60%** (`pretrade.maker_fee_bps` 22 /
  `taker_fee_bps` 38, `ml.label_round_trip_cost_pct` 0.6).
- Live cohort net mean **−0.6881%** per trip; gross mean −0.0002%
  (SE 0.2469%).
- **Effective n 26.1 of 92 nominal** (mean uniqueness 0.284) — SE optimistic
  by ×1.88; resolvable-edge floor **~0.9265%**.
- **92% of the accrued cohort are probe admissions** — `p_win =
  max(p_win, 0.7)` against a bar near 0.567, so they clear by construction.
  The gate's own words: *"This cohort measures the EXPLORATION CONSTANT, not
  the selector the verdict is about."*
- Fee-free gross **disagrees in sign** between populations: entry-opened
  only (n=334) −0.0136%, win 56.6%; with hedge-opened (n=493) −0.0146%,
  win 43.2%.

**These numbers are AS-OF 2026-09-04 and decay** (CLAUDE.md's own rule: a
number written into a document becomes a false claim). Re-derive with
`LB_OUTPUTS=<corpus> python scripts/cohort_eval.py` — which honours
`LB_OUTPUTS` as of this session's fix; before it, the gate could only read the
repo-root `outputs/`. At the time of writing the counter had already moved
92→94 trips and effective n 26.1→28.0.

The structural consequence, which this design exists to make measurable: the
**detection floor (~0.93%) is roughly five times the effect the design
targets (~0.17%)**. A measurement plane that cannot say this out loud is not
worth building.

---

## 2. Agents

Governed by the referee lattice: *blind analysts → consensus diff → operator
head → one learner; no evaluator ever feeds the learner.* These are analysts.
They read primary data, write dated reports, and cannot write to
`config.json`, the model, or any decision path. **They do not read each
other** — independence is what makes a disagreement informative rather than
an echo.

### 2.1 `asset-econometrician`

**Mandate.** For each of the 7 core pairs (PAXG, ETH, BTC, SUI, ARB, MINA,
FLOW), answer *what is estimable here, and with what uncertainty* — never
*what predicts*, which is the model's job and is frozen.

**Reads:** `signal_history.csv`, `fills.csv`, `equity.csv`, the candle store.

**Hard boundaries (enforced by the battery in §3, not by good intentions):**
- segments by `exec_era` before any pooled statistic;
- reports **effective n**, never row count;
- decomposes any label-skill claim into RESOLUTION vs DIRECTION per
  CLAUDE.md rule 7(f) before the word "signal" appears.

**Writes:** `docs/quant/YYYY-MM-DD_asset_econometrics.md` + JSON sidecar.

### 2.2 `flow-forensics`

**Mandate.** Attack one registered, dated defect: *"honest maker and layering
attacker score byte-identically."* This is a **separation** problem. It is
the highest-value target in the repo because 99.6% of vetoes are FLOW+MINA
while BTC has zero — i.e. the detector's output is currently explained better
by asset liquidity than by conduct.

**Reads:** `audit.jsonl` event sequences, book snapshots, `manip_suspect` /
spoof scores, `fills.csv`.

**Method.** Treat honest-maker and layering as two hypotheses over
*order-lifetime distributions*: cancel-to-fill hazard, near-touch
replenishment timing, depth-pull autocorrelation. Test whether **any**
statistic separates them.

**A negative result is a first-class deliverable.** "These two are not
separable from what we log" tells the operator to change what is logged, and
is more valuable than a detector tuned until it looks decisive.

**Boundary:** reports only. It cannot alter the live manip gate — that is
`execution/` and cohort-resetting.

**Writes:** `docs/quant/YYYY-MM-DD_flow_forensics.md`.

### 2.3 Existing three, reused unchanged

`liquiditybot-engineer` implements what the analysts justify (it carries the
moratorium-classification duty). `fintech-quant-researcher` sources method
choices from literature so estimator selection is not taste.
`market-conduct-compliance` reviews any `flow-forensics` finding before it
could influence order behaviour — it already exists for exactly this.

### 2.4 Rejected: a "selection referee"

An agent that both proposes and scores estimators is the shape CLAUDE.md
warns about — *a gate's release condition must never depend on the thing it
blocks*. The lattice already has consensus-diff and operator-head layers.
**The operator head stays the operator.**

---

## 3. The econometric battery

`scripts/asset_econometrics.py`. One module, two clearly separated concerns.

### 3.1 New estimation

| estimator | why it is new | anti-fit guard |
|---|---|---|
| HAC / Newey–West SEs | **nothing** in the repo is autocorrelation-consistent, yet `walkforward_lab.py` measures serial dependence in the trip sequence — every SE printed today assumes away what the repo already knows is there | lag from Newey–West's own rule, never tuned |
| GARCH(1,1) realized vol | `sigma_bar_pct` has no benchmark | reported beside, never replacing |
| Structural-break tests | placed at the **known** cut boundaries #7/#8/#9 | a *searched* break point is a fitted parameter — searching is forbidden |
| Cointegration on basis | `basis_dir` carries w=−0.220 (third-largest weight) on an untested premise | per-asset, era-segmented |

### 3.2 Cross-checks of existing hand-rolled statistics

The-method rule 2 made concrete — *one number from one tool is a hypothesis*:

| hand-rolled | cross-checked against | why it matters |
|---|---|---|
| `_norm_cdf`, `_z_quantile` (`gate_truth_report`) | `scipy.stats.norm` | these silently set **every** CI and MDE the gate prints |
| `_rank_auc`, `_spearman` | `scipy.stats` | rank statistics feed the efficacy reports |
| `pbo_cscv` (`ml/overfit.py`) | independent CSCV implementation | the overfit verdict rests on it |
| `autocorr` (`walkforward_lab`) | `statsmodels.acf` | feeds the effective-n story |

**On disagreement the hand-rolled version wins by default** until the
disagreement is explained. Precedent: 2026-08-21, the C++ diode disagreed with
Python on accrued trips and *the diode was wrong*. A referee that disagrees is
INTERESTING, not automatically right.

### 3.3 Explicitly excluded

No new features. No re-weighting. No method horse-race with a winner picked —
that is argmax selection, and CLAUDE.md's rule is *"PBO measures the deployed
selection rule, never argmax"* with OF-4 adding *"never tune a gate to a
backtest peak."*

---

## 4. Data flow

```
pc-live bundle ──┐
signal_history   ├─→ asset_econometrics.py ─→ docs/quant/*.md + JSON sidecar
fills / equity   │      (era-segmented,             │
audit.jsonl ─────┘       effective-n)               ↓
                                          agents read the sidecar
                                                    ↓
                                       docs/HANDOFF.md  (the router)
```

Cross-session sharing rides existing mechanisms — `paper-telemetry` bundles
inbound, `HANDOFF.md` as the durable record. **No new channel**, deliberately:
ISO-1 was caused by a second write path nobody was watching. Since the ISO-1
fix, cloud sessions no longer push bundles, so session findings land in the
handoff, which every session reads first.

---

## 5. How "don't cheat" is enforced

Four mechanisms, all mechanical:

1. **Pre-registration.** Every hypothesis is written to a dated decision table
   *before* the battery runs, reusing the signed-decision-table pattern of
   `docs/quant/2026-08-16_era4_readout_decision_table.md`. A result without a
   prior registration prints as EXPLORATORY and may not be cited as evidence.
2. **Era segmentation is a hard gate.** The battery **errors** rather than
   warns on any pooled statistic spanning an `exec_era` boundary. `SD-012`
   already flags this hazard; here it becomes enforced.
3. **Effective n everywhere.** Every SE divides by `n_eff`. A statistic that
   cannot compute its own `n_eff` does not print.
4. **Resolution/direction decomposition mandatory** before the word "signal",
   with day-block CIs.

Structural backstop: the agents are blind analysts whose output reaches no
learner, so a wrong conclusion costs a document, not an era.

**Expected outcome, stated in advance so it cannot be spun later:** this will
mostly produce *negative* results — wider CIs than current reports imply, and
plausibly "not separable from what we log" on manipulation. A battery that
only ever confirms is one to distrust.

---

## 6. Testing

- Every new estimator pinned against a **hand-computed or analytically known**
  fixture, matching `scripts/ground_truth_metrics.py`'s existing stance
  ("implemented from its definition and pinned by tests against hand-computed
  fixtures").
- Cross-check pairs asserted to agree within an explicit tolerance; the
  tolerance is a pin, not a knob.
- The era-segmentation gate mutation-verified: a deliberately era-spanning
  input must raise.
- Library absence handled by `pytest.importorskip` so a box without the stack
  still runs the suite — the `fc8ba805` pattern.
- `requirements.txt` untouched; `tests/test_dependency_hygiene.py` must stay
  green, including `test_suite_collects_without_optional_analysis_stack`.

---

## 7. Staging

**This design is stage 1 and stops at evidence.** Any use of these findings to
change the live feature set, sizing or gates is stage 2: a separate operator
adjudication that mints an execution era, with stage 1's reports as its
evidence base. Nothing here pre-commits that decision, and nothing here may be
cited as having made it.

---

## 8. Open questions for the operator

1. **Does the era-4 gate keep accruing?** The review's finding — 92% probes,
   effective n 26.1/92, detection floor 5× the target effect — argues it is
   measuring the exploration constant. Continuing to fill it buys a verdict
   about a selector that did not select. Not this design's call.
2. **Which lever does stage 2 pull if the evidence supports one** — horizon
   (earn more than 0.60%) or cost (pay less than 0.60%)? The exit-asymmetry
   read already rules out exit-policy changes: *"median loss exceeds the worst
   adverse excursion by +0.437% … this is COST, not a stop being hit too
   tight."*
