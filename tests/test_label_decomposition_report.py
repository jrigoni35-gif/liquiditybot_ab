"""Planted-defect pins for scripts/label_decomposition_report.py.

Each test plants a KNOWN geometry and asserts the number/flag the instrument
must produce, so a direction channel that leaks resolution, an inverted
resolution target, a row (not day) bootstrap, a percentile slip, a wrong-key
join or a vacuous negative arm goes RED rather than merely different.
Mutation evidence is recorded in the promoting commit. Nothing here touches
the production corpus: every corpus is synthesized in-process.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from scripts import label_decomposition_report as L

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "label_decomposition_report.py"


def naive_weighted_auc(x, pos, w):
    """O(n^2) reference: P(x_pos > x_neg) + 0.5 P(tie), rows counted w times."""
    x, pos, w = np.asarray(x, float), np.asarray(pos, bool), np.asarray(w, float)
    num = 0.0
    den = 0.0
    for i in np.flatnonzero(pos):
        for j in np.flatnonzero(~pos):
            ww = w[i] * w[j]
            den += ww
            num += ww * (1.0 if x[i] > x[j] else 0.5 if x[i] == x[j] else 0.0)
    return num / den if den else None


def test_weighted_auc_matches_naive_with_ties_and_weights():
    rng = np.random.default_rng(1)
    x = rng.integers(0, 6, size=60).astype(float)          # heavy ties
    pos = rng.random(60) < 0.4
    w = rng.integers(0, 4, size=60)                         # some rows dropped (0)
    gid, ng = L.tie_groups(x)
    got = L.weighted_auc(gid, ng, pos, w)
    assert got == pytest.approx(naive_weighted_auc(x, pos, w), abs=1e-12)
    # perfect separation reads 1.0; inverted reads 0.0; constant reads 0.5
    assert L.plain_auc([1, 2, 3, 4], [0, 0, 1, 1]) == 1.0
    assert L.plain_auc([4, 3, 2, 1], [0, 0, 1, 1]) == 0.0
    assert L.plain_auc([7, 7, 7, 7], [0, 0, 1, 1]) == 0.5
    assert L.plain_auc([1, 2, 3], [1, 1, 1]) is None          # one class: undefined


def test_bootstrap_weights_equal_explicit_index_resampling():
    """Multiplicity weights ARE the resampled index multiset (double derive)."""
    rng = np.random.default_rng(2)
    n = 300
    sig = np.sort(rng.uniform(0, 10 * L.DAY_S, n))
    x = rng.normal(size=n)
    pos = rng.random(n) < 0.5
    row_day, ndays = L.day_index(sig)
    W = L.draw_day_weights(row_day, ndays, reps=5, seed=7)
    gid, ng = L.tie_groups(x)
    for r in range(5):
        idx = np.repeat(np.arange(n), W[r])
        assert L.weighted_auc(gid, ng, pos, W[r]) == pytest.approx(
            L.plain_auc(x[idx], pos[idx]), abs=1e-12)
    # each draw is exactly `ndays` day draws: total weight == n rows' worth of days
    day_counts = np.bincount(row_day, weights=W[0]) / np.bincount(row_day)
    assert int(round(day_counts.sum())) == ndays


def _corpus(n_days=20, per_day=50, seed=3):
    rng = np.random.default_rng(seed)
    n = n_days * per_day
    sig = np.repeat(np.arange(n_days), per_day) * L.DAY_S + rng.uniform(0, L.DAY_S, n)
    return rng, n, sig


def test_direction_channel_scores_resolved_rows_only():
    """Feature separates tb_time from resolved perfectly and is PURE NOISE
    among resolved rows. DIRECTION must read ~0.5 on exactly the resolved
    rows; scoring tb_pt against 'everything else' would drag it far off."""
    rng, n, sig = _corpus()
    n_res = 600                                 # resolved rows come in (pt, sl) PAIRS
    resolved = np.zeros(n, bool)
    resolved[:n_res] = True
    barrier = np.full(n, "tb_time", dtype=object)
    barrier[:n_res] = np.tile(["tb_pt", "tb_sl"], n_res // 2)
    x = rng.normal(scale=0.1, size=n)
    x[:n_res] = 10.0 + np.repeat(rng.normal(size=n_res // 2), 2)   # pair shares its noise
    perm = rng.permutation(n)                   # no ordering artifact
    barrier, x, resolved = barrier[perm], x[perm], resolved[perm]
    y = (barrier == "tb_pt").astype(float)
    (r,) = L.decompose({"f": x}, y, barrier, sig, reps=50, seed=1)
    assert r["n_resolved"] == int(resolved.sum())
    assert r["direction_n"] == int(resolved.sum())
    assert r["direction_pos"] == int((barrier == "tb_pt").sum())
    # identical x multisets on both sides of the direction target -> EXACTLY 0.5
    assert r["direction_auc"] == pytest.approx(0.5, abs=1e-9)
    # the same feature vs tb_pt over ALL rows is the confounded reading
    assert L.plain_auc(x, barrier == "tb_pt") > 0.7
    assert r["resolution_auc"] == 1.0


def test_resolution_target_orientation():
    """Higher feature on RESOLVED rows -> RESOLUTION AUC > 0.5 (tb_time is the
    negative class). An inverted target reads < 0.5 here."""
    rng, n, sig = _corpus()
    resolved = rng.random(n) < 0.5
    barrier = np.where(resolved, "tb_pt", "tb_time").astype(object)
    y = (barrier == "tb_pt").astype(float)
    x = np.where(resolved, 1.0, 0.0) + rng.normal(scale=0.3, size=n)
    (r,) = L.decompose({"f": x}, y, barrier, sig, reps=50, seed=1)
    assert r["resolution_auc"] > 0.9
    assert r["resolution_pos"] == int(resolved.sum())
    assert r["resolution_ci"][0] > 0.5
    assert r["direction_auc"] is None and r["flag"] == L.FLAG_UNDEF   # no tb_sl rows


def test_day_index_block_is_one_calendar_day_wide():
    """The BLOCK WIDTH itself. Hour blocks (DAY_S/24) would read the same
    corpus as 24x more blocks and manufacture exclusions wholesale, and no
    other pin sees it: every fixture below either shares one timestamp per
    day or spreads rows i.i.d. inside a day."""
    d0 = 1_780_000_000 - (1_780_000_000 % 86400)
    sig = np.array([d0, d0 + 3600.0, d0 + 43200.0, d0 + 86399.999,
                    d0 + 86400.0, d0 + 2 * 86400.0])
    idx, n = L.day_index(sig)
    assert n == 3, "block width is not one calendar day"
    assert idx.tolist() == [0, 0, 0, 0, 1, 2]
    # a full day of hourly stamps is ONE block, not 24
    assert L.day_index(d0 + np.arange(24) * 3600.0)[1] == 1
    assert L.DAY_S == 86400.0


def test_bootstrap_resamples_days_not_rows():
    """Rows inside a day are copies of one draw (a shared path). A DAY-block
    CI must be far wider than a row-level CI on the same data; a bootstrap
    that resamples rows collapses the two to the same width. Rows are spread
    ACROSS the day on purpose: with every row at the same second, an
    hour-wide block would give the same 12 blocks and this pin would not see
    a units error in day_index."""
    rng = np.random.default_rng(4)
    n_days, per_day = 12, 80
    day_val = rng.normal(size=n_days)
    day_pos = rng.random(n_days) < 0.5
    x = np.repeat(day_val, per_day)
    pos = np.repeat(day_pos, per_day)
    barrier = np.where(pos, "tb_pt", "tb_sl").astype(object)
    y = pos.astype(float)
    sig_day = (np.repeat(np.arange(n_days), per_day) * L.DAY_S
               + np.tile(np.arange(per_day) * (L.DAY_S / per_day), n_days))
    (day_block,) = L.decompose({"f": x}, y, barrier, sig_day, reps=300, seed=1)
    # give every row its own day -> day-block bootstrap degenerates to a row bootstrap
    sig_row = np.arange(n_days * per_day) * L.DAY_S + 10.0
    (row_level,) = L.decompose({"f": x}, y, barrier, sig_row, reps=300, seed=1)
    w_day = day_block["direction_ci"][1] - day_block["direction_ci"][0]
    w_row = row_level["direction_ci"][1] - row_level["direction_ci"][0]
    assert day_block["days"] == n_days and row_level["days"] == n_days * per_day
    assert w_day > 2.5 * w_row, (w_day, w_row)


def test_percentile_ci_is_index_based_on_sorted_draws():
    boots = np.arange(1001, dtype=float)[::-1]                 # unsorted on purpose
    lo, hi = L.percentile_ci(boots)
    assert lo == pytest.approx(25.0) and hi == pytest.approx(975.0)
    assert L.percentile_ci(np.array([np.nan, 3.0, 1.0, 2.0])) == (1.05, 2.95)
    assert L.percentile_ci(np.array([])) is None
    assert L.percentile_ci(np.array([None, None], dtype=object)) is None


def test_classify_flags():
    assert L.classify((0.55, 0.60), (0.45, 0.55)) == L.FLAG_RES_ONLY
    assert L.classify((0.40, 0.45), (0.51, 0.60)) == L.FLAG_DIR
    assert L.classify((0.45, 0.55), (0.40, 0.49)) == L.FLAG_DIR
    assert L.classify((0.45, 0.55), (0.45, 0.55)) == L.FLAG_NULL
    assert L.classify((0.50, 0.60), (0.40, 0.50)) == L.FLAG_NULL   # touching includes
    assert L.classify(None, (0.4, 0.45)) == L.FLAG_UNDEF
    assert L.classify((0.4, 0.45), None) == L.FLAG_UNDEF
    assert L.ci_excludes_half(None) is None


def test_rows_sorted_by_abs_direction_desc_undefined_last():
    rng, n, sig = _corpus(seed=5)
    resolved = rng.random(n) < 0.7
    up = rng.random(n) < 0.5
    barrier = np.where(~resolved, "tb_time", np.where(up, "tb_pt", "tb_sl")).astype(object)
    y = (barrier == "tb_pt").astype(float)
    feats = {"null": rng.normal(size=n),
             "strong": np.where(up, 1.0, -1.0) + rng.normal(scale=0.5, size=n),
             "weak": np.where(up, 0.2, -0.2) + rng.normal(size=n),
             "nan": np.full(n, np.nan)}
    rows = L.decompose(feats, y, barrier, sig, reps=30, seed=1)
    assert [r["feature"] for r in rows][:1] == ["strong"]
    assert rows[-1]["feature"] == "nan" and rows[-1]["flag"] == L.FLAG_UNDEF
    dev = [abs(r["direction_auc"] - 0.5) for r in rows[:-1]]
    assert dev == sorted(dev, reverse=True)
    assert rows[0]["flag"] == L.FLAG_DIR


def test_extra_csv_joins_on_all_key_columns(tmp_path):
    """Two assets share every signal_ts with DIFFERENT values; a join on
    signal_ts alone (or on asset alone) mis-assigns them. Rows are written
    shuffled, with one duplicate key and one unmatched corpus row."""
    # join_extra_csv imports pandas lazily, so this is the ONE test in the
    # file that needs it - guarded here rather than at module scope so the
    # pandas-less workspaces still run the other pins (see the note in
    # tests/test_feed_freeze_gate.py).
    pytest.importorskip("pandas")
    ts = np.array([100.0, 200.0, 300.0, 100.0, 200.0, 300.0, 400.0])
    asset = np.array(["ADA", "ADA", "ADA", "SOL", "SOL", "SOL", "ADA"], dtype=object)
    expect = np.array([1.0, 2.0, 3.0, 11.0, 12.0, 13.0, np.nan])
    lines = ["asset,signal_ts,tape_x,text_col"]
    order = [4, 0, 5, 1, 3, 2]                 # shuffled relative to the corpus
    for i in order:
        lines.append(f"{asset[i]},{ts[i]:.3f},{expect[i]},hello")
    lines.append("ADA,100.000,999,dup")        # duplicate key: first wins
    p = tmp_path / "extra.csv"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    feats, meta = L.join_extra_csv(p, ["asset", "signal_ts"], asset, ts)
    assert list(feats) == ["tape_x"]           # non-numeric column ignored
    got = feats["tape_x"]
    assert np.array_equal(np.isnan(got), np.isnan(expect))
    assert np.array_equal(got[:6], expect[:6])
    assert meta["corpus_rows_matched"] == 6 and meta["corpus_rows_unmatched"] == 1
    assert meta["csv_duplicate_keys"] == 1
    assert meta["corpus_join_rate"] == pytest.approx(6 / 7, abs=1e-4)
    assert meta["corpus_duplicate_keys"] == 0
    # a NON-UNIQUE corpus key (the production case) matches one CSV row to
    # several corpus rows, so the rate must be counted over CORPUS rows
    dup_asset = np.concatenate([asset, np.array(["ADA"], dtype=object)])
    dup_ts = np.concatenate([ts, np.array([100.0])])
    _f2, m2 = L.join_extra_csv(p, ["asset", "signal_ts"], dup_asset, dup_ts)
    assert m2["corpus_duplicate_keys"] == 1
    assert m2["corpus_rows_matched"] == 7
    assert m2["corpus_join_rate"] == pytest.approx(7 / 8, abs=1e-4)
    with pytest.raises(ValueError):
        L.join_extra_csv(p, ["asset", "nope"], asset, ts)


def test_self_test_arms_in_process():
    seeds = range(3)
    pos = L.positive_arm(seeds, reps=120)
    assert pos["hard_correct"] == 3, pos
    neg = L.negative_arm(seeds, reps=120, scramble=True)
    assert neg["scrambled"] and neg["ci_checked"] == 27
    # the control CAN fail: unscrambled planted effects must be reported NOT ok
    live = L.negative_arm(seeds, reps=120, scramble=False)
    assert live["ok"] is False and live["false_rate"] > L.NEG_ARM_MAX_FALSE_RATE


def test_self_test_cli_is_discoverable_by_assurance_and_passes():
    """scripts/instrument_contract.py registers a self-test by the
    add_argument("--self-test") literal and requires its output to carry a
    negative-arm marker and a rate. Pin all three on the real CLI."""
    from scripts import instrument_contract as ic
    assert SCRIPT in ic.instruments_with_self_test()
    r = subprocess.run([sys.executable, str(SCRIPT), "--self-test", "--reps", "150"],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    blob = r.stdout + r.stderr
    assert r.returncode == 0, blob
    assert ic._NEG_ARM.search(blob), blob
    assert ic._RATE.search(blob), blob
    assert re.search(r"positive arm: .*?(\d+)/(\d+) seeds", blob)


def test_synth_corpus_channels_are_pure():
    c = L.synth_corpus(0, days=40, per_day=60)
    b = c["barrier"]
    resolved = np.isin(b, L.RESOLVED_BARRIERS)
    # A: no direction information among resolved rows
    a_dir = L.plain_auc(c["features"]["A"][resolved], b[resolved] == "tb_pt")
    assert 0.46 < a_dir < 0.54
    assert L.plain_auc(c["features"]["A"], resolved) > 0.7
    # B: no resolution information
    assert 0.46 < L.plain_auc(c["features"]["B"], resolved) < 0.54
    assert L.plain_auc(c["features"]["B"][resolved], b[resolved] == "tb_pt") > 0.7
    assert set(np.unique(b)) <= set(L.TB_BARRIERS)
    assert np.array_equal(c["y"], (b == "tb_pt").astype(float))


def test_flag_is_undefined_below_the_block_floor():
    """DEGENERATE BLOCK COUNT. With one distinct day every bootstrap draw is
    the same multiset, the CI collapses to zero width and PURE NOISE reads
    DIRECTIONAL. Below MIN_CI_DAYS blocks the flag must refuse instead."""
    rng = np.random.default_rng(11)
    n = 400
    sig = np.full(n, 1_780_000_000.0) + rng.uniform(0, 3600.0, n)   # ONE utc day
    barrier = np.where(rng.random(n) < 0.5, "tb_pt", "tb_sl").astype(object)
    y = (barrier == "tb_pt").astype(float)
    (r,) = L.decompose({"noise": rng.normal(size=n)}, y, barrier, sig, reps=200, seed=1)
    assert r["days"] == 1 and r["ci_blocks"] == 1 and r["few_blocks"] is True
    lo, hi = r["direction_ci"]
    assert hi - lo == pytest.approx(0.0, abs=1e-12)        # the collapse itself
    assert r["flag"] == L.FLAG_UNDEF                        # NOT manufactured
    # the floor is a block count, not a row count: the same rows spread over
    # MIN_CI_DAYS days are scored normally again
    sig_wide = (np.repeat(np.arange(L.MIN_CI_DAYS), n // L.MIN_CI_DAYS) * L.DAY_S
                + rng.uniform(0, 3600.0, n))
    (r2,) = L.decompose({"noise": rng.normal(size=n)}, y, barrier, sig_wide,
                        reps=200, seed=1)
    assert r2["ci_blocks"] == L.MIN_CI_DAYS and r2["few_blocks"] is False
    assert r2["flag"] in (L.FLAG_NULL, L.FLAG_DIR, L.FLAG_RES_ONLY)


def test_resolution_loader_is_not_filed_as_null():
    """THE FLAG COLUMN MUST NOT HIDE THE RESOLUTION CHANNEL. A feature that
    loads RESOLUTION hard while its RAW AUC sits on 0.5 (here by
    construction: the tb_time rows carry a coin-flip label, which dilutes
    RAW to exactly chance without touching either channel) used to read
    NULL. It is a RESOLUTION-ONLY row."""
    rng = np.random.default_rng(12)
    n_days, per_day = 20, 60
    n = n_days * per_day
    sig = np.repeat(np.arange(n_days), per_day) * L.DAY_S + rng.uniform(0, L.DAY_S, n)
    u = rng.random(n)
    barrier = np.where(u < 0.3, "tb_pt", np.where(u < 0.6, "tb_sl", "tb_time")).astype(object)
    resolved = np.isin(barrier, L.RESOLVED_BARRIERS)
    x = np.where(resolved, 1.0, 0.0) + rng.normal(size=n)
    # label = the barrier on resolved rows, a fair coin on tb_time rows:
    # positives and negatives then hold the SAME feature mixture -> RAW 0.5
    y = np.where(resolved, (barrier == "tb_pt").astype(float),
                 (rng.random(n) < 0.5).astype(float))
    (r,) = L.decompose({"loader": x}, y, barrier, sig, reps=300, seed=3)
    assert r["resolution_ci"][0] > 0.5                      # loads resolution
    assert r["raw_ci"][0] < 0.5 < r["raw_ci"][1]            # raw says nothing
    assert r["direction_ci"][0] < 0.5 < r["direction_ci"][1]
    assert r["flag"] == L.FLAG_RES_ONLY, (r["raw_ci"], r["resolution_ci"], r["direction_ci"])
    assert r["resolution_ci_excludes_half"] is True
    # and the rule itself, unit-wise (res_ci=None keeps the old raw-only rule)
    assert L.classify((0.45, 0.55), (0.45, 0.55), (0.60, 0.70)) == L.FLAG_RES_ONLY
    assert L.classify((0.45, 0.55), (0.45, 0.55), (0.45, 0.55)) == L.FLAG_NULL
    assert L.classify((0.45, 0.55), (0.45, 0.55), None) == L.FLAG_NULL
    assert L.classify((0.55, 0.60), (0.45, 0.55), None) == L.FLAG_RES_ONLY
    assert L.classify((0.45, 0.55), (0.51, 0.60), (0.60, 0.70)) == L.FLAG_DIR
    assert L.classify((0.45, 0.55), (0.45, 0.55), (0.60, 0.70), 4) == L.FLAG_UNDEF


def test_flag_stability_is_measured_on_disjoint_bootstrap_halves():
    """A flag that only one half of the SAME draws reproduces is a bootstrap
    realization, not a result. Seeds pinned: effect 1.0 is stable, the
    marginal effect 0.12 / seed 2 is flagged DIRECTIONAL on the full draw
    and NULL on the second half."""
    strong = L.synth_corpus(0, days=12, per_day=40, effect=1.0)
    rows = {r["feature"]: r for r in L.decompose(
        strong["features"], strong["y"], strong["barrier"], strong["sig"],
        reps=400, seed=0)}
    assert rows["B"]["flag"] == L.FLAG_DIR and rows["B"]["flag_stable"] is True
    assert rows["B"]["flag_halves"] == [L.FLAG_DIR, L.FLAG_DIR]
    marg = L.synth_corpus(2, days=12, per_day=40, effect=0.12)
    b = {r["feature"]: r for r in L.decompose(
        marg["features"], marg["y"], marg["barrier"], marg["sig"],
        reps=400, seed=2)}["B"]
    assert b["flag"] == L.FLAG_DIR
    assert b["flag_stable"] is False and b["flag_halves"] == [L.FLAG_DIR, L.FLAG_NULL]


def test_null_calibration_measures_this_corpus_not_the_nominal_5pct():
    """The realized false-exclusion rate is a property of the CORPUS's block
    structure, so it must be measured on it. Degenerate blocks (1 day) make
    every interval exclude 0.5; 30 well-populated days sit near nominal.
    The synthetic self-test rate does not transfer to either."""
    c = L.synth_corpus(5, days=30, per_day=40)
    wide = L.null_calibration(c["y"], c["barrier"], c["sig"], n_features=12,
                              reps=200, seed=7)
    assert wide["direction"]["checked"] == 12 and wide["raw"]["checked"] == 12
    assert wide["direction"]["rate"] <= 0.34, wide          # near nominal, not 1.0
    assert wide["flag_counts"][L.FLAG_NULL] >= 8, wide
    n = c["y"].size
    one_day = np.full(n, 1_780_000_000.0)                   # every row, one block
    tight = L.null_calibration(c["y"], c["barrier"], one_day, n_features=12,
                               reps=200, seed=7)
    assert tight["direction"]["rate"] > 0.9, tight          # collapsed intervals
    assert tight["flag_counts"][L.FLAG_UNDEF] == 12         # and the floor refuses them


# --- power calibration: the mirror of null_calibration (2026-09-02) --------
def _synth_barrier(n=6000, ndays=25, seed=0):
    rng = np.random.default_rng(seed)
    per = n // ndays
    sig = np.repeat(np.arange(ndays), per) * 86400.0
    b = rng.choice(["tb_pt", "tb_sl", "tb_time"], size=per * ndays,
                   p=[0.38, 0.45, 0.17]).astype(object)
    return (b == "tb_pt").astype(float), b, sig


def test_power_calibration_detection_rate_rises_with_effect_size():
    """The curve must be monotone-ish and saturate: a bigger planted effect
    cannot be detected LESS often. A flat curve means the plant is broken."""
    y, b, sig = _synth_barrier(seed=1)
    r = L.power_calibration(y, b, sig, grid=(0.0, 0.05, 0.4),
                              per_size=6, reps=120)
    rates = [g["detection_rate"] for g in r["grid"]]
    assert rates[0] < 0.5          # a ZERO effect is not "detected"
    assert rates[-1] >= rates[1] >= rates[0]
    assert r["grid"][-1]["effect_sd"] == 0.4


def test_power_calibration_reports_mde_and_none_means_no_resolution():
    """mde None is a FINDING about the test, not a null about the market -
    the report must be able to say it."""
    y, b, sig = _synth_barrier(seed=2)
    ok = L.power_calibration(y, b, sig, grid=(0.4,), per_size=6, reps=120)
    assert ok["mde"] == 0.4
    # a grid of effects too small for any corpus to see
    none = L.power_calibration(y, b, sig, grid=(1e-6,), per_size=6, reps=120)
    assert none["mde"] is None
    assert "STATEMENT ABOUT THE TEST" in none["note"].upper()


def test_power_calibration_requires_the_correct_sign():
    """A DIRECTIONAL flag pointing the wrong way is not a detection. Pinned
    because counting bare flags would inflate power by the false-positive
    rate that null_calibration exists to measure."""
    y, b, sig = _synth_barrier(seed=3)
    r = L.power_calibration(y, b, sig, grid=(0.3,), per_size=6, reps=120)
    g = r["grid"][0]
    assert g["detected_with_correct_sign"] <= g["flagged_directional"]
    assert g["detection_rate"] == round(
        g["detected_with_correct_sign"] / g["features"], 4)


def test_power_calibration_plants_direction_not_resolution():
    """The plant must load DIRECTION only. If it leaked into RESOLUTION the
    curve would measure the wrong channel and read as power we do not have."""
    y, b, sig = _synth_barrier(seed=4)
    n = y.size
    resolved = np.isin(b, L.RESOLVED_BARRIERS)
    lift = np.where(resolved, np.where(b == "tb_pt", 1.0, -1.0), 0.0)
    rng = np.random.default_rng(99)
    feats = {"planted": rng.normal(size=n) + 0.4 * lift}
    row = L.decompose(feats, y, b, sig, reps=200, seed=5)[0]
    assert row["direction_auc"] > 0.5
    assert row["flag"] == L.FLAG_DIR
    # resolution must stay at chance: the plant is 0 on tb_time rows
    assert abs(row["resolution_auc"] - 0.5) < 0.05


def test_power_calibration_does_not_count_a_backwards_detection():
    """Plant the effect with the WRONG sign. The flag still fires (the
    feature IS directional), but it points the opposite way, so it must not
    count as power. Without this, `detected == flagged` and counting bare
    flags would inflate power by exactly the false-positive rate that
    null_calibration exists to measure."""
    y, b, sig = _synth_barrier(seed=11)
    r = L.power_calibration(y, b, sig, grid=(-0.4,), per_size=6, reps=150)
    g = r["grid"][0]
    assert g["flagged_directional"] >= 5      # the flag fires: it IS directional
    assert g["detected_with_correct_sign"] == 0   # but backwards
    assert g["detection_rate"] == 0.0
    assert r["mde"] is None
