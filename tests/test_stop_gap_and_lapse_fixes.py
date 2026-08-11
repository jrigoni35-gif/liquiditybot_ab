"""
Regressions for the 2026-07-14 stop-enforcement-gap incident and the
adversarial review of TH-016.

The lived failure: an ETH short with a 1.8% stop was carried across
runner outages; the loop that enforces stops was dead for hours, price
walked to -6.9%, and the revival sweep filled the exit there. The
postmortem attributed the loss to its 54bps fee tail (cost_overrun),
feeding 8 false causes into the monitor's window - the edge_ratio_bump
that suppresses REAL entries was being sustained by ops failures
masquerading as cost signal.

Review findings covered here:
- stop_gap attribution fires before cost_overrun and never feeds the
  cost/whipsaw governors
- first-batch candle holes must not seed the TH-016 spacing EWMA
  (median-of-batch seeding; a raw first-delta seed masked later holes)
- a pre-lapse sweep must not re-latch from surviving candle_hist
- one absurd-but-finite candle ts must not permanently kill the fence
"""
import math

from ml.monitor import ModelMonitor
from ml.postmortem import PostmortemEngine, TradeThesis
from strategies.thales import ThalesEngine


def _thesis(realized_pct, stop_pct=1.8, stopped=True, fees_usd=0.12,
            entry_usd=15.0):
    t = TradeThesis(
        position_id="p1", asset="ETH", symbol="ETH/USD", direction="short",
        entry_ts=0.0, p_win=0.62, expected_ret_pct=0.24,
        expected_cost_bps=30.0, stop_pct=stop_pct, target_pct=1.98,
        entry_regime="range", entry_liq="thin", narrative_label="neutral",
        fair_value=1759.42, quote_price=1759.21, model_scored=False)
    t.fill_price = 1759.44
    t.entry_usd = entry_usd
    t.fees_usd = fees_usd
    t.realized_ret_pct = realized_pct
    t.stopped_out = stopped
    t.exit_ts = 88560.0
    t.exit_regime = "range"
    t.exit_liq = "liquid"
    return t


def _engine(tmp_path, **cfg):
    base = {"report_dir": str(tmp_path / "pm"),
            "summary_path": str(tmp_path / "pm.csv"),
            # owed 65: without this the engine's complete path ledger falls
            # through to the PRODUCTION default - the ninth instance of the
            # QA-writes-production class, caught by conftest's tripwire
            "paths_path": str(tmp_path / "trade_paths.csv")}
    base.update(cfg)
    return PostmortemEngine(base)


def test_unenforced_stop_is_stop_gap_not_cost_overrun(tmp_path):
    """The lived trade: -6.91% realized on a 1.8% stop WITH a 54bps fee
    overrun. The gap loss dwarfs the fee quirk; attribution must say so."""
    eng = _engine(tmp_path)
    t = _thesis(realized_pct=-6.91)
    assert eng._cost_overrun_bps(t) > 15.0     # the fee tail IS an overrun
    assert eng._attribute(t) == "stop_gap"     # ...but ops dominates


def test_normal_stop_fills_keep_their_real_causes(tmp_path):
    eng = _engine(tmp_path)
    # clean stop at -1.9% (slippage within 2x): cost tail attributes
    t = _thesis(realized_pct=-1.9)
    assert eng._attribute(t) == "cost_overrun"
    # gapped-through-but-plausible fill at -2.2% (1.22x): not an ops gap
    t2 = _thesis(realized_pct=-2.2, fees_usd=0.004)
    assert eng._attribute(t2) != "stop_gap"
    # non-stopped losers can never be stop_gap
    t3 = _thesis(realized_pct=-9.0, stopped=False, fees_usd=0.004)
    assert eng._attribute(t3) != "stop_gap"
    # NaN realized (non-material notional) must not blow up or misfire
    t4 = _thesis(realized_pct=float("nan"))
    assert eng._attribute(t4) != "stop_gap"


def test_stop_gap_never_feeds_the_cost_or_whipsaw_governors():
    mon = ModelMonitor({})
    for _ in range(8):
        mon.record_close(0.6, 0, True, cause="stop_gap")
    assert mon.edge_ratio_bump == 0.0, "ops failures must not bump the gate"
    assert mon.stop_widen == 1.0
    # and stop_gap dilution lets a stale cost bump decay (cost_overrun==0)
    mon2 = ModelMonitor({})
    mon2.edge_ratio_bump = 0.2
    mon2.record_close(0.6, 0, True, cause="stop_gap")
    assert mon2.edge_ratio_bump < 0.2


def test_config_guard_rejects_incoherent_stop_gap_factor():
    from core.config_guard import validate
    fatals = [m for s, m in validate(
        {"ml": {"postmortem": {"stop_gap_factor": 1.0}}}) if s == "FATAL"]
    assert any("stop_gap_factor" in m for m in fatals)


# ---------------------------------------------------------------------
# TH-016 review fixes
# ---------------------------------------------------------------------
def _bars(t0, n, spacing=300.0, px=100.0):
    return [{"ts": t0 + spacing * i, "open": px, "close": px,
             "high": px + 0.5, "low": px - 0.5} for i in range(n)]


def test_first_batch_hole_cannot_poison_the_spacing_seed():
    """Review MEDIUM: fresh state + a hole between the first two bars
    seeded the EWMA at hole size (10800s for a 5m feed), leaving the
    fence dead and masking every later genuine hole. The seed now comes
    from the batch median."""
    eng = ThalesEngine({"enabled": True, "influence": "shadow"})
    batch = _bars(1000.0, 2) + _bars(1000.0 + 300 + 10800, 10)
    eng.observe_candles("BTC", batch, 20000.0)
    st = eng._st("BTC")
    assert st.bar_spacing < 600.0, "seed must be batch median, not the hole"
    assert st.bar_hole_count == 1, "the in-batch hole must be fenced"
    assert len(st.candle_hist) == 10          # post-hole bars only
    # a SECOND genuine hole later must still be detected
    eng.observe_candles("BTC", _bars(batch[-1]["ts"] + 10800, 3), 40000.0)
    assert st.bar_hole_count == 2


def test_pre_lapse_sweep_cannot_relatch_from_surviving_candles():
    """Review LOW: _check_lapse cleared last_sweep, but _stop_zones
    re-derived and re-latched the pre-gap sweep bar from candle_hist on
    the next status() call, resurrecting pre-lapse advice."""
    eng = ThalesEngine({"enabled": True, "influence": "shadow",
                        "lapse": {"fast_gap_sec": 600.0}})
    bars = _bars(1000.0, 10)
    bars.append({"ts": 1000.0 + 300 * 10, "open": 100.2, "close": 100.0,
                 "high": 101.5, "low": 100.0})   # sweep bar
    eng.observe_candles("BTC", bars, 4100.0)
    eng.observe_fast("BTC", {"bids": [[99.9, 1]], "asks": [[100.1, 1]]},
                     100.0, 4100.0)
    st = eng._st("BTC")
    eng.status(4100.0)                           # _stop_zones latches here
    assert st.last_sweep.get("dir") == 1
    eng.observe_fast("BTC", {"bids": [[99.9, 1]], "asks": [[100.1, 1]]},
                     100.0, 4800.0)              # 700s gap -> lapse
    assert st.lapse_count == 1 and st.last_sweep == {}
    eng.status(4801.0)                           # re-derives via _scores
    assert st.last_sweep == {}, "pre-lapse sweep must not re-latch"


def test_absurd_candle_ts_self_heals_instead_of_killing_the_fence():
    """Review LOW: a finite ms-vs-s timestamp made last_bar_ts a
    permanent high watermark (max-only update): every later real bar had
    d<0 and genuine holes went undetected forever. Plain assignment
    re-bases; non-finite ts is rejected outright."""
    eng = ThalesEngine({"enabled": True, "influence": "shadow"})
    eng.observe_candles("BTC", _bars(1000.0, 12), 5000.0)
    st = eng._st("BTC")
    bogus = [{"ts": 1.75e12, "open": 100.0, "close": 100.0,
              "high": 100.5, "low": 99.5},
             {"ts": float("inf"), "open": 100.0, "close": 100.0,
              "high": 100.5, "low": 99.5},
             {"ts": float("nan"), "open": 100.0, "close": 100.0,
              "high": 100.5, "low": 99.5}]
    eng.observe_candles("BTC", bogus, 5300.0)
    assert math.isfinite(st.last_bar_ts)
    holes_before = st.bar_hole_count
    nxt = _bars(1000.0 + 300 * 12, 4)            # real bars resume
    eng.observe_candles("BTC", nxt, 6600.0)
    assert st.last_bar_ts == nxt[-1]["ts"], "watermark must re-base down"
    eng.observe_candles("BTC", _bars(nxt[-1]["ts"] + 10800, 3), 30000.0)
    assert st.bar_hole_count > holes_before, "fence must still work after"
