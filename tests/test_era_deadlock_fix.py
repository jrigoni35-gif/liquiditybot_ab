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
    # CONSCIOUS RE-PIN 2026-08-01 (432-bar migration): 24/36 -> 432/480.
    # The ORDERING assertion above is the real contract and is unchanged;
    # only the pair of numbers moved, together, as the guard requires.
    assert vertical == 432 and scratch == 480


def test_guard_fatals_the_clock_inversion():
    """The exact shipped-for-5-days configuration must now be FATAL."""
    cfg = _cfg()
    cfg["ml"]["label_max_bars"] = 96          # the bug, verbatim
    # 2026-08-01: the shadow horizons are now [108, 216, 432], all of
    # which exceed 96, so multi_horizon FATALs FIRST and masks the
    # clock-inversion message this test exists to pin. Shrink them so the
    # probe isolates the inversion, which is the actual subject.
    cfg["ml"]["multi_horizon"]["horizons_bars"] = [24, 48, 96]
    # ...and restore the 36-bar scratch the bug actually shipped with.
    # The scratch is now 480, so a 96-bar vertical sits INSIDE it and is
    # perfectly legal - the inversion only exists relative to a scratch
    # BELOW the vertical, which is the pair this test pins.
    cfg["profit_taking"]["time_stop"]["max_bars_no_progress"] = 36
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


def test_era_filter_keeps_the_CURRENT_horizon_era_not_a_hardcoded_name():
    """2026-07-31 second-order defect, found in live verification.

    `_apply_era_exclusion` hardcoded the un-qualified
    LABEL_ERA_TRIPLE_BARRIER as the era to KEEP. The moment the era name
    gained a horizon qualifier (triple_barrier_h24), that filter kept the
    STALE 96-bar rows and excluded the NEW 24-bar ones - including the
    first live tb_time rows the horizon fix had just produced. The kept
    era must be the one the running config labels under, or the filter
    preserves exactly the rows it exists to remove.
    """
    from ml.history import _apply_era_exclusion
    eras = ["triple_barrier"] * 200 + ["triple_barrier_h24"] * 200
    n = len(eras)
    X = [[0.0]] * n
    y = [0] * n
    w = [1.0] * n
    sig = [float(i) for i in range(n)]
    meta = [(0.0, 0.0, "live") for _ in range(n)]
    cfg = {"enabled": True, "min_new_era_rows": 150}

    # current config labels at 24 bars -> keep ONLY the h24 rows
    out = _apply_era_exclusion(X, y, w, sig, meta, eras, cfg,
                               current_era="triple_barrier_h24")
    assert out[5]["active"] is True
    assert len(out[0]) == 200, "must keep the current-horizon rows"
    assert out[5]["excluded"]["total"] == 200

    # legacy default is unchanged (byte-identical for pre-fix callers)
    out96 = _apply_era_exclusion(X, y, w, sig, meta, eras, cfg)
    assert len(out96[0]) == 200
    assert "triple_barrier_h24" in out96[5]["excluded"]["by_era_source"]
