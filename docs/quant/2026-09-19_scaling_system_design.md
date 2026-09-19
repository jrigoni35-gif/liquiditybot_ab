# Scaling governor — design + pre-registration for the 09-22 boundary (2026-09-19)

**Status:** DESIGN, awaiting boundary adjudication. Sizing is
cohort-resetting under the era-9 moratorium; nothing here ships before
the operator mints the next boundary. The SAFE half —
`scripts/scaling_report.py` — ships now (measurement only) and is the
evidence base this design cites.

## The problem it solves

The institutional diagnosis (`docs/quant/2026-09-19_institutional_diagnosis.md`)
names it: the book pays ~60.5 bps round-trip friction (45.5 booked fees +
~15 measured adverse) against a measured gross edge that is statistically
zero, and size is currently set by a fixed probe ticket the grid ladder
then splits into $35–$114 rungs. Two consequences: the fee schedule, not
the signal, sets the break-even bar; and the account cannot grow into
better economics because size is constant regardless of measured edge.

## The governor, in four rules

1. **COST FLOOR (kill line).** A setup trades only if its measured gross
   edge clears `fee_bps_RT + adverse_bps` at the CURRENT binding tier.
   Today that line is **60.5 bps**; a maker-rebate shape drops it to
   **~17 bps**. The floor is re-derived, never remembered — the venue
   module and the adverse instrument own both inputs.
2. **TIER ROLL (scaling asset).** The operator's real 30d volume is a
   pre-paid cost reduction: each ladder row qualified drops the kill
   line by 10–30 bps (120 → 90 → 60 → 55 → 45 bps at the verified
   ladder). The governor reads the binding tier at boot and at every
   fee-recon proposal (the R3 file is the correction channel).
3. **EDGE-CONDITIONAL SIZE (earned, never assumed).**
   `size = min(cap, quarter_Kelly × edge/variance × bankroll)`, zeroed
   without positive edge. Inputs come ONLY from the registration trip
   view (`era_readout.py`), never from raw fills. AS-OF 09-19 the
   measured edge is −$0.43/trip (n=40) → the governor sizes **$0.00**.
   That is not a failure of the design; it is the design working.
4. **GOVERNANCE COUPLING.** Size changes only at boundaries (one change
   per era), the heat cap still bounds total exposure, and every
   parameter the governor reads is stamped and re-derivable. A governor
   that cannot cite its inputs refuses to size — same discipline as
   `VolState.sigma_bar_pct_measured` (R1).

## Why these four benefits, specifically

- **Fee amortization**: at a fixed edge, larger size does not improve
  the bps economics — but the TIER ROLL does, and the only route to
  higher tiers is volume. The governor makes that path explicit instead
  of accidental.
- **Asymmetric survival**: quarter-Kelly with a hard cap and a zero
  floor cannot increase exposure during a losing regime — the failure
  mode that killed the immature eras was process noise, and the
  governor is structurally blind to process noise (it only reads
  measured edge).
- **Institutional comparability**: this is the promote-from-simulation
  pattern — sim eras produce the edge/variance inputs, live eras
  validate at capped size, size ratchets only on validated edge.

## Pre-registered inputs (what ships behind the flag)

| Input | Source | AS-OF 09-19 |
|---|---|---|
| fee_bps_RT | `core.venue_fees` binding row | 45.5 |
| adverse_bps | edge-hunter tape / R3 proposals | 15.0 |
| edge $/trip, var | `era_readout.py --json` (registration view) | −0.4299, sd 0.8659 |
| bankroll, cap, fraction | config + this registration | $800, $500, 0.25 |

## What the 09-22 operator decides

- Adopt the governor for the NEXT era's geometry (behind
  `scaling.enabled`, default false), or defer.
- If era-9 reads STOP: the governor's first live input will be the next
  configuration's era-1 readout — scaling begins at $0 and earns its
  way up. That is the intended trajectory.
- The governor does NOT address the probe-lane bypass (the model still
  cannot reach p=0.85); that is a separate docket item, not this one.
