"""CUT #10 — the verified-defects boundary (era-7). Pins for B1-B6 + the stamp.

Every one of these was a CONFIRMED defect, reproduced against the running
system on 2026-09-05 and adversarially re-verified, then held behind the
era-6 accrual moratorium's cohort-resetting fences until the operator
adjudicated them as one bundled boundary on 2026-09-06. Each pin FAILS on the
pre-cut code; each was mutation-checked.

  B1  core/watchdog.py       never-delivered book read FRESH (age 0)
  B2  risk/profit_tiers.py   est_fee_bps absent-default 0.0 -> 6bps floor
  B3  risk/protocols.py      NaN equity -> multiplier 1.0, no reason (fail OPEN)
  B4  main.py                a read-only venue could be the execution feed
  B5  core/fill_ledger.py    dedup disarmed silently on an unloadable cache
  B6  core/config_guard.py   peak-arrival constant 2.4x stale; cap saturated
  --  core/fill_ledger.py    EXEC_ERA minted 10-<sha> in the SAME commit
"""
from __future__ import annotations

import csv
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------- B1
def test_never_delivered_book_is_STALE():
    """Was a strict xfail from creation until this cut. `get(a, now)` read an
    asset the feed silently dropped as age 0 - neither warn nor critical."""
    from core.watchdog import Watchdog
    wd = Watchdog({"stale_warn_sec": 30.0, "stale_critical_sec": 120.0})
    st = wd.evaluate(now=1_000_000.0, book_ts={}, assets=["BTC"],
                     kraken_mids={"BTC": 100.0}, fair_values={"BTC": 100.0},
                     equity=1000.0, open_positions=1, dry_run=False)
    assert "BTC" in st.stale_assets, "a never-delivered book still reads FRESH"
    assert st.critical_stale, "age == now must clear the critical threshold"


def test_a_delivered_fresh_book_is_still_fresh():
    """ANTI-RUBBER-STAMP: the fix must not make every asset stale."""
    from core.watchdog import Watchdog
    wd = Watchdog({"stale_warn_sec": 30.0, "stale_critical_sec": 120.0})
    st = wd.evaluate(now=1_000_000.0, book_ts={"BTC": 999_995.0},
                     assets=["BTC"], kraken_mids={"BTC": 100.0},
                     fair_values={"BTC": 100.0}, equity=1000.0,
                     open_positions=1, dry_run=False)
    assert "BTC" not in st.stale_assets


def test_the_strict_xfail_marker_came_off_with_the_fix():
    """The docket said the marker must change in the same commit as the fix -
    a strict xfail that starts passing reds the whole suite."""
    # AST, not text: the first draft sliced the 1,200 chars before the def and
    # caught the PREVIOUS test's body saying "the pin xfails". Decorators are
    # the only thing that can mark a test, so inspect those.
    import ast
    tree = ast.parse((ROOT / "tests/test_fail_open_pins.py")
                     .read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
              and n.name == "test_never_delivered_book_reads_stale")
    decos = [ast.unparse(d) for d in fn.decorator_list]
    assert not any("xfail" in d for d in decos), (
        f"test_never_delivered_book_reads_stale is still marked: {decos}")


# ------------------------------------------------------------------- B2
def _engine(cfg):
    from risk.profit_tiers import ProfitTierEngine
    return ProfitTierEngine(cfg)


def test_ABSENT_est_fee_bps_does_not_price_fees_as_free():
    """The absent-key default was 0.0: (2*0 + 6)/1e4 = 6 bps break-even floor
    where the booked schedule gives 76. Now the venue's WORST published taker
    row - a wider floor holds exits longer, never tighter."""
    from core.venue_fees import worst_row
    eng = _engine({"be_buffer_bps": 6.0})            # est_fee_bps ABSENT
    assert eng.est_fee_bps == pytest.approx(worst_row()[1]), (
        f"absent est_fee_bps defaulted to {eng.est_fee_bps} - not the venue's "
        f"worst published taker row")
    assert eng.est_fee_bps > 0.0, "fees priced as FREE on an absent key"


def test_an_EXPLICIT_zero_est_fee_bps_stays_legal():
    """The quant-trials world and several fixtures pass 0 on purpose."""
    assert _engine({"est_fee_bps": 0, "be_buffer_bps": 6.0}).est_fee_bps == 0.0


def test_config_guard_FATALs_an_absent_est_fee_bps():
    """Production must never reach ANY default. The other four fee keys were
    already FATAL-on-absent; est_fee_bps joins them."""
    import copy
    import json

    from core.config_guard import validate
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    bad = copy.deepcopy(cfg)
    bad["profit_taking"].pop("est_fee_bps", None)
    fatals = [m for s, m in validate(bad) if s == "FATAL"]
    assert any("est_fee_bps" in m for m in fatals), (
        "removing profit_taking.est_fee_bps produced no fee-specific FATAL")


# ------------------------------------------------------------------- B3
def _stack():
    from risk.protocols import RiskProtocolStack
    rp = RiskProtocolStack({"enabled": True,
                            "loss_budget": {"enabled": True}})
    rp.observe(10_000.0)
    return rp


@pytest.mark.parametrize("equity", [float("nan"), float("inf"),
                                    float("-inf"), 0.0, -5.0])
def test_nonfinite_equity_FAILS_CLOSED_with_a_reason(equity):
    """Traced before the fix: max(nan,0.0) keeps the NaN, budget_taper_mult
    returns NaN, both `m <= EPS` and `m < 0.999` are False -> no multiply, no
    reason, multiplier 1.0. The hard veto whose contract is 'fails CLOSED,
    never open' failed open on the one input it could not do arithmetic on."""
    from core.codes import Code
    rp = _stack()
    mult, reasons = rp.entry_multiplier(0.05, equity, 50.0, "BTC/USD", 0.1)
    assert mult == 0.0, f"equity={equity!r} produced multiplier {mult} - fail OPEN"
    assert any(Code.RP_EQUITY_NONFINITE in str(r) for r in reasons), (
        f"no registered reason code emitted for equity={equity!r}: {reasons}")


def test_a_finite_healthy_equity_is_NOT_vetoed():
    """ANTI-RUBBER-STAMP: the closed door must open for a normal book."""
    rp = _stack()
    mult, reasons = rp.entry_multiplier(0.05, 10_000.0, 50.0, "BTC/USD", 0.1)
    assert mult > 0.0
    assert not any("RP-052" in str(r) for r in reasons)


# ------------------------------------------------------------------- B4
def _engine_kwargs():
    """The minimum LiquidityBot construction that reaches OrderManager."""
    import json
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg["system"]["record_feeds"] = False
    return cfg


def test_a_readonly_venue_cannot_be_the_execution_feed():
    """Verified 2026-09-05: a live submit on a non-Kraken feed PLACED, wire
    payload emitted, while two controls in the same harness refused. The
    invariant rested on a default value. Now it is an assertion."""
    from data.okx_feed import OKXFeed
    from main import LiquidityBot
    rogue = OKXFeed.__new__(OKXFeed)          # a real read-only venue class
    # the engine touches kraken_pair() before it reaches OrderManager; give
    # the rogue that surface so the ONLY thing that can stop it is the pin
    rogue.kraken_pair = lambda s: "XXBTZUSD"
    with pytest.raises(RuntimeError, match="INVARIANT #3"):
        LiquidityBot(_engine_kwargs(), kraken=rogue, resume=False)


def test_a_wrapped_readonly_venue_is_also_refused():
    """FeedRecorder wraps the feed; the check must unwrap it."""
    from data.binanceus_feed import BinanceUSFeed
    from main import LiquidityBot
    inner = BinanceUSFeed.__new__(BinanceUSFeed)
    wrapped = SimpleNamespace(_feed=inner, kraken_pair=lambda s: "XXBTZUSD")
    with pytest.raises(RuntimeError, match="INVARIANT #3"):
        LiquidityBot(_engine_kwargs(), kraken=wrapped, resume=False)


def test_test_doubles_still_construct():
    """ANTI-RUBBER-STAMP: a deny-list, not an allow-list - the suite's mocks
    must keep working or every engine test dies with this pin."""
    from main import LiquidityBot
    dbl = SimpleNamespace(kraken_pair=lambda s: "XETHZUSD")
    try:
        LiquidityBot(_engine_kwargs(), kraken=dbl, resume=False)
    except RuntimeError as e:
        assert "INVARIANT #3" not in str(e), "a test double was refused"
    except Exception:                          # noqa: BLE001
        pass                                   # other construction faults are not this pin's subject


# ------------------------------------------------------------------- B5
def _row(oid="o1", size=1.0, px=100.0):
    return {"ts": 1.0, "order_id": oid, "position_id": "p", "purpose": "entry",
            "symbol": "BTC/USD", "side": "buy", "ordertype": "limit",
            "post_only": True, "attempt": 1, "fill_size": size,
            "fill_price": px, "arrival_ref": px, "slip_bps": 0.0,
            "fees_delta_usd": 0.02, "remaining": 0.0, "reason": "",
            "exec_era": "t", "book": ""}


def test_an_unloadable_cache_does_NOT_disarm_dedup(tmp_path, monkeypatch):
    """Before the cut: load failure -> EMPTY set cached -> the duplicate landed
    (measured rows=3). Now: load failure -> direct scan -> duplicate REFUSED."""
    import core.fill_ledger as FL
    path = tmp_path / "fills.csv"
    FL.append_fill(path, _row())                  # row 1
    FL._seen_keys.pop(str(path), None)            # forget the cache
    monkeypatch.setattr(FL, "_load_keys", lambda p: None)   # cache unloadable
    FL.append_fill(path, _row())                  # the replay
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    assert len(rows) == 1, (
        f"{len(rows)} rows - a replayed fill re-landed in the P&L book while "
        f"the dedup cache was unloadable")


def test_unknowable_dedup_state_REFUSES_the_row_and_says_so(tmp_path, monkeypatch, caplog):
    """If the direct scan fails too, the replay question is unknowable: refuse
    the row (a lost row is recoverable from the audit trail, a duplicate in
    realized P&L is not) and emit the registered code."""
    import logging

    import core.fill_ledger as FL
    path = tmp_path / "fills.csv"
    FL.append_fill(path, _row("o1"))
    FL._seen_keys.pop(str(path), None)
    monkeypatch.setattr(FL, "_load_keys", lambda p: None)

    def _boom(p, k):
        raise OSError("locked")
    monkeypatch.setattr(FL, "_key_on_disk", _boom)
    with caplog.at_level(logging.ERROR):
        FL.append_fill(path, _row("o2"))
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    assert len(rows) == 1, "a row was appended with dedup state unknowable"
    assert any("OM-086" in r.getMessage() for r in caplog.records), (
        "the refusal carried no registered reason code")


def test_the_REAL_load_failure_path_does_not_disarm_dedup(tmp_path, monkeypatch):
    """Exercises _load_keys ITSELF, not a monkeypatched stand-in.

    Mutation caught the gap (2026-09-06): the two pins above inject None
    straight into the append path, so reverting _load_keys to `return set()`
    on failure - the original defect - left them green. This one makes the
    real reader raise once (inside _load_keys) and then behave, so the only
    thing separating rows==1 from rows==2 is what _load_keys returns."""
    import core.fill_ledger as FL
    path = tmp_path / "fills.csv"
    FL.append_fill(path, _row("o1"))
    FL._seen_keys.pop(str(path), None)
    real = FL.csv.DictReader
    calls = {"n": 0}

    def one_shot(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:               # the _load_keys read
            raise OSError("byte-0 lock")
        return real(*a, **k)              # the direct scan, and the reader below
    monkeypatch.setattr(FL.csv, "DictReader", one_shot)
    FL.append_fill(path, _row("o1"))      # the replay
    monkeypatch.undo()
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    assert calls["n"] >= 2, "fixture: the load failure never reached _load_keys"
    assert len(rows) == 1, (
        f"{len(rows)} rows - _load_keys turned a read failure into an EMPTY "
        f"cache and the replayed fill re-landed in realized P&L")


def test_a_healthy_cache_still_appends_a_NEW_fill(tmp_path):
    """ANTI-RUBBER-STAMP: fail-closed must not become fail-always."""
    import core.fill_ledger as FL
    path = tmp_path / "fills.csv"
    FL._seen_keys.pop(str(path), None)
    FL.append_fill(path, _row("a"))
    FL.append_fill(path, _row("b"))
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    assert len(rows) == 2


# ------------------------------------------------------------------- B6
def test_capacity_constant_is_the_remeasured_peak_and_the_cap_clears_demand():
    """43.7/h on the check's own statistic (rolling 36h window, full-width,
    per lineage), two independent derivations agreeing to the tenth. Demand
    1574; cap must clear it. Pinned as a RELATIONSHIP plus a floor."""
    import json

    import core.config_guard as cg
    assert cg._CAND_REF_PEAK_ARRIVALS_PER_H >= 43.7, (
        "the peak-arrival constant fell back below the 2026-09-06 measurement")
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    h = int(cfg["ml"]["label_max_bars"]) * 300 / 3600
    demand = math.ceil(cg._CAND_REF_PEAK_ARRIVALS_PER_H * h)
    assert int(cfg["ml"]["max_open_candidates"]) >= demand, (
        f"max_open_candidates {cfg['ml']['max_open_candidates']} is below the "
        f"Little's-law demand {demand} - the queue saturates and newest-pop "
        f"eviction refuses labeling to the busy-hour signals")


# ---------------------------------------------------------------- stamp
def test_exec_era_was_minted_for_this_cut():
    """The stamp travels WITH the row and must bump in the SAME commit as the
    boundary (core/fill_ledger.py's own rule). Format: <cut>-<8 hex>."""
    from core.fill_ledger import EXEC_ERA
    m = re.match(r"^(\d+)-([0-9a-f]{8})$", EXEC_ERA)
    assert m, f"EXEC_ERA {EXEC_ERA!r} is not <cut>-<8hex>"
    assert int(m.group(1)) >= 10, (
        f"EXEC_ERA {EXEC_ERA!r} still names a pre-cut-10 era - the B1-B6 "
        f"code is live but every fill would be stamped as era-6")
