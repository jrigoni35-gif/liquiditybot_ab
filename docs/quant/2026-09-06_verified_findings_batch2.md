# The remaining SAFE verified findings, fixed

**Date:** 2026-09-06
**Class:** SAFE — measurement, observability and honesty. Nothing here changes
which orders are placed or how they fill. Nothing reset.
**Prior batch:** `docs/quant/2026-09-05_verified_findings_batch.md`
**Register:** `vault/raw/audits/2026-09-05_deferred_findings_verification.json`

---

## 1. Fixed

| | file | defect |
|---|---|---|
| **S2** | `ml/history.py` | `.bak_{int(time.time())}` gave two rotations in one second the SAME name; the second `os.replace` overwrote the first while the log said *"old file kept at …"* both times. Now `time_ns()`+pid. |
| **S3** | `runner.py` | `prune_recordings` was called ONLY from `BotRunner.__init__`. Now on the telemetry cadence (`_REC_PRUNE_SEC`, hourly). |
| **S8** | `fee_anatomy_report.py`, `cost_attribution.py` | Both defaulted to **40/80** — not a Kraken row at any volume, ~2× the booked 22/38. Now read the booked schedule; fallback is the venue's **worst published** row (25/40). |
| **S9** | `test_hard_invariants.py`, `venue_adapters.py` | Permanent files claimed the router is on the **LIVE path** (it is not) and that the kraken-only rule is **subclass-proof** (it is not — a plain `@property`). |
| **S10** | `core/fill_ledger.py` | `except OSError: pass` disarmed dedup **silently**, while the append path in the same file logs. Now logged + counted (`dedup_disarmed`). |
| **S11** | `scripts/smoke_test.py` | The only bare `PositionSizer(` outside `tests/` — a DoD gate sized Kelly at the **retired 25/40**. Now receives the live `pretrade` block. |
| **S13** | `scripts/outputs_gc.py` | `git grep` return code never inspected, so **"git failed" ≡ "0 references"** and a referenced corpus file was archived. |
| **S14** | `cohort_eval.py`, `ground_truth_metrics.py`, `defensive_cadence_report.py` | Label era was a hardcoded literal in three consumers while two others already derived it. |
| **S15** | `risk/protocols.py` | Anchor skip was silent; the status triple was **byte-identical** for a dead guard and a healthy day. Now logged + `anchors_set`/`anchor_skips` on the board. |
| **S16** | `scripts/pc_supervisor.py` | `IsProcessInJob` had **never once succeeded** — 13 of 13 log occurrences were failures — because ctypes truncated the `-1` pseudo-handle without `argtypes`. |

## 2. NOT fixed, deliberately — S5

`core/config_guard.py` `_CAND_REF_PEAK_ARRIVALS_PER_H = 18.3`.

**The name says PEAK; the value is a 36-hour SUSTAINED average.** Re-derived
here on `signal_history.csv` (25,840 rows, 337 lineages, 2,032 populated
hour-bins), MAX-per-lineage seq-span within a calendar hour:

```
peak 75/h · p99 55/h · p95 46/h · MEDIAN 17/h
```

18.3 sits at the **median hourly rate** — consistent with its own derivation
(*"659/36h = 18.3/h sustained"*), which is a sustained figure the constant's
name then reads as a peak.

**Left in place, for three reasons:**
1. Which statistic is *correct* depends on the capacity check's semantics. It
   is Little's law over a 36h horizon, and a queue sized for 36h is not
   necessarily overflowed by a one-hour burst that drains. **The defect may be
   the NAME.**
2. Three derivations disagree on the peak: **43.7/h** (2026-09-05 verification
   pass), **75/h** (here), and **21,600/h** from a first attempt of mine whose
   sliding window floored its span at 1 s — *that scan was broken*, and it is
   recorded so nobody repeats it.
3. Raising it **arms a FATAL** against `ml.max_open_candidates=1200`.
   `dry_run=True` downgrades that to a warning, so nothing happens today — but
   at the **armed-live boot it becomes a hard boot refusal**. Correcting the
   constant without adjudicating capacity (B6) would silently plant a live-arm
   blocker.

Treat the capacity check as **UNPROVEN** rather than passing.

## 3. Two tests re-baselined — and one of them WAS the defect

`test_benchmarks_against_the_verified_tier_not_the_struck_one` existed to stop
a **struck** schedule (16/26) being reintroduced from fee blogs. Its assertion
was `KRAKEN_T1_MAKER_BPS == 40.0`.

**40/80 is not a row Kraken publishes at any volume.** So the pin against a
struck schedule was itself pinning an **invented** one, at ~2× the booked
22/38. That is the third instance of this shape in the register
(`core/venue_fees.py` carries the others). Rewritten to assert the tool
benchmarks against whatever is **BOOKED**, which catches a struck schedule, an
invented one, and future drift alike.

`test_fee_anatomy_report.py:108` hardcoded the maker/taker prize at 40 bps —
the 80−40 spread of that invented row. Now **derived** from the module's own
spread (16 bps at 22/38), so the next fee change re-baselines the pin instead
of reddening it.

Also found while fixing S8: `KRAKEN_T5_MAKER_BPS = 15.0 / 30.0`, the "deep-tier
floor" used for the headroom row, is **also not a published row**. Replaced
with `core.venue_fees.best_possible_row()` (0/5). A headroom figure computed
against a tier that does not exist is not a bound.

> Note for the record: the **booked 22/38 is itself not a published row**
> either. That is cut #9's deliberate booking choice, and changing it is fee
> booking — **BOUNDARY**, not this batch.

## 4. What the mutation run caught in my own work

`tests/test_verified_findings_batch2.py` — 18 pins, **14/14 mutations RED after
correction**. Three of my own errors were caught, none by reading:

1. **A broken fix.** `risk/protocols.py` had **no module logger**, so my
   `log.warning` raised `NameError` — and the surrounding `try/except`, the
   very swallow the finding is about, ate it. The counter incremented and the
   log never appeared. Added the logger.
2. **A weak pin.** The S3 AST pin accepted any `_prune_recordings_now` call
   outside `__init__` — which the helper's own body satisfies — so it passed
   with the cadence call deleted. Now requires a caller that is neither.
3. **A mutation aimed at the wrong line.** Removing `GetCurrentProcess.argtypes`
   did not break S16, because `IsProcessInJob.argtypes[0]=HANDLE` re-widens the
   truncated handle. Probed all four combinations directly: neither set →
   fails (err 6); `IsProcessInJob.argtypes` alone → succeeds;
   `GetCurrentProcess` alone → raises `OverflowError`. The mutation now
   truncates the first argtype to `c_int`, which is the original defect.

## 5. What this cannot see

`_job_status()` reports the **calling** process's job. A value obtained by
importing it from a shell or a test describes *that* process, not the live
supervisor — an earlier verification pass mis-attributed exactly this. The
2026-08-16 blackout question must be answered from the supervisor's own log
line, now that the line can finally say something.

Four findings ([7], [13], [16], [24]) had their verdicts truncated in transit
and remain **unclassified — not refuted**.

## 6. DoD

pytest full suite · smoke **220/0** · assurance **51/0** · overfit **3 ARMED**
passed on a live 15,440-row corpus (4 rungs dark) · ruff clean · pyright **0** ·
bandit 0 issues over 66,721 lines · compileall clean.
