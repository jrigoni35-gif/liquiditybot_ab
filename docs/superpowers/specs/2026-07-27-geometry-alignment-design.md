# Geometry Alignment: one bet from label to fill

**Date:** 2026-07-27 · **Status:** implemented @ 6ac770b (T1-T8)
· **Origin:** systematic-debugging of the entry drought + derived-bar work
(commit ae4b531). Operator decisions recorded below are binding.

## Problem (measured, not hypothesized)

Three geometries currently describe three different bets:

| Layer | Bet | Numbers (live config, 2026-07-27) |
|---|---|---|
| Label (`ml/labeling.py:triple_barrier`) | +8σ_bar before −6σ_bar within 96 bars (8h), net of ~0.5% expected cost | σ-scaled pt ≈ ~1% typical → cost ≈ half the profit distance; bracket breakeven ≈ 0.72; label base rate 0.399 ≈ the 8:6 random-walk rate (0.4286) |
| Sizing (`risk/position_sizer.py`) | Kelly on the tier/stop structure | b_net = 0.583 (avg gross win 2.19% vs stop 2.0%, rt cost 0.65%) → breakeven 0.632 |
| Live exits (`risk/profit_tiers.py`) | tiers 1/2/3.5/5% × 25% + 2% stop + ratchet | realized barrier reasons: `tier`/`trail`/`floor`/`time_stop` |

Consequences: the model's p prices a bet nobody trades; Kelly prices a bet
the model doesn't predict; live closes emit barrier reasons the era system
maps to the OLD label era, so live outcomes likely do not reach tb-era
training at all (verification item V1). Costs eat 30% of the tier bet's
gross win and ~50% of the label bet's profit distance.

## Operator decisions (binding)

1. **The bet:** conviction entries trade the label's bracket ("Trade the
   label's bet"). Extended during design, approved: ALL model-lane entries
   (conviction AND probes) trade the bracket — probes are the label
   factory and their live closes must speak tb vocabulary.
2. **Risk containment:** "Risk lives in SIZE." The bracket keeps its true
   geometry (sl uncapped); notional shrinks as sl widens so dollar-risk
   matches the legacy 2%-stop trade. Overlays (ratchet, hard-stop DD,
   flatten, force_dry) remain senior — exits are always allowed.

## D1 — The bet (engine)

Model-lane entries (conviction + exploration probes) carry a bracket
computed AT ENTRY and stored on position meta:

- `pt_frac`, `sl_frac` from the shared geometry helper (D2), using the
  entry-time σ_bar and expected cost;
- `deadline_ts` = entry + `ml.label_max_bars` bars (the label horizon).

Exit evaluation each cycle (existing fast_cycle exit seam):

- **pt leg:** maker-first exit at entry×(1+side·pt_frac) — existing
  maker-first machinery; never blocks hard exits (F2 invariant).
- **sl leg:** existing stop-escalation ladder at entry×(1−side·sl_frac)
  (final-rung market allowed — OM-011 exception unchanged).
- **vertical:** at `deadline_ts`, close the remainder via the normal exit
  path (maker-first, escalate).
- Overlay exits (ratchet/hard-stop/flatten/force_dry/manip) fire exactly
  as today and record their own barrier reasons.

Postmortem barrier reasons for bracket exits: `tb_pt` / `tb_sl` /
`tb_time` — the SAME strings the labeler emits, so live rows join the
triple_barrier era natively. Tier exits remain untouched for the long
book and any non-model lane.

Config: `bracket_exits: {"enabled": true}` (top-level block). `false` is
the escape hatch — reverts model-lane exits to the tier engine.

## D2 — Cost-aware geometry, one source of truth

New helper in `ml/labeling.py` consumed by BOTH the labeler and the
engine (alignment is structural, not by convention):

```python
def barrier_geometry(sigma_bar: float, cost_pct: float, cfg) -> tuple:
    """(pt_frac, sl_frac). sigma_bar is a FRACTION; cost_pct in PERCENT.
    sigma_eff = max(sigma_bar, pt_cost_mult * (cost_pct/100) / pt_mult)
    pt_frac = pt_mult * sigma_eff ; sl_frac = sl_mult * sigma_eff"""
```

- Floor applied to the σ INPUT: both barriers scale together, the 8:6
  ratio is preserved (ratio retuning is out of scope, OF-4), one knob.
- New config: `ml.label_pt_cost_mult` = **4.0** (profit distance ≥ 4×
  expected cost → costs ≤ 25% of gross win). At c = 0.5%: floor pt = 2%,
  sl = 1.5%. Sizer-worst-case breakeven at the floor:
  (2.0 − 0.65)/(1.5 + 0.65) = 0.628 → bar 0.614 — probe synthetic p
  (0.64) clears with 0.026 headroom (guard-checked, D5).
- `CandidateLabeler` switches to the helper (same pt/sl/horizon knobs,
  now cost-floored). Horizon stays 96 bars; floor-widened barriers
  resolve less often → honest `tb_time` verticals, already visible on
  the era-mix panels.
- **Schema bump:** history rows gain `pt_frac`, `sl_frac` columns
  (existing auto-migration machinery; older rows migrate with 0.0 =
  "unknown geometry"). Every label becomes self-describing; per-row b is
  auditable.

## D3 — Sizing coherence

`PositionSizer.size()` gains `bracket: tuple[float, float] | None = None`
(pt_pct, sl_pct — PERCENT units, matching `rt_cost_pct`). Default None →
byte-identical legacy path (CLAUDE.md invariant 7). When set:

- `b_net_trade = (pt_pct − rt_cost_pct) / (sl_pct + rt_cost_pct)`
  (worst-case costs — the sizer's existing discipline);
- bar = `max(1/(1+b_net_trade) + p_bar_edge_margin, min_p_win)` +
  counter-trend bonus (the derived-bar machinery, now per-trade);
- Kelly `f*` on `b_net_trade`, same kelly_fraction/cap/dd-throttle;
- **risk-in-size:** `usd = equity × f × (stop_loss_pct / sl_pct)` —
  identical to legacy at sl = 2%, notional shrinks as sl widens; all
  existing caps (max_position_pct, heat, budgets, min ticket, floors)
  apply downstream unchanged.

SZ-023 detail strings carry the bracket basis (pt/sl/b/breakeven).

## D4 — Cost honesty (measured, never assumed)

No blind fee edits. Implementation reads realized round-trip costs from
postmortems/fee-recon; if measured differs from the configured 25/40 bps
beyond tolerance (±20%), config is updated CONSCIOUSLY with the evidence
in the commit message and docs/quant note. If Kraken's real tier is
~16/26, every breakeven drops materially — but only measurement earns it.

## D5 — Guards (core/config_guard.py)

- FATAL: `ml.label_pt_cost_mult` outside [0, 20] (0 = legacy floor-disable,
  not FATAL); WARN below 2 (costs >50% of the profit distance — the bet
  the floor exists to prevent).
- FATAL: `bracket_exits.enabled` with `ml.label_mode != "triple_barrier"`
  (the bracket trades the tb bet; incoherent otherwise).
- Probe-clearance interlock extended: WARN when `ml.exploration.p_win`
  has < 0.005 clearance over the WORST-CASE bracket bar (the floored
  bracket, sizer costs — 0.614 today).
- Existing derived-bar guards unchanged for the non-bracket path.

## D6 — Proof instrument + verification

- **Comparator (report-only, new ML-code from the registry):** for every
  bracket-traded close, record labeled-counterfactual vs realized:
  barrier agreement + |net ret delta|. Surfaced in
  `status["ml"]` → gc gauge `liquiditybot_bracket_divergence_rate` (+
  agreement count), one stat panel on the execution board (era row).
  Divergence feeds the cost model (D4), never gates anything.
- **V1 (verification item, first implementation task):** confirm the
  live-row era-mapping hole — realized reasons `tier`/`trail`/`floor`
  land outside the tb era, so today's live closes are excluded from
  era-filtered training. Quantify (how many live rows since exclusion
  activated), document in docs/quant, and confirm bracket closes join
  the tb era after D1.

## Success criteria

1. ≥95% of model-lane closes emit `tb_*` barrier reasons (rest = senior
   overlay exits).
2. Labeled-vs-realized divergence within cost-model tolerance on ≥80% of
   bracket closes (comparator, first 100 closes).
3. Live tb-era rows accumulate in training (era panels move).
4. Full battery green; `scripts/quant_trials.py` G1–G5 green — if the
   exit change legitimately moves G-numbers, conscious re-baseline at
   200×1200 with a docs/quant note (never widen a gate to pass).
5. No invariant touched: dry_run road-to-live, Kraken-only, withdrawal
   deny-list, limit-only entries (pt exit is a maker limit; sl uses the
   existing ladder), exits always allowed.

## Testing requirements (plan must enumerate per task)

RED-first per component; every NEW test 10+ runs; mutation-check the
load-bearing branches (bracket vs legacy path selection, geometry floor);
Windows parity rule: any test that commits files and asserts on blob
bytes pins `-text` or sets autocrlf explicitly; frozen clock for any
weight/recency assertions; schema-migration round-trip test.

## Out of scope

pt/sl ratio retuning (8:6 stays), fee negotiation/venue work, long-book
engine, label-history rewrites (the era system already partitions),
in-repo UI, any relaxation of hard invariants.

## Rollout

Ships enabled in DRY_RUN via the normal branch → battery → main → PC
test-gated updater path. Watch: era panels, divergence stat, drought
clock. Escape hatch: `bracket_exits.enabled=false` (config, restart).
