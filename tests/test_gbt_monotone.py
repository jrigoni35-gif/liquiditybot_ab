"""tests/test_gbt_monotone.py — T3.4: bound-propagated monotone
constraints in the owned GradientBoostedStumps, + the opt-in "gbt_mono"
ladder rung (ml/walkforward.py, ml/overfit.py, main.py), shipped disabled.

Covers (per the task brief):
  1. PROPERTY SWEEP - a synthetic corpus engineered so the UNCONSTRAINED
     model genuinely VIOLATES monotonicity in a flagged feature (the RED
     half, asserted explicitly before anything about the constrained
     model), then the CONSTRAINED model is monotone across a grid of
     probe rows sweeping only the flagged feature.
  2. Determinism pin: same seed + corpus -> identical to_dict.
  3. monotone_constraints=None leaves the model untouched - asserted
     MACHINE-INDEPENDENTLY (no-new-key, None==={}, determinism, and a
     real constraint still moves the trees). This replaced a hardcoded
     sha256 of to_dict() that was green on the authoring container and
     RED on the Windows target runtime, blocking every deploy; the
     one-time pre/post comparison against `git show bd92339:ml/models.py`
     is recorded in task-3-report.md and stands on its own.
  4. The two-sided mutation proof (disable the clamp -> property test
     FAILS; restore -> passes) is NOT a permanent test here (mutating
     production code from a test would itself be the kind of "unverified
     edit" CLAUDE.md forbids) - it was performed manually and both raw
     outputs are recorded in task-3-report.md.
  5. Guard tests: unknown feature name FATAL, bad sign FATAL, >12
     constraints WARN, shipped config.json validates clean.
  6. AdaptiveGBT propagation smoke: monotone_constraints reaches members
     via **gbt_kwargs (no AdaptiveGBT code change needed - it already
     forwards arbitrary gbt kwargs to every GradientBoostedStumps member).

Plus ladder/PBO-space wiring sanity (gbt_mono placed directly after gbt,
opt-in only, evidence-gated via pbo_family -> "gbt").
"""
import json

import numpy as np

from core.config_guard import validate
from ml.features import FEATURE_NAMES
from ml.models import AdaptiveGBT, GradientBoostedStumps, load_model, save_model
from ml.overfit import model_space_pbo
from ml.walkforward import _COMPLEXITY, _LADDER, evaluate_and_select

# real, verified indices (context brief): gate_confidence=61, spread_bps=7,
# fv_edge_bps=9, flow_tox=59, manip_suspect=52 - not used directly by these
# unit tests (which exercise GradientBoostedStumps on small synthetic
# matrices, not the full 62-wide corpus), but asserted here so a future
# FEATURE_NAMES edit that silently moves one of the five shipped-config
# constraint features is caught at test time, not at guard time.
_SHIPPED_CONSTRAINT_INDICES = {
    # deliberate re-pin: v9 shadow pair (ofi_dir/basis_mom_dir) slots
    # before the direction/gate_confidence tail, moving gate_confidence
    # 61->63; v10 dark-pool block (dp_surge_z/dp_vol_z/dp_hhi/avail_dp)
    # moves it 63->67; every other constrained feature keeps its index
    "gate_confidence": 67, "spread_bps": 7, "fv_edge_bps": 9,
    "flow_tox": 59, "manip_suspect": 52,
}


def test_shipped_constraint_feature_indices_are_verified():
    for name, idx in _SHIPPED_CONSTRAINT_INDICES.items():
        assert FEATURE_NAMES[idx] == name, (
            f"{name} moved to a different index - config.json's "
            f"ml.gbt_mono.constraints names it by NAME (resolved by main.py "
            f"at retrain time), so this only matters if code ever hardcodes "
            f"the index; still worth pinning as a canary")


# ---------------------------------------------------------------------------
# helper: a genuinely non-monotonic synthetic world
# ---------------------------------------------------------------------------
def _concave_world(n=4000, seed=13, d=5):
    """Flagged feature (column 2) has a TRUE inverted-U (concave)
    relationship with the label: probability peaks at feature=0 and falls
    off toward BOTH extremes. This is not noise dressed up as a violation -
    it is a real, fittable pattern that is inherently non-monotonic, so ANY
    monotone sign constraint (+1 or -1) is "wrong" for at least half the
    range and an unconstrained tree will happily learn the true shape,
    violating either constraint. Columns 0/1 are strong linear drivers so
    the tree has real work to do elsewhere too (not simply a corpus
    engineered around one feature)."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d)).astype(float)
    logit = 1.1 * X[:, 0] - 0.8 * X[:, 1] - 0.9 * (X[:, 2] ** 2) + 0.15
    p = 1.0 / (1.0 + np.exp(-logit))
    y = (rng.random(n) < p).astype(float)
    return X, y


def _sweep(model, flagged_col, grid, base_row, d):
    """predict_proba across `grid` values of `flagged_col`, every other
    column held at `base_row`'s value."""
    rows = np.tile(base_row, (len(grid), 1)).astype(float)
    rows[:, flagged_col] = grid
    return model.predict_proba(rows)


# ---------------------------------------------------------------------------
# 1) property sweep: RED (real violation) -> GREEN (constrained is monotone)
# ---------------------------------------------------------------------------
def test_unconstrained_gbt_genuinely_violates_monotonicity():
    """RED half: verify the violation exists BEFORE trusting anything about
    the constrained model. If this assertion doesn't fire, the corpus is
    not doing its job and must be redesigned (per the task brief) - not
    weakened into a tautology."""
    X, y = _concave_world()
    m = GradientBoostedStumps(seed=3, n_estimators=200).fit(
        X[:3000], y[:3000], X[3000:], y[3000:])
    grid = np.linspace(-2.5, 2.5, 21)
    p = _sweep(m, 2, grid, np.zeros(5), 5)
    diffs = np.diff(p)
    # a genuine violation of EITHER monotone direction: some step goes up,
    # some step goes down, across the same sweep.
    assert diffs.min() < -1e-6, (
        f"corpus does not violate +1 (non-decreasing): min diff "
        f"{diffs.min():.6f} - RED half failed, redesign the corpus")
    assert diffs.max() > 1e-6, (
        f"corpus does not violate -1 (non-increasing): max diff "
        f"{diffs.max():.6f} - RED half failed, redesign the corpus")


def test_constrained_gbt_is_monotone_across_a_grid_of_probe_rows():
    """GREEN half: with monotone_constraints={2: sign}, predict_proba must
    be monotone non-decreasing (+1) / non-increasing (-1) as ONLY column 2
    varies, across several different base rows (not just the origin)."""
    X, y = _concave_world()
    grid = np.linspace(-2.5, 2.5, 25)
    rng = np.random.default_rng(99)
    base_rows = [rng.normal(size=5) for _ in range(6)]
    for sign in (1, -1):
        m = GradientBoostedStumps(
            seed=3, n_estimators=200, monotone_constraints={2: sign}
        ).fit(X[:3000], y[:3000], X[3000:], y[3000:])
        for base in base_rows:
            base = base.copy()
            p = _sweep(m, 2, grid, base, 5)
            diffs = np.diff(p)
            if sign > 0:
                assert diffs.min() >= -1e-9, (
                    f"sign=+1 violated: base={base}, worst step "
                    f"{diffs.min():.3e}")
            else:
                assert diffs.max() <= 1e-9, (
                    f"sign=-1 violated: base={base}, worst step "
                    f"{diffs.max():.3e}")


def test_unflagged_features_are_not_constrained():
    """The constraint is per-feature: sweeping an UNFLAGGED column (0, the
    strong linear driver) on the sign={2: ...}-constrained model is free to
    move either direction - the enforcement must not leak onto other axes."""
    X, y = _concave_world()
    m = GradientBoostedStumps(
        seed=3, n_estimators=200, monotone_constraints={2: 1}
    ).fit(X[:3000], y[:3000], X[3000:], y[3000:])
    grid = np.linspace(-2.5, 2.5, 21)
    p = _sweep(m, 0, grid, np.zeros(5), 5)
    # column 0 has a positive linear coefficient in the true model, so this
    # should be increasing (not the point of the test, just a sanity check);
    # the actual claim is merely that it is NOT artificially bounded flat.
    assert np.diff(p).max() > 1e-3, (
        "unflagged feature 0 shows no variation - constraint enforcement "
        "may be leaking onto axes it was never asked to touch")


# ---------------------------------------------------------------------------
# 2) determinism pin
# ---------------------------------------------------------------------------
def test_determinism_same_seed_same_corpus_identical_to_dict():
    X, y = _concave_world(n=1200, seed=41)
    kwargs = dict(seed=5, n_estimators=60, monotone_constraints={2: -1})
    m1 = GradientBoostedStumps(**kwargs).fit(X[:900], y[:900], X[900:], y[900:])
    m2 = GradientBoostedStumps(**kwargs).fit(X[:900], y[:900], X[900:], y[900:])
    assert json.dumps(m1.to_dict(), sort_keys=True) == \
        json.dumps(m2.to_dict(), sort_keys=True)


# ---------------------------------------------------------------------------
# 3) None leaves the model untouched (machine-independent)
# ---------------------------------------------------------------------------
# The original one-time pre/post check ran the ACTUAL pre-T3.4 ml/models.py
# (git show bd92339:ml/models.py) in an isolated module load and compared
# to_dict(); that transcript is in task-3-report.md and remains the evidence
# that adding the parameter changed nothing. It is NOT re-derivable here: the
# digest it produced is a hash of raw floats and is therefore CPU/numpy
# specific. See the test below for what is asserted instead.
_PRE_T34_KEYS = {"base", "colsample", "importance", "kind", "l2", "lr",
                 "max_depth", "min_child_hess", "n_features", "seed",
                 "subsample", "trees"}


def _corpus_for_pin(n=1500, seed=13, d=6):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d)).astype(float)
    logit = 1.1 * X[:, 0] - 0.8 * X[:, 1] - 0.9 * (X[:, 2] ** 2) + 0.15
    p = 1.0 / (1.0 + np.exp(-logit))
    y = (rng.random(n) < p).astype(float)
    return X, y


def test_monotone_constraints_none_leaves_the_model_untouched():
    """The unconstrained path is inert — machine-INDEPENDENTLY.

    This replaced a hardcoded sha256 of json.dumps(to_dict()). That pin
    was green on the authoring container and RED on the Windows target
    runtime (2026-07-26: got 4c02fab7… vs pinned 0f80ee5b…, key-set
    assertion passing, so shape identical and only float values moved).
    to_dict() serializes raw floats — `base` is 4.44e-16, a summation
    -order residue that should be zero — so a bit-exact digest asserts
    identical FP arithmetic across CPU/numpy builds, which is not a
    property this project has or wants. It is also not a QUALITY gate
    whose loosening would hide a regression: the pre/post comparison it
    encoded was a ONE-TIME migration check, performed against
    `git show bd92339:ml/models.py` in a separate process and recorded
    in task-3-report.md. That evidence stands; re-deriving it on every
    machine forever was never possible.
    Cost of leaving it: the PC's test-gated auto-updater rejected EVERY
    deploy (deploy.head stuck at 19cd87b while main moved on), so no
    code could reach the bot at all.

    What is asserted instead — all portable, and jointly they still fail
    if the constraint machinery ever leaks into the unconstrained path:
      1. to_dict() gains NO key when unconstrained (the serialization
         contract every consumer depends on);
      2. None and {} are indistinguishable (the machinery is dormant,
         not merely empty-configured);
      3. the fit is deterministic under a fixed seed;
      4. a REAL constraint still changes the output — without this the
         other three would pass against a build where constraints were
         silently ignored everywhere.
    """
    X, y = _corpus_for_pin()
    tr, te = slice(0, 1200), slice(1200, None)

    def _fit(mc):
        return GradientBoostedStumps(
            seed=5, n_estimators=80, monotone_constraints=mc
        ).fit(X[tr], y[tr], X[te], y[te]).to_dict()

    d_none = _fit(None)

    # 1. serialization contract: no new key on the unconstrained path
    assert set(d_none.keys()) == _PRE_T34_KEYS, (
        "monotone_constraints=None must add NO new key to to_dict() - "
        f"got {sorted(d_none.keys())}")

    # 2. dormant, not just empty: None and {} agree exactly (same
    #    process, same machine -> bit-exact comparison IS valid here)
    assert _fit({}) == d_none, (
        "monotone_constraints={} must be indistinguishable from None - "
        "the bound-propagation machinery is not inert when unused")

    # 3. determinism under a fixed seed
    assert _fit(None) == d_none, "same seed must reproduce the same model"

    # 4. teeth: a real constraint MUST move the FITTED TREES, otherwise
    #    1-3 would also pass against a build that ignores constraints.
    #    Compare trees ONLY, never the whole dict: to_dict() serializes a
    #    "monotone_constraints" key whenever the arg is non-empty, so a
    #    whole-dict `!=` is satisfied by that key alone and would pass
    #    even with the constraint logic ripped out (verified by mutating
    #    ml/models.py's `sign = ...` lookup to None — the whole-dict form
    #    of this assertion did NOT catch it; this form does).
    assert _fit({0: 1, 2: -1})["trees"] != d_none["trees"], (
        "a non-empty monotone_constraints produced the SAME TREES as the "
        "unconstrained fit - the constraint logic is being ignored")


def test_from_dict_roundtrip_preserves_constraints_and_predictions():
    X, y = _concave_world(n=1200, seed=7)
    m = GradientBoostedStumps(
        seed=2, n_estimators=60, monotone_constraints={2: 1, 0: -1}
    ).fit(X[:900], y[:900], X[900:], y[900:])
    d = json.loads(json.dumps(m.to_dict()))     # real JSON round trip
    assert d["monotone_constraints"] == {"2": 1, "0": -1}   # JSON-safe keys
    m2 = GradientBoostedStumps.from_dict(d)
    assert m2.monotone_constraints == {2: 1, 0: -1}         # back to int keys
    assert np.allclose(m2.predict_proba(X[900:]), m.predict_proba(X[900:]))


def test_save_load_roundtrip_via_registry_dispatch(tmp_path):
    X, y = _concave_world(n=800, seed=8)
    m = GradientBoostedStumps(
        seed=1, n_estimators=40, monotone_constraints={2: -1}
    ).fit(X, y)
    path = tmp_path / "gbt_mono.json"
    save_model(m, str(path))
    loaded = load_model(str(path))
    assert isinstance(loaded, GradientBoostedStumps)
    assert loaded.monotone_constraints == {2: -1}
    assert np.allclose(loaded.predict_proba(X), m.predict_proba(X))


def test_unconstrained_model_omits_the_key_entirely():
    X, y = _concave_world(n=600, seed=2)
    m = GradientBoostedStumps(seed=1, n_estimators=30).fit(X, y)
    assert "monotone_constraints" not in m.to_dict()
    assert m.monotone_constraints is None


# ---------------------------------------------------------------------------
# 5) guard tests
# ---------------------------------------------------------------------------
def _sev(cfg, sev):
    return [m for s, m in validate(cfg) if s == sev]


def test_guard_unknown_feature_name_is_fatal():
    cfg = {"system": {"dry_run": True},
           "ml": {"gbt_mono": {"enabled": False,
                                "constraints": {"not_a_real_feature": 1}}}}
    assert any("gbt_mono" in m and "not_a_real_feature" in m
               for m in _sev(cfg, "FATAL"))


def test_guard_bad_sign_is_fatal():
    cfg = {"system": {"dry_run": True},
           "ml": {"gbt_mono": {"enabled": False,
                                "constraints": {"spread_bps": 2}}}}
    assert any("gbt_mono" in m for m in _sev(cfg, "FATAL"))


def test_guard_bool_sign_is_fatal():
    # isinstance(True, int) is True in Python - a bare `sign not in (1, -1)`
    # would silently accept True as 1; the guard must reject it explicitly.
    cfg = {"system": {"dry_run": True},
           "ml": {"gbt_mono": {"enabled": False,
                                "constraints": {"spread_bps": True}}}}
    assert any("gbt_mono" in m for m in _sev(cfg, "FATAL"))


def test_guard_valid_constraints_are_clean():
    cfg = {"system": {"dry_run": True},
           "ml": {"gbt_mono": {
               "enabled": False,
               "constraints": {"gate_confidence": 1, "spread_bps": -1,
                               "fv_edge_bps": 1, "flow_tox": -1,
                               "manip_suspect": -1}}}}
    assert not any("gbt_mono" in m for m in _sev(cfg, "FATAL"))


def test_guard_validates_even_when_disabled():
    """A typo in the constraints dict must FATAL regardless of enabled: -
    the operator flips enabled:true later without re-editing constraints,
    so the earlier the error surfaces the better."""
    cfg = {"system": {"dry_run": True},
           "ml": {"gbt_mono": {"enabled": False,
                                "constraints": {"nonsense_feature": 1}}}}
    assert any("gbt_mono" in m for m in _sev(cfg, "FATAL"))


def test_guard_warns_above_twelve_constraints():
    thirteen = dict.fromkeys(FEATURE_NAMES[:13], 1)
    cfg = {"system": {"dry_run": True},
           "ml": {"gbt_mono": {"enabled": False, "constraints": thirteen}}}
    assert any("gbt_mono" in m for m in _sev(cfg, "WARN"))
    assert not any("gbt_mono" in m for m in _sev(cfg, "FATAL"))


def test_shipped_config_validates_clean():
    import pathlib
    cfg_path = pathlib.Path(__file__).resolve().parents[1] / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert not [m for s, m in validate(cfg)
                if s == "FATAL" and "gbt_mono" in m]
    gm = cfg["ml"]["gbt_mono"]
    assert gm["enabled"] is False, "T3.4 must ship DISABLED"
    assert len(gm["constraints"]) == 5
    assert set(gm["constraints"]) == {"gate_confidence", "spread_bps",
                                      "fv_edge_bps", "flow_tox",
                                      "manip_suspect"}


# ---------------------------------------------------------------------------
# 6) AdaptiveGBT propagation smoke
# ---------------------------------------------------------------------------
def test_adaptive_gbt_propagates_monotone_constraints_to_members():
    X, y = _concave_world(n=1200, seed=17)
    m = AdaptiveGBT(k=3, seed=4, monotone_constraints={2: 1}).fit(
        X[:900], y[:900])
    assert len(m.members) == 3
    for member in m.members:
        assert member.monotone_constraints == {2: 1}
    # and the constraint is genuinely ENFORCED on each member, not just
    # stored - reuse the same sweep check as the standalone model test.
    grid = np.linspace(-2.5, 2.5, 21)
    p = _sweep(m, 2, grid, np.zeros(5), 5)
    assert np.diff(p).min() >= -1e-9


# ---------------------------------------------------------------------------
# ladder / PBO-space wiring sanity (mirrors adaptive_gbt's own test suite)
# ---------------------------------------------------------------------------
def test_gbt_mono_sits_directly_after_gbt_in_complexity_order():
    order = {name: i for i, name in enumerate(_COMPLEXITY)}
    assert order["gbt_mono"] == order["gbt"] + 1, _COMPLEXITY


def test_default_ladder_never_evaluates_gbt_mono():
    X, y = _concave_world(n=1200, seed=21)
    r = evaluate_and_select(X, y, label_span=30)          # no extra_models
    assert "gbt_mono" not in r
    assert r["selected"] in _LADDER


def test_optin_ladder_evaluates_gbt_mono_when_requested():
    X, y = _concave_world(n=1400, seed=23)
    r = evaluate_and_select(
        X, y, label_span=30, extra_models=("gbt_mono",),
        gbt_mono_cfg={"constraints": {2: 1}})
    assert "gbt_mono" in r
    assert len(r["gbt_mono"]["oof_p"]) > 0


def test_pbo_space_includes_gbt_mono_only_when_asked():
    X, y = _concave_world(n=1000, seed=27)
    base = model_space_pbo(X, y, label_span=30, n_splits=4, n_blocks=6)
    ext = model_space_pbo(X, y, label_span=30, n_splits=4, n_blocks=6,
                          include_gbt_mono=True,
                          gbt_mono_cfg={"constraints": {2: 1}})
    assert "gbt_mono" not in base["configs"]
    assert "gbt_mono" in ext["configs"]
    assert len(ext["configs"]) == len(base["configs"]) + 1
    # placed directly after the gbt_* hyperparameter block, before mlp_small
    assert ext["configs"][ext["configs"].index("gbt_mono") - 1] \
        .startswith("gbt_d")
    assert ext["configs"][ext["configs"].index("gbt_mono") + 1] == "mlp_small"


def test_pbo_space_tracks_the_shipped_config_flag():
    import pathlib
    cfg_path = pathlib.Path(__file__).resolve().parents[1] / "config.json"
    gm = json.loads(cfg_path.read_text(encoding="utf-8"))["ml"]["gbt_mono"]
    enabled = bool(gm.get("enabled", False))
    resolved = {FEATURE_NAMES.index(n): s
               for n, s in gm["constraints"].items()}
    X, y = _concave_world(n=900, seed=31)
    pb = model_space_pbo(X, y, label_span=30, n_splits=3, n_blocks=6,
                         include_gbt_mono=enabled,
                         gbt_mono_cfg={"constraints": resolved}
                         if enabled else None)
    assert ("gbt_mono" in pb["configs"]) == enabled
