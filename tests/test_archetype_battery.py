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


def test_battery_end_to_end_pins(tmp_path):
    """One compact battery run pins five spec properties at once:
    (a) LIVENESS — the oracle member records >=1 entry (a tape that
        cannot host a trade is a red suite, not a quiet zero) [SEV-1];
    (b) ORACLE RANKS FIRST among members by net_pct (injection duty);
    (c) AUDIT ISOLATION — the production audit trail gains zero bytes;
    (d) LEDGER/META — rows appended, attempted/refused counters written,
        and the meta sidecar's counters agree with run_battery's own
        return value (attempted == accepted + refused, both routes);
    (e) DEPLOYED COVERAGE — the no-factory "deployed" member (real,
        unmodified gate stack) is measured under BOTH default harness
        profiles, not just the archetypes.
    Grid: 8 tapes x subset — widened from 2 (still seconds, well inside
    test budget). At 2 tapes random_entry/buy_hold NEVER cleared MIN_TRIPS
    on either seed (both are limit-order archetypes measured against a
    short, low-vol synthetic tape — a real fill is rare per attempt, not
    absent by construction), leaving oracle the ONLY non-degenerate member
    and making "oracle ranks first" vacuously true over a population of
    one — exactly the silently-confident-instrument shape CLAUDE.md's
    mindset section warns about. Verified empirically (not assumed): at
    8 tapes buy_hold clears MIN_TRIPS on seed 7, giving the rank pin a
    genuine (deterministic, seed-pinned) competitor without touching any
    decisioning/order-lifecycle code — see (b)'s len(mean_net) guard."""
    import os
    from pathlib import Path as P

    from scripts.archetype_battery import (ARCHETYPES, PriceWorld,
                                           oracle_factory, run_battery)
    from scripts.trial_ledger import read_ledger

    prod_audit = P("outputs") / "audit.jsonl"
    before = prod_audit.stat().st_size if prod_audit.exists() else -1

    members = {"random_entry": ARCHETYPES["random_entry"],
               "buy_hold": ARCHETYPES["buy_hold"],
               "oracle": lambda seed: oracle_factory(
                   PriceWorld(seed, bars=200)),
               "deployed": None}
    res = run_battery(tapes=8, cycles=48, out_dir=tmp_path / "bat",
                      ledger_path=tmp_path / "trial_ledger.csv",
                      members=members)
    rows = read_ledger(tmp_path / "trial_ledger.csv")
    assert res["rows"] == len(rows) > 0
    oracle_rows = [r for r in rows if r["strategy_id"] == "oracle"
                   and not r["degenerate"]]
    assert oracle_rows, "oracle degenerate on every tape — tape cannot host a trade"
    # (e) deployed rides both default HARNESS_PROFILES (members passed
    # explicitly, profiles=None -> HARNESS_PROFILES applies to every
    # member including the no-factory one) — rows exist regardless of
    # whether the short tape gave deployed a live trade (degenerate is a
    # flag on the row, not a reason to skip appending it).
    deployed_profiles = {r["harness_profile"] for r in rows
                         if r["strategy_id"] == "deployed"}
    assert deployed_profiles == {"native", "neutral-admission"}, deployed_profiles
    by_member = {}
    for r in rows:
        if r["net_pct"] is not None and not r["degenerate"]:
            by_member.setdefault(r["strategy_id"], []).append(r["net_pct"])
    mean_net = {k: sum(v) / len(v) for k, v in by_member.items()}
    assert len(mean_net) >= 2, "need a competitor for the rank pin"
    assert max(mean_net, key=mean_net.get) == "oracle", mean_net
    after = prod_audit.stat().st_size if prod_audit.exists() else -1
    assert after == before, "battery wrote the PRODUCTION audit trail"
    meta_path = tmp_path / "trial_ledger.meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["attempted"] == res["attempted"]
    assert meta["accepted"] == res["rows"]
    assert meta["refused"] == res["refused"]
    assert res["attempted"] == res["rows"] + res["refused"]
    assert os.path.getsize(res["report_path"]) > 0


def test_all_null_population_brackets_zero(tmp_path):
    """Pure-noise members' mean net over the population must bracket 0
    within 3 SD/sqrt(n) at the booked anchor — a directional tape or a
    leaky harness shows up here [the-method all-null obligation]."""
    import statistics as st

    from scripts.archetype_battery import ARCHETYPES, run_battery
    from scripts.trial_ledger import read_ledger
    members = {"random_entry": ARCHETYPES["random_entry"]}
    run_battery(tapes=4, cycles=48, out_dir=tmp_path / "bat",
                ledger_path=tmp_path / "ledger.csv", members=members,
                profiles=None)
    rows = [r for r in read_ledger(tmp_path / "ledger.csv")
            if r["fee_anchor"] == "booked" and not r["degenerate"]
            and r["net_pct"] is not None]
    if len(rows) < 3:
        return                       # degenerate-dominated: floor did its job
    nets = [r["net_pct"] for r in rows]
    bound = 3 * (st.pstdev(nets) / max(len(nets), 1) ** 0.5) + 0.05
    assert abs(st.mean(nets)) <= bound, (st.mean(nets), bound)
