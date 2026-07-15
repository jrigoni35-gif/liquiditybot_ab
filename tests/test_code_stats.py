"""
tests/test_code_stats.py — the central reason-code frequency ledger.

Every registered code (PT-/SZ-/RP-/FW-/…) now bumps a cumulative counter via
tag(), so the operator can finally see HOW OFTEN each reject/veto/fault fires,
not just the current disposition. Regression for the "no central {code: count}"
gap surfaced by the fault audit.
"""
from core import code_stats
from core.codes import Code, tag


def test_bump_and_snapshot():
    code_stats.reset()
    code_stats.bump("SZ-030")
    code_stats.bump("SZ-030")
    code_stats.bump("PT-040")
    snap = code_stats.snapshot()
    assert snap["SZ-030"] == 2 and snap["PT-040"] == 1


def test_tag_bumps_the_ledger():
    code_stats.reset()
    tag(Code.SZ_KELLY_ZERO, "kelly 0")
    tag(Code.SZ_KELLY_ZERO, "kelly 0 again")
    tag(Code.PT_EV_NEGATIVE, "ev fail")
    assert code_stats.snapshot()[Code.SZ_KELLY_ZERO.value] == 2
    assert code_stats.snapshot()[Code.PT_EV_NEGATIVE.value] == 1


def test_by_prefix_aggregates():
    code_stats.reset()
    for _ in range(3):
        tag(Code.SZ_KELLY_ZERO, "x")
    tag(Code.SZ_PWIN_BAR, "y")            # another SZ family member
    tag(Code.FW_RATE_LIMIT, "z")
    agg = code_stats.by_prefix()
    assert agg["SZ"] == 4 and agg["FW"] == 1


def test_top_orders_by_frequency():
    code_stats.reset()
    for _ in range(5):
        code_stats.bump("SZ-030")
    for _ in range(2):
        code_stats.bump("PT-040")
    assert list(code_stats.top(1)) == ["SZ-030"]


def test_bump_never_raises():
    code_stats.reset()
    code_stats.bump("anything")           # must not raise
    assert code_stats.snapshot()["anything"] == 1


def test_tag_still_returns_canonical_string():
    assert tag(Code.OM_MARKET_REFUSED, "no market entry") == \
        "OM-011: no market entry"
