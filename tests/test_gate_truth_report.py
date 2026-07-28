"""Gate-truth report: grades the informed-flow components against
realized triple-barrier outcomes from the persisted sg_* telemetry."""
import csv
import re

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
    # win-rate split (finding 1b): all 20 aligned rows (s_flow x direction
    # > 0) are the winners -> aligned win rate 1.000; all 20 opposed rows
    # (s_flow x direction < 0) are the losers -> opposed win rate 0.000.
    assert "aligned=1.000 (n=20)  opposed=0.000 (n=20)" in text


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


def test_build_report_calibration_buckets_show_anti_calibration(tmp_path):
    """Synthetic corpus where LOW-confidence rows win more than HIGH-
    confidence rows (the spec's motivating 2026-07-28 audit finding: win
    0.359 -> 0.321 -> 0.297 as confidence rose) -> the calibration section
    prints both bucket lines with the right win rates plus the
    gate_confidence-vs-label AUC line, and that AUC is < 0.5 (anti-
    calibrated: rank order of confidence is negatively associated with
    winning)."""
    p = tmp_path / "hist.csv"
    rows = []
    for i in range(20):
        win = i < 15                          # 15/20 win at LOW confidence
        rows.append({"position_id": f"lo{i}", "asset": "ETH", "side": "long",
                     "direction": "1.000000", "label": "1" if win else "0",
                     "source": "candidate",
                     "barrier": "tb_pt" if win else "tb_sl",
                     "label_era": "triple_barrier", "ts": str(i),
                     "signal_ts": str(i), "sg_flow": "0.1000",
                     "gate_confidence": "0.300000"})
    for i in range(20):
        win = i < 5                           # 5/20 win at HIGH confidence
        rows.append({"position_id": f"hi{i}", "asset": "ETH", "side": "long",
                     "direction": "1.000000", "label": "1" if win else "0",
                     "source": "candidate",
                     "barrier": "tb_pt" if win else "tb_sl",
                     "label_era": "triple_barrier", "ts": str(20 + i),
                     "signal_ts": str(20 + i), "sg_flow": "0.1000",
                     "gate_confidence": "0.900000"})
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    assert "[4] gate_confidence calibration" in text
    assert "[0.000,0.500)" in text and "n=20" in text and "win_rate=0.750" in text
    assert "[0.800,0.999)" in text and "win_rate=0.250" in text
    m = re.search(r"gate_confidence AUC=(-?\d+\.\d+)", text)
    assert m is not None
    assert float(m.group(1)) < 0.5


def test_classify_nan_auc_yields_thin_not_misaligned():
    """A degenerate one-class component AUC (NaN) must not fall through to
    the spearman comparison: NaN >= 0.0 is False in Python, so an
    unguarded path silently mis-verdicts as XV-041 MISALIGNED instead of
    XV-042 THIN."""
    w = {"flow": 1.0, "delta": 0.6, "accum": 0.9, "burst": 0.8, "trend": 0.7}
    aucs_with_nan = {"flow": float("nan"), "delta": 0.60, "accum": 0.47,
                     "burst": 0.55, "trend": 0.58}
    code, line = classify_alignment(w, aucs_with_nan, n=500)
    assert code == "XV-042"
    assert "XV-042" in line


def test_build_report_all_winners_nan_guard(tmp_path):
    """n=120 (>= SG_MIN_ROWS) all-winners sample makes every per-component
    AUC NaN (one-class: no losers) -> verdict must be XV-042 THIN, never a
    false XV-041 MISALIGNED."""
    p = tmp_path / "hist.csv"
    rows = []
    for i in range(120):
        rows.append({"position_id": f"p{i}", "asset": "ETH", "side": "long",
                     "direction": "1.000000", "label": "1",
                     "source": "candidate", "barrier": "tb_pt",
                     "label_era": "triple_barrier", "ts": str(i),
                     "signal_ts": str(i), "sg_flow": "0.5000",
                     "sg_delta": "0.4000", "sg_accum": "0.3000",
                     "sg_burst": "0.2000", "sg_trend": "0.1000",
                     "sg_evidence": "1.5000", "sg_conc": "0.3000",
                     "gate_confidence": "0.500000"})
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    assert "XV-042" in text
    assert "XV-041" not in text


def test_section_headers_are_renumbered_1_through_5(tmp_path):
    p = tmp_path / "hist.csv"
    rows = [{"position_id": "p0", "asset": "ETH", "side": "long",
             "direction": "1.000000", "label": "1", "source": "candidate",
             "barrier": "tb_pt", "label_era": "triple_barrier",
             "sg_flow": "0.5000", "ts": "1", "signal_ts": "1",
             "gate_confidence": "0.500000"}]
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    order = ["[1] instrumentation coverage", "[2] per-component",
             "[3] evidence strength", "[4] gate_confidence calibration",
             "[5] verdict"]
    positions = [text.index(s) for s in order]
    assert positions == sorted(positions)
