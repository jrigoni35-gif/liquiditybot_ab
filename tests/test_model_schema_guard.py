"""
tests/test_model_schema_guard.py

A meta-model artifact left behind by a feature-schema bump must be REJECTED
at load (ML-013), not loaded and then faulted on every inference.

Regression for a live incident: a machine pulled v6 code but kept a
43-feature v1 outputs/meta_model.json. Every p_win() raised
    ValueError: operands could not be broadcast together (1,58) (43,)
and silently fell back to the 0.56 cold-start prior — the model was dead
weight, AND the cold-start retrain gate never fired because a champion
looked "present". The loader now rejects a width/schema-mismatched champion
so the service drops to a clean prior and the retrain gate cold-starts.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from ml.contracts import SCHEMA_VERSION
from ml.features import FEATURE_NAMES
from ml.meta_model import MetaModelService
from ml.models import (EnsembleMLP, GradientBoostedStumps, LogisticModel,
                       save_model)

N = len(FEATURE_NAMES)          # current schema width


def _fit(model, n_feat, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(80, n_feat))
    y = (X[:, 0] + rng.normal(scale=0.5, size=80) > 0).astype(float)
    return model.fit(X, y)


def _write_artifact(path: Path, model, *, schema=None):
    """Write the artifact JSON directly (NOT via save_model), so it is
    unregistered — verify() returns ok=None and the integrity gate passes,
    isolating the schema gate under test."""
    d = model.to_dict()
    if schema is not None:
        d["feature_schema_version"] = schema
    path.write_text(json.dumps(d), encoding="utf-8")


def _svc(path: Path) -> MetaModelService:
    return MetaModelService({"model_path": str(path),
                             "cold_start_prior_p": 0.56})


def test_n_features_reports_training_width():
    assert _fit(LogisticModel(), 12).n_features == 12
    assert _fit(EnsembleMLP(k=2, epochs=40), 9).n_features == 9
    assert _fit(GradientBoostedStumps(n_estimators=30), 7).n_features == 7


def test_current_width_model_loads(tmp_path):
    _write_artifact(tmp_path / "m.json", _fit(EnsembleMLP(k=2, epochs=40), N))
    assert _svc(tmp_path / "m.json").trained is True


def test_legacy_wrong_width_champion_rejected(tmp_path):
    # the exact incident: an UNSTAMPED artifact of the wrong width
    _write_artifact(tmp_path / "m.json", _fit(EnsembleMLP(k=2, epochs=40), N - 5))
    svc = _svc(tmp_path / "m.json")
    assert svc.trained is False
    assert svc.model_id == ""
    # p_win degrades to the configured prior and NEVER raises
    assert svc.p_win(np.zeros(N), 1.0) == pytest.approx(0.56)


def test_stamped_old_schema_rejected_even_when_width_ok(tmp_path):
    # kind-agnostic path: correct width, but an older stamped schema version
    _write_artifact(tmp_path / "m.json",
                    _fit(GradientBoostedStumps(n_estimators=30), N),
                    schema=SCHEMA_VERSION - 1)
    assert _svc(tmp_path / "m.json").trained is False


def test_gbt_width_survives_roundtrip():
    from ml.models import load_model
    import tempfile
    m = _fit(GradientBoostedStumps(n_estimators=30), N)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "g.json"
        p.write_text(json.dumps(m.to_dict()), encoding="utf-8")
        assert load_model(str(p)).n_features == N


def test_save_model_stamps_current_schema(tmp_path):
    save_model(_fit(GradientBoostedStumps(n_estimators=30), N),
               str(tmp_path / "m.json"))
    d = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert d["feature_schema_version"] == SCHEMA_VERSION
