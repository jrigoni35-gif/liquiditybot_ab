"""tests/test_audit_ml_offline.py - 2026-08-01 audit, group "ml-offline".

The offline ML lane (train_meta / overfit_check / learning_curve /
feature_stability / interpret_report + ml.overfit + ml.history) is what
decides which model SHIPS. Six defects made it measure - and deploy - a
different process than the one the bot runs:

  H12  every offline consumer built HistoryStore WITHOUT max_bars, so
       current_era resolved to the legacy "triple_barrier" while main.py
       resolves "triple_barrier_h24". With era exclusion armed on both
       sides the offline corpus is the exact COMPLEMENT of production's,
       and train_meta DEPLOYS the model fitted on it.
  H11  train_meta's evidence gate counted RAW CSV live rows instead of
       the loader's own live_clean, admitting model families production
       refuses (measured: 275 vs 0 -> {mlp, adaptive_gbt, ...} vs
       {logistic}).
  H14  OF-3's PBO and OF-7's dead-feature read fit every config with
       UNIFORM weights while the deployed selector fits with the de Prado
       sample weights.
  M10  cold-start bootstrap is vstacked per-symbol (clock restarts at the
       block boundary, then sig is discarded), so the row-count purge
       trains on ETH labels contemporaneous with the BTC test rows; and
       bootstrap rows wrote depth_ratio at the zeros-init 0.0 while its
       live neutral is 1.0.
  LOW  OF-5 and the regime diagnostic still read the hardcoded default
       corpus path; four consumers hardcoded the sample-weight kwargs
       instead of reading ml.sample_weights.

NOT fixed here, deliberately: overfit_check's hardcoded 96-bar label_span
is NOT repaired by wiring ml.label_max_bars (24) in - production does not
purge at 24 either (main.py passes res=res and purged_walk_forward ignores
label_span in that branch), so span-24 would UNDER-purge every fold. The
correct parity fix is threading `res`, pinned below.
"""
import ast
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

import ml.history as mlh
import ml.overfit as mlo
from ml.features import FEATURE_NAMES
from ml.history import (HistoryStore, bootstrap_dataset, load_for_config,
                        store_for_config, triple_barrier_era)
from ml.overfit import (_fit_predict_arm, feature_dof_report,
                        model_space_pbo, train_test_gap)
from ml.walkforward import BAR_SECONDS, purged_walk_forward

_ROOT = Path(__file__).resolve().parents[1]

# The five offline consumers the audit enumerates. Every one of them loads
# the REAL training corpus, and the era/sample-weight knobs must reach all
# of them or none - that is the whole point of the shared seam.
_OFFLINE_CONSUMERS = ("train_meta.py", "overfit_check.py",
                      "learning_curve.py", "feature_stability.py",
                      "interpret_report.py")


# ---------------------------------------------------------------------------
# corpus fixtures
# ---------------------------------------------------------------------------
_EXTRA_COLS = ["label", "net_pnl_usd", "source", "ts", "signal_ts",
               "barrier", "probe", "disp", "candidate_id", "book",
               "label_era"]


def _write_corpus(path: Path, rows: list) -> None:
    """Minimal signal_history.csv the real loader accepts. `rows` are
    dicts overriding the defaults below."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ["position_id", "asset", "side", *FEATURE_NAMES, *_EXTRA_COLS]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for i, r in enumerate(rows):
            base = {"position_id": f"p{i}", "asset": r.get("asset", "ETH"),
                    "side": "long", "label": r.get("label", i % 2),
                    "net_pnl_usd": r.get("net_pnl_usd", "0.5"),
                    "source": r.get("source", "live"),
                    "ts": r.get("ts", 1_700_000_000 + 600 * i),
                    "signal_ts": r.get("signal_ts", 1_700_000_000 + 600 * i),
                    "barrier": r.get("barrier", "tb_pt"),
                    "probe": r.get("probe", "0"), "disp": "", "book": "5m",
                    "candidate_id": "",
                    "label_era": r.get("label_era", "triple_barrier_h24")}
            for n in FEATURE_NAMES:
                base[n] = r.get(n, 0.0)
            w.writerow(base)


def _era_split_corpus(path: Path, n_each: int = 6) -> None:
    """n_each rows in the ENGINE era (triple_barrier_h24) and n_each in
    the LEGACY one (triple_barrier), distinguishable by their label."""
    rows = []
    for i in range(n_each):
        rows.append({"label_era": "triple_barrier_h24", "label": 1,
                     "ret_1_dir": 0.5 + 0.01 * i})
    for i in range(n_each):
        rows.append({"label_era": "triple_barrier", "label": 0,
                     "ret_1_dir": -0.5 - 0.01 * i})
    _write_corpus(path, rows)


# ---------------------------------------------------------------------------
# H12 - the era the offline lane resolves
# ---------------------------------------------------------------------------
def test_store_for_config_resolves_the_engine_era_not_the_legacy_default(
        tmp_path):
    """main.py:714-719 passes max_bars=ml.label_max_bars; every offline
    consumer used the bare constructor, whose default is the legacy 96.
    config_guard FATALs label_max_bars >= max_bars_no_progress (36), so a
    valid live config can NEVER be 96 - the drift was structural."""
    ml_cfg = {"history_path": str(tmp_path / "h.csv"), "label_max_bars": 24}
    store = store_for_config(ml_cfg)

    assert store.max_bars == 24
    assert triple_barrier_era(store.max_bars) == "triple_barrier_h24"
    # the legacy default is untouched for direct callers (extend, don't break)
    assert HistoryStore(str(tmp_path / "h.csv")).max_bars == 96
    assert triple_barrier_era(96) == "triple_barrier"


def test_store_for_config_matches_the_shipped_config_era():
    """The invariant the audit asks for: EVERY load_training_data consumer
    resolves the same triple_barrier_era(config.ml.label_max_bars) main.py
    does. Read from the shipped config so a future retune cannot re-open
    the split silently."""
    shipped = json.loads((_ROOT / "config.json").read_text(encoding="utf-8"))
    ml_cfg = shipped.get("ml", {})
    engine_era = triple_barrier_era(int(ml_cfg.get("label_max_bars", 96)))

    store = store_for_config(ml_cfg)
    assert triple_barrier_era(store.max_bars) == engine_era
    # and the shipped config is genuinely NOT the legacy horizon, i.e. this
    # assertion is not vacuous
    assert engine_era != "triple_barrier"


def test_offline_era_filter_kept_the_exact_complement_of_production(tmp_path):
    """The measured defect, reproduced small: with era exclusion armed,
    the 24-bar store keeps ONLY engine-era rows and the 96-bar store keeps
    ONLY legacy rows - disjoint sets, both non-empty. The offline lane was
    auditing (and train_meta deploying) production's complement."""
    corpus = tmp_path / "hist.csv"
    _era_split_corpus(corpus)
    era_cfg = {"min_new_era_rows": 2}

    engine = HistoryStore(str(corpus), max_bars=24)
    Xe, ye, _we = engine.load_training_data(era_cfg=era_cfg)
    legacy = HistoryStore(str(corpus))          # the old offline default
    Xl, yl, _wl = legacy.load_training_data(era_cfg=era_cfg)

    assert len(Xe) and len(Xl), "both eras must be represented"
    assert set(ye.tolist()) == {1.0} and set(yl.tolist()) == {0.0}, (
        "the two eras must be disjoint row sets, which is the defect")

    shared = store_for_config({"history_path": str(corpus),
                               "label_max_bars": 24})
    Xs, ys, _ws = shared.load_training_data(era_cfg=era_cfg)
    assert np.array_equal(Xs, Xe) and np.array_equal(ys, ye), (
        "the shared seam must load exactly what the engine loads")


def test_no_offline_consumer_constructs_a_bare_history_store():
    """Anti-regression for "a future knob threaded to one consumer and not
    the rest": the five offline consumers must build their store through
    ml.history.store_for_config, never by calling HistoryStore(...)
    themselves. (feature_stability keeps HistoryStore as its injectable
    store_factory DEFAULT - a reference, not a call - which this allows.)"""
    offenders = []
    for name in _OFFLINE_CONSUMERS:
        path = _ROOT / "scripts" / name
        text = path.read_text(encoding="utf-8")
        # AST, not a substring scan: every one of these files DOCUMENTS the
        # old bare-constructor defect in prose, and a text match would pin
        # the comments rather than the code.
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and \
                    isinstance(node.func, ast.Name) and \
                    node.func.id == "HistoryStore":
                offenders.append(f"{name}:{node.lineno}")
        assert "store_for_config" in text, f"{name} bypasses the shared seam"
    assert offenders == []


def test_feature_stability_load_corpus_threads_the_configured_era(tmp_path):
    """load_corpus builds via the injectable store_factory; the horizon
    must reach it. (This screen discards its weight vector, so the
    sample-weight kwargs are correctly NOT threaded here.)"""
    from scripts.feature_stability import load_corpus

    seen = {}

    class _Store:
        def __init__(self, path, max_bars=96):
            self.path = path
            seen["max_bars"] = int(max_bars)
            self.last_load_stats = {"live_clean": 3}

        def load_training_data(self, return_sig=True, weights_cfg=None,
                               era_cfg=None):
            return np.zeros((4, 3)), np.zeros(4), None, np.arange(4.0)

        def source_counts(self):
            return {"live": 3}

    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"ml": {"history_path": "x",
                                      "label_max_bars": 24}}),
                   encoding="utf-8")
    load_corpus(str(cfg), min_rows=1, store_factory=_Store)
    assert seen["max_bars"] == 24


# ---------------------------------------------------------------------------
# LOW - ml.sample_weights must be read, not hardcoded
# ---------------------------------------------------------------------------
class _KwargSpyStore:
    """Records the exact load_training_data kwargs a consumer sends."""

    def __init__(self, path="x", max_bars=96):
        self.path = Path(path)
        self.max_bars = int(max_bars)
        self.last_load_stats = {"live_clean": 7}
        self.seen: dict = {}

    def load_training_data(self, **kwargs):
        self.seen = dict(kwargs)
        n = 4
        empty = (np.zeros((n, len(FEATURE_NAMES))), np.zeros(n), np.ones(n))
        if kwargs.get("return_label_times"):
            return (*empty, np.arange(float(n)), np.arange(float(n)))
        if kwargs.get("return_sig"):
            return (*empty, np.arange(float(n)))
        return empty

    def source_counts(self):
        return {"live": 99}


_TUNED_WEIGHTS = {"half_life_days": 11, "candidate_weight": 0.33,
                  "manip_discount": 0.77, "uniqueness_enabled": True}


def test_load_for_config_sources_every_sample_weight_knob_from_config():
    """main.py:5673-5675 resolves half_life_days/candidate_weight/
    manip_discount from ml.sample_weights; the offline consumers passed
    literals (train_meta omitted manip_discount entirely), so a retuned
    value was honored by the in-process retrain and silently ignored by
    the CLI that ships the artifact."""
    store = _KwargSpyStore()
    load_for_config(store, {"sample_weights": _TUNED_WEIGHTS,
                            "era_exclusion": {"min_new_era_rows": 5}},
                    return_label_times=True)

    assert store.seen["half_life_days"] == 11.0
    assert store.seen["candidate_weight"] == 0.33
    assert store.seen["manip_discount"] == 0.77
    assert store.seen["weights_cfg"] == _TUNED_WEIGHTS
    assert store.seen["era_cfg"] == {"min_new_era_rows": 5}
    assert store.seen["return_label_times"] is True


def test_load_for_config_defaults_are_the_previously_hardcoded_literals():
    """Behavior-preserving lift: an empty ml block must reproduce the exact
    literals the consumers used to hardcode."""
    store = _KwargSpyStore()
    load_for_config(store, {})
    assert store.seen["half_life_days"] == 30.0
    assert store.seen["candidate_weight"] == 0.4
    assert store.seen["manip_discount"] == 0.5


def test_overfit_check_load_dataset_reads_the_configured_weights(monkeypatch):
    import scripts.overfit_check as oc

    store = _KwargSpyStore()
    monkeypatch.setattr(oc, "store_for_config", lambda *a, **k: store)
    oc.load_dataset(force_synthetic=True,
                    ml_cfg={"sample_weights": _TUNED_WEIGHTS,
                            "era_exclusion": {}})

    assert store.seen["manip_discount"] == 0.77
    assert store.seen["half_life_days"] == 11.0


# ---------------------------------------------------------------------------
# M10 - bootstrap neutrals and the cold-start clock
# ---------------------------------------------------------------------------
def _candles(closes, t0=1_700_000_000):
    return [{"time": t0 + 300 * i, "close": c, "high": c * 1.01,
             "low": c * 0.99, "volume": 100.0 + i}
            for i, c in enumerate(closes)]


def _wave(n=700, period=6.0, base=100.0):
    t = np.arange(n)
    return list(base * (1.0 + 0.15 * np.sin(t / period)))


def test_bootstrap_writes_depth_ratio_at_its_live_neutral():
    """depth_ratio's live default is 1.0 ("depth is at its trailing
    median", ml/features.py:404); the zeros-init left every bootstrap row
    claiming zero depth, which ml/contracts.py's (0, 3) band admits
    silently. The 2026-07-29 neutrals block missed this one feature."""
    idx = FEATURE_NAMES.index("depth_ratio")
    X, _y = bootstrap_dataset(_candles(_wave()))
    assert len(X)
    assert np.allclose(X[:, idx], 1.0)


def test_bootstrap_return_sig_is_opt_in_and_carries_entry_bar_times():
    candles = _candles(_wave())
    X2, y2 = bootstrap_dataset(candles)                    # legacy arity
    X3, y3, sig = bootstrap_dataset(candles, return_sig=True)

    assert np.array_equal(X2, X3) and np.array_equal(y2, y3)
    assert len(sig) == len(X3)
    times = {c["time"] for c in candles}
    assert set(sig.tolist()) <= times, "sig must be entry-bar timestamps"
    assert np.all(np.diff(sig) > 0), "one symbol's block is already ordered"


def test_bootstrap_short_history_return_sig_arity():
    """The <300-candle early return must honor the new arity too."""
    short = _candles([100.0] * 50)
    assert len(bootstrap_dataset(short)) == 2
    X, y, sig = bootstrap_dataset(short, return_sig=True)
    assert len(X) == len(y) == len(sig) == 0


# ---------------------------------------------------------------------------
# train_meta end-to-end (H11, H12, M10, sample weights)
# ---------------------------------------------------------------------------
@pytest.fixture
def _isolated_audit(monkeypatch):
    """scripts.train_meta redirects the process-wide audit trail to
    outputs/ at IMPORT time; keep this test's records out of the live
    bot's directory entirely."""
    import core.audit as ca
    saved = ca._AUDIT
    yield
    monkeypatch.setattr(ca, "_AUDIT", saved, raising=False)


def _train_meta_config(tmp_path: Path, corpus: Path, **ml_over) -> Path:
    ml = {"history_path": str(corpus), "label_max_bars": 24,
          "min_train_rows": 4, "model_path": str(tmp_path / "meta.json"),
          "retrain_history_path": str(tmp_path / "retrain.jsonl"),
          "sample_weights": dict(_TUNED_WEIGHTS),
          "era_exclusion": {"min_new_era_rows": 2},
          "label_mode": "triple_barrier", "monitor": {}}
    ml.update(ml_over)
    cfg = {"ml": ml, "system": {"state_path": str(tmp_path / "state.json")},
           "exchanges": {"okx": {"symbols": ["ETH-USDT-SWAP",
                                             "BTC-USDT-SWAP"]}}}
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


def _stub_evaluate_and_select(captured: dict):
    def _fake(X, y, **kw):
        captured["X"], captured["y"] = X, y
        captured.update(kw)
        n = min(len(X), 40)
        oof_y = np.array([float(i % 2) for i in range(n)])
        oof_p = np.clip(0.4 + 0.2 * oof_y, 0.01, 0.99)
        return {"selected": "logistic", "admitted": ["logistic"], "gated": [],
                "model": object(), "oof_idx": np.arange(n),
                "importance": [],
                "logistic": {"oof_p": oof_p, "oof_y": oof_y,
                             "mean_brier": 0.2, "calib_gap": 0.01}}
    return _fake


def _run_train_meta(monkeypatch, cfg_path: Path, argv_extra=()) -> dict:
    import scripts.train_meta as tm

    captured: dict = {}
    monkeypatch.setattr(tm, "evaluate_and_select",
                        _stub_evaluate_and_select(captured))
    monkeypatch.setattr(tm, "_deploy_challenger",
                        lambda *a, **k: captured.setdefault("deployed", False))
    monkeypatch.setattr(sys, "argv",
                        ["train_meta.py", "--config", str(cfg_path),
                         *argv_extra])
    captured["rc"] = tm.main()
    return captured


def test_train_meta_evidence_gate_counts_live_clean_not_the_raw_csv(
        monkeypatch, tmp_path, _isolated_audit):
    """H11: the gate read source_counts()["live"] - a raw header-indexed
    scan applying NONE of the loader's admissibility rules (book=="long"
    exclusion, dirty drops, era exclusion). Measured live: 275 vs 0, which
    is the difference between admitting {mlp, adaptive_gbt, ...} and
    {logistic}. This CLI is the only real-corpus consumer that writes a
    DEPLOYABLE artifact."""
    corpus = tmp_path / "hist.csv"
    rows = [{"label_era": "triple_barrier_h24", "label": i % 2,
             "source": "live", "ret_1_dir": 0.01 * i} for i in range(60)]
    # live, but excluded by the era filter - counted by the raw scan anyway
    rows += [{"label_era": "triple_barrier", "label": i % 2, "source": "live",
              "ret_1_dir": -0.01 * i} for i in range(20)]
    _write_corpus(corpus, rows)

    cap = _run_train_meta(monkeypatch, _train_meta_config(tmp_path, corpus))

    from ml.history import HistoryStore as _HS
    raw_live = _HS(str(corpus), max_bars=24).source_counts().get("live", 0)
    assert raw_live == 80, "the raw scan sees every live row in the file"
    assert cap["n_live"] == 60, (
        "the evidence gate must count the loader's own clean/era-filtered "
        f"live rows, not the raw {raw_live}")

    record = json.loads(
        (tmp_path / "retrain.jsonl").read_text(encoding="utf-8").strip())
    assert record["live"] == 60, "the audit log must record the honest count"


def test_train_meta_loads_the_engine_era_and_the_configured_weights(
        monkeypatch, tmp_path, _isolated_audit):
    """H12 + sample weights, at the script that DEPLOYS: the CLI must load
    exactly the rows main.py loads, with the config's own weight knobs."""
    corpus = tmp_path / "hist.csv"
    _era_split_corpus(corpus, n_each=60)     # >= train_meta's own 60-row floor

    seen: dict = {}
    real_load = mlh.HistoryStore.load_training_data

    def _spy(self, **kw):
        seen.update(kw)
        seen["max_bars"] = self.max_bars
        return real_load(self, **kw)

    monkeypatch.setattr(mlh.HistoryStore, "load_training_data", _spy)
    cap = _run_train_meta(monkeypatch, _train_meta_config(tmp_path, corpus))

    assert seen["max_bars"] == 24, "era must come from ml.label_max_bars"
    assert seen["manip_discount"] == 0.77
    assert seen["half_life_days"] == 11.0
    # only the engine-era rows (label 1) reached the fit
    assert set(cap["y"].tolist()) == {1.0}


class _FakeOKX:
    """Two symbols over the SAME ~10-day window - the shipped shape."""

    def __init__(self, _cfg):
        pass

    def get_history_candles(self, symbol, bar="5m", total=2880):
        # ~2000 bars each: enough EMA crosses (>=100/symbol) that
        # purged_walk_forward actually yields folds, which is what makes
        # the leak below measurable rather than vacuous.
        base = 100.0 if symbol.startswith("ETH") else 2000.0
        phase = 0.0 if symbol.startswith("ETH") else 3.0
        t = np.arange(2000)
        closes = list(base * (1.0 + 0.15 * np.sin(t / 6.0 + phase)))
        return _candles(closes)

    def get_candles(self, symbol, bar="5m", limit=300):
        return self.get_history_candles(symbol)


def test_cold_start_bootstrap_keeps_one_global_clock(monkeypatch, tmp_path,
                                                     _isolated_audit):
    """M10: each symbol's block was vstacked WHOLE and then `sig` was
    discarded, so purged_walk_forward fell back to the row-count purge -
    documented "correct ONLY if rows are evenly spaced in time". Because
    both blocks cover the same calendar window, training rows had signal
    timestamps strictly LATER than the entire test block. Measured OOF
    Brier optimism rose monotonically with cross-asset correlation
    (rho=0.85 -> -0.0138, 2.7x challenger_brier_margin)."""
    import data.okx_feed as okx_mod

    monkeypatch.setattr(okx_mod, "OKXFeed", _FakeOKX)
    corpus = tmp_path / "hist.csv"
    _write_corpus(corpus, [{"label_era": "triple_barrier_h24", "label": i % 2,
                            "ret_1_dir": 0.1 * i} for i in range(4)])
    cap = _run_train_meta(monkeypatch, _train_meta_config(tmp_path, corpus),
                          argv_extra=("--bootstrap",))

    X, sig = cap["X"], cap["sig"]
    assert sig is not None, (
        "a cold-start mix must keep a coherent clock, not fall back to the "
        "row-count purge")
    assert len(sig) == len(X)
    assert np.all(np.diff(sig) >= 0), "the matrix must be sorted on ONE clock"
    assert len(np.unique(sig)) < len(sig), (
        "both symbol blocks share timestamps, so a merged clock must show "
        "ties - a per-symbol vstack would not")

    # Rebuild the SHIPPED row order (live block, then one whole block per
    # symbol) and show the leak on it, then show the fix removes it. Same
    # rows, same labels - only the clock handling differs.
    fake = _FakeOKX(None)
    blocks = [bootstrap_dataset(fake.get_history_candles(s), max_bars=24,
                                label_mode="triple_barrier",
                                return_sig=True)[2]
              for s in ("ETH-USDT-SWAP", "BTC-USDT-SWAP")]
    live_sig = np.array([1_700_000_000.0 + 600.0 * i for i in range(4)])
    shipped_order = np.concatenate([live_sig, *blocks])
    assert np.array_equal(np.sort(shipped_order), sig), (
        "the fixed matrix must be exactly the shipped rows, re-sorted")

    span = 24
    horizon = span * BAR_SECONDS
    leaked = 0
    for tr, te in purged_walk_forward(len(shipped_order), 5, span, sig=None):
        leaked += int((shipped_order[tr] + horizon
                       > shipped_order[te[0]]).sum())
    assert leaked > 0, (
        "the shipped per-symbol vstack + row-count purge must leak, or this "
        "test is not pinning the defect")
    for tr, te in purged_walk_forward(len(X), 5, span, sig=sig):
        assert bool((sig[tr] + horizon <= sig[te[0]]).all()), (
            "the time purge must drop every row whose label window reaches "
            "the test block")


# ---------------------------------------------------------------------------
# H14 - the measured space must be fitted the way the deployed space is
# ---------------------------------------------------------------------------
def _weighted_world(n=200, seed=5):
    """First half: y = f>0. Second half: the INVERTED relationship. A fit
    that honors weights near zero on the second half learns the first
    half's rule; an unweighted fit learns the average of the two."""
    rng = np.random.default_rng(seed)
    f = rng.normal(size=n)
    X = np.column_stack([f, rng.normal(size=n), rng.normal(size=n)])
    y = np.where(np.arange(n) < n // 2, f > 0, f < 0).astype(float)
    w = np.where(np.arange(n) < n // 2, 1.0, 1e-6)
    return X, y, w


def test_fit_predict_arm_actually_honors_the_sample_weights():
    from ml.models import LogisticModel

    X, y, w = _weighted_world()
    folds = [(np.arange(0, 150), np.arange(150, 200))]
    oof_idx = np.arange(150, 200)

    def factory():
        return LogisticModel(seed=5)

    p_uniform, _ = _fit_predict_arm("a", factory, X, y, folds, oof_idx)
    p_weighted, _ = _fit_predict_arm("a", factory, X, y, folds, oof_idx,
                                     sample_weight=w)
    assert not np.allclose(p_uniform, p_weighted), (
        "weights must change the fit, or threading them is cosmetic")


def test_model_space_pbo_fits_every_arm_with_the_deployed_weights(monkeypatch):
    """The deployed selector fits every rung with sample_weight=w
    (ml/walkforward.py:302-303). model_space_pbo had no sample_weight
    parameter at all, so OF-3 certified a selection rule the bot does not
    run: per-family Brier moved 0.0012-0.0121 against a BRIER_MARGIN of
    0.002."""
    X, y, w = _weighted_world(n=600, seed=11)
    seen: list = []
    real = mlo._fit_predict_arm

    def _spy(*a, **kw):
        seen.append(kw.get("sample_weight"))
        return real(*a, **kw)

    monkeypatch.setattr(mlo, "_fit_predict_arm", _spy)
    model_space_pbo(X, y, label_span=10, n_splits=4, n_blocks=6, seed=13,
                    sample_weight=w)

    assert seen, "no arms were fitted - the assertion below would be vacuous"
    assert all(s is not None and np.array_equal(np.asarray(s), w)
               for s in seen), "every arm must be fitted with the same w"


def test_model_space_pbo_default_stays_unweighted():
    """The byte-identity contract: omitting sample_weight must reach the
    fit as None (tests/test_pbo_variants.py's _PINNED fixture was captured
    against the unweighted implementation and must keep passing)."""
    X, y, _w = _weighted_world(n=600, seed=11)
    seen: list = []
    real = mlo._fit_predict_arm

    def _spy(*a, **kw):
        seen.append(kw.get("sample_weight"))
        return real(*a, **kw)

    try:
        mlo._fit_predict_arm = _spy
        model_space_pbo(X, y, label_span=10, n_splits=4, n_blocks=6, seed=13)
    finally:
        mlo._fit_predict_arm = real
    assert seen and all(s is None for s in seen)


def test_feature_dof_report_permutes_the_weighted_model(monkeypatch):
    """OF-7 answers "which features does the DEPLOYED model use", so the
    gbt it permutes must be the weighted one."""
    X, y, w = _weighted_world(n=400, seed=7)
    seen: list = []
    real_cls = mlo.GradientBoostedStumps

    class _SpyGBT(real_cls):
        def fit(self, X, y, *a, **kw):
            seen.append(kw.get("sample_weight"))
            return super().fit(X, y, *a, **kw)

    monkeypatch.setattr(mlo, "GradientBoostedStumps", _SpyGBT)
    feature_dof_report(X, y, ["f0", "f1", "f2"], label_span=8, n_splits=4,
                       sample_weight=w)
    assert seen and seen[0] is not None
    assert np.array_equal(np.asarray(seen[0]), w[:len(seen[0])])

    seen.clear()
    feature_dof_report(X, y, ["f0", "f1", "f2"], label_span=8, n_splits=4)
    assert seen and seen[0] is None, "the default must stay unweighted"


# ---------------------------------------------------------------------------
# label span: thread `res`, NOT ml.label_max_bars
# ---------------------------------------------------------------------------
def _res_world(n=400):
    """Evenly spaced 5m signals whose labels all resolve one bar later, so
    the res-based purge (the deployed branch) keeps materially more
    training rows than the fixed label_span horizon."""
    rng = np.random.default_rng(3)
    sig = 1_700_000_000.0 + BAR_SECONDS * np.arange(n)
    res = sig + BAR_SECONDS
    X = rng.normal(size=(n, 4))
    y = (rng.random(n) < 1 / (1 + np.exp(-X[:, 0]))).astype(float)
    return X, y, sig, res


def test_res_purge_is_materially_different_from_the_span_purge():
    """Setup check for the two pins below: `res` is not a no-op here."""
    X, _y, sig, res = _res_world()
    span_only = [len(tr) for tr, _ in
                 purged_walk_forward(len(X), 5, 96, sig=sig)]
    with_res = [len(tr) for tr, _ in
                purged_walk_forward(len(X), 5, 96, sig=sig, res=res)]
    assert with_res != span_only
    assert all(a >= b for a, b in zip(with_res, span_only))


def test_train_test_gap_threads_res_to_the_deployed_purge(monkeypatch):
    """OF-1's label_span literal (96) drifting from ml.label_max_bars (24)
    is NOT fixed by wiring the config knob in: production passes res=res
    and purged_walk_forward IGNORES label_span in that branch, so span-24
    would UNDER-purge every fold. Threading res is the parity fix."""
    X, y, sig, res = _res_world()
    seen: list = []
    real = mlo.purged_walk_forward

    def _spy(*a, **kw):
        seen.append(kw.get("res"))
        return real(*a, **kw)

    monkeypatch.setattr(mlo, "purged_walk_forward", _spy)
    train_test_gap(X, y, n_splits=3, sig=sig, res=res)
    assert seen and all(s is not None for s in seen)
    assert np.array_equal(np.asarray(seen[0]), res)


def test_model_space_pbo_threads_res_to_the_deployed_purge(monkeypatch):
    X, y, sig, res = _res_world()
    seen: list = []
    real = mlo.purged_walk_forward

    def _spy(*a, **kw):
        seen.append(kw.get("res"))
        return real(*a, **kw)

    monkeypatch.setattr(mlo, "purged_walk_forward", _spy)
    model_space_pbo(X, y, label_span=96, n_splits=3, n_blocks=6, sig=sig,
                    res=res)
    assert seen and all(s is not None for s in seen)


# ---------------------------------------------------------------------------
# overfit_check main(): OF-5 / regime diagnostic corpus path + OF-1/3/7 wiring
# ---------------------------------------------------------------------------
def _stub_overfit_battery(monkeypatch, oc, calls: dict):
    """Neuter the expensive instruments so main()'s WIRING is what the
    test measures. Each stub records what it was handed."""
    n = 60
    X = np.zeros((n, len(FEATURE_NAMES)))
    y = np.array([float(i % 2) for i in range(n)])
    w = np.linspace(0.5, 1.5, n)
    sig = 1_700_000_000.0 + BAR_SECONDS * np.arange(n)
    res = sig + BAR_SECONDS

    def _load(**kw):
        calls["load_dataset"] = kw
        return X, y, w, sig, res, "SYNTHETIC benchmark (stubbed)", n

    def _gap(*a, **kw):
        calls["train_test_gap"] = kw
        return {}

    def _pbo(*a, **kw):
        calls["model_space_pbo"] = kw
        return {"pbo": None, "reason": "stubbed"}

    def _dof(*a, **kw):
        calls["feature_dof_report"] = kw
        return {"starved": False, "rows_per_feature": 99.0, "n_rows": n,
                "n_features": len(FEATURE_NAMES), "dead_feature_frac": 0.0,
                "dead_features": []}

    def _regime(gaps, X_, y_, on_synth, csv_path):
        calls["regime_csv_path"] = csv_path

    monkeypatch.setattr(oc, "load_dataset", _load)
    monkeypatch.setattr(oc, "train_test_gap", _gap)
    monkeypatch.setattr(oc, "model_space_pbo", _pbo)
    monkeypatch.setattr(oc, "feature_dof_report", _dof)
    monkeypatch.setattr(oc, "regime_diagnostic", _regime)
    monkeypatch.setattr(oc, "learning_curve_diagnostic",
                        lambda *a, **k: None)
    monkeypatch.setattr(oc, "extras_liveness_diagnostic", lambda *a, **k: None)
    monkeypatch.setattr(oc, "shuffled_label_check",
                        lambda *a, **k: {"ok": True, "mean_auc": 0.5,
                                         "z": 0.0, "z_limit": 3.0})
    monkeypatch.setattr(oc, "purge_leakage_probe",
                        lambda *a, **k: {"purge_does_not_inflate": True,
                                         "unpurged_oof_auc": 0.5,
                                         "purged_oof_auc": 0.5,
                                         "leak_closed": 0.0})
    monkeypatch.setattr(oc, "make_offline_recording", lambda *a, **k: "")
    monkeypatch.setattr(oc, "strategy_plateau", lambda *a, **k: None)
    monkeypatch.setattr(oc, "PASS_N", 0)
    monkeypatch.setattr(oc, "FAIL_N", 0)
    monkeypatch.setattr(oc, "REPORT", [])
    return w, res


def test_overfit_check_reads_the_configured_corpus_and_ships_deployed_parity(
        monkeypatch, tmp_path):
    """Three fixes in one run of main():
      * OF-5 and the regime diagnostic used a bare HistoryStore() - the
        hardcoded default path, the exact desync the ML layer already
        fixed at load_dataset. After a rotation/repoint they emit a
        confident DSR verdict on the WRONG sample.
      * OF-1 must get `res`, OF-3 must get `res` AND the deployed sample
        weights, OF-7 must get the weights.
    cwd-relative resolution is preserved (tests/test_overfit_check_ci.py
    :39-44 depends on it), which is why the corpus below is a RELATIVE
    path written under the test's cwd."""
    import main as engine_main
    import scripts.overfit_check as oc

    rel = "corpus/hist.csv"
    corpus = tmp_path / rel
    corpus.parent.mkdir(parents=True, exist_ok=True)
    # 20 live rows: below OF-5's 30-outcome evidence floor on purpose, so
    # the gate reports DEFERRED either way and this test can never depend
    # on the shipped ml.exploration.enabled flag - what it measures is
    # WHICH FILE the sample came from, not the verdict.
    rows = ["position_id,net_pnl_usd,source,probe"] + [
        f"p{i},{0.20 + 0.01 * i},live," for i in range(20)]
    corpus.write_text("\n".join(rows) + "\n", encoding="utf-8")

    cfg = {"ml": {"history_path": rel, "label_max_bars": 24,
                  "sample_weights": dict(_TUNED_WEIGHTS),
                  "era_exclusion": {}, "exploration": {"enabled": False}}}
    monkeypatch.setattr(engine_main, "load_config", lambda _p: cfg)

    calls: dict = {}
    w, res = _stub_overfit_battery(monkeypatch, oc, calls)
    report = tmp_path / "report.md"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv",
                        ["overfit_check.py", "--quick", "--force-synthetic",
                         "--report-path", str(report)])
    rc = oc.main()

    assert rc == 0, report.read_text(encoding="utf-8")
    text = report.read_text(encoding="utf-8")
    # OF-5 read the CONFIGURED corpus (20 live rows), not the hardcoded
    # outputs/signal_history.csv default - which does not exist under this
    # cwd, so the old code reported an EMPTY sample.
    assert "mixed n=20" in text or "20 live labeled trades" in text, text
    # word-boundary anchored (2026-08-09): a bare substring test read
    # "2>0< live labeled trades" as the empty-sample string it was meant to
    # forbid, so this assertion failed on a report that PROVES the fix.
    # The flip that surfaced it is itself the improvement: OF-5's phase
    # flag is now resolved once through main.load_config (injectable, so
    # THIS test's cfg decides), where it used to re-read the shipped
    # repo config.json off disk and ignore the injected one - which is
    # exactly the independence this test's docstring asks for.
    assert not re.search(r"\b0 live labeled trades", text), text
    assert "mixed n=0" not in text, text
    # ...and the regime diagnostic was handed the same file
    assert Path(calls["regime_csv_path"]) == Path(rel)

    assert calls["load_dataset"]["ml_cfg"] is cfg["ml"]
    assert np.array_equal(calls["train_test_gap"]["res"], res)
    assert np.array_equal(calls["model_space_pbo"]["res"], res)
    assert np.array_equal(calls["model_space_pbo"]["sample_weight"], w)
    assert np.array_equal(calls["feature_dof_report"]["sample_weight"], w)

# ---------------------------------------------------------------------------
# OF-7 reports EFFECTIVE n (2026-09-15). The gate itself is NOT re-registered:
# every pin below either measures the new report-only line or pins that the
# old check still reads the nominal count it was registered on.
# ---------------------------------------------------------------------------

def test_dof_effective_n_equals_nominal_when_labels_never_overlap():
    """The calibration arm. Disjoint label spans ARE independent, so the
    deflation must be exactly 1.0 - not merely 'close'. Without this arm a
    dof_effective_n that always returned n would pass every other pin.

    DISJOINT MEANS DISJOINT AT BAR RESOLUTION. The route quantises to
    ml.corpus._UNIQ_GRID_SEC (300 s), so two labels 100 s apart share a bar
    and ARE concurrent by this measure - the first version of this fixture
    used 50 s spans at 100 s spacing and read n_eff=14 of 40, which is the
    helper being right and the fixture being wrong. Spacing here is a full
    bar, which is also the corpus's own resolution (median live span 35,464
    s ~ 118 bars, so the quantisation is irrelevant at OF-7's real scale).
    """
    import scripts.overfit_check as oc
    n = 40
    sig = [float(i * 600) for i in range(n)]
    res = [float(i * 600 + 300) for i in range(n)]
    d = oc.dof_effective_n(sig, res, 4)
    assert d["available"]
    assert abs(d["n_eff"] - n) < 1e-6, "disjoint labels were deflated"
    assert abs(d["se_inflation"] - 1.0) < 1e-6
    assert abs(d["rows_per_feature_effective"]
               - d["rows_per_feature_nominal"]) < 1e-6


def test_dof_effective_n_collapses_when_every_label_shares_one_path():
    """The other end. N rows on ONE identical span are one observation, and
    that is the whole reason this line exists."""
    import scripts.overfit_check as oc
    n = 40
    d = oc.dof_effective_n([0.0] * n, [1000.0] * n, 4)
    assert d["available"]
    assert d["n_eff"] <= 1.5, f"fully concurrent rows kept n_eff={d['n_eff']}"
    assert d["rows_per_feature_effective"] < d["rows_per_feature_nominal"]
    assert d["se_inflation"] > 4.0, "the SE inflation was not reported"


def test_of7_still_gates_on_the_nominal_count_it_was_registered_on():
    """THE REGISTRATION PIN, and the reason the rest of this is an info()
    line. Build a corpus that is comfortably un-starved nominally and
    badly starved effectively; OF-7's `starved` verdict must be unmoved.

    Re-pointing a pre-registered gate at a different quantity after seeing
    the data is the move CLAUDE.md's overfit-discipline section forbids -
    raising the bar on a new quantity is lowering a floor wearing a hat.
    If someone later wires the effective figure into `starved`, this pin
    goes red and the conversation happens before the change ships."""
    import scripts.overfit_check as oc
    X, y, w = _weighted_world(n=400, seed=7)
    dof = feature_dof_report(X, y, ["f0", "f1", "f2"], label_span=8,
                             n_splits=4, sample_weight=w)
    assert dof["rows_per_feature"] >= 10.0
    assert dof["starved"] is False, "nominal precondition broke"

    # same rows, all concurrent -> effectively starved many times over
    eff = oc.dof_effective_n([0.0] * len(y), [1000.0] * len(y),
                             dof["n_features"])
    assert eff["available"]
    assert eff["rows_per_feature_effective"] < 10.0, "fixture not starved"
    assert dof["starved"] is False,         "OF-7's gate moved onto the effective count - that is a silent "         "re-registration of a pre-registered gate"


def test_dof_effective_n_says_so_instead_of_guessing_when_spans_are_degenerate():
    """Fail LOUD, not silently-nominal. A corpus whose resolution stamps
    never exceed their signal stamps carries no concurrency information,
    and the caller must be told that rather than handed n_eff == n."""
    import scripts.overfit_check as oc
    d = oc.dof_effective_n([5.0, 6.0, 7.0], [5.0, 6.0, 7.0], 3)
    assert d["available"] is False
    assert "degenerate" in d["reason"] or "resolution_ts" in d["reason"]
    assert "rows_per_feature_effective" not in d

    # A LENGTH MISMATCH is a different fault and must say so. Dropping the
    # guard still yields available=False (the zip raises and the broad
    # except swallows it), so asserting only that flag left the guard
    # untested - a mutation sweep proved it by deleting the guard with no
    # pin going red. What the guard actually buys is the message.
    mismatched = oc.dof_effective_n([1.0, 2.0], [5.0], 3)
    assert mismatched["available"] is False
    assert "len(sig)=2" in mismatched["reason"], mismatched["reason"]
    assert "len(res)=1" in mismatched["reason"], mismatched["reason"]
    assert "Error" not in mismatched["reason"],         "the mismatch escaped the guard and came back as a raw exception"

    empty = oc.dof_effective_n([], [], 3)
    assert empty["available"] is False


def test_dof_effective_n_never_claims_more_evidence_than_rows_exist(monkeypatch):
    """The clamp. n_eff > n would read as evidence nobody collected, and
    would flip se_inflation below 1.0 - an SE claimed BETTER than nominal,
    from a deflation whose entire job is to make it worse.

    THE CLAMP MUST BE INJECTED TO BE TESTED. Real uniqueness is <= 1 per
    row, so a healthy upstream can never return n_eff > n and an honest
    fixture cannot exercise the clamp: a mutation sweep deleted it and all
    six pins stayed green. The clamp is defence against a BROKEN upstream,
    so the broken upstream is what the pin has to supply.
    """
    import scripts.overfit_check as oc
    n = 12
    sig = [float(i) for i in range(n)]
    res = [float(i) + 0.5 for i in range(n)]

    d = oc.dof_effective_n(sig, res, 3)          # honest arm
    assert d["available"]
    assert d["n_eff"] <= n
    assert d["se_inflation"] >= 1.0

    import ml.corpus as mc
    monkeypatch.setattr(mc, "effective_n", lambda rows: (10_000.0, 1.0))
    blown = oc.dof_effective_n(sig, res, 3)
    assert blown["n_eff"] <= n,         "an upstream n_eff larger than the row count was passed through"
    assert blown["se_inflation"] >= 1.0,         "the SE was reported BETTER than nominal - the clamp is gone"

    monkeypatch.setattr(mc, "effective_n", lambda rows: (0.0, 0.0))
    zeroed = oc.dof_effective_n(sig, res, 3)
    assert zeroed["n_eff"] >= 1.0, "n_eff of 0 would divide by zero"


def test_dof_effective_n_names_its_route_as_a_bound_not_an_answer():
    """Provenance. The asset-blind route counts two different assets'
    overlapping labels as one path, so it is a LOWER bound on n_eff. A
    reader who takes it for THE effective n under-reads the corpus; the
    dict has to carry its own direction."""
    import scripts.overfit_check as oc
    d = oc.dof_effective_n([0.0, 1.0], [10.0, 11.0], 2)
    assert "asset-blind" in d["route"]
    assert "lower bound" in d["route"]

def test_dof_effective_n_stays_cheap_on_a_corpus_sized_input():
    """THE PIN THIS FUNCTION WAS MISSING, and the defect is mine.

    The first draft reused scripts.cohort_eval.cohort_effective_n because
    scripts/overfit_check.py already imports it for the OF-5 sentinel. That
    helper is written for a cohort of ~50 TRIPS and is O(n^3): an outer loop
    over spans, a middle loop over ~2n sorted endpoints, and a full rescan
    of every span inside both. OF-7's input is the TRAINING CORPUS - 19,203
    usable spans measured live, i.e. ~1.4e13 operations. The battery was
    killed after 16 minutes having printed nothing, and because its stdout
    was block-buffered to a file there was no partial output to diagnose
    from; the wedge was found by reading the callee, not by watching it.

    A neighbour's helper is not free just because it is already imported:
    its COMPLEXITY is part of its interface, and nothing in this repo's
    gates measures that. This pin does, at a size no unit test would
    otherwise reach. The bar-grid route runs the real 19k corpus in ~0.8 s;
    the O(n^3) route at 2,500 spans alone is ~3e10 operations and cannot
    finish inside this budget.

    THE CALL RUNS IN A JOINABLE DAEMON THREAD, not inline. An elapsed-time
    assertion placed after the call can only catch a SLOWDOWN; it cannot
    catch the actual failure mode, which is that the call never returns and
    takes the whole suite with it. join(timeout) turns a hang into a red.
    """
    import threading
    import time

    import scripts.overfit_check as oc
    n = 2_500
    sig = [float(i * 60) for i in range(n)]
    res = [float(i * 60 + 36_000) for i in range(n)]   # heavily overlapping
    box: dict = {}

    def _run():
        box["d"] = oc.dof_effective_n(sig, res, 64)

    th = threading.Thread(target=_run, daemon=True)
    t0 = time.time()
    th.start()
    th.join(20.0)
    elapsed = time.time() - t0
    assert not th.is_alive(), (
        f"dof_effective_n had not returned after {elapsed:.0f}s on {n} "
        f"overlapping spans - that is the O(n^3) route, not the bar-grid one")
    d = box["d"]
    assert d["available"], d.get("reason")
    # and it must still be MEASURING, not short-circuiting to nominal
    assert d["n_eff"] < n, "heavily overlapping spans were not deflated"

def test_dof_effective_n_quantises_to_the_five_minute_bar():
    """The quantisation is a PROPERTY, not an artefact, and a reader who
    does not know it will misread a small-span corpus as more dependent
    than it is. Sub-bar separation is concurrency by this measure; the
    route's grid is the same 5 m bar the corpus itself is built on."""
    import scripts.overfit_check as oc
    n = 12
    tight = oc.dof_effective_n([float(i * 10) for i in range(n)],
                               [float(i * 10 + 5) for i in range(n)], 4)
    spaced = oc.dof_effective_n([float(i * 600) for i in range(n)],
                                [float(i * 600 + 300) for i in range(n)], 4)
    assert tight["available"] and spaced["available"]
    assert tight["n_eff"] < spaced["n_eff"],         "sub-bar-spaced labels were not treated as concurrent"
    assert abs(spaced["n_eff"] - n) < 1e-6

def test_dof_effective_n_survives_the_synthetic_paths_none_label_times():
    """load_dataset returns (Xs, ys, None, None, None, ...) on the SYNTHETIC
    benchmark - its own docstring says so in as many words - and the first
    version of dof_effective_n took len(sig) OUTSIDE its try, so len(None)
    raised a TypeError that CRASHED THE WHOLE BATTERY to a non-zero exit.

    A REPORT-ONLY LINE TAKING DOWN THE GATE IT REPORTS ON is the worst
    failure available to SAFE-class code, and the live-corpus run this was
    developed against could never have shown it: on that path sig and res
    are real arrays. Eight suite tests did catch it - every one of them by
    running the battery as a SUBPROCESS, costing 3m45s to say 'TypeError'.
    This pin says the same thing in microseconds and names the cause, which
    is the difference between a gate that catches a defect and a gate
    someone will be tempted to skip.
    """
    import scripts.overfit_check as oc
    for sig, res in ((None, None), (None, [1.0, 2.0]), ([1.0, 2.0], None)):
        d = oc.dof_effective_n(sig, res, 64)          # must not raise
        assert d["available"] is False, (sig, res)
        assert d["n"] == 0, (sig, res)
        assert "None" in d["reason"] or "label times" in d["reason"], d
        # and the caller's formatting path must survive the result too
        assert "rows_per_feature_effective" not in d

