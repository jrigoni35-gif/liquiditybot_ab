"""Moomoo frozen-quote gate (input-feed docket, owed 41a).

THE DEFECT (input-feed audit 2026-08-07, #1 CRITICAL): moomoo has no
market-hours or quote-staleness guard. When the US market is closed,
get_market_snapshot keeps returning the same frozen last/prev pair and
_poll re-appended the identical basket return to the z-score window
every 5 minutes - 93% of that day's polls were duplicates of two
values, and the z visibly decayed +0.39 -> +0.00 over hours of frozen
input. The same mechanism pinned opt_oi_pcr_z at a permanent 0.00.
Weekends inject ~62h of manufactured decay.

THE GATE: a full-basket freeze - every per-ticker return identical to
the previous poll - is the closed-market signature (three liquid names
byte-identical is not a quiet market). On a frozen poll the window is
NOT appended; the z is computed from the unpolluted history, so it
holds its last honest value instead of decaying. The snapshot carries
quotes_frozen=True (additive field, interface rule 7) and the
transition logs DF-010 once per episode, DF-011 on resume - the same
latched one-log-per-episode discipline as FW-080. Options gate
likewise on raw (pcr, oi_pcr) equality.

Persistence of the windows (41c) deliberately lands AFTER this gate:
the audit's own warning - persistence alone would carry the stale-
repeat decay across restarts and make it harder to see.
"""
import logging

import pytest

# pandas is a moomoo-SDK-side dependency, present on the PC but optional
# everywhere else (engine scope forbids it; the import-integrity law says
# absent third-party deps must skip, never break collection - an unguarded
# module-scope import here interrupted the whole suite on pandas-less
# environments, which is the deploy-gate self-bricking shape).
pd = pytest.importorskip("pandas")

from data.moomoo_feed import MoomooFeed  # noqa: E402


def _snap_df(last_by_code: dict, prev: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame([{"code": c, "last_price": v,
                          "prev_close_price": prev}
                         for c, v in last_by_code.items()])


class _Ctx:
    """Quote-context double: returns the queued snapshot frames in order,
    repeating the last one when exhausted (a frozen feed)."""
    def __init__(self, frames):
        self.frames = list(frames)
        self.i = 0

    def get_market_snapshot(self, codes):
        df = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        return 0, df

    def close(self):
        pass


def _feed(frames) -> MoomooFeed:
    f = MoomooFeed({"enabled": True, "host": "127.0.0.1", "port": 11111,
                    "poll_minutes": 5,
                    "tickers": [{"code": "US.COIN", "weight": 1.0},
                                {"code": "US.QQQ", "weight": 1.0}],
                    "options": {"enabled": False}})
    f._ctx = _Ctx(frames)
    return f


def test_frozen_basket_does_not_append_and_flags_snapshot():
    live = _snap_df({"US.COIN": 105.0, "US.QQQ": 101.0})
    f = _feed([live, live, live])          # identical frames = frozen
    s1 = f._poll(1000.0)
    n_after_first = len(f._ret_hist)
    s2 = f._poll(1300.0)
    s3 = f._poll(1600.0)
    assert n_after_first == 1
    assert len(f._ret_hist) == 1, "frozen polls must not grow the window"
    assert s1.quotes_frozen is False
    assert s2.quotes_frozen is True and s3.quotes_frozen is True
    assert s2.available is True, "frozen is not unavailable - the quote is real"
    assert s2.risk_z == s1.risk_z, "z must hold, not decay toward zero"


def test_moving_quotes_append_normally():
    f = _feed([_snap_df({"US.COIN": 105.0, "US.QQQ": 101.0}),
               _snap_df({"US.COIN": 106.0, "US.QQQ": 101.5}),
               _snap_df({"US.COIN": 104.0, "US.QQQ": 100.5})])
    for i, t in enumerate((1000.0, 1300.0, 1600.0)):
        s = f._poll(t)
        assert s.quotes_frozen is False
    assert len(f._ret_hist) == 3


def test_freeze_transition_logs_df010_once_and_resume_df011(caplog):
    live = _snap_df({"US.COIN": 105.0, "US.QQQ": 101.0})
    moved = _snap_df({"US.COIN": 106.0, "US.QQQ": 101.0})
    f = _feed([live, live, live, moved])
    with caplog.at_level(logging.INFO, logger="liquiditybot.data.moomoo"):
        f._poll(1000.0)        # live
        f._poll(1300.0)        # freeze begins -> DF-010
        f._poll(1600.0)        # still frozen -> silent
        f._poll(1900.0)        # resumes -> DF-011
    frozen_logs = [r for r in caplog.records if "DF-010" in r.getMessage()]
    resume_logs = [r for r in caplog.records if "DF-011" in r.getMessage()]
    assert len(frozen_logs) == 1, "one DF-010 per episode, not per poll"
    assert len(resume_logs) == 1


def test_single_ticker_moving_is_not_a_freeze():
    """Only a FULL-basket freeze is the closed-market signature; one name
    moving while another sits still must append normally."""
    f = _feed([_snap_df({"US.COIN": 105.0, "US.QQQ": 101.0}),
               _snap_df({"US.COIN": 105.0, "US.QQQ": 101.5})])
    f._poll(1000.0)
    s2 = f._poll(1300.0)
    assert s2.quotes_frozen is False
    assert len(f._ret_hist) == 2
