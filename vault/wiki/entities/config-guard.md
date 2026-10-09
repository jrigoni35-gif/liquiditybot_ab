---
title: config_guard
category: entity
summary: "The startup coherence checker that FATALs on incoherent configurations rather than letting a knob change weaken an invariant — extended 2026-08-09 to CROSS-SECTION FRESHNESS RELATIONS after two independently-reasonable ceilings in two files (a 5.0s cache age vs a 4000ms veto) created a band of data guaranteed to be fetched and guaranteed to be rejected; and the day its own prose was caught ASSERTING a premise that had been falsified. 2026-08-09 also recorded what it has been saying out loud all along: derived entry bar 0.990 > 0.90, 'fix the geometry, the bar is only reporting it' — computed from tiers/stop/fees alone with no model or corpus, making it the cheapest available falsifier for any account that locates the problem in the model or the data. 2026-08-10 added the WARN-not-FATAL doctrine: passive_hazard_with_book=true restores the pre-boundary-#4 double-counting simulator and warns rather than FATALs, because a FATAL would make the pre-#4 cohort unreproducible and therefore unauditable - FATAL is for INCOHERENT config, WARN for COHERENT-BUT-SUPERSEDED, and the warning carries the magnitude (2f-f^2 vs f, 22.0% vs 11.66%, ~1.88x at the touch) rather than only the key name. And at the 2026-08-11 since-6am audit the guard gained its first DECLARATION-CONSUMER JOIN check: the stop_round knobs must exist where the reader reads them (config[risk]), so the cut-#7 phantom-knob class — a documented control surface whose consumer looked up a nonexistent block — now FATALs at boot instead of silently defaulting"
tags: [module, safety, configuration, staleness, economics]
sources: 12
updated: 2026-08-10
---

# config_guard

The startup validator. Its posture is **FATAL on nonsense** rather than warn-and-continue.

## Representative checks
- Refuses live start with fees below the venue's public floor unless explicitly overridden.
- Cross-checks that two independently-configured fee sections **agree**.
- Enforces **ladder ordering** — the daily-loss limit must trip before the hard-stop drawdown
  ("brake before parachute"). This check is the code-level mechanization of the survival side of
  [[synthesis/risk-posture-doctrine]]: the daily 5% brake sits below the 15% parachute, and the
  guard FATALs on any configuration that inverts them.
- Enforces tier-trigger monotonicity.
- FATALs on contradictory filter levers (both forced-on and forced-off), and on forcing a filter on
  while the labeler cannot produce the era it selects for — "would train on zero rows forever."
- FATALs on floors under every long-book cadence knob, so **"a config change alone cannot turn the
  patient accumulation book into a touch-hugging flicker quoter."**
- Bounds a windowing parameter that previously had **zero coverage at all**.

## A check that priced a product decision (2026-08-05)
When the operator opened the universe to **PAXG** ([[synthesis/tangible-value-doctrine]],
commit `717b2e39`), the guard **FATALed at 13 pairs**. The constraint it encodes is a measured
capacity limit, not a preference: with the **WS feed down**, the REST book poll runs at
**3 req/s**, which sustains a **12-pair envelope** — and base(7) + extra(6) = 13 would starve it.

The resolution was to pay for gold out of the discretionary budget: `skimmer.max_extra`
**6 → 5**, a **permanent tangible-value anchor in place of a rotating candidate**. Recorded in
config beside the knob: *"Raising this again requires raising the envelope first."*

> **This is the guard working as intended in its least-discussed mode.** It did not catch a typo
> or an inverted ladder — it **converted a product wish into its true cost** at startup, before a
> degraded-feed day could discover the same limit the expensive way. A warn-and-continue guard
> here would have shipped a universe that quietly starves its own book poll on the one day the WS
> feed is down ([[concepts/failure-plane-taxonomy]]).

## A new check class — CROSS-SECTION FRESHNESS RELATIONS (2026-08-09)

`3c0debd7` adds a **FATAL on the relation** between a producer's freshness ceiling and a
consumer's: `websockets.kraken_max_book_age_sec` **must stay strictly below**
`pretrade.max_data_staleness_ms / 1000`. Verified two-sided — it FATALs the old config
(5.0 vs 4.0) and passes the new (3.5 vs 4.0).

**Why it needed to be a guard rather than a corrected number.** Both values were
independently reasonable, lived in **different config sections**, and were owned by
different subsystems — nothing anywhere asserted a relation between them. At 5.0 > 4.0 the
gap was not slack: it was a band where a book is **served by the cache and then vetoed by
the gate**, preempting a REST read that would have been fresh, on ~0.6–3% of entry
evaluations ([[entities/pretrade-gate]]). **Fixing the number closes the instance; fixing
the relation closes the class** — the same distinction
[[concepts/two-paths-one-quantity]] draws about arguments vs definitions.

The knob carries the ordering in prose beside it: **"Lower this knob rather than raising the
veto ceiling"** — [[concepts/never-widen-a-gate]] written into the config file, so the next
author meeting this FATAL is pointed at the safe side of it.

> **The general shape, worth checking for elsewhere:** wherever a producer caps how stale
> data may be **served** and a consumer caps how stale data may be **used**, the producer's
> cap must be the tighter one. Otherwise the difference is a guaranteed-waste band, and it
> stays invisible for as long as any third condition keeps the consumer unreachable — here,
> a full 5/5 book, which would have cleared the moment a position closed.

## When the guard's own prose asserted a falsified premise

The same audit found that `config_guard:2835-2848`'s explanatory comment still **ASSERTED**
the premise `36fcfd6e` had just falsified — *"book_ts is stamped at read time, not data
time"* — and that **`tests/test_audit_fixes.py` pinned that dead premise in its test NAME
and assertion message**. Both rewritten.

This is worth recording as a hazard specific to this module: **a guard's comments are read
as authority.** The guard is the file people consult to learn what an invariant *is*, so a
stale rationale here propagates further than a stale comment elsewhere — and **a test that
encodes a premise in its name outlives the premise unless someone renames it**, because a
green test reads as ongoing confirmation. Filed to
[[synthesis/documentation-drift-register]].

## The design role
It is what makes "thresholds live in config" safe. The overfit discipline requires no fitted literals in
decision paths and every knob lifted into config — which would be dangerous without a layer that refuses
incoherent combinations at startup.

## The gap it does not close
**Code defaults drifting from shipped config.** An audit found ~8 fallback defaults disagreeing with the
config file — the guard validates the config, not the code path that runs when a key is absent.

## The verdict it has been saying out loud, and that planning should quote (2026-08-09)

`core/config_guard.py:3104-3107` — verbatim, and it fires because the **derived entry bar is
0.990**:

> *"derived entry bar {0.990} exceeds 0.90 - the payoff geometry (tiers/stop/fees) is so
> cost-heavy that no plausible model clears it; **fix the geometry, the bar is only reporting
> it**"*

**A required win probability of ~99% is not a modelling problem.** The guard is not merely
flagging a knob here — it is stating the project's economic verdict in one line, and it was
stating it while the corpus was busy explaining the same evidence as a model/data problem
([[concepts/unfalsifiable-explanation]]).

This warning corroborates the whole-book decomposition from the same day
([[sources/session-20260809-unbiased-economics]]): **gross P&L before any fees is −11.66 (≈0)
against 382.59 of fees, 32.8x** — i.e. the geometry is so cost-heavy that the breakeven bar
approaches certainty. Two independent instruments, one from configuration arithmetic and one from
the ledger, reaching the same place.

> **The design reading.** `config_guard` computes the bar from **tiers, stop and fees alone** — no
> model, no corpus, no labels. It is therefore the **cheapest available falsifier** for any
> account that locates the problem in the model or the data: those accounts predict a clearable
> bar, and the bar is 0.990. It has been printing at every startup.

*(Note it is a `warn`, not a FATAL — deliberately, since the guard's FATAL posture is for
**incoherent** configuration, and this configuration is coherent and merely uneconomic. Worth
recording that the project's sharpest economic finding rides a warning-level line.)*

## The WARN-not-FATAL doctrine, stated explicitly (2026-08-10)

`aeeaae36` added the guard's clearest statement yet of **when a dangerous setting must NOT be
fatal** (`core/config_guard.py:471-480`, [[sources/session-20260810-fill-double-count]] §3):

```
passive_hazard_with_book = true  →  WARN, never FATAL
```

`true` restores the **pre-boundary-#4 simulator**, in which the passive hazard and
`_sim_maker_cross` both model the same market crossing — a per-order fill rate of `2f−f²` against
a calibration target of `f` (**22.0% vs 11.66%, ~1.88x at the touch**).

> **A FATAL would make the pre-#4 cohort unreproducible — and therefore UNAUDITABLE.**
> Reproducing a superseded execution regime is a **legitimate operation**, and the vault's entire
> era-boundary discipline depends on it being possible. Gating it fatally would trade
> **auditability** for tidiness.

**Three properties make the WARN load-bearing rather than a soft option:**

1. **It carries the MAGNITUDE, not just the key name** — the formula, both rates, and the ratio.
   A warning that says *"this is risky"* is ignorable; one that says *"every paper fill statistic
   produced under this carries a ~2x upward bias near the touch"* is not.
2. **The config `_doc` states the prohibition the guard cannot enforce** — *"it is NOT a tuning
   knob and must never be set true to recover entry volume"* (`config.json:376`). The guard warns;
   the doc names the **specific temptation**.
3. **A test pins the warning both ways** — `tests/test_fill_double_count.py` asserts the guard
   warns when the old model is restored, **and** that the shipped config has it off.

> **The distinction this establishes: FATAL for INCOHERENT, WARN for COHERENT-BUT-SUPERSEDED.**
> A configuration that contradicts itself cannot be run at all. A configuration that faithfully
> reproduces a *past* regime is coherent — it is only wrong as a statement about *today*, and the
> right response is to make it **loud and unmistakable**, not impossible. The counterweight to
> [[concepts/never-widen-a-gate]]: that rule forbids loosening a gate to admit **results**, not
> forbidding a documented reproduction mode for **past** results.

**Also recorded here:** `config.json:376`'s `_passive_hazard_with_book_doc` and the guard comment
above it **both date boundary #4 to "2026-08-09"**, while the commit is stamped
**`2026-08-10T11:03:35Z`**. Filed as a drift row — see
[[synthesis/documentation-drift-register]]; a boundary declaration that disagrees with its own
commit stamp is self-refuting, and this `_doc` is the corpus's canonical statement of that
boundary.

## The declaration-consumer join check (2026-08-11 audit)

([[sources/session-20260811-operator-audit]] §7.) Cut #7's phantom-knob finding —
`stop_round_buffer_bps` documented as a live tuning surface while its only reader looked it
up in `config["risk_management"]`, a block that has never existed
([[synthesis/documentation-drift-register]], [[entities/osler]]) — got its structural guard:
**config_guard now checks the `stop_round` knobs at the join**, i.e. that the declared knobs
exist where the retargeted reader (`config["risk"]`) actually reads them. The class this
closes is new for the guard: every prior check validates a **relation between values**; this
one validates that a **declaration and its consumer are wired to the same key at all** — the
config-plane sibling of [[concepts/false-green]], where turning a knob "works" (no error, no
effect). A future re-divergence FATALs at boot instead of silently falling to a default that
may coincidentally equal the configured value, which is exactly the coincidence that made the
original disconnection invisible.

## Related
[[sources/hardening-catalog]] · [[concepts/failure-plane-taxonomy]] ·
[[sources/session-20260809-unbiased-economics]] · [[synthesis/the-money-path-thesis]] ·
[[concepts/unfalsifiable-explanation]] ·
[[entities/long-book]] · [[sources/whole-code-audit]] · [[entities/pretrade-gate]] ·
[[concepts/tautological-instrument]] · [[concepts/never-widen-a-gate]] ·
[[sources/session-20260809-corpus-corruption]] ·
[[sources/session-20260810-fill-double-count]] · [[concepts/paper-real-boundary]] ·
[[synthesis/documentation-drift-register]] · [[sources/session-20260811-operator-audit]]
