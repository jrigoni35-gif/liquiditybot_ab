# AGENTS.md â€” liquiditybot engineering law

Binding for every agent session touching this repo (Kimi Code, Claude Code,
Codex, Cursor, OpenCode, â€¦), new or continued. This file and CLAUDE.md are
the SAME law: Claude Code auto-loads CLAUDE.md, Kimi Code and other
AGENTS.md-aware CLIs auto-load this one. The bodies below this header are
kept identical â€” edit one and edit both in the same commit; an unpaired
edit is documentation drift.
Read this file FIRST. When an instruction in chat conflicts with a HARD
INVARIANT below, stop and say so instead of complying.

## Hard invariants (never weaken, never "temporarily" bypass)

1. `system.dry_run` defaults to **true**. No engine code path, config
   default, or control command may set it false at runtime. (The SAFE
   battery harness `scripts/smoke_test.py` deliberately sets it False at
   :1491/:1508/:2028 to exercise the live path â€” that harness is the one
   named exemption, not a loophole; it never runs in the engine.) The only
   road to live has **FOUR** steps, not three: delete the
   `outputs/force_dry.on` sentinel (or boot `--fresh`, which clears it) â†’
   config `dry_run:false` â†’ restart â†’ typed `ARM LIVE`.
   The sentinel step is not optional and is easy to miss because it fails
   SAFE and silently: `runner.apply_force_dry_sentinel` runs at boot BEFORE
   the engine reads `system.dry_run` and forces it true whenever that file
   exists, logging only `sentinel is a no-op this boot` while the config
   already says dry. **This box has carried that sentinel since
   2026-08-01** and has logged that line on every boot since; following the
   three-step version of this instruction here would not reach live, and
   the reason would not be obvious. `force_dry` moves one way only
   (LIVEâ†’DRY) â€” see invariant 2.
2. `force_dry` is one-way (LIVEâ†’DRY) and must flip **both** `bot.dry_run`
   and `bot.orders.dry_run` (OrderManager caches the flag at init).
3. Kraken is the **sole execution venue**. OKX / Binance.US / ccxt /
   moomoo are read-only data. IBKR/DMA/prime/FIX adapters exist as
   hard-off stubs.
   **The enforcement is a DENY-LIST in `main.py` (~:871), not the venue
   adapter.** If the feed handed to `OrderManager` is one of the real
   read-only venue classes â€” OKX / BinanceUS / Moomoo / WebData / Context /
   ccxt â€” engine construction RAISES `VN_ROGUE_EXECUTION`. `FeedRecorder`
   wraps the feed, so the check unwraps `_feed` first. Deliberately a
   deny-list and not an allow-list: the suite injects `SimpleNamespace` /
   `MockKraken` doubles and must keep constructing. Pinned three ways by
   `tests/test_cut10_boundary.py` â€” rogue refused, wrapped rogue refused,
   and an anti-rubber-stamp case proving doubles still work.
   **`VenueAdapter.execution_eligible` is NOT on this path** and this file
   named it as the enforcement until 2026-09-10. Re-derived that day:
   `execution_eligible` appears only in `execution/routing.py` and
   `execution/venue_adapters.py`, never in `main.py` / `runner.py` /
   `execution/order_manager.py`, and a full-range scan of all 87,640 audit
   records found ZERO `VN-*` of any kind. The router is constructed and never
   read. Cut #10 (B4) fixed the code after a 2026-09-05 measurement in which
   a live submit on a non-Kraken feed PLACED with a wire payload emitted â€”
   the invariant had rested on a default value â€” but the LAW kept citing the
   layer that had never guarded it. Do not relax the deny-list, do not
   subclass around it, and do not restore a claim that the adapter enforces
   this.
4. Withdrawals/transfers are impossible: the endpoint deny-list
   (Withdraw, WithdrawInfo, WalletTransfer, WithdrawAddresses) blocks
   before any network I/O. Never add withdrawal capability in any form.
5. Entries are limit orders only (OM-011); market orders are for the
   exit escalation ladder's final rung. Exits are ALWAYS allowed â€”
   disarm, faults, and kill switches block new risk, never escapes.
6. Hash-chained JSONL audit trail and a registered reason code on every
   disposition. New behavior = new registered code in `core/codes.py`,
   never a bare string. **`core/codes.py` is the registry and the only
   authority on which prefixes exist** â€” no count is written here on
   purpose. The enumerated list this replaces had drifted to a third of
   the real families, because a prefix list written into law goes stale
   the day someone adds one. Re-derive when you need it.
7. Public interfaces stay stable. Extend with defaults; do not rename or
   change signatures without updating every caller AND the suites.

## Architecture — `docs/law/architecture.md`

Module boundaries, the runner loop, state files, logging, serializability:
read `docs/law/architecture.md` BEFORE touching module boundaries, the
runner lifecycle loop, or state-file schemas. Do not re-tangle what is
separated.

## Overfit discipline — `docs/law/overfit_discipline.md`

No fitted-looking literals in decision paths; thresholds live in
`config.json` behind `core/config_guard.py`; model/gate changes must keep
the overfit battery and quant-trial gates green. Read
`docs/law/overfit_discipline.md` BEFORE touching any tunable, model, or
gate.

## Accrual moratorium — era-9 (summary; full text `docs/law/era9_moratorium.md`)

Era-9 accrues from the cut #12 runner restart (2026-09-08) under operator
approval. **READ `docs/law/era9_moratorium.md` BEFORE any change that could
place, size, or exit an order** — the full text carries the cut record, the
price of a mint, and the four mechanisms the law does not name. The binding
core:

- **COHORT-RESETTING — forbidden without operator adjudication** (any of
  these mints the next boundary and restarts accrual): entry decisioning,
  position sizing, stop/exit geometry (placement, nudges, time limits),
  the fill simulator, fee booking, the order lifecycle, the universe, the
  hedger, the probe ticket, or the heat cap. Exactly two exemptions: a
  **SAFETY INVARIANT** (hard invariants 1–7 above) and a **WRONG VENUE
  CONSTANT** making the bot trade on a false cost. Nothing else.
- An era runs a **MINIMUM OF 14 DAYS** before a discretionary boundary may
  be called; a mint must be justified in writing, in its decision record,
  against the price enumerated in the full text.
- **SAFE class** (no adjudication needed): measurement/report tools,
  dashboards, tests, wiki, telemetry export, and bug fixes that do not
  alter which orders are placed or how they fill.
- Read points are REGISTERED: **n=50 = the lean** (sign + CI), **n=100 =
  the verdict**. The registration is the law; readouts never decide.
- Model-side investment is FROZEN (2026-08-10 operator adjudication); the
  retrain loop itself continues by design. Do not retune on accruing
  gate numbers.

## Definition of done — `docs/law/definition_of_done.md`

## Definition of done (every change, every session)

Run ALL of it; a change is not done while anything is red:
`python -m pytest tests/ -q` Â· `python scripts/smoke_test.py` Â·
`python scripts/assurance_check.py` Â· `python scripts/overfit_check.py`
Â· `ruff check core data execution ml risk regime strategies sentiment
api main.py runner.py tests scripts/quant_trials.py
scripts/overfit_check.py` Â· `pyright core data execution ml risk regime
strategies sentiment api main.py runner.py` (type ratchet: shipped scope
is at ZERO errors â€” keep it there; tests/scripts are outside the gate)
Â· `bandit -c pyproject.toml -r . -x ./.venv,./tests,./outputs` Â· `python -m
compileall -q . -x '(\.venv|\.claude)'`.

Gate-degradation caveats (synthetic corpus substitution, dark overfit
rungs, effective-n deflation, the never-lower-a-floor rule): read
`docs/law/definition_of_done.md` BEFORE declaring any gate green — a green
is only as big as its corpus.

## Working style

- Terse, dense engineering output. No filler, no re-explaining settled
  architecture. File-by-file change maps.
- Never ship sloppy/buggy code: no guessed APIs (read the module first),
  no silent behavior changes, no unverified edits â€” run the matrix.
- Do not break global state; do not ignore these conventions; do not
  lose the thread â€” reread this file and README before large changes.
- Deliverable = clean zip (no `.venv`, no `__pycache__`) rebuilt from a
  tree that just passed the full matrix, verified by fresh-extract run.
- Token-frugal handoffs (token spend follows plaintext, not compressed
  bytes â€” xz/DEFLATE buy storage, never context):
  * diffs over files: send hunks, never whole-file dumps when a patch
    tells the story; reads of an unchanged 900-line module cost ~100x
    the 10-line change against it.
  * transit-only stripping: docstrings/comments may be dropped from a
    throwaway copy an agent reads for shape only â€” the canonical tree
    is never touched, and any edit targets the pristine source.
  * route by law file: load only the module the task touches; the
    module separation (core/ risk/ execution/) is the localization
    code, and re-reading it whole is the expensive failure mode.

## SESSION BRIDGE (read `docs/HANDOFF.md` before acting)

Auto-delivered to every Claude session in this repo.

**This file is the LAW; `docs/HANDOFF.md` is the STATE.** Read the
handoff first: it carries the live gate count, the open adjudication
docket with authority pointers, what is currently blocked, and â€” most
importantly â€” a RECENTLY SETTLED table so you do not re-litigate a
decision that was already made with evidence, or re-implement a fix
that already shipped. Update it at the end of any session that changes
state; its own contract section says how. Static architecture lives in
`docs/ONBOARDING.md`.

## THE MINDSET — `docs/law/mindset.md`

The instrument is the first suspect: a surprising number gets its
instrument verified before it gets a theory, and one number from one tool
is a hypothesis. The seven measured recurrences, the binding operating
consequences, and the durable coordination rules: `docs/law/mindset.md` —
read before trusting any measurement, referees included.


<!-- rtk-instructions v2 -->
# RTK

Prefix every shell command with `rtk`: `rtk git status`, `rtk cargo test`,
`rtk npm run build`, `rtk ls src/`. Keep the prefix inside chains:
`rtk git add . && rtk git commit -m "msg"`. Commands RTK has no filter for
run as-is, so the prefix is always safe.

# Command output

Command output here is condensed to save tokens, keeping every signal and
dropping costly noise. Treat it as the complete result: run commands
normally, and batch related commands into one call to avoid extra turns.
Truncated results state their recovery path in their own output. Re-run a
command as `rtk proxy <cmd>` only when its result is unusable: empty when
output was clearly expected, contradicting its exit code, or garbled.

## About RTK

RTK (Rust Token Killer) is a CLI proxy that filters command output to save
tokens; behavior and exit code are unchanged.

- `rtk gain` / `rtk gain --history` â€” token savings, overall and per command.
- `rtk proxy <cmd>` â€” run a command unfiltered, still tracked.
- `RTK_DISABLED=1 <cmd>` â€” skip RTK for one command.
- `rtk discover` â€” find past commands RTK could have condensed.
<!-- /rtk-instructions -->