"""W2-17: governor L0<->L1 (and L1<->L2 healthy-side) de-escalation deadband.

ml/monitor.py's _evaluate() re-derives degraded/failing from a sliding window
on EVERY closed trade. A Brier hovering within noise of baseline+brier_margin
flips degraded on and off from window churn alone; the OLD else-branch
(`self.level = max(prev - 1, 0)`) de-escalates on a SINGLE healthy evaluation,
so the governor flaps L0<->1<->0 every other trade, toggling kelly_mult
(1.0<->0.7) and shrinkage with it. The L1->L2 escalation side already has
streak discipline (_level_streak); de-escalation had none.

Contract (post-fix): de-escalation (any downward step) requires
`deescalate_healthy_windows` (config-lifted, default 3) CONSECUTIVE healthy
evaluations. Escalation stays immediate (fail toward caution).
"""
from ml.monitor import ModelMonitor

# window_trades=1 + a fixed base_rate clip means calibration_gap is always 0
# (n=1 < the 5-bin minimum) and hit_deficit never fires (see inline math) -
# each single-record window is then judged on brier_margin alone, letting a
# single close fully determine "healthy" vs "degraded" independent of history.
CFG = {"window_trades": 1, "min_trades_to_judge": 1}

DEGRADED = (0.85, 1)   # promised .85, won: brier .0225 vs baseline .0025 -> degraded, not failing
HEALTHY = (0.94, 1)    # promised .94, won: brier .0036 vs baseline .0025 -> healthy


def test_deescalation_flaps_are_gated_by_a_consecutive_healthy_streak():
    m = ModelMonitor(CFG)
    levels = []

    def close(p, y):
        m.record_close(p, y, model_scored=True)
        levels.append(m.level)

    close(*DEGRADED)                    # 0 -> 1 (escalation is immediate)
    assert levels[0] == 1

    # an oscillating healthy/degraded stream never strings together
    # `deescalate_healthy_windows` (default 3) consecutive healthy evaluations
    # - the level must therefore never flap back down to 0.
    for _ in range(10):
        close(*HEALTHY)
        close(*DEGRADED)

    assert min(levels) == 1, \
        f"level flapped down during an oscillating stream (never 3 " \
        f"consecutive healthy windows): {levels}"
    transitions = sum(1 for i in range(1, len(levels))
                      if levels[i] != levels[i - 1])
    assert transitions == 0, \
        f"expected zero transitions after the initial escalation, " \
        f"got {transitions}: {levels}"


def test_deescalation_still_happens_after_n_consecutive_healthy_windows():
    m = ModelMonitor(CFG)
    m.record_close(*DEGRADED, model_scored=True)
    assert m.level == 1
    # exactly deescalate_healthy_windows (default 3) consecutive healthy closes
    n = m.deescalate_healthy_windows
    for i in range(n):
        m.record_close(*HEALTHY, model_scored=True)
        if i < n - 1:
            assert m.level == 1, "must not de-escalate before the streak completes"
    assert m.level == 0, "must de-escalate once the healthy streak completes"


def test_deescalate_healthy_windows_config_lifted_default_is_three():
    m = ModelMonitor({})
    assert m.deescalate_healthy_windows == 3


def test_deescalate_healthy_windows_is_configurable():
    m = ModelMonitor({**CFG, "deescalate_healthy_windows": 1})
    m.record_close(*DEGRADED, model_scored=True)
    assert m.level == 1
    m.record_close(*HEALTHY, model_scored=True)
    assert m.level == 0, "with the knob set to 1 a single healthy window " \
                        "must de-escalate immediately (old behavior)"
