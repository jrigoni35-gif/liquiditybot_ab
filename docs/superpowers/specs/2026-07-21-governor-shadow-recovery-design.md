# Governor shadow-recovery (ML-075) — design

## Problem (root cause, evidence-confirmed)

A killed model (monitor level 2, `use_model=False`) is blindfolded from
proving itself:

- Every close is recorded `model_scored=(use_model and trained)` → `False`
  while killed (`main.py:2258`).
- The recovery window `_windows()` counts only model-scored closes, so it
  can never reach `min_trades=15` while killed → `_evaluate()` early-returns.
- The ONLY re-arm path left is `note_deployed()` — a *retrained* challenger
  clearing the deploy gate (0.005 Brier margin, ≥30 OOF, 40 new rows, 12h
  cooldown).

On a young/starved corpus (80 rows, cold) that stalls for a very long time.
Observed live 2026-07-21: model KILLED, `{kind="prior"}`, kelly_mult 0.40.

## Fix — shadow-recovery (breaks the deadlock, does NOT lower the bar)

While killed, keep scoring the champion in the background on each labeled
close (telemetry-only, never influences sizing/entry). When the champion
*would have* beaten baseline on the trades that actually happened — judged
on the IDENTICAL bar (`brier_margin`, `min_trades`, calibration, Wilson-LCB)
— re-arm one step, level 2 → 1 (throttled, kelly 0.7). Getting 1 → 0 is
still earned live via the normal model-scored window.

**Safety.** Re-arm is to the THROTTLED level, never straight to full. It is
a *probation*: at level 1 `use_model=True`, real model-scored closes accrue,
and if the champion is actually bad on model-selected trades the normal
`_evaluate` re-kills 1 → 2. Self-correcting. Zero capital ever risked on the
shadow score. Selection caveat (the shadow window judges the champion on
*prior*-selected trades) is exactly why it only earns the half-step.

## Change map

- `ml/postmortem.py` — `TradeThesis`: add `shadow_p: float = -1.0` (champion's
  armed calibrated p at entry, computed even when killed; -1 = unknown /
  predates field). Additive, default-preserving.
- `main.py`
  - entry (~2238): `shadow_p = self.meta.p_win(feats, gate_conf,
    shrinkage=self.monitor.shrink_base, use_model=True)` when `self.meta.trained`
    else `-1.0`; pass `shadow_p=shadow_p` into `TradeThesis`. TELEMETRY-ONLY —
    the sized `p_win` is untouched, so no trade changes.
  - close (~1507): when a thesis closes with a valid `shadow_p` (≥0), call
    `self.monitor.record_shadow_close(thesis.shadow_p, int(realized_net_usd>0))`.
- `ml/monitor.py`
  - `__init__`: `self.shadow_recovery = bool(cfg.get("shadow_recovery", True))`;
    `self._shadow_records: deque(maxlen=self.window*3)`.
  - `record_shadow_close(shadow_p, label)`: append; then, if `level==2` and
    enabled, `_try_shadow_recovery()`.
  - `_shadow_window()`: mirror `_windows()` over `_shadow_records`.
  - `_try_shadow_recovery()`: build the shadow window; apply the SAME `degraded`
    test used in `_evaluate`; if NOT degraded, step `level 2→1`, `_apply_level()`,
    audit `ML_SHADOW_RECOVER`, and CLEAR `_shadow_records` (fresh probation).
    Never touches level when `<2`; never steps below 1.
  - clear `_shadow_records` on entry into level 2 (fresh kill) and in
    `note_deployed` (fresh champion).
- `core/codes.py` — `ML_SHADOW_RECOVER = "ML-075"`.
- `config.json` — `ml.monitor.shadow_recovery: true` + `_doc`.
- `core/config_guard.py` — validate it is a bool (no FATAL; type coherence only).

## Tests (TDD, `tests/test_monitor_shadow_recovery.py`)

1. killed + clean shadow window (champion beats baseline) → re-arms 2→1.
2. killed + bad shadow window (champion worse than baseline+margin) → stays 2.
3. shadow recovery is a HALF-step: never 2→0 in one shot; 1→0 still needs the
   live model-scored window.
4. `shadow_recovery=False` → never re-arms via shadow (stays killed).
5. shadow records never perturb the normal model-scored kill/recover path.
6. bar identity: the same window that a model-scored path would call degraded
   does NOT re-arm.

## Verification (money path — full battery + quant/overfit)

`pytest -q` · `smoke_test` · `assurance_check` · `overfit_check` ·
`quant_trials` (CI-bound) · ruff · pyright (shipped scope zero) · bandit ·
compileall. Re-baseline consciously only if a legitimate number moves.
