# Reject-inference bounds (lane B′) — run 2026-09-20T12:30Z, SAFE-plane

Instrument: `scripts/reject_inference_bounds.py` (read-only; refuses rather
than approximates). Question (spec §1,
`docs/superpowers/specs/2026-09-20-desk-instruments-plan2-sor-ipma-design.md`):
could the absorbed strata of the era-9 pre-DE-010 arrivals hide net edge?
Answered with Manski worst/best bounds, never point estimates.

## Headline numbers (real run, exit 0)

Window since 2026-09-08T00:00:00Z (era-9 = 12-10d4d0c2). Census seam
re-verified this run: **N = 80,024 arrivals** (the era is still accruing —
the 2026-09-19 census read 77,676), **lost L = 62,494** (EN-030 only;
EN-020 = 0), **deep pipeline D = 17,478**, **gradeable g = 52**,
**CV-with-asset = 455**, **DE-010 coverage = 4** events (the first post-
capture record landed; all 4 events fall after the corpus end).

- fee_rt_bps = **45.0** (`pretrade.maker_fee_bps 15 + taker_fee_bps 30`),
  horizon = **2160 min** (`ml.label_max_bars 432 × 300 s` — the label
  vertical IS the live bracket deadline).
- Covered corpus window: 2026-09-08T00:00Z .. 2026-09-17T11:59Z (the last
  minute with a full 36 h forward path). **49,256 arrivals covered; 30,768
  arrivals in the tail beyond corpus coverage — UNMEASURABLE by this
  instrument, counted via per-hour EN-000 deltas, never imputed.**

### Era-window Manski bound (net-of-fee bps per arrival, both directions, all 4 assets)

**[−1201.34, +1111.34]** over 13,680 minutes/asset. Descriptive quantiles
of the same pooled distribution (labeled, NOT the bound):
p01 = −867.29, **p50 = −45.00 (= exactly the round-trip fee: the median
36 h move is zero)**, p99 = +777.29.

Per asset: BTC [−703.65, 613.65] · ETH [−881.29, 791.29] ·
LINK [−1201.34, 1111.34] · PAXG [−388.77, 298.77]. (The extremal 36 h move
in the window is LINK ±11.6%; PAXG is the tightest.)

### Per-stratum bounds

| stratum | n | coverage | bound / value |
|---|---|---|---|
| gradeable g | 52 | 38 covered + 14 censored | **DR taken mean +20.65 bps**; counterfactual [−1201.34, +1111.34] |
| lost L | 62,494 | unconditional | [−1201.34, +1111.34] per arrival |
| deep D | 17,478 | unconditional (residual) | [−1201.34, +1111.34] per arrival |
| CV-with-asset | 455 | 425 covered + 30 censored | mean per-record [−233.82, +143.82] |
| DE-010 captured | 4 | 0 covered + 4 censored | UNIDENTIFIED (events post-date corpus end) |

Gradeable stratum: propensity of the taken action = **1.0** under the
deterministic policy, so the doubly-robust estimator reduces to the sample
mean of realized outcomes (IPW weight 1/1.0; outcome-regression term
cancels) — stated, not assumed away. The 38 covered taken actions averaged
**+20.65 net bps** at the 36 h horizon. The counterfactual (had they been
absorbed) is bounded, never point-estimated.

### DR-IPMA per gate

| gate | absorbed | share of N | importance (DR marginal effect on net edge) | performance (absorb rate + width) |
|---|---|---|---|---|
| EN-020 | 0 | 0.0000% | n/a (0 absorbed) | n/a |
| EN-030 | 62,494 | 78.0941% | [−1201.34, +1111.34] (maximally wide: no per-arrival record) | width 2312.68 |
| CV-000 | 75 | 0.0937% | n/a (admission gate; value realized downstream) | width 401.38 |
| CV-010 | 208 | 0.2599% | **[−287.92, +197.92]** (per-record realized paths) | width 485.84 |
| CV-030 | 172 | 0.2149% | **[−158.71, +68.71]** | width 227.42 |
| deep-pipeline gates (SZ/RP/PT/OM…) | 17,478 | residual | **UNIDENTIFIED** (no per-arrival attribution pre-DE-010) | n/a |

CV-010's denied arrivals carried the gate's own mean estimate
est_edge_bps = 112.7 (against est_cost ~63 where logged); the realized-path
bound on what the denial forewent is [−287.92, +197.92] net bps — the
estimate sits inside the bound, as it must if the instrument is coherent.

## Method

- Strata come from `scripts/gradeability_census.py census()` itself; this
  script's independent streaming re-count (chain verified incrementally,
  records never loaded unboundedly) must match it exactly, else
  `CENSUS_INCONSISTENT`. The streaming verifier replicates
  `read_chain`/`verify_chain` semantics including writer-seam adoption.
- Outcome instrument: corpus 1m bars (`research/corpus/binance_vision`),
  entry at the OPEN of the arrival minute's bar, exit at the CLOSE of the
  bar 2160 minutes later. The manifest's claims (4 symbols × 1,428,480
  rows, 2024-01-01 → 2026-09-18 23:59, gap-free) were re-verified against
  the parquets at load — row counts, first/last, and a full-array 60 s
  grid diff — not trusted. The era bound was additionally recomputed by an
  independent second path after the run: identical to 2 dp.
- Manski bounds use the full empirical support: unconditional strata
  (L, D) get the era-window bound over every covered minute × asset ×
  direction; conditional strata (CV: ts+asset; DE-010: ts+asset+
  decision_mid) get per-record realized-path bounds. Where direction is
  absent the bound widens over both directions; the field is never
  fabricated (pinned by `test_never_fabricates_direction`).
- Refusals (script-local, census style): `CHAIN_TORN`,
  `AUDIT_UNREADABLE`, `CENSUS_INCONSISTENT`, `CORPUS_MISSING`,
  `CORPUS_MANIFEST_MISMATCH`, `CORPUS_NO_COVERAGE`, `CONFIG_UNREADABLE` —
  banner + exit 2.

## Assumptions (stated, none silent)

1. **Venue proxy**: the corpus is Binance USDT-margined spot; the bot marks
   on Kraken USD. The USD/USDT and cross-venue basis is ignored — a
   bound-widening caveat, small versus 45 bps fees.
2. **Fee-only cost**: klines carry no book, so spread/impact are NOT in the
   cost stack. Every bound is optimistic on the cost side by the missing
   half-spread; true net outcomes are weakly worse. fee_rt follows the
   `horizon_edge_sweep.py` precedent (maker+taker from config).
3. **Horizon**: `ml.label_max_bars × 300 s` — the bot's own evaluation
   horizon by construction (label vertical = live bracket deadline;
   `main.py` computes `horizon_h` the same way). The 300 s bar constant is
   the engine's own, not a new literal.
4. **Tail attribution**: EN-000 ticks are hourly cumulative vectors; a
   tick's arrival delta is attributed to the tick's timestamp. The 30,768
   tail arrivals (2026-09-17T12:00Z onward, incl. everything after the
   2026-09-18 corpus end) are outside any bound this corpus can support.
5. **Gradeable outcome definition**: the taken action's value is the
   corpus forward path from the fill's ts/asset/side at the uniform 36 h
   horizon — NOT the bot's realized P&L (exit geometry mixes holding
   periods). One instrument across all strata, apples-to-apples.
6. "Missing corpus coverage → refusal" is implemented at the instrument
   level (absent/unreadable/lying corpus, zero era overlap). Per-record
   censoring (asset outside corpus, ts beyond the last full-horizon
   minute) is counted and reported, not a refusal — the era outliving its
   corpus is a measurement boundary, not an inconsistency.

## Bottom line

What the lost stratum could hide: up to **+1111 net bps per arrival** at
the 36 h horizon (a LINK-scale 11.6% move in the right direction) — or
**−1201 bps**. With 99.78% of arrivals absorbed and no per-arrival record,
the honest full-support answer is maximally wide: the lost 62,494 cannot be
shown to hide edge, and cannot be shown not to. What it could NOT hide
without leaving a trace: the descriptive center of the counterfactual
distribution is **−45.0 bps (p50 = exactly the fee)** with p01/p99 at
−867/+777 — for the median arrival the absorption was worth precisely the
round-trip cost, and only **39.1%** of covered minutes even moved more
than 45 bps in either direction over 36 h (19.6% of the pooled
both-direction points net positive). The tightened strata tell the same story at higher
resolution: CV-gated arrivals bound at [−233.82, +143.82] mean, and the 38
measurable taken actions realized +20.65 bps against a 45 bps cost stack.
Where this instrument is blind — the 30,768-arrival tail and the 17,478
deep-pipeline residual — it says so (UNIDENTIFIED) rather than imputing.
That is the input to the 09-22 boundary's n=50/n=100 lean ruling: the
absorbed population's value is bounded, the bounds are wide, and DE-010
(now capturing: 4 events, all post-corpus) is the only road to narrowing
them.


---

## Pass 2 — 2026-09-20 ~23:17Z, corpus extended to 2026-09-19 23:59Z

Trigger: corpus re-pull (`scripts/fetch_binance_vision_1m.py`, +1,440 rows/symbol, 0 gaps/dupes) closed the 09-19 tail. (Full stdout archived local-only at `outputs/research/bounds_pass2.txt`; outputs/ is gitignored — the numbers below are the durable copy.)

- arrivals **N = 87,620** (covered 60,592; uncovered tail **27,028** — counted via EN-000 deltas, UNMEASURABLE, not imputed). Coverable window ends at corpus_end − 36 h horizon = 2026-09-18T11:59Z; the tail is everything since.
- era-window Manski bound: **[−1211.3, +1121.3]** net bps/arrival (pass 1: [−1201.34, +1111.34]) — widened slightly with the extra day; descriptive p50 = −45.0 (exactly the round-trip fee).
- gradeable g = 55 (42 covered + 13 censored): DR taken mean **+3.47 bps** (pass 1: +20.65 on 38 covered). Four newly covered entries moved the mean 17 bps — all gradeable means are small-n calibration, never verdicts.
- CV stratum 460 (444 covered + 16 censored): [−249.31, +159.31].
- DE-010 stratum: **7,600 captured events, 0 covered** — all postdate the coverable window; first coverage requires the corpus to clear their ts + 36 h (earliest possible: a 09-22 re-pull covers the 09-20 07:00Z batch).
- Gate importance: EN-030 = the era interval [−1211.3, +1121.3] (width 2,332.6); deep-pipeline gates remain UNIDENTIFIED.
