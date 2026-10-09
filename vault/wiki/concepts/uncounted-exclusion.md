---
title: "Uncounted Exclusion (a filter that drops a population without saying so)"
category: concept
summary: "An instrument that filters rows and does not count what it dropped — or counts them all under one wrong reason — reports a number about a population nobody chose, and the reader has no way to detect it; the type specimen discarded all 159 complete hedge round trips as 'partial or malformed', which flipped the sign of the median gross and therefore flipped the branch the go/no-go tool PRINTS. The winners-censoring instance — postmortem_summary records only EV-underperformers, so the winners' heat profile (15 positive rows in 266) never existed on disk and no evidence-derived stop geometry was derivable — CLOSED at the source by the complete trade-path ledger (trade_paths.csv, every finalized close, cause EMPTY for performers: named, not omitted), with its own caveats: history stays censored, and the new ledger carried a QA fixture row at filing (owed 65). NEW INSTANCE 2026-08-11 audit, the harder-to-see kind: two long-book flatten closes (ETH d5513dd5 / BTC e35c0a59) had NO thesis at close, so the postmortem writer produced no row AT ALL — an exclusion with no filter predicate to audit — FIXED with degraded orphan_close path rows in ml/postmortem.py (the row exists, marked degraded: named, not omitted)"
tags: [instrumentation, reporting, population, hedging, audit, cost, censoring]
sources: 3
updated: 2026-08-10
---

# Uncounted Exclusion

## The claim

Every analysis tool filters. **The defect is not filtering — it is filtering silently**, or
attributing every exclusion to one benign-sounding reason.

> **A skip counter with no breakdown by reason is the same defect as no skip counter at all.**

The reader sees a number and a sample size. Nothing in the output says *which* rows the sample
size describes, so **the reader cannot tell a deliberate scope from an accidental amputation** —
and the two look identical on the page.

## The type specimen: the go/no-go tool (2026-08-09)

`scripts/breakeven_test.py:126` counts **only `purpose == "entry"`** as the opening leg. All
**159 COMPLETE hedge round trips** are therefore discarded and reported under one line:

> **"165 skipped: partial or malformed"**

**None of them are malformed.** They close to **within 0.0% of opening size**. They were
excluded by a *deliberate-looking* predicate and then described by a *defect-sounding* label.

Reimplementing the tool's own accumulation both ways over `outputs/fills.csv`:

| | Shipped (`entry` only) | Corrected (`entry` \| `hedge`) |
|---|---|---|
| closed / skipped | **235 / 165** | **394 / 6** |
| gross | −3.03 | **−13.01** |
| fees | 59.23 | **374.96** |
| net | −62.27 | **−387.96** |
| **median gross** | **+0.0505%** | **−0.0303%** |

**The sign flips — and the sign selects which of two hard-coded branches the tool prints:**

| | printed verdict |
|---|---|
| shipped (`:214-230`) | *"This is NOT 'no edge' … that is exit geometry … **fixable without touching the signal**"* |
| corrected (`:231-241`) | *"**GROSS EXPECTANCY IS NEGATIVE** … no execution change, holding period, gate, filter or model creates expectancy that is not in the entries."* |

> **The two branches are opposite instructions about where to spend the next month.** A silent
> filter did not blur this tool's answer; **it inverted it.**

**Fix: ~10 lines, plus break the skip counter out by reason** — so *"partial"* and *"leg type
deliberately excluded"* can never again share a bucket.
([[sources/session-20260809-adversarial-audits]] §4.1)

## The other instances, same day, same shape

- **`scripts/cost_attribution.py:126`** — a **bare `continue` with NO skip counter**. The reader
  sees **n=1019** in one paragraph and a cost computed from **n=235** in the next, with nothing
  connecting them. The printed **0.668%/trade is correct for the 235 directional trades**; the
  honest blended figure is **0.7766%**. Severity is **not** the 1.16x gap — it is that **a
  cost-attribution tool is structurally blind to its own largest cost event.**
- **`main.py:1671`, `if not pos.is_hedge:`** — one predicate gating **two** subsystems. The
  entire **−325.70** hedge book is invisible to the performance ledger **and** to the
  consecutive-loss circuit breaker. **This is why 159 consecutive losing hedge round trips over
  10.4h never tripped the breaker: they were never recorded as losses.** An uncounted exclusion
  on a **risk control** is not a reporting defect; it is a **live risk defect**.

> The recurrence of one predicate — *"is this a hedge?"* — across three independent instruments
> and one circuit breaker is the finding. **The hedge leg is the systematically invisible half of
> this book**, and it is the loss-making half.

## The winners-censoring instance — CLOSED at the source (2026-08-11 ship, filed 2026-08-10)

The class ran one level deeper than a filtering *tool*: a filtering **ledger**.
`postmortem_summary.csv` records only trades that **underperformed** entry-time EV, so the
excursion paths of WINNING trades — the MAE envelope of trades that paid, *how much heat a good
trade takes before it works* — were **computed by `_excursions` and then discarded**: only
**15 positive-realized rows in 266** (re-verified at filing: 269/15), and the winners' heat
profile **did not exist on disk at all**. Any **evidence-derived stop geometry** was therefore
underivable from local data — a stop placed off the losers' MAE distribution alone is fitted to
the population that failed, the disposition-geometry defect
([[concepts/behavioral-isomorphism]]) measured from a ledger structurally unable to refute it.

**Closed by the complete trade-path ledger** (`ml/postmortem.py` `PATHS_COLS` →
`outputs/trade_paths.csv`, [[sources/directive-20260811-grand-synthesis]]): **every finalized
close, winners included**; `cause` is **EMPTY for a performer — named, not omitted**, exactly
rule 4 below (never let a scope decision wear a defect's label — nor hide it in an absent row).
The summary keeps its underperformer semantics byte-untouched. *Caveats filed with the close:*
the ledger accrues **from ship time only** (history stays censored); battery 14 was in flight at
filing; and the filing's own verification found a **QA fixture row already in the production
file** via the `paths_path` fallback ([[concepts/default-path-fallback-writes]] ninth instance,
[[synthesis/owed-measurements]] item 65) — the uncensored ledger must also be an
**uncontaminated** one before anything parameterizes from it.

## The orphan-close instance — a row the writer never saw (2026-08-11 audit, FIXED)

([[sources/session-20260811-operator-audit]] §6.2.) The winners-censoring close above fixed
*which* closes get a row; the since-6am audit found a class of closes that got **no row at
all**: the long-book flatten closes **ETH `d5513dd5`** and **BTC `e35c0a59`** carried **no
thesis at close** (an orphan close — the position ended without the entry-time thesis object
the postmortem writer keys on), so `postmortem_summary`/`trade_paths` simply **undercounted**
— an exclusion produced not by a filter predicate but by a **missing input**, which is the
harder kind to see: there is no `continue` to audit, the row just never happens.

**Fixed in `ml/postmortem.py` with degraded `orphan_close` path rows** — the row exists,
explicitly marked degraded, exactly rule 4 again: *named, not omitted*. A degraded row that
says "this close had no thesis" is data; an absent row is a silent scope decision the reader
cannot detect. *(The two historical orphan closes stay undercounted — history is not
rewritten; the fix is at the writer, forward-only.)*

## Why the direction is never random

The rows a tool finds easiest to exclude are the **irregular** ones: hedges, forced closes,
partials, probes. **Those are the loss-making rows.** So an uncounted exclusion has an expected
sign, and it is **flattering** — this class is the single most common mechanism behind
[[concepts/self-flattery-gradient]].

## The rules

1. **Count every skip, and count it BY REASON.** One aggregate skip number is worse than none,
   because it looks like diligence.
2. **A skip rate above a few percent is a finding, not a footnote.** `165/400 = 41%` skipped was
   printed on every run and read by nobody.
3. **State the population in the same breath as the statistic.** *"gross −3.03"* is not a claim;
   *"gross −3.03 over 235 directional round trips, 159 hedge round trips excluded"* is.
4. **Never let a scope decision wear a defect's label.** *"malformed"* told the reader the data
   was bad when the **tool** was narrow.
5. **When one predicate gates two subsystems, split it.** `if not pos.is_hedge:` had a defensible
   reading for the breaker and an indefensible one for the ledger; sharing the line forced one
   answer onto both questions ([[concepts/two-paths-one-quantity]], inverted — *one* path serving
   *two* decisions).

## The mirror class

[[concepts/pooled-populations]] is the opposite error: **merging** two populations that differ by
design, rather than dropping one. Both are failures to state **what population a number
describes**, and both flatter here.

## Related
[[concepts/pooled-populations]] · [[concepts/self-flattery-gradient]] ·
[[concepts/zero-is-not-a-reading]] · [[concepts/cost-truth]] ·
[[concepts/two-paths-one-quantity]] · [[concepts/honest-data-framing]] ·
[[sources/session-20260809-adversarial-audits]] · [[synthesis/the-money-path-thesis]] ·
[[synthesis/owed-measurements]] · [[sources/directive-20260811-grand-synthesis]] ·
[[concepts/behavioral-isomorphism]] · [[sources/session-20260811-operator-audit]] ·
[[entities/long-book]]
