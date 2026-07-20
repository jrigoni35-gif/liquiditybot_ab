"""
tests/test_persistence_bak.py — snapshot generation recovery.

Regression for a HIGH state-loss bug found in the abnormality audit: a crash
between _seal_and_write's primary->.bak rotation and the tmp->primary publish
leaves the primary MISSING but .bak valid. restore() used to early-return on a
missing primary and start FRESH — discarding every position / open order /
pending label / PnL total the .bak still held. Now both restore() and
load_raw() go through _pick_snapshot(), which falls back to .bak; and clear()
removes the backup + tmp too so --fresh cannot resurrect stale state.
"""
from core.persistence import StateStore


def test_pick_snapshot_recovers_from_bak_when_primary_missing(tmp_path):
    s = StateStore(str(tmp_path / "state.json"))
    assert s.write_raw({"version": 2, "marker": "good"})
    primary = tmp_path / "state.json"
    bak = tmp_path / "state.json.bak"
    # simulate the crash: primary rotated to .bak, then the process died
    # before the tmp->primary publish -> primary gone, .bak the only survivor
    primary.replace(bak)
    assert bak.exists() and not primary.exists()
    data = s._pick_snapshot()
    assert data is not None and data["marker"] == "good", \
        "must recover from .bak when the primary is missing"


def test_pick_snapshot_prefers_primary(tmp_path):
    s = StateStore(str(tmp_path / "state.json"))
    s.write_raw({"version": 2, "marker": "old"})   # -> primary
    s.write_raw({"version": 2, "marker": "new"})   # old->bak, new->primary
    assert s._pick_snapshot()["marker"] == "new"


def test_clear_removes_primary_and_bak(tmp_path):
    s = StateStore(str(tmp_path / "state.json"))
    s.write_raw({"version": 2})
    s.write_raw({"version": 2})                     # creates the .bak
    assert (tmp_path / "state.json.bak").exists()
    s.clear()
    assert not (tmp_path / "state.json").exists()
    assert not (tmp_path / "state.json.bak").exists(), \
        "clear() must delete the backup or --fresh resurrects stale state"


def test_no_shared_or_leftover_tmp(tmp_path):
    s = StateStore(str(tmp_path / "state.json"))
    s.write_raw({"version": 2})
    assert not (tmp_path / "state.tmp").exists()     # the fixed shared name is gone
    assert not list(tmp_path.glob("state.*.tmp"))    # pid tmp renamed away on success


# --- restored-order feature vectors are version-gated (fleet finding) -------
def test_restored_order_features_are_schema_gated(tmp_path):
    """A feature-schema bump changes what a same-width vector MEANS. The
    pending-label section already dropped foreign-version vectors, but a
    restored ENTRY order's meta['features'] slipped through ungated and
    would produce a stale-semantics training row via log_entry on a
    post-restart fill. Foreign version -> vector stripped, order kept."""
    from types import SimpleNamespace

    from core.persistence import (SNAPSHOT_VERSION, StateStore,
                                  _feature_schema_version, order_to_dict)
    from execution.order_manager import ManagedOrder

    def _snap(ver_delta):
        o = ManagedOrder(order_id="e1", txid=None, asset="ETH",
                         pair="XETHZUSD", symbol="ETH/USD", side="buy",
                         price=100.0, size=1.0, purpose="entry",
                         meta={"features": [0.1, 0.2], "p_win": 0.6})
        return {"version": SNAPSHOT_VERSION, "dry_run": True,
                "feature_schema_version":
                    _feature_schema_version() + ver_delta,
                "open_orders": [order_to_dict(o)]}

    def _restore(data):
        s = StateStore(str(tmp_path / "state.json"))
        assert s.write_raw(data)
        odict = {}
        bot = SimpleNamespace(
            dry_run=True,
            orders=SimpleNamespace(_orders=odict,
                                   open_orders=lambda: list(odict.values())),
            sizer=SimpleNamespace(_last_entry={}), _pos_realized={},
            monitor=SimpleNamespace(restore=lambda d: None),
            postmortem=SimpleNamespace(restore=lambda d: None),
            candidates=SimpleNamespace(restore=lambda d: None),
            gate_stats=SimpleNamespace(restore=lambda d: None),
            _stop_hit={}, perf=None, breaker=None, risk_protocols=None,
            thales=None,
            state=SimpleNamespace(open_position_count=lambda: 0,
                                  cash_balance=0.0, savings_balance=0.0),
            history=SimpleNamespace(_pending={}))
        s.restore(bot)                    # other sections log-and-skip
        return bot.orders._orders["e1"]

    stale = _restore(_snap(ver_delta=+1))     # foreign schema version
    assert "features" not in stale.meta, "stale-semantics vector stripped"
    assert stale.meta.get("p_win") == 0.6, "rest of meta intact"

    fresh = _restore(_snap(ver_delta=0))      # current schema version
    assert fresh.meta.get("features") == [0.1, 0.2], "current vector kept"
