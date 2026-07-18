"""tests/test_adaptive_gbt.py — AdaptiveGBT: the opt-in, continuously-
learnable top ladder rung (ml/models.py).

Covers the four things that make it safe to ship: it is a correct
probability model, it serializes byte-faithfully through the same
save/load path as every other artifact, its warm-update continuous-
learning path can only ever help or hold (bounded, guarded, finite),
and it enters the DEPLOYED selection strictly opt-in so the default
pipeline the overfit battery measures is untouched.
"""
import json
import warnings

import numpy as np

from core.config_guard import validate
from ml.calibration import brier_score
from ml.contracts import SCHEMA_VERSION
from ml.features import FEATURE_NAMES
from ml.models import (AdaptiveGBT, GradientBoostedStumps, load_model,
                       save_model)
from ml.walkforward import _COMPLEXITY, _LADDER, evaluate_and_select


def _interaction_world(n, seed):
    """A conditional-interaction target boosted trees can exploit but a
    linear model cannot fully — the honest way to see the tree rungs move."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 8))
    logit = 0.6 * X[:, 0] + 1.8 * X[:, 1] * (X[:, 2] > 0) - 0.4
    y = (rng.random(n) < 1.0 / (1.0 + np.exp(-logit))).astype(float)
    return X, y


# --------------------------------------------------------------------------
# 1. it is a correct probability model
# --------------------------------------------------------------------------
def test_fit_predict_is_a_valid_probability():
    X, y = _interaction_world(1200, 0)
    m = AdaptiveGBT(k=4, seed=1).fit(X[:900], y[:900])
    p = m.predict_proba(X[900:])
    assert p.shape == (300,)
    assert np.isfinite(p).all()
    assert (p >= 0.0).all() and (p <= 1.0).all()
    assert m.kind == "adaptive_gbt"
    assert len(m.members) == 4
    # each bag is a genuinely independent fit (different seeds) -> the
    # ensemble mean is not identical to any single member
    solo = m.members[0].predict_proba(X[900:])
    assert not np.allclose(p, solo)


def test_predict_is_exactly_the_member_mean():
    X, y = _interaction_world(600, 2)
    m = AdaptiveGBT(k=3, seed=5).fit(X, y)
    expected = np.mean([mm.predict_proba(X) for mm in m.members], axis=0)
    assert np.allclose(m.predict_proba(X), expected)


def test_n_features_stamped_and_unfitted_is_none():
    X, y = _interaction_world(400, 3)
    assert AdaptiveGBT(k=2).n_features is None          # before fit
    m = AdaptiveGBT(k=2, seed=1).fit(X, y)
    assert m.n_features == 8


# --------------------------------------------------------------------------
# 2. it serializes byte-faithfully through the artifact path
# --------------------------------------------------------------------------
def test_json_round_trip_is_identical():
    X, y = _interaction_world(900, 4)
    m = AdaptiveGBT(k=4, seed=7).fit(X[:700], y[:700])
    m2 = AdaptiveGBT.from_dict(json.loads(json.dumps(m.to_dict())))
    assert np.allclose(m2.predict_proba(X[700:]), m.predict_proba(X[700:]))
    assert m2.kind == "adaptive_gbt" and len(m2.members) == 4


def test_save_load_dispatch_and_schema_stamp(tmp_path):
    X, y = _interaction_world(800, 5)
    m = AdaptiveGBT(k=3, seed=2).fit(X, y)
    path = tmp_path / "adaptive.json"
    save_model(m, str(path), extra={"oof_brier": 0.2})
    loaded = load_model(str(path))
    assert isinstance(loaded, AdaptiveGBT)              # kind dispatch
    assert np.allclose(loaded.predict_proba(X), m.predict_proba(X))
    stamp = json.loads(path.read_text(encoding="utf-8"))
    assert stamp["feature_schema_version"] == SCHEMA_VERSION


# --------------------------------------------------------------------------
# 3. warm-update continuous learning: bounded, guarded, and it actually
#    moves the model toward the fresh regime
# --------------------------------------------------------------------------
def test_warm_update_grows_bounded_and_stays_finite():
    X, y = _interaction_world(700, 6)
    m = AdaptiveGBT(k=3, warm_rounds=20, max_total_trees=800, seed=3).fit(X, y)
    before = [len(mm.trees) for mm in m.members]
    m.warm_update(X, y)
    after = [len(mm.trees) for mm in m.members]
    # every member with head-room gained trees, none exceeded the cap
    assert all(a >= b for a, b in zip(after, before))
    assert any(a > b for a, b in zip(after, before))
    assert all(a <= 800 for a in after)
    assert np.isfinite(m.predict_proba(X)).all()


def test_warm_update_never_exceeds_the_cap():
    X, y = _interaction_world(500, 7)
    # cap only a little above the base fit so the ceiling actually bites
    m = AdaptiveGBT(k=2, warm_rounds=40, max_total_trees=420, seed=1).fit(X, y)
    for _ in range(30):
        m.warm_update(X, y)
    assert all(len(mm.trees) <= 420 for mm in m.members)
    assert np.isfinite(m.predict_proba(X)).all()


def test_warm_update_leans_toward_the_new_regime():
    # train on regime A (feature 0 bullish), then warm-update on regime B
    # (feature 0 REVERSED). A model that genuinely learns online must shift
    # its verdict on a B-flavored probe toward B after the update.
    rng = np.random.default_rng(11)
    Xa = rng.normal(size=(900, 6))
    ya = (rng.random(900) < 1.0 / (1.0 + np.exp(-(1.6 * Xa[:, 0])))).astype(float)
    m = AdaptiveGBT(k=3, warm_rounds=30, max_total_trees=900, seed=2).fit(Xa, ya)

    Xb = rng.normal(size=(500, 6))
    yb = (rng.random(500) < 1.0 / (1.0 + np.exp(-(-1.6 * Xb[:, 0])))).astype(float)
    probe = np.zeros((1, 6))
    probe[0, 0] = 2.0                       # strongly +feature0
    p_before = float(m.predict_proba(probe)[0])
    m.warm_update(Xb, yb)
    p_after = float(m.predict_proba(probe)[0])
    # under regime A, +feature0 -> win (p high); under B it -> loss (p low).
    # the warm update must drag the probe's probability downward.
    assert p_after < p_before - 0.02


def test_continue_fit_guards_are_no_ops():
    X, y = _interaction_world(300, 8)
    # unfitted model: nothing to continue from
    g = GradientBoostedStumps(seed=1)
    g.continue_fit(X, y, 5)
    assert g.trees == []
    # width mismatch: refuse silently
    g2 = GradientBoostedStumps(seed=1).fit(X, y)
    n_before = len(g2.trees)
    g2.continue_fit(X[:, :4], y, 5)
    assert len(g2.trees) == n_before
    # non-positive rounds: no-op
    g2.continue_fit(X, y, 0)
    assert len(g2.trees) == n_before


def test_warm_update_survives_a_save_load_cycle(tmp_path):
    # continuous learning must work AFTER a restart: a model loaded from disk
    # carries its regularization (subsample/l2/min_child/seed now serialized),
    # so continue_fit is faithful, not silently defaulted.
    X, y = _interaction_world(700, 9)
    m = AdaptiveGBT(k=2, warm_rounds=15, max_total_trees=800, seed=4).fit(X, y)
    path = tmp_path / "m.json"
    save_model(m, str(path))
    loaded = load_model(str(path))
    grew_before = [len(mm.trees) for mm in loaded.members]
    loaded.warm_update(X, y)
    assert all(len(mm.trees) > b
               for mm, b in zip(loaded.members, grew_before))
    assert np.isfinite(loaded.predict_proba(X)).all()
    # the serialized GBT members carry their regularization forward
    reg = json.loads(path.read_text(encoding="utf-8"))["members"][0]
    assert {"subsample", "l2", "min_child_hess", "seed"} <= set(reg)


# --------------------------------------------------------------------------
# 4. deployed selection is strictly opt-in
# --------------------------------------------------------------------------
def test_default_ladder_never_evaluates_adaptive():
    X, y = _interaction_world(1200, 10)
    r = evaluate_and_select(X, y, label_span=30)          # no extra_models
    assert "adaptive_gbt" not in r
    assert r["selected"] in _LADDER


def test_optin_ladder_evaluates_and_places_by_complexity():
    X, y = _interaction_world(1400, 12)
    r = evaluate_and_select(X, y, label_span=30,
                            extra_models=("adaptive_gbt",),
                            adaptive_cfg={"bags": 3})
    assert "adaptive_gbt" in r
    # never the baseline on an interaction world; must be a real rung
    assert r["selected"] in _COMPLEXITY
    assert r["selected"] != "logistic"
    # the extra rung is the MOST complex step, so it only wins by beating mlp
    order = {name: i for i, name in enumerate(_COMPLEXITY)}
    assert order["adaptive_gbt"] == max(order.values())


def test_optin_stays_simplicity_biased_on_linear_data():
    rng = np.random.default_rng(13)
    X = rng.normal(size=(700, 6))
    y = (rng.random(700) < 1.0 / (1.0 + np.exp(-(0.9 * X[:, 0] - 0.1)))
         ).astype(float)
    r = evaluate_and_select(X, y, label_span=30,
                            extra_models=("adaptive_gbt",))
    # a pure-linear world must not buy the most complex rung
    assert r["selected"] == "logistic"


def test_shipped_config_validates_and_guard_bounds_the_rung():
    # NOTE: this deliberately does NOT pin enabled True/False — that is an
    # operator choice, not an invariant. What must hold either way: the
    # SHIPPED config validates clean, and every adaptive bound FATALs a bad
    # value when the rung is enabled while being ignored when it is off.
    import pathlib
    cfg_path = pathlib.Path(__file__).resolve().parents[1] / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert not [m for s, m in validate(cfg)
                if s == "FATAL" and "adaptive" in m]      # ships clean

    def fatals_for(**over):
        bad = json.loads(json.dumps(cfg))
        bad["ml"]["adaptive_gbt"].update(over)
        return [m for s, m in validate(bad) if s == "FATAL"]

    # all three bounds bite when ENABLED
    assert any("max_total_trees" in m
               for m in fatals_for(enabled=True, max_total_trees=100))
    assert any("bags" in m for m in fatals_for(enabled=True, bags=0))
    assert any("warm_rounds" in m
               for m in fatals_for(enabled=True, warm_rounds=0))
    # ...and are correctly IGNORED when disabled (nonsense but dormant)
    assert not any("adaptive" in m for m in fatals_for(
        enabled=False, max_total_trees=1, bags=0, warm_rounds=0))


def test_pbo_space_includes_the_rung_only_when_asked():
    # OF-3 must measure the DEPLOYED selection space: enabling the rung
    # grows the PBO space by EXACTLY one and ranks it LAST (most complex),
    # so the ladder only elects it by out-earning every simpler config.
    from ml.overfit import model_space_pbo
    X, y = _interaction_world(600, 30)
    base = model_space_pbo(X, y, label_span=30, n_splits=3, n_blocks=6)
    ext = model_space_pbo(X, y, label_span=30, n_splits=3, n_blocks=6,
                          include_adaptive=True, adaptive_cfg={"bags": 2})
    assert "adaptive_gbt" not in base["configs"]
    assert "adaptive_gbt" in ext["configs"]
    assert len(ext["configs"]) == len(base["configs"]) + 1
    assert ext["configs"][-1] == "adaptive_gbt"          # appended last


def test_pbo_space_tracks_the_shipped_config_flag():
    # the OF-3 invariant end to end: the adaptive rung is in the measured
    # PBO space IFF the shipped config enables it — so OF-3 always certifies
    # the rule the bot actually deploys, whatever the operator sets the flag
    # to (no pinned choice, just the coupling).
    import pathlib
    from ml.overfit import model_space_pbo
    cfg_path = pathlib.Path(__file__).resolve().parents[1] / "config.json"
    ag = json.loads(cfg_path.read_text(encoding="utf-8"))[
        "ml"]["adaptive_gbt"]
    enabled = bool(ag.get("enabled", False))
    X, y = _interaction_world(500, 33)
    pb = model_space_pbo(X, y, label_span=30, n_splits=3, n_blocks=6,
                         include_adaptive=enabled,
                         adaptive_cfg=ag if enabled else None)
    assert ("adaptive_gbt" in pb["configs"]) == enabled


def test_adaptive_is_competitive_with_gbt_when_it_matters():
    # not a "must beat" (that would be tuning to a seed): the honest claim is
    # that bagging boosted trees is at least on par with the single gbt rung
    # out-of-fold on an interaction world it can model.
    X, y = _interaction_world(1600, 21)
    r = evaluate_and_select(X, y, label_span=30,
                            extra_models=("adaptive_gbt",),
                            adaptive_cfg={"bags": 4})
    assert r["adaptive_gbt"]["mean_brier"] <= r["gbt"]["mean_brier"] + 0.01
    # and it produced real OOF probabilities, not an empty degenerate block
    assert len(r["adaptive_gbt"]["oof_p"]) > 0
    assert brier_score(r["adaptive_gbt"]["oof_y"],
                       r["adaptive_gbt"]["oof_p"]) < 0.25


def test_unfitted_predict_degrades_to_a_fault_not_a_number():
    # an unfitted model must never emit a plausible-looking probability that
    # Kelly would act on. Like EnsembleMLP (mean of no members), AdaptiveGBT
    # yields a NON-FINITE value, which MetaModelService.p_win's
    # `if not np.isfinite(p): raise -> prior` guard converts into a safe
    # cold-start fallback. Assert the safe-degradation contract, not a raise.
    m = AdaptiveGBT(k=2, seed=1)                        # never fitted
    with warnings.catch_warnings(), np.errstate(invalid="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)  # mean of no members
        p = m.predict_proba(np.zeros((1, len(FEATURE_NAMES))))
    assert not np.isfinite(np.asarray(p)).all()
    assert m.n_features is None
