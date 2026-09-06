# 24 deferred findings verified by execution; five fixed

**Date:** 2026-09-05
**Class:** SAFE (all five). No change to which orders are placed or how they fill.
**Method:** 17-agent workflow — each finding reproduced against the running
system (mutation / injection / ask-the-runtime), then adversarially re-verified
by an independent agent instructed to refute. Agents were forbidden from writing
to the repo, since several findings sit behind BOUNDARY fences.
**Full register:** `scratchpad` workflow output, preserved at
`vault/raw/audits/` — see §6.

---

## 0. Why this batch exists

64 hunt findings + 10 candle findings were carried as **UNVERIFIED** across
several sessions; two prior workflows attempting verification died on session
limits. Implementing unverified findings is the anti-pattern this repo's method
exists to prevent, so the batch was verified first. Of 31 critical/high, seven
were already fixed on 2026-09-05, leaving 24 to verify.

**Outcome: 16 CONFIRMED+SAFE, 7 CONFIRMED+BOUNDARY, a long REFUTED list, 4
CANNOT_DETERMINE.** Five of the SAFE ones are fixed here — the rest are ranked
in the register.

## 1. What was fixed

### S12 — invariant #4's only enforcement point tested a raw string
`data/kraken_feed.py`. `if endpoint in FORBIDDEN_PRIVATE_ENDPOINTS` compared the
caller's **raw** string, so **56 of 56** trivial respellings missed the frozenset
and reached `requests`: `withdraw`, `WITHDRAW`, `Withdraw ` (trailing space),
`Withdraw\n`, `Balance/../Withdraw`, `wallettransfer`.

Most are self-defeating at the venue (signed path ≠ wire path → `EAPI:Invalid
signature`), but *"the attack fails at the counterparty"* is not the guarantee
*"the call cannot be made"*. Lowercase `withdraw` in particular is **both
correctly signed and correctly addressed**, and whether Kraken's private path is
case-sensitive **cannot be settled without attempting a real withdrawal**. So it
is settled in the code: normalise case + whitespace, and refuse any endpoint
carrying a path separator outright.

Reachability today is nil — all 12 call sites pass string literals. This is
defence-in-depth on a hard invariant, and it is cheap.

### S1 — a REJECTED snapshot was destroyed, and the trigger is the armed-live restart
`core/persistence.py`. `restore()` returning False starts fresh; the runner's
periodic `snapshot()` is unconditional on whether a restore succeeded, so at the
shipped `snapshot_interval_sec = 30` **both generations of the rejected state are
gone inside ~60 s**. Measured: `811.11 recoverable anywhere on disk: False`.

**The reachable trigger is the paper↔live boot mismatch** — step 3 of invariant
1's four-step road to live. (The version check has never fired: `SNAPSHOT_VERSION`
has exactly one commit in its history, "Initial commit".) That is the boot whose
prior state is least reproducible and where the operator can least afford to lose
it. Live `outputs/state.json` is 3,186,151 B.

Fix: copy (never move) both generations to `state.json.rejected_<ts>_<reason>`
before returning False. `restore()` semantics unchanged. `scripts/session_export.py`
gained a **prefix** rule — the quarantine names are unique per timestamp, so the
exact-name `NEVER` set could not see them, and state.json never travels.

### S4 — a repo import error was laundered into an admitted deploy
`scripts/auto_update.py`. `missing = any(m in blob.lower() for m in _MISSING_TOOL)`
matched over the **whole** stdout+stderr blob. `scripts/smoke_test.py:543`
`traceback.print_exc()`s any exception from 60 mocked engine cycles, so the needle
surface is the entire engine — and a genuine `ModuleNotFoundError: No module named
'strategies.smc'` in **our own code** was classified `TOOL UNAVAILABLE`, which
`_dod_gates` `continue`s past, **admitting the deploy**. Verified end-to-end
through the real smoke_test: `classified_TOOL_UNAVAILABLE=True`.

Two narrowings, both required: inspect only the **final** traceback line, and
**exclude repo top-level packages** from the class. A missing repo module is
precisely the breakage the gate exists for.

### S7 — lock staleness was shorter than the real in-lock ceiling
`scripts/auto_update.py`. The shipped comment declared the in-lock ceiling
`BATTERY_TIMEOUT_MAX + 1200 = 6000s` — it counted the pytest wall and the replay
gate and **silently omitted every DoD gate**. Independently re-derived from
source this session:

```
4800 (battery MAX) + 1200 (replay) + 5 hard gates x 900 + 2 advisory x 1800 = 14100s
```

against `LOCK_STALE_SEC = 7800.0` — a **6,300-second band** in which a peer reads
a healthy updater's lock as abandoned. Measured boundary: 7799 s → BUSY,
**7800 s → TWO UPDATERS**. The reclaim path then runs `git worktree remove`,
takes rc=255 *Permission denied*, and **destroys 8 of 8 files and deregisters the
worktree anyway** while a battery child is live.

Fix: `LOCK_STALE_SEC` is now **derived** from the gate tables (× 1.15 margin →
16,214 s), and the gate call sites read the same constants, so adding a gate
widens the window automatically. The pin asserts the **relationship**, never
either number.

### S6 — restore() re-minted every candidate id, orphaning the corpus join key
`ml/history.py`. `c["id"] = f"cand-{self._id_salt}-{self._seq}"` ran
unconditionally, while `core/persistence.py` restores the **position's**
`candidate_id` unchanged — so the two halves disagree after any restart.
Measured on the real training path (`_scan_live_dedup_keys`): **79 of 187 cited
ids orphaned (42.2%)**, drifting again on every subsequent restart.

**The fix is narrower than the one proposed.** The register suggested "keep the
id already present in `d`", which would reintroduce the 2026-07-14 collision: a
**bare pre-salt** `cand-{seq}` id can be reused after a filesystem rollback
resets the counter. An id already carrying a per-launch salt
(`os.urandom(4).hex()`) is unique by construction, so only bare ids are
re-minted. Salted ids survive.

## 2. Verification

`tests/test_verified_findings_2026_09_05.py` — 22 pins, **12/12 mutations RED,
0 vacuous**.

**The mutation run caught a real gap in my own pins.** The first version tested
the *helpers* (`_endpoint_is_forbidden`, `_classify_missing_tool`) and not the
*call sites*, so reverting the wiring in `_private_post` and `_run_gate` left
every pin **green** while both guards were fully bypassed. That is finding #11's
exact shape — *"the invariant batteries pin the dead guard; the guard that
actually runs has zero tests"* — reproduced by me inside the commit that fixes
it. Call-site pins were added; both mutations now go red.

## 3. NOT fixed — BOUNDARY, operator sign-off required

| | what | fence tripped |
|---|---|---|
| B1 | `core/watchdog.py:140` `book_ts.get(a, 0.0)` fail-closed | entry decisioning; `tests/test_fail_open_pins.py:43` is already a **strict xfail** and will red the suite the moment the fix lands — sign-off must cover the marker too |
| B2 | `risk/profit_tiers.py:218` `est_fee_bps` default `0.0` → 6 bps break-even floor where booked gives 82 | stop/exit geometry **AND** fee booking — two fences in one edit. Latent in the shipped config (give-back arms at 5% < tier_1 8%; 0 divergences over a 1921-point sweep) |
| B3 | `risk/protocols.py` `spent_fracs` fail OPEN on NaN → multiplier 1.0, no reason code | entry decisioning + position sizing |
| B4 | wiring the venue layer onto the production order path | order lifecycle. `self.router` is constructed and **never read**; `.route(` appears only in tests |
| B5 | `core/fill_ledger.py` dedup fail-closed | fee/P&L booking by consequence |
| B6 | raising `ml.max_open_candidates` 1200 → ≥1574 | candidate pipeline feeding entry decisioning |
| B7 | backfilling historical `candidate_id`s | training-corpus composition |

## 4. REFUTED — do not re-find these

The register's refuted list is long and includes **several of the verifying
agents' own hypotheses, killed by their own mutations**. Highlights:

- **[15]** "arms 76 bps too loose" — false confirm on **reachability**: give-back
  arms at 5% while long-book tier 1 is +8% and `_ratchet_stop` is tighten-only.
  0 divergences across 4 sigmas; exhaustive 1921-point sweep, 0 crossings.
- **[8]** "the deny-list could silently shrink; the pin covers only 4 of 7 verbs"
  — **refuted by mutation**: shrinking the frozenset reds
  `tests/test_hard_invariants.py:28`, which iterates all seven.
- **[30]** "`LimitFlags=0x3000`" — read from the **wrong job object**
  (`QueryInformationJobObject(None, …)` reads the *calling* process's job, i.e.
  the agent's). Downgraded [K]→[I].
- **[32]** a lock sweep showing every age acquiring — **broken scan, not a
  finding**: `core/runtime.py:333` grants same-pid re-entry and both locks
  carried the same pid.
- **[0]** a seq-vs-`bar_time` monotonicity scan reporting "0 inversions" —
  **zero detection power**: re-mint preserves seq/bar_time co-monotonicity, so a
  planted re-mint also yields 0.
- **[29]** a multi-pattern grep finding no `snapshot_interval_sec` — **broken
  scan** (the rtk hook mangled the pattern); plain grep finds `main.py:683`. It
  nearly refuted a correct citation.
- **[3]** "irreversible within seconds" — actually **~60 s**
  (`snapshot_interval_sec = 30`). Substance unchanged, the number was overstated
  in the alarming direction.
- **[14]** "the 0.632 comment went stale via the fee cuts" — that construction
  computed **0.6902** the day the comment was written. **Wrong when written**,
  which is worse than stale.

## 5. What this cannot see

Four indices ([7], [13], [16], [24]) had their verdict text truncated in
transmission and are **unclassified — their absence is not a refutation**. Every
corpus figure is as-of a stamped read against live, mutating files. The
SAFE/BOUNDARY split is a claim about the fences in CLAUDE.md as written, not
about second-order coupling that was not traced; S6 and S13 both touch corpora
that eventually feed a retrained model, and only their forward-only halves are
classified SAFE (the retroactive halves are fenced at B7).

## 6. DoD

pytest full suite · smoke **220/0** · assurance **51/0** · overfit **3 ARMED**
passed on a live 15,046-row corpus (4 rungs dark — read the `--` lines) · ruff
clean · pyright **0** · bandit 0 issues over 66,643 lines scanned · compileall
clean.
