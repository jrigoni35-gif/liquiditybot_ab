"""Calibrated drift (2026-09-30): the alarm line is each feature's own
in-sample CONSECUTIVE-window PSI null, the denominator is the measurable
features, and the buffer is fed by the same event as the corpus rows.

Measured motive: on the training corpus itself (no drift by definition),
300 consecutive rows read 18.4% drift share / 42% of measurable features at
the fixed PSI 0.25 line; 300 random rows read 1.4%.
"""
from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from ml.calibration import feature_deciles, feature_psi_null
from ml.features import DRIFT_EXCLUDED_FEATURES, FEATURE_NAMES
from ml.monitor import ModelMonitor

ROOT = Path(__file__).resolve().parents[1]
N_F = len(FEATURE_NAMES)
VOTING = [j for j, n in enumerate(FEATURE_NAMES)
          if n not in DRIFT_EXCLUDED_FEATURES]


def _corpus(n=6000, seed=0, slow_share=0.5):
    """Columns: half slow random walks (autocorrelated, like vol/drawdown),
    the rest iid; one constant (degenerate) voting column."""
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, (n, N_F))
    slow = VOTING[: int(len(VOTING) * slow_share)]
    for j in slow:
        X[:, j] = np.cumsum(rng.normal(0, 0.05, n))
    X[:, VOTING[-1]] = 1.0                      # degenerate
    return X, slow


def _monitor(buf):
    m = ModelMonitor({})
    for row in buf:
        m.note_features(row)
    return m


def test_null_is_high_for_slow_features_and_low_for_iid():
    X, slow = _corpus()
    edges = feature_deciles(X)
    null = feature_psi_null(X, edges, window=300, n_windows=100)
    assert len(null) == N_F
    fast = [j for j in VOTING[:-1] if j not in slow]
    assert np.median([null[j] for j in slow]) > 0.25     # the artifact
    assert np.median([null[j] for j in fast]) < 0.10     # sampling noise
    assert null[VOTING[-1]] == 0.0                       # degenerate


def test_null_refuses_a_corpus_shorter_than_two_windows():
    X, _ = _corpus(n=500)
    assert feature_psi_null(X, feature_deciles(X), window=300) == []


def test_null_is_deterministic():
    X, _ = _corpus(n=2000)
    e = feature_deciles(X)
    assert feature_psi_null(X, e, n_windows=30) == \
        feature_psi_null(X, e, n_windows=30)


def test_calibration_silences_the_in_sample_artifact():
    X, _ = _corpus()
    edges = feature_deciles(X)
    null = feature_psi_null(X, edges, window=300, n_windows=150)
    m = _monitor(X[2000:2300])                     # consecutive, no drift
    m.check_drift(edges, FEATURE_NAMES)            # legacy fixed line
    legacy = m.drift_share
    m.check_drift(edges, FEATURE_NAMES, psi_null=null)
    assert legacy >= 0.2                           # alarms on nothing
    assert m.drift_calibrated is True
    assert m.drift_share < 0.10                    # calibrated: quiet
    assert m.drift_share_uncalibrated == pytest.approx(legacy)


def test_calibration_still_fires_on_a_real_shift():
    X, _ = _corpus()
    edges = feature_deciles(X)
    null = feature_psi_null(X, edges, window=300, n_windows=150)
    buf = X[2000:2300].copy()
    for j in VOTING[:-1]:                          # every measurable feature
        buf[:, j] += 6.0 * X[:, j].std()           # moves far out
    m = _monitor(buf)
    m.check_drift(edges, FEATURE_NAMES, psi_null=null)
    assert m.drift_share >= 0.9


def test_calibrated_denominator_is_the_measurable_features():
    X, _ = _corpus()
    edges = feature_deciles(X)
    null = feature_psi_null(X, edges, window=300, n_windows=50)
    m = _monitor(X[:300])
    m.check_drift(edges, FEATURE_NAMES, psi_null=null)
    assert m.drift_measurable == len(VOTING) - 1
    assert m.drift_share == pytest.approx(
        len(m.drifting) / m.drift_measurable)


@pytest.mark.parametrize("bad", [None, [], [0.3] * 3])
def test_no_or_mismatched_null_is_exactly_legacy(bad):
    X, _ = _corpus(n=2000)
    edges = feature_deciles(X)
    m = _monitor(X[:300])
    m.check_drift(edges, FEATURE_NAMES, psi_null=bad)
    assert m.drift_calibrated is False
    assert m.drift_share == m.drift_share_uncalibrated


def test_status_publishes_both_numbers():
    s = ModelMonitor({}).status()
    assert "drift_calibrated" in s and "drift_share_uncalibrated" in s


# ---------------- engine wiring (AST, not text) ----------------
def _main_tree():
    return ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))


def test_buffer_is_fed_only_by_a_real_registration():
    tree = _main_tree()
    fed_inside = fed_outside = 0
    for n in ast.walk(tree):
        if not isinstance(n, ast.If):
            continue
        test_src = ast.unparse(n.test)
        body_calls = {ast.unparse(c.func) for c in ast.walk(
            ast.Module(body=n.body, type_ignores=[]))
            if isinstance(c, ast.Call)}
        if test_src.startswith("self.candidates.register("):
            fed_inside += "self.monitor.note_features" in body_calls
    all_calls = [c for c in ast.walk(tree) if isinstance(c, ast.Call)
                 and ast.unparse(c.func) == "self.monitor.note_features"]
    fed_outside = len(all_calls) - fed_inside
    assert fed_inside == 1 and fed_outside == 0


def test_retrain_computes_saves_and_the_monitor_reads_the_null():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    tree = _main_tree()
    calls = {ast.unparse(c.func): c for c in ast.walk(tree)
             if isinstance(c, ast.Call)}
    cd = calls["self.monitor.check_drift"]
    assert any(k.arg == "psi_null" for k in cd.keywords)
    assert "feature_psi_null" in calls
    assert '"feature_psi_null"' in src and '"psi_null": psi_null' in src


def test_apply_sets_the_corpus_reference_before_any_gate_can_return():
    """A rejected challenger returns early; the corpus drift reference must
    already be set by then, or an old champion keeps drift uncalibrated."""
    fn = next(n for n in ast.walk(_main_tree())
              if isinstance(n, ast.FunctionDef) and n.name == "_retrain_apply")
    first_return = min((n.lineno for n in ast.walk(fn)
                        if isinstance(n, ast.Return)), default=10 ** 9)
    sets = [s.lineno for s in fn.body if isinstance(s, ast.Assign)
            and any(ast.unparse(t) == "self._drift_ref" for t in s.targets)]
    assert sets and sets[0] < first_return


class _Meta:
    def __init__(self, deciles, null):
        self.feature_deciles = deciles
        self.feature_psi_null = null


def _bot(meta, ref=None):
    import main
    b = main.LiquidityBot.__new__(main.LiquidityBot)
    b.meta = meta
    if ref is not None:
        b._drift_ref = ref
    return b


def test_reference_prefers_the_champions_own_null():
    b = _bot(_Meta(["champ"], [0.3]), ref=(["corpus"], [0.4]))
    assert b._drift_reference() == (["champ"], [0.3])


def test_reference_falls_back_to_the_latest_corpus_pair():
    # an old champion (no null) + a rejected challenger's corpus pair
    b = _bot(_Meta(["champ"], []), ref=(["corpus"], [0.4]))
    assert b._drift_reference() == (["corpus"], [0.4])


def test_reference_is_legacy_when_nothing_carries_a_null():
    b = _bot(_Meta(["champ"], []))
    assert b._drift_reference() == (["champ"], None)
    b2 = _bot(_Meta(["champ"], []), ref=(["corpus"], []))
    assert b2._drift_reference() == (["champ"], None)
