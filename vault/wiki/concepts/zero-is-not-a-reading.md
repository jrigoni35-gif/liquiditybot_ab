---
title: Zero Is Not a Reading
category: concept
summary: When "I have no measurement" is returned as a value inside the domain of the comparison — 0.0 for an unseen correlation, 0.0 for an empty book's cost, size 0 for "already initialized" — the gate cannot tell absence from evidence, and the sentinel lands on whichever side of the threshold it happens to fall; five instances in this repo, and the one time it was handled correctly it returned None. Sequel 2026-08-07: the class fired LIVE a second time (147 more laps on a cold estimator flapping |rho|~1 <-> 0.0 — an under-evidenced reading is as fabricated as a missing one), and the class fix shipped — gate on the evidence COUNT, never on the value's plausibility. Input-plane wing 2026-08-08 — staleness closed (41a gate + 41c persisted windows), absence closed at the record layer (41b's ""-vs-"0" corpus columns); saturation and clipping (41d/41e) still parse as numbers. SIZING-PATH INSTANCE 2026-08-09 — the worst placement yet: a getattr default against the bot's own type made a dead book reader and a genuinely flat book both read 0.0 heat, three risk controls went inert ALL failing permissive, and tickets ran 13.7% larger than designed; the fix is the first here to install the DISCRIMINATOR (log once when the book cannot be read) instead of a better default, and a getattr against your own types is now named as a manufactured sentinel
tags: [defect-class, sentinels, gates, cold-start, method, data-quality]
sources: 9
updated: 2026-08-09
---

# Zero Is Not a Reading

## The claim

A function that answers *"how correlated are these?"*, *"what does this cost?"*, or *"has this
been initialized?"* has **two** possible failures: the measurement can be **wrong**, or it can be
**absent**. Absence is the more dangerous one, because it is usually encoded as a **value inside
the domain of the answer** — `0.0`, `0`, `False`, an empty dict — and every downstream comparison
then treats it as a measurement.

> **The sentinel for "no data" must be outside the domain of the comparison, or the comparison
> must test for it separately.** `0.0` is a perfectly good correlation. `0` is a perfectly good
> file size. Neither can also mean *"ask me later."*

The compounding hazard is that the resulting log line is **literally true and completely
misleading**: `"correlation 0.00 below floor"` is an accurate rendering of a number that was
never measured.

## The type specimen: 147 round trips on a number that did not exist

`regime/correlation.py:40-41` —

```python
def corr(self, a, b):
    return self.corr_fast.get((a, b), self.corr_fast.get((b, a), 0.0))
```

— and `_EwmaCov.corr` returns `0.0` whenever either variance is `<= EPS`. **An unseen pair, a
cold engine, a fresh process, or an asset with no return history all read `0.00`.** The hedger's
unwind test was `corr < min_hedge_correlation (0.55)`, so **every one of those states is a
decisive unwind verdict**, indistinguishable from a genuine decorrelation.

On 2026-08-06 that produced **147 hedge open/unwind round trips in 24.65 minutes, 294 fills,
$289.73 of fees — 95.6% of the window's equity drop** ([[sources/session-20260806-hedge-thrash]]).
The 147 identical unwind reasons all said `correlation 0.00 below floor`. **They were right about
the number and wrong about the world.**

### The same file already knew

`beta()` in the same class returns `0.0` for an unknown pair too — and the hedger's **open** path
**defends against it**: `beta = beta if abs(beta) > self.beta_floor else 1.0` converts an
unreliable beta to `1.0` rather than sizing a hedge at zero. The **unwind** path consumed `corr()`
raw, with no equivalent floor. **The same defect class, the same module, the same function — one
path guarded, the other not.** The knowledge existed; it just was not applied where it decided
whether to *destroy* a position.

## Four more instances in this corpus

| Site | The sentinel | What it was read as |
|---|---|---|
| **Book-walk cost on a wholly empty side** | returns **`0.0`** instead of the veto sentinel | *"this trade is free"* — an entry proceeds where the gate exists to stop it ([[comparisons/stated-invariants-vs-audited-reality]], [[sources/whole-code-audit]]) |
| **Participation clamp at zero depth** | **silently no-ops** | *"no clamp needed"* rather than *"no depth data"* — same audit row |
| **`if dest_hist.exists()` header branch** | a **zero-length** file **exists** | *"already initialized, skip the header"* — the corpus stays headerless and `csv.DictReader` **adopts the first TRAINING ROW as its column names**. **Three independent occurrences in this repo** ([[concepts/torn-append-fusion]], [[sources/session-20260806-append-gate]]) |
| **A missing `registry.jsonl`** | absence | *"unknown provenance"*, which **`reload()` accepted** — the ML-011 tamper gate degraded to a log line ([[comparisons/stated-invariants-vs-audited-reality]]) |

The pattern across all five: **the absent case falls on the permissive side of a gate in four of
them, and on the destructive side in the fifth.** Nobody chose either.

## The one time it was done right

`bracket_divergence_summary` reports **`agree_rate: None`** until a priced (`tb_pt`/`tb_sl`) close
exists, with **`n_priced` printed beside `n`** ([[concepts/tautological-instrument]],
[[sources/session-20260806-geometry-filing]]). That is the whole discipline in one line: the
unmeasurable state returns a value **outside the domain** of the thing being reported, and it
**carries its own sample size**. The instrument previously reported **`1.0000`** — a number
that was **94.3% definitional** — which is the same defect wearing a flattering value instead of
a punishing one.

> **A sentinel that flatters is worse than one that punishes, because nothing investigates it.**

## The rules this class produces

1. **Return a sentinel outside the domain**, or return `(value, is_measured)`. `None`,
   `float("nan")` with an explicit check, or an explicit `Optional` — anything the comparison
   operator cannot silently consume.
2. **If the sentinel must stay in-domain, test for it at every gate, not at the source.** The
   source cannot know which side of which threshold it will land on.
3. **Choose the direction consciously, per call site, and write down why.** The repo's own
   doctrine is directional: paper results may only err **against** the strategy
   ([[concepts/cost-truth]]), and entries **fail closed**. Applied here, absence should have
   **blocked the hedge OPEN** (do not take new risk on no evidence) and **must not have forced
   the UNWIND** (do not destroy a live position on no evidence). **The same sentinel is not the
   same verdict on both sides of a create/destroy pair.**
4. **Carry `n` with every rate.** A ratio without its denominator cannot report its own emptiness.
5. **Read the log line as a stranger would.** `"correlation 0.00 below floor"` passed review 147
   times because it is a well-formed sentence about a real threshold. **A true sentence about a
   fabricated input is the hardest kind of log to doubt.**

## The sequel — reframed after the panel's timeline adjudication (2026-08-07)

~~"Twelve hours after this page was written, the type specimen recurred with the two-paths bug
already fixed: 147 more laps."~~ **Panel-corrected
([[sources/session-20260807-institutional-review]] §B): the 147-lap window IS the type
specimen above — one event, double-filed under two clocks — and it ran on pre-`5c111962`
code.** What is true and *stronger* than the original framing: during that one event **both**
of this page's artifact values were live at once — the wrong-pair `corr(ADA,ARB)` read 0.0
(missing pair) *and* the ~01:00Z restarts made the estimator cold, so the same 0.00 was also
the under-evidenced sentinel; and a cold EWMA at 2 samples reads **|rho|≈1** (the open's floor
passes) while variance ≤ EPS reads **0.0** (the unwind fires). This extends the claim:

> **An under-evidenced reading is as fabricated as a missing one.** `0.0` is the absence
> sentinel; `|rho|≈1` at n=2 is the same defect wearing a *confident* value. The domain check
> cannot catch either, because both are perfectly plausible correlations.

**The class fix shipped in `cf454d5e`**, and it is this page's rules made mechanical:

- **Rule 4 applied at the gate:** `CorrState.pair_samples(a,b)` carries the **evidence count**
  with the reading, and the hedge open requires `pair_samples ≥ corr_min_samples (12)`. Its
  docstring is the doctrine verbatim: *"consumers gate on this count, never on the rho value's
  plausibility."*
- **Rule 3's asymmetry applied exactly:** absence **blocks the OPEN** (no new risk on no
  evidence) and **never gates the UNWIND** — a cold-estimator unwind may fire once (idempotent)
  and re-hedging is what waits for warmth ([[concepts/deadlock-discipline]] rule 1). The $318
  came from re-opening, not from closing.
- **A deliberate in-domain sentinel, direction chosen and written down (rule 3's "write down
  why"):** an EMPTY samples dict returns `_WARM_ASSUMED` (10^9) — "warmth was never tracked" —
  so every legacy caller, stub and restored snapshot stays byte-identical. Boot corner verified:
  at process start both sentinels fire (samples empty → warm-assumed; `corr()` → 0.0 < floor)
  and they land on **opposite sides** of the open gate — the blocking one wins, so the corner is
  safe by the floor's accident, then by the count once the first tick lands.

Residual, owed (item 35a): the counts are **not persisted**, so warmth is re-earned every boot —
the sentinel discipline now exists in-process and resets with the process. Panel addendum
(2026-08-07): the warmup floor is **12 × 150s = 30 min = exactly the median uptime**, so
roughly half of process lives never reach warm — and the guards also suppress **trims**, so
the evidence gate's fail-safe direction quietly disables risk *reduction* too
([[sources/session-20260807-institutional-review]] §D).

## The input-plane wing (2026-08-07 night) — three feeds that cannot say "I don't know"

The fleet sweep ([[sources/session-20260807-fleet-findings]] §3) found the class saturating the
**context/ML input plane**, all verified live:

- **Feed failure ≡ neutral, byte-for-byte.** The ML context dict (`main.py:5703-5718`) consults
  **no `.available` flags**, and a dead feed's 0.0s are **identical to the historical padding
  neutrals** (`ml/features.py:50-57` `CONTEXT_NEUTRAL`). The model cannot distinguish "options
  feed down" from "options flat" from "row predates the feature" — three different worlds, one
  encoding. This is the live half of owed item 12 (missing-data indicators).
  > **FIXED at the record layer 2026-08-08 evening, commit `64724480` (owed 41b,
  > [[sources/session-20260808-evening-availability-persistence]] §1):** every corpus row
  > now carries `avail_web`/`avail_equity`/`avail_options`/`quotes_frozen` as trailing
  > bookkeeping columns, with **`""` = UNKNOWN strictly distinguished from `"0"` =
  > measured down** — the three worlds get three encodings *in the record*. The model
  > input is deliberately unchanged (0 DoF, ledger closed); decision-path consumption
  > stays sequenced behind h432.
- **A frozen input is the slow-motion variant.** moomoo re-appends the same closed-market
  quote every poll with no staleness guard (`moomoo_feed.py:218-272`) — verified live as
  identical `+3.60%` baskets for hours with **z decayed to +0.00**. Repetition of a stale value
  *drives* the reading to neutral: not a sentinel this time, but the same lie — the gate
  consumes "no new information" as "measured calm."
  > **FIXED 2026-08-08, commit `01d59908` — the wing's first shipped repair**
  > ([[sources/session-20260808-battery-split-freeze-gate]] §2): a **full-basket
  > per-ticker repeat** is treated as *absence of new evidence* — the window is not
  > appended and **z holds its last honest value** instead of decaying; the snapshot says
  > so (`quotes_frozen`, additive) and the transitions are latched registered codes
  > (DF-010/DF-011). The rule made mechanical: **repetition is not a reading either.**
- **A gate whose input is pinned can never fire.** Sentiment `vol_z ≡ 0` because item volume
  reads the saturated cap (**200 every poll**, `scanner.py:275-292`) — so the fear/euphoria
  spike gates are structurally dead; and `opt_iv_skew` sits at its **−3.00 clip bound** — a
  rail, not a reading ([[concepts/tautological-instrument]] holds the gauge-side siblings).

Fixes owed as item 41 — **the staleness spelling closed 2026-08-08 (41a, and 41c
`e22df720` extended it across restarts: persisted windows plus a pinned composition test
that a still-frozen market reads frozen on the first post-restart poll, never re-seeded);
the absence spelling closed the same evening at the record layer (41b, above). Saturation
and clipping remain open (41d/41e).** The class rule generalizes: **absence, staleness,
saturation and clipping are four spellings of "I don't know," and two of the four still
parse as numbers.**

## The sizing-path instance (2026-08-09) — and the first fix that names the discriminator

Commit `1fee174e` ([[sources/session-20260809-adversarial-audits]] §1). `risk/position_sizer.py`
read the open book as `getattr(state, "positions", {}).values()`. **`PortfolioState` has no
`positions` attribute** — the book is `_positions`, exposed as `open_positions()` — so the
**default was taken unconditionally**, and the sizer computed heat over an empty dict **forever**.

**The sentinel:**

| | reads as |
|---|---|
| **a dead reader** (the bug) | `heat = 0.0` |
| **a genuinely flat book** (correct, and common) | `heat = 0.0` |

**Identical, benign, and on the SIZING path** — the one place in this system where a permissive
zero directly multiplies risk. Three controls went inert and **all three failed permissive**:
the heat veto (`max_portfolio_heat_frac` 0.35) became unreachable, the signed-inventory skew
(`SZ-061`) never applied, and the inventory-aggression multiplier **pinned at `light_boost` 1.10**
— a **permanent 10% size-UP** where it should have tapered toward `heavy_cut` 0.65. Measured live
with real position ages: heat **0.1176** read as **0.0000**, multiplier **0.9488** vs the pinned
**1.1000** ⇒ **tickets 13.7% larger than designed**, exactly when the book was loaded.

**The fix is the first in this corpus to install the discriminator rather than a better default:**
one centralised `_open_book()` accessor that **logs once when a state cannot report its book.**
The two cases now produce **two signals**, which is the whole content of this page's rule 1.

> **Post-deploy proof the instrument is non-tautological:** `status` `heat_frac` now reads
> **0.1177**, where it had been **structurally 0.0 for the entire life of the gauge** — the same
> shape of proof the `marks_age_sec` repair produced ([[concepts/tautological-instrument]]).

**Rule added by this instance:** *`getattr(obj, "name", default)` against your own types is a
manufactured sentinel.* It converts `AttributeError` — the loudest and cheapest possible
"I don't know" — into a silent value inside the domain of the comparison. **Prefer the access
that crashes.** The test suite could not catch it because the doubles supplied the missing
attribute ([[concepts/test-double-fidelity]]).

## Relationship to the neighbouring classes

- [[concepts/test-double-fidelity]] — how a manufactured sentinel survives a test suite: the
  double provides the attribute production lacks, so the `getattr` default is never exercised in
  test and always taken in production.
- [[concepts/two-paths-one-quantity]] — the multiplier. A missing-data sentinel that both paths
  read the **same** way is a bad decision made once; one that **opposed** paths read differently
  is an infinite loop. Rule 3 above is where the two classes meet.
- [[concepts/tautological-instrument]] — the mirror image: there the instrument had data and the
  quantity was **definitionally** fixed. Both produce a confident number that measures nothing.
- [[concepts/iron-law-of-debugging]] — *"the raw scan is a lead sheet, never a verdict."* Same
  epistemics one level up: a **default** is not a **measurement**, and neither is a **match**.
- [[concepts/honest-null-result]] — the disciplined form of the same situation when a human is in
  the loop: say the measurement is empty rather than reporting the empty value.
- [[concepts/dead-mute-trap]] · [[concepts/probe-livelock]] — absorbing states built from two
  individually-correct rules; a zeroed sentinel is often the value that makes the state absorbing.

## Related
[[sources/session-20260806-hedge-thrash]] · [[sources/session-20260807-hedge-churn-guards]] ·
[[concepts/deadlock-discipline]] · [[concepts/two-paths-one-quantity]] ·
[[concepts/tautological-instrument]] · [[concepts/iron-law-of-debugging]] ·
[[concepts/cost-truth]] · [[concepts/honest-null-result]] · [[concepts/evidence-floors]] ·
[[concepts/torn-append-fusion]] · [[concepts/dead-mute-trap]] ·
[[comparisons/stated-invariants-vs-audited-reality]] · [[sources/whole-code-audit]] ·
[[sources/session-20260806-geometry-filing]] · [[sources/session-20260806-append-gate]] ·
[[sources/session-20260807-fleet-findings]] ·
[[sources/session-20260808-battery-split-freeze-gate]] ·
[[sources/session-20260808-evening-availability-persistence]] ·
[[synthesis/owed-measurements]]
