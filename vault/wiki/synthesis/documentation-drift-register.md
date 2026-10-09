---
title: Documentation Drift Register
category: synthesis
summary: Architecture claims superseded by later work, tracked so a stale doc is not read as current truth — as of 2026-08-06, shipped source comments that were already stale at commit time; as of 2026-08-07, a Definition-of-Done claim (the pyright ratchet) that had been unverifiable on the box for weeks, and a commit message describing a deploy path ("the normal auto_update bounce") that does not exist for locally-authored commits; as of 2026-08-09, the sharpest class yet — stale strings that ship INSIDE a running instrument and inside a passing test, believed because they run: an overfit report calling total loaded rows "live rows" (which made a false root cause plausible for a day) and a config_guard comment plus a test NAME still asserting a premise that had been falsified the night before; then the register's first INVERTED row — a test that pinned a string rather than a property and so went RED on correct code — beside a CLI rejection message claiming to mirror a gate it does not implement; and closing that day, the strongest false claim on any board (a hero tile describing itself as "the true bottom line… hedges included" while plotting the one figure that excludes hedge fees) beside a test docstring that named the exact bug class its own fixture was hiding; and as of 2026-08-10 the most operationally dangerous shape yet — a BOUNDARY DECLARATION that disagrees with its own commit stamp (config.json and config_guard both date execution-era boundary #4 to 2026-08-09 when aeeaae36 is stamped 2026-08-10T11:03:35Z), beside a reason code (XV-023) in circulation that core/codes.py never registered — the boundary-declaration row RESOLVED the same day by 2fee7f64 (the shipped strings now carry the true UTC instant, and the exec_era column plus the era-4 gate tests pin it in code); the XV-023 row STANDS at a head that registered two other codes; and as of the cut-#7 session (2026-08-11) the register's first PHANTOM KNOB — config.json documents stop_round_buffer_bps as a live tuning surface while the only reader looked it up in config[risk_management], a block that has never existed, so the knob was wired to nothing and the coinciding 5.0 default made the disconnection invisible — RESOLVED at e7d5ca1a (reader retargeted to config[risk], pinned so nothing may read the nonexistent block again); and at the 2026-08-11 since-6am audit three rows swept in one pass (the stop_placement docstring's phantom-block reference, the Osler test docstring describing the retired tighten-above semantics, and _goals_doc still narrating the $5,000 regime — rewritten for the $800 stressor), the phantom-knob row upgraded from resolved to GUARDED (config_guard now checks the stop_round knobs at the declaration-consumer join), all 14 commits since 2026-08-10T11:00Z verified claim-vs-diff clean, and one recurrence caught: the audit's own ledger lens quoted the stale 16/26 Kraken schedule out of config.json's rationale — the falsified premise still propagates from the doc, and only the vault's flag caught it — CLOSED AT THE SOURCE by the apply-batch 66744ed1: a stale-fee note now ships in config.json market_maker recording that min_half_spread_bps=26 descends from the struck schedule, so the propagation vector itself carries the correction (the knob deliberately NOT retuned — quote-pricing is cohort-resetting, held behind the h432 gate)
tags: [register, drift, architecture]
sources: 24
updated: 2026-08-16
---

# Documentation Drift Register

The architecture corpus was written across several revisions and audits. These claims are **stale**.

| Stale claim | Where | Current truth |
|---|---|---|
| The 5-gate engine is the live path | base architecture map | the engine was switched; a third doc hedges with "5-gate/informed-flow" |
| "The MLP must beat the logistic baseline" | base map | the zoo is now logistic / gbt / blend / mlp / adaptive_gbt on an evidence-gated ladder |
| Calibration makes probabilities "mean what they say" for sizing | base map | **selection stays on raw Brier**; "calibration must not rescue complexity"; it is a final deploy check only |
| REST polling for books | base map | books via **websocket** — and the audit found its checksum never validated |
| "153/153 tests passing" | security audit | superseded (2742 pytest / 219 smoke / 47 assurance in the latest full run) |
| "Zero subprocess anywhere" | security audit | later ops sidecars shell out, including a force-kill escalation |
| The threat model enumerates only REST responses | security audit | the websocket surface is never mentioned |
| Offline self-test has 36 checks | assurance spine table | the same document's verification block says 47 |
| Smoke test has 188 checks | assurance behavior-delta | the same document's verification block says 205 |
| A detector code is "adopted with full semantics" | research sweep | another doc says the same code is **"not built"** — and the two assign it **different subjects** |
| "v1: four detectors" | THALES header | six are catalogued in the same section |
| A config fingerprint code is enforced | assurance trace matrix | the audit lists it as **needing registration** |
| Rate limits stated in incompatible units | hardening vs compliance | 30/min order screening vs 3/sec REST transport — different layers, never reconciled |
| "Dry-run paper mode" framing | compliance | live spot **and** margin paths exist and are documented, even if unarmed |
| "**246 fills and ~$143 of spread in 21 minutes**" / "121 times" | `execution/hedging.py`'s unwind comment and `tests/test_hedge_thrash.py`'s docstring, both shipped in `5c111962` | **A mid-incident snapshot.** The thrash kept running while the fix was written. Final ledger tally: **147 round trips, 294 fills, $289.73 of fees, 24.65 minutes** (20:09:40.459–20:34:19.303). **The shipped source understates its own incident by roughly half** — quote [[sources/session-20260806-hedge-thrash]], not the comment. The docstring's "121 times / 246 fills" is also internally inconsistent by two fills. |
| "if BTC/ETH correlation decays below the floor… gets unwound" | `execution/hedging.py` module docstring | The universe is **seven assets** (`PAXG ETH BTC SUI ARB MINA FLOW`) with **no privileged BTC/ETH pairing**; the live thrash was **ETH-exposed, ADA-hedged**. The sentence describes the intent correctly and **names an example that predates the universe** — and, until `5c111962`, no code performed the computation it describes ([[comparisons/stated-invariants-vs-audited-reality]]). |
| `# asset -> latch ts (FW-060)` | `execution/hedging.py:75`, shipped in `cf454d5e` | The latch's registered code is **FW-070** (`FW_HEDGE_CHURN_LATCH`); **FW-060 is `FW_NO_REFERENCE`**, a different firewall mechanism. The emitting code and `core/codes.py` are correct; only the comment points at the wrong registry entry. Stale **at commit time**, in the very commit that registered the right code ([[sources/session-20260807-hedge-churn-guards]] §6.3). |
| "What shipped, exactly per the DEADLOCK DISCIPLINE above" | `docs/quant/2026-08-07_ada_hedge_churn_HANDOFF.md` RESOLVED section (`21769fb8`) | **Inexact by half a rule:** discipline rule 3's second sentence — *"Persist the correlation estimator's sample count too"* — did **not** ship; `samples` appears nowhere in `core/persistence.py` (only the hedger's guard clocks ride the snapshot). Every boot re-colds the estimator; direction safe, owed item 35(a). The doc's own resolution notice overstates its conformance to the doc's own rules. *(08-07 panel: escalated — the circulated `cf454d5e` record is **false on four verified counts**, rows below.)* |
| "churn guards: OPENS only, exits untouched" | `execution/hedging.py:238` comment (and the D4 record) | **The guards gate TRIMS too.** The warm check and `_open_blocked` sit above the trim block (`hedging.py:239-291`), suppressing the delta-reducing partial exit that `main.py:2634-2646` itself classifies "risk REDUCTION, never gated." Judge-reproduced live, re-verified at filing. The code contradicts its own comment three lines up ([[sources/session-20260807-institutional-review]] §D). |
| "12 ticks — reachable well inside the 0.5h median uptime" | churn-guards record + wiki copy of it | **False at the floor:** 12 × `candle_refresh_sec` 150s = **30 min = exactly the median uptime** (`main.py:4041` passes no `bar_ts`). Roughly half of process lives never reach warm. |
| "INCIDENT #2, hours after #1's fix" / "5c111962 held" | the churn-guards filing and resolution notice | **The deploy-gap is inverted:** the 147-lap churn ran on **pre-`5c111962` code** (D3 committed 01:53Z — after the event ended — deployed 02:08Z), and the "two incidents" are **one ledger event double-filed under two clocks** ([[synthesis/open-contradictions-register]] #19). The record's timeline was never checked against `auto_update.log`. |
| "the exposure is computed once" | Jane Street lens citation of `5c111962`'s fix (and any wiki echo) | **The helper is *called* at both `hedging.py:184` and `:230`** — one *definition*, two *computations*. "Shared function" ≠ "computed once per cycle"; the panel's prescription is a frozen per-cycle `HedgeCycleInputs` ([[concepts/two-paths-one-quantity]]). |
| The zero-error **pyright ratchet** as a standing DoD gate | repo CLAUDE.md (Definition of Done) | **The stage had quietly not existed on the box for weeks:** pyright was never installed; `test_windows.bat` printed `SKIPPED` and every local "battery green" asserted a type gate that did not run — the ratchet's zero was real only in cloud-session environments. Repaired in the capacity sweep (`00bd0e52`+`101f7436`): the bat **hard-fails on a missing tool**; pyright **1.1.411** in-venv, **0 errors on shipped scope, measured**. The claim is now true again — by measurement, not by assertion ([[sources/session-20260807-capacity-sweep]] §1b, [[concepts/false-green]]). |
| The `cf454d5e` battery record: `… ruff · pyright 0 …` | churn-guards resolution record (and this wiki's copy of it) | **Did not hold on the pulled tree.** That commit's own hedger snapshot section grew `core/persistence.py` `restore()` to **C901 42 > 40**, so full-scope ruff on the production tree was **RED** — unnoticed because nobody ran full-scope ruff after the pull and the local pyright stage was printing `SKIPPED`. Fixed by extracting `_restore_subsystem_sections` per the file's own convention. An environment's battery record certifies **that environment**, not the box the code deploys to ([[sources/session-20260807-capacity-sweep]] §1a). |
| "Deploys via the normal auto_update bounce; the next respawn archives the current 153MB" | `48a63610`'s commit message (the child-log rotation feature) | **There is no "normal auto_update bounce" for a locally-authored commit.** `decide()` routes local==remote/local-ahead to paths that **never touch the runner** — only externally-pushed commits bounce it; the pushers reload on any rev change, making the log *look* like a deploy happened. The commit deployed anyway **only because its one file was `pc_supervisor.py`**, the single self-restarting file. Stale **at commit time**, same class as the `5c111962`/`cf454d5e` rows: the author described the deploy path from memory while shipping evidence of the opposite ([[sources/session-20260807-evening-ops]] §2, [[entities/auto-update]]). The rotation half of the sentence came TRUE 15 minutes later — verified live. |

## The 2026-08-09 additions: **an instrument that printed the wrong noun, and a test that pinned a dead premise**

Four rows from the corpus-corruption filing ([[sources/session-20260809-corpus-corruption]]),
all fixed at source in `3c0debd7`. They belong together because each is a **stale string that
was load-bearing for a conclusion**, not merely inaccurate.

| Stale claim | Where | Current truth |
|---|---|---|
| The overfit report labels its row count **"live rows"** | `scripts/overfit_check.py:216` (report string) and `:9` (module docstring) | **It is LOADED rows — candidate + live, after every filter.** The battery printed **`live rows=467`** for a corpus holding **305 live rows total** that is **append-only** — an arithmetically impossible number, read for a day as growth rather than as the alarm it was. It is what made the false root cause of [[sources/session-20260808-night-staleness-overfit]] §2 *plausible*. Report string now reads `live history ({len(X)} rows)`. |
| "the synthetic→live switch happens at **60 rows**" | the wiki, sourced from a **long-deleted** literal | **The predicate is `len(X) >= len(FEATURE_NAMES)*10` = 640** (`:180-182,:207`). The flat `60` was **deleted 2026-07-11 by `7486ab29`** — stale by a month when it was filed. |
| "**book_ts is stamped at read time, not data time**" | `core/config_guard.py:2835-2848` explanatory prose | **Falsified by `36fcfd6e` the night before** — books now carry `recv_ts`, the feed's own write stamp. The guard's comments are read as *authority* on what an invariant is, so a stale rationale here propagates further than most. Rewritten. |
| The same dead premise pinned in a **test NAME and assertion message** | `tests/test_audit_fixes.py` | **A green test reads as ongoing confirmation of whatever its name asserts.** A premise encoded in a test name outlives the premise unless someone renames it — and nothing fails when it goes stale, because the test still passes on the new behaviour. Rewritten. |

> **The lesson these four share:** *the register's existing rows describe documents that
> aged out of agreement with the code. These describe an **instrument** and a **test** —
> artifacts that are believed **because they run**.* A stale doc is read sceptically; a
> **printed number** and a **passing test** are read as evidence. **Prose that ships inside a
> measurement is not documentation — it is part of the measurement**, and it should be
> re-read whenever the quantity it names changes.

### Two more the same day, from `8e9d7e6f` — including the register's first *inverted* row

([[sources/session-20260809-gate-policy-and-self-heal]] §2–§3.)

| Stale claim | Where | Current truth |
|---|---|---|
| *"This mirrors the bot's own auto-retrain deploy gate"* — the CLI's REJECT message | `scripts/train_meta.py:126` | **False in exactly the case that matters.** The CLI lacks the ML-083 era-orphan branch `main.py:6330` has, so on an orphaned badge it **REJECTS what the runner ACCEPTS** — measured live 2026-08-09 (CLI REJECTED 0.2714 at 00:52; runner DEPLOYED 0.2473 at 02:56). The message is doubly costly because the bot's own **ML-032** text instructs the operator to run this script. **Registered as [[synthesis/owed-measurements]] item 49; not yet fixed** — it is a behaviour change, deliberately unbundled. |
| A test asserting a property via **bare substring match** | `tests/test_audit_ml_offline.py` | The check read **`"2\|0 live labeled trades"`** as the **`"0 live labeled trades"`** it meant to forbid, so it **FAILED on a report that proves the fix**. Now **word-boundary anchored**. |

> **The second row inverts this register's usual direction and is worth stating separately.**
> Every other row here is a stale claim that stayed **green** while the code moved underneath
> it. This one went **red on correct code** — a test that pinned a *string* rather than a
> *property*, so improving the code broke it. **Both failure modes have the same root:** the
> artifact encodes a *rendering* of the truth instead of the truth. A rendering that stops
> matching either lies quietly (row 1) or cries wolf (row 2), and the second is only less
> dangerous because someone must look at it.
>
> **The register's reading rule extends accordingly:** *when a test fails on a change you
> believe is correct, check whether the test pins the property or the prose before assuming
> the change is wrong.*

### The adversarial-audit rows (2026-08-09, later) — a panel description and a test docstring

([[sources/session-20260809-adversarial-audits]].)

| Stale claim | Where | Current truth |
|---|---|---|
| *"the true bottom line, never resets, hedges included"* | the description on the Grafana hero tile **"Net P&L (all time)"** (audit A defect **D1**) | **All three clauses false of the series it plots.** The tile plots `liquiditybot_realized_total` = **−208.31** against a true all-in of **−382.34**: `realized_pnl_total` nets **closing-leg fees only**, so it is not the bottom line, and the **185.94 of opening-leg (entry AND hedge) fees is exactly what it excludes** — the clause *"hedges included"* is false in the specific way the number is wrong. **The strongest false claim on any board.** The underlying number is **FIXED by `a6334162`**; the **board still points at the old series**, and the repoint is now **unblocked** (it required the new keys to exist in the running process — `gc_pusher` skips absent keys — which is true post-bounce). |
| *"an earlier draft read a nonexistent `units` attribute … made the RP-050/051 heat gates unreachable in production"* | the docstring of `tests/test_protocols.py::test_open_heat_reads_position_size_not_units` | **Accurate about the past and blind to the present.** The same test's own fixture, `class _State: positions = {...}`, **supplied an attribute `PortfolioState` does not have**, so it guarded a nonexistent field on `Position` **while depending on a nonexistent attribute on `state`** — hiding the identical bug one level up for the life of the module (`1fee174e`, [[concepts/test-double-fidelity]]). The docstring is **true and reassuring and was covering a live risk defect**. |

> **What the second row adds to this register.** The 08-09 morning rows established that a
> **passing test** is read as evidence because it runs. This row is sharper: the test's **prose
> named the exact failure class**, which made it read as *coverage of that class*. **A docstring
> that names a bug is not a guarantee against the bug** — it is a claim about the test's
> intent, and intent is not scope.
>
> **Reading rule, extended:** *a comment that says what a test protects against tells you what
> its author feared, not what the test covers. Check the fixture, not the docstring.*

## The 2026-08-06 additions are a new kind of drift: **source comments, not architecture docs**

Every row above them describes a **document** that aged out of agreement with the code. The two
hedging rows describe **comments inside the shipped file**, one of which was written **during the
incident it describes** and was already stale **at commit time**. That is a faster clock than this
register was built for, and it produces a sharper hazard: an architecture doc is read
sceptically; **a comment three lines above the code is read as the code's own testimony.**

> **A number written while an incident is still running is a snapshot, not a measurement.** Where
> a comment must cite an incident, cite the **ledger query that reproduces it** — here,
> `outputs/fills.csv` filtered to `symbol=ADA/USD` and `purpose in (hedge, exit)` over the window
> — so the reader can re-derive the final figure instead of inheriting the interim one.

## The 2026-08-10 additions: **a boundary date that is off by a day in the artefact that defines it, and a reason code that was never registered**

([[sources/session-20260810-fill-double-count]].)

| Stale claim | Where | Current truth |
|---|---|---|
| **`"OWED 57 / EXECUTION-ERA BOUNDARY #4 (2026-08-09)"`** and *"reproducing a pre-**2026-08-09** cohort"* | `config.json:376` `_passive_hazard_with_book_doc` **and** `core/config_guard.py:471-480`'s comment — **both shipped, both running** | **The commit is stamped `2026-08-10 06:03:35 −05:00` = `2026-08-10T11:03:35Z`** (git author *and* committer). The 08-09 date is the *session's* narrative date — the two preceding commits are `2026-08-09 16:06 −05:00` — but **a cohort cut is arithmetic on a timestamp**, and any consumer that trusts the `_doc` cuts ~14h early. **Measured blast radius: a naive `2026-08-09T00:00Z` cut misclassifies 4 ledger rows** (0 `post_only`, 2 entries) as post-boundary. Small, and the *only* reason it is small is that the ledger happened to be quiet. |
| **`XV-023`** cited as a reason code by this vault (owed 40b, 57b) and by `config.json:371` | declared **only** in a docstring, `core/fill_calibration.py:17` | **`core/codes.py:364-366` registers `XV-020`, `XV-021`, `XV-022` and stops there.** XV-023 is a code in circulation that the registry has never heard of — the same shape as this register's older *"a config fingerprint code is enforced / the audit lists it as needing registration"* row. Caught while deciding **not** to mint an XV-024 for owed 57b ([[entities/reason-code-registry]]). |

> **The first row is this register's most operationally dangerous shape to date, and it is a NEW
> one.** The older rows describe prose that *aged* out of agreement with code. The 08-09 rows
> describe prose that ships *inside a running instrument*. **This row is prose that ships inside
> the instrument AND defines the boundary the instrument exists to declare** — the `_doc` is not
> commentary *about* boundary #4, it is the corpus's canonical statement *of* it, and it is the
> string a future session will grep for when cutting a cohort. **A boundary declaration that
> disagrees with its own commit stamp is a self-refuting artefact.**
>
> **Fix direction (not applied here — `raw/`-side, operator's to edit):** the `_doc` should carry
> the **UTC stamp**, not a date; the vault's copy already does
> ([[concepts/paper-real-boundary]] rule 4, standing question 4 in `CLAUDE.md`/`AGENTS.md`).
> Domain rule 9 exists because [[synthesis/open-contradictions-register]] entry 19 double-filed
> one churn purely on local-vs-UTC rendering — **the same class, one layer up: there it split one
> event into two, here it moves a regime boundary by fourteen hours.**
>
> **FIRST ROW RESOLVED same day by `2fee7f64`** (2026-08-10T11:36:47−05:00,
> [[sources/session-20260810-stressor-epoch]] §0): the shipped `_doc` and `config_guard`
> comment now carry the real UTC instant `2026-08-10T11:03:35Z`, and `6fe6d98d`'s `exec_era`
> provenance column plus `d6112bca`'s `tests/test_era4_gate.py` pin the instant in code — the
> boundary declaration, the ledger rows, and the gate now agree by construction
> ([[synthesis/comparability-boundaries]]). **The XV-023 row STANDS** — still unregistered at
> a head that added two other codes (`core/codes.py` verified at the stressor filing, 193
> codes, stops at XV-022).

## The 2026-08-11 addition: **the register's first PHANTOM KNOB — a config surface wired to nothing**

([[sources/session-20260811-cut7-geometry-epoch]] §3.)

| Stale claim | Where | Current truth |
|---|---|---|
| **`stop_round_buffer_bps` is a live tuning knob** (documented beside `_stop_round_doc` in the `risk` block, present, defaulted, apparently governing the Osler nudge) | `config.json` `risk` block; the reader in `main.py nudge_stop_off_round_number` | **The knob was never read.** The reader looked it up in `config["risk_management"]` — a block that **has never existed** — so every lookup fell to the hardcoded default, and **only the coincidence that the default (5.0) equalled the configured value made the disconnection invisible.** Operator turns of the knob would have silently done nothing. **RESOLVED at cut #7 (`e7d5ca1a`)**: reader retargeted to `config["risk"]`, `stop_round_offset_bps` added beside the buffer, and **pinned — nothing may read the nonexistent `risk_management` block again.** |

> **Why this is a new shape for this register.** Every prior row is prose that disagrees with
> code. This row is **structure that disagrees with itself**: the config file presents a
> control surface, the code presents a consumer, and the join between them is a key that
> matches nothing — each half individually correct-looking, the pair wired to nothing. It is
> the config-plane sibling of [[concepts/false-green]] (turning the knob "works" — no error,
> no effect) and of [[concepts/default-path-fallback-writes]] (the lookup's silent fallback to
> a default is what buried the miss). The discriminator that catches the class is the same
> AST-over-grep move as ever: **trace the read, not the declaration.** And note the
> compounding: the phantom knob hid inside an instrument that was ALSO nearly dormant and ALSO
> semantically inverted ([[entities/osler]]) — three defects in one nudge, each masking the
> others' observable consequences.

## The 2026-08-11 since-6am audit: three rows swept in one pass, and the phantom-knob row gets its guard

([[sources/session-20260811-operator-audit]] §7.)

| Stale claim | Where | Current truth |
|---|---|---|
| The stop-placement docstring still referenced the **phantom config block** the cut-#7 fix had just retired | `risk/stop_placement.py` docstring | **FIXED** — the docstring now describes the shipped `config["risk"]` read. Prose describing a retired defect *inside the file that fixed it* is drift at zero distance: the code was right and its own testimony was one commit stale. |
| The **Osler test docstring** described the retired tighten-above implementation | the cut-#7 test file | **FIXED** — the docstring now matches the widen-beyond semantics its own asserts pin ([[entities/osler]]). The four tests had flipped sign at `e7d5ca1a`; the prose above them had not — [[concepts/false-green]] design rule 10's mirror (the docstring states the author's *old* fear). |
| **`_goals_doc` still described the $5,000 regime** | `config.json` `_goals_doc` | **FIXED** — rewritten for the **$800 stressor** (goals $100/mo, RP-072 ladder, [[sources/session-20260810-stressor-epoch]]). A goals doc carrying the pre-epoch capital was this register's boundary-declaration shape on the **capital axis**: the string a future session greps for when asking what regime the book was run under. |

> **And the phantom-knob row is now GUARDED, not just resolved:** `config_guard` checks the
> `stop_round` knobs at the **declaration-consumer join** ([[entities/config-guard]]) — the
> first check in the guard that validates *wiring* rather than a value relation, so the
> class re-diverging FATALs at boot. Also recorded from the same audit: **all 14 commits
> since 2026-08-10T11:00Z verified claim-vs-diff clean** — the first full-window commit
> claim check since this register's rows started shipping inside commit messages — and one
> **recurrence** the audit itself produced: its ledger lens quoted the **stale 16/26 Kraken
> schedule** from the config's own rationale ([[concepts/cost-truth]] — the falsified
> premise is still propagating out of `config.json:325`; the vault's flag, not the doc, is
> what caught it).
>
> **The recurrence row's fix landed in the apply-batch (`66744ed1`,
> [[sources/session-20260811-apply-batch]] §4):** a **stale-fee note now ships IN
> `config.json`'s `market_maker` block**, recording that `min_half_spread_bps=26` descends
> from the STRUCK 16/26 schedule — the propagation vector itself now carries the correction,
> so a future reader (human or 7-agent audit) inherits the flag instead of the premise. The
> knob is deliberately NOT retuned (quote-pricing = cohort-resetting, held with the fee
> constants behind the h432 gate). This is the register's preferred closure shape: fix the
> doc where the drift propagates from, not only the page that catches it.

## The 2026-08-16 additions: **a RECORD that is false rather than stale, and a registration whose subject was deleted**

Both rows are a different species from everything above. The rows above are
*claims* that decayed. These are **artifacts that were never true** — and one of
them is the operator's own control-plane log.

| Stale/false claim | Where | Current truth |
|---|---|---|
| Eight remote `pause`/`snapshot` commands were **queued and RC-010 forwarded** on 2026-08-01 (ids `1785619944 … 1785622368`) | `outputs/remote_control.log`, **16 lines**, 2026-08-01 16:32:24–17:12:48 local | **No such command ever existed.** They are pytest fixtures from `tests/test_remote_control.py` that leaked past the `root` redirect ([[concepts/scoped-data-unscoped-record]]) because this tree was on a pre-fix checkout — **24.74 h after** `64b6fd52` landed upstream. The exactly-once ledger `outputs/remote_consumed.json` (**5 entries, last written 2026-07-25 19:49 local**) is the true record and disagrees. **Standing instruction: `remote_control.log` entries before 2026-08-01 17:20 local are untrustworthy in this tree**; trust the ledger + `pc_status` envelope + paper-telemetry branch history, which agree one-for-one ([[sources/session-20260811-16-vscode-3b307393]] §2). |
| `MCP_DOCKER` is a live MCP server for sessions on this box | global `C:\Users\haird\.claude.json` → `mcpServers` | **Docker was deleted from the host on 2026-08-11** (operator order). The registration remains and cannot start — no `docker` binary, no `MCP_DOCKER` tools surfaced. Harmless (the runtime never consumes MCP — [[entities/liquiditybot]]), but it is a config claim outliving its subject. **And the co-claim in the same session's notes — that coinpaprika's tools died with Docker — is FALSE:** `coinpaprika` is registered directly in the repo's `.mcp.json` as a hosted SSE endpoint and still works ([[sources/session-20260811-16-vscode-3b307393]] §3). |

**The first row is the sharper one and belongs to a class this register has not
carried before: a stale *claim* misleads a reader; a false *record* misleads an
investigation.** The forensics that opened it were chasing eight commands that a
passing test had written into the operator's log — the same shape as the
`INTEGRITY FAIL` line that opened the 2026-07-31 incident, and evidence that
**the record plane needs the same provenance discipline as the data plane.**

## The 2026-08-16 catch-up additions: **a comment that CERTIFIES a wrong constant, and a query pointed at a retired era**

The first row below is the register's sharpest species yet, and it is one step past
the "false record" row above: **the comment does not merely fail to describe the
code — it supplies a reassuring EXPLANATION for the discrepancy it should have
flagged.** A reviewer who checked the constant against the comment would have been
*talked out of the finding by the comment itself*.

| Stale/false claim | Where | Current truth |
|---|---|---|
| `CUT7_TS = 1786411630.0` annotated as **"2026-08-11T01:33:50Z (deploy less 800ms is fine at row granularity)"** | `scripts/defensive_cadence_report.py:39` | **The constant is 400.0 SECONDS EARLY and the comment misstates the gap by a factor of 500.** `1786411630.0` is **2026-08-11T01:27:10Z**; the correct value for `01:33:50Z` is **`1786412030.0`** (re-derived twice: `datetime.fromtimestamp(ts, utc)` and `datetime(...).timestamp()`). The gap is **6m40s**, not 800 ms. It is not the commit instant either — `e7d5ca1a` is stamped `01:33:28Z` = `1786412008.0`, still 358 s later. **Consequence: every geometry-side statistic this report cuts at `CUT7_TS` is cut 6m40s early.** Provenance: introduced **pre-gap by `d3779c8e`** and **untouched by all 25 gap commits** — no gap commit caused it and none caught it. *(Line 38, `CAPITAL_EPOCH_TS = 1786403127.0` = **2026-08-10T23:05:27Z**, is **CORRECT** — the defect is one line, not a pattern.)* |
| `label_era == "triple_barrier"` treated as the deployed era | `scripts/gate_truth_report.py`, `main.py` report-only field, **8 test fixtures** | **RESOLVED at `bb7c193b`; verified at head 2026-08-16** — `gate_truth_report.py:207` now derives `_label_era = triple_barrier_era(_max_bars)` from config, with the retired literal surviving only inside the explanatory comment at `:197-204`. The **432-bar** era has been deployed since the horizon migration; `"triple_barrier"` is the **RETIRED 96-bar** era. The report had read **5,328 retired rows / 0 deployed rows** and printed **XV-040 ALIGNED**; corrected verdict **XV-042 THIN** (56.1 effective observations < 100, *no verdict yet*). All 8 fixtures hardcoded the same literal and so **passed vacuously**. Full treatment: [[concepts/false-green]] §the sibling class. |
| ~~`scripts/build_trading_dashboard.py:1398` still queries the **retired** era~~ | — | **REFUTED at head `c4272391` (checked 2026-08-16).** The file is **1,361 lines** — *there is no line 1398* — and `grep -nE 'triple_barrier|label_era'` over it returns **zero** matches. The claim was carried into the catch-up as disclosed residue and does not reproduce. **Recorded rather than deleted**: this register's whole purpose is that a claim which cannot be re-derived is itself the finding ([[synthesis/governance-doctrine]] rule 16). |

> **The rule this register gains:** *a comment that EXPLAINS a discrepancy is doing
> more work than a comment that describes the code, and it must be held to a higher
> standard.* "Deploy less 800ms is fine at row granularity" is a **verification
> claim** — it asserts someone checked. Nobody had. This is
> [[concepts/false-green]]'s logic applied to prose: an assurance is evidence only
> if it could have been written differently had the check failed.

## Why this register exists
An architecture document is a **snapshot of intent at a revision**. Read as current truth it produces
confident wrong answers — and this corpus contains a worked example of exactly that failure mode: an
instrument built on a header comment that misattributed a data defect to corpus size, when
[[concepts/scoped-data-unscoped-record|the file was 99.7% test output]].

## The reading rule
When an architecture doc and an audit disagree, **the audit wins**. When two architecture docs disagree,
**the later revision wins**, and the assurance spec is authoritative for invariants and reason-code
families.

## Related
[[comparisons/stated-invariants-vs-audited-reality]] · [[synthesis/open-contradictions-register]] ·
[[sources/session-20260806-hedge-thrash]] · [[concepts/two-paths-one-quantity]] ·
[[sources/session-20260809-corpus-corruption]] · [[concepts/false-green]] ·
[[entities/overfit-check]] · [[entities/config-guard]] ·
[[sources/session-20260809-gate-policy-and-self-heal]] · [[entities/ml-governor]] ·
[[sources/session-20260810-fill-double-count]] · [[entities/reason-code-registry]] ·
[[concepts/paper-real-boundary]] · [[sources/session-20260811-cut7-geometry-epoch]] ·
[[concepts/default-path-fallback-writes]] · [[entities/osler]] ·
[[sources/session-20260811-operator-audit]] ·
[[sources/session-20260811-16-vscode-3b307393]] ·
[[concepts/scoped-data-unscoped-record]] ·
[[concepts/session-identity-is-not-stable]] ·
[[synthesis/owed-measurements]]
