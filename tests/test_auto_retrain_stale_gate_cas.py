"""W2-2 call-site wiring: main.py's in-process auto-retrain
(_maybe_auto_retrain) must thread the stale-gate CAS through to save_model,
so a concurrent CLI scripts/train_meta.py deploy landing between this gate's
should_deploy() read and its save cannot be silently clobbered.

Everything not under test (history loading, walk-forward selection,
interpretability background) is stubbed; ml.models.save_model, the CAS
mechanism itself, and ModelMonitor are real.
"""
import types
from pathlib import Path

import numpy as np

from main import LiquidityBot
from ml.models import LogisticModel, load_model, save_model
from ml.monitor import ModelMonitor


def _fit_logistic(seed):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(80, 4))
    y = (X[:, 0] > 0).astype(float)
    return LogisticModel(seed=seed).fit(X, y)


def _fake_history(n=200):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(n, 4))
    y = (X[:, 0] > 0).astype(float)
    w = np.ones(n)
    sig = np.arange(n, dtype=float)
    res = np.zeros(n)
    return types.SimpleNamespace(
        row_count=lambda: n,
        load_training_data=lambda **k: (X, y, w, sig, res),
        last_load_stats={"live_clean": n})


def _bot(tmp_path, monitor):
    b = LiquidityBot.__new__(LiquidityBot)
    b.config = {"ml": {"retrain_history_path":
                       str(tmp_path / "retrain_history.jsonl")}}
    b.history = _fake_history()
    b.monitor = monitor
    b.meta = types.SimpleNamespace(
        trained=False, model=None, calibrator=None, trained_rows=0,
        model_path=str(tmp_path / "meta_model.json"),
        reload=lambda: None)
    b._retrain_attempted = False
    b._rows_at_last_train = 0
    b._retrain_failures = 0
    return b


def test_racing_concurrent_writer_is_not_clobbered(tmp_path, monkeypatch):
    monitor = ModelMonitor({
        "retrain_flag_path": str(tmp_path / "retrain.flag"),
        "retrain_min_rows": 60, "deploy_min_oof": 20})
    b = _bot(tmp_path, monitor)

    # stub the heavy pipeline stages: contract screen (keep everything),
    # walk-forward selection (fixed winner), and the SHAP background sample
    import ml.contracts as contracts_mod
    import ml.interpret as interpret_mod
    import ml.walkforward as wf_mod

    monkeypatch.setattr(contracts_mod, "get_contract",
                        lambda: types.SimpleNamespace(
                            check_matrix=lambda X: {"keep": np.ones(len(X), bool)}))
    monkeypatch.setattr(interpret_mod, "background_sample", lambda X, n: [])

    oof_p = np.concatenate([np.full(20, 0.9), np.full(20, 0.1)])
    oof_y = np.concatenate([np.ones(20), np.zeros(20)])
    challenger_model = _fit_logistic(seed=7)
    results = {"selected": "logistic", "gated": None,
              "logistic": {"oof_p": oof_p, "oof_y": oof_y},
              "model": challenger_model, "importance": []}
    monkeypatch.setattr(wf_mod, "evaluate_and_select",
                        lambda *a, **k: results)

    # the CONCURRENT writer (e.g. a CLI train_meta.py run) deploys ITS OWN
    # champion to model_path the instant should_deploy() runs - i.e. AFTER
    # this gate captured its prior-artifact hash but BEFORE it writes.
    real_should_deploy = ModelMonitor.should_deploy
    concurrent_model = _fit_logistic(seed=99)

    def racing_should_deploy(self, challenger_brier, n_oof=None):
        save_model(concurrent_model, b.meta.model_path)
        return real_should_deploy(self, challenger_brier, n_oof=n_oof)
    monkeypatch.setattr(ModelMonitor, "should_deploy", racing_should_deploy)

    reload_calls = []
    b.meta.reload = lambda: reload_calls.append(True)

    assert not Path(b.meta.model_path).exists()
    b._maybe_auto_retrain()

    loaded = load_model(b.meta.model_path)
    assert loaded is not None
    # the concurrent writer's artifact must survive untouched
    assert np.allclose(loaded.w, concurrent_model.w)
    # the stale writer must never have "deployed": no reload, no champion sync
    assert reload_calls == [], \
        "a CAS-refused save must not trigger meta.reload()"
    assert monitor.champion_brier == 0.25, \
        "a CAS-refused save must not call note_deployed() / move the badge"


def test_uncontested_deploy_still_succeeds(tmp_path, monkeypatch):
    """Sanity: with no race, the SAME wiring deploys normally."""
    monitor = ModelMonitor({
        "retrain_flag_path": str(tmp_path / "retrain.flag"),
        "retrain_min_rows": 60, "deploy_min_oof": 20})
    b = _bot(tmp_path, monitor)

    import ml.contracts as contracts_mod
    import ml.interpret as interpret_mod
    import ml.walkforward as wf_mod
    monkeypatch.setattr(contracts_mod, "get_contract",
                        lambda: types.SimpleNamespace(
                            check_matrix=lambda X: {"keep": np.ones(len(X), bool)}))
    monkeypatch.setattr(interpret_mod, "background_sample", lambda X, n: [])

    oof_p = np.concatenate([np.full(20, 0.9), np.full(20, 0.1)])
    oof_y = np.concatenate([np.ones(20), np.zeros(20)])
    challenger_model = _fit_logistic(seed=7)
    results = {"selected": "logistic", "gated": None,
              "logistic": {"oof_p": oof_p, "oof_y": oof_y},
              "model": challenger_model, "importance": []}
    monkeypatch.setattr(wf_mod, "evaluate_and_select", lambda *a, **k: results)

    reload_calls = []
    b.meta.reload = lambda: reload_calls.append(True)

    b._maybe_auto_retrain()

    assert reload_calls == [True]
    assert monitor.champion_brier < 0.25
    loaded = load_model(b.meta.model_path)
    assert np.allclose(loaded.w, challenger_model.w)
