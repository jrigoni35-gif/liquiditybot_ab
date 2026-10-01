"""scripts/target_book_validation.py - the instruments are tested before
their readings are trusted (docs/law/mindset.md: the instrument is the
first suspect)."""
import csv
import json
import math
from pathlib import Path

import numpy as np

from scripts import target_book_validation as tv

ROOT = Path(__file__).resolve().parents[1]


def test_variance_ratio_reads_one_on_iid_and_departs_on_structure():
    rng = np.random.default_rng(3)
    x = rng.standard_normal(4000)
    vr, z = tv.variance_ratio(x, 4)
    assert abs(vr - 1) < 0.08 and abs(z) < 3
    ar = np.zeros(4000)                          # AR(1) phi=+0.3: trending
    for t in range(1, 4000):
        ar[t] = 0.3 * ar[t - 1] + x[t]
    assert tv.variance_ratio(ar, 4)[1] > 3
    mr = np.diff(x)                              # MA(1) theta=-1: reverting
    assert tv.variance_ratio(mr, 4)[1] < -3


def test_bridge_extremes_bracket_the_bar():
    rng = np.random.default_rng(5)
    x = rng.normal(0, 0.02, 5000)
    mx, mn = tv._bridge_extremes(x, np.full_like(x, 0.02 ** 2), rng)
    assert np.all(mx >= np.maximum(x, 0) - 1e-15)
    assert np.all(mn <= np.minimum(x, 0) + 1e-15)


def test_gbm_bars_are_coherent_ohlc():
    rng = np.random.default_rng(7)
    cov = np.diag([0.02, 0.03]) ** 2
    b = tv.gbm_bars(np.zeros(2), cov, 300, ["A", "B"], rng)
    for a in ("A", "B"):
        for i in range(1, 300):
            assert b.low[a][i] <= min(b.close[a][i], b.close[a][i - 1]) + 1e-9
            assert b.high[a][i] >= max(b.close[a][i], b.close[a][i - 1]) - 1e-9


def test_shuffle_keeps_the_return_multiset():
    rng = np.random.default_rng(9)
    b = tv.gbm_bars(np.zeros(2), np.diag([0.02, 0.03]) ** 2, 200, ["A", "B"], rng)
    s = tv.shuffled_bars(b, rng)
    r0, r1 = tv.log_returns(b), tv.log_returns(s)
    assert np.allclose(np.sort(r0, axis=0), np.sort(r1, axis=0))
    assert not np.allclose(r0, r1)


def test_plan_reproduces_constant_mix_exactly():
    rng = np.random.default_rng(1)
    R = rng.normal(0, 0.03, (300, 3))
    w = np.array([0.3, 0.3, 0.3])
    ref = tv.constant_mix_numpy(R, w)
    via = tv.constant_mix_plan(R, w, ["A", "B", "C"])
    assert np.max(np.abs(via / ref - 1)) < 1e-9


def test_markov_g_is_null_sized_on_iid_states():
    rng = np.random.default_rng(2)
    seq = list(rng.choice(tv.STATES, 3000))
    g = tv.g_stat(tv.transition(seq))
    assert g < 30                    # chi2(9) 99.99% quantile ~ 33.7
    sticky = [tv.STATES[0]] * 1500 + [tv.STATES[1]] * 1500
    assert tv.g_stat(tv.transition(sticky)) > 1000


def test_rebalance_payoff_sign():
    """Bar t pushes A up, bar t+1 brings it back: undoing the move pays."""
    R = np.log(np.array([[1.0, 1.0], [1.10, 1.0], [1 / 1.10, 1.0]]))
    pay = tv.rebalance_payoff(R, np.array([0.5, 0.5]))
    assert pay[2] > 0
    R2 = np.log(np.array([[1.0, 1.0], [1.10, 1.0], [1.10, 1.0]]))
    assert tv.rebalance_payoff(R2, np.array([0.5, 0.5]))[2] < 0


def test_binomial_p():
    assert tv._binom_two_sided(5, 10) == 1.0
    assert tv._binom_two_sided(0, 5) == 2 * 0.5 ** 5


def test_offline_battery_runs_and_writes_only_where_told(tmp_path):
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    root = tmp_path / "ohlc" / "1440m"
    root.mkdir(parents=True)
    rng = np.random.default_rng(4)
    for k, a in enumerate(cfg["target_book"]["assets"]):
        c = 100.0
        with (root / f"{a}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t_open_s", "high", "low", "close"])
            for i in range(140):
                c *= math.exp(rng.normal(0, 0.02 + 0.01 * k))
                w.writerow([1_700_000_000 + 86400 * i, c * 1.02, c * 0.98, c])
    out = tmp_path / "out"
    rc = tv.main(["--csv-root", str(tmp_path / "ohlc"), "--intervals", "1440",
                  "--paths", "4", "--out", str(out)])
    assert rc == 0
    rep = json.loads(next(out.glob("validation_*.json")).read_text(encoding="utf-8"))
    ids = {r["id"].split("[")[0] for r in rep["ledger"]}
    assert ids == {f"A{i}" for i in range(1, 15)}
    assert all(r["verdict"] for r in rep["ledger"])
