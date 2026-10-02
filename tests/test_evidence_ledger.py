"""scripts/evidence_ledger.py - asymmetric evidence rule: the PAST may
eliminate, only the FUTURE may promote."""
import numpy as np
import pytest

from scripts import evidence_ledger as el

DAY = 86400.0


def _series(mean, n=120, block_days=7, start=0.0, seed=1):
    rng = np.random.default_rng(seed)
    t = start + np.arange(n) * block_days * DAY
    return {"t": t.tolist(), "x_bps": [[v] for v in rng.normal(mean, 30, n)],
            "h_hours": [24.0]}


def test_thinning_spaces_blocks_by_the_horizon():
    t = np.arange(10) * 7 * DAY
    idx = el.thin(t, horizon_h=672, block_h=168)          # 28 d horizon, weekly blocks
    assert list(idx) == [0, 5]                            # (block + horizon) / block


def test_past_can_eliminate_but_cannot_promote():
    h = {"id": "x", "horizon_h": 24, "bound_bps": 400, "forward_from": "2030-01-01"}
    strong = el.evaluate(h, _series(+120.0), two_c=45.0)
    assert strong["status"] != "LIVE"                     # all data pre-registration
    assert strong["forward"]["n"] == 0
    dead = el.evaluate(h, _series(0.0), two_c=45.0)
    assert dead["status"] == "ELIMINATED FOR TRIPS"       # history can kill


def test_forward_data_can_promote():
    h = {"id": "x", "horizon_h": 24, "bound_bps": 400, "forward_from": "1970-01-01"}
    r = el.evaluate(h, _series(+120.0), two_c=45.0)
    assert r["status"] == "LIVE"
    assert r["forward"]["db_exist"] >= 13.0


def test_unknown_horizon_is_refused():
    h = {"id": "x", "horizon_h": 5, "bound_bps": 400, "forward_from": "1970-01-01"}
    with pytest.raises(KeyError):
        el.evaluate(h, _series(0.0), two_c=45.0)


def test_registry_is_well_formed_and_unique():
    import json
    from pathlib import Path
    doc = json.loads((Path(__file__).resolve().parents[1] / "docs" / "quant" /
                      "hypothesis_registry.json").read_text(encoding="utf-8"))
    ids = [h["id"] for h in doc["hypotheses"]]
    assert len(ids) == len(set(ids))
    fps = [(h["signal"], h["horizon_h"]) for h in doc["hypotheses"]]
    assert len(fps) == len(set(fps))
    for h in doc["hypotheses"]:
        assert h["source"] in ("literature", "bot", "llm")
        assert h["forward_from"] >= h["registered_at"] or h["source"] == "bot"
        assert h["bound_bps"] > 0 and h["horizon_h"] > 0


def test_tilt_is_judged_against_zero_not_the_round_trip():
    h = {"id": "g", "horizon_h": 24, "bound_bps": 400, "forward_from": "1970-01-01",
         "use": "tilt"}
    r = el.evaluate(h, _series(+20.0, n=400), two_c=45.0)
    assert r["status"] in ("LIVE", "UNDECIDED")           # +20 bps is a real tilt edge
    assert not r["status"].startswith("ELIMINATED")


def test_elimination_is_sticky_once_crossed():
    """Ville: deciding at the FIRST crossing is valid; a later decay of the
    wealth must not un-eliminate."""
    h = {"id": "x", "horizon_h": 24, "bound_bps": 400, "forward_from": "2030-01-01"}
    early = _series(0.0, n=150, seed=4)
    late = _series(+400.0, n=150, seed=5, start=150 * 7 * DAY)
    both = {"t": early["t"] + late["t"], "x_bps": early["x_bps"] + late["x_bps"],
            "h_hours": [24.0]}
    assert el.evaluate(h, both, two_c=45.0)["status"] == "ELIMINATED FOR TRIPS"


def test_e_bh_demotion_keeps_the_elimination():
    rows = [{"id": "a", "family": "f", "forward": {"e_exist": 25.0}, "e_dead_used": 30.0,
             "status": "EDGE BELOW ROUND TRIP", "use": "trip"},
            {"id": "b", "family": "f", "forward": {"e_exist": 1.0}, "e_dead_used": 1.0,
             "status": "UNDECIDED", "use": "trip"},
            {"id": "c", "family": "f", "forward": {"e_exist": 1.0}, "e_dead_used": 1.0,
             "status": "UNDECIDED", "use": "trip"}]
    el.apply_e_bh(rows)
    assert rows[0]["status"] == "ELIMINATED FOR TRIPS"


def test_write_status_never_un_eliminates():
    reg = [{"id": "a", "status": "ELIMINATED FOR TRIPS"}, {"id": "b", "status": "UNDECIDED"}]
    el.merge_status(reg, {"a": "UNDECIDED", "b": "ELIMINATED FOR TRIPS"})
    assert [h["status"] for h in reg] == ["ELIMINATED FOR TRIPS", "ELIMINATED FOR TRIPS"]
