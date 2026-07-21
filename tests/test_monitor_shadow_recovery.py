"""Governor shadow-recovery (ML-075): a KILLED model is otherwise blindfolded
from recovering — while killed every close is model_scored=False, so the
model-scored window can never refill and only a retrained challenger can
re-arm. Shadow-recovery scores the champion in the background (telemetry-only,
never traded) and re-arms 2->1 when it WOULD have beaten baseline on the trades
that actually happened, judged on the identical bar. 1->0 is still earned live.
"""
from ml.monitor import ModelMonitor

CFG = {"min_trades_to_judge": 5, "window_trades": 30, "shadow_recovery": True}


def _kill(m):
    """Drive the governor to level 2 (KILLED) on real model-scored failure:
    promised 0.9, everything loses."""
    for _ in range(14):
        m.record_close(0.9, 0, model_scored=True)
    assert m.level == 2 and m.use_model is False
    return m


def _feed_shadow(m, n, p, label):
    for _ in range(n):
        m.record_shadow_close(p, label)


def _clean_shadow_block(m):
    """One block of a calibrated, informative champion window: high-conf calls
    (0.8) win 4/5, low-conf calls (0.2) win 1/5 -> beats the base-rate baseline
    in Brier AND is well-calibrated (so it clears the SAME bar the kill used)."""
    for k in range(5):
        m.record_shadow_close(0.8, 1 if k < 4 else 0)
    for k in range(5):
        m.record_shadow_close(0.2, 1 if k < 1 else 0)


def _clean_live_block(m):
    """Same calibrated informative window, but as model-scored live closes."""
    for k in range(5):
        m.record_close(0.8, 1 if k < 4 else 0, model_scored=True)
    for k in range(5):
        m.record_close(0.2, 1 if k < 1 else 0, model_scored=True)


# ---------------------------------------------------------- the deadlock exists
def test_killed_model_cannot_recover_without_shadow():
    """Sanity: with shadow OFF, model-scored closes stop while killed, so the
    governor stays pinned at 2 no matter how many non-model closes arrive."""
    m = _kill(ModelMonitor({**CFG, "shadow_recovery": False}))
    for _ in range(30):
        m.record_close(0.6, 1, model_scored=False)   # killed => not model-scored
    assert m.level == 2 and m.use_model is False


# ------------------------------------------------------------- shadow re-arms
def test_clean_shadow_window_rearms_two_to_one():
    m = _kill(ModelMonitor(CFG))
    _clean_shadow_block(m)                     # calibrated champion beats baseline
    assert m.level == 1, "clean shadow window should re-arm the killed model 2->1"
    assert m.use_model is True and m.kelly_mult == 0.7   # throttled, not full


def test_bad_shadow_window_stays_killed():
    m = _kill(ModelMonitor(CFG))
    # champion still terrible: promises 0.9, everything loses
    _feed_shadow(m, 10, 0.9, 0)
    assert m.level == 2 and m.use_model is False


# ---------------------------------------------------------- it's a HALF-step
def test_shadow_only_rearms_to_one_never_straight_to_zero():
    m = _kill(ModelMonitor(CFG))
    for _ in range(4):                        # a long, clean shadow run
        _clean_shadow_block(m)
    assert m.level == 1, "shadow recovery must stop at the throttled level"


def test_full_trust_still_earned_live_at_level_one():
    m = _kill(ModelMonitor(CFG))
    _clean_shadow_block(m)                     # shadow re-arm 2->1
    assert m.level == 1
    # now REAL model-scored clean closes take it 1->0
    for _ in range(2):
        _clean_live_block(m)
    assert m.level == 0 and m.kelly_mult == 1.0


# ------------------------------------------------------------- config gate
def test_shadow_recovery_flag_off_disables_rearm():
    m = _kill(ModelMonitor({**CFG, "shadow_recovery": False}))
    for i in range(20):
        m.record_shadow_close(0.8, 1) if i % 2 == 0 else \
            m.record_shadow_close(0.2, 0)
    assert m.level == 2, "shadow_recovery=False must never re-arm via shadow"


# ------------------------------------------ shadow never perturbs normal path
def test_shadow_closes_do_not_move_a_healthy_governor():
    m = ModelMonitor(CFG)                      # level 0, healthy
    _feed_shadow(m, 20, 0.9, 0)                # a terrible shadow stream
    assert m.level == 0, "shadow path must only ever step 2->1, never kill/raise"


def test_rearm_clears_stale_kill_window_so_it_is_not_reconvicted():
    """The stale pre-kill records must be cleared on re-arm, else the first
    live close at level 1 re-convicts on evidence the model no longer owns."""
    m = _kill(ModelMonitor(CFG))
    _clean_shadow_block(m)
    assert m.level == 1
    # a single clean model-scored close must NOT snap back to 2 on stale window
    m.record_close(0.6, 1, model_scored=True)
    assert m.level == 1
