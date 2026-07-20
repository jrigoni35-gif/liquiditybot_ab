"""Deterministic engine driver for STEP-THROUGH debugging (VS Code F5).

The suite/smoke entries in launch.json tell you WHETHER the engine is
healthy; this driver is for WATCHING IT THINK: it builds the real
LiquidityBot on the smoke harness's injected feeds (network-free, seeded,
QA-redirected outputs), fills the book to the concurrency cap through the
real order pipeline (forced signals, same recipe as smoke's lifecycle
test), then TIME-TRAVELS `now` past the label horizon so the ML-073
realization path and its VOI fastpath fire while you step them. Drop
breakpoints anywhere in main.py — the interesting ones:

    main.py  _maybe_realize_mature_label   (ML-073 + VOI fastpath decision)
    main.py  effective_realize_spans       (full-book fastpath arithmetic)
    main.py  _submit_exit                  (escalation ladder / dedup)
    ml/history.py  log_close               (the live label being banked)

Run:  python scripts/debug_cycle.py [--watch-cycles N] [--timetravel-h H]
or F5 -> "Engine: step deterministic cycles (injected feeds)".

Scripting inputs: none — fully non-interactive; exits on cycle exhaustion.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from smoke_test import (  # noqa: E402
    MockBinanceUS, MockKraken, MockOKX, qa_redirect_paths)


def build_bot():
    """The smoke harness's hermetic bot: real config, mocked venues, entry
    knobs from the lifecycle smoke (clear net-Kelly so forced entries fill)."""
    from main import LiquidityBot, load_config
    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    cfg["system"]["dry_run"] = True
    cfg["capital_management"]["starting_capital_usd"] = 10_000
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg["position_sizer"] = dict(cfg.get("position_sizer", {}),
                                 entry_cooldown_min=0, min_p_win=0.50)
    cfg["ml"]["cold_start_prior_p"] = 0.66
    cfg["pretrade"] = dict(cfg.get("pretrade", {}),
                           min_edge_cost_ratio=0.1, price_exit_leg=False)
    qa_redirect_paths(cfg, "debug_cycle")       # owns model/history paths
    # fresh corpus EVERY session — must come AFTER the redirect (unlinking
    # a pre-redirect path left the real file accumulating live rows across
    # runs until until_live_rows auto-off silenced the very ML-073 path
    # this driver demonstrates; adversarially-verified fleet finding)
    Path(cfg["ml"]["history_path"]).unlink(missing_ok=True)
    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = LiquidityBot(cfg, okx=MockOKX(prices),
                       binanceus=MockBinanceUS(prices),
                       kraken=MockKraken(prices), resume=False)
    return bot, prices


def force_signals(bot):
    """Bypass the gate stack (subject here is the realize path, not signal
    quality) — same mechanism as smoke's test_entry_fill_exit_path."""
    from strategies.signal_gates import SignalResult
    forced = {"on": True}
    real_eval = bot.gates.evaluate_asset

    def fake_eval(base_asset, view):
        if forced["on"] and base_asset in ("ETH", "BTC"):
            return SignalResult(symbol=f"{base_asset}/USD", direction="long",
                                confidence=1.0, size=0.0, all_confirmed=True,
                                gates_passed={})
        return real_eval(base_asset, view)

    bot.gates.evaluate_asset = fake_eval
    for a in ("ETH", "BTC"):                    # longs allowed regardless of
        st = bot.macro.state(a)                 # the synthetic regime label
        st.label = "bull_quiet"
        st.playbook = dict(bot.macro.playbooks["bull_quiet"])
        bot.macro._states[a] = st
    return forced


def watch(bot, t, label):
    """The debugger watch-table, printed per step (what you'd pin in the
    VARIABLES pane): book, ages, label corpus, working orders."""
    ages = sorted(round((t - p.opened_at.timestamp()) / 3600.0, 2)
                  for p in bot.state.open_positions())
    sc = bot.history.source_counts()
    orders = [(o.purpose, o.symbol) for o in bot.orders.open_orders()]
    print(f"[{label:>12}] book={len(ages)} ages_h={ages} "
          f"labels={sc or {}} orders={orders}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--watch-cycles", type=int, default=12,
                    help="slow ticks to watch after the time travel")
    ap.add_argument("--timetravel-h", type=float, default=2.5,
                    help="hours to jump `now` forward so ML-073 matures")
    ap.add_argument("--cap", type=int, default=2,
                    help="concurrency cap override — 2 is always reachable "
                         "with the two mock assets, so 'book FULL' (the VOI "
                         "fastpath arm condition) actually occurs; pass 0 to "
                         "keep the config value and watch the free-slot "
                         "(full-window) branch instead")
    args = ap.parse_args()

    bot, prices = build_bot()
    if args.cap:
        bot.capital.max_concurrent_positions = args.cap
    cap = bot.capital.max_concurrent_positions
    rng = np.random.default_rng(21)
    t = time.time()

    print(f"== phase 1: fill the book to the cap ({cap}) through the real "
          f"order pipeline (forced signals) ==")
    bot.hourly_cycle(t)
    forced = force_signals(bot)
    for c in range(80):
        bot.fast_cycle(t)
        if c % 3 == 0:
            bot.slow_cycle(t)
        t += 5.0
        if bot.state.open_position_count() >= cap:
            break
    forced["on"] = False
    watch(bot, t, "book filled")

    print(f"== phase 2: time-travel now +{args.timetravel_h}h -> ML-073 "
          f"horizon crossed (breakpoint: _maybe_realize_mature_label) ==")
    t += args.timetravel_h * 3600.0
    for c in range(args.watch_cycles):
        for a in prices:                        # flat drift: exits should come
            prices[a] *= float(np.exp(rng.normal(0.0, 0.0005)))  # from ML-073
        bot.fast_cycle(t)
        bot.slow_cycle(t)                       # realize path lives here
        watch(bot, t, f"slow tick {c}")
        t += 30.0
    sc = bot.history.source_counts()
    print(f"== done: live labels banked = {sc.get('live', 0)} "
          f"(candidate={sc.get('candidate', 0)}) ==")


if __name__ == "__main__":
    main()
