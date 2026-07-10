"""Regression for the manual retrain deploy gate.

scripts/train_meta.py used to call save_model() unconditionally, bypassing
the champion/challenger gate (ModelMonitor.should_deploy/.note_deployed)
that main.py's in-process auto-retrain already enforces. A manual retrain
could silently swap in a worse model, and the governor's persisted
champion_brier in state.json never tracked what was actually deployed
(observed stuck at the 0.25 default despite real deploys having happened).
"""
import json

import numpy as np

from core.persistence import StateStore
from ml.models import GradientBoostedStumps, load_model
from ml.monitor import ModelMonitor
from scripts.train_meta import _deploy_challenger


def _fitted_gbt():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(120, 4))
    y = (X[:, 0] + 0.3 * rng.normal(size=120) > 0).astype(float)
    return GradientBoostedStumps(seed=3).fit(X, y)


def _seed_state(state_path, champion_brier: float) -> dict:
    m = ModelMonitor({})
    m.champion_brier = champion_brier
    seed = {"monitor": m.to_dict()}
    StateStore(str(state_path)).write_raw(seed)
    return seed


def test_worse_challenger_rejected_and_model_file_untouched(tmp_path):
    model_path = tmp_path / "meta_model.json"
    state_path = tmp_path / "state.json"
    _seed_state(state_path, champion_brier=0.10)
    config = {"ml": {"monitor": {}}, "system": {"state_path": str(state_path)}}

    deployed = _deploy_challenger(config, _fitted_gbt(),
                                  challenger_brier=0.20, extra={},
                                  model_path=str(model_path))

    assert deployed is False
    assert not model_path.exists()
    still = json.loads(state_path.read_text(encoding="utf-8"))
    assert still["monitor"]["champion_brier"] == 0.10


def test_better_challenger_deployed_and_champion_persisted(tmp_path):
    model_path = tmp_path / "meta_model.json"
    state_path = tmp_path / "state.json"
    _seed_state(state_path, champion_brier=0.30)
    config = {"ml": {"monitor": {}}, "system": {"state_path": str(state_path)}}

    deployed = _deploy_challenger(config, _fitted_gbt(),
                                  challenger_brier=0.10,
                                  extra={"oof_brier": 0.10},
                                  model_path=str(model_path))

    assert deployed is True
    m = load_model(str(model_path))
    assert m is not None and m.kind == "gbt"
    updated = json.loads(state_path.read_text(encoding="utf-8"))
    assert updated["monitor"]["champion_brier"] == 0.10


def test_no_existing_snapshot_still_deploys_without_creating_one(tmp_path):
    model_path = tmp_path / "meta_model.json"
    state_path = tmp_path / "state.json"       # never created
    config = {"ml": {"monitor": {}}, "system": {"state_path": str(state_path)}}

    deployed = _deploy_challenger(config, _fitted_gbt(),
                                  challenger_brier=0.15, extra={},
                                  model_path=str(model_path))

    assert deployed is True
    assert model_path.exists()
    assert not state_path.exists()   # no partial/synthetic snapshot written
