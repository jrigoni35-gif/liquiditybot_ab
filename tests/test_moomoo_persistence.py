"""Moomoo window persistence (input-feed audit 2026-08-07, owed 41c).

THE DEFECT: every rolling window rebuilt EMPTY on restart (fleet
inventory: moomoo `_ret_hist` verified in-memory-only), and at the
measured median 0.5h restart cadence that meant ~3.5h/day of context z
fabricated back toward neutral by an empty history.

SEQUENCED AFTER the 41a freeze gate on the audit's own warning:
persisting a polluted window would have carried stale-repeat decay
across restarts and made it harder to see. The composition under test
here is the point: a restored `_last_per` lets the FIRST post-restart
poll classify a still-closed market as frozen (no append), where a
clean boot would have re-seeded the empty window with the frozen quote.
"""
import pytest

# Optional third-party dep: skip, never break collection (see the note in
# tests/test_feed_freeze_gate.py - same law, same fix).
pd = pytest.importorskip("pandas")

from data.moomoo_feed import MoomooFeed  # noqa: E402


def _snap_df(last_by_code: dict, prev: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame([{"code": c, "last_price": v,
                          "prev_close_price": prev}
                         for c, v in last_by_code.items()])


class _Ctx:
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
    f = MoomooFeed({"enabled": True, "poll_minutes": 5,
                    "tickers": [{"code": "US.COIN", "weight": 1.0},
                                {"code": "US.QQQ", "weight": 1.0}],
                    "options": {"enabled": False}})
    f._ctx = _Ctx(frames)
    return f


def test_windows_and_freeze_state_roundtrip():
    f1 = _feed([_snap_df({"US.COIN": 105.0, "US.QQQ": 101.0}),
                _snap_df({"US.COIN": 106.0, "US.QQQ": 101.5}),
                _snap_df({"US.COIN": 106.0, "US.QQQ": 101.5})])
    f1._poll(1000.0)
    f1._poll(1300.0)
    f1._poll(1600.0)                       # frozen poll: latch set
    d = f1.to_dict()
    f2 = _feed([])
    f2.from_dict(d)
    assert list(f2._ret_hist) == list(f1._ret_hist)
    assert f2._last_per == f1._last_per
    assert f2._frozen is True
    assert f2.to_dict() == d               # stable fixed point


def test_restored_state_gates_first_poll_of_a_still_frozen_market():
    """The 41a x 41c composition: restart during a closed market must not
    append the frozen quote to a freshly-emptied window."""
    live = _snap_df({"US.COIN": 105.0, "US.QQQ": 101.0})
    f1 = _feed([_snap_df({"US.COIN": 104.0, "US.QQQ": 100.5}), live, live])
    f1._poll(1000.0)
    f1._poll(1300.0)
    f1._poll(1600.0)                       # freeze begins
    n_before = len(f1._ret_hist)
    d = f1.to_dict()

    f2 = _feed([live])                     # "restart": market still closed
    f2.from_dict(d)
    s = f2._poll(2000.0)
    assert s.quotes_frozen is True, (
        "first post-restart poll must recognize the pre-restart freeze")
    assert len(f2._ret_hist) == n_before, "no append on the frozen poll"


def test_restored_moved_market_appends_normally():
    f1 = _feed([_snap_df({"US.COIN": 105.0, "US.QQQ": 101.0})])
    f1._poll(1000.0)
    d = f1.to_dict()
    f2 = _feed([_snap_df({"US.COIN": 107.0, "US.QQQ": 102.0})])
    f2.from_dict(d)
    s = f2._poll(2000.0)
    assert s.quotes_frozen is False
    assert len(f2._ret_hist) == 2          # restored 1 + fresh append


def test_malformed_section_leaves_clean_boot_state():
    f = _feed([])
    f.from_dict({"ret_hist": ["not-a-number"], "last_per": 7})
    assert list(f._ret_hist) == []
    assert f._last_per == {} and f._frozen is False
    f.from_dict("garbage")                 # type: ignore[arg-type]
    assert list(f._ret_hist) == []


def test_statestore_carries_moomoo_section(tmp_path):
    """Through the REAL snapshot()/restore() (the fixed-shape-rebuild
    hazard class): the section must survive, and a close()-only moomoo
    stub (the runner-state double convention) must not break snapshot."""
    from types import SimpleNamespace

    from core.persistence import StateStore

    f1 = _feed([_snap_df({"US.COIN": 105.0, "US.QQQ": 101.0}),
                _snap_df({"US.COIN": 105.0, "US.QQQ": 101.0})])
    f1._poll(1000.0)
    f1._poll(1300.0)                       # frozen

    import tests.test_gate_components as tgc
    hs = tgc._mk_store(tmp_path / "src")
    bot = tgc._persist_stub_bot(hs)
    bot.moomoo = f1
    store = StateStore(str(tmp_path / "state.json"))
    assert store.snapshot(bot)

    f2 = _feed([])
    hs2 = tgc._mk_store(tmp_path / "dst")
    revived = tgc._persist_stub_bot(hs2)
    revived.moomoo = f2
    assert store.restore(revived)
    assert f2._frozen is True and f2._last_per == f1._last_per

    # and a bare close()-only stub still snapshots (guard on the METHOD)
    bot.moomoo = SimpleNamespace(close=lambda: None)
    assert store.snapshot(bot)
