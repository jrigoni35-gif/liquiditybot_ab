"""Regressions for the train->save->register->load pipeline, caught by
actually RUNNING train_meta (not by static review):

1. train_meta's extra metadata used the key "importance", overwriting the gbt
   model's internal per-feature dict with a list -> from_dict crashed on
   .items() and the bot could not load the model it had just trained.
2. Registry pedigree was keyed on raw path strings: registered with forward
   slashes, verified with str(Path()) backslashes on Windows -> every model
   loaded as "unknown provenance".
"""
import json

import numpy as np

from ml.models import GradientBoostedStumps, load_model, save_model
from ml.registry import ModelRegistry


def _fitted_gbt():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(120, 4))
    y = (X[:, 0] + 0.3 * rng.normal(size=120) > 0).astype(float)
    return GradientBoostedStumps(seed=3).fit(X, y)


def test_list_importance_in_artifact_does_not_block_load(tmp_path):
    path = tmp_path / "m.json"
    save_model(_fitted_gbt(), str(path),
               extra={"wf_importance": [("f0", 0.1)]})
    m = load_model(str(path))
    assert m is not None and m.kind == "gbt"
    # simulate the OLD clobbered artifact: importance replaced by a list
    d = json.loads(path.read_text(encoding="utf-8"))
    d["importance"] = [["f0", 0.1], ["f1", 0.0]]
    path.write_text(json.dumps(d), encoding="utf-8")
    m2 = load_model(str(path))          # must tolerate, not crash
    assert isinstance(m2, GradientBoostedStumps)
    assert m2.importance_ == {}


def test_wf_importance_key_does_not_clobber_model_importance(tmp_path):
    path = tmp_path / "m.json"
    model = _fitted_gbt()
    save_model(model, str(path), extra={"wf_importance": [("f0", 0.1)]})
    d = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(d["importance"], dict)        # model's own, intact
    assert d["wf_importance"] == [["f0", 0.1]]      # walkforward's, separate


def test_deploy_seam_rejection_is_retried_not_permanent(tmp_path,
                                                        monkeypatch):
    """save_model publishes the artifact and appends its ledger row a beat
    LATER; a reload landing in that gap verifies new bytes against the
    previous champion's row and rejects a good model as tampered (ML-011).
    Because _loaded_mtime is stamped before the verify, reload_if_changed
    then never retries — a millisecond race becomes a persistent model
    outage. Rejection must un-stamp the mtime so the next cycle re-reads:
    the race heals, a genuine tamper simply re-rejects."""
    import ml.meta_model as mm
    from ml.features import FEATURE_NAMES

    # REAL feature width: reload()'s schema gate (ML-013) rejects a narrow
    # artifact before the integrity result matters, so the retry must be
    # exercised through an honestly-shaped model
    rng = np.random.default_rng(7)
    X = rng.normal(size=(160, len(FEATURE_NAMES)))
    y = (X[:, 0] + 0.3 * rng.normal(size=160) > 0).astype(float)
    wide = GradientBoostedStumps(seed=7).fit(X, y)

    path = tmp_path / "meta_model.json"
    save_model(wide, str(path), extra={})
    svc = mm.MetaModelService({"model_path": str(path)})

    calls = {"n": 0}
    real_verify = mm.get_registry().verify

    def flaky_verify(p):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"ok": False}          # the deploy-seam gap
        return real_verify(p)
    monkeypatch.setattr(mm.get_registry(), "verify", flaky_verify)

    svc.reload()
    assert svc.model is None              # rejected, cold-start prior
    assert svc._loaded_mtime == 0.0, \
        "a rejected artifact must not pin the mtime, or it is never retried"
    svc.reload_if_changed()               # next cycle: ledger row has landed
    assert svc.model is not None, "the deploy-seam race must self-heal"


def test_registry_pedigree_survives_path_separator_mismatch(tmp_path):
    reg = ModelRegistry(str(tmp_path / "reg"))
    art = tmp_path / "outputs" / "meta_model.json"
    art.parent.mkdir(parents=True)
    art.write_text('{"kind": "gbt"}', encoding="utf-8")
    posix = str(art).replace("\\", "/")
    win = str(art).replace("/", "\\")
    reg.register(posix, {"kind": "gbt"})
    v = reg.verify(win)                 # opposite separator style
    assert v["ok"] is True              # pedigree found, hash matches
    art.write_text('{"kind": "tampered"}', encoding="utf-8")
    assert reg.verify(win)["ok"] is False   # tamper still detected
