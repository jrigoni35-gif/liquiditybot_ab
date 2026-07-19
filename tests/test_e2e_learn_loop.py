"""E2E happy-path: the LEARNING journey, end to end, deterministic and
network-free. This is the bot's core "user journey" for the model brain:

    a paper trade is entered  ->  it closes  ->  the realized outcome becomes
    a LIVE ground-truth label  ->  source_counts reflects it  ->  the
    method-selection brain (admissible_families / evaluate_and_select) reacts
    to how much GROUND TRUTH has accrued, admitting complexity only when the
    live evidence earns it.

Prod-like: real CSV files under tmp_path (the actual persistence the running
bot uses), the real HistoryStore and walk-forward selector. Happy path first;
one error-path assertion proves a dirty label can't corrupt the journey.
"""
import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import HistoryStore
from ml.walkforward import admissible_families, evaluate_and_select

_SEL_CFG = {"enabled": True,
            "min_live_rows": {"gbt": 60, "blend": 60, "mlp": 150,
                              "adaptive_gbt": 250},
            "min_total_rows": {"gbt": 150, "blend": 150, "mlp": 400,
                               "adaptive_gbt": 600}}


def _feats(seed):
    rng = np.random.default_rng(seed)
    return rng.normal(0, 1, len(FEATURE_NAMES))


def test_entry_then_close_writes_exactly_one_live_label(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("pos1", "ETH", "long", _feats(1))
    hs.log_close("pos1", net_pnl_usd=7.5)            # a winning close
    assert hs.source_counts() == {"live": 1}
    X, y, w = hs.load_training_data()
    assert len(X) == 1 and y[0] == 1.0               # win -> label 1


def test_loss_close_labels_zero(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("pos1", "ETH", "long", _feats(1))
    hs.log_close("pos1", net_pnl_usd=-3.0)
    X, y, w = hs.load_training_data()
    assert y[0] == 0.0


def test_close_without_entry_is_a_noop(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_close("ghost", net_pnl_usd=5.0)           # never entered
    assert hs.source_counts() == {}


def test_journey_brain_stays_on_baseline_until_live_labels_earn_complexity(
        tmp_path):
    """The full loop: a proxy-heavy corpus with only a few real closes must
    keep the method-selection on logistic; the complex families are not even
    trained until live ground truth accrues."""
    hs = HistoryStore(str(tmp_path / "h.csv"))
    # 200 candidate (triple-barrier proxy) rows: plenty of TOTAL data
    for i in range(200):
        f = _feats(1000 + i)
        label = int(f[0] > 0)
        hs._append_row(f"cand{i}", "ETH", "long", f, label, 0.0, "candidate")
    # only 5 real closed trades so far
    for i in range(5):
        hs.log_entry(f"live{i}", "BTC", "long", _feats(i))
        hs.log_close(f"live{i}", net_pnl_usd=(1.0 if i % 2 else -1.0))

    sc = hs.source_counts()
    assert sc["live"] == 5 and sc["candidate"] == 200

    X, y, w = hs.load_training_data()
    n_live = sc["live"]
    # brain's admission decision at this evidence level: baseline only
    assert admissible_families(n_live, len(X), _SEL_CFG) == {"logistic"}
    res = evaluate_and_select(X, y, n_splits=4, n_live=n_live,
                              select_cfg=_SEL_CFG)
    assert res["selected"] == "logistic"
    assert set(res["gated"]) == {"gbt", "blend", "mlp"}


def test_error_path_dirty_label_never_corrupts_the_journey(tmp_path):
    """A non-finite feature vector mid-journey must be refused at the store
    boundary - the corpus the brain loads stays 100% finite."""
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("good", "ETH", "long", _feats(1))
    hs.log_close("good", net_pnl_usd=2.0)
    bad = _feats(2)
    bad[0] = float("nan")
    hs.log_entry("bad", "ETH", "long", bad)
    hs.log_close("bad", net_pnl_usd=2.0)             # refused at write (ML-015)
    assert hs.source_counts() == {"live": 1}         # only the clean one
    X, y, w = hs.load_training_data()
    assert np.all(np.isfinite(X)) and np.all(np.isfinite(y))
