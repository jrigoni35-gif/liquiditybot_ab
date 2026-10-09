---
title: "Session 2026-08-21 — the manipulation gate cannot tell repricing from layering, and the gate that decides everything fires below its own noise"
category: source
status: SETTLED
summary: "SETTLED as a record of what this session measured — audits A, B and C all RAN, and A's verdict (UNRESOLVED in both directions) is itself the established result. ONE downstream conclusion has since been re-marked PROVISIONAL: the live-readiness FRAMING on synthesis/live-readiness-verdict, reframed by the open cost-stack investigation at sources/session-20260821-cost-stack-in-flight. The NOT-READY direction and all five blockers are unaffected. Three audits in one session: (A) the SZ-045 manipulation veto's efficacy is UNRESOLVED in both directions — the effect lives on the disposition stamp, dies on the manip score, and a placebo stamp scores higher; (B) injection into the SHIPPED spoof detector shows honest maker repricing in a melt-up scores 0.949 (veto_at 0.90) and is byte-identical to real layering at matched cadence, is directionally biased against trending tape, and is evadable at >=120s repost; (C) the adversarial pass on eeff0f7a found a security pin satisfied by a COMMENT and an unregistered code minted into the hash-chained audit. Live-readiness verdict: NOT READY, five independent blockers, era-4 at 33/50 with effective n 9.9 and 85% probe admissions."
tags: [session, manipulation, thales, era-4, live-readiness, injection, adversarial-review]
source_path: raw/quant/2026-08-21_manip_gate_and_live_readiness.md
source_date: 2026-08
ingested: 2026-08-21
sources: 1
updated: 2026-08-21
---


> [!warning] COUNTER-CALLOUT 2026-09-02 — THE JACCARD WAS MEASURING A SEAM, NOT THE DETECTOR
> The 0.462 Jaccard and the "116/454 = 25.6% of stamped rows record a manip_suspect
> BELOW the threshold they were refused by" on this page have a MECHANICAL cause found
> 2026-09-02: `ml/history.py:2460 mark_disposition` stamps the NEWEST OPEN candidate for
> (asset, direction) with **last-wins semantics — no candidate-id match, no recency
> bound**, while the veto reads a per-CYCLE score. The stamp and the feature snapshot are
> written on different clocks, so a row can carry a disposition decided ~10^2 cycles after
> its own features were frozen.
> **What is retracted:** the framing of those rows as "refused by a threshold they sit
> below". They were not; they carry a stamp from a later evaluation.
> **What SURVIVES, and is now explained:** the placebo result. A last-wins stamp is a
> RECENCY channel, which is precisely why the placebo stamp (SZ-021 +33.51 pp) outscored
> the real one (+15.48 pp) — that comparison was always the sound half of this page.
> **Recomputed today:** Jaccard 0.442, 204/752 = 27.1% below threshold. Stable, not
> shrinking. The defect is corpus-wide, not manip-specific: every `disp` value inherits it.
> Full account: repo `docs/quant/2026-09-02_manip_gate_reconciliation.md` and HANDOFF (15a)–(15c).


# Session 2026-08-21 — the shape is not the intent

Repo HEAD `dae58cf6`, deployed head on the PC `dae58cf6` (`auto_update.outcome`
= `current`). Full measurement record with every command and stamp:
`raw/quant/2026-08-21_manip_gate_and_live_readiness.md`. The verdict itself has
its own router page: [[synthesis/live-readiness-verdict]].

> **Freshness.** Every corpus number here is as-of a stamped snapshot
> (`signal_history.csv` md5 `a6b83a65e0a037bdc4ad740ae49f1a77`, 14,170 rows,
> ts .. 2026-08-21T22:42:22Z) and every live-state number as-of
> 2026-08-21T23:53:07Z. Both files grow while being read.

---

## 1. The live-readiness verdict: NOT READY, remain in DRY_RUN

The only road to live is unchanged and is not touched here: config
`dry_run:false` → restart → typed `ARM LIVE`. Five blockers, each sufficient
alone:

| # | blocker | evidence |
|---|---|---|
| 1 | **The gate has not read out** — 33/50 | double-derived: `pc_status.era4.accrual_n` = 33 AND `scripts/cohort_eval.py` = 33/50 |
| 2 | **The gate cannot resolve what it will be asked** | effective n **9.9 of 33** (mean uniqueness 0.301, SE optimistic ×1.82); resolvable floor **~1.7033%** vs observed gross **+1.1820%** |
| 3 | **The cohort is 85% exploration constant** | `probe: {'1': 28, '0': 5}`; a probe forces `p_win = 0.7` against a ~0.567 bar → clears by construction. Also `MIXED(both)`: 18/33 trips straddle a deploy, 2 champions, 2 label eras |
| 4 | **Two CRITICAL findings are inert ONLY because `dry_run` is true** | `risk/leverage.py:75` margin veto FAILS OPEN; `execution/inventory.py:134-155` → `main.py:2921` derisk force-closes a HEDGE uncoordinated (the cf454d5 ADA churn shape, −$318) |
| 5 | **The entry path's manipulation gate cannot separate honest repricing from layering** | §3 below, injection into the shipped engine |

Additive and standing: the fee constants are falsified (25/40 shipped vs Tier-1
40/80, owed 88) — live fills would book against a cost stack the ledger
under-prices.

**Blocker 2 is the same shape as [[synthesis/owed-measurements]] item 82,
recurring at a different n and the opposite sign.** The gate is a pre-committed
TRIGGER, not a measurement; a readout names which decision became decidable and
decides nothing. Reading it as a verdict on the strategy would be the exact
error the n=50 apparatus exists to prevent.

---

## 2. Audit A — does the SZ-045 veto refuse winners? NOT ESTABLISHED, both ways

The corpus logs a counterfactual outcome for refused candidates, so the question
is answerable. It was asked with two instruments that are supposed to name the
same event, and **they disagree**:

| instrument | pooled MH delta (refused − passed), direction-adjusted, ESS-corrected | z | p |
|---|---|---|---|
| disposition `disp == SZ-045` | **+11.71 pp** | +2.41 | 0.016 |
| feature `manip_suspect >= 0.9` | **+2.80 pp** | +0.61 | 0.542 |

`both = 277 · disp-only = 104 · feature-only = 218 · **Jaccard 0.462**`, and
**116/454 = 25.6% of SZ-045-stamped rows record a manip_suspect BELOW the veto
threshold** they were supposedly refused by (disp-only median 0.858).

Holding one fixed and moving the other settles it: **the manipulation score
explains nothing** (+4.75pp z=0.46 / −1.24pp z=−0.11); the whole effect rides on
the **stamp** (+17.71pp z=1.60 p=0.111 / +11.72pp z=1.08 p=0.281) — and neither
stamp contrast is significant on its own.

**The placebo kills the headline.** Every terminal stamp with n≥30, vs the rest:
`SZ-021 +33.51pp` (larger than the manip stamp's `+15.48pp`), `capped −6.59pp`,
`SZ-022 −13.08pp`, `SZ-023 −14.41pp`. Being stamped predicts outcome; being
stamped *for manipulation* adds nothing distinguishable.

Within-asset, in the current label era, apples-to-apples among candidates that
actually reached the gate: **MINA shows nothing** (dWR −0.7pp, dNet −0.13pp on
n=87 vs n=114); FLOW's +34.3pp rides on a control arm of **n=23, effective n
3.0**. The dose-response that existed in `triple_barrier`
(0.212 → 0.200 → 0.266 → 0.347) is **flat in `triple_barrier_h432`**
(0.500 → 0.419 → 0.468 → 0.457).

Effective n, because the nominal n is a lie here: mean per-asset uniqueness
**0.0726** (~13.8 concurrent same-asset labels), median label span 9.4 h; the
141 refused rows are **n_eff 14.7**.

**Verdict: the gate's efficacy is unresolved in BOTH directions. Do not retune
it on this** — and retuning it would be cohort-resetting regardless (entry
decisioning, era-4 moratorium).

> ⚠️ **Currency correction to [[comparisons/thales-engine-vs-manip-suspect]]**,
> which states "no fill ever reached the veto threshold, so the veto has never
> fired in anger." **That was true on 2026-08-01 and is false now**: 454 rows
> carry the SZ-045 stamp, 142 of them in the current label era. Callout filed on
> that page the same session.

---

## 3. Audit B — the detector cannot tell the two processes apart

Static reading says the detector is sound ("a large near-touch level vanished
untouched — that is layering"). The running object says otherwise. Injection
into the **shipped** `regime.liquidity_regime.LiquidityRegimeEngine` with the
live config (synthetic 15-level book, 2 bps grid, 30 s cadence, 80 snapshots):

```
controls behave:   flat book 0.000 · resting wall 0.000 · asks LIFTED/consumed 0.000
the false positive: melt-up +15bps/30s, maker REPRICES its offer   spoof 0.949  SPOOFY
the same repricing on a flat mid                                   spoof 0.000  liquid
```

`veto_at` is **0.90**. Nothing is pulled in bad faith in that scenario — a maker
holds an offer 25 bps above the mid and follows the mid up.

**It is directional.** Melt-up trips the OFFER side (0.949) and not the bid
(0.003); a crash trips the BID side (0.949) and not the offer (0.003). The side
that must chase the trend is the side that reads as manipulation.

**At matched cadence the two processes are the same observation:**

```
repost every 30s:  MALICIOUS layering 0.949 SPOOFY  |  HONEST repricing 0.949 SPOOFY
repost every 60s:  MALICIOUS layering 0.764 liquid  |  HONEST repricing 0.000 liquid
```

Cadence — the attacker's free parameter — decides, not intent. Trip conditions
enumerated: any trend ≥1 bps/30 s; size ≥8× the median level (exactly
`spoof_size_mult`); quote distance +25 bps trips while +2..+10 bps and +100 bps
do not, because the level leaves the tracked 15-level window. **The apparent
"safe" zones are blind spots, not immunity.**

**Evasion floor:** repost every 30 s → 0.949, 60 s → 0.764, 90 s → 0.629,
**≥120 s → 0.000**. A layering campaign that reposts no faster than every two
minutes scores zero against a 0.90 veto bar.

This is an **entry-path** fact, not a telemetry one:
`spoof_score` → `manip_suspect_score = MAX(spoof, whiplash, divergence)`
(`main.py:370-392`) → `risk.manip_gate` (`main.py:1287-1298`) → **SZ-045 entry
refusal** (`main.py:4678-4700`); 0.949 also clears the `spoofy` label bar 0.85
(`regime/liquidity_regime.py:348-352`) → `size_mult 0.0`, `reduce_only`.

**What it could not see:** a real Kraken book, the production RATE of the false
positive, and the other two `MAX()` inputs. This establishes a **capability**,
not a frequency. The corpus half is consistent with it — 95.8% of the era's
veto band is MINA+FLOW, the two widest-spread assets on the book.

New concept extracted: [[concepts/observational-equivalence]].

---

## 4. Audit C — the adversarial pass on `eeff0f7a` (shipped `dae58cf6`)

Seven agents (3 hostile personas in independent contexts + 3 verifiers required
to RUN rather than reason + synthesis). **Zero criticals survived** — all three
personas opened with one and the verifiers killed all three on executed
evidence, which is [[concepts/adversarial-verification]] working in the
uncomfortable direction. Four findings did survive:

- **W1** — `loads_bounded` never raises, so a rejected hostile body fell through
  the SUCCESS tail: latency booked, `retries_recovered` incremented, "retry
  recovered" logged, for a discarded payload; the surviving warning named
  neither venue nor URL across three feeds sharing one client. *The commit that
  hardened the poison boundary had deleted that boundary's only
  venue-identifying alarm.* ([[concepts/false-green]] shape.)
- **W2** — a leading UTF-8 BOM parsed before the change and returned `None`
  after. Permanent and per-poll: a CDN rewrite drops a venue from the composite
  feed forever.
- **W3** — the audit code-extractor scraped prose on faith, minting a fake
  `stale book at 12` code into a **hash-chained** record that `verify_chain`
  still returns `ok=True` on and that can never be corrected in place. Now
  membership-filtered against `core.audit._REGISTERED_CODES`, the registry that
  existed for exactly this question and was never consulted.
- **W4** — the "constant-time comparison" pin was two `inspect.getsource()`
  substring greps, **satisfied by the string appearing in a COMMENT**.
  Mutation-verified: `return str(a) == str(b)` passes the entire pin with the
  suite green. Now a sentinel-patch pin. A textbook
  [[concepts/tautological-instrument]] specimen in the CHECK class.

**Process defect, recorded:** the same commit shipped a new `_token_ok`
authentication primitive in two API servers and its message mentioned neither —
the diff was read filtered to the four expected files. An auth primitive reached
a live bot inside a commit titled "NaN/Infinity JSON rejection at the HTTP
boundary".

Matrix at `dae58cf6`: 3881 pass / 0 fail · smoke 219/0 · assurance 49/0 · ruff
clean · compileall OK. All SAFE class.

---

## 5. State changes worth inheriting

- **The deploy pipeline is unblocked.** `docs/HANDOFF.md` records it stuck on a
  dirty tree plus an unpushed commit (2026-08-20); `auto_update.outcome` now
  reads `current` at `dae58cf6`. That HANDOFF entry is stale as of
  2026-08-21T23:53:07Z.
- Era-4 accrual moved 30 → 33 between 2026-08-20T21:48Z and 2026-08-21T23:53Z.
- Corpus 14,198 rows / 346 live labels; drift share 0.333 against the 30%
  retrain vote line; champion `logistic`, 14 deploys inside the accrual window.

## Owed measurements registered

Items **94** (stamp-vs-feature provenance), **95** (a discriminating feature for
the spoof detector — BOUNDARY class), **96** (production frequency of the
trend-shaped false positive in the 2026-08-20 surge window). See
[[synthesis/owed-measurements]].

## Related

[[concepts/observational-equivalence]] · [[comparisons/thales-engine-vs-manip-suspect]] ·
[[entities/thales-engine]] · [[concepts/average-uniqueness-and-ess]] ·
[[concepts/tautological-instrument]] · [[concepts/adversarial-verification]] ·
[[concepts/never-widen-a-gate]] · [[synthesis/owed-measurements]] ·
[[synthesis/the-money-path-thesis]] · [[synthesis/live-readiness-verdict]]
