"""scripts/disposition_integrity_report.py - the verification node over the
disposition writer. Pure functions on synthetic rows/events; no I/O."""
from __future__ import annotations

import datetime as dt

from scripts import disposition_integrity_report as D


def _local_line(asset: str, when_utc: float, score: float, veto: float = 0.90) -> str:
    """A runner.log line whose LOCAL-time stamp corresponds to `when_utc`."""
    local = dt.datetime.fromtimestamp(when_utc)          # naive local, this box
    return (f"{local:%Y-%m-%d %H:%M:%S},{local.microsecond // 1000:03d} INFO "
            f"liquiditybot.main: [{asset}] sizer veto: SZ-045: manip suspect "
            f"{score:.2f} >= veto {veto:.2f}")


def test_parse_log_line_round_trips_local_stamp_to_utc_epoch():
    t = 1_787_000_000.0
    e = D.parse_log_line(_local_line("FLOW", t, 0.97))
    assert e and e["asset"] == "FLOW" and e["score"] == 0.97 and e["veto"] == 0.90
    assert abs(e["ts"] - t) < 0.002          # millisecond stamp survives
    assert D.parse_log_line("2026-09-02 10:00:00,000 INFO x: LB-010: BTC: manip "
                            "suspect 1.00 >= veto 0.90 (SZ-045)") is None  # not the sizer path


def test_stamp_matches_nearest_event_at_or_after_registration_only():
    t = 1_787_000_000.0
    rows = [{"id": "c1", "asset": "FLOW", "signal_ts": t, "manip_suspect": 0.50}]
    events = [{"ts": t - 60, "asset": "FLOW", "score": 0.99, "veto": 0.9},   # BEFORE: ineligible
              {"ts": t + 300, "asset": "FLOW", "score": 0.95, "veto": 0.9},  # nearest after
              {"ts": t + 900, "asset": "FLOW", "score": 0.91, "veto": 0.9}]
    rec = D.match_stamps(rows, events)[0]
    assert rec["matched"] and rec["lag_s"] == 300 and rec["event_score"] == 0.95
    assert abs(rec["score_delta"] - 0.45) < 1e-9


def test_no_event_within_window_is_unmatched_not_guessed():
    t = 1_787_000_000.0
    rows = [{"id": "c1", "asset": "MINA", "signal_ts": t, "manip_suspect": 0.95}]
    events = [{"ts": t + 10 * 3600, "asset": "MINA", "score": 0.95, "veto": 0.9},
              {"ts": t + 5, "asset": "FLOW", "score": 0.95, "veto": 0.9}]  # other asset
    rec = D.match_stamps(rows, events, window_s=3600)[0]
    assert rec["matched"] is False and "lag_s" not in rec


def test_report_counts_the_seam_disagreement_and_orphans():
    t = 1_787_000_000.0
    # COVERAGE IS STRICT: a row is auditable only if signal_ts >= the log's
    # first event, so that "unmatched" is unambiguous (the log fully covers
    # its window). A row registered before the log begins - even by one
    # second, even if its verdict landed inside the log - is counted as
    # before_log, never scored. The first fixture here put the seam row 30 s
    # before the first event and expected it covered; the code was right.
    rows = [
        {"id": "a", "asset": "FLOW", "signal_ts": t, "manip_suspect": 0.40},   # seam
        {"id": "b", "asset": "FLOW", "signal_ts": t + 100, "manip_suspect": 0.95},  # agrees
        {"id": "z", "asset": "FLOW", "signal_ts": t - 99_999, "manip_suspect": 0.9},  # pre-log
    ]
    events = [{"ts": t, "asset": "FLOW", "score": 0.95, "veto": 0.9},        # log starts here
              {"ts": t + 130, "asset": "FLOW", "score": 0.95, "veto": 0.9},
              {"ts": t + 50_000, "asset": "FLOW", "score": 0.93, "veto": 0.9}]  # orphan
    rep = D.build_report(rows, events, window_s=3600)
    assert rep["stamped_rows_before_log"] == 1 and rep["stamped_rows_covered"] == 2
    assert rep["matched"] == 2
    assert rep["seam_rows"] == 1                # stored 0.40 < 0.9 <= live 0.95
    assert rep["score_disagrees"] == 1          # |0.95-0.40| > tol; |0.95-0.95| ok
    assert rep["orphan_events"] == 1
    assert rep["lag_s_p50"] == 0.0               # lags [0, 30]; "at or after" includes equal


def test_row_registered_before_the_log_is_never_scored_even_if_its_verdict_is_inside():
    """The strict coverage rule, pinned on purpose: relaxing it to
    'window overlaps the log' would make unmatched ambiguous (event before
    the log vs. no event at all), so the report refuses to score the band."""
    t = 1_787_000_000.0
    rows = [{"id": "a", "asset": "FLOW", "signal_ts": t - 1, "manip_suspect": 0.4}]
    events = [{"ts": t, "asset": "FLOW", "score": 0.95, "veto": 0.9}]
    rep = D.build_report(rows, events, window_s=3600)
    assert rep["stamped_rows_before_log"] == 1 and rep["stamped_rows_covered"] == 0
    assert rep["matched"] == 0


def test_window_is_a_hard_bound_not_a_preference():
    t = 1_787_000_000.0
    rows = [{"id": "c", "asset": "ARB", "signal_ts": t, "manip_suspect": 0.2}]
    ev = [{"ts": t + 7000, "asset": "ARB", "score": 0.99, "veto": 0.9}]
    assert D.match_stamps(rows, ev, window_s=6999)[0]["matched"] is False
    assert D.match_stamps(rows, ev, window_s=7000)[0]["matched"] is True
