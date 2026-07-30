"""ML-042/should_deploy like-for-like fix (task-cmp-brief.md).

Binding invariant: a champion score and a challenger score may only be
compared when both are computed over the IDENTICAL evaluation row set. If
a like-for-like pair cannot be produced, the gate must NOT deploy.

Before this fix, main.py's retrain gate (~4725-4775) rescored the frozen
champion on the fresh OOF tail (ML-042 — base rate can differ ~79% from
the full span, measured live 0.0841 vs 0.1508) but then compared that
fresh score against the challenger's Brier over the FULL oof_idx span:
two different label populations, so the champion won by construction, not
merit (task-champ-report.md: four days, 68/68 REJECT; on the SAME 2342
rows the challenger actually wins 0.0786 vs 0.0882).

Test 1 exercises the real main.py call site end-to-end and is written to
FAIL against the pre-fix code (see task-cmp-report.md for the pasted RED
output) and PASS once should_deploy gates on shared rows only.
"""
import json
import types
from pathlib import Path

import numpy as np

from core.audit import get_audit
from core.codes import Code
from main import LiquidityBot
from ml.models import LogisticModel, load_model
from ml.monitor import ModelMonitor


class _ConstModel:
    """Frozen incumbent with a fixed, X-independent predict_proba — keeps
    the champion's own score exactly known and easy to hand-verify."""

    def __init__(self, p):
        self.p = p

    def predict_proba(self, X):
        return np.full(len(X), self.p)


def _fit_logistic(seed, n=80):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 4))
    y = (X[:, 0] > 0).astype(float)
    return LogisticModel(seed=seed).fit(X, y)


def _fake_history(X, y):
    n = len(X)
    w = np.ones(n)
    sig = np.arange(n, dtype=float)
    res = np.zeros(n)
    return types.SimpleNamespace(
        row_count=lambda: n,
        load_training_data=lambda **k: (X, y, w, sig, res),
        last_load_stats={"live_clean": n})


def _bot(tmp_path, monitor, X, y, champion_model, trained_rows):
    b = LiquidityBot.__new__(LiquidityBot)
    b.config = {"ml": {"retrain_history_path":
                       str(tmp_path / "retrain_history.jsonl")}}
    b.history = _fake_history(X, y)
    b.monitor = monitor
    b.meta = types.SimpleNamespace(
        trained=champion_model is not None, model=champion_model,
        calibrator=None, trained_rows=trained_rows,
        model_path=str(tmp_path / "meta_model.json"),
        reload=lambda: None)
    b._retrain_attempted = False
    b._rows_at_last_train = 0
    b._retrain_failures = 0
    # A loaded champion makes _retrain_gate's cold-start clause False;
    # touch the retrain flag so `want` is still True (mirrors an operator/
    # governor-requested retrain - exactly what triggers a real gate
    # decision against a live champion in production, per _retrain_gate's
    # own docstring: "degradation/drift retrains still route through the
    # monitor level / flag").
    monitor.flag_path.parent.mkdir(parents=True, exist_ok=True)
    monitor.flag_path.touch()
    return b


def _stub_pipeline(monkeypatch, results):
    import ml.contracts as contracts_mod
    import ml.interpret as interpret_mod
    import ml.walkforward as wf_mod
    monkeypatch.setattr(
        contracts_mod, "get_contract",
        lambda: types.SimpleNamespace(
            check_matrix=lambda X: {"keep": np.ones(len(X), bool)}))
    monkeypatch.setattr(interpret_mod, "background_sample", lambda X, n: [])
    monkeypatch.setattr(wf_mod, "evaluate_and_select", lambda *a, **k: results)


def _audit_mark():
    p = get_audit().path
    return p, (p.read_text(encoding="utf-8") if p.exists() else "")


def _audit_new_records(mark):
    path, before = mark
    after = path.read_text(encoding="utf-8") if path.exists() else ""
    new_lines = after[len(before):].strip().splitlines()
    return [json.loads(line) for line in new_lines if line.strip()]


# ---------------------------------------------------------------------
# Test 1: RED before the fix, GREEN after — the Brier ordering reverses
# between "scored on their own populations" and "scored on a shared set".
# ---------------------------------------------------------------------

def _mismatched_population_scenario():
    """300-row corpus; the champion trained on the first 200 rows, so OOF
    rows 200..299 are its fresh/unseen tail (100 rows). Full-span base
    rate 0.30 (90/300); fresh-tail base rate 0.08 (8/100) — the same
    relative gap the live diagnostic measured (0.0841 vs 0.1508, ~79%).

    Champion (frozen, constant p=0.10):
      - fresh-tail Brier (100 rows, what ML-042 reports)   = 0.0740
      - full-span Brier  (300 rows, never actually gated)  = 0.2500

    Challenger (isotonic-calibrated, like the real deploy path):
      - full-span Brier (uninformative p=0.50 flat on the 200 old rows;
        confident and correctly-directed on the 100 fresh rows) ~= 0.161
      - fresh-tail-only Brier (scored on the SAME 100 rows the champion
        was rescored on)                                    ~= 0.0004

    Old (buggy) comparison: challenger FULL (~0.161) vs champion FRESH
    (0.0740) -> 0.161 is not < 0.0740 - 0.005 -> REJECT.
    Fixed (shared-row) comparison: challenger FRESH (~0.0004) vs champion
    FRESH (0.0740) -> 0.0004 < 0.0740 - 0.005 -> DEPLOY.
    """
    rng = np.random.default_rng(3)
    n_old, n_fresh = 200, 100
    y_old = np.concatenate([np.ones(82), np.zeros(118)])
    y_fresh = np.concatenate([np.ones(8), np.zeros(92)])
    y = np.concatenate([y_old, y_fresh])
    X = rng.normal(size=(n_old + n_fresh, 4))
    oof_idx = np.arange(n_old + n_fresh)

    champion = _ConstModel(0.10)

    p_old = np.full(n_old, 0.50)                      # uninformative on old
    p_fresh = np.where(y_fresh > 0.5, 0.90, 0.02)      # confident + correct
    oof_p = np.concatenate([p_old, p_fresh])
    oof_y = y[oof_idx]

    challenger_model = _fit_logistic(seed=11)
    results = {"selected": "logistic", "gated": None,
              "oof_idx": oof_idx,
              "logistic": {"oof_p": oof_p, "oof_y": oof_y},
              "model": challenger_model, "importance": []}
    return X, y, champion, results, n_old


def test_deploy_flips_to_shared_row_winner(tmp_path, monkeypatch):
    X, y, champion, results, trained_rows = _mismatched_population_scenario()
    monitor = ModelMonitor({"retrain_flag_path":
                            str(tmp_path / "retrain.flag"),
                            "retrain_min_rows": 60, "deploy_min_oof": 30})
    b = _bot(tmp_path, monitor, X, y, champion, trained_rows)
    _stub_pipeline(monkeypatch, results)

    assert not Path(b.meta.model_path).exists()
    b._maybe_auto_retrain()

    # Like-for-like gate must DEPLOY: the challenger is genuinely better on
    # the SAME 100 fresh rows the champion was honestly rescored on, even
    # though its full-span score looks worse than the champion's fresh-tail
    # score — the exact reversal that made every one of 68 live deploy
    # decisions reject for four days (task-champ-report.md).
    loaded = load_model(b.meta.model_path)
    assert loaded is not None, (
        "challenger was not deployed - should_deploy is still comparing "
        "the champion's fresh-tail Brier against the challenger's "
        "FULL-SPAN Brier (population mismatch, see task-champ-report.md)")
    assert np.allclose(loaded.w, results["model"].w)
    assert monitor.champion_brier < 0.25


# ---------------------------------------------------------------------
# Test 2: fail-closed when an honest shared row set cannot be built.
# ---------------------------------------------------------------------

def test_fail_closed_when_shared_set_too_small(tmp_path, monkeypatch):
    rng = np.random.default_rng(5)
    n, trained_rows = 100, 95            # only 5 fresh rows: < deploy_min_oof
    X = rng.normal(size=(n, 4))
    y = np.array([1.0] * 30 + [0.0] * 70)
    oof_idx = np.arange(n)
    champion = _ConstModel(0.10)
    challenger_model = _fit_logistic(seed=13)
    oof_p = np.full(n, 0.30)
    results = {"selected": "logistic", "gated": None,
              "oof_idx": oof_idx,
              "logistic": {"oof_p": oof_p, "oof_y": y.copy()},
              "model": challenger_model, "importance": []}

    monitor = ModelMonitor({"retrain_flag_path":
                            str(tmp_path / "retrain.flag"),
                            "retrain_min_rows": 60, "deploy_min_oof": 30})
    b = _bot(tmp_path, monitor, X, y, champion, trained_rows)
    _stub_pipeline(monkeypatch, results)

    mark = _audit_mark()
    b._maybe_auto_retrain()

    assert not Path(b.meta.model_path).exists(), (
        "an incomparable champion/challenger pair (5 fresh rows < "
        "deploy_min_oof=30) must fail closed - no deploy")
    assert monitor.champion_brier == 0.25, \
        "badge must not move when the fresh rescore has no honest evidence"
    records = _audit_new_records(mark)
    codes = [r["code"] for r in records]
    assert Code.ML_DEPLOY_REJECT.value in codes, \
        "fail-closed path must log a registered reason code, never a bare string"
    rejects = [r for r in records if r["code"] == Code.ML_DEPLOY_REJECT.value]
    assert rejects[-1]["data"].get("n_shared") == 5
    assert rejects[-1]["data"].get("decision") == "REJECT"


# ---------------------------------------------------------------------
# Test 3: base-rate regression pin — the decision must not flip merely
# because the (shared) population's base rate differs, when the
# underlying skill gap is the same.
# ---------------------------------------------------------------------

def test_decision_invariant_to_shared_population_base_rate():
    """Regression pin: once champion and challenger are scored on ONE
    shared population, the DEPLOY decision tracks the skill gap (absolute
    Brier improvement), not the base rate of that population. A base-rate
    swing alone (0.08 vs 0.15 - the exact live gap that broke the gate,
    task-champ-report.md) must never flip the decision when the
    challenger's improvement over the champion is comparably real in
    both cases."""
    def _scenario(n_pos, n_neg, champion_p):
        y = np.concatenate([np.ones(n_pos), np.zeros(n_neg)])
        n = n_pos + n_neg
        X = np.zeros((n, 1))
        oof_idx = np.arange(n)
        champion = _ConstModel(champion_p)
        # challenger: confident, correctly-directed prediction per row -
        # genuine skill above the local baseline, same "shape" of
        # improvement at both base rates
        challenger_p = np.where(y > 0.5, 0.90, 0.03)
        return X, y, champion, oof_idx, challenger_p

    monitor = ModelMonitor({"deploy_min_oof": 20})

    for n_pos, n_neg, champion_p in ((16, 184, 0.08), (30, 170, 0.15)):
        X, y, champion, oof_idx, challenger_p = _scenario(
            n_pos, n_neg, champion_p)
        champ_fresh = monitor.rescore_frozen(champion, None, X, y, oof_idx,
                                             seen_rows=0, min_n=20)
        assert champ_fresh is not None
        shared = monitor.shared_challenger_brier(
            oof_idx, seen_rows=0, min_n=20,
            challenger_oof_p=challenger_p, y=y)
        assert shared is not None
        challenger_brier, n_shared = shared
        monitor.champion_brier = champ_fresh
        base_rate = n_pos / (n_pos + n_neg)
        assert monitor.should_deploy(challenger_brier, n_oof=n_shared), (
            f"base rate {base_rate:.2f}: a comparably skillful challenger "
            f"must deploy regardless of the shared population's base rate")


def test_era_orphan_ignore_champion_applies_cold_start_bar():
    """ML-083 (2026-07-29 wave-4/5 adversarial-verify fix): with the
    badge BELOW 0.25 (live: 0.1237, measured on the dead pre-exclusion
    population, base rate 0.169), plain should_deploy still gated
    challengers against the orphaned badge — a well-calibrated
    challenger on the NEW corpus (base 0.30, naive base-rate Brier
    ~0.21) could never clear 0.1237, so the deploy deadlock survived in
    a softer form. ignore_champion=True sets the badge aside (it is a
    cross-base-rate Brier, exactly what the like-for-like gate refuses
    to compare) and applies the true cold-start standard: Brier < 0.25
    plus the deploy_min_oof evidence floor — nothing widened beyond
    cold-start parity."""
    monitor = ModelMonitor({"deploy_min_oof": 20})
    monitor.champion_brier = 0.1237
    # badge rules the plain path: 0.20 on the new corpus is real skill
    # but cannot beat a dead population's 0.1237
    assert monitor.should_deploy(0.20, n_oof=100) is False
    assert monitor.should_deploy(0.20, n_oof=100,
                                 ignore_champion=True) is True
    # the cold-start bar itself is NOT widened: coin-or-worse stays
    # rejected, and the evidence floor still binds
    assert monitor.should_deploy(0.26, n_oof=100,
                                 ignore_champion=True) is False
    assert monitor.should_deploy(0.20, n_oof=5,
                                 ignore_champion=True) is False
