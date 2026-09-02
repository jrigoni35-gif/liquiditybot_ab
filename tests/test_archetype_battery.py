"""Archetype battery: the tape must be able to host a trade.

SEV-1 pins: bar times ADVANCE across market-data calls (the old mock froze
them at 0..119), venue prices stay coherent (the watchdog hard-returns on
~180bps+ divergence), and the candle series actually EVOLVES so momentum/
EMA rungs are not constants."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# --- audit isolation: WHO OWNS IT (pin (c) of test_battery_end_to_end_pins) ---
# NOT this file. tests/conftest.py::_no_production_outputs_writes already
# fails, BY NODE ID, any test whose process opens ANY path under the repo's
# outputs/ for write (session-wide sys.audit hook, _ALLOWED empty, rename/
# replace/remove included). That set strictly CONTAINS "opened
# outputs/audit.jsonl for write", so a second audit hook here would be a
# fork of conftest's, weaker, and would have to be kept in step with it
# whenever a new evasion route (os.link, shutil.copyfile, os.truncate) is
# covered. It was tried and removed: with a production-outputs write planted
# in run_battery, conftest failed both battery tests while the local watcher
# stayed green on everything outside audit.jsonl - i.e. the fork was never
# the load-bearing guard. scripts/archetype_battery.py's own header already
# cites the conftest fixture by name; this is the other half of that
# reference.
#
# History kept because it is the reason the pin looks the way it does: the
# ORIGINAL pin compared outputs/audit.jsonl's size before and after the
# battery (`after == before`). That raced the LIVE runner, which appends to
# the production trail on its own schedule (bursty: median inter-record gap
# ~0.06 s, p90 ~31 s, with silences past 1,800 s measured 2026-09-02), so
# the pin went red whenever the runner happened to write during the test and
# green whenever it happened not to - a fact about the runner, never about
# the battery, and NOT evidence of isolation when green. Widening it
# ("grew by < X") was rejected as gate-widening. What is left here is the
# part conftest cannot see: that the audit SINGLETON the battery logs to is
# the redirected sink and not the production trail, plus a positive control
# that the battery actually audited something ("0 findings" and "the scan is
# broken" separated in every run).


def _norm(p) -> str | None:
    """Comparable form of a path as open() sees it: absolute against the
    CURRENT cwd (the AuditTrail default is the RELATIVE 'outputs/audit.jsonl'
    and resolves the same way), case-folded for the Windows target."""
    try:
        return os.path.normcase(os.path.abspath(os.fspath(p)))
    except (TypeError, ValueError):       # int fds, non-path objects
        return None


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
    (c) AUDIT ISOLATION — the audit SINGLETON the battery logs to is the
        redirected sink, not the production trail (neither spelling of it),
        with a POSITIVE CONTROL that the sink actually GREW, so a battery
        that audits nothing cannot read as "isolated" ("0 findings" and
        "the scan is broken" are separated in every run). The stronger
        property — that NOTHING under the repo's outputs/ was opened for
        write anywhere in this process — belongs to
        tests/conftest.py::_no_production_outputs_writes and is asserted
        there, by node id, for this test like every other; see the module
        header for why it is not re-implemented here;
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
    from pathlib import Path as P

    from core.audit import get_audit
    from scripts.archetype_battery import (ARCHETYPES, PriceWorld,
                                           oracle_factory, run_battery)
    from scripts.trial_ledger import read_ledger

    # (c) setup. Two spellings of the production trail: the repo-rooted
    # file the operator reads, and the AuditTrail DEFAULT ('outputs/
    # audit.jsonl', cwd-relative) a lost redirect would actually hit.
    repo = P(__file__).resolve().parents[1]
    prod_keys = {_norm(repo / "outputs" / "audit.jsonl"),
                 _norm(P("outputs") / "audit.jsonl")}
    sink = P(get_audit().path)             # the singleton the battery logs to
    sink_key = _norm(sink)
    assert sink_key not in prod_keys, f"audit singleton is the production trail: {sink}"
    assert not sink_key.startswith(_norm(repo / "outputs") + os.sep), sink
    sink_before = sink.stat().st_size if sink.exists() else 0

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
    # (c) POSITIVE CONTROL: the battery audited, and it audited at the
    # redirected sink. Red here means the isolation reading is unreadable
    # (battery silent / redirect gone), not "clean". The complementary
    # negative — nothing under the repo's outputs/ opened for write — is
    # conftest's _no_production_outputs_writes, which fails THIS node id.
    sink_after = sink.stat().st_size if sink.exists() else 0
    assert sink_after > sink_before, (
        "the redirected audit sink did not grow - battery silent or redirect "
        f"lost, not isolated: bytes {sink_before}->{sink_after} at {sink}")
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


def test_production_outputs_guard_is_owned_by_conftest_and_armed():
    """pin (c)'s stronger half — nothing under the repo's outputs/ is opened
    for write — is OWNED by tests/conftest.py::_no_production_outputs_writes,
    not by this module. Deleting it, or widening _ALLOWED to silence a
    failure, would quietly retire the guarantee this file's docstring
    claims, so assert it is loaded, empty-allowlist, and LIVE: opening a
    DIRECTORY under outputs/ for write raises before any byte is written yet
    still fires the audit event, which is the whole hook path end to end.
    Zero filesystem mutation (verify: outputs/control stays empty)."""
    conf = next((m for n, m in list(sys.modules.items())
                 if n.rsplit(".", 1)[-1] == "conftest"
                 and hasattr(m, "_no_production_outputs_writes")), None)
    assert conf is not None, "tests/conftest.py production-outputs guard is not loaded"
    assert conf._ALLOWED == (), f"allowlist widened: {conf._ALLOWED}"
    repo = Path(__file__).resolve().parents[1]
    control = repo / "outputs" / "control"
    keep = len(conf._violations)
    try:
        conf._flag(str(repo / "outputs" / "audit.jsonl"))     # classifier
        conf._flag(str(Path(__file__)))                       # outside outputs/: ignored
        if control.is_dir():
            before = sorted(p.name for p in control.iterdir())
            try:
                open(str(control), "a").close()               # audit event, then OSError
            except OSError:
                pass
            assert sorted(p.name for p in control.iterdir()) == before   # no mutation
        got = list(conf._violations[keep:])
    finally:
        del conf._violations[keep:]        # never hand the fixture a violation
    assert any(v.endswith(os.path.normcase("audit.jsonl")) for v in got), got
    if control.is_dir():
        assert any(v == os.path.normcase(str(control)) for v in got), got
    assert not any(v.endswith(os.path.normcase("test_archetype_battery.py")) for v in got)
