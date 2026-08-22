# Loop alignment audit — operator → bot → market → analysis → operator

*Operator directive 2026-08-22: "look at my firewalls and decisions and
make sure all of the edge-driven elements are aligned correctly within
you → bot → market → back to analysis of data within." Read against the
measured edge (`2026-08-22_boundary_around_the_invariant_edge.md`): the
regime-invariant edge is the COST-AWARE REJECTION STACK — SZ-030
net-Kelly f\*≤0, the SZ-023 derived p-bar, SZ-046.*

## Verdict

The loop is **structurally sound and internally consistent — and
externally mis-anchored at exactly one point.** Every stage agrees with
every other stage, which is why nothing inside the loop can detect the
error. Only the independent measurement route caught it.

## Stage 1 — operator → bot

**Aligned.** Two channels, both correctly one-directional:

- **Control plane** (`scripts/remote_control.py`): `REMOTE_SAFE_COMMANDS`
  is de-risking-only by construction — `pause / stop / entries_off /
  force_dry / flatten_all / disarm_live`. `arm_live` is excluded by an
  import-time guard that refuses to load if violated. **The remote
  channel can only ever reduce risk**, never add it. Commands expire at
  30 min and apply exactly once.
- **Deploy** (`scripts/auto_update.py`): battery-gated fast-forward,
  pinned to `main` via `system.deploy_branch`, never across a dirty
  tree. Code reaching the bot is code that passed the suite.

No edge-relevant lever exists on this channel that could loosen a veto
remotely. That is the correct shape.

## Stage 2 — bot → market (the decision path)

**Firewall: correctly scoped, correctly ignorant of the edge.**
`execution/risk_firewall.py` implements REQ-FW-01..08: input validation,
reference integrity, rate limit, duplicate suppression, price collar,
notional ceilings, fault containment, power-on self-test. It carries
**no fee or edge awareness at all** — and it should not. It is the last
mechanical check before the venue (is this order well-formed, non-
duplicate, in-collar, within ceiling), not an economic one. Economics
belong upstream in the SZ layer. **Aligned — do not add cost logic
here.**

**The SZ layer is where the edge lives, and it reads one cost stack:**

```
config.pretrade.maker_fee_bps = 25    taker_fee_bps = 40
        |
        +-> risk/position_sizer.py:139-140   -> SZ-030 net-Kelly f* <= 0
        +-> the DERIVED p-bar                -> SZ-023 rungs
        +-> main.py:1478, 4737, 5670         -> pretrade EV gate cost stack
```

**THE DEFECT (docket FEE-1): the configured stack is ~half the venue's
real bottom tier** — Kraken T1 is 40/80, config says 25/40. So the
invariant edge is invariant *around the wrong anchor*, and it errs in
the dangerous direction: understating cost lowers the net-Kelly
breakeven, so **SZ-030 rejects too FEW trades**. The most trustworthy
rule in the system is systematically too permissive.

## Stage 3 — market → back (fills, booking, labels)

**This is where internal consistency becomes the problem.**

`config.order_manager.maker_fee_bps = 25 / taker_fee_bps = 40` — the
**same understated numbers** the decision path used. So realized P&L is
*booked* at the same wrong cost the entry was *approved* at.

Consequence: the corpus labels, the postmortems, the equity curve, and
the cohort's net figures all inherit the same optimism. Decision and
measurement agree with each other **because they share the error**.
A loop that is internally consistent and externally wrong is the hardest
failure to see from inside — nothing disagrees, so nothing alarms.

The fill ledger itself is sound: `exec_era` stamped per fill, honest-fill
era-4 physics, hash-chained audit. The *physics* of the loop is right;
the *price* is wrong.

## Stage 4 — analysis (and the one thing that caught it)

**Aligned, and it did its job.** The analysis layer does NOT inherit the
configured constant — it measures cost from realized fills
(`scripts/cost_truth_report.py`, `scripts/cost_attribution.py`). That
independent route produced **66.76 bps measured round-trip** against a
configured stack implying far less, which is how FEE-1 surfaced at all.

This is the referee lattice working exactly as designed: an independent
instrument disagreed with the engine's own assumption, and the
disagreement was the finding. It is also the third time in this repo's
record that a *measurement* route caught something the decision path
could not see about itself.

## The interlock that makes FEE-1 a boundary decision, not a one-liner

Writing the true fee does not just change a number. `core/config_guard.py`
(the SZ-030/exploration breakeven check, ~line 3324-3338) computes
`b_net` from the fee stack and `breakeven = 1/(1+b_net)`, then verifies
the exploration probe's `p_win` clears it. At true fees:

- breakeven moves **0.690 → 0.834** (+14.3 points)
- exploration ships `p_win = 0.700`
- → `p_win < breakeven` → **config_guard FATAL → the bot will not start**

That is the guard doing its job: it refuses an incoherent config rather
than letting a probe lane run below breakeven. But it means **the true
cost number and the exploration lane are in direct conflict**, and the
probe lane generates ~85% of the cohort the era-4 gate is accruing
(FEE-2). Correcting the fee therefore *necessarily* bundles with a probe
redesign — it cannot ship alone.

## Alignment findings, ordered

| # | finding | class |
|---|---|---|
| **A1** | The edge's cost anchor is ~half the venue's real bottom tier; SZ-030 is too permissive in the dangerous direction | BOUNDARY (FEE-1) |
| **A2** | Decision-side and booking-side share the same wrong constant, so the loop cannot self-detect A1 | BOUNDARY (same fix) |
| **A3** | Correcting A1 trips a config_guard FATAL via the probe breakeven — fee correction and probe redesign are one decision, not two | BOUNDARY (FEE-1+FEE-2 bundled) |
| **A4** | OM-080 fee reconciliation has never fired — the account's actual tier row is *unverified*; the 40/80 figure is the published bottom tier, not this account's measured tier | SAFE to resolve: one read-only `TradeVolume` call (FEE-3) |
| **A5** | Firewall carries no cost awareness — correct as-is; adding economics there would duplicate the SZ layer and split the edge across two places | NO ACTION |
| **A6** | Control plane cannot loosen a veto remotely | NO ACTION (verified correct) |

## What this changes about the boundary design

`2026-08-22_boundary_around_the_invariant_edge.md` PROTECTS SZ-030 /
SZ-023-derived-bar / SZ-046 from re-tuning. **That protection stands and
is reinforced here** — with one refinement now explicit:

> Protecting the veto **rules** does not mean freezing their **cost
> anchor**. The rules are invariant and trustworthy; the constant they
> read is wrong. Boundary #6 may correct the anchor (FEE-1+FEE-2
> together) *without* touching the rule structure — and doing so makes
> the protected rules stricter, never looser, which is the safe
> direction.

Ordering for boundary #6, updated:

1. **FEE-1 + FEE-2 bundled** — correct the anchor of the thing that
   demonstrably works. Highest value: it makes the invariant edge
   *honest*, and every downstream statistic with it.
2. **REG-8 v2** — delete the turbulence clause (measures the wrong
   thing, touches no protected rule).
3. SWEEP-0/1 (CRITICAL correctness), ALGO-5, REG-7, LS-1/2.

## Pre-work that is SAFE and should precede the boundary

- **FEE-3**: run the read-only `TradeVolume` reconciliation once so the
  boundary decision uses this account's *measured* tier rather than the
  published bottom tier. It needs the first real credential on the box;
  scope it query-only.
- Re-run `cost_truth_report` stratified by era so the measured 66.76 bps
  is separated from the pre-honest-fill eras.
