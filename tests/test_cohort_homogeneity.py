"""Cohort homogeneity + label-geometry breakeven — report-only instruments.

Found 2026-08-14: outputs/fills.csv carried 6 rows written by a binary whose
COLS predate the exec_era stamp (the live tree sat at 21769fb8, 2026-08-07,
until the 08-12 fast-forward), so 4 of 13 accruing era-4 trips contain legs
granted by a fill simulator with the TTL-hazard bug and the ~1.88x near-touch
double-count live. cohort_eval could not see it: selection is exit-time only
and the string exec_era did not appear in the file.

THE LOAD-BEARING TEST HERE IS test_selection_rule_unchanged. Everything else
classifies; if the classification ever starts FILTERING, the pre-registration
is broken and the verdict is worthless.
"""
import csv
import json

from scripts.cohort_eval import (B4_TS, CAPITAL_EPOCH_TS, deploy_epochs,
                                 era4_trips, geometry_breakeven, homogeneity)

# core/fill_ledger.COLS — exec_era is LAST (index 16 of 17), which is what
# makes "absent" and "blank" distinguishable via csv.DictReader's restval.
COLS = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
        "ordertype", "post_only", "attempt", "fill_size", "fill_price",
        "arrival_ref", "slip_bps", "fees_delta_usd", "remaining", "reason",
        "exec_era"]
STALE_COLS = COLS[:-1]              # what the pre-stamp binary actually wrote

EPOCH = max(B4_TS, CAPITAL_EPOCH_TS)
T_IN = EPOCH + 3600.0               # safely inside the accruing window


def _write(tmp_path, rows, header=COLS, name="fills.csv"):
    p = tmp_path / name
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow([r.get(c, "") for c in header])
    return str(p)


def _trip(pid, topen, tclose, era="7-e7d5ca1a", px=100.0):
    """One entry-opened round trip.

    `px` must DIFFER between trips in the same fixture: era4_trips dedupes on
    the fill signature (purpose, side, size, price) and that dedupe runs
    BEFORE the epoch cut, so two byte-identical trips collide regardless of
    when they closed. That is pre-existing selection-path behaviour and is
    deliberately not touched here."""
    base = {"symbol": "X", "fill_size": "1", "fees_delta_usd": "0.1",
            "remaining": "0", "exec_era": era}
    return [
        dict(base, ts=topen, order_id=pid + "e", position_id=pid,
             purpose="entry", side="buy", fill_price=f"{px:g}"),
        dict(base, ts=tclose, order_id=pid + "x", position_id=pid,
             purpose="exit", side="sell", fill_price=f"{px + 1.0:g}"),
    ]


# --- fill-era classification ------------------------------------------------
def test_stamped_trip_is_clean(tmp_path):
    t = era4_trips(_write(tmp_path, _trip("p1", T_IN, T_IN + 60)))
    assert len(t) == 1
    hg = homogeneity(t, [])
    assert hg["stale_trips"] == 0 and hg["prestamp_trips"] == 0
    assert hg["fill_eras"] == ["7-e7d5ca1a"]
    assert hg["fill_mixed"] is False


def test_absent_exec_era_field_is_stale_binary(tmp_path):
    """A 16-column row: the writer's COLS predate the stamp entirely."""
    path = _write(tmp_path, _trip("p1", T_IN, T_IN + 60), header=STALE_COLS)
    t = era4_trips(path)
    assert len(t) == 1, "a stale-binary trip must still be RECONSTRUCTED"
    hg = homogeneity(t, [])
    assert hg["stale_trips"] == 1
    assert hg["prestamp_trips"] == 0, "absent is not the same as blank"
    assert hg["fill_mixed"] is True
    assert hg["verdict"] == "MIXED(fill)"


def test_blank_exec_era_is_prestamp_not_stale(tmp_path):
    """Blank means a stamp-AWARE writer emitted a pre-stamp row — the
    ledger's decide-by-ts rule is correct for these and wrong for stale."""
    t = era4_trips(_write(tmp_path, _trip("p1", T_IN, T_IN + 60, era="")))
    hg = homogeneity(t, [])
    assert hg["prestamp_trips"] == 1 and hg["stale_trips"] == 0


def test_two_stamped_eras_is_mixed(tmp_path):
    rows = _trip("p1", T_IN, T_IN + 60, era="7-e7d5ca1a", px=100.0) + \
        _trip("p2", T_IN + 120, T_IN + 180, era="4-aeeaae36", px=200.0)
    hg = homogeneity(era4_trips(_write(tmp_path, rows)), [])
    assert sorted(hg["fill_eras"]) == ["4-aeeaae36", "7-e7d5ca1a"]
    assert hg["fill_mixed"] is True


# --- THE INVARIANT ----------------------------------------------------------
def test_selection_rule_unchanged(tmp_path):
    """Era classification must never become era FILTERING. A trip closing
    before the epoch is excluded (as always); a contaminated trip closing
    after it is INCLUDED (as always) and merely flagged."""
    early = _trip("old", EPOCH - 7200, EPOCH - 3600, px=100.0)
    contaminated = _trip("new", T_IN, T_IN + 60, px=200.0)
    path = _write(tmp_path, early + contaminated, header=STALE_COLS)
    trips = era4_trips(path)
    assert len(trips) == 1, "epoch cut must still exclude the pre-epoch trip"
    assert trips[0]["stale_legs"] == 2
    # and the flagged trip still carries its P&L into the verdict population
    assert trips[0]["gross_pct"] > 0


# --- model-era join ---------------------------------------------------------
def _retrain(tmp_path, recs):
    p = tmp_path / "retrain_history.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    return str(p)


def test_deploy_epochs_reads_only_deployed(tmp_path):
    path = _retrain(tmp_path, [
        {"ts": 100.0, "deployed": False, "selected": "gbt"},
        {"ts": 200.0, "deployed": True, "selected": "logistic"},
        {"ts": 150.0, "deployed": True, "selected": "blend"},
    ])
    eps = deploy_epochs(path)
    assert [e[1] for e in eps] == ["blend", "logistic"], "must sort ascending"


def test_missing_retrain_ledger_degrades_not_raises(tmp_path):
    assert deploy_epochs(str(tmp_path / "nope.jsonl")) == []
    t = era4_trips(_write(tmp_path, _trip("p1", T_IN, T_IN + 60)))
    assert homogeneity(t, [])["verdict"] == "UNKNOWN(no model ledger)"


def test_deploy_inside_a_trip_is_a_straddle(tmp_path):
    t = era4_trips(_write(tmp_path, _trip("p1", T_IN, T_IN + 600)))
    eps = [(T_IN + 300, "logistic", 211, 0.21887)]
    hg = homogeneity(t, eps, cohort_start=EPOCH)
    assert hg["straddling_trips"] == 1
    assert hg["model_mixed"] is True and hg["verdict"] == "MIXED(model)"


def test_deploy_outside_the_window_is_not_reported(tmp_path):
    """The full epoch history resolves WHO was in force, but only in-window
    deploys are listed — otherwise the section prints months of noise."""
    t = era4_trips(_write(tmp_path, _trip("p1", T_IN, T_IN + 60)))
    eps = [(EPOCH - 99999, "gbt", 1, 0.1), (T_IN + 10_000, "logistic", 2, 0.2)]
    hg = homogeneity(t, eps, cohort_start=EPOCH)
    assert [f for _ts, f in hg["deploys"]] == ["logistic"]
    assert hg["champions"] == ["gbt"], "in-force champion resolved from history"


# --- geometry breakeven -----------------------------------------------------
def test_geometry_breakeven_arithmetic(tmp_path):
    """pt=2%, sl=1% => breakeven hit rate = 1/(2+1) = 0.3333.
    3 targets vs 7 stops => actual 0.30 => NEGATIVE margin.
    expectancy = (3*0.02 - 7*0.01)/10 = -0.001 => -0.1%."""
    hdr = ["label_era", "pt_frac", "sl_frac", "barrier"]
    rows = ([{"label_era": "triple_barrier_h432", "pt_frac": "0.02",
              "sl_frac": "0.01", "barrier": "tb_pt"}] * 3
            + [{"label_era": "triple_barrier_h432", "pt_frac": "0.02",
                "sl_frac": "0.01", "barrier": "tb_sl"}] * 7
            + [{"label_era": "triple_barrier_h432", "pt_frac": "0.02",
                "sl_frac": "0.01", "barrier": "tb_time"}] * 5
            + [{"label_era": "legacy", "pt_frac": "9", "sl_frac": "9",
                "barrier": "tb_pt"}] * 99)
    g = geometry_breakeven(_write(tmp_path, rows, header=hdr, name="sh.csv"))
    assert g["available"] is True
    assert g["n"] == 15, "other label eras must be excluded"
    assert g["n_pt"] == 3 and g["n_sl"] == 7 and g["n_time"] == 5
    assert abs(g["breakeven_hit"] - 1 / 3) < 1e-9
    assert abs(g["actual_hit"] - 0.3) < 1e-9
    assert g["margin"] < 0
    assert abs(g["expectancy_pct"] - (-0.1)) < 1e-9


def test_geometry_missing_file_degrades(tmp_path):
    g = geometry_breakeven(str(tmp_path / "nope.csv"))
    assert g["available"] is False and g["n"] == 0


# --- selection era: WHAT the cohort is made of ------------------------------
def test_composition_joins_by_position_id_and_flags_probe_share(tmp_path):
    """The third homogeneity axis, and measured 2026-08-15 the worst: 13 of 14
    accruing trips are probe admissions, whose p_win is forced to the
    exploration constant 0.7 against a derived bar near 0.567 — so the model's
    own probability never entered the admission decision."""
    from scripts.cohort_eval import cohort_composition
    trips = [{"pid": "p1"}, {"pid": "p2"}, {"pid": "p3"}]
    hdr = ["position_id", "probe", "label_era", "source"]
    rows = [{"position_id": "p1", "probe": "1",
             "label_era": "triple_barrier_h432", "source": "live"},
            {"position_id": "p2", "probe": "1",
             "label_era": "exit_sim", "source": "live"},
            {"position_id": "p3", "probe": "0",
             "label_era": "exit_sim", "source": "live"},
            # a row for a position NOT in the cohort must be excluded
            {"position_id": "zzz", "probe": "0",
             "label_era": "legacy", "source": "candidate"}]
    c = cohort_composition(trips, _write(tmp_path, rows, header=hdr,
                                         name="sh.csv"))
    assert c["available"] is True
    assert c["joined"] == 3, "must join only cohort position_ids"
    assert c["probe"] == {"1": 2, "0": 1}
    assert abs(c["probe_share"] - 2 / 3) < 1e-9
    assert c["label_eras_present"] == 2, "two label eras in one cohort"
    assert "legacy" not in c["label_era"], "non-cohort rows must not leak in"


def test_composition_degrades_without_a_join(tmp_path):
    """Report-only tools must never become the reason the gate cannot be read."""
    from scripts.cohort_eval import cohort_composition
    assert cohort_composition([], str(tmp_path / "x.csv"))["available"] is False
    assert cohort_composition([{"pid": "p1"}],
                              str(tmp_path / "nope.csv"))["available"] is False


def test_era4_trips_carries_position_id(tmp_path):
    """The join key. Without it the composition section is blind."""
    t = era4_trips(_write(tmp_path, _trip("pid-abc", T_IN, T_IN + 60)))
    assert len(t) == 1 and t[0]["pid"] == "pid-abc"
