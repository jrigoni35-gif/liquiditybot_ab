"""Whole-codebase cleanup batch 1 — behavior-preserving correctness fixes.

Covers the postmortem zero-notional guard (the div-by-zero the audit found on
a defensively-floored trade). config_guard, gc_pusher, rest_server and the
launcher fixes are pinned in their own suites.
"""
import pytest

from main import LiquidityBot
from ml.postmortem import PostmortemEngine, TradeThesis


def test_symbol_base_disambiguates_eth_from_ethfi():
    b = LiquidityBot._symbol_base
    assert b("ETH-USDT") == "ETH" and b("ETH/USDT") == "ETH"
    assert b("ETHUSDT") == "ETH" and b("BTCUSD") == "BTC"
    # the bug: startswith('ETH') matched these; base-parse must not collapse them
    assert b("ETHFI-USDT") == "ETHFI"
    assert b("ETHFIUSDT") == "ETHFI"


def _thesis(entry_usd, fees_usd=5.0):
    return TradeThesis(
        position_id="p", asset="BTC", symbol="BTC/USD", direction="long",
        entry_ts=0.0, p_win=0.6, expected_ret_pct=0.1, expected_cost_bps=40.0,
        stop_pct=1.0, target_pct=2.0, entry_regime="calm", entry_liq="normal",
        narrative_label="test", fair_value=100.0, quote_price=100.0,
        model_scored=True, fill_price=100.0, fees_usd=fees_usd,
        entry_usd=entry_usd)


def _engine(tmp_path):
    return PostmortemEngine({"paths_path": str(tmp_path / "trade_paths.csv"),
                             "report_dir": str(tmp_path / "pm"),
                             "summary_path": str(tmp_path / "pm_summary.csv")})


def test_cost_overrun_zero_notional_no_zerodiv(tmp_path):
    # defensively-floored zero-notional trade: must not ZeroDivisionError
    t = _thesis(entry_usd=0.0, fees_usd=5.0)
    assert _engine(tmp_path)._cost_overrun_bps(t) == 0.0


def test_cost_overrun_positive_notional_still_computes(tmp_path):
    # 5/1000*1e4 = 50 bps fees, 0 slip, minus 40 expected = +10 bps overrun
    t = _thesis(entry_usd=1000.0, fees_usd=5.0)
    assert _engine(tmp_path)._cost_overrun_bps(t) == pytest.approx(10.0)
