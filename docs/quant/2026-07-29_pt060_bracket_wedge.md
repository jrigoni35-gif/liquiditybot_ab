# PT-060 bracket wedge — incident + design correction (2026-07-29)

## Incident (operator: "its getting faked out and bled")

Position `3ea2a851` (LINK/USD short, paper exploration probe, entered
ts 1785249740, model_p 0.278 / sized_p 0.64, ~$12 notional):

- From bar 42 the live events feed logged
  `PT-060: LINK/USD time-stop: no favorable progress (42 bars, MFE 0.18%)
  — scratching full close` **every ~5 s for ~2 hours** (~1,900 lines) —
  with **zero** exit order submissions. The pc-live audit chain confirms:
  between entry and the runner restart the only LINK records are SZ-047
  probe throttles; the first exit order (`d96cab21`) was created at
  ts 1785269953 — 1.4 s **after** the restart.
- The restart-close was an accident of state: cold sigma re-armed the
  give-back at peak 0.18% (the pre-#133/#134 arming class; the current
  tree's `_measured_sigma` gate already prevents this — verified) and the
  trail fired instantly because price was far through the floor.
- Postmortem: realized **−1.69%** vs expected −0.08%. The PT-060 scratch
  at bar 36 would have taken ~−0.2%.

## Root cause

Not a submission failure — a **design interaction** in geometry-alignment
spec D1 (T5). Every model-lane entry (probe and conviction alike) is a
bracket position; `_manage_open_position` suppressed BOTH the scheduled
profit-take AND the PT-060 time-stop for bracket positions, handing the
time dimension to the bracket deadline leg. But:

- PT-060 scratch: `max_bars_no_progress = 36` bars (3 h)
- bracket deadline: `ml.label_max_bars = 96` bars (8 h)

A no-progress position (the exact cohort PT-060 was derived from —
2026-07-23: MFE 0.16% / MAE −1.44%, recovered_after_stop **0/17**) sat in
the 36→96-bar gap with its measured protection disabled, riding toward
the sl leg. Since probes are ~all model-lane flow, the suppression
disabled the no-progress protection fleet-wide — the equity bleed the
operator sees is fake-out entries each paying ~8–20× the intended
scratch cost.

The 5-second log spam was a separate hygiene defect: the tier engine
announces the scratch inside `evaluate()` before the caller decides
whether the action may act.

## Correction (shipped)

1. `main.py::_manage_open_position`: `suppressed_for_bracket` now covers
   ONLY the scheduled profit-take. PT-060 is reclassified as what its
   derivation always was — a **protective senior overlay** (loss
   avoidance), same seniority class as the give-back ratchet and the
   hard stop (CLAUDE.md invariant 5: exits always allowed; blocks never
   escapes). The one-cycle resting-maker deferral (P2 review Minor #6)
   is unchanged and now applies to bracket positions too.
2. Label side is untouched **by construction**: a PT-060 close lands
   `barrier="realized"` exactly like every senior-overlay close (pinned
   by `test_finalize_position_overlay_reason_falls_back_to_realized`),
   never `tb_*` — no tb-era contamination. The probe's candidate twin
   (cand_id lineage, W2-4) still receives the full triple-barrier label
   from market data, so the model's tb training signal is intact. The
   conscious divergence — the traded bet carries a protective overlay
   the tb label does not model — is the same divergence give-back and
   chandelier already have under spec D1 ("overlays stay senior").
3. Log hygiene: PT-060 announces once per position (`_ts_announced`,
   in-memory, same pattern as `_gb_armed_log`); the ACTION still fires
   every cycle until the close lands. `correlation shift detected` logs
   a compact top-3 summary once per False→True episode (full dict at
   DEBUG). `probe THROTTLED` logs at most once per asset per 10 min
   (the SZ-047 audit record stays per-event — invariant 6).

Tests: `tests/test_bracket_exits.py`
(`test_pt060_time_stop_fires_as_senior_overlay_on_bracket_position`,
`test_pt060_on_bracket_still_defers_one_cycle_for_resting_maker_take`),
`tests/test_log_hygiene.py`, and
`tests/test_probe_throttle.py::test_throttle_log_line_rate_limited_per_asset_audit_untouched`.

## Quant adjudication

- quant-trials gates: unaffected — the trials harness runs
  `time_stop: {enabled: false}` and no bracket seam (world-model scope
  note at `scripts/quant_trials.py:55-69`).
- Label distribution: live tb-era rows shrink only by the no-progress
  class that now scratches (their candidate twins still label); this is
  a return to the pre-T5 measured state, not a new regime.
- Expected live effect: no-progress probes cap at ~−0.2%-class scratches
  at 3 h instead of −1.4%-class rides toward sl at up to 8 h.
