# MANIP-2 / MANIP-3 reconciliation — the SZ-045 stamp is not a row-level fact

**Class: SAFE** (read-only investigation; this memo is the only write).
Author: delegated session, 2026-09-02. No code, config, or ledger touched.

---

## 1. Re-derived counts (as-of; the runner is appending)

Source `outputs/signal_history.csv`. Needles stated verbatim.

| quantity | needle | route 1 | route 2 | route 3 |
|---|---|---|---|---|
| total rows | — | 22,870 | 22,878 | — |
| stamped SZ-045 | `disp == "SZ-045"` (exact, no `:` payload) | 752 | 752 | 752 |
| feature at/above veto | `manip_suspect >= 0.90` | 1,037 | 1,037 | — |
| overlap | both | 548 | 548 | — |
| stamped but feature `< 0.90` | | 204 | 204 | — |
| feature `>= 0.90` but not stamped | | 489 | 489 | — |
| min `manip_suspect` among stamped | | 0.212628 | 0.212628 | — |

- Route 1: `csv.DictReader` stream, read **2026-09-02T13:45:15Z** (file mtime 13:35:12Z, 18,396,086 B).
- Route 2: `pandas.read_csv`, read **2026-09-02T13:47:40Z**.
- Route 3: `grep -c ",SZ-045," outputs/signal_history.csv`, read **2026-09-02T13:47:39Z**.
- The two routes disagree on **total rows only** (22,870 → 22,878: eight rows appended in the
  2m25s between reads). All five load-bearing counts are **identical across routes**. [K]
- The prompt's 2026-09-02T02:52:45Z figures (22,560 / 744 / 1,028 / 544 / 0.2126) are the same
  quantities ~11h earlier; the seam has not narrowed with accrual. [K]
- `disp` for this code is the **bare** `"SZ-045"` — 752/752 rows, one distinct string, no
  `"CODE: message"` payload (unlike `SZ-022`/`SZ-023`, which carry one). The rich message goes
  only to the Python logger. `main.py:4714-4721` vs `main.py:4722`. [K]

---

## 2. Mechanism — confirmed, and it is (a)+(d), not (b) or (c)

### Writer of `disp`
`main.py:1839 _mark_cand` → `ml/history.py:2460 mark_disposition`:

```
for cand in reversed(self._cands):
    if cand.get("asset") == asset and cand.get("direction") == direction:
        cand["disp"] = str(code)[:DISPOSITION_MAX_CHARS]
        return
```

**LAST-WINS onto the NEWEST OPEN candidate for (asset, direction). No id match, no
recency bound, no first-wins guard, unconditional overwrite.** [K]

### Evaluator of the veto
`main.py:4708-4722` (entry loop) and `main.py:5615-5634` (long-book adds).
Both read `float(self._manip_scores.get(asset, 0.0))` — a **per-asset, per-cycle**
scalar refreshed every slow cycle at `main.py:4376`. [K]

### The seam
The candidate ROW is written once, at registration (`main.py:4664` →
`ml/history.py:2379 register`), which is gated twice: the SCS event-sampler latch
(`self._scs_pending[asset]`) and a same-bar dedup (`_last_reg[(asset,direction)] == bar_time`).
The veto runs **every cycle**. Measured registration cadence per asset:
**p50 = 923 s, p90 = 8,366 s, max = 744,845 s** (n = 11,745 consecutive pairs). At a ~5 s cycle
that is on the order of **10^2 veto evaluations per stored row** at the median, every one of them
free to overwrite `disp`, against a single frozen feature snapshot. And the score itself moves:
**|Δ manip_suspect| between consecutive same-asset rows p50 = 0.073, p90 = 0.347, mean = 0.127.** [K]

**So `disp` is a property of the LAST cycle that had an opinion about (asset, direction); the row's
`manip_suspect` is a property of the ONE cycle that registered it. They are different clocks.**
The 204/489 split is what that costs.

### Candidates explicitly separated
- **(a) first-wins ordering — REFUTED as stated, replaced by LAST-WINS-ACROSS-CYCLES.** The code
  overwrites; there is no first-wins guard. In-cycle ordering still contributes (see (d)).
- **(b) different score — REFUTED as the primary cause.** `main.py:4376` and `main.py:6096` call the
  same `manip_suspect_score` (`main.py:370`) on the same `liq_state.spoof_score`,
  `whiplash_suspicion`, `_book_imbalance(kraken_books[asset])`, `_composite_imbalance`. One
  **secondary** divergence survives and is real but small: the refresh at `main.py:4348-4357` applies
  the DL-10 staleness blank-out (`kbook = {}` past `watchdog.stale_critical_sec`), the feature builder
  at `main.py:6087` does **not** — under a critically stale Kraken book the two divergence terms differ.
  Rounding is also refuted quantitatively: the gate compares `round(score, 3)`; re-scoring the stamped
  set at 3 dp moves the overlap 548 → **550**, i.e. rounding explains **≤ 2 of 204**. [K]
- **(c) non-constant threshold — REFUTED.** `config.json risk.manip_gate = {enabled: true,
  downsize_at: 0.6, veto_at: 0.9, min_scale: 0.25}`. One global constant, no per-asset or
  regime scaling anywhere in `manip_entry_scale` (`main.py:394`). [K]
- **(d) the gate is never reached — an UPPER BOUND on the 489, NOT a confirmed majority
  explanation.** *(Downgraded 2026-09-02T14:06:13Z — see §7 C-2; the original text read "CONFIRMED
  for the majority of the 489".)* Disposition breakdown of rows with `manip_suspect >= 0.90` and
  `disp != "SZ-045"`, re-derived **2026-09-02T14:06:13Z** and reproducing exactly:
  `capped 300 · SZ-023 80 · SZ-022 61 · SZ-021 33 · SZ-030 7 · (empty) 4 · SZ-050 3 · SZ-060 1`
  (n=489). [K]
  `capped` is stamped at `main.py:4678` with a `continue` **before** the manip gate, so a cycle that
  stamps `capped` provably did not run the gate. **But that is a statement about a CYCLE, and `disp`
  is not a cycle — it is the last stamp any cycle left on the candidate** (`ml/history.py:2482-2485`:
  no code filter, no recency bound, unconditional overwrite). Reading this table row-wise —
  "`capped` 300 ⇒ the gate was not reached for 300 rows" — is **the identical category error §2's own
  verdict forbids two paragraphs above.** An earlier cycle's `SZ-045` on the same (asset, direction)
  is silently overwritten by a later `capped`, and the row keeps only the loser.
  **Caught in the act, not merely argued** (scratchpad `verify3.py`, read 2026-09-02T14:06:13Z):
  within the `events.jsonl` window, **2 of 46** candidates whose FINAL `disp` is `capped` received
  at least one live `SZ-045` veto event during their open life, as did **3 of 66** whose final `disp`
  is `SZ-021`. So `capped`-as-final-stamp does **not** imply the gate never ran. [K]
  What is established: `capped` **can** pre-empt the gate (code, `main.py:4677-4679`), and it **did
  not always** (the 2/46 counter-examples). The share of the 300 for which it genuinely did is
  **[UNKNOWN]** and is not recoverable from `signal_history.csv` alone — that is MANIP-3.
  The `SZ-02x/03x` stamps are the same stale-stamp seam running the other way (a later cycle's sizer
  veto landing on this row). [K]

### Traced rows (5 + 5, per the brief)
Stamped `SZ-045`, feature below threshold — `(asset, direction, ts, ms | same-asset ms within +1 h)`:

```
MINA +1 1784709634 0.718 | []            <- no later registration; stamp came from a cycle with no row of its own
FLOW -1 1784729950 0.835 | [0.904]
MINA +1 1784731012 0.893 | [0.907]
MINA +1 1784741236 0.589 | [0.946, 0.968, 0.976, 0.950]
MINA +1 1784769684 0.884 | [0.779, 0.311, 0.456, 0.446]
```
Feature at/above threshold, not stamped:
```
FLOW -1 1784781418 0.910 disp='capped'  | [0.580]   <- 'capped' was the LAST stamp; whether the
                                                       gate ran earlier on this candidate is
                                                       UNKNOWN from this row (see (d), C-2)
BTC  +1 1784034626 0.944 disp=''        | []
BTC  +1 1784045795 0.955 disp=''        | [0.000, 0.540, 0.008]
BTC  -1 1784097014 0.934 disp=''        | [0.310, 0.475, 0.683, 0.228, 0.122, 0.078]
BTC  +1 1784508632 0.924 disp=''        | [0.178, 0.759, 0.052, 0.370, 0.234, 0.052]
```
Corpus-wide: **75/204 (37%)** of the low-side stamped rows have a same-asset row within +1 h whose
score is ≥ 0.90, and **257/489 (53%)** of the high-side unstamped rows have one within +1 h below
0.90 — i.e. in roughly half the cases the *neighbouring registration alone* already exhibits the
crossing, and the true veto cycle (unobserved, sub-bar) has ~185 more chances at the median. The
remainder are the (d) cases and cycles that produced no row at all. ([K] on the counts, [I] on the split.)

**Verdict: `disp == "SZ-045"` and `manip_suspect >= 0.90` are not two measurements of one event.
Neither is a corrected version of the other. Joining them row-wise is a category error.**

---

## 3. MANIP-3 — the sizer's manipulation refusal is NOT in the hash chain

`outputs/audit.jsonl` (25.0 MB; grepped/streamed, never read whole), read
**2026-09-02T13:46:00Z**. Needle `"SZ-045"`: **3 lines**, all
`"code": "LB-010"`, `"src": "long_book"`, e.g.

```
{"code":"LB-010","data":{"asset":"BTC","kind":"manip","manip_score":1.0},...,
 "msg":"LB-010: BTC: manip suspect 1.00 >= veto 0.90 (SZ-045)","seq":68577,"src":"long_book"}
```

These come from the **long-book rung** path (`main.py:5615-5634`), not the entry sizer. They carry
`asset` and `manip_score` and **no candidate or position id**. Join rate to the 752 stamped signal
rows: **0/752 — CONFIRMED, and it is structural, not sparse.** [K]

Root cause: the entry-loop veto at `main.py:4714` calls `_log_sizer_veto` (`main.py:4152`), which is
`log.log(...)` — the Python logger — plus `_mark_cand`. **Neither touches `get_audit()`.** No SZ-045
disposition from the entry path has ever been capable of reaching the chain. [K]

**Answer to the question that matters: no. The sizer's manipulation refusal is not auditable from the
hash-chained trail at all.** What exists nearby: `ML-070`/`ML-071` exploration records
(`main.py:4638-4648`, 23,889 lines) carry `{"manip": round(ms,3), "position_id": pid}` at the same
cycle, but they fire *before* the gate and *only* for probe-admitted signals — they record the score,
never the refusal.

### Minimal ADDITIVE record that would fix it (described only — NOT implemented)
One `get_audit().log(...)` call co-located with the existing `_log_sizer_veto` at `main.py:4714`,
inside the `if scale is None:` branch, emitting `Code.SZ_MANIP_SUSPECT` with payload:
`{asset, direction, manip_score: ms, veto_at: self._manip_veto_at, candidate_id:
self.candidates.open_candidate_id(asset, direction), position_id: pid, ts: now}`.

- **Join key already exists on both sides**: `open_candidate_id` is a live API already called at
  `main.py:4841`, and 22,477 of 22,874 signal_history rows carry a `cand-…` id in the
  `position_id` column. A `candidate_id` in the payload makes the join exact.
- **`manip_score` in the payload is the load-bearing half** — it is the *gate's* value at the *veto*
  cycle, which is precisely the number the frozen feature column cannot supply. With it, MANIP-2's
  seam becomes measurable instead of inferred.
- Emitting `direction` matters: `mark_disposition` keys on (asset, direction), so an audit row
  without it cannot reproduce which candidate was stamped.
- **This is BOUNDARY, not SAFE.** It is inside the entry decisioning loop; even a pure-observation
  line there is era-6 cohort-resetting territory and needs operator adjudication. Not written.
- It also does **not** repair the 752 historical rows. Their `disp` remains a last-wins artifact.

---

## 4. What this does to the standing Jaccard 0.462

`vault/wiki/sources/session-20260821-manip-gate-and-live-readiness.md:59-77` records
`both = 277 · disp-only = 104 · feature-only = 218 · Jaccard 0.462`, and
`116/454 = 25.6% of SZ-045-stamped rows record a manip_suspect BELOW the veto threshold`.
Today's corpus: `both = 548 · disp-only = 204 · feature-only = 489 · Jaccard **0.442**`
(548/1241), and **204/752 = 27.1% below threshold**. The seam is stable, not shrinking. [K]

**That measurement does not survive as a claim about the manipulation gate. It was measuring the
seam.** Specifically:

1. **The Jaccard number itself is now explained, not anomalous.** 0.462/0.442 is the expected overlap
   of a per-cycle last-wins stamp with a per-registration frozen feature, given p50 923 s between
   registrations and p50 |Δ| 0.073 per registration. It is an instrument-geometry constant, not a
   property of the manipulation signal.
2. **The page's own headline survives — for a *stronger* reason than it gave.** It found the feature
   arm null (+2.80 pp, z = +0.61, p = 0.542) and the effect riding entirely on the stamp, then killed
   the headline with a placebo showing *every* terminal stamp predicts outcome (`SZ-021 +33.51 pp`
   larger than the manip stamp's `+15.48 pp`). The mechanism found here says exactly why: **a
   last-wins stamp is a recency channel.** It encodes the state of a cycle far closer in time to the
   label window than the row's own features, so *any* stamp leaks outcome information regardless of
   which code it carries. The placebo was right and its explanation is now mechanical.
3. **What must be retracted is the framing of `116/454 = 25.6%` as rows "refused by a threshold they
   sit below".** They were not refused by anything the row records. Nothing was miscomputed and no
   veto misfired — a per-asset per-cycle verdict was written onto a per-candidate frozen row.
4. **Any future study must pick one arm and say so.** `disp == "SZ-045"` answers "was this
   (asset,direction) most recently vetoed for manipulation at *some* cycle while this candidate was
   open" — a stamp study. `manip_suspect >= 0.90` answers "was the book painted at registration" — a
   feature study. There is presently **no instrument in the repo that answers "was THIS candidate
   refused for manipulation"**, and §3 says why: the record does not exist.

---

## 5. Status

- **MANIP-2 — CLOSED.** Mechanism confirmed at `ml/history.py:2460-2488` (last-wins, newest-open,
  no id match, no recency bound) plus `main.py:4678` (`capped` `continue` upstream of the gate — the
  memo originally mis-cited this as `4680`; corrected 2026-09-02T14:06Z).
  Candidates (b) and (c) refuted at code and config level; (b) survives only as a bounded secondary
  (DL-10 staleness asymmetry `main.py:4348` vs `main.py:6087`; rounding ≤ 2 of 204).
  **Amended 2026-09-02T14:06Z (§7):** the mechanism is now confirmed *per veto event* over a 20.5 h
  window (241 events, min lag 62 s, 28.2% low-side — §7 C-1), which is stronger evidence than the
  original neighbour proxy; but candidate **(d) is downgraded to an upper bound** (§7 C-2), so the
  489-row breakdown no longer carries a confirmed majority explanation. CLOSED stands on (a); the
  *composition* of the 489 does not.
- **MANIP-3 — CLOSED as a finding, OPEN as a defect.** Confirmed: 3 audit lines, all `LB-010`
  long-book, join 0/752. The entry-path SZ-045 refusal has **no audit emitter**, so it is unauditable
  from the hash chain by construction. The remedy is specified in §3 and is **BOUNDARY** — it needs
  operator adjudication before anyone writes it. Docket it; do not ship it as SAFE.

## 6. What was NOT run

No significance test, no CI, no bootstrap, no effective-n or power calculation was computed here —
every number above is an **exhaustive count or a distributional quantile over the full corpus**, not
an estimate, so no sampling interval applies. The vault's z-statistics were **read, not re-run**;
this memo does not claim they are arithmetically wrong, only that their `disp` arm measures a
different object than its label implies. No runtime experiment, mutation, or injection was performed
— the mechanism is established by code reading plus corpus arithmetic (registration cadence, |Δ|
distribution, disposition breakdown), not by watching a planted defect fire; a mutation test would
require touching `main.py`, which is BOUNDARY.

> **CORRECTION 2026-09-02T14:05:17Z (C-1).** The original closing sentence read: "The exact
> veto-cycle timestamps are **unobservable** from the shipped artifacts (that is MANIP-3), so the
> temporal argument is corroborated at the neighbouring-registration level (37% / 53%) rather than
> proven per row." **That is FALSE, and it caused the decisive test to be skipped in favour of a
> weaker proxy.** `outputs/events.jsonl` carries timestamped veto lines with the LIVE gate score.
> Superseded by §7 C-1 below, which runs the test.

---

## 7. Correction log — adversarial review, 2026-09-02T14:05–14:06Z [K]

Two CONFIRMED defects. Both are **the memo failing its own §2 verdict**: C-1 asserted an
unobservability it did not test, C-2 made the row-wise inference §2 forbids. Nothing in §1's count
table changed; the counts were re-derived independently at **2026-09-02T14:05:08Z** and reproduce
exactly (`stamped 752 · feature≥0.90 1,037 · overlap 548 · low-side 204 · high-side 489`;
total rows now 22,884, the runner is still appending — scratchpad `verify1.py`).

### C-1 — the veto cycle IS observable, in a bounded window, and the test now runs

**Needle:** `grep -c "manip suspect" outputs/events.jsonl` → **241**, read
**2026-09-02T14:04:28Z** (file 4.8 MB). Identical count for needle `SZ-045`. Second route: JSON
parse of every line, `'manip suspect' in line` → 241. The asset is recoverable from the `msg`
prefix — two distinct message shapes only, `[FLOW]` **139** and `[MINA]` **102**. Sample:
`{"ts": 1788266794.146, "level": "INFO", "logger": "liquiditybot.main",`
`"msg": "[FLOW] sizer veto: SZ-045: manip suspect 0.98 >= veto 0.90"}` [K]

**The test the memo said could not be run** (scratchpad `verify1.py`, read
**2026-09-02T14:05:17Z**): join each of the 241 veto events to the newest prior
`signal_history.csv` row for that asset.

| quantity | value |
|---|---|
| events joined | 241 / 241 |
| lag `veto_ts − row_ts`, p50 | **8,255 s** |
| lag, p90 | **19,780 s** |
| lag, **minimum** | **62 s** — no event is ever same-cycle-fresh |
| lag, maximum | 23,476 s |
| events landing on a row whose FROZEN `manip_suspect` < 0.90 | **68 / 241 = 28.2%** |

28.2% independently matches the corpus-wide low-side share **204/752 = 27.1%** derived from a
different file by a different route. The seam is confirmed **per event**, not merely inferred from
neighbours — the 37%/53% neighbouring-registration proxy in §2 is now the weaker, superseded
corroboration, not the primary evidence. [K]

**Worked example, the overwrite caught live:** candidate `cand-85af3df1-99756` (MINA, direction
−1, row `ts` 1788279031, frozen `manip_suspect` **0.650638**) received **four** separate ≥0.90
veto events at lags 946 / 1,347 / 2,004 / 2,256 s, and its final `disp` is **`SZ-021: regime
crisis`**. Both failure directions in one row: a stamped-vs-frozen mismatch *and* a last-wins
overwrite that erased the manip verdict entirely. [K]

**SCOPE — read before quoting any of the above.** This is a **20.5-hour window on two assets**,
not the corpus:

- `events.jsonl` spans **1788266793.859 → 1788357923.401** = 2026-09-01T12:46:34Z →
  2026-09-02T09:25:23Z (**25.31 h**, 27,076 lines). `signal_history.csv` spans **51.06 days**.
  The observable window is **~2% of the corpus span**. [K]
- `_log_sizer_veto` (`main.py:4152-4160`) emits at **INFO only when `explored` is true**, DEBUG
  otherwise; the file contains **0 DEBUG lines** (levels: INFO 26,965 · WARNING 105 · CRITICAL 5 ·
  ERROR 1). So these 241 are the **exploration-admitted subset of vetoes**, not all vetoes. [K]
- **Denominator warning:** "241 of 752 stamps ≈ 32%" is a **cross-window ratio and is wrong**. Only
  **29** `SZ-045`-stamped rows fall inside the veto-event window at all. 241 events against 29
  in-window stamps is itself the last-wins collapse, ~8:1. [K]
- The log line carries **no direction**, so the join is asset-only; every lag above is a **lower
  bound**. [K]

This does **not** overturn §3 (MANIP-3): the entry-path veto still has **no audit-chain emitter**,
carries no candidate id, and is absent outside this rolling log's retention. What is overturned is
the claim that the temporal argument *could not be made*. It could, it now is, and it strengthens
§2's verdict rather than weakening it.

### C-2 — the 489 breakdown was read row-wise, against this memo's own rule

Downgraded in place at §2 (d). Summary: `capped 300` means only that `capped` was the **last**
stamp before labeling. `ml/history.py:2482-2485` applies no code filter and no recency bound, and
`main.py:4678` proves `capped` **can** pre-empt the gate, never that it **did** for these 300.
Counter-examples exist and were found: **2 of 46** in-window `capped`-final candidates received a
live `SZ-045` veto event during their open life. Candidate (d) is therefore an **upper-bound
hypothesis**, not a confirmed majority explanation, and the true share is [UNKNOWN].
Also corrected: the `capped` stamp is at `main.py:4678`, mis-cited as `4680` throughout the
original. [K]

### What these corrections did NOT establish

No significance test, CI, bootstrap, effective-n or power calculation was run — the additions are
exhaustive counts and quantiles over a fully enumerated window, so no sampling interval applies,
and **no null-power claim is made about the 2/46 counter-examples**: they are an existence proof,
and the 46 is far too small and too window-bound to estimate the `capped` share. No code, config,
or ledger was written; `outputs/` was read only. The other 187 events (those landing on ≥0.90
rows) were not traced individually. `verify1.py`/`verify3.py` are scratchpad, not committed, so
per verification-standard check 7 the numbers above are **reproducible only by re-running the
stated needles**, not by re-executing pinned code.
