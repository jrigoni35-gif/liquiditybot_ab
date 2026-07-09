"""config_guard profit-tier coherence: the tier-close check must reflect the
engine's actual %-of-CURRENT-size semantics (geometric), not the old, wrong
%-of-ORIGINAL sum. Closes compound to 1 - prod(1 - close/100) and can never
exceed 100%; the meaningful warning is a large unmanaged runner, not a >100% sum.
"""
from core.config_guard import validate


def _cfg(closes, triggers=(1.0, 2.0, 3.5, 5.0)):
    return {"system": {"dry_run": True},
            "profit_taking": {f"tier_{i}": {"trigger_pct_gain": tg,
                                            "close_pct_of_position": cp}
                              for i, (tg, cp) in
                              enumerate(zip(triggers, closes), 1)}}


def _warns(cfg):
    return [m for sev, m in validate(cfg) if sev == "WARN"]


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def test_shipped_25pct_tiers_leave_a_bounded_runner_no_warn():
    # 4x25% of CURRENT -> 0.75^4 = 31.6% runner, below the 50% warn line
    assert not any("rides the trailing" in m for m in _warns(_cfg([25, 25, 25, 25])))


def test_small_closes_flag_a_large_runner():
    # 4x10% of CURRENT -> 0.9^4 = 65.6% still riding -> warn
    warns = _warns(_cfg([10, 10, 10, 10]))
    assert any("rides the trailing" in m and "66%" in m for m in warns)


def test_full_closes_never_warn_and_never_exceed_100():
    # even 4x99% cannot retire >100% of original; must not warn or fatal here
    cfg = _cfg([99, 99, 99, 99])
    assert not any("rides the trailing" in m for m in _warns(cfg))
    assert not any("close_pct_of_position out of" in m for m in _fatals(cfg))


def test_non_monotone_triggers_still_fatal():
    assert any("not strictly above" in m
               for m in _fatals(_cfg([25, 25, 25, 25],
                                     triggers=(1.0, 1.0, 3.5, 5.0))))


def test_close_pct_out_of_range_still_fatal():
    assert any("close_pct_of_position out of" in m
               for m in _fatals(_cfg([25, 25, 25, 150])))
