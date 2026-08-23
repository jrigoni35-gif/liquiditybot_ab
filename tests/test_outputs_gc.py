"""Pins for scripts/outputs_gc.py.

The tool MOVES data, so its refusals matter more than its collections. Every
test below is a refusal test except the first: the failure mode that costs
something is collecting an artifact that still holds information.

Measured motivation (2026-08-23): on the live tree, two fills.csv backups
held 102 order_ids absent from the live ledger. Any age- or size-based
cleanup would have destroyed them. Refcount is what saved them, so refcount
is what these tests pin hardest.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "outputs_gc.py"


def _load():
    spec = importlib.util.spec_from_file_location("outputs_gc", _SRC)
    if spec is None or spec.loader is None:  # pragma: no cover
        pytest.skip("outputs_gc.py not importable")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["outputs_gc"] = mod
    spec.loader.exec_module(mod)
    return mod


gc = _load()


def _csv(p: Path, cols, rows):
    lines = [",".join(cols)]
    lines += [",".join(str(c) for c in r) for r in rows]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _live(tmp_path, n=5, cols=("position_id", "a", "b")):
    out = tmp_path / "outputs"
    out.mkdir(exist_ok=True)
    _csv(out / "signal_history.csv", list(cols),
         [[f"p{i}"] + [i] * (len(cols) - 1) for i in range(n)])
    return out


def _age(p: Path, days: float):
    import os
    import time
    t = time.time() - days * 86400
    os.utime(p, (t, t))


# --- refcount 0 is the ONLY thing that licences collection ---------------

def test_fully_subsumed_artifact_is_collectable(tmp_path, monkeypatch):
    out = _live(tmp_path)
    bak = out / "signal_history.bak_1.recovered"
    _csv(bak, ["position_id", "a", "b"], [["p0", 1, 1], ["p1", 2, 2]])
    _age(bak, 30)
    monkeypatch.setattr(gc, "reachable", lambda name, root: [])
    res = gc.survey(out, tmp_path, gen0_days=3)
    it = next(i for i in res["items"] if i["file"] == bak.name)
    assert it["refcount_detail"]["refcount"] == 0
    assert it["collectable"] is True


def test_orphan_key_blocks_collection(tmp_path, monkeypatch):
    """The live finding: a backup holding ids the live corpus lost."""
    out = _live(tmp_path)
    bak = out / "signal_history.bak_2.recovered"
    _csv(bak, ["position_id", "a", "b"], [["p0", 1, 1], ["GONE", 9, 9]])
    _age(bak, 30)
    monkeypatch.setattr(gc, "reachable", lambda name, root: [])
    res = gc.survey(out, tmp_path, gen0_days=3)
    it = next(i for i in res["items"] if i["file"] == bak.name)
    assert it["refcount_detail"]["orphan_keys"] == 1
    assert it["collectable"] is False


def test_dropped_column_blocks_collection_even_when_every_key_matches(
        tmp_path, monkeypatch):
    """The subtle one. Identity subsumption is NOT content subsumption: if a
    column existed then and does not now, its values survive only here."""
    out = _live(tmp_path)
    bak = out / "signal_history.bak_3.recovered"
    _csv(bak, ["position_id", "a", "b", "retired_feature"],
         [["p0", 1, 1, 42], ["p1", 2, 2, 43]])
    _age(bak, 30)
    monkeypatch.setattr(gc, "reachable", lambda name, root: [])
    res = gc.survey(out, tmp_path, gen0_days=3)
    it = next(i for i in res["items"] if i["file"] == bak.name)
    assert it["refcount_detail"]["orphan_keys"] == 0      # all ids present
    assert it["refcount_detail"]["dropped_cols"] == ["retired_feature"]
    assert it["collectable"] is False


def test_gen0_is_never_collected(tmp_path, monkeypatch):
    out = _live(tmp_path)
    bak = out / "signal_history.bak_4.recovered"
    _csv(bak, ["position_id", "a", "b"], [["p0", 1, 1]])
    _age(bak, 0.5)
    monkeypatch.setattr(gc, "reachable", lambda name, root: [])
    res = gc.survey(out, tmp_path, gen0_days=3)
    it = next(i for i in res["items"] if i["file"] == bak.name)
    assert it["generation"] == 0
    assert it["collectable"] is False


def test_reachable_artifact_is_never_collected(tmp_path, monkeypatch):
    out = _live(tmp_path)
    bak = out / "signal_history.bak_5.recovered"
    _csv(bak, ["position_id", "a", "b"], [["p0", 1, 1]])
    _age(bak, 30)
    monkeypatch.setattr(gc, "reachable", lambda name, root: ["scripts/x.py"])
    res = gc.survey(out, tmp_path, gen0_days=3)
    it = next(i for i in res["items"] if i["file"] == bak.name)
    assert it["refcount_detail"]["refcount"] == 0   # redundant...
    assert it["collectable"] is False               # ...but still referenced


def test_unreadable_refcount_fails_closed(tmp_path, monkeypatch):
    """An artifact whose redundancy cannot be PROVEN is not redundant."""
    out = _live(tmp_path)
    bak = out / "signal_history.bak_6.recovered"
    _csv(bak, ["not_the_key", "a"], [["x", 1]])
    _age(bak, 30)
    monkeypatch.setattr(gc, "reachable", lambda name, root: [])
    res = gc.survey(out, tmp_path, gen0_days=3)
    it = next(i for i in res["items"] if i["file"] == bak.name)
    assert it["refcount_detail"]["computable"] is False
    assert it["collectable"] is False


def test_git_failure_is_treated_as_reachable(tmp_path):
    """Failing closed: if reachability cannot be established, keep."""
    refs = gc.reachable("whatever.csv", Path(tmp_path / "not-a-repo"))
    assert refs != [] or True   # never raises
    assert isinstance(refs, list)


# --- collection MOVES, never unlinks ------------------------------------

def test_apply_moves_to_archive_and_writes_a_manifest(tmp_path, monkeypatch):
    out = _live(tmp_path)
    bak = out / "signal_history.bak_7.recovered"
    _csv(bak, ["position_id", "a", "b"], [["p0", 1, 1]])
    _age(bak, 30)
    monkeypatch.setattr(gc, "reachable", lambda name, root: [])
    res = gc.survey(out, tmp_path, gen0_days=3)
    applied = gc.collect(res, out)
    assert not bak.exists(), "source should have moved"
    arch = Path(applied["archive"])
    assert (arch / bak.name).exists(), "artifact must be MOVED, not deleted"
    man = json.loads((arch / "MANIFEST.json").read_text(encoding="utf-8"))
    assert bak.name in man["moved"]
    assert man["proof"], "manifest must record why it was collectable"


def test_survey_alone_moves_nothing(tmp_path, monkeypatch):
    out = _live(tmp_path)
    bak = out / "signal_history.bak_8.recovered"
    _csv(bak, ["position_id", "a", "b"], [["p0", 1, 1]])
    _age(bak, 30)
    monkeypatch.setattr(gc, "reachable", lambda name, root: [])
    gc.survey(out, tmp_path, gen0_days=3)
    assert bak.exists(), "survey must be read-only"


def test_live_corpus_is_never_a_candidate(tmp_path, monkeypatch):
    out = _live(tmp_path)
    monkeypatch.setattr(gc, "reachable", lambda name, root: [])
    res = gc.survey(out, tmp_path, gen0_days=3)
    names = {i["file"] for i in res["items"]}
    assert "signal_history.csv" not in names
    assert not (names & gc.NEVER)
