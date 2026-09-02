"""Gate-truth report: grades the informed-flow components against
realized triple-barrier outcomes from the persisted sg_* telemetry."""
import csv
import json as _json
import re

from ml.history import triple_barrier_era
from scripts.gate_truth_report import (SG_MIN_ROWS, _rank_auc,
                                       build_report, classify_alignment,
                                       effective_n)

# The era the report will actually select, derived the SAME way the
# report derives it. These fixtures used to hardcode "triple_barrier";
# when ml.label_max_bars moved to 432 the report (correctly) stopped
# selecting them and the tests only caught it because the literal was
# ALSO hardcoded in the report. A fixture that hardcodes an era pins
# the era, not the behaviour - and goes silently vacuous at the next
# horizon migration, which is the defect this file now guards.
CURRENT_ERA = triple_barrier_era(
    int((_json.load(open("config.json", encoding="utf-8")).get("ml")
         or {}).get("label_max_bars", 96)))



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
                     else "tb_sl", "label_era": CURRENT_ERA,
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
             "barrier": "tb_pt", "label_era": CURRENT_ERA,
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
                     "label_era": CURRENT_ERA, "ts": str(i),
                     "signal_ts": str(i), "sg_flow": "0.1000",
                     "gate_confidence": "0.300000"})
    for i in range(20):
        win = i < 5                           # 5/20 win at HIGH confidence
        rows.append({"position_id": f"hi{i}", "asset": "ETH", "side": "long",
                     "direction": "1.000000", "label": "1" if win else "0",
                     "source": "candidate",
                     "barrier": "tb_pt" if win else "tb_sl",
                     "label_era": CURRENT_ERA, "ts": str(20 + i),
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
                     "label_era": CURRENT_ERA, "ts": str(i),
                     "signal_ts": str(i), "sg_flow": "0.5000",
                     "sg_delta": "0.4000", "sg_accum": "0.3000",
                     "sg_burst": "0.2000", "sg_trend": "0.1000",
                     "sg_evidence": "1.5000", "sg_conc": "0.3000",
                     "gate_confidence": "0.500000"})
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    assert "XV-042" in text
    assert "XV-041" not in text


# ---- effective n (uniqueness-weighted independent observations) -----------
# Operator-approved 2026-07-29: XV-042 speaks in the unit the statistics
# actually run on. Overlapping same-asset label windows share one return
# path (de Prado average uniqueness, the loader's exact algorithm computed
# within the report's sample) — N fully-concurrent rows are ~one
# independent observation, not N.

def _u_row(i, asset="ETH", sig=0.0, ts=1200.0):
    return {"asset": asset, "signal_ts": str(sig), "ts": str(ts),
            "position_id": f"u{i}"}


def test_effective_n_overlap_vs_disjoint_vs_cross_asset():
    # 4 same-asset rows over the SAME 5-bar window -> concurrency 4 on
    # every bar -> u=0.25 each -> n_eff 1.0
    full = [_u_row(i, sig=0.0, ts=1499.0) for i in range(4)]
    n_eff, mean_u = effective_n(full)
    assert abs(n_eff - 1.0) < 1e-9 and abs(mean_u - 0.25) < 1e-9
    # 4 same-asset rows on DISJOINT windows -> u=1 each -> n_eff 4.0
    disj = [_u_row(i, sig=i * 3000.0, ts=i * 3000.0 + 299.0)
            for i in range(4)]
    n_eff, mean_u = effective_n(disj)
    assert abs(n_eff - 4.0) < 1e-9 and abs(mean_u - 1.0) < 1e-9
    # same window, DIFFERENT assets -> no shared path -> n_eff 4.0
    cross = [_u_row(i, asset=f"A{i}", sig=0.0, ts=1499.0)
             for i in range(4)]
    n_eff, _ = effective_n(cross)
    assert abs(n_eff - 4.0) < 1e-9


def test_effective_n_empty_and_bad_signal_ts():
    assert effective_n([]) == (0.0, 0.0)
    # signal_ts missing/zero falls back to ts (single-bar lifespan) rather
    # than fabricating a [0, ts] mega-span that overlaps everything
    lone = [_u_row(0, sig=0.0, ts=900000.0),
            _u_row(1, sig=0.0, ts=1800000.0)]
    lone[0]["signal_ts"] = ""
    lone[1]["signal_ts"] = "0"
    n_eff, _ = effective_n(lone)
    assert abs(n_eff - 2.0) < 1e-9


def test_classify_thin_speaks_in_effective_n():
    w = {"flow": 1.0, "delta": 0.6, "accum": 0.9, "burst": 0.8,
         "trend": 0.7}
    good = {"flow": 0.60, "delta": 0.52, "accum": 0.58, "burst": 0.55,
            "trend": 0.53}
    # raw n clears the floor but effective n does not -> THIN, and the
    # line names the honest unit
    code, line = classify_alignment(w, good, n=500, n_eff=40.0)
    assert code == "XV-042"
    assert "effective" in line
    # effective n clears -> verdict proceeds and reports both counts
    code, line = classify_alignment(w, good, n=500, n_eff=320.0)
    assert code == "XV-040"
    assert "n_eff=320" in line
    # n_eff omitted -> byte-identical legacy behavior (raw-n gate)
    code, _ = classify_alignment(w, good, n=500)
    assert code == "XV-040"


def test_build_report_effective_n_gates_the_verdict(tmp_path):
    """120 raw instrumented rows (>= SG_MIN_ROWS) that all share ONE label
    window are ~one independent observation -> the report must show the
    effective count and verdict XV-042 THIN, never a verdict scored on the
    inflated raw n."""
    p = tmp_path / "hist.csv"
    rows = []
    for i in range(120):
        win = i % 2 == 0
        rows.append({"position_id": f"p{i}", "asset": "ETH", "side": "long",
                     "direction": "1.000000", "label": "1" if win else "0",
                     "source": "candidate",
                     "barrier": "tb_pt" if win else "tb_sl",
                     "label_era": CURRENT_ERA, "ts": "1499",
                     "signal_ts": "1", "sg_flow": "0.5000" if win
                     else "-0.5000", "sg_delta": "0.1000",
                     "sg_evidence": "1.0000", "sg_conc": "0.3000",
                     "gate_confidence": "0.500000"})
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    assert "effective n" in text
    assert "XV-042" in text and "XV-040" not in text and "XV-041" not in text


def test_build_report_independent_rows_still_reach_a_verdict(tmp_path):
    """120 genuinely disjoint rows keep effective n ~= raw n -> the floor
    clears and the verdict is scored (the deflator must not make verdicts
    unreachable on honest data)."""
    p = tmp_path / "hist.csv"
    rows = []
    for i in range(120):
        win = i % 2 == 0
        t0 = i * 3000
        rows.append({"position_id": f"p{i}", "asset": "ETH", "side": "long",
                     "direction": "1.000000", "label": "1" if win else "0",
                     "source": "candidate",
                     "barrier": "tb_pt" if win else "tb_sl",
                     "label_era": CURRENT_ERA, "ts": str(t0 + 299),
                     "signal_ts": str(t0), "sg_flow": "0.5000" if win
                     else "-0.5000", "sg_delta": "0.1000",
                     "sg_evidence": "1.0000", "sg_conc": "0.3000",
                     "gate_confidence": "0.500000"})
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    assert "XV-040" in text or "XV-041" in text
    assert "n_eff=120" in text


def test_section_headers_are_renumbered_1_through_5(tmp_path):
    p = tmp_path / "hist.csv"
    rows = [{"position_id": "p0", "asset": "ETH", "side": "long",
             "direction": "1.000000", "label": "1", "source": "candidate",
             "barrier": "tb_pt", "label_era": CURRENT_ERA,
             "sg_flow": "0.5000", "ts": "1", "signal_ts": "1",
             "gate_confidence": "0.500000"}]
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    order = ["[1] instrumentation coverage", "[2] per-component",
             "[3] evidence strength", "[4] gate_confidence calibration",
             "[5] verdict"]
    positions = [text.index(s) for s in order]
    assert positions == sorted(positions)


def test_report_reads_the_CONFIGURED_era_not_a_hardcoded_one(tmp_path):
    """Regression pin for the 2026-08-15 retired-era defect.

    build_report filtered `label_era == "triple_barrier"` - the retired
    unqualified 96-bar era - while ml.label_max_bars had moved to 432.
    Measured on the live corpus at the time: the literal selected 5,328
    retired rows (4,228 instrumented) and ZERO deployed rows, and the
    report printed a confident XV-040 ALIGNED verdict about a label
    geometry the bot had stopped using. Nothing failed, because nothing
    named the population.

    This pins the CONTRACT (read the era the config declares) rather
    than any era name, so it cannot go vacuous at the next migration.
    """
    cfg = tmp_path / "cfg.json"
    cfg.write_text(_json.dumps({"ml": {"label_max_bars": 432}}),
                   encoding="utf-8")
    deployed, retired = triple_barrier_era(432), triple_barrier_era(96)
    assert deployed != retired            # guard the premise

    p = tmp_path / "h.csv"
    rows = []
    # 40 RETIRED-era rows carrying strong instrumentation, and 12
    # DEPLOYED-era rows. A reader of the old code sees 40; the contract
    # says it must see 12.
    for i in range(40):
        rows.append({"label_era": retired, "label": "1", "ts": str(i),
                     "signal_ts": str(i), "direction": "1",
                     "sg_flow": "0.9", "gate_confidence": "0.9"})
    for i in range(12):
        rows.append({"label_era": deployed, "label": "0",
                     "ts": str(500 + i * 400),
                     "signal_ts": str(500 + i * 400), "direction": "1",
                     "sg_flow": "0.4", "gate_confidence": "0.4"})
    cols = ["label_era", "label", "ts", "signal_ts", "direction",
            "sg_flow", "gate_confidence"]
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    text = build_report(str(p), str(cfg))
    assert f"era rows: {len(rows) - 40}" in text, \
        "report must select the DEPLOYED era, not the retired one"
    assert f"label era: {deployed}" in text, \
        "the report must NAME the population it measured"
    # EQUALITY, not `retired not in ...`: the qualified era name CONTAINS
    # the retired one as a prefix ("triple_barrier_h432".startswith(
    # "triple_barrier")), so a substring check here can never fail - it
    # would be exactly the tautological pin this docket exists to catch.
    named = text.split("label era:")[1].split("(")[0].strip()
    assert named == deployed, f"named {named!r}, expected {deployed!r}"


# ---------------------------------------------------------------------------
# PARTIAL IDENTIFICATION of the XV-040 verdict (2026-08-31)
#
# [2]'s AUCs are ESTIMATES and rho reads only their RANK ORDER, so sampling
# error at EFFECTIVE n can reorder them outright. Measured on the live corpus
# 2026-08-31T00:39:31Z: n=10718, n_eff=611.3, AUCs
# {flow .504, delta .502, accum .513, burst .495, trend .521} - spread 0.026
# against a 95% margin of +/-0.046. 120 of 120 orderings feasible, identified
# set of rho = [-1.00, +1.00]: the report was printing a confident XV-040
# ALIGNED on a rho whose SIGN the evidence does not determine.
# ---------------------------------------------------------------------------
_LIVE_AUCS = {"flow": 0.504, "delta": 0.502, "accum": 0.513,
              "burst": 0.495, "trend": 0.521}
_W5 = {"flow": 1.0, "delta": 0.6, "accum": 0.9, "burst": 0.8, "trend": 0.7}


def test_auc_se_uses_effective_n_and_inflates():
    from scripts.gate_truth_report import auc_se_on_neff
    se_nom = auc_se_on_neff(10718, 0.44)
    se_eff = auc_se_on_neff(611.3, 0.44)
    # nominal n is optimistic by sqrt(n / n_eff) = x4.187
    assert abs(se_eff / se_nom - (10718 / 611.3) ** 0.5) < 0.02
    # degenerate one-class split yields NaN, never a zero margin
    assert auc_se_on_neff(500.0, 0.0) != auc_se_on_neff(500.0, 0.0)


def test_rho_identified_set_is_exhaustive_and_not_constant():
    from scripts.gate_truth_report import rho_identified_set
    keys = list(_LIVE_AUCS)
    # margin 0 -> only the observed ordering is feasible -> a POINT
    lo, hi, nf = rho_identified_set(_W5, _LIVE_AUCS, 0.0, keys)
    assert nf == 1 and abs(lo - hi) < 1e-12
    # live margin on effective n -> every ordering feasible -> whole range
    lo, hi, nf = rho_identified_set(_W5, _LIVE_AUCS, 0.0461, keys)
    assert nf == 120 and lo < 0.0 < hi


def test_classify_declines_when_rho_sign_is_not_identified():
    """The planted-defect proof, pinned: with the margin the live corpus
    actually supports, ALIGNED must NOT be claimed."""
    code, line = classify_alignment(_W5, _LIVE_AUCS, 10718, n_eff=611.3,
                                    auc_margin=0.0461)
    assert code == "XV-042"
    assert "NOT IDENTIFIED" in line and "identified set" in line
    # DEFECT-2: guard disarmed -> the OLD confident verdict returns. This
    # is what shipped before 2026-08-31, and pinning it proves the new
    # branch (not some unrelated change) is what declines.
    code_off, _ = classify_alignment(_W5, _LIVE_AUCS, 10718, n_eff=611.3)
    assert code_off == "XV-040"


def test_identification_guard_is_not_a_blanket_refusal():
    """A guard that always declines detects nothing. Genuinely separated
    AUCs must still reach a verdict at the SAME margin."""
    strong = {"flow": 0.80, "delta": 0.52, "accum": 0.72, "burst": 0.64,
              "trend": 0.58}
    code, _ = classify_alignment(_W5, strong, 10718, n_eff=611.3,
                                 auc_margin=0.0461)
    assert code == "XV-040"
    inverted = {"flow": 0.52, "delta": 0.80, "accum": 0.58, "burst": 0.64,
                "trend": 0.72}
    code, _ = classify_alignment(_W5, inverted, 10718, n_eff=611.3,
                                 auc_margin=0.0461)
    assert code == "XV-041"


# --- POWER, COMPUTED (2026-09-02) --------------------------------------
# Replaces the hand-computed "~0.17 AUC at ~16 independent observations"
# that stood in the module docstring from 2026-07-29 and was never
# recomputed. Every pin below exists to turn RED under one named defect;
# the defect table is in the session return, not in a comment that could
# drift from it.

def _z_by_bisection(p):
    """INDEPENDENT inverse-normal: bisection on math.erf. Deliberately a
    different algorithm from the report's Acklam+Halley route - a re-read
    of the same code is not a second implementation (verification
    standard check 1)."""
    import math as _m
    lo, hi = -12.0, 12.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if 0.5 * (1.0 + _m.erf(mid / _m.sqrt(2.0))) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _mde_independent(n_eff, pos_rate, power=0.80, alpha=0.05):
    """Second, independently written MDE: own SE, own z route."""
    import math as _m
    n1 = n_eff * pos_rate
    n0 = n_eff - n1
    se = _m.sqrt((n1 + n0 + 1.0) / (12.0 * n1 * n0))
    return (_z_by_bisection(1.0 - alpha / 2.0) + _z_by_bisection(power)) * se


def test_z_quantile_matches_an_independent_inversion_and_the_literature():
    from scripts.gate_truth_report import _z_quantile
    for p in (0.001, 0.02, 0.1, 0.5, 0.8, 0.80, 0.9, 0.975, 0.995, 0.999):
        assert abs(_z_quantile(p) - _z_by_bisection(p)) < 1e-9, p
    # literature constants, a third route (no code of ours involved)
    assert abs(_z_quantile(0.975) - 1.959963985) < 1e-8
    assert abs(_z_quantile(0.80) - 0.841621234) < 1e-8
    # out of domain -> nan, never a silent 0.0
    for bad in (0.0, 1.0, -0.1, 1.5):
        assert _z_quantile(bad) != _z_quantile(bad)


def test_mde_matches_the_independent_implementation():
    from scripts.gate_truth_report import mde_auc
    for n_eff, rate in ((16.0, 0.5), (30.0, 0.5), (100.0, 0.44),
                        (611.3, 0.44), (10718.0, 0.44)):
        assert abs(mde_auc(n_eff, rate)
                   - _mde_independent(n_eff, rate)) < 1e-9, (n_eff, rate)


def test_mde_is_the_power_multiple_of_the_se_not_one_se():
    """DEFECT-2 pin (MDE at 1 SE). The MDE is (z_a/2 + z_power) x SE =
    2.8016 SE; a 1-SE 'detectable effect' is a ~50%-power figure and
    understates what the sample can see by 2.8x."""
    from scripts.gate_truth_report import auc_se_on_neff, mde_auc
    se = auc_se_on_neff(611.3, 0.44)
    assert abs(mde_auc(611.3, 0.44) / se - 2.801585) < 1e-6
    assert mde_auc(611.3, 0.44) > 2.5 * se


def test_mde_moves_with_the_power_target():
    """DEFECT-3 pin (power target ignored). A `power` argument that does
    not change the answer is decoration."""
    from scripts.gate_truth_report import auc_se_on_neff, mde_auc
    se = auc_se_on_neff(200.0, 0.5)
    m50 = mde_auc(200.0, 0.5, power=0.50)
    m80 = mde_auc(200.0, 0.5, power=0.80)
    m90 = mde_auc(200.0, 0.5, power=0.90)
    assert m50 < m80 < m90
    assert abs(m50 / se - 1.959964) < 1e-6      # power .5 -> alpha only
    # FORWARD power check, the other direction of the derivation: at the
    # 80% MDE the achieved power really is 80%.
    import math as _m
    power = 0.5 * (1.0 + _m.erf((m80 / se - 1.959963985) / _m.sqrt(2.0)))
    assert abs(power - 0.80) < 1e-6


def test_mde_uses_effective_n_and_a_raw_n_mde_is_optimistic():
    """DEFECT-1 pin (effective n replaced by raw n). Same optimism factor
    sqrt(n / n_eff) the AUC margin already carries."""
    from scripts.gate_truth_report import mde_auc
    m_eff = mde_auc(611.3, 0.44)
    m_raw = mde_auc(10718.0, 0.44)
    assert m_eff > m_raw
    assert abs(m_eff / m_raw - (10718.0 / 611.3) ** 0.5) < 0.02


def test_mde_degenerate_inputs_return_nan_never_zero():
    """Verification-standard check 6: a degenerate input fails loudly. A
    zero MDE would read as INFINITE power."""
    from scripts.gate_truth_report import mde_auc
    for args in ((500.0, 0.0), (500.0, 1.0), (0.0, 0.5), (-5.0, 0.5)):
        assert mde_auc(*args) != mde_auc(*args), args
    assert mde_auc(500.0, 0.5, power=0.0) != mde_auc(500.0, 0.5, power=0.0)
    assert mde_auc(500.0, 0.5, alpha=1.0) != mde_auc(500.0, 0.5, alpha=1.0)


def test_report_prints_the_mde_computed_on_effective_n(tmp_path):
    """DEFECT-4 pin (uniqueness deflation dropped at the call site): 30
    assets x 4 fully-concurrent rows = 120 raw rows, n_eff exactly 30.0.
    The printed MDE must be the n_eff=30 figure (0.3002), not the raw
    n=120 figure (0.1483)."""
    p = tmp_path / "hist.csv"
    rows = []
    for g in range(30):
        for j in range(4):
            win = j % 2 == 0
            rows.append({"position_id": f"p{g}_{j}", "asset": f"A{g}",
                         "side": "long", "direction": "1.000000",
                         "label": "1" if win else "0",
                         "source": "candidate",
                         "barrier": "tb_pt" if win else "tb_sl",
                         "label_era": CURRENT_ERA, "ts": "1499",
                         "signal_ts": "1",
                         "sg_flow": "0.5000" if win else "-0.5000",
                         "sg_delta": "0.1000", "sg_evidence": "1.0000",
                         "sg_conc": "0.3000",
                         "gate_confidence": "0.500000"})
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    m = re.search(r"MDE \+/-([0-9.]+) AUC at 80% power / two-sided 0\.05, "
                  r"on effective n=([0-9.]+)", text)
    assert m, text
    assert abs(float(m.group(2)) - 30.0) < 0.05
    assert abs(float(m.group(1)) - _mde_independent(30.0, 0.5)) < 5e-5
    # the raw-n figure must NOT be what got printed
    assert abs(float(m.group(1)) - _mde_independent(120.0, 0.5)) > 0.1
    # the floor rung is printed too, and is the n_eff=SG_MIN_ROWS figure
    f = re.search(r"floor it is \+/-([0-9.]+)", text)
    assert f and abs(float(f.group(1))
                     - _mde_independent(float(SG_MIN_ROWS), 0.5)) < 5e-5


def test_report_mde_uses_the_sample_win_rate_it_advertises(tmp_path):
    """DEFECT-5 pin (class balance substituted at the CALL SITE).

    The DEFECT-4 fixture above is win-rate EXACTLY 0.500, so every
    pos_rate defect at the `mde_auc(n_eff, _win)` call site -- a
    hardcoded 0.5, a `max(_win, 0.5)` floor, a swapped argument -- is
    invisible to it end-to-end while all the unit pins (which call
    mde_auc directly) stay green. This fixture is deliberately
    IMBALANCED: 30 assets x 4 fully-concurrent rows, 1 winner each ->
    n_eff 30.0, win rate exactly 0.250.

    The MDE is not flat in pos_rate: mde_auc(30, 0.25) is ~15% larger
    than mde_auc(30, 0.50), and the gap widens as the balance worsens
    (at a 5% win rate it is ~2.3x), always in the direction of
    UNDERSTATING the undetectable band -- the same direction of error
    as the struck hand-figure this section replaced. The parenthetical
    win rate must also be the one that was USED, not decoration beside
    a different number."""
    p = tmp_path / "hist.csv"
    rows = []
    for g in range(30):
        for j in range(4):
            win = j == 0                     # 1 of 4 -> win rate 0.250
            rows.append({"position_id": f"p{g}_{j}", "asset": f"A{g}",
                         "side": "long", "direction": "1.000000",
                         "label": "1" if win else "0",
                         "source": "candidate",
                         "barrier": "tb_pt" if win else "tb_sl",
                         "label_era": CURRENT_ERA, "ts": "1499",
                         "signal_ts": "1",
                         "sg_flow": "0.5000" if win else "-0.5000",
                         "sg_delta": "0.1000", "sg_evidence": "1.0000",
                         "sg_conc": "0.3000",
                         "gate_confidence": "0.500000"})
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    m = re.search(r"MDE \+/-([0-9.]+) AUC at 80% power / two-sided 0\.05, "
                  r"on effective n=([0-9.]+) \(win rate ([0-9.]+)\)", text)
    assert m, text
    printed_mde, printed_neff, printed_win = (float(m.group(1)),
                                              float(m.group(2)),
                                              float(m.group(3)))
    assert abs(printed_neff - 30.0) < 0.05
    # the advertised win rate is the real one
    assert abs(printed_win - 0.25) < 5e-4, printed_win
    # and the MDE was computed AT that win rate, by the independent route
    assert abs(printed_mde - _mde_independent(30.0, 0.25)) < 5e-5
    # a 0.5 class balance is NOT what got used -- the separation the
    # DEFECT-4 fixture cannot make
    assert abs(printed_mde - _mde_independent(30.0, 0.5)) > 5e-3
    # the floor rung carries the same win rate
    f = re.search(r"floor it is \+/-([0-9.]+)", text)
    assert f and abs(float(f.group(1))
                     - _mde_independent(float(SG_MIN_ROWS), 0.25)) < 5e-5
    assert abs(float(f.group(1))
               - _mde_independent(float(SG_MIN_ROWS), 0.5)) > 1e-3


def test_report_says_unknown_not_zero_when_power_is_uncomputable(tmp_path):
    """All-winners corpus -> one-class split -> no SE -> the report must
    say power is UNKNOWN rather than print a 0.0000 MDE."""
    p = tmp_path / "hist.csv"
    rows = [{"position_id": f"w{i}", "asset": f"A{i}", "side": "long",
             "direction": "1.000000", "label": "1", "source": "candidate",
             "barrier": "tb_pt", "label_era": CURRENT_ERA,
             "ts": str(i * 3000 + 299), "signal_ts": str(i * 3000),
             "sg_flow": "0.5000", "sg_delta": "0.1000",
             "sg_evidence": "1.0000", "sg_conc": "0.3000",
             "gate_confidence": "0.500000"} for i in range(120)]
    _write_corpus(p, rows)
    text = build_report(str(p), "config.json")
    assert "MDE not available" in text and "power is UNKNOWN" in text
    assert "MDE +/-0.0000" not in text


def test_docstring_carries_no_hand_computed_power_figure():
    """The stale-claim pin: prose may point at the computed value, but a
    numeric power claim must never live in the docstring again."""
    import scripts.gate_truth_report as g
    doc = g.__doc__ or ""
    assert "0.17 AUC" not in doc.split("What stood here")[0]
    assert "mde_auc()" in doc and "RUNNING the report" in doc
