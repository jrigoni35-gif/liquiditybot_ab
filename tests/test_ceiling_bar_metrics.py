"""Ceiling-vs-bar telemetry (2026-08-31): the moving-property watch behind
the era-6 structural-closure finding. Pins: (1) the bar comes from the REAL
PositionSizer, never a copied formula; (2) a planted closed-world (max knot
shrunk below the bar) exports a NEGATIVE margin; (3) missing inputs degrade
to [] — absent, never fabricated."""
import json

import scripts.gc_pusher as gp


def _plant(tmp_path, ymax, shrink, monkeypatch):
    cfg = json.loads((gp._REPO_ROOT / "config.json").read_text("utf-8"))
    (tmp_path / "config.json").write_text(json.dumps(cfg), "utf-8")
    (tmp_path / "meta.json").write_text(
        json.dumps({"calibration": {"x": [0.0, 1.0], "y": [0.1, ymax]}}),
        "utf-8")
    (tmp_path / "status.json").write_text(
        json.dumps({"monitor": {"shrinkage": shrink}}), "utf-8")
    monkeypatch.setattr(gp, "CEILING_CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(gp, "META_MODEL_PATH", tmp_path / "meta.json")
    monkeypatch.setattr(gp, "CEILING_STATUS_PATH", tmp_path / "status.json")


def _by_name(metrics):
    # real OTLP gauge shape: value lives at gauge.dataPoints[0].asDouble
    return {m["name"]: m["gauge"]["dataPoints"][0]["asDouble"]
            for m in metrics}


def test_planted_closed_world_exports_negative_margin(tmp_path, monkeypatch):
    # ymax 0.60, shrink 0.5 -> ceiling 0.55, far under any derived bar.
    _plant(tmp_path, ymax=0.60, shrink=0.5, monkeypatch=monkeypatch)
    got = _by_name(gp._ceiling_bar_metrics(0.0))
    assert set(got) == {"liquiditybot_p_entry_bar",
                        "liquiditybot_p_ceiling_theoretical",
                        "liquiditybot_p_ceiling_margin"}
    assert got["liquiditybot_p_ceiling_theoretical"] == \
        0.5 + (0.60 - 0.5) * 0.5
    assert got["liquiditybot_p_ceiling_margin"] < 0.0, \
        "a closed world must read as closed"


def test_bar_matches_the_real_sizer_not_a_copy(tmp_path, monkeypatch):
    _plant(tmp_path, ymax=0.98, shrink=0.0, monkeypatch=monkeypatch)
    from risk.position_sizer import PositionSizer
    cfg = json.loads((gp._REPO_ROOT / "config.json").read_text("utf-8"))
    want = PositionSizer(cfg.get("position_sizer", {}),
                         cfg.get("profit_taking", {}),
                         cfg.get("risk", {}),
                         pretrade_cfg=cfg.get("pretrade", {}),
                         capital_cfg=cfg.get("capital_management", {})
                         ).p_bar_base
    got = _by_name(gp._ceiling_bar_metrics(0.0))
    assert got["liquiditybot_p_entry_bar"] == float(want)


def test_missing_meta_degrades_to_empty_never_fabricates(tmp_path,
                                                         monkeypatch):
    _plant(tmp_path, ymax=0.98, shrink=0.0, monkeypatch=monkeypatch)
    monkeypatch.setattr(gp, "META_MODEL_PATH", tmp_path / "absent.json")
    assert gp._ceiling_bar_metrics(0.0) == []


def test_empty_knots_degrade_to_empty(tmp_path, monkeypatch):
    _plant(tmp_path, ymax=0.98, shrink=0.0, monkeypatch=monkeypatch)
    (tmp_path / "meta.json").write_text(
        json.dumps({"calibration": {"x": [], "y": []}}), "utf-8")
    assert gp._ceiling_bar_metrics(0.0) == []
