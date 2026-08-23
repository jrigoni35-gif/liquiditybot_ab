"""
scripts/assurance_check.py — offline power-on built-in test (PBIT)

Verifies every Assurance Build invariant with zero network access.
Run after any config or code change, before smoke_test.py:

    python scripts/assurance_check.py

Exit code 0 = all invariants hold. Nonzero = the printed invariant is
broken; do not arm live.
"""

import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

PASS, FAIL = 0, 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok    {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import logging
    logging.disable(logging.CRITICAL)
    # PBIT self-tests (firewall battery, fault latches, OM cancels) write
    # audit records; keep them out of the production trail
    from core.audit import configure_audit
    from ml.registry import configure_registry
    configure_audit(os.path.join(tempfile.gettempdir(),
                                 "liqbot_assurance_audit.jsonl"))
    configure_registry(os.path.join(tempfile.gettempdir(),
                                    "liqbot_assurance_models"))

    print("[1] risk firewall PBIT")
    from execution.risk_firewall import RiskFirewall
    fw = RiskFirewall({"enabled": True}, None)
    check("power-on self test passes", fw.self_test() == [])
    v = fw.check(pair="T/USD", side="buy", purpose="entry",
                 price=float("nan"), size=1.0, ref_price=100.0,
                 equity=1e6)
    check("NaN entry price rejects (FW-011)",
          not v.allowed and any("FW-011" in r for r in v.reasons))
    v = fw.check(pair="T/USD", side="sell", purpose="exit",
                 price=float("nan"), size=1.0, ref_price=100.0,
                 equity=1e6)
    check("NaN exit price substitutes ref (fail-safe)",
          v.allowed and v.price == 100.0)

    print("[2] audit chain integrity")
    from core.audit import AuditTrail
    with tempfile.TemporaryDirectory() as td:
        a = AuditTrail(os.path.join(td, "audit.jsonl"))
        for i in range(5):
            a.log("pbit", "FT-010", f"record {i}", {"i": i})
        r = a.verify()
        check("5-record chain verifies", r["ok"] and r["records"] == 5)
        # tamper with record 3 and confirm the chain breaks there
        p = os.path.join(td, "audit.jsonl")
        with open(p, encoding="utf-8") as f:
            lines = f.readlines()
        lines[2] = lines[2].replace("record 2", "record X")
        with open(p, "w", encoding="utf-8") as f:
            f.writelines(lines)
        r = a.verify()
        check("tampering detected at exact record",
              not r["ok"] and r["first_break"] == 3)

    print("[3] fault manager state machine")
    from core.fault import FaultManager, Severity, OpState
    fm = FaultManager()
    fm.arm()
    check("INIT -> ARMED on arm()", fm.state is OpState.ARMED)
    fm.latch("pbit_fault", Severity.FAULT, "test")
    check("FAULT forces DEGRADED, new risk refused",
          fm.state is OpState.DEGRADED and not fm.allow_new_risk())
    check("exits always allowed", fm.allow_exits())
    fm.latch("pbit_crit", Severity.CRITICAL, "test")
    check("CRITICAL forces HALTED", fm.state is OpState.HALTED)
    fm.clear_fault("pbit_crit")
    check("clearing critical -> DEGRADED (fault remains)",
          fm.state is OpState.DEGRADED)
    fm.clear_fault("pbit_fault")
    check("all clear -> ARMED", fm.state is OpState.ARMED)

    print("[4] quoter structural fee floor")
    from execution.market_maker import AvellanedaStoikovQuoter
    q = AvellanedaStoikovQuoter({"min_half_spread_bps": 1.0,
                                 "min_profit_bps": 1.0})
    quote = q.quote(100.0, 0.05, 0.0, "liquid", fee_bps=25.0)
    check("half spread >= fee + margin (QT-010)",
          quote.half_spread_bps >= 26.0 - 1e-9)
    check("bid <= reservation <= ask",
          quote.bid <= quote.reservation <= quote.ask)
    quote = q.quote(100.0, 0.5, 1.0, "liquid", fee_bps=25.0)
    check("max long inventory keeps quote uncrossed",
          quote.bid <= quote.reservation <= quote.ask)
    bad = q.quote(float("nan"), 0.05, 0.0)
    check("NaN fair value refuses to quote", bad.bid == 0.0)

    print("[5] fair value uncertainty discount")
    from execution.fair_value import FairValueEngine
    fv = FairValueEngine({"ema_alpha": 0.35, "edge_haircut_z": 1.0})
    book = {"bids": [[99.9, 5]], "asks": [[100.1, 5]]}
    for _ in range(10):
        fv.update("T", [book], book)
    st = fv.state("T")
    check("stable inputs -> updated FV near mid",
          st.updated and abs(st.fair_value - 100.0) < 0.2)
    poisoned = {"bids": [[float("nan"), 5]], "asks": [[100.1, 5]]}
    st2 = fv.update("T", [poisoned], book)
    check("poisoned venue book cannot corrupt FV",
          math.isfinite(st2.fair_value))

    print("[6] pre-trade EV gate")
    from execution.pretrade import PreTradeGate, PreTradeContext
    g = PreTradeGate({"maker_fee_bps": 25, "taker_fee_bps": 40,
                      "min_edge_cost_ratio": 1.3})
    deep = {"bids": [[99.9, 50]], "asks": [[100.1, 50]]}
    ctx = PreTradeContext(kraken_book=deep, sigma_daily_pct=3.0,
                          adv_usd=5e7, liq_label="liquid",
                          spread_bps=5.0, staleness_ms=100.0)
    # re-baselined for round-trip pricing (price_exit_leg): "strong" at
    # the 25/40 tier now means clearing entry + taker-exit + half-spread
    # (~74bps cost -> ~96bps bar at 1.3x), evidenced by 9/9 live
    # cost_overrun postmortems at median 44bps under entry-only pricing
    d = g.evaluate("buy", 1.0, 100.0, exp_alpha_bps=110.0,
                   fv_edge_bps=10.0, ctx=ctx)
    check("strong edge approves with p_fill/EV attached",
          d.approved and 0 < d.p_fill <= 1 and d.ev_bps > 0)
    d = g.evaluate("buy", 1.0, 100.0, exp_alpha_bps=20.0,
                   fv_edge_bps=0.0, ctx=ctx)
    check("thin edge below fee stack rejects (PT-041)",
          not d.approved and any("PT-041" in r for r in d.reasons))
    d = g.evaluate("buy", float("nan"), 100.0, 50.0, 0.0, ctx)
    check("non-finite input rejects (PT-010)",
          not d.approved and any("PT-010" in r for r in d.reasons))
    check("maker cost includes adverse selection",
          g.evaluate("buy", 1.0, 100.0, 80.0, 10.0, ctx).est_cost_bps
          > 25.0)

    print("[7] sizer net-Kelly + drawdown throttle")
    from risk.position_sizer import payoff_ratio_from_config
    profit = {f"tier_{i}": {"trigger_pct_gain": t,
                            "close_pct_of_position": 25}
              for i, t in enumerate((1.0, 2.0, 3.5, 5.0), 1)}
    b_gross = payoff_ratio_from_config(profit, {"stop_loss_pct": 2.0}, 0.0)
    b_net = payoff_ratio_from_config(profit, {"stop_loss_pct": 2.0}, 0.5)
    check("net payoff ratio strictly below gross", b_net < b_gross)

    print("[8] order state machine")
    from execution.order_manager import OrderManager, ManagedOrder
    om = OrderManager(feed=None, config={}, dry_run=True)
    o = ManagedOrder(order_id="pbit", txid="DRY", asset="T", pair="TUSD",
                     symbol="T/USD", side="buy", price=100.0, size=1.0)
    check("pending -> filled legal", om._transition(o, "filled", "pbit"))
    check("filled is terminal (filled -> partial refused)",
          not om._transition(o, "partial", "pbit"))
    o2 = ManagedOrder(order_id="pbit2", txid="DRY", asset="T",
                      pair="TUSD", symbol="T/USD", side="buy",
                      price=100.0, size=1.0)
    om._transition(o2, "expired", "pbit")
    check("illegal transition forces safe terminal, never a fill",
          not om._transition(o2, "filled", "pbit")
          and o2.status in ("expired", "cancelled"))
    check("market order refused for entries (OM-011)",
          om.submit(asset="T", symbol="T/USD", pair="TUSD", side="buy",
                    price=100.0, size=1.0, purpose="entry",
                    ordertype="market") is None)

    print("[9] ML contract + registry + governor")
    from ml.contracts import get_contract
    from ml.features import FEATURE_NAMES
    import numpy as np
    c = get_contract()
    good = np.zeros(len(FEATURE_NAMES))
    good[FEATURE_NAMES.index("depth_ratio")] = 1.0
    good[FEATURE_NAMES.index("fear_greed")] = 0.5
    ok, _ = c.check(good)
    check("in-range vector passes contract", ok)
    bad = good.copy()
    bad[0] = float("nan")
    ok, reasons = c.check(bad)
    check("NaN feature fails contract (ML-010)",
          not ok and any("ML-010" in r for r in reasons))
    ok, reasons = c.check(good[:-1])
    check("schema-length mismatch fails (ML-013)",
          not ok and any("ML-013" in r for r in reasons))

    from ml.registry import ModelRegistry
    with tempfile.TemporaryDirectory() as td:
        reg = ModelRegistry(td)
        art = os.path.join(td, "m.json")
        with open(art, "w", encoding="utf-8") as f:
            f.write('{"kind": "logistic"}')
        mid = reg.register(art, {"kind": "logistic", "oof_brier": 0.21})
        check("artifact registers with id", len(mid) == 12)
        check("untampered artifact verifies",
              reg.verify(art)["ok"] is True)
        with open(art, "a", encoding="utf-8") as f:
            f.write(" ")
        check("tampered artifact fails verify (ML-011)",
              reg.verify(art)["ok"] is False)

    from ml.monitor import ModelMonitor, wilson_lcb
    check("wilson LCB sane (10/20 -> ~0.33)",
          0.30 < wilson_lcb(10, 20) < 0.40)
    pbit_flag = os.path.join(tempfile.gettempdir(), "liqbot_pbit_retrain.flag")
    m = ModelMonitor({"window_trades": 30, "min_trades_to_judge": 15,
                      "retrain_flag_path": pbit_flag})
    for _ in range(20):                       # promised 0.75, delivered 0.30
        m.record_close(0.75, 0, True)
        m.record_close(0.75, 1, True) if _ % 3 == 0 else None
    check("credible hit shortfall degrades the model", m.level >= 1)
    check("kill switch bounds hold",
          m.kelly_mult >= m.kelly_mult_min - 1e-9
          and m.shrinkage <= m.shrink_max + 1e-9)
    snap = m.to_dict()
    m2 = ModelMonitor({"retrain_flag_path": pbit_flag})
    m2.restore(snap)
    check("governor persistence round-trips", m2.level == m.level)


    print("[10] informed-flow gates + execution tactics")
    from strategies.informed_flow import InformedFlowEngine

    def mk_candles(n, trend=1.0, vol=100.0, last_vol=None, clv=0.9):
        out, px = [], 100.0
        for i in range(n):
            px *= (1.0 + 0.001 * trend)
            v = vol * (0.9 if i % 2 else 1.1)      # baseline needs variance
            if last_vol is not None and i == n - 1:
                v = last_vol
            rng_ = px * 0.004
            lo = px - rng_ * clv
            hi = lo + rng_
            out.append({"open": px * 0.999, "high": hi, "low": lo,
                        "close": px, "volume": v})
        return out

    eng = InformedFlowEngine({"persistence_evals": 3, "vol_z_min": 2.0})
    view = {"kraken_symbol": "ETH/USD", "imbalance_ratio": 1.8,
            "funding_rate": 0.0001,
            "candles": mk_candles(40, trend=1.0, last_vol=400.0, clv=0.9)}
    r = None
    for _ in range(3):
        r = eng.evaluate_asset("ETH", view)
    assert r is not None
    check("persistent bullish informed flow confirms long",
          r.all_confirmed and r.direction == "long" and r.urgency > 0)
    eng2 = InformedFlowEngine({"persistence_evals": 3})
    flip = dict(view)
    r = None
    for i in range(3):
        flip["imbalance_ratio"] = 1.8 if i % 2 == 0 else 0.7
        r = eng2.evaluate_asset("ETH", flip)
    assert r is not None
    check("non-persistent imbalance does NOT confirm (noise/spoof)",
          not r.all_confirmed)
    eng3 = InformedFlowEngine({"persistence_evals": 3})
    absorb = dict(view)
    absorb["candles"] = mk_candles(40, trend=1.0, last_vol=400.0, clv=0.1)
    r = None
    for _ in range(3):
        r = eng3.evaluate_asset("ETH", absorb)
    assert r is not None
    check("price-up-on-distribution (absorption) is vetoed",
          not r.all_confirmed)
    r = InformedFlowEngine({}).evaluate_asset("ETH", {"candles": None,
                                                      "imbalance_ratio":
                                                      float("nan")})
    check("malformed view fails closed, never raises", not r.all_confirmed)

    from execution.tactics import ExecutionPlanner
    from execution.market_maker import Quote
    q = Quote(reservation=100.0, bid=99.7, ask=100.3,
              half_spread_bps=30.0, skew_bps=0.0)
    book = {"bids": [[99.95, 5]], "asks": [[100.05, 5]]}
    pl = ExecutionPlanner({})
    check("low urgency rests at the AS quote",
          pl.plan_entry("long", q, book, 0.1).style == "as_quote")
    check("mid urgency joins the touch (still maker)",
          pl.plan_entry("long", q, book, 0.5).style == "join"
          and pl.plan_entry("long", q, book, 0.5).post_only)
    imp = pl.plan_entry("long", q, book, 0.8)
    check("high urgency improves inside the spread without crossing",
          imp.style == "improve" and 99.95 < imp.price < 100.05
          and imp.post_only)
    tk = pl.plan_entry("long", q, book, 0.95)
    check("max urgency proposes taker at the opposite touch",
          tk.style == "taker" and tk.taker and not tk.post_only
          and abs(tk.price - 100.05) < 1e-9)
    check("taker suppressed in spoofy liquidity",
          pl.plan_entry("long", q, book, 0.95, "spoofy").style != "taker")
    check("no-taker config caps the ladder at improve",
          ExecutionPlanner({"allow_taker": False})
          .plan_entry("long", q, book, 0.95).style != "taker")
    check("malformed book degrades to AS quote",
          pl.plan_entry("long", q, {}, 0.95).style == "as_quote")

    print("[11] training-corpus timestamp coherence")
    # TANK Debate 1 item F (docs/superpowers/specs/2026-07-30-tank-
    # program-design.md, verdict in the session record): the purged
    # walk-forward and the uniqueness weighting both ASSUME each row's
    # [signal_ts, ts] span is coherent — nothing audited the raw file
    # until now. Hard invariants: ts finite/positive, signal_ts <= ts
    # when present, no far-future stamps. Rows with a missing signal_ts
    # are the loader's documented legacy fallback (sig := ts) — counted
    # and reported as a trend, never a failure.
    import csv as _csv
    import time as _time
    # CORPUS IS PINNED, NOT ASSUMED (2026-08-23). The path was relative, so
    # running this from a bare git worktree - which is exactly how the deploy
    # battery would run it - found no outputs/ and passed the whole section
    # VACUOUSLY, printing "ok" and contributing to a 48/0 green that had never
    # read a corpus. Proven in a real `git worktree add --detach`. LB_OUTPUTS
    # lets a caller point this at the LIVE corpus (the same trick
    # auto_update._replay_gate_passes already uses with --recording-dir), and
    # the vacuous branch now NAMES itself so the degraded form can never be
    # mistaken for the verified one on a summary line.
    _out_dir = os.environ.get("LB_OUTPUTS") or "outputs"
    hist_path = os.path.join(_out_dir, "signal_history.csv")
    if not os.path.exists(hist_path):
        check(f"signal_history ABSENT at {hist_path} -> section VACUOUS "
              f"(this green proves nothing about any corpus)", True)
    else:
        bad_order = bad_finite = future = fallback = total = 0
        horizon = _time.time() + 600.0     # small skew allowance
        with open(hist_path, encoding="utf-8", newline="") as f:
            for row in _csv.DictReader(f):
                total += 1
                try:
                    ts = float(row.get("ts") or "nan")
                except ValueError:
                    ts = float("nan")
                sig_raw = (row.get("signal_ts") or "").strip()
                if not (math.isfinite(ts) and ts > 0):
                    bad_finite += 1
                    continue
                if ts > horizon:
                    future += 1
                if not sig_raw:
                    fallback += 1
                    continue
                try:
                    sig = float(sig_raw)
                except ValueError:
                    bad_finite += 1
                    continue
                if not (math.isfinite(sig) and sig > 0):
                    bad_finite += 1
                elif sig > ts + 1e-6:
                    bad_order += 1
        check(f"every ts finite and positive ({total} rows)",
              bad_finite == 0)
        check("no signal_ts after its own close ts", bad_order == 0)
        # Far-future stamps are CLOCK SKEW (an ops condition that self-
        # heals), not data corruption - report-only by conscious decision
        # (2026-07-31 review #5): a hard gate here wedges every battery-
        # gated auto-deploy behind a hand-edit of the corpus. The two
        # checks above stay hard: they detect writer bugs that silently
        # poison training and SHOULD stop deploys.
        print(f"        far-future ts rows: {future}/{total} "
              f"(clock-skew trend, report-only)")
        print(f"        legacy sig-fallback rows: {fallback}/{total} "
              f"(informational trend - loader substitutes ts)")

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
