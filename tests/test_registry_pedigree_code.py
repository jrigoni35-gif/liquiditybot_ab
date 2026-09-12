"""ML-060 meant two opposite things, and neither reached the tally.

`core/codes.Code.ML_REGISTERED = "ML-060"` is documented as "artifact
registered". `ml/registry.py` was ALSO emitting the literal "ML-060" for the
OPPOSITE event - an artifact loaded with no registry row at all. Any frequency
tally over ML-060 therefore summed "has a pedigree" with "has none", which makes
the one question a provenance gate exists to answer unanswerable.

Both sites also used the Python logger rather than the audit, so neither bumped
core/code_stats - the central {code: count} ledger that status.json by_prefix
and the exported liquiditybot_code_count read. A provenance warning nobody
aggregates cannot surface "the champion has loaded with unknown provenance for
three weeks".
"""
from __future__ import annotations

import json
from pathlib import Path

from core import code_stats
from core.codes import Code

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_the_two_events_have_separate_codes():
    assert Code.ML_REGISTERED.value == "ML-060"
    assert Code.ML_NO_PEDIGREE.value == "ML-061"
    assert Code.ML_REGISTERED != Code.ML_NO_PEDIGREE


def test_registry_no_longer_emits_ML_060_for_the_opposite_event():
    """Source pin: the unknown-provenance branch must not carry the code that
    means `registered`."""
    src = (REPO_ROOT / "ml" / "registry.py").read_text(encoding="utf-8")
    line = [ln for ln in src.splitlines()
            if "has no registry pedigree" in ln]
    assert line, "the unknown-provenance warning vanished"
    assert all("ML-060" not in ln for ln in line), (
        "ml/registry.py still emits ML-060 (which means 'registered') for an "
        "artifact that has NO pedigree")
    assert any("ML-061" in ln for ln in line)


def test_an_unregistered_artifact_bumps_the_central_tally(tmp_path):
    """INJECTION, not inspection: verify an artifact with no ledger row and
    assert the count actually moved."""
    from ml.registry import ModelRegistry

    art = tmp_path / "model.json"
    art.write_text(json.dumps({"hand": "trained"}), encoding="utf-8")
    reg = ModelRegistry(str(tmp_path / "models"))

    before = code_stats.snapshot().get("ML-061", 0)
    res = reg.verify(str(art))
    after = code_stats.snapshot().get("ML-061", 0)

    assert res["ok"] is None, "an unregistered artifact must verify as unknown"
    assert after == before + 1, (
        "unknown provenance did not reach core/code_stats, so it stays a log "
        "line nobody can aggregate")


def test_unknown_provenance_still_LOADS(tmp_path):
    """The deliberate design is preserved: unknown provenance is reported, not
    blocked, so a hand-trained model still loads. This is not a fail-closed
    change and must not become one by accident."""
    from ml.registry import ModelRegistry

    art = tmp_path / "m.json"
    art.write_text("{}", encoding="utf-8")
    res = ModelRegistry(str(tmp_path / "models")).verify(str(art))
    assert res["ok"] is None          # not False - it is not a rejection
    assert "sha256" in res
