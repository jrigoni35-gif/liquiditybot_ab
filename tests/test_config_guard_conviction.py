"""tests/test_config_guard_conviction.py — Phase A conviction block
coherence: the guard refuses configs where the formula would be vacuous
or self-contradictory (Compounder spec §2/§6)."""
from core.config_guard import validate


def _cfg(**conv):
    base = {"conviction": {"enabled": True, "mode": "report",
                           "agreement_floor": 0.75, "ev_cost_mult": 2.0,
                           "share_window": 40, "share_min_n": 20,
                           "share_lo": 0.1, "share_hi": 0.9},
            "pretrade": {"min_edge_cost_ratio": 1.3}}
    base["conviction"].update(conv)
    return base


def _fatals(cfg):
    return [m for s, m in validate(cfg)
            if s == "FATAL" and "conviction" in m]


def test_default_block_clean():
    assert _fatals(_cfg()) == []


def test_absent_block_clean():
    # module defaults apply; the guard only judges a present block
    assert _fatals({"pretrade": {"min_edge_cost_ratio": 1.3}}) == []


def test_bad_mode_fatal():
    assert _fatals(_cfg(mode="shadow"))


def test_agreement_floor_out_of_range_fatal():
    assert _fatals(_cfg(agreement_floor=1.5))
    assert _fatals(_cfg(agreement_floor=-0.1))


def test_ev_mult_below_pretrade_bar_fatal():
    # a conviction bar under the any-entry pretrade bar is vacuous
    assert _fatals(_cfg(ev_cost_mult=1.2))


def test_share_band_incoherent_fatal():
    assert _fatals(_cfg(share_lo=0.9, share_hi=0.1))
    assert _fatals(_cfg(share_lo=-0.1))
    assert _fatals(_cfg(share_hi=1.1))


def test_window_min_n_incoherent_fatal():
    assert _fatals(_cfg(share_window=10, share_min_n=20))
    assert _fatals(_cfg(share_window=0))
