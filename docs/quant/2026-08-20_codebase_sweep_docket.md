# Full-codebase sweep — findings docket (2026-08-20)

*25-agent adversarial sweep (9 subsystem finders × 3 hostile lenses → 16
verified by independent refuters; 2.35M tokens, 0 errors). 22 raw → 13
confirmed. SAFE_NOW items fixed this session; BOUNDARY/DOCKET items
recorded here for era-4 operator adjudication (they alter which orders
are placed or how they fill — the moratorium forbids fixing them without
a boundary decision). Full machine result:
`docs/quant/2026-08-20_codebase_sweep_result.json`.*

## FIXED this session (SAFE_NOW — no decision-path reach)

| # | file:line | fix |
|---|---|---|
| 4 | ml/registry.py:187 | verify_chain now FAILS on an unchained row appended after the chain began — runtime-injection-verified the old code passed a forged no-`h` `registered` row as ok=True and the ML-011 gate then trusted a swapped artifact. + 2 new tamper tests |
| 10 | tests/test_registry_chain.py:41 | the bare-`pass` stub (a hardening file's first test asserting nothing) now pins the chain shape + the appended-forgery case |
| 2 | scripts/session_import.py:326/356 | symlink guard on the copy-if-absent meta_model.json / skimmer_active.json hand-off — bundles are attacker-authored and imported unattended; the listed-file symlink refusal now covers these too |
| 7 | data/_http.py:143 | DL-7 body cap also bounds the actual decoded length, not just the content-length header — a server omitting the header no longer bypasses the cap |
| 12 | diode/README.md:7 | doc named the field `truncated_by_quote`; the binary emits `quote_truncated` (the only name tests accept) |

## DOCKET — BOUNDARY class (operator adjudication at readout)

Each alters live order/fill behavior; the era-4 cohort accrues on
dry-run fills that several of these paths never touch, but the
adjudication is the operator's.

- **[0] CRITICAL execution/inventory.py:134-155** — `derisk_actions` hard-
  cap loop can select a HEDGE position and `main.py:2921` force-closes it
  via `_submit_exit` with zero hedge coordination. `_record_unwind` (its
  only call site, hedging.py:223) never arms the rehedge cooldown / FW-070
  churn latch, so the hedger re-opens next cycle → derisk cuts again:
  guard-invisible reproduction of the cf454d5 ADA churn incident (-$318)
  via an unguarded path. Reachable when a hedged asset also holds same-
  direction signal longs, or at hedge sizes above the 25% cap
  (max_equity_frac 0.5 permits 2× with no config_guard coherence check).
  No test covers the seam. *Fix touches which orders are placed.*
- **[1] CRITICAL risk/leverage.py:75** — margin-health veto FAILS OPEN: the
  0.0 sentinel means both "API failed" and "no margin in use", so a
  transient TradeBalance failure (hourly refresh, main.py:6253) disables
  the 150%/200% margin block for a full hour, leaving leverage at up to the
  10× region cap on live margin orders. Inert today (dry_run gates the
  refresh) but sits one config flip from the live safety path; no last-
  known-good, no distinct unknown state, no test. *Live entry decisioning.*
- **[3] WARNING main.py:2793** — watchdog PNL-velocity trigger is fed equity
  from tick-quarantined (unconfirmed) marks, so a single fat-finger print
  can trip an emergency action off a mark the system already distrusts.
- **[5] WARNING risk/protocols.py:289-295** — CVaR per-asset buffer lookup
  falls back to unanchored substring containment (`asset in k`), which can
  attribute one asset's realized-return buffer to another (exercised in
  production on every branch, per the refuter). Sizing input.
- **[8] WARNING main.py:2674-2739** — fast_cycle's marks/books fetch loop is
  the only pre-stop stage with no try/except isolation; a raise there skips
  the whole cycle including stop evaluation, unlike its guarded siblings.

## Tail (unverified, lower confidence — recorded, not actioned)

api/rest_server.py:163 non-constant-time secret compare; core/audit.py:175
dedup-guard substring match; ml/registry.py:106 `_tail_link` shares the
(now-fixed) verify_chain blind spot — worth a follow-up pass; _http.py:150
`resp.json()` on OKX/Binance paths; two doc-drift lines. None are
decision-path; batch into the next SAFE sweep.

## Probed and found clean (silence ≠ not-looking)

Verified sound by the finders: order_manager state machine + venue
`execution_eligible` gate; position_sizer fail-closed pipeline; circuit
breaker lifecycle; kraken signing/nonce; ws_feed re-sanitization; runner
command dispatch + single-instance lock + force_dry ordering; auto_update
ff-only + no-TOCTOU; fill_ledger dedup + torn-tail healing; conftest
outputs-write guard; diode era4/wilson vs the Python reference; and the
full CandidateLabeler/triple-barrier/era-exclusion learning path.
