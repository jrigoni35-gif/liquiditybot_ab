# liquiditybot — Assurance Build (rev 3.0)

Government-protocol rewrite of the trading core: safety-critical
discipline (DO-178C-style traceability, NASA/JPL fault-containment
posture, SEC 15c3-5 order screening), profit-path corrections that
remove structurally negative-EV behavior at the 25/40bps fee tier, and
SR 11-7 / OCC 2011-12 model-risk governance over the learning stack.

Every rewritten module is a drop-in interface-compatible replacement.
Modules already at assurance grade (watchdog, config_guard,
persistence, sanitize, alerts, runtime, feeds, regimes, sentiment) are
carried forward unchanged and mapped in the trace matrix below —
rewriting sound code for its own sake adds risk, not assurance.

## The assurance spine (new)

| module | provides |
| --- | --- |
| core/codes.py | global append-only reason-code registry; every reject/clamp/fault/deploy carries one |
| core/audit.py | hash-chained JSONL audit trail (outputs/audit.jsonl); tampering breaks the chain at the exact record; `verify()` replays it |
| core/fault.py | latching fault manager; INIT/ARMED/DEGRADED/HALTED op-state machine; exits always allowed |
| core/clock.py | monotonic time authority for intervals; wall time for audit stamps only |
| ml/contracts.py | versioned feature contract enforced at every inference and training load |
| ml/registry.py | SHA-256 model identity, immutable artifact archive, model cards, append-only lifecycle ledger (outputs/models/) |
| scripts/assurance_check.py | offline PBIT: 36 invariant checks, no network |

## Requirement trace matrix

| REQ | requirement | enforced by | codes |
| --- | --- | --- | --- |
| FW-01/02 | every order input positively validated; unverifiable reference fails closed (entries) / safe (exits) | risk_firewall._validate | FW-01x, FW-060 |
| FW-03..06 | rate limit, dupe suppression, price collar, notional ceilings on EVERY order | risk_firewall._check | FW-020..051 |
| FW-07/08 | firewall never raises at runtime; power-on self-test refuses to arm on failure | check() wrapper, self_test() | FW-09x |
| PT-01 | non-finite pre-trade inputs reject | pretrade.evaluate | PT-010 |
| PT-02 | maker cost includes adverse selection (kappa x sigma_bar) | pretrade cost stack | — |
| PT-03 | fill-probability-weighted EV must clear the floor | pretrade EV block | PT-040 |
| QT-01 | half spread >= maker fee + margin: passive round trip never net-negative by construction | market_maker floor | QT-010 |
| QT-02 | bid <= reservation <= ask under any inventory | skew clamp | — |
| FV-01 | edge discounted by the estimator's own noise floor; sub-noise edge reports 0 | fair_value.edge_bps | — |
| FV-02 | innovation gate: one poisoned print cannot yank fair value | fair_value.update | FV-020 |
| SZ-01 | Kelly sized on payoffs NET of round-trip fees (alpha stays gross; execution costs charged once, at pretrade) | position_sizer b/b_net split | SZ-030 |
| SZ-02 | continuous drawdown throttle decelerating toward the hard stop | position_sizer | SZ-050 |
| OM-01 | order status changes only through the legal-transition table; violations forced to safe terminal, never a fabricated fill | order_manager._transition | OM-030 |
| OM-02 | market orders exist only as escalated exits | order_manager.submit | OM-011 |
| OM-03 | sub-ordermin exits handled: dust remainders finalized flat, dust slices escalate to full close, rejected exits never escalate | main._submit_exit | OM-012 |
| ML-01 | no inference on inputs the contract hasn't passed; violation -> prior, counted | meta_model.p_win | ML-010/020 |
| ML-02 | no artifact load without integrity verification against the registry ledger | meta_model.reload | ML-011 |
| ML-03 | every trained model hashed, archived, carded with data lineage | models.save_model -> registry | ML-060 |
| ML-04 | staged governor: degrade shrinks, failing kills the model (prior takes over); level changes/deploys/retrains audit-chained | monitor | ML-030/050 |
| ML-05 | hit-rate judgment requires material AND statistically credible shortfall (Wilson LCB) | monitor._evaluate | — |
| ML-06 | challenger deploys only past the champion Brier margin; decision audited | monitor.should_deploy | ML-040/041 |
| IF-01 | signal confirms only on unanimous direction across flow-persistence, accumulation, burst, and trend gates | informed_flow.evaluate_asset | — |
| IF-02 | absorption veto: price advancing on net distribution never confirms | informed_flow._gate_accumulation | — |
| IF-03 | one-print imbalance (noise/spoof) never confirms; persistence over k evaluations required | informed_flow._gate_persistence | — |
| TX-01 | taker entries clear the FULL taker cost stack at the pre-trade gate; urgency is a placement preference, never an EV bypass | main entry path: pretrade(taker=plan.taker) | PT-04x |
| TX-02 | improve style prices strictly inside the spread (post-only can never self-cross); taker suppressed in spoofy regimes; malformed inputs degrade to the passive AS quote | tactics.plan_entry | — |
| SYS-01 | tier ladder advances ON FILL (rev-1 latent bug: tier_closed was never written — tier 1 re-fired forever; tiers 2–4 and the trailing stop were unreachable) | main._handle_fill | — |
| SYS-02 | session config SHA-256 fingerprint is the audit chain's first record | main.__init__ | CG-000 |
| SYS-03 | carried-forward invariants: dry_run default true, withdrawal endpoint deny list, ARM LIVE gate, exits never blocked, dead-man switch, checksummed snapshots | watchdog / config_guard / kraken_feed / persistence (unchanged) | WD/CG |

## Informed-flow signal engine + execution tactics (rev 3.0)

`strategies.engine` is set to `informed_flow` (rollback: `five_gate`).
The engine detects informed participation in public microstructure —
persistent book imbalance, accumulation/distribution agreement with
price, directional volume bursts that close near their extreme — and
only trades WITH it, with funding and trend sanity vetoes. It emits an
urgency score consumed by `execution/tactics.py`, which ladders order
placement: AS quote -> join touch -> improve inside the spread ->
EV-gated taker cross. The taker rung pays the 40bps stack only when
the pre-trade gate certifies the edge survives it; every rung below
stays maker. Tune thresholds via replay sweeps; the new engine has
zero paper hours — run it in dry_run before trusting it with size.

## Behavior deltas from rev 1 (review before relying on old expectations)

1. NaN/Inf anywhere in an ENTRY order path now rejects instead of
   passing through (firewall, pretrade, sizer, quoter, fair value).
   Exits still fail safe.
2. Firewall limit config is BOUNDED; "disable via 1e9" is refused at
   init. Disable screening with `enabled: false` if you must.
3. Maker entries carry an adverse-selection cost and an EV-at-p_fill
   requirement. Defaults are gentle (kappa 0.35, miss_cost 0.5bps,
   ev_min 0) — tune with scripts/replay.py sweeps, not intuition.
4. Kelly runs on net payoffs: same p(win) sizes smaller than rev 1
   (that is the correction, not a regression). Net breakeven p is
   logged at startup.
5. The tier ladder actually ladders now; expect fewer, later, larger
   partial exits than the rev-1 behavior of re-firing tier 1.
6. smoke_test.py updated to the new contracts (bounded firewall
   config, hermetic resume=False fixtures) — 188 checks.

## Verification procedure

```bash
python scripts/assurance_check.py    # 47 invariant checks, offline
python scripts/smoke_test.py         # 205 end-to-end checks, offline
python -m bandit -c pyproject.toml -r . -x ./.venv,./tests   # 0 issues
python - <<'EOF'                     # audit chain integrity
from core.audit import get_audit; print(get_audit().verify())
EOF
```

## Operations doctrine

- DEGRADED means degraded: a latched fault blocks new risk until an
  operator clears the named fault. Nothing auto-clears.
- The audit chain and the registry ledger are append-only. Do not
  edit them; verify() and the hash chain exist to catch exactly that.
- The governor can only make the bot more conservative than config.
  If the model is at level 2, the fix is a better model through the
  deployment gate, not a bigger knob.
- No profitability is guaranteed or implied. This build removes
  structurally negative-EV paths and makes every decision accountable;
  the edge itself still has to be earned in the data.
