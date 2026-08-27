"""Archetype battery: the tape must be able to host a trade.

SEV-1 pins: bar times ADVANCE across market-data calls (the old mock froze
them at 0..119), venue prices stay coherent (the watchdog hard-returns on
~180bps+ divergence), and the candle series actually EVOLVES so momentum/
EMA rungs are not constants."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_tape_bar_times_advance_and_series_evolves(tmp_path):
    from scripts.archetype_battery import record_tape, tape_coherence
    rec = record_tape(seed=1, cycles=40, out_dir=tmp_path)
    c = tape_coherence(rec)
    assert c["bar_times_advance"] is True
    assert c["distinct_series"] > 1          # the frozen-mock failure mode
    assert c["max_venue_gap_bps"] < 50.0     # far inside the watchdog gate


def test_tape_is_seed_deterministic(tmp_path):
    from scripts.archetype_battery import record_tape
    a = Path(record_tape(seed=3, cycles=20, out_dir=tmp_path / "a"))
    b = Path(record_tape(seed=3, cycles=20, out_dir=tmp_path / "b"))
    fa = [json.loads(x)["result"] for x in a.read_text(encoding="utf-8").splitlines()]
    fb = [json.loads(x)["result"] for x in b.read_text(encoding="utf-8").splitlines()]
    assert fa == fb


def test_tapes_differ_across_seeds(tmp_path):
    from scripts.archetype_battery import PriceWorld
    w1, w2 = PriceWorld(1, 200, 300), PriceWorld(2, 200, 300)
    assert w1.price("ETH", 150) != w2.price("ETH", 150)


def _view(closes, mark):
    return {"candles": [{"time": float(i), "open": c, "high": c, "low": c,
                         "close": c, "volume": 1.0}
                        for i, c in enumerate(closes)],
            "mark_price": mark}


def test_archetypes_registry_shape():
    from scripts.archetype_battery import ARCHETYPES
    assert set(ARCHETYPES) == {"random_entry", "buy_hold", "naive_grid",
                               "clockwork_dca", "momentum_chaser",
                               "stop_herder", "vol_trend", "deployed"}
    assert ARCHETYPES["deployed"] is None


def test_rungs_emit_valid_signalresults_and_never_raise():
    from scripts.archetype_battery import ARCHETYPES
    closes = [100 + 0.3 * i for i in range(60)]
    for name, factory in ARCHETYPES.items():
        if factory is None:
            continue
        fn = factory(seed=7)
        r = fn("ETH", _view(closes, closes[-1]))
        assert r.symbol == "ETH/USD"
        assert r.direction in ("long", "short", None)
        assert (r.direction is None) == (r.all_confirmed is False)
        r2 = fn("ETH", _view([], 100.0))     # empty candles never raise
        assert r2.direction is None


def test_momentum_flips_with_the_tape():
    from scripts.archetype_battery import ARCHETYPES
    up = ARCHETYPES["momentum_chaser"](seed=1)("ETH",
        _view([100 + i for i in range(30)], 130.0))
    dn = ARCHETYPES["momentum_chaser"](seed=1)("ETH",
        _view([130 - i for i in range(30)], 100.0))
    assert up.direction == "long" and dn.direction == "short"


def test_state_is_fresh_per_factory_call():
    from scripts.archetype_battery import ARCHETYPES
    closes = [100.0] * 40
    a = ARCHETYPES["clockwork_dca"](seed=2)
    b = ARCHETYPES["clockwork_dca"](seed=2)
    va = [a("ETH", _view(closes, 100.0)).direction for _ in range(6)]
    vb = [b("ETH", _view(closes, 100.0)).direction for _ in range(6)]
    assert va == vb                      # same seed, same fresh sequence


def test_oracle_sees_the_future(tmp_path):
    from scripts.archetype_battery import PriceWorld, oracle_factory
    w = PriceWorld(5, bars=200)
    fn = oracle_factory(w, horizon_bars=12)
    i = 140
    view = _view([w.price("ETH", j) for j in range(i - 40, i + 1)],
                 w.price("ETH", i))
    r = fn("ETH", view)
    future_up = w.price("ETH", i + 12) > w.price("ETH", i)
    assert r.direction == ("long" if future_up else "short")
