---
title: "Geometry Filing-System Deep Dive (2026-08-06) — One Durable Append, Four Honest Reports"
category: source
summary: "Commit ee0ac4ad. A deep dive into how trade geometry is FILED found the write path itself SOUND — rotation loses nothing, the pending-vector round-trips, the 3+64+22=89 width invariant is exact, and the live pt_frac/sl_frac threaded into log_close IS the traded geometry with no recompute anywhere. A suspected 10.9% ground-truth hole resolved to 34 quarantined QA fills + 3 documented FEATURE_SCHEMA_VERSION drops (exactly the 3 positions open at the v8→v9 bump, matched by position id): nothing was bleeding. What WAS wrong split in two — (1) torn-append fusion, the class found twice before, present in eight more writers, now consolidated into ONE primitive core/runtime.durable_append beside atomic_write_json rather than an eleventh copy; and (2) four places the system wrote down something other than what it meant: a 40-char disposition cap that amputated the bracket geometry on 3,666 of 9,692 corpus rows (ZERO retained a bracket payload), a bracket-divergence gauge publishing 1.0000 that was 94.3% arithmetically incapable of reading anything else, an AuditTrail OSError path that would report the regulated trail of record as permanently TAMPERED for what was crash damage, and a corpus rotation that stamped a fresh cache key onto stale LIVE counters feeding position SIZING (reproduced as a 6x asset overcount the cache protected from correction). Battery 3398 passed / 1 skipped, 22 new tests each RED first."
tags: [session, durability, torn-append, honesty, corpus, geometry, telemetry, audit-chain, instruments, sizing]
sources: 1
source_path: none — session work product (see Provenance)
source_date: 2026-08
authors: [claude]
ingested: 2026-08-06
updated: 2026-08-06
---

# Geometry Filing-System Deep Dive (2026-08-06)

## Provenance

Session work product — no `raw/` snapshot. **One** commit on the working checkout
`liquiditybot_ab`, **head = remote = `ee0ac4ad`**, working tree clean. Battery at commit:
**pytest 3398 passed / 1 skipped** (**22 new tests, each written RED against the unfixed code
first**), **smoke 219**, **assurance 49**, **ruff + compileall clean**. Files touched: 12
(`core/audit.py`, `core/codes.py`, `core/runtime.py`, `data/context_engine.py`, `main.py`,
`ml/history.py`, `ml/postmortem.py`, `ml/retrain_log.py`, `scripts/corpus_sync.py`, plus three
test files) — **+738 / −106**.

The question asked was narrow: **how is trade geometry actually filed?** The answer split into a
**null** (the path is sound), a **durability class** (one shape, ten instances), and **four
honesty defects** (the system wrote down something other than what it meant).

---

## 1. The null — the write path is sound, and nothing was bleeding

**This is a result, not an absence of one.** Five separate suspicions were run down and each
came back clean:

- **Rotation loses nothing.** All **13 `.bak` generations** fully recovered; **0 rows missing**
  from the day's corpus.
- **The pending-vector dict round-trips through `state.json`** — a restart does not orphan the
  feature vector waiting for its close.
- **The width invariant `3 + 64 + 22 = 89` is exactly right** — 3 lead columns
  (`position_id`, `asset`, `side`), 64 features, 22 trailing meta.
- **The live `pt_frac`/`sl_frac` threaded into `log_close` IS the traded geometry.** There is
  **no recompute anywhere on the path** — the corpus records the bracket that was actually
  placed, not a reconstruction of it.
- **The suspected 10.9% hole in the ground-truth sample is not a hole.** It resolved to **34
  quarantined QA-harness fills** plus **3 documented `FEATURE_SCHEMA_VERSION` drops**. The
  decisive check: *at the instant of the v8→v9 bump, exactly 3 positions were open, and they are
  precisely the 3 unlabeled closes — matched by position id.* Not a rate, not a correlation; an
  identity.

> **Nothing was bleeding.** This matters for the corpus's own record: the ground-truth sample
> that [[concepts/payoff-asymmetry]] and the 432-bar cohort ([[comparisons/horizon-96-vs-24-bars]])
> both rest on was audited at the filing layer and is intact.

**But establishing that took forensic reconstruction from `fills.csv`** — because the corpus
emitted **no signal at all** when a close produced no row. That silence is itself one of the four
defects (below, §3.5).

---

## 2. Durability — one class, ten instances, and finally ONE primitive

### The class
[[concepts/torn-append-fusion]]: a kill mid-append — `auto_update`'s `taskkill /F`, or power loss
— leaves a final line with **no trailing newline**. The next append **welds onto that fragment**,
producing one malformed line, and the reader **drops BOTH records**. One kill destroys the torn
record *and* the next good one.

Found and fixed **twice before**: `core/fill_ledger.py` (`b409a24b`, owed item 29h) and
`ml/registry.py` (`4799bfc7`, item 30a). A sweep this session found **the same shape in eight
more writers**.

### The decision: a primitive, not an eleventh copy
> The wiki had already named the honest close for this class:
> *"A sweep that asserts the invariant across all append-only writers — rather than fixing them
> one crash at a time."* ([[concepts/torn-append-fusion]], 2026-08-05.)
> **This commit is that sweep.**

The heal now lives **once**, as **`core/runtime.durable_append`** — deliberately placed **beside
`atomic_write_json`**, its **whole-file sibling**, in a module that is already the **established
import direction** (`ml/models.py` imports from it). Same durability contract, same never-raise
discipline; one is for the file republished whole, the other for the file that grows a record at
a time.

**Three guarantees, in the order the docstring ranks them:**

1. **Size-0 counts as new.** `not path.exists()` alone does not catch a zero-length file, and
   appending a data row to one without the header makes `csv.DictReader` **silently adopt the
   first record as the column names**.
2. **A torn tail is ISOLATED, never repaired.** Writing a separator first leaves the fragment as
   its own junk line that CSV/JSONL readers skip, and the new record lands intact beside it.
   *Repair would have to invent the missing bytes; isolation loses exactly the one record the
   kill already destroyed, and no more.*
3. **`fsync` bounds the torn window** to the single record being written, instead of everything
   since the last OS flush.

**It returns `False` on `OSError` rather than raising** — because **every call site is
bookkeeping on a path where the trade, decision or disposition has ALREADY happened** (CLAUDE.md
invariant 5). Losing a log row must never unwind the action it records.

### The eight call sites adopted

| Writer | File | Why it mattered |
|---|---|---|
| `ml/history.py::_append_row` | `signal_history.csv` | The **89-column ground-truth corpus**. A fused row destroys **two labelled outcomes and their 64-feature vectors**, and `load_training_data`'s `except (KeyError, ValueError): continue` **dropped the chimera with no counter and no log line**. |
| `scripts/corpus_sync.py` | `signal_history.csv` | The corpus's **SECOND independent appender**. Two writers with no heal is **exactly the seam that produced SD-007** (`audit_chain_break`) on the audit chain. Now **one append per recovery batch**, not per row. |
| `ml/history.py::HorizonShadowStore` | `horizon_shadow.csv` | See the size-0 hole below. |
| `ml/retrain_log.py` | `retrain_history.jsonl` | **Reproduced 2026-08-06: one kill destroyed 2 retrain records.** |
| `data/context_engine.py` | `context_history.jsonl` | **The least reversible append in the repo.** Its own point-in-time contract ("never re-fetch") makes a fused snapshot **permanently unrecoverable by design** — there is no second chance to re-read a PIT macro reading — *even though its cadence is the lowest*. |
| `core/runtime.py` | `equity.csv` | 145,576 rows. |
| `ml/postmortem.py` | `postmortem_summary.csv` | Header and row were **two separate literal lists in two different methods**; now one `SUMMARY_COLS` so they cannot drift. |
| `main.py::_append_period_row` | weekly + monthly period ledgers | **The only append-only writer in the repo with NO error handling at all** — an `OSError` propagated straight into the period-close path, so an **unwritable `outputs/` could abort a weekly/monthly roll**. |

### The size-0 hole was not theoretical
`HorizonShadowStore._ensure` creates its header under `not exists()`, **which a zero-length file
passes THROUGH**. A kill in the create-to-first-flush window left a **headerless** file, and
`csv.DictReader` then **adopted the first RESEARCH ROW as its column names**. **Two consumers
read that file that way.**

> This is **instance 2's mechanism, in a different file** — the `fills.csv` create-window bug of
> `46cdc19a`, one day old, reproduced verbatim in the horizon shadow ledger. The strongest
> possible argument for a shared primitive over a per-file fix.

### Preventive, not remedial
**All ten files are clean on disk today** — **9,692 corpus rows · 145,576 equity rows · 29,013
audit records · 25,039 events · plus 44 rotated generations — zero fusions.** The class was fixed
before it fired at scale, which is the only time a durability fix is cheap.

---

## 3. Honesty — four reports that did not say what the system meant

### 3.1 `mark_disposition` amputated the bracket geometry (the largest by row count)

The candidate `disp` column was capped at **40 characters**. A full **SZ-023** disposition is
**113 chars**:

```
SZ-023: p 0.28 below bar 0.63 (net breakeven 0.594 + margin 0.036, derived)
        [bracket pt=2.06% sl=1.54% b=0.983]
```

**40 chars kept it as far as `'(net break'`.**

**Measured on the live corpus:**
- **2,614 SZ-023 rows** lost the `[bracket pt=..% sl=..% b=..]` payload the sizer had *just
  computed*.
- **1,052 SZ-030 rows** lost their net breakeven and `b_net`.
- **ZERO of 9,692 rows** retained a bracket payload. Not "few" — **none**.

> **That geometry is the whole reason a VETOED candidate is worth filing at all.** It is the bet
> that *would* have been traded. And `scripts/gate_efficacy_report.py`
> **regex-scrapes this very field** to recover the thresholded quantity — so the instrument built
> to judge gate efficacy was reading a column that had been cut through the middle of its payload
> for the corpus's entire life.

**Fixed:** cap → **200** (`DISPOSITION_MAX_CHARS`), which clears the longest constructed
disposition with headroom. **`main.py` stops pre-truncating to 40** at three call sites before
the store's own cap — the double-cap was invisible because the outer one was tighter. **A cap
still exists** deliberately: an unbounded free-text column in a 9,692-row corpus is its own
hazard, and the veto strings are **engine-generated, not user input**.

### 3.2 The labeled-vs-traded bracket divergence gauge published a tautology

`bracket_divergence_summary` is the **ML-082 status surface**: it exists to answer *"did the
traded bet resolve where the label says it should?"* — the labeled geometry against the traded
geometry. It reached Grafana as `liquiditybot_bracket_divergence_rate`.

**The defect:** a **`tb_time`** record's counterfactual **IS its realized value**. So its delta is
**0 by construction**, and it **always "agrees"** — it carries **no information whatsoever** about
whether label and trade concur.

**Measured over the instrument's entire production lifetime: 33 of 35 records (94.3%) were
`tb_time`.**

> The gauge read **1.0000** and was **94% arithmetically incapable of reading anything else.**
> An instrument reporting perfect agreement, that could not have reported disagreement.

**Fixed:** each record now carries a **`priced`** flag (`barrier in ("tb_pt", "tb_sl")`).
`agree_rate` and `mean_abs_ret_delta_pct` are computed over the **PRICED subset only** and report
**`None` until one exists**. **`n` still counts every bracket close**, and a new **`n_priced`**
is published beside it — so the pair says *"of N closes, only M could be measured"*, which is the
fact an operator needs and **which a single blended rate hid**.

> **The `None`-not-zero discipline was already in this function** — its original docstring says
> `n=0` returns `agree_rate: None` **"instead of a 1.0 that would read as 'perfect agreement'
> instead of 'not measured'."** The author had seen the exact hazard and guarded the **empty**
> case while the **definitionally-empty** case walked straight through. Absence was handled;
> **vacuity** was not.

**The existing test asserted the old 1.0.** It was **right about the mechanism and wrong about
what should be published** — its docstring now records why, rather than being deleted. See
[[concepts/tautological-instrument]].

### 3.3 `AuditTrail.log` would report the regulated trail of record as permanently TAMPERED

An `OSError` inside `f.write` can fire **PART-WAY THROUGH**, leaving **orphan bytes** with no
newline. The handler dropped the record — but **`_synced` was already `True`**, so **no later
`log()` ever re-adopted the tail**, and the next append **welded onto the fragment**.

Once further records followed, `verify_chain` saw a **mid-file break with `tail_after_break > 0`**,
classified it **`torn=False` → `tamper=True`**, and would report the **regulated trail of record
as TAMPERED — permanently — for what was actually crash damage.**

> **The severity is not data loss; it is a false accusation that does not decay.** This is the
> file the corpus's entire provenance argument rests on
> ([[entities/reason-code-registry]], [[concepts/certificate-hierarchy]]) — the one that
> **convicted the 136 quarantined fixture fills**. A permanent false TAMPER verdict on it would
> discredit the instrument that does the convicting, and the failure mode is
> *indistinguishable from the real thing at read time*.

**Fixed in one line:** re-arm `self._synced = False` on the `OSError` path. `_adopt_tail` already
truncates a torn/malformed final line, so the next write **heals the fragment via the
already-tested path** instead of fusing onto it.

### 3.4 A corpus rotation stamped a fresh cache key onto stale counters — and they feed SIZING

`HistoryStore._ensure_schema` rotates the corpus on a schema change (`os.replace` to a
timestamped `.bak`). Two derived caches — **`_regime_counts`** and **`_asset_live_counts`** —
key on the corpus file's **`(mtime_ns, size)`** and are refreshed **after each append**.

The rotation replaced the file **wholesale** while the in-memory counts still described the
**OLD** corpus. The next append then **stamped the NEW file's key onto the STALE counts** — and
`_load_regime_counts` / `_load_asset_live_counts` saw a **matching key and refused to re-scan**.

> **The cache actively protected the wrong answer from correction.** Reproduced as a **6x asset
> overcount**. A stale cache that expires is a latency bug; a stale cache that has been handed a
> **valid-looking freshness token** is a correctness bug with no self-healing path.

**This is not telemetry.** `asset_live_counts` is **`n_a` in SPB-R scarcity pricing — position
SIZING** — and `regime_live_count` **gates the regime-coverage admission hold**. A 6x overcount
propagates into how much size the bot takes and what it is allowed to admit.

**Fixed:** the rotation now explicitly invalidates both caches
(`_regime_counts_loaded`/`_regime_counts_key`, `_asset_live_loaded`/`_asset_live_key`) before
`_mark_rotated()`.

### 3.5 Two smaller ones, filed because the mechanism generalizes

**(a) The width guard and its warning message were two independent literals.** `_append_row`'s
guard used a correct `22`; its **warning message** used a stale `20` that had silently drifted as
`sg_*` (7 columns) and `entry_price`/`exit_price` (2 columns) were appended. So the message
**reported a phantom 69-column schema against a true 64** — **in the one line a human reads while
debugging a misaligned corpus.**

> A guard that is right and a message that is wrong is worse than both being wrong: the code does
> the correct thing while **actively misdirecting the person sent to investigate**.

**Fixed:** both now derive from **one pair of constants** (`_N_LEAD = 3`,
`_N_TRAIL = 13 + len(SG_COMPONENT_KEYS) + 2 = 22`), **pinned against the live header by a test**.
They cannot drift apart again.

**(b) `log_close`'s `if entry is None: return` was the ONLY unlogged exit in the whole write
path.** A close with no pending feature vector writes no training row — **silently**. That
silence is why establishing that **nothing was wrong** (§1) required forensic reconstruction from
`fills.csv` that **the corpus itself should have made unnecessary**.

**Fixed:** new registered code **`ML-084`** (`ML_UNLABELED_CLOSE`) plus a per-process
`unlabeled_closes` counter. Deliberately **a counter, not an alarm** — legitimate causes exist (a
`FEATURE_SCHEMA_VERSION` bump **deliberately** drops pending vectors, `core/persistence.py`) —
**but it must be VISIBLE**. Report-only: the close itself is unaffected.

---

## 4. What this session changes elsewhere in the wiki

- **[[concepts/torn-append-fusion]] — the class is SWEPT.** The page's own named honest close
  ("a sweep that asserts the invariant across all append-only writers") is **discharged**, and the
  fix moved from a per-file pattern to **one primitive**, `core/runtime.durable_append`.
- **New concept — [[concepts/tautological-instrument]].** An instrument whose reading is fixed by
  construction over most of its population. The bracket-divergence gauge is the type specimen.
- **New citation hazards** in [[synthesis/open-contradictions-register]]: the **1.0000
  bracket-agreement gauge** must never be cited as evidence that labels and trades concur, and
  **no pre-`ee0ac4ad` corpus `disp` column contains bracket geometry** — any analysis that
  regex-scraped it (including `gate_efficacy_report`) read a truncated field.
- **[[comparisons/stated-invariants-vs-audited-reality]]** gains two rows: *"the audit trail
  distinguishes tampering from crash damage"* and *"a vetoed candidate's geometry is on file."*
- **[[entities/historystore]]** — corpus at **9,692 rows**; the disposition cap, the cache
  invalidation, the width-guard literals and ML-084 all live in this module.
- **[[entities/reason-code-registry]]** — **183 → 184 codes** with ML-084.
- **[[synthesis/owed-measurements]]** — the torn-append sweep closes; the ground-truth attrition
  question closes with an identity match; ML-084's first live reading is newly owed.

## Related
[[sources/session-20260805-evening]] · [[concepts/torn-append-fusion]] ·
[[concepts/tautological-instrument]] · [[entities/historystore]] ·
[[entities/reason-code-registry]] · [[entities/liquiditybot]] · [[entities/auto-update]] ·
[[comparisons/stated-invariants-vs-audited-reality]] ·
[[synthesis/open-contradictions-register]] · [[synthesis/owed-measurements]] ·
[[concepts/default-path-fallback-writes]] · [[concepts/iron-law-of-debugging]] ·
[[concepts/honest-data-framing]] · [[concepts/payoff-asymmetry]] ·
[[comparisons/horizon-96-vs-24-bars]] · [[concepts/ghost-badge]] ·
[[concepts/liveness-by-output-cadence]] · [[concepts/certificate-hierarchy]]
