"""config_guard: the two ml.era_exclusion lever/floor incoherences (OBJ-8).

(1) ARMING-vs-OVERFIT-FLOOR window. ml.era_exclusion.min_new_era_rows arms a
    filter that drops every old-era row; scripts/overfit_check.py substitutes
    a planted-signal SYNTHETIC benchmark whenever the LOADED corpus is under
    len(FEATURE_NAMES) * 10. Nothing orders the two, so a min_new_era_rows
    below that floor guarantees a window in which the filter is ARMED while
    the overfit battery is validating machinery rather than market. Shipped
    150 < 640 (64 features x 10) puts the system in that window by design and
    it reopens at every horizon migration -> WARN, never FATAL, and the fix is
    NEVER to move either number (both are measurement standards, CLAUDE.md).

(2) forced_off parity. forced_on carries a semantic FATAL (label_mode);
    forced_off carried only a bool type-check despite being the lever that
    restores the pre-exclusion, era-POOLED training view. WARN when true
    (a legitimate rollback mode - a FATAL would make the pre-exclusion view
    unreachable), clean when false (the shipped value).
"""
import re
from pathlib import Path

from core.config_guard import _OVERFIT_ROWS_PER_FEATURE, validate


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


def _warns(cfg):
    return [m for sev, m in validate(cfg) if sev == "WARN"]


def _overfit_floor():
    from ml.features import FEATURE_NAMES
    return len(FEATURE_NAMES) * _OVERFIT_ROWS_PER_FEATURE


# --- (1) arming floor vs overfit synthetic-substitution floor --------------

def test_shipped_min_new_era_rows_warns_below_overfit_floor():
    """The SHIPPED config is inside the window - the guard must say so."""
    warns = [m for m in _warns(_cfg()) if "min_new_era_rows" in m]
    assert warns, (
        "min_new_era_rows=150 is below the overfit battery's "
        f"{_overfit_floor()}-row synthetic-substitution floor; the guard "
        "must warn that the era filter arms while the battery is still "
        "measuring a planted-signal benchmark")


def test_arming_floor_warning_is_not_fatal():
    """Refusing to start on the shipped, intentional config would be worse
    than trading with the instrument honestly labelled."""
    assert not any("min_new_era_rows" in m for m in _fatals(_cfg()))


def test_arming_floor_warning_states_both_numbers_and_the_window():
    msg = next(m for m in _warns(_cfg()) if "min_new_era_rows" in m)
    floor = _overfit_floor()
    assert "150" in msg, "the arming floor must be named"
    assert str(floor) in msg, "the overfit floor must be named"
    assert str(floor - 150) in msg, "the WINDOW SIZE must be named"


def test_arming_floor_warning_forbids_moving_either_number():
    """The message must not read as a tuning suggestion - both numbers are
    measurement standards, and the response is to read the corpus line."""
    msg = next(m for m in _warns(_cfg()) if "min_new_era_rows" in m).lower()
    assert "measurement standard" in msg
    assert "corpus line" in msg
    assert "unproven" in msg


def test_no_arming_floor_warning_at_or_above_the_overfit_floor():
    """The warning names a real incoherence, not a constant scold: at/above
    the floor the filter can only arm on a corpus the battery accepts."""
    floor = _overfit_floor()
    assert not any("min_new_era_rows" in m
                   for m in _warns(_cfg(min_new_era_rows=floor)))
    assert not any("min_new_era_rows" in m
                   for m in _warns(_cfg(min_new_era_rows=floor + 1)))


def test_absent_era_exclusion_block_does_not_warn():
    assert not any("min_new_era_rows" in m
                   for m in _warns(_cfg(era_block=False)))


def test_invalid_min_new_era_rows_fatals_without_floor_warning():
    """A non-numeric value is already FATAL; the floor comparison must not
    also fire on it (and must not raise comparing str to int)."""
    cfg = _cfg(min_new_era_rows="a lot")
    assert any("min_new_era_rows" in m for m in _fatals(cfg))
    assert not any("min_new_era_rows" in m for m in _warns(cfg))


def test_mirrored_multiplier_matches_overfit_check_source():
    """DRIFT PIN. _OVERFIT_ROWS_PER_FEATURE is a MIRROR of the floor
    scripts/overfit_check.py actually applies. If that line changes, this
    goes red and the mirror must be updated in the same commit - the guard
    is worthless if it reports a floor the battery does not use."""
    src = Path(__file__).resolve().parents[1] / "scripts" / "overfit_check.py"
    text = src.read_text(encoding="utf-8")
    pat = re.compile(r"min_rows\s*=\s*len\(FEATURE_NAMES\)\s*\*\s*(\d+)")
    hits = {int(m) for m in pat.findall(text)}
    assert hits, (
        "could not find overfit_check.load_dataset's "
        "`min_rows = len(FEATURE_NAMES) * N` floor - the mirror in "
        "core/config_guard.py can no longer be verified against it")
    assert hits == {_OVERFIT_ROWS_PER_FEATURE}, (
        f"overfit_check applies {hits} rows/feature but config_guard "
        f"mirrors {_OVERFIT_ROWS_PER_FEATURE}")


# --- (2) forced_off semantic parity with forced_on -------------------------

def test_forced_off_true_warns():
    warns = [m for m in _warns(_cfg(forced_off=True)) if "forced_off" in m]
    assert warns, (
        "forced_off=true restores the pre-exclusion, era-POOLED training "
        "view - it must not pass with only a bool type-check while "
        "forced_on carries a semantic guard")


def test_forced_off_true_is_not_fatal():
    """It is a legitimate rollback mode; a FATAL would make the
    pre-exclusion view unreachable, which a rollback lever may never be."""
    assert not any("forced_off" in m for m in _fatals(_cfg(forced_off=True)))


def test_forced_off_false_is_clean():
    """The SHIPPED value must produce neither FATAL nor WARN."""
    cfg = _cfg(forced_off=False)
    assert not any("forced_off" in m for m in _fatals(cfg))
    assert not any("forced_off" in m for m in _warns(cfg))


def test_forced_off_warning_names_what_it_actually_does():
    msg = next(m for m in _warns(_cfg(forced_off=True)) if "forced_off" in m)
    low = msg.lower()
    assert "40x" in low or "40 x" in low, "the base-rate span must be named"
    assert "rollback lever" in low
    assert "entry volume" in low, (
        "the message must foreclose the actual misuse - flipping it to "
        "recover corpus size / entry volume")


def test_forced_off_non_bool_still_fatals_and_does_not_warn():
    """The type FATAL stays primary; the semantic check must not fire on a
    truthy non-bool (parity with forced_on's isinstance guard)."""
    cfg = _cfg(forced_off="yes")
    assert any("forced_off" in m for m in _fatals(cfg))
    assert not any("forced_off" in m for m in _warns(cfg))


def test_forced_off_warning_survives_the_both_true_fatal():
    """Both levers pulled is already FATAL; the forced_off semantics are
    still reported so the operator sees what each lever would have done."""
    cfg = _cfg(forced_off=True, forced_on=True)
    assert any("forced_on" in m and "forced_off" in m for m in _fatals(cfg))
    assert any("forced_off" in m for m in _warns(cfg))
