"""Evidence-gated model selection: the "don't try to learn every way when
there's no chance" rule. A higher-capacity family (gbt/blend/mlp/
adaptive_gbt) is trained and entered into selection ONLY when the LIVE
(ground-truth) label count and the TOTAL row count clear its floors.
logistic - the linear baseline - is always admissible. The gate is mirrored
in the PBO harness so OF-3 measures the space the bot actually selects from.
"""
import numpy as np
import pytest

from core.config_guard import validate
from ml.overfit import model_space_pbo
from ml.walkforward import (admissible_families, evaluate_and_select,
                            pbo_family)

_CFG = {"enabled": True,
        "min_live_rows": {"gbt": 60, "blend": 60, "mlp": 150,
                          "adaptive_gbt": 250},
        "min_total_rows": {"gbt": 150, "blend": 150, "mlp": 400,
                           "adaptive_gbt": 600}}


def _data(n=500, seed=1):
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, (n, 6))
    # a learnable-but-weak signal so folds are non-degenerate both classes
    y = (X[:, 0] + rng.normal(0, 1.5, n) > 0).astype(float)
    return X, y


# --- admissible_families ---------------------------------------------------
def test_logistic_always_admitted_even_at_zero_evidence():
    adm = admissible_families(0, 0, _CFG)
    assert adm == {"logistic"}


def test_no_gating_when_disabled_or_absent():
    everything = {"logistic", "gbt", "blend", "mlp", "adaptive_gbt"}
    assert admissible_families(0, 0, None) == everything
    assert admissible_families(0, 0, {"enabled": False}) == everything


def test_families_admit_in_evidence_order():
    # 35 live (today's corpus): logistic only
    assert admissible_families(35, 1401, _CFG) == {"logistic"}
    # 60 live, 150 total: gbt + blend join
    assert admissible_families(60, 150, _CFG) == {"logistic", "gbt", "blend"}
    # 150 live but only 200 total: mlp's TOTAL floor (400) still blocks it
    assert admissible_families(150, 200, _CFG) == {"logistic", "gbt", "blend"}
    # 150 live, 400 total: mlp joins
    assert "mlp" in admissible_families(150, 400, _CFG)
    # 250 live, 600 total: everything
    assert admissible_families(250, 600, _CFG) == {
        "logistic", "gbt", "blend", "mlp", "adaptive_gbt"}


def test_pbo_family_maps_variants():
    assert pbo_family("logistic") == "logistic"
    assert pbo_family("gbt_d3_lr10") == "gbt"
    assert pbo_family("mlp_small") == "mlp"
    assert pbo_family("adaptive_gbt") == "adaptive_gbt"


# --- evaluate_and_select ---------------------------------------------------
def test_selection_gated_to_logistic_at_low_live_count():
    X, y = _data()
    res = evaluate_and_select(X, y, n_splits=4, n_live=35, select_cfg=_CFG,
                              extra_models=("adaptive_gbt",))
    assert res["admitted"] == ["logistic"]
    assert set(res["gated"]) == {"gbt", "blend", "mlp", "adaptive_gbt"}
    assert res["selected"] == "logistic"            # nothing else was trained
    assert "gbt" not in res                          # never scored


def test_selection_ungated_trains_full_ladder():
    X, y = _data(n=700)                # >= 600 total so adaptive_gbt's floor clears
    res = evaluate_and_select(X, y, n_splits=4, n_live=300, select_cfg=_CFG,
                              extra_models=("adaptive_gbt",))
    assert res["gated"] == []
    for fam in ("logistic", "gbt", "blend", "mlp", "adaptive_gbt"):
        assert fam in res["admitted"] and fam in res


def test_no_gate_params_reproduces_historical_ladder():
    X, y = _data()
    res = evaluate_and_select(X, y, n_splits=4)      # no n_live/select_cfg
    assert res["gated"] == []
    assert "gbt" in res["admitted"]


# --- PBO mirror ------------------------------------------------------------
def test_pbo_reports_no_selection_when_gated_to_one_family():
    X, y = _data()
    pb = model_space_pbo(X, y, n_splits=4, n_live=35, select_cfg=_CFG)
    assert pb["pbo"] is None
    assert pb["n_configs"] == 1 and pb["configs"] == ["logistic"]
    assert "no model selection" in pb["reason"]


def test_pbo_measures_full_space_when_ungated():
    X, y = _data(n=700)
    pb = model_space_pbo(X, y, n_splits=4, n_live=300, select_cfg=_CFG)
    assert pb["n_configs"] > 1                        # real selection space


# --- config_guard ----------------------------------------------------------
def _base_ok_ml():
    # minimal config the guard can chew on; only model_selection matters here
    return {"system": {"dry_run": True},
            "ml": {"model_selection": {
                "enabled": True,
                "min_live_rows": {"gbt": 60, "mlp": 150},
                "min_total_rows": {"gbt": 150, "mlp": 400}}}}


def _fatals(cfg):
    return [m for s, m in validate(cfg) if s == "FATAL"
            and "model_selection" in m]


def test_guard_accepts_monotonic_floors():
    assert _fatals(_base_ok_ml()) == []


def test_guard_rejects_nonmonotonic_live_floor():
    cfg = _base_ok_ml()
    cfg["ml"]["model_selection"]["min_live_rows"] = {"gbt": 200, "mlp": 50}
    assert _fatals(cfg)                               # mlp < gbt: incoherent


def test_guard_rejects_total_below_live():
    cfg = _base_ok_ml()
    cfg["ml"]["model_selection"]["min_total_rows"] = {"gbt": 30, "mlp": 400}
    # gbt: total 30 < live 60
    assert _fatals(cfg)


if __name__ == "__main__":                            # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
