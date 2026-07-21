"""Champion-badge reconciliation (ML-076): the governor's champion_brier badge
must track the model actually loaded. A restored monitor snapshot can outlive
its model — the badge then claims a Brier the loaded model cannot back up, and
gating challengers against that ghost lets it squat forever (measured live:
badge 0.1441 vs loaded model 0.2259, every honest 0.189 challenger rejected ->
model stuck KILLED). reconcile_champion_badge realigns the badge UP to the
loaded model's own OOF, and must NEVER touch level/kelly/records (a startup
reconcile that silently un-killed a governed model would be a safety hole).
"""
from ml.monitor import ModelMonitor

CFG = {"min_trades_to_judge": 5, "window_trades": 30}


def test_ghost_badge_realigns_up_to_loaded_model():
    m = ModelMonitor(CFG)
    m.champion_brier = 0.1441                 # ghost from an older, dropped model
    changed = m.reconcile_champion_badge(0.2259)   # loaded model's honest OOF
    assert changed is True
    assert m.champion_brier == 0.2259
    # a challenger that could not beat the ghost now clears the honest bar
    assert m.should_deploy(0.189, n_oof=50) is True


def test_consistent_badge_is_left_alone():
    m = ModelMonitor(CFG)
    m.champion_brier = 0.20
    assert m.reconcile_champion_badge(0.20) is False
    assert m.champion_brier == 0.20


def test_badge_at_or_above_loaded_is_left_alone():
    # badge already >= the loaded model's self-score (e.g. a REALISTIC rescored
    # value, higher Brier than the model's optimistic birth certificate) -> the
    # reconcile must NOT pull it down toward that optimistic number, which would
    # re-open the squat. Only a ghost (badge BETTER/lower than the loaded model)
    # is realigned, and always upward.
    m = ModelMonitor(CFG)
    m.champion_brier = 0.30
    assert m.reconcile_champion_badge(0.22) is False
    assert m.champion_brier == 0.30


def test_missing_or_bad_loaded_score_is_a_noop():
    m = ModelMonitor(CFG)
    m.champion_brier = 0.14
    for bad in (None, 0.0, 1.0, -0.1, 1.5, float("nan")):
        assert m.reconcile_champion_badge(bad) is False
    assert m.champion_brier == 0.14


def test_unloaded_model_discards_ghost_badge_to_no_champion_default():
    # live root cause: the deployed champion (58-feature logistic) fails the v8
    # width guard, so it never loads (meta.trained False, oof None). The badge
    # then claims a champion that does not exist on this schema — a pure ghost
    # that blocks every fresh challenger. With no backing model, reset it to the
    # no-champion default so a current-schema challenger can finally deploy.
    m = ModelMonitor(CFG)
    m.champion_brier = 0.1441
    assert m.reconcile_champion_badge(None, model_loaded=False) is True
    assert m.champion_brier == 0.25
    # should_deploy's no-champion clause now lets a real challenger through
    assert m.should_deploy(0.20, n_oof=50) is True


def test_unloaded_model_with_default_badge_is_noop():
    m = ModelMonitor(CFG)
    m.champion_brier = 0.25
    assert m.reconcile_champion_badge(None, model_loaded=False) is False
    assert m.champion_brier == 0.25


def test_loaded_flag_defaults_true_keeps_conservative_noop_on_missing_oof():
    # model_loaded defaults True -> a LOADED model with a transiently-missing oof
    # stays conservative (no discard), preserving the original contract.
    m = ModelMonitor(CFG)
    m.champion_brier = 0.14
    assert m.reconcile_champion_badge(None) is False
    assert m.champion_brier == 0.14


def test_reconcile_never_touches_governor_state():
    # a KILLED governor stays killed: reconcile fixes the badge ONLY, never the
    # level/kelly/use_model — re-arming must still be earned, not a boot side effect.
    m = ModelMonitor(CFG)
    for _ in range(14):
        m.record_close(0.9, 0, model_scored=True)
    assert m.level == 2 and m.use_model is False
    lvl, kelly, use = m.level, m.kelly_mult, m.use_model
    m.champion_brier = 0.1441
    assert m.reconcile_champion_badge(0.2259) is True
    assert m.level == lvl and m.kelly_mult == kelly and m.use_model == use
