## Overfit discipline (applies to EVERY tunable)

- No fitted-looking literals in decision paths. Thresholds live in
  `config.json` with guard checks in `core/config_guard.py` (FATAL for
  incoherent combinations). If you find a hardcoded knob, lift it with
  an identical default â€” behavior-preserving, then tune.
- Model changes must keep the battery green: `scripts/overfit_check.py`
  (OF-1 gap, OF-2 shuffle-null, OF-3 PBO on the DEPLOYED simplicity-
  ladder rule, OF-4 plateau, OF-5 DSR, OF-6 purge, OF-7 DoF) and
  `tests/test_overfit.py`. PBO measures the deployed selection rule,
  never argmax.
- Signal-gate work optimizes NET profit or it doesn't ship: every gate
  change must clear the pretrade EV gate's cost stack in smoke, keep
  quant-trial G3/G5 (upside intact, capture), and beat the simplicity
  ladder out-of-sample â€” never tune a gate to a backtest peak (OF-4).
- Protocol/risk changes must keep `scripts/quant_trials.py` gates
  green (G1â€“G5, CI-bound in `tests/test_quant_trials.py`). If a
  legitimate change moves numbers, re-baseline consciously at 200Ã—1200 â€”
  never widen a gate to silence CI.

