---
title: "The Unbiased Economic Read (2026-08-09) — Gross Edge Is ~Zero, 100% of the Loss Is Costs, and the House Vocabulary Was Absorbing the Result"
category: source
summary: "The all-in P&L decomposition nobody had computed: gross trading P&L before ANY fees is −11.66 over ~250 closed positions (~−$0.05/trade, indistinguishable from zero) against 382.59 of fees — fees are 32.8x the absolute gross edge and 100% of the −394.25 all-in loss is costs. Three unrelated instruments corroborate a gross edge ≤ 0 (OOF AUC 0.43–0.48, champion Brier 0.24728 vs 0.25 coin, MFE median 0.18% vs ~0.65% round-trip cost). Files the operator's framing-conformity directive as a first-class rule, registers the structural blocker that the corpus carries no gross or fee column, and records the all-in reporting fix as AUTHORED-NOT-COMMITTED"
tags: [economics, pnl, cost, falsifiability, framing, corpus-schema, paper-mode, unbiased]
sources: 1
source_date: 2026-08
ingested: 2026-08-09
updated: 2026-08-09
---

# The Unbiased Economic Read (2026-08-09)

> **Operator directive (2026-08-09, the reason this page exists), verbatim:** *"make sure you're
> taking an unbiased opinion... Not making those unbiased opinions (true data) conform to my bot"*
> and *"this blocks the corpus from understanding real truth."*
>
> This page files the economic truth **and** the correction to the corpus's own framing habit. The
> second half is not commentary — it is the finding the operator actually flagged.

> **Paper/real boundary ([[concepts/paper-real-boundary]], domain rule 9).** Every dollar below is
> **sim-side**: fees are config constants (25/40 bps, themselves falsified —
> [[concepts/cost-truth]]), fills are RNG-at-limit, no queue, no depth. The *decomposition* is an
> exact identity over the bot's own ledger and is therefore true of the simulated book; the
> *dollar magnitudes* are not venue truth. See the directional caveat below — it cuts against
> the bot, not for it.

---

## 1. The headline number nobody had computed

All figures re-derived independently at filing time from the live `outputs/state.json`
(`saved_at` 1786291418, `portfolio` block), not quoted from a report:

```
starting_capital        5000.00
cash_balance            4604.02
realized_pnl_total      -208.31   (net of CLOSING-leg fees ONLY)
fees_paid_total          382.59   (the one complete fee ledger)
savings_balance            1.47
reserve_balance            0.26
```

`entry_fees_total` is **not a persisted key on this snapshot** (see §6) and was **recovered
exactly from the cash identity**:

```
entry_fees_total = starting_capital + realized_pnl_total
                   - savings - reserve - cash_balance
                 = 185.94
closing legs     = fees_paid_total - entry_fees_total = 196.65
```

Which yields the decomposition:

| Term | Value |
|---|---|
| **GROSS trading P&L, before ANY fees** | **−11.66** |
| Total fees paid (opening 185.94 + closing 196.65) | **−382.59** |
| **NET realized, all-in** | **−394.25**  =  **−7.89%** of starting capital |
| **Fees as a multiple of \|gross edge\|** | **32.8x** |

*(A fourth number for completeness: `net_pnl_all_time`, defined as the equity identity
`total_equity − starting_capital`, reads **−383.26** — the same −394.25 plus **+10.99** of open
unrealized. Quote whichever, but declare which.)*

### What this says, stated without softening

Over **~250 closed positions / 438 entry fills** the strategy produced **essentially zero gross
P&L** — −11.66 in total, **~−$0.05 per trade**, a quantity indistinguishable from zero — and paid
**382.59** in fees. **100% of the loss is costs.**

> **This is NOT the same statement as "the corpus is data-starved."** It is stronger, and it is
> unwelcome: **there is no measured gross edge to be starved OF.**

### Independent corroboration — three instruments, no shared mechanism

| Instrument | Reading | What it means |
|---|---|---|
| Out-of-sample AUC, logistic / gbt / mlp | **0.43 – 0.48** | at or **BELOW** chance — no demonstrated discrimination |
| Champion Brier ([[entities/ml-governor]]) | **0.24728** vs **0.25** for predicting a coin | beats nothing by **0.003** |
| Postmortem max-favourable-excursion | median **0.18%**, p90 **0.55%**, vs **~0.65%** round-trip cost | the **median trade never moved far enough IN ITS FAVOUR, at its single best moment, to cover its own costs** |

Three unrelated instruments, one verdict. This is the shape of a corroborated null, not of a
noisy sample.

### The directional caveat, stated because it cuts AGAINST the bot

The fill simulator is **documented-optimistic**: fills granted at the full quoted offset, no queue
position, no depth consumption, and pooled maker markout reads **+3.58 bps @5s** where real
passive fills should mark out **negative** via adverse selection
([[sources/session-20260807-fleet-findings]], [[sources/session-20260808-morning-batch]]).

Therefore **real-execution gross would be WORSE than −11.66, not better.** The honest statement
is not "gross is −11.66"; it is:

> **gross edge ≤ 0.**

---

## 2. The framing correction — the part the operator flagged

The repo has a fluent internal vocabulary: *"cold-start corpus"*, *"data-starved"*, *"exploration
buys labels"*, *"tuition"*, *"the learning curve is CLIMBING"*, *"DoF budget"*, *"era exclusion"*.
**Every one of those terms is individually defensible** and each has a real page in this wiki.

Used together they compose into an explanation that **absorbs almost any bad result**:

- a losing week becomes **tuition**;
- a failing gate becomes a corpus that **needs to grow**;
- a coin-flip model becomes a **learning curve that has not plateaued**.

### I demonstrated the failure mode myself, twice, this session

Both belong on the record as evidence for the rule, not as re-litigation — **both are already
corrected in place**:

1. **The overfit-stage red attributed to the house narrative.** I wrote that the red was "the
   cold-start corpus failing honestly, exactly as the 2026-08-08 DoF adjudication predicts" — a
   sentence that **fit the data to the house story**. The actual cause was **corpus corruption
   from a migrator bug** ([[sources/session-20260809-corpus-corruption]]). The vocabulary made a
   **data-integrity incident look like an expected milestone**, and it **reached the wiki before
   it was caught** ([[sources/session-20260808-night-staleness-overfit]], now struck-and-corrected
   in place).

2. **A measurement-grammar sentence describing something unmeasured.** `36fcfd6e`'s record said
   *"the identical red reproduces on the parent commit"* — **asserted, never run** — and it
   carried the entire deploy argument. Running it would have exposed the +9,272-row corpus
   corruption the same evening ([[concepts/false-green]], mirror specimen).

> These are the same disease in two organs: **(1)** an explanation flexible enough to swallow a
> data bug, and **(2)** a claim wearing the costume of a measurement. Both were produced by the
> agent maintaining this corpus, which is precisely why the rule below has to be mechanical
> rather than a resolution to be more careful.

### The rule

Filed as a first-class concept: **[[concepts/unfalsifiable-explanation]]** —
*an explanation that cannot be wrong is not an explanation.*

Before accepting any house-vocabulary account of a bad number, **state what observation would
falsify it**:

| Term | Its implicit prediction | The measurement | Verdict |
|---|---|---|---|
| "data-starved" | gross edge **> 0** that is merely hard to **select on** | gross **−11.66 (~0)** | **falsified as a complete account** |
| "exploration is tuition" | the labels are **teaching** something | OOF AUC **< 0.5** after **305** live labels | **not yet** — the tuition has bought no measured discrimination |

**Neither term is banned. Both must now carry their falsifier.**

---

## 3. The structural blocker — the corpus cannot see its own costs

**Registered as owed item 50, HIGH** ([[synthesis/owed-measurements]]).

`outputs/signal_history.csv` carries **`net_pnl_usd`** and **no gross column** and **no per-row
fee column** — verified at filing against the live **93-column** header (`net_pnl_usd` is column
69; the only fee-adjacent column in the file). Consequences, all structural rather than
cosmetic:

- **No row can distinguish "the signal was wrong" from "the signal was right and costs ate it."**
- **No offline analysis can compute gross edge by subpopulation** — by asset, regime, horizon, or
  signal strength — which is **the single most decision-relevant question open right now** (§5).
- **`ml/postmortem.py` cannot decompose either.** Its terminal fallback bucket
  (`postmortem.py:334`, `return "underperformance"` — *"closed below expectation without a single
  dominant cause"*) absorbs **202 of 264 postmortems = 76% of trades die undiagnosed.** The
  taxonomy's other buckets (`cost_overrun`, `alpha_wrong`, `regime_shift`, `fear_event`) are
  fine; **the inputs needed to distinguish them are missing.**
- **The binary win/loss label conflates the two cases at the point where the MODEL learns**, so
  the learner is **structurally incapable of learning the distinction no matter how many rows
  accrue.** This is the sharpest reading on the page: it means corpus growth *cannot* fix it.

### Proposed fix (own change, own battery — explicitly NOT bundled)

Add **`gross_pnl_usd`** and **`fees_usd`** as **trailing** corpus columns via the established
extend-with-defaults ritual (header + `migrate_history` pad + the downstream pins), backfilling
history offline from `outputs/fills.csv`, which carries per-fill `fees_delta_usd` keyed by
`position_id`.

The migrator idempotence fix (`3c0debd7`) makes the resulting rotation safe — **the exact path
that corrupted the corpus is now fixed and tested** ([[concepts/migration-idempotence]]). Note
the backfill inherits the ledger gap in §7.

---

## 4. Also found, unfixed — the fills ledger is short by 6.24

`outputs/fills.csv` fee ledger sums **376.35** across **1,019 rows** (column `fees_delta_usd`,
re-summed at filing) against `fees_paid_total` **382.59** — **6.24 (1.6%) of fees never reach the
ledger.**

So **every offline cost analysis built on `fills.csv` reads optimistic by that much**, including
the §3 backfill if it is built naively. This is a **separate defect** from the reporting one in
§6. It updates existing register entry 18
([[synthesis/open-contradictions-register]]), whose earlier snapshot read 382.28 vs 376.04.

---

## 5. What the unbiased read implies for next work

**Stated as adjudication input — these are not decisions taken here.**

1. **Search the free population first.** The **9,570 CANDIDATE rows are counterfactual and cost
   ZERO fees**, versus **305 live rows that cost ~382.59**. If gross edge is to be found, it can
   be searched for in the free population **without paying another cent of fees**. **Any plan
   that proposes "trade more to learn more" should first justify why the free, 31x-larger sample
   cannot answer the same question.**
2. **The horizon evidence is the one live lead — and it is a GEOMETRY lead, not a model lead.**
   Shadow win rate rises **monotonically 22.3% → 30.4% → 35.4%** at **108 → 216 → 432** bars,
   i.e. **exits are early relative to the cost being paid**
   ([[comparisons/horizon-96-vs-24-bars]]).
3. **`config_guard` already says the geometry verdict out loud** and it should be quoted in any
   planning ([[entities/config-guard]], `core/config_guard.py:3104-3107`, verbatim):

   > *"derived entry bar {0.990} exceeds 0.90 - the payoff geometry (tiers/stop/fees) is so
   > cost-heavy that no plausible model clears it; fix the geometry, the bar is only reporting
   > it"*

   **A required win probability of ~99% is not a modelling problem.**

---

## 6. Shipped this pass — the reporting half of the fix

> ⚠️ **STATUS AT FILING: AUTHORED, BATTERY IN FLIGHT, NOT COMMITTED.** Verified at filing:
> `git status` shows `core/state.py`, `core/persistence.py`, `runner.py`, `scripts/gc_pusher.py`
> **modified** and `tests/test_pnl_all_time.py` **untracked**; `HEAD` is `8e9d7e6f`. The live
> `outputs/state.json` **does not carry the `entry_fees_total` key**. Per governance rule 12
> ("confirmed" = measured, battery-green, **committed**) this section is **work in flight, not a
> shipped fact** — the §1 decomposition does **not** depend on it (it was recovered from the cash
> identity independently). Filed this way deliberately: **stating it as shipped would be the
> exact conformity error this page exists to correct.**

**Operator-reported symptom:** *"net pnl all time doesn't match up with equity."*

**Verified exactly — no money was missing; the STATEMENT was wrong:**

```
equity = cash 4604.02 + savings 1.47 + reserve 0.26 + unrealized 10.99 = 4616.74
cash   = 5000 − 208.31 − 185.94 − 1.73 (pools)                        = 4604.02
```

**Cause.** `core/state.py` `record_entry_fee` debits **opening-leg** fees (entry **and** hedge —
`main.py:2019-2020` fires for every non-exit leg) **straight to cash**, while
`record_realized_pnl` nets **only the CLOSING leg**. So **185.94 of 382.59 lifetime fees (49%)
appeared in no P&L figure at all** — visible only in equity and `fees_total`. This is the same
invisible-fee-channel class the 08-07 reconciliation found
([[sources/session-20260807-pnl-reconciliation]]), now measured on the whole book rather than one
incident.

**The change.**
- `PortfolioState.entry_fees_total` accumulator.
- `net_pnl_all_time()` — **defined as the EQUITY IDENTITY, not a sum of counters**, so a future
  counter omission cannot hide. *(This is the design lesson: the bug existed because a P&L number
  was a sum of the counters someone remembered.)*
- `realized_net_all_in()`.
- Persisted, with an **exact one-time backfill from the cash identity** for pre-upgrade snapshots
  — verified live to recover **185.94**.
- Four new status keys (`starting_capital`, `entry_fees_total`, `realized_net_all_in`,
  `net_pnl_all_time`) + `gc_pusher` metrics.
- **8 red-first tests** in `tests/test_pnl_all_time.py`, including the backfill through the
  **REAL** `StateStore` and a **pool-skim invariance** check.

**Also corrected:** `total_equity`'s docstring omitted the **reserve** term it has always added.

**Deliberately HELD:** dashboard regeneration, pending the in-flight panel audit, so **one**
regeneration covers all findings (boards are **generated** — never hand-edited).

---

## 7. What this page does and does not move

**Moves:**
- [[synthesis/the-money-path-thesis]] — supplies the gross/fee decomposition the thesis had
  asserted qualitatively ("the book's entire drawdown is fees") but **never computed**. It is now
  a number: **32.8x**, and gross ≈ 0 rather than merely small.
- [[concepts/dof-budget]] and [[concepts/priced-bleed]] — both now carry falsifiers.
- [[synthesis/owed-measurements]] item **50** (new, HIGH).

**Does NOT move:**
- **[[concepts/payoff-asymmetry]] is not refuted by this page** — it is *relocated*. The
  asymmetry (0.561 vs 0.750 needed) is a statement about the **shape** of the gross distribution;
  this page says the **mean** of that distribution is ~0 before costs. Both hold; the second is
  upstream of the first.
- The two 08-02 nulls (no entry-timing signal; no surviving bracket) — **unmoved, and now
  better explained**: a search for edge inside a population whose gross mean is ~0 is expected to
  return null.
- Nothing here licenses widening any gate ([[concepts/never-widen-a-gate]]).

## Related
[[concepts/unfalsifiable-explanation]] · [[synthesis/the-money-path-thesis]] ·
[[concepts/cost-truth]] · [[concepts/payoff-asymmetry]] · [[concepts/dof-budget]] ·
[[concepts/priced-bleed]] · [[concepts/paper-real-boundary]] · [[entities/historystore]] ·
[[entities/config-guard]] · [[synthesis/owed-measurements]] ·
[[synthesis/open-contradictions-register]] · [[sources/session-20260807-pnl-reconciliation]] ·
[[sources/session-20260809-corpus-corruption]]
