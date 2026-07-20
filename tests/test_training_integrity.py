"""#51 batch: training-integrity trio (LP-1, LP-4, LP-6).

LP-1  the time purge assumed every label resolves at signal + label_span,
      but live rows held past the window resolve at CLOSE — their labels
      leaked into training folds that precede their resolution.
LP-4  ml/contracts.check_matrix existed but was wired into NEITHER train
      path — poisoned rows entered the fit the inference contract would
      have refused to score.
LP-6  the CLI retrain fabricated oof_brier=0.25 when zero OOF predictions
      existed and walked it into the champion gate as if measured.
"""
import numpy as np

from ml.walkforward import BAR_SECONDS, purged_walk_forward

ROOT_SPAN = 96 * BAR_SECONDS


def _grid(n, step=600.0, t0=1_000_000.0):
    return np.array([t0 + i * step for i in range(n)])


# --- LP-1: resolution-aware purge -------------------------------------------
def test_res_purge_drops_long_held_live_row():
    n = 400
    sig = _grid(n)
    res = sig + 60.0                       # candidates: resolve quickly
    # one live row early in the train block whose label resolves DAYS later
    res[10] = sig[-1] + 5 * 86400.0
    folds = list(purged_walk_forward(n, n_splits=3, label_span=96,
                                     sig=sig, res=res))
    assert folds, "folds must still be produced"
    for train_idx, test_idx in folds:
        assert 10 not in train_idx, \
            "a row whose label resolves after the test opens must be purged"
        # its neighbors (resolved long before) stay
        assert 9 in train_idx and 11 in train_idx


def test_res_purge_keeps_normally_resolved_rows():
    n = 400
    sig = _grid(n)
    res = sig + 60.0
    with_res = [(set(a), set(b)) for a, b in
                purged_walk_forward(n, 3, 96, sig=sig, res=res)]
    # fast-resolving rows: the res purge keeps MORE than the fixed-horizon
    # purge (which assumes every label spans the full 8h window)
    fixed = [(set(a), set(b)) for a, b in
             purged_walk_forward(n, 3, 96, sig=sig)]
    for (ta, sa), (tf, sf) in zip(with_res, fixed):
        assert sa == sf, "test blocks identical"
        assert ta >= tf, "res-aware purge never keeps less than fixed-horizon"


def test_legacy_paths_unchanged():
    n = 400
    sig = _grid(n)
    legacy_time = list(purged_walk_forward(n, 3, 96, sig=sig))
    legacy_rows = list(purged_walk_forward(n, 3, 96))
    assert legacy_time and legacy_rows      # both modes still yield folds
    # res=None is byte-identical to the sig-only path
    same = list(purged_walk_forward(n, 3, 96, sig=sig, res=None))
    for (a1, b1), (a2, b2) in zip(legacy_time, same):
        assert np.array_equal(a1, a2) and np.array_equal(b1, b2)


# --- LP-1 loader: resolution times surface, ordered with sig ----------------
def test_loader_returns_label_times(tmp_path):
    from ml.features import FEATURE_NAMES
    from ml.history import HistoryStore
    hs = HistoryStore(str(tmp_path / "h.csv"))
    f = np.zeros(len(FEATURE_NAMES))
    hs.log_entry("p1", "ETH", "long", f)
    hs.log_close("p1", 5.0)
    X, y, w, sig, res = hs.load_training_data(return_label_times=True)
    assert len(res) == len(sig) == 1
    assert res[0] >= sig[0], "a label resolves at/after its signal"


# --- LP-4: both train paths screen through the contract ---------------------
def test_both_train_paths_wire_the_contract_screen():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for path in ("main.py", "scripts/train_meta.py"):
        src = (root / path).read_text(encoding="utf-8")
        assert 'get_contract().check_matrix(X)["keep"]' in src, path
        assert "return_label_times=True" in src, path
        assert "res=res" in src, path


def test_check_matrix_drops_poisoned_rows():
    from ml.contracts import get_contract
    from ml.features import FEATURE_NAMES
    good = np.zeros((3, len(FEATURE_NAMES)))
    bad = good.copy()
    bad[1, 0] = float("nan")
    out = get_contract().check_matrix(bad)
    assert out["dropped"] == 1 and out["keep"].tolist() == [True, False, True]


# --- LP-6: no fabricated OOF Brier -------------------------------------------
def test_cli_refuses_unmeasured_challenger():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] /
           "scripts" / "train_meta.py").read_text(encoding="utf-8")
    assert "else 0.25" not in src, "fabricated OOF Brier must be gone"
    assert "refusing to deploy an unmeasured challenger" in src
