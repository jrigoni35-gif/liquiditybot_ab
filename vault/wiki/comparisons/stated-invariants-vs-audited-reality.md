---
title: Stated Invariants vs Audited Reality
category: comparison
summary: Where the architecture documents claim a guarantee and the code audit found it failing — and, as of 2026-08-06, where a load-bearing guarantee was never stated at all, and where one was stated correctly at the top of the file that then measured something else; as of 2026-08-09 the widest gap in the table, THREE risk controls inert from one expression (a getattr default against an attribute PortfolioState does not have), all three failing PERMISSIVE, tickets 13.7% larger than designed — and the first row here that ~3,400 PASSING TESTS covered, because the doubles supplied the missing attribute
tags: [comparison, audit, invariants, gap]
sources: 10
updated: 2026-08-29
---

# Stated Invariants vs Audited Reality

The architecture corpus states guarantees; one audit measured them. This page is the gap.

| Stated guarantee | Audited reality |
|---|---|
| **"Exits are always allowed"** | A deterministic raise in an earlier cycle **starves ALL exits indefinitely** — and the alert text **claims the opposite**. A hedge-open path could submit new risk mid-catastrophe off frozen marks. |
| **Every disposition carries a registered code** | Several codes are **not registered**, including one the assurance spec explicitly claims as enforced. |
| **Latching faults never auto-clear** | Latched state is **not persisted** — a routine restart silently re-arms a CRITICAL latch. "Trip laundered by reboot." |
| **NaN/Inf in an entry path rejects; entries fail closed** | A participation clamp **silently no-ops at zero depth**; a book-walk cost returns **0.0 instead of the veto sentinel** on a wholly empty side; and after a fix, entries proceed on a **frozen** blocked-flag value — **failing OPEN during the one incident that breaks the watchdog**. |
| **A passive round trip is never net-negative by construction** | A shipped code default for the half-spread floor is **4 bps against a configured 26** — which does not clear a 25 bps maker fee. |
| **Full battery green, no gate moved** | The same task shipped a **fleet-wide protection regression** the harness structurally could not see. |
| **Zero subprocess anywhere** | Later ops sidecars shell out, including a force-kill escalation with no identity check. |

## Addition 2026-08-05 — a second exit-blocking corner, found and fixed the same day
The 08-05 debug sweep ([[sources/session-20260805-debug-sweep]], finding 6, LOW · possible)
adds a new row to the first line of the table: if mark, book mid, and fair value are **all**
absent/non-finite while the computed exit limit price is non-finite, the firewall rejects the
exit (`FW_INVALID_PRICE`, `risk_firewall.py:331-335`) and `_submit_exit`'s
`if order is None: return  # rejected orders never escalate` (main.py:2163-2164) means the
escalation counter never increments — **the MARKET rung is unreachable through this path**,
so the escape stays blocked exactly as long as the feed stays poisoned. Reachability is low
(upstream sanitizers). Distinct mechanism from the exit-starvation row above, same stated
guarantee.

**FIXED same day (commit `b409a24b`, [[synthesis/owed-measurements]] item 29f), two guards:**
a rejected exit now **counts an escalation attempt** — the ladder cannot freeze at rung 0 —
and a non-finite computed exit price **falls back mark → ref → entry**, making
`FW_INVALID_PRICE` unreachable for exits even under total feed poisoning. The design stance:
a stale limit anchor is survivable (timeout → ladder → market); a rejected exit is not.
Pinned by `test_exit_ladder_reject`, written red-first. **Invariant #5 is restored in this
corner** — the table's first row now records two found-and-fixed mechanisms, not one open
one.

## Addition 2026-08-05 evening — three more, from debug round 2 ([[sources/session-20260805-evening]])

| Stated guarantee | Audited reality |
|---|---|
| **An emergency remote command is acked only if it will run** (the C-F3 gate) | `remote_control._runner_alive` treated a **fresh** `status.json` as alive — but the **clean-shutdown path writes a FINAL status carrying `runner_state=STOPPED` with a FRESH `written_at`**. For **~2 minutes after every deploy bounce**, a remote `flatten_all`/`stop` was forwarded, ledgered **"applied" (at-most-once, never retried)**, then purged by the next boot as predating `_PROC_START`. **An acked emergency command that never ran.** The earlier **H6** fix covered commands sent **DURING** a boot, not in the **dead gap before one**. **FIXED `f3253f0d`:** a terminal `runner_state` means **DOWN regardless of freshness**. |
| **A cancelled order is cancelled** | Kraken orders carry **no `expiretm`**, and `feed._private_post` **never raises** — on a rate limit, 5xx, or error payload it returns **`None`**. Both cancel paths **discarded that result** and forced local state terminal, so the order left `open_orders()` **while still resting at the venue**. And the **healthy bot's own ~30s `CancelAllOrdersAfter` refresh prevents the venue deadman from ever firing** — the backstop is defeated by the bot being well. **FIXED `f3253f0d`:** terminal transition still happens (a blocked escape is worse), but the residue is **AUDIBLE** — new code **OM-090**, a `cancel_unconfirmed` counter, and a hash-chained audit record naming txid, path, symbol and remaining. |
| **"Hash-chained" provenance protects the model registry** | `ml/registry.py` has **no real chain**: `verify()` compares **one unauthenticated sha256 from the last matching row**, so deleting, reordering or editing the ledger is **undetectable** — and **deleting `registry.jsonl` downgrades every load to "unknown provenance", which `reload()` accepts**. The **ML-011 tamper gate degrades to a log line.** The property is real for `audit.jsonl` and **not** real here, despite the shared vocabulary. **FIXED same day, `4799bfc7`** — see below. |

The first two are the same shape as the table's older rows: **a guarantee that holds on the
happy path and inverts in the corner the guarantee exists for** — a shutdown, a venue error. The
third is different and worth separating: it is a guarantee that was **never implemented at all**,
carried this far by a word (*hash-chained*) that is true of a neighbouring file.

> ~~⚠️ **Citation hazard:** the corpus's decisive provenance argument — *"`order_id` membership in
> the **hash-chained** `audit.jsonl`"* ([[concepts/default-path-fallback-writes]]) — is sound
> **for `audit.jsonl`**. Do not extend the phrase to `registry.jsonl` on the strength of the
> shared adjective.~~
> **RESOLVED 2026-08-05 (late evening), commit `4799bfc7`.** The registry is now **genuinely
> hash-chained** — `prev` + `seq` + content hash, **built the same way `core/audit.py` builds it**
> — with a `verify_chain()` that **walks the links**, and **a broken chain now FAILS the load gate
> instead of authorizing it**. Pinned by `tests/test_registry_chain.py` (**9 tests**: edited row ·
> deleted row · reordered rows · a **rewritten row minting provenance for a swapped artifact**).
> The adjective and the property now agree; the phrase is safe to extend.

### The third row is the one to learn from: the adjective closed the gap, not the audit
Two of the seven older rows above were guarantees that **held on the happy path and inverted in the
corner they exist for**. This one was a guarantee **never implemented at all**, carried for months
by a **word** that was true of a neighbouring file — and it survived every prior audit *because* the
word was in the code. The general form, worth reaching for on any future invariant:

> **A shared adjective is not a shared property.** When two files are described by the same
> guarantee word, check whether they share the *construction*, not the vocabulary. Here the check
> was cheap and the answer was no.

**And the fix found an eleventh bug.** Writing the torn-row case for the chain test surfaced that
`registry.jsonl` had the **same torn-append fusion defect as `fills.csv`** — a crash mid-append
leaves a fragment and the next write **welds onto it**, taking a good record down with the bad one.
Third instance of that class; same heal applied; now [[concepts/torn-append-fusion]].

## Addition 2026-08-05 late evening — two more, both closed with item 30 (`4799bfc7`)

| Stated guarantee | Audited reality |
|---|---|
| **An emergency remote command is acked only if it will run** (same row as R2-1, the *other* half) | `scripts/remote_control.py` treated a **transient `git show` failure** as a terminal **REJECT** and wrote that verdict into the **exactly-once ledger** — so a momentary git hiccup **permanently consumed a valid command**. R2-1 was the command acked-but-never-run; this is the command **rejected but never bad**. **FIXED:** read failures are **left unledgered and retried**, bounded by the command's own **30-minute expiry** — transient recovers, genuinely bad ages out. |
| **A wedged process loses its lock** | `runner.py`'s heartbeat refreshed **unconditionally while `_last_progress_ts is None`**, so a runner hung **during boot** looked alive **forever** and no supervisor or operator relaunch could reclaim the lock — the [[concepts/liveness-by-output-cadence]] shape, liveness judged by a signal the wedged process still emits. **FIXED:** a **bounded boot grace measured from process start** (`lock_boot_max_stall_sec`, default **2x the running stall bound**). |

Both are the table's oldest shape restated: **the guarantee is written for the failure case and
tested on the happy path.** A remote-control ledger that is right about good commands and wrong
about unreadable ones; a liveness heartbeat that is right about a running engine and wrong about a
booting one.

## Addition 2026-08-06 — three more, from the geometry filing-system deep dive (`ee0ac4ad`)

| Stated guarantee | Audited reality |
|---|---|
| **The audit chain distinguishes crash damage from tampering** (`torn` vs `tamper` is the whole point of the classification) | `AuditTrail.log` dropped a record on `OSError` **without re-arming `_adopt_tail`**. An `OSError` can fire **PART-WAY THROUGH `f.write`**, leaving **orphan bytes**; `_synced` was already `True`, so **no later `log()` re-adopted** and the next append **welded onto the fragment**. Once further records followed, `verify_chain` saw a mid-file break with **`tail_after_break > 0` → `torn=False` → `tamper=True`** — and would report **the regulated trail of record as TAMPERED, permanently, for what was crash damage.** **FIXED:** one line re-arms `_synced`, so the next write heals through the already-tested truncation path. |
| **Every disposition carries its reasoning to the corpus** — a vetoed candidate is filed *with the bet that would have been traded* | `mark_disposition` capped `disp` at **40 chars**, cutting **through** the payload: a full SZ-023 is **113 chars** and 40 kept it as far as `'(net break'`. **ZERO of 9,692 corpus rows retained a `[bracket ...]` payload**; 2,614 SZ-023 rows and 1,052 SZ-030 rows lost geometry the sizer had just computed. `scripts/gate_efficacy_report.py` **regex-scrapes this exact field**. **FIXED:** cap → 200, and `main.py` stops pre-truncating to 40 before the store's own cap. |
| **A close either produces a labeled training row or is accounted for** | `log_close`'s `if entry is None: return` was **the ONLY unlogged exit in the entire corpus write path** — no log line, no counter. Ground-truth attrition was **structurally undetectable** from the corpus itself; a suspected 10.9% hole took **forensic reconstruction from `fills.csv`** to disprove. **FIXED:** new registered code **ML-084** plus an `unlabeled_closes` counter. |

**A fourth belongs in the table but has no stated invariant to violate — which is the point.**
`HistoryStore._ensure_schema` rotated the corpus while leaving `_regime_counts` and
`_asset_live_counts` keyed on the **old** file's `(mtime_ns, size)`; the next append stamped the
**new** key onto the **stale** counts and the loaders **refused to re-scan**. Reproduced as a **6x
asset overcount the cache actively protected from correction** — and these are **not telemetry**:
`asset_live_counts` is **`n_a` in SPB-R scarcity pricing (position SIZING)** and
`regime_live_count` **gates the regime-coverage admission hold**.

> **The 08-06 rows sharpen the table's thesis in a new direction.** The earlier entries are
> guarantees **written for the failure case and tested on the happy path**. These three are
> guarantees **nobody had written down at all** — that a tamper verdict means tampering, that a
> filed veto carries its geometry, that a close is accounted for. Each was a **real, load-bearing
> reader expectation** with no invariant, no test and no code asserting it. **An unstated
> invariant is not a weaker invariant; it is one whose violation nothing is looking for.**
> ([[sources/session-20260806-geometry-filing]])

## Addition 2026-08-06 (later) — the sharpest row in the table (`0e30ca09`)

| Stated guarantee | Audited reality |
|---|---|
| **Every append-only writer in the repo heals a torn tail** — asserted one commit earlier, after a deliberate ten-file sweep that consolidated the heal into `core/runtime.durable_append` and found **zero fusions on disk** | **`scripts/session_import.py:366` was never checked.** A **THIRD independent appender to `signal_history.csv`** — bare `open(..., "a")`, no probe, no `fsync`, plus the `if exists()` header branch that leaves a **zero-length corpus headerless** so `csv.DictReader` **adopts the first TRAINING ROW as its column names**. It runs **HOURLY and UNATTENDED** under `corpus_sync --apply`, the worst-placed of the three. **FIXED** in the same commit that added the gate — and **the gate is how it was found**, on its first run. |

> **Every other row in this table is an invariant that was stated and never measured. This one was
> stated, believed, deliberately swept the day before, and still false.** The sweep was careful and
> conducted with the defect shape fully in mind; it still walked past a writer. **A sweep is a
> search whose coverage is a function of attention; a gate is an inventory whose coverage is
> written down.** That is the difference the table has been circling for six rows.
> ([[sources/session-20260806-append-gate]], [[concepts/adoption-is-not-enforcement]])

## Addition 2026-08-06 (later still) — the invariant named the wrong pair, and the ledger proved it (`5c111962`)

| Stated guarantee | Audited reality |
|---|---|
| **"Hedge validity is conditional on correlation: if BTC/ETH correlation decays below the floor, the hedge is a second bet rather than a hedge and gets unwound"** — `execution/hedging.py`'s own module docstring | The unwind measured **neither** pair the sentence implies. It computed `corr(hedge_asset, others[0])` — the hedge's asset against **the alphabetically-first OTHER asset in the universe** — while the open had gated on `corr(exposed, hedge_asset)`. Live, **`corr(ETH, ADA) ≥ 0.55` opened and `corr(ADA, ARB) = 0.00` unwound**, 147 times in 24.65 minutes: **294 fills, $72,433.15 notional on a $4,933 book, $289.73 of fees = 95.6% of the window's $303.07 equity drop, and zero other fills.** The docstring's *concept* was right and no line of code implemented it. **FIXED** by a shared `_exposure_by_asset()` helper so both paths read one definition ([[sources/session-20260806-hedge-thrash]]). |

**This row is a third kind, distinct from both earlier groups.** The table's older rows are
invariants **stated and never measured**; the 08-06 geometry rows are invariants **never stated at
all**. This one was **stated, in the file it governs, at the top, in a sentence any reader would
quote** — and the code below it measured a different quantity **while describing itself correctly
in every log line it wrote**. The 147 unwind reasons all read `correlation 0.00 below floor`:
**true about the number, false about the world**.

> **The lesson is the reverse of the `registry.jsonl` row.** There, a **shared adjective**
> (*hash-chained*) implied a property the code did not have. Here, a **correct docstring** implied
> a computation the code did not perform. In both cases the prose was the only thing anybody
> checked. **Read the expression, not the sentence above it** — and note that the sentence names
> **BTC/ETH**, a pairing the live seven-asset universe (`PAXG ETH BTC SUI ARB MINA FLOW`) does not
> privilege in any way. **A docstring that has outlived its example is evidence nobody re-read it
> when the universe changed.**

## Addition 2026-08-09 — THREE risk controls at once, and the widest gap in this table (`1fee174e`)

([[sources/session-20260809-adversarial-audits]] §1.) One expression —
`getattr(state, "positions", {}).values()`, at three sites in `risk/position_sizer.py`, against a
`PortfolioState` that **has no `positions` attribute** — took the `getattr` default
**unconditionally, for the life of the module.**

| Stated guarantee | Audited reality |
|---|---|
| **Aggregate portfolio heat is capped** — `max_portfolio_heat_frac` **0.35**, enforced by a veto with its own registered code `RP_HEAT_FULL` | **Unreachable.** Heat computed over an empty dict reads **0.0000** always. Measured on the live book: true gross heat **0.1176**. The panel *"Heat vs cap"* had read **0.0% forever** and was the visible symptom. |
| **Sizing reserves capacity against the side the book is already loaded on** — the signed-inventory reservation skew, code `SZ-061` | **Never applied.** Measured live signed heat **+0.1052**, read as **0.0000**. |
| **Ticket size tapers as the book fills** — inventory aggression from `light_boost` **1.10** toward `heavy_cut` **0.65** | **Pinned at 1.10** — a **permanent 10% size-UP**, the boosting end of the taper, applied as though the book were always empty. Correct multiplier on the live book: **0.9488**. **⇒ tickets 13.7% LARGER than designed**, precisely when risk was already on. |

**Three rows, one line of code, and the direction is the finding: all three failed PERMISSIVE.**
There is no reading of this defect in which the bot was too cautious — a dead heat gate cannot
veto, a dead skew cannot reserve, and the aggression term's *default* end is the *boosting* end
([[concepts/self-flattery-gradient]]).

> **What makes this row different from every other row above.** The earlier rows are invariants
> that **were measured and found failing**. This one was **covered by tests that passed** — ~3,400
> of them — because the test doubles supplied the attribute production lacks
> ([[concepts/test-double-fidelity]], [[synthesis/governance-doctrine]] rule 15). The sharpest
> detail: the test that hid it, `test_open_heat_reads_position_size_not_units`, **exists to catch
> this exact failure class**, and its own fixture reintroduced the class one level up.
>
> **The table's rule extends:** *a stated invariant is a design intent until something measures
> it — and a test is not a measurement if its fixtures are the only place its premises hold.*

**Post-fix verification (live, after the bounce):** `status` `heat_frac` reads **0.1177**, where
it had been structurally 0.0 for the entire life of the instrument.

## Addition 2026-08-29 — the cut-#8 fee cluster, two fail-opens, and a guard that was understated against its own purpose (session cdb03d59)

A 38-agent stated-vs-real audit (miscommunication-mishap workflow) surfaced
32 candidates, **29 CONFIRMED by injection** (3 refuted). Two are the
table's sharpest recurrence — a safety control that **fails PERMISSIVE**:

| Stated guarantee | Audited reality |
|---|---|
| **"Understated fees make the pre-trade gate approve net-losing trades"** — `core/config_guard.py`'s own FATAL, the whole reason it reads live fees | The floor it enforced was **`25/40` — the RETIRED pre-cut-#8 tier** — while cut #8 (2026-08-28) moved venue truth to **`40/80`**. So any config in **`[25/40, 40/80)`, up to HALF the true taker leg**, passed the FATAL silently, and a config that DELETED the fee keys fell to the guard's own 25/40 fallback and also passed. The gate that exists to catch understated fees **was itself understated by half**. Not live-mispriced (shipped config = 40/80, passes correctly), but a **dead backstop at venue truth**. **FIXED `0a06f619`** (2026-08-29): floor → 40/80, injection-proven the live 40/80 config's verdict is UNCHANGED (strict `<`, sits exactly at floor) and only future understated configs are newly rejected — SAFE. New pins `tests/test_config_guard_fee_floor.py`, mutation-killed (regress → 7 red). |
| **`risk/leverage.py` margin health: "scaled below 200%, entries blocked below 150%"** (module docstring) — the buffer is the point | A **missing/failed** `TradeBalance` read returns `0.0`, and the guard `elif margin_level_pct > 0:` (leverage.py:75) treats 0.0 as **"no constraint"** rather than **"unknown → unsafe"** — so on a margin-fetch failure the governor **AUTHORIZES full leverage (up to region_cap 10×)** exactly when the signal the buffer needs is absent. Reason list is **byte-identical** for margin=0 (unread) and margin=300 (healthy) — the [[concepts/zero-is-not-a-reading]] shape, same class as the dead heat gate. Gated behind live-arming (`use_margin=True` AND not dry_run), so paper-inert, but **live-armed on any fetch failure**. **DOCKETED — cohort-resetting** (the fix changes leverage decisioning; and naively routing 0.0→block would cap ALL dry-run leverage since the fetch never runs in dry-run, so the real fix must separate dry-run-unknown from live-fetch-failed). Sibling: `core/watchdog.py:140` `book_ts.get(a, 0.0)` reads a never-delivered book as **age 0 / fresh** instead of stale (main.py:4356/4779 use the fail-closed default). |

Plus a **stale cut-#8 fee cluster** (~12 Important/Minor sites — fallback
literals and docstrings still at 25/40 across `pretrade.py`,
`market_maker.py`, `history.py`, `labeling.py`, `fair_value.py`,
`assurance_check.py`, `hedging.py` prose, `config.json` notes): latent
while the config carries the keys, but the exact "next fee-key edit passes
permissive" trap. SAFE coherence pass in flight (docstrings freely; fallback
literals only where PROVEN unreached; `market_maker` fee default scrutinized
as possibly-reached = would be cohort-resetting).

> **A new row-shape for this table, and it is about the auditor, not the
> code.** The same session's own ad-hoc extraction snippets carried FOUR
> instrument misreads (candidate/fill pooling, `spread_bps`×10 scaling, a
> regime one-hot probe with a `"0.000000"≠"0"` string bug — AND a
> *self-correction of that probe that was also wrong* — see
> [[concepts/the-method]] "Measured recurrences"). The stated-vs-real gap is
> not only a property of shipped code; it is the default failure mode of any
> under-governed instrument, including the session-side snippet reading the
> corpus. The corpus-column trap catalog (stored*10=bps, `sigma_bar_pct` is
> a percent, `*_pct` fractions, `_dir` side-relative, `''`==UNKNOWN) is being
> filed into `ml/history.py`'s schema block so the next reader does not
> re-derive the traps by stepping in them.

## What this is not
It is not evidence the invariants are wrong or performative. Six of the seven were found **by the
project's own audit**, filed with severity, and fixed TDD with a failing repro first. The clean-area
consensus in the same audit independently confirmed the firewall, the sanitize boundary, the detector
clamps, purging, and the evidence floors.

## What it is
Evidence for a rule the corpus demonstrates repeatedly: **a stated invariant is a design intent until
something measures it.** The corpus's own doctrine of
[[concepts/adversarial-verification|verifying rather than assuming]] is the correct response, and the
one fix that created a new fail-open path is the reminder that **fixing a fail-closed bug can create a
fail-open one**.

## Related
[[sources/whole-code-audit]] · [[concepts/parallel-domain-audit]] · [[concepts/assurance-spine]] ·
[[concepts/torn-append-fusion]] · [[sources/session-20260805-evening]] ·
[[sources/session-20260806-geometry-filing]] · [[sources/session-20260806-append-gate]] ·
[[sources/session-20260806-hedge-thrash]] · [[concepts/two-paths-one-quantity]] ·
[[concepts/zero-is-not-a-reading]] ·
[[concepts/adoption-is-not-enforcement]] · [[concepts/tautological-instrument]] ·
[[entities/historystore]] · [[entities/reason-code-registry]] ·
[[synthesis/owed-measurements]] · [[sources/session-20260809-adversarial-audits]] ·
[[concepts/test-double-fidelity]] · [[concepts/self-flattery-gradient]]
