"""config_guard: ml.era_exclusion block (era-gated training exclusion,
operator decision 2026-07-26, docs/quant/2026-07-26_era_exclusion.md).

min_new_era_rows must be a non-negative number whenever the ml.era_exclusion
block is present at all. forced_off/forced_on must each be booleans and may
not both be true (contradictory operator intent - force active vs force
inactive). forced_on additionally requires ml.label_mode == "triple_barrier"
(the "era tag is unavailable" FATAL): forcing the filter active while the
labeler can never produce the era it selects for would train on zero rows
forever.
"""
from core.config_guard import validate


def _cfg(min_new_era_rows=150, forced_off=False, forced_on=False,
        label_mode="triple_barrier", era_block=True):
    ml: dict = {"label_mode": label_mode}
    if era_block:
        era: dict = {}
        if min_new_era_rows is not None:
            era["min_new_era_rows"] = min_new_era_rows
        if forced_off is not None:
            era["forced_off"] = forced_off
        if forced_on is not None:
            era["forced_on"] = forced_on
        ml["era_exclusion"] = era
    return {"system": {"dry_run": True}, "ml": ml}


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def test_shipped_default_no_fatal():
    assert not any("era_exclusion" in m for m in _fatals(_cfg()))


def test_absent_era_exclusion_block_no_fatal():
    assert not any(
        "era_exclusion" in m
        for m in _fatals(_cfg(era_block=False)))


def test_negative_min_new_era_rows_is_fatal():
    fatals = _fatals(_cfg(min_new_era_rows=-1))
    assert any("min_new_era_rows" in m for m in fatals)


def test_non_numeric_min_new_era_rows_is_fatal():
    fatals = _fatals(_cfg(min_new_era_rows="a lot"))
    assert any("min_new_era_rows" in m for m in fatals)


def test_bool_min_new_era_rows_is_fatal():
    fatals = _fatals(_cfg(min_new_era_rows=True))
    assert any("min_new_era_rows" in m for m in fatals)


def test_zero_min_new_era_rows_no_fatal():
    assert not any("era_exclusion" in m for m in _fatals(_cfg(min_new_era_rows=0)))


def test_non_bool_forced_off_is_fatal():
    fatals = _fatals(_cfg(forced_off="yes"))
    assert any("forced_off" in m for m in fatals)


def test_non_bool_forced_on_is_fatal():
    fatals = _fatals(_cfg(forced_on="yes"))
    assert any("forced_on" in m for m in fatals)


def test_forced_on_and_forced_off_both_true_is_fatal():
    fatals = _fatals(_cfg(forced_on=True, forced_off=True))
    assert any("forced_on" in m and "forced_off" in m for m in fatals)


def test_forced_on_with_triple_barrier_label_mode_no_fatal():
    fatals = _fatals(_cfg(forced_on=True, label_mode="triple_barrier"))
    assert not any("forced_on" in m and "label_mode" in m for m in fatals)


def test_forced_on_with_exit_policy_label_mode_is_fatal():
    fatals = _fatals(_cfg(forced_on=True, label_mode="exit_policy"))
    assert any("forced_on" in m and "label_mode" in m for m in fatals), (
        "forcing the era filter active while the labeler is configured to "
        "never produce the era it selects for must FATAL - the era tag is "
        "unavailable under this label mode")


def test_forced_on_false_with_exit_policy_label_mode_no_fatal():
    """forced_on defaults false (shipped) - exit_policy label_mode alone is
    not an era_exclusion incoherence unless forced_on is actually set."""
    fatals = _fatals(_cfg(forced_on=False, label_mode="exit_policy"))
    assert not any("forced_on" in m for m in fatals)
