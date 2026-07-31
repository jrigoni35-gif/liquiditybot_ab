"""2026-07-31 era-deadlock fix (option E: horizon re-alignment).

The bug: `label_max_bars` (96) is BOTH the label's vertical AND the live
bracket deadline, while the exit ladder's PT-060 no-progress scratch
fires at bar 36. The vertical sat 60 bars beyond the point the ladder
scratches, so only 9.3% of live positions reached it, essentially no
live row could carry a `tb_*` barrier, every live label fell into an old
label era, era exclusion dropped all 251 of them, `live_clean` was 0 and
the evidence gate was pinned to ['logistic'] permanently.

These tests pin the fix and make the inversion impossible to reintroduce.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config_guard import validate
from ml.history import (LABEL_ERA_TRIPLE_BARRIER, HistoryStore,
                        label_era_of, triple_barrier_era)

ROOT = Path(__file__).resolve().parents[1]


def _cfg():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def test_shipped_vertical_sits_inside_the_no_progress_scratch():
    cfg = _cfg()
    vertical = cfg["ml"]["label_max_bars"]
    scratch = cfg["profit_taking"]["time_stop"]["max_bars_no_progress"]
    assert vertical < scratch, (
        "the vertical must be reachable before the ladder scratches - "
        "that ordering IS the deadlock")
    assert vertical == 24 and scratch == 36


def test_guard_fatals_the_clock_inversion():
    """The exact shipped-for-5-days configuration must now be FATAL."""
    cfg = _cfg()
    cfg["ml"]["label_max_bars"] = 96          # the bug, verbatim
    msgs = [m for m in _fatals(cfg) if "label_max_bars" in m]
    assert msgs, "a vertical beyond the scratch must be FATAL"
    assert "unreachable" in msgs[0]


def test_guard_allows_the_fix_and_bounds_the_knob():
    assert not [m for m in _fatals(_cfg()) if "label_max_bars" in m]
    bad = _cfg()
    bad["ml"]["label_max_bars"] = 2
    assert [m for m in _fatals(bad) if "label_max_bars" in m]


def test_new_rows_carry_a_horizon_qualified_era():
    """Two horizons must never share one era name: a tb_* label at 24
    bars does not mean what a tb_* label at 96 bars means."""
    assert triple_barrier_era(96) == LABEL_ERA_TRIPLE_BARRIER
    assert triple_barrier_era(24) == f"{LABEL_ERA_TRIPLE_BARRIER}_h24"
    assert triple_barrier_era(24) != triple_barrier_era(96)


def test_only_the_triple_barrier_era_is_qualified(tmp_path):
    """Every other era name is untouched - the qualification applies to
    the horizon-dependent label only."""
    s24 = HistoryStore(str(tmp_path / "h.csv"), max_bars=24)
    assert s24._row_era("tb_time") == "triple_barrier_h24"
    assert s24._row_era("tb_pt") == "triple_barrier_h24"
    for b in ("realized", "time_stop", "", "trail", "sl"):
        assert s24._row_era(b) == label_era_of(b), (
            f"{b!r} is not horizon-dependent and must be unchanged")


def test_default_store_is_byte_identical_to_shipped_behavior(tmp_path):
    """Extend-with-defaults: a store built the old way writes the old
    un-suffixed era for every barrier."""
    legacy = HistoryStore(str(tmp_path / "l.csv"))
    for b in ("tb_pt", "tb_sl", "tb_time", "realized", "time_stop", ""):
        assert legacy._row_era(b) == label_era_of(b)


def test_coupling_check_is_scoped_to_configs_that_declare_a_horizon():
    """A config fragment with no `ml` block makes no claim about labeling
    and must not turn FATAL through a default it never opted into (the
    SPB-R surcharge-bound precedent). The shipped config always carries
    the key, so the real pairing is always checked."""
    bare = {"system": {"dry_run": True},
            "profit_taking": {"time_stop": {"enabled": True,
                                            "max_bars_no_progress": 6,
                                            "min_mfe_frac_of_tier1": 0.5}}}
    assert not [m for m in _fatals(bare) if "label_max_bars" in m]
    # ...but declare a horizon that the scratch pre-empts and it FATALs
    declared = dict(bare, ml={"label_max_bars": 24})
    assert [m for m in _fatals(declared) if "label_max_bars" in m]
