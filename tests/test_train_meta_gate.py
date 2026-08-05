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
from ml.models import GradientBoostedStumps, load_model, save_model
from ml.monitor import ModelMonitor
from scripts.train_meta import _deploy_challenger


def _fitted_gbt(seed=3):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(120, 4))
    y = (X[:, 0] + 0.3 * rng.normal(size=120) > 0).astype(float)
    return GradientBoostedStumps(seed=seed).fit(X, y)


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


# --------------------------------------------------------- W2-2 stale-gate CAS
def test_concurrent_writer_race_is_refused_not_clobbered(tmp_path, monkeypatch):
    """A CLI _deploy_challenger run and the runner's in-process auto-retrain
    can race a deploy: both gate a challenger against the SAME on-disk
    champion, then whichever finishes last must not silently overwrite the
    other's already-deployed artifact with a decision made against a
    champion that no longer exists. Here, another writer deploys ITS OWN
    challenger the instant this gate's should_deploy() runs - i.e. strictly
    between this call's prior-hash read and its save."""
    model_path = tmp_path / "meta_model.json"
    state_path = tmp_path / "state.json"
    _seed_state(state_path, champion_brier=0.30)
    config = {"ml": {"monitor": {}}, "system": {"state_path": str(state_path)}}

    concurrent_model = _fitted_gbt(seed=99)
    real_should_deploy = ModelMonitor.should_deploy

    def racing_should_deploy(self, challenger_brier, n_oof=None):
        # a concurrent writer deploys first, strictly after this call's
        # prior-artifact hash was already captured
        save_model(concurrent_model, str(model_path))
        return real_should_deploy(self, challenger_brier, n_oof=n_oof)
    monkeypatch.setattr(ModelMonitor, "should_deploy", racing_should_deploy)

    deployed = _deploy_challenger(config, _fitted_gbt(seed=5),
                                  challenger_brier=0.10, extra={},
                                  model_path=str(model_path), n_oof=50)

    assert deployed is False, \
        "a stale-gate race must be refused, not silently deployed"
    on_disk = load_model(str(model_path))
    assert on_disk.importance_ == concurrent_model.importance_, \
        "the concurrent writer's artifact must survive untouched"
    # the stale writer must not have touched the persisted champion baseline
    still = json.loads(state_path.read_text(encoding="utf-8"))
    assert still["monitor"]["champion_brier"] == 0.30


def test_uncontested_deploy_unaffected_by_the_cas_wiring(tmp_path):
    """Sanity: with no race, the same CAS-aware code path still deploys."""
    model_path = tmp_path / "meta_model.json"
    state_path = tmp_path / "state.json"
    _seed_state(state_path, champion_brier=0.30)
    config = {"ml": {"monitor": {}}, "system": {"state_path": str(state_path)}}

    deployed = _deploy_challenger(config, _fitted_gbt(seed=5),
                                  challenger_brier=0.10, extra={},
                                  model_path=str(model_path), n_oof=50)

    assert deployed is True
    updated = json.loads(state_path.read_text(encoding="utf-8"))
    assert updated["monitor"]["champion_brier"] == 0.10


def test_stale_badge_cannot_squat_against_cli_challenger(tmp_path):
    """ML-042 parity for the CLI lane (2026-07-28): the engine's
    auto-retrain rescores the FROZEN champion on the same fresh OOF rows
    before gating (main.py stale-badge guard); the CLI gate compared
    against the RESTORED badge — a birth certificate from an older corpus
    era — so an unbeatable stale badge (0.05 here) could squat forever
    against every honestly-scored CLI challenger. With X/y/oof_idx
    provided, the CLI gate must realign the badge from the on-disk
    champion's own fresh-OOF rescore before deciding."""
    from ml.features import FEATURE_NAMES
    model_path = tmp_path / "meta_model.json"
    state_path = tmp_path / "state.json"
    rng = np.random.default_rng(11)
    # REAL feature width: MetaModelService.reload() enforces the schema/
    # width guard (#17) and refuses narrow artifacts — the realign must be
    # exercised through the honest loader, not around it
    X = rng.normal(size=(200, len(FEATURE_NAMES)))
    y_train = (X[:, 0] > 0).astype(float)
    champ = GradientBoostedStumps(seed=5).fit(X, y_train)
    assert save_model(champ, str(model_path), extra={})
    _seed_state(state_path, champion_brier=0.05)       # unbeatable badge
    config = {"ml": {"monitor": {}}, "system": {"state_path": str(state_path)}}
    y_fresh = 1.0 - y_train              # champion anti-predictive on fresh
    challenger = GradientBoostedStumps(seed=9).fit(X, y_fresh)
    deployed = _deploy_challenger(config, challenger,
                                  challenger_brier=0.20, extra={},
                                  model_path=str(model_path),
                                  n_oof=len(X), X=X, y=y_fresh,
                                  oof_idx=np.arange(len(X)))
    assert deployed is True
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["monitor"]["champion_brier"] == 0.20  # note_deployed won


# ------------------------------------------- 29b stale-state write-back guard
def test_deploy_persists_baseline_onto_fresh_snapshot_not_stale(
        tmp_path, monkeypatch):
    """_deploy_challenger loads state.json at gate time and persists the new
    champion baseline after the deploy. This script is DOCUMENTED to run
    beside a LIVE runner (side-car audit note in train_meta.py), whose 30s
    snapshot cadence can land a newer book strictly inside that window.
    The persistence step must re-read the FRESH snapshot and mutate only
    its 'monitor' section - writing the gate-time copy back publishes a
    stale book as the primary generation: positions closed during the gate
    resurrect and executed fills vanish from balances if the runner dies
    before its next snapshot (exactly what auto_update's taskkill
    escalation does to a wedged runner)."""
    model_path = tmp_path / "meta_model.json"
    state_path = tmp_path / "state.json"
    m = ModelMonitor({})
    m.champion_brier = 0.30
    StateStore(str(state_path)).write_raw(
        {"monitor": m.to_dict(),
         "positions": {"OLD-POS": {"size": 1.0}},
         "cash_balance": 1000.0})
    config = {"ml": {"monitor": {}}, "system": {"state_path": str(state_path)}}

    real_should_deploy = ModelMonitor.should_deploy

    def runner_snapshots_meanwhile(self, challenger_brier, n_oof=None):
        # the live runner writes a NEWER book strictly after this gate's
        # initial load_raw() and before its persistence step
        m2 = ModelMonitor({})
        m2.champion_brier = 0.30
        StateStore(str(state_path)).write_raw(
            {"monitor": m2.to_dict(),
             "positions": {"NEW-POS": {"size": 2.0}},
             "cash_balance": 900.0})
        return real_should_deploy(self, challenger_brier, n_oof=n_oof)
    monkeypatch.setattr(ModelMonitor, "should_deploy",
                        runner_snapshots_meanwhile)

    deployed = _deploy_challenger(config, _fitted_gbt(seed=5),
                                  challenger_brier=0.10, extra={},
                                  model_path=str(model_path), n_oof=50)

    assert deployed is True
    after = json.loads(state_path.read_text(encoding="utf-8"))
    assert after["positions"] == {"NEW-POS": {"size": 2.0}}, \
        "the runner's fresh book was clobbered by the gate-time snapshot"
    assert after["cash_balance"] == 900.0
    assert after["monitor"]["champion_brier"] == 0.10   # baseline still lands


def test_gate_without_oof_context_keeps_restored_badge_behavior(tmp_path):
    # the realign only runs when the caller supplies the OOF context —
    # legacy callers (and failure paths) keep the exact prior behavior
    model_path = tmp_path / "meta_model.json"
    state_path = tmp_path / "state.json"
    _seed_state(state_path, champion_brier=0.05)
    config = {"ml": {"monitor": {}}, "system": {"state_path": str(state_path)}}
    deployed = _deploy_challenger(config, _fitted_gbt(),
                                  challenger_brier=0.20, extra={},
                                  model_path=str(model_path))
    assert deployed is False                            # badge still gates
