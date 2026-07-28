"""Gate-truth report: grades the informed-flow components against
realized triple-barrier outcomes from the persisted sg_* telemetry."""
import csv

from scripts.gate_truth_report import (SG_MIN_ROWS, _rank_auc,
                                       build_report, classify_alignment)


def test_rank_auc_basics():
    assert abs(_rank_auc([1, 2, 3, 4], [0, 0, 1, 1]) - 1.0) < 1e-9
    assert abs(_rank_auc([4, 3, 2, 1], [0, 0, 1, 1]) - 0.0) < 1e-9
    # brute-force pairwise check: positives {1,3} vs negatives {2,4} ->
    # only (3>2) concordant of 4 pairs = 0.25 (task-5 brief asserted 0.5
    # here, which is not the Mann-Whitney value for this input - verified
    # independently by direct pairwise enumeration, not just this formula)
    assert abs(_rank_auc([1, 2, 3, 4], [1, 0, 1, 0]) - 0.25) < 1e-9


def test_classify_thin_below_floor():
    code, _ = classify_alignment({"flow": 1.0}, {"flow": 0.6},
                                 n=SG_MIN_ROWS - 1)
    assert code == "XV-042"


def test_classify_aligned_and_misaligned():
    w = {"flow": 1.0, "delta": 0.6, "accum": 0.9, "burst": 0.8,
         "trend": 0.7}
    aligned_aucs = {"flow": 0.60, "delta": 0.52, "accum": 0.58,
                    "burst": 0.55, "trend": 0.53}
    code, _ = classify_alignment(w, aligned_aucs, n=500)
    assert code == "XV-040"
    inverted = {"flow": 0.45, "delta": 0.60, "accum": 0.47,
                "burst": 0.55, "trend": 0.58}
    code, _ = classify_alignment(w, inverted, n=500)
    assert code == "XV-041"


def _write_corpus(path, rows):
    from ml.history import HistoryStore
    hs = HistoryStore(str(path))
    hs._ensure_schema()
    header = hs._header
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow([r.get(c, "0") for c in header])


def test_build_report_end_to_end(tmp_path):
    """20 instrumented winners with positive aligned flow + 20 losers
    with negative aligned flow -> flow AUC 1.0 in the report text; below
    the floor -> XV-042 verdict line present."""
    p = tmp_path / "hist.csv"
    rows = []
    for i in range(40):
        win = i < 20
        rows.append({"position_id": f"p{i}", "asset": "ETH", "side": "long",
                     "direction": "1.000000", "label": "1" if win else "0",
                     "source": "candidate", "barrier": "tb_pt" if win
                     else "tb_sl", "label_era": "triple_barrier",
                     "ts": str(1000 + i), "signal_ts": str(1000 + i),
                     "sg_flow": "0.8000" if win else "-0.8000",
                     "sg_delta": "0.1000", "sg_evidence": "1.2000",
                     "sg_conc": "0.3000"})
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    assert "flow" in text and "1.000" in text
    assert "XV-042" in text            # 40 < SG_MIN_ROWS: verdict is THIN


def test_report_ignores_uninstrumented_and_old_era(tmp_path):
    p = tmp_path / "hist.csv"
    rows = [{"position_id": "z", "asset": "ETH", "side": "long",
             "direction": "1.000000", "label": "1", "source": "candidate",
             "barrier": "trail", "label_era": "exit_sim",
             "sg_flow": "0.9000", "ts": "1", "signal_ts": "1"},
            {"position_id": "y", "asset": "ETH", "side": "long",
             "direction": "1.000000", "label": "1", "source": "candidate",
             "barrier": "tb_pt", "label_era": "triple_barrier",
             "sg_flow": "0.0000", "ts": "2", "signal_ts": "2"}]
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    assert "instrumented era rows: 0" in text
