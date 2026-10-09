---
title: "Public-Record Data Atlas — free routes to algo/prop/HFT economics, and the traps in them"
category: synthesis
status: SETTLED
summary: "First filing of the free public-record lanes into algo/prop/HFT firm economics, with the traps that make naive use wrong. HIGHEST-VALUE LANE: UK Companies House full accounts are FREE and carry a real P&L (Jane Street Financial Ltd FY2025 revenue USD 71,495k / profit 49,153k; Citadel Securities Europe FY2024 USD 310,766k; HRT Europe FY2024 GBP 84,309,989; XTX Markets Ltd FY2025 GBP 62,041k with ZERO staff; Tower Research Europe FY2024 PBT MINUS 467,377). CRITICAL CAVEAT that must survive: Optiver UK and Jump Trading International 'revenue' is INTERNAL RECHARGE under transfer pricing, so ranking these seven on revenue is meaningless and was REFUSED. Two REFUTED claims recorded so they are not re-derived: FINRA weeklySummary carries NO firm identity (firmCRDNumber EMPTY on all 5,000 rows pulled), and SEC Rule 606 net payments are wholesaler COSTS, not revenue — any join reading them as market-maker revenue is INVERTED. CapitolTrades / STOCK Act REJECTED for this bot on cadence, identification, legal and literature grounds (now a row on evidence-closed-register). Statistics: bucket-midpoint imputation overstates the conditional mean 175-326%; assumption-free bounds do NOT shrink with n (15x ratio at any n); detecting a 26bps 6-month abnormal return needs 52,248-145,135 independent trades; with 535 candidates E[max z] under pure noise is 2.93 and E[max Sharpe | ZERO SKILL] is 0.63 at N=535/T=24 — the same correction overfit_check.py applies. And the cross-population correlation between House PTRs and SEC Form 4 is NOT COMPUTABLE: time-aligned shared-ticker intersection is EMPTY, n=0 pairs."
tags: [external-data, public-record, hft-economics, disclosure, multiplicity, effective-n, refuted-claims, availability]
sources: 1
updated: 2026-08-30
---

# Public-Record Data Atlas

**What this page is.** The first vault filing of the *free, keyless,
machine-readable* routes into the economics of the firms on the other side of
this book — and, more valuably, the **traps** that make each lane produce a
confident wrong number. Measured 2026-08-30;
source: [[sources/session-20260830-audit-wave-and-external-data-atlas]].

**Read [[concepts/availability-failure-mode]] first.** This project's standing
rule is that *no keyless machine-readable source = rejected regardless of
evidence quality*. Everything on this page passed availability; that is the
only reason it is here, and it is **not** an argument that any of it should
be wired to anything.

**Paper/real boundary** (domain rule 9): every figure here is
**venue-data-side / public-record-side**. None of it is sim output, and none
of it is evidence about this bot's own execution.

## 1. The lane that works — UK Companies House full accounts

**[K] Companies House full accounts are FREE and carry a real profit-and-loss
account.** This is the single highest-value finding on the page: the UK
subsidiaries of the major algo/prop/HFT houses file statutory accounts that
are public, downloadable, and audited — a level of disclosure with no US
equivalent for private partnerships.

| Firm (UK entity) | Company no. | FY | Reported "revenue" | Notes |
|---|---|---|---|---|
| Jane Street Financial Ltd | `06211806` | 2025 | **USD 71,495k** (profit **49,153k**) | trading entity |
| Citadel Securities (Europe) Ltd | `05462867` | 2024 | **USD 310,766k** | trading entity |
| HRT Europe Ltd | `06796079` | 2024 | **GBP 84,309,989** | trading entity |
| XTX Markets Ltd | `09415174` | 2025 | **GBP 62,041k** | **ZERO staff** |
| Tower Research Capital Europe | `06005750` | 2024 | **PBT −467,377** | a LOSS |
| Optiver UK | `11478632` | — | ⚠️ **INTERNAL RECHARGE** | see below |
| Jump Trading International | `05976015` | — | ⚠️ **INTERNAL RECHARGE** | see below |

> [!danger] **THE CAVEAT THAT MUST SURVIVE ANY QUOTATION OF THIS TABLE.**
> **Optiver UK (`11478632`) and Jump Trading International (`05976015`)
> report "revenue" that is INTERNAL RECHARGE, not trading revenue** —
> the accounts describe it as *"charged to group undertakings"* /
> *"back-office support services to affiliates"* under **transfer pricing**.
> These entities are cost centres billing their own group; the number is a
> markup on expenses, not a P&L from markets.
> **Ranking these seven firms on "revenue" is therefore MEANINGLESS, and
> was REFUSED** rather than produced with a footnote. A table that puts a
> trading entity and a service-recharge entity in one sorted column is a
> [[concepts/false-green]]-class artifact: it reads like a comparison and
> is not one. **The column above is deliberately labelled "reported
> revenue", never "revenue".**

Two structural reads worth keeping [I]:

- **XTX's ZERO staff at GBP 62,041k** is the cleanest available public
  illustration that the licensing/IP entity and the trading entity are
  routinely different legal persons. Any per-head or per-firm economics
  computed off a single UK entity is computing a **legal artifact**.
- **Tower Research Europe at a PBT of −467,377** is the useful one for this
  project's morale and its epistemics both: a named HFT house's European
  entity **losing money in a filed, audited account**. It is a standing
  counterexample to the premise that these firms print money everywhere.

**Access note [K]:** **SEC hosts require an SEC-format declared
`User-Agent` — literally `"Name email"`.** A generic UA returns **403**. This
is the availability boundary being *soft*, not closed: the data is free, but
the fetch fails silently-ish for anyone who does not know the convention.

## 2. Two REFUTED claims — recorded so nobody re-derives them

Filed per [[concepts/no-orphan-claims]] and domain rule 3 (*retractions are
first-class content*). Both were **believed, then measured, then abandoned.**

**(i) FINRA `weeklySummary` is NOT a firm-attributed sizing lane.** [K]
It was believed to be *"the only free FIRM-ATTRIBUTED sizing lane"* available.
A **5,000-row pull measured `firmCRDNumber` EMPTY on every row.** The dataset
**carries no firm identity at all.** Any plan resting on attributing volume to
a named firm through this endpoint is dead at the source, not merely
imprecise.

**(ii) SEC Rule 606 net payments are wholesaler COSTS, not revenue —
the sign is INVERTED.** [K] Rule 606 net payments are money the
**market-maker PAYS to acquire retail order flow**. Reading them as
market-maker *revenue* inverts the direction of the cash. **Any join built on
that reading produces a number with the wrong sign**, and it would look
perfectly plausible — bigger payments would read as a more successful
wholesaler, when they are the price of the flow.

Both belong to the same class as the register on [[concepts/the-method]]: a
confident instrument, wrong, with nothing flagging it. Neither was caught by
inspection; both were caught by **pulling the data and looking at the actual
column**.

**A third, same-day, same-shape refutation from a neighbouring lane:**
[[sources/pyth-evaluation-2026-08-30]] — Pyth's free surface was believed to
be keyless real-time and historical price; the **runtime** returned **401 /
404 / 401** on every price endpoint while only metadata search returned 200.
Same lesson, different vendor: **the documentation said "No auth" and the
backing REST disagreed.** Filed here because it is the same availability
question this page exists to answer, and because *three* refutations in one
day, all of the form "the source is not what its documentation claims", is a
rate worth noticing before trusting the next lane's README.

## 3. Disclosure statistics — what the numbers can and cannot support

All computed 2026-08-30. **[K] but un-re-runnable as scripted** — the
computation lived in a **session-scoped scratchpad script**
(`…/scratchpad/disclosure_stats.py`) that is not in the repo and will be
garbage-collected: registered as [[synthesis/owed-measurements]] **item 111**,
with the closed forms stated here so the numbers can be regenerated without
it.

**Bucket-midpoint imputation is badly biased, in the flattering direction.**
STOCK Act amounts are RANGE-BUCKETED; imputing the midpoint of the bottom
bucket (`$1,001–$15,000`, a **15x span**) **overstates the conditional mean by
175%–326%** across Pareto α ∈ [1.0, 2.0], and by **202%** for lognormal
σ = 1. Equal-weighted across all 7 buckets the overstatement is **43.2%**. The
mechanism is that realistic within-bucket distributions are right-skewed with
mass at the floor, and the midpoint sits far above the conditional mean.

**Assumption-free bounds do NOT shrink with n — and this is the part that
kills the lane.** 1,000 disclosures all in bucket 1 bound the total in
**[$1,001,000, $15,000,000]**: a **15x ratio regardless of n**. More data
does not narrow an interval whose width is set by the *coding of the
variable*, not by sampling error. This is [[concepts/location-not-magnitude]]
in a new domain: the disclosure tells you *that* a trade happened, never *how
big*.

**Power — why the literature's null is weaker than it sounds.** Detecting a
**26bps** 6-month abnormal return requires **52,248–145,135 INDEPENDENT
trades** at a 6-month σ of 21%–35%; clustering inflates the SE a further
**1.40x–2.43x**. So the published null (§4) is **ABSENCE OF EVIDENCE for small
effects** while it **credibly EXCLUDES large ones** — a distinction this
corpus has paid for before under a different name
([[concepts/average-uniqueness-and-ess]]).

**Multiplicity — the number that connects this to our own gates.** With
**535 candidates**, Bonferroni demands **|z| > 3.91**, and **E[max z] under
pure noise is 2.93**. A naive `t > 1.96` claim about an **ex-post-selected**
member does not even clear **the expected maximum of noise**. The DSR
analogue: **N = 535 trials over T = 24 periods gives E[max Sharpe | ZERO
SKILL] = 0.63.**

> [!important] **This is the same correction `scripts/overfit_check.py`
> applies (OF-5, Deflated Sharpe), and it is exactly why TRIALS-1 — the
> measured trial count for DSR — is docketed.** The external domain is
> incidental; the arithmetic is the house's own. A selected-best result
> without its trial count is uninterpretable here for the same reason it is
> uninterpretable there.

## 4. Disclosed-trade behavior — and a correlation that does not exist

Two samples pulled 2026-08-30 [K]: **House PTRs, n=611 records / 85 documents
/ 58 filers**, filing window **2026-07-01 .. 08-27**; **SEC Form 4, n=68 rows /
25 filings / 22 persons**.

**THE HEADLINE IS A NEGATIVE, and it is the most useful thing here: the
cross-population correlation is NOT COMPUTABLE.** After time-aligning both
populations to the same **market** period, the **shared-ticker intersection is
EMPTY — n = 0 pairs.** The single raw MMM overlap that appeared before
alignment is an **artifact of pairing on the FILING window instead of the
TRANSACTION window** — precisely the [[synthesis/comparability-boundaries]]
error, committed on someone else's data. **Detecting r = 0.3 would need ≥ 85
time-aligned shared tickers.** So the honest statement is *"not computable at
this sample"*, never *"no relationship"*.

**Two composition facts that invalidate naive reads of Form 4** [K]:

- **66.2% of Form 4 rows are COMPENSATION MECHANICS** (codes M/A/C/F/D/L/J).
  Only **33.8%** are open-market transactions. A "insiders traded X" count
  that does not filter by code is mostly counting vesting and withholding.
- **Natural-person purchase dollars are $239,605.15 — 0.81% of a headline
  $29.65M**, the remainder being **fund subscriptions**. The headline is
  three orders of magnitude away from the thing a reader thinks it measures.

**And the unit trap, which is the transferable lesson** [K]: on the same
sample, the P:S ratio is **0.353 by row count**, **5.99 by shares**, and
**9.875 by dollars** — *three units, OPPOSITE directions*. **A buy/sell ratio
without a stated unit is not a number.** This is the 2026-08-27 reading
discipline (a) verbatim — *a ratio is not a number until its DENOMINATOR is
read from the code that computes it* — recurring on external data.

## 5. CapitolTrades / STOCK Act — REJECTED for this bot

Full row on [[synthesis/evidence-closed-register]]. Summarized here because
the reasons are independently instructive; **each is sufficient alone.**

- **CADENCE — already closed, twice, by this corpus.** The evidence-closed
  register's 13F row closes the **45-day-lag cadence class**, and
  congressional PTRs share that cadence. Its equity-leads-crypto row closes
  hourly leads because **documented transmission is MINUTES** — this feed is
  **30–45+ DAYS**. The rejection does not need new evidence; it is an
  application of two standing ones.
- **NOT IDENTIFIED — amounts are RANGE-BUCKETED** (bottom bucket
  `$1,001–$15,000`, a 15x span), so **position sizing is not identified**
  (§3). **Blind-trust assets are excluded** entirely, and filings are
  **self-reported with no verification mechanism**.
- **LEGAL — UNRESOLVED, and not an agent's call.** The Senate eFD gate
  quotes the **Ethics in Government Act** barring use *"for any commercial
  purpose other than by news media"*, **civil penalty up to $10,000**.
  Whether systematic trading constitutes such a purpose is **[UNKNOWN]** and
  **needs counsel, not an agent**. Filed as unresolved rather than resolved
  in the convenient direction.
- **LITERATURE — a published null.** Belmont, Sacerdote, Sehgal & Van Hoek
  (2022), *Journal of Public Economics* **207:104602**, sample **Jan 2012 –
  Dec 2020**: **no evidence of superior performance**; even **95th/99th
  percentile** returns are **consistent with random stock picking**. Grade
  this against §3's power arithmetic before quoting it as strong: it
  credibly excludes a large effect and is underpowered for a small one.

## What this atlas does NOT establish

- **Nothing here is adopted, wired, or proposed for adoption.** Availability
  is a precondition, not an argument.
- The Companies House figures are **single-entity, single-year reads** of
  filed accounts. No comparability work has been done across entities,
  currencies (USD and GBP both appear above, deliberately unconverted), or
  fiscal-year definitions — and §1's recharge caveat says why that work
  would be harder than it looks.
- §3 and §4 are **one session's samples**, at the stated n, with the
  scripting registered as owed (item 111).
- The legal question in §5 is **[UNKNOWN]**, not resolved.

## Related

[[sources/session-20260830-audit-wave-and-external-data-atlas]] ·
[[synthesis/evidence-closed-register]] · [[synthesis/owed-measurements]] ·
[[concepts/availability-failure-mode]] · [[concepts/the-method]] ·
[[concepts/evidence-grading-ladder]] · [[concepts/location-not-magnitude]] ·
[[concepts/average-uniqueness-and-ess]] · [[concepts/false-green]] ·
[[sources/session-20260808-institutional-data-adjudication]]
