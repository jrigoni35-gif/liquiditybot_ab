"""scripts/target_book_paper.py - the forward paper instance. Its record must
be immutable once a bar has closed, must grade nothing before PAPER_FROM, and
must survive an unreachable venue."""
import json
import math
from pathlib import Path

from scripts import target_book_paper as tp
from scripts.target_book_replay import align

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
STEP = tp.INTERVAL_MIN * 60


def _series(n_before, n_after, seed=0):
    t0 = tp.paper_from_ts() - n_before * STEP
    out = {}
    for k, a in enumerate(CFG["target_book"]["assets"]):
        rows = []
        for i in range(n_before + n_after):
            c = 100 * math.exp(0.05 * math.sin((i + seed) / (5 + k)) + 0.001 * i)
            rows.append((t0 + i * STEP, c * 1.01, c * 0.99, c))
        out[a] = rows
    return out


def test_nothing_before_paper_from_is_graded():
    doc = tp.run(align(_series(200, 0)), CFG)
    assert doc["steps"] == 0 and doc["arms"] == {} and "waiting" in doc["note"]
    doc = tp.run(align(_series(200, 1)), CFG)
    assert doc["steps"] == 0                      # one bar after: not yet settled
    doc = tp.run(align(_series(200, 2)), CFG)
    assert doc["steps"] == 1 and doc["warmup_bars"] == 200
    assert doc["first_decision_open_utc"] == tp.PAPER_FROM


def test_a_closed_bar_never_changes_its_result():
    """Deterministic replay: adding later bars leaves every earlier point of
    the record exactly as it was (no mutable state, no look-ahead)."""
    full = _series(200, 120)
    short = {a: r[:200 + 60] for a, r in full.items()}
    d1 = tp.run(align(short), CFG)
    d2 = tp.run(align(full), CFG)
    assert d1["curve"] == d2["curve"][:len(d1["curve"])]
    assert d2["steps"] == 119 and len(d2["curve"]) == 120


def test_arms_use_the_real_instance_terms_and_reconcile():
    doc = tp.run(align(_series(200, 120)), CFG)
    reg = doc["registered"]
    assert reg["cash_usd"] == CFG["capital_management"]["starting_capital_usd"]
    assert reg["maker_fee_bps"] == CFG["pretrade"]["maker_fee_bps"]
    assert set(doc["arms"]) == {"buy_hold", "target_book", "target_book_vol40"}
    assert doc["lab"]["reconcile"].endswith("[OK]")
    for a in doc["arms"].values():
        assert a["equity_usd"] > 0 and 0 <= a["max_drawdown"] < 1


def test_store_keeps_the_first_copy_of_a_closed_bar(tmp_path):
    tp.merge_store(tmp_path, "BTC", [(1, 2.0, 1.0, 1.5), (2, 2.0, 1.0, 1.6)])
    rows = tp.merge_store(tmp_path, "BTC", [(2, 9.0, 9.0, 9.0), (3, 2.0, 1.0, 1.7)])
    assert rows == [(1, 2.0, 1.0, 1.5), (2, 2.0, 1.0, 1.6), (3, 2.0, 1.0, 1.7)]


def test_gaps_are_counted_not_filled():
    assert tp.count_gaps([0, STEP, 4 * STEP], STEP) == 2


def test_unreachable_venue_reports_the_stored_bars(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    from scripts.target_book_replay import save_csv
    for a, rows in _series(200, 30).items():
        save_csv(src / f"{a}.csv", rows)
    out = tmp_path / "out"
    assert tp.main(["--once", "--csv-dir", str(src), "--out", str(out)]) == 0
    first = json.loads((out / tp.STATUS_NAME).read_text(encoding="utf-8"))

    def boom(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr(tp, "fetch_kraken", boom)
    monkeypatch.setattr(tp.time, "sleep", lambda s: None)
    assert tp.main(["--once", "--out", str(out)]) == 0
    again = json.loads((out / tp.STATUS_NAME).read_text(encoding="utf-8"))
    assert again["steps"] == first["steps"] and len(again["fetch_errors"]) == 4
    assert len((out / "runs.jsonl").read_text(encoding="utf-8").splitlines()) == 2
