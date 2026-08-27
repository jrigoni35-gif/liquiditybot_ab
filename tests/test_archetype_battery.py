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
