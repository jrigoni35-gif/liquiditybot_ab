"""tests/test_external_retrain_adopt.py — a LIVE bot adopts an EXTERNAL retrain.

scripts/train_meta.py run against a running bot writes outputs/meta_model.json
and a champion_brier into state.json that the bot's next snapshot then clobbers
— so the offline deploy never reached the running engine and the baseline
reverted. MetaModelService.reload_if_changed() lets the engine detect the
changed artifact, reload it, and expose its own oof_brier so the caller realigns
the champion baseline. The bot's OWN in-process retrain calls reload() directly
(re-stamping the mtime), so this never double-fires for it.
"""
import json
import os
from pathlib import Path

import numpy as np

from ml.contracts import SCHEMA_VERSION, get_contract
from ml.meta_model import MetaModelService
from ml.models import GradientBoostedStumps


def _fit(n_features, seed=1):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(200, n_features))
    y = (X[:, 0] > 0).astype(float)
    return GradientBoostedStumps(seed=seed).fit(X, y)


def _artifact(path: Path, model, oof_brier, schema=SCHEMA_VERSION):
    """Write the artifact JSON directly (unregistered -> integrity gate passes,
    isolating reload/schema behavior)."""
    d = model.to_dict()
    d["feature_schema_version"] = schema
    if oof_brier is not None:
        d["oof_brier"] = oof_brier
    path.write_text(json.dumps(d), encoding="utf-8")


def _svc(path: Path):
    return MetaModelService({"model_path": str(path)})


def test_reads_oof_brier_and_is_stable_when_unchanged(tmp_path):
    p = tmp_path / "m.json"
    _artifact(p, _fit(get_contract().n), oof_brier=0.181)
    svc = _svc(p)
    assert svc.trained is True and svc.oof_brier == 0.181
    assert svc.reload_if_changed() is False        # nothing changed on disk


def test_picks_up_an_external_retrain_and_new_brier(tmp_path):
    p = tmp_path / "m.json"
    _artifact(p, _fit(get_contract().n, seed=1), oof_brier=0.181)
    svc = _svc(p)
    base = svc._loaded_mtime
    # external retrain rewrites the artifact with a better brier
    _artifact(p, _fit(get_contract().n, seed=2), oof_brier=0.150)
    os.utime(p, (base + 10, base + 10))            # guarantee a newer mtime
    assert svc.reload_if_changed() is True
    assert svc.trained is True and svc.oof_brier == 0.150


def test_rejected_external_model_is_detected_but_not_adopted(tmp_path):
    p = tmp_path / "m.json"
    _artifact(p, _fit(get_contract().n), oof_brier=0.181)
    svc = _svc(p)
    base = svc._loaded_mtime
    # a wrong-WIDTH model change: detected, reloaded, but rejected by the width
    # gate -> not trained, no brier to adopt (the main.py hook checks both)
    _artifact(p, _fit(get_contract().n - 5), oof_brier=0.10)
    os.utime(p, (base + 10, base + 10))
    assert svc.reload_if_changed() is True         # change WAS detected
    assert svc.trained is False and svc.oof_brier is None


def test_own_reload_restamps_mtime_so_no_double_fire(tmp_path):
    # the bot's in-process retrain calls reload() itself; a following
    # reload_if_changed must NOT re-fire on the same file
    p = tmp_path / "m.json"
    _artifact(p, _fit(get_contract().n), oof_brier=0.181)
    svc = _svc(p)
    svc.reload()                                   # simulate the in-process path
    assert svc.reload_if_changed() is False
