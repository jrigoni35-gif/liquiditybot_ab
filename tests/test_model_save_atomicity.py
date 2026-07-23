"""W2-2: model artifact write is non-atomic and unlocked across two racing
writers.

save_model() used plain open(path, "w") + json.dump: no temp+rename, so a
crash/exception mid-write truncates the destination FIRST and can leave a
torn, unparseable artifact behind - overwriting a perfectly good champion
with garbage. It also had no guard against two independent writers (the
runner's in-process auto-retrain vs a CLI scripts/train_meta.py run)
racing a deploy: both gate a challenger against the CURRENT champion, and
whichever finishes last silently clobbers the other's already-deployed
artifact with a decision made against a champion that no longer exists on
disk.

(a) atomicity: a raise mid-write must never corrupt a pre-existing artifact.
(b) stale-gate CAS: save_model(..., expect_prior_sha256=...) must refuse a
    write when the on-disk artifact changed since the caller's gate read.
"""
import json

import numpy as np
import pytest

import ml.models as models
from ml.models import GradientBoostedStumps, LogisticModel, load_model, save_model
from ml.registry import sha256_file


def _fit_logistic(seed=1):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(80, 4))
    y = (X[:, 0] > 0).astype(float)
    return LogisticModel(seed=seed).fit(X, y)


def _fit_gbt(seed=1):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(80, 4))
    y = (X[:, 0] > 0).astype(float)
    return GradientBoostedStumps(n_estimators=20, seed=seed).fit(X, y)


# --------------------------------------------------------------- (a) atomic
def test_crash_mid_write_never_corrupts_the_existing_artifact(tmp_path, monkeypatch):
    path = tmp_path / "meta_model.json"
    save_model(_fit_logistic(seed=1), str(path))
    good_bytes = path.read_bytes()
    json.loads(good_bytes)                       # sanity: it's valid JSON

    def torn_dump(_d, f, *a, **k):
        f.write('{"partial": true')               # simulate a crash mid-write
        raise RuntimeError("simulated crash mid-write")
    monkeypatch.setattr(models.json, "dump", torn_dump)

    with pytest.raises(RuntimeError):
        save_model(_fit_logistic(seed=2), str(path))

    # the PRE-EXISTING artifact must be untouched: never truncated, never torn
    assert path.read_bytes() == good_bytes, \
        "a failed write corrupted the pre-existing artifact"
    json.loads(path.read_text(encoding="utf-8"))   # still parses


def test_no_leftover_state_after_a_clean_save(tmp_path):
    path = tmp_path / "meta_model.json"
    save_model(_fit_logistic(seed=1), str(path))
    # only the real artifact exists - no stray tmp files from the atomic write
    leftovers = [p for p in tmp_path.iterdir() if p != path]
    assert leftovers == [], f"stray files left behind: {leftovers}"


# ----------------------------------------------------------- (b) stale-gate CAS
def test_cas_refuses_write_when_artifact_changed_since_gate_read(tmp_path):
    path = tmp_path / "meta_model.json"
    save_model(_fit_logistic(seed=1), str(path))
    prior_hash = sha256_file(str(path))            # what the stale writer's gate read

    # a concurrent writer deploys FIRST, changing the on-disk artifact
    save_model(_fit_gbt(seed=2), str(path))
    hash_after_concurrent = sha256_file(str(path))
    assert hash_after_concurrent != prior_hash

    # the stale writer now tries to save the challenger it gated against the
    # OLD (pre-race) artifact
    ok = save_model(_fit_logistic(seed=3), str(path),
                    expect_prior_sha256=prior_hash)

    assert ok is False, "a stale gate must be refused, not silently applied"
    assert sha256_file(str(path)) == hash_after_concurrent, \
        "the concurrent writer's artifact must survive, not be clobbered"


def test_cas_allows_write_when_artifact_unchanged_since_gate_read(tmp_path):
    path = tmp_path / "meta_model.json"
    save_model(_fit_logistic(seed=1), str(path))
    prior_hash = sha256_file(str(path))

    ok = save_model(_fit_logistic(seed=2), str(path),
                    expect_prior_sha256=prior_hash)

    assert ok is True
    assert sha256_file(str(path)) != prior_hash    # the new model is live
    assert load_model(str(path)) is not None


def test_cas_cold_start_expects_no_prior_artifact(tmp_path):
    path = tmp_path / "meta_model.json"
    # a concurrent writer already deployed a cold-start champion
    save_model(_fit_logistic(seed=9), str(path))

    ok = save_model(_fit_logistic(seed=1), str(path), expect_prior_sha256=None)

    assert ok is False, \
        "a gate that read 'no champion exists' must refuse once a " \
        "concurrent writer has already created one"


def test_cas_cold_start_succeeds_when_truly_no_prior_artifact(tmp_path):
    path = tmp_path / "meta_model.json"        # never written
    ok = save_model(_fit_logistic(seed=1), str(path), expect_prior_sha256=None)
    assert ok is True
    assert load_model(str(path)) is not None


def test_omitting_the_cas_param_skips_the_check_entirely(tmp_path):
    """Backward compatibility: existing single-writer callers that never
    pass expect_prior_sha256 must be unaffected."""
    path = tmp_path / "meta_model.json"
    save_model(_fit_logistic(seed=1), str(path))
    ok = save_model(_fit_logistic(seed=2), str(path))   # no CAS param at all
    assert ok is True
