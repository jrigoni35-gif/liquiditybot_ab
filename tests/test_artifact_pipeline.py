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
