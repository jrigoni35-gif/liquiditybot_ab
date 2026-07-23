"""tests/test_fee_reconciliation.py — W2-9 remainder: periodic REPORT-ONLY
reconciliation of configured Kraken maker/taker bps
(execution/order_manager.OrderManager.check_fee_reconciliation) against the
account's ACTUAL fee tier (data/kraken_feed.KrakenFeed.get_trade_fee_tiers,
private TradeVolume).

Covers: mismatch-beyond-tolerance emits OM-080 once per interval;
within-tolerance is silent; configured-below-actual is flagged regardless of
tolerance magnitude (the dangerous direction); a credential-less feed skips
silently; a malformed TradeVolume response skips silently; the interval is
honored under an INJECTED now (never wall-clock); the withdrawal deny list
is untouched by this work; and the last result is surfaced in status().
"""
import json
import types

from core.audit import get_audit
from core.codes import Code
from data.kraken_feed import FORBIDDEN_PRIVATE_ENDPOINTS
from execution.order_manager import OrderManager


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _feed(tiers=None, has_creds=True, calls=None):
    """Minimal venue stub exposing exactly the surface
    check_fee_reconciliation calls: has_private_credentials() and
    get_trade_fee_tiers(pairs)."""
    calls = calls if calls is not None else []

    def _get_tiers(pairs):
        calls.append(list(pairs))
        return tiers

    return types.SimpleNamespace(
        has_private_credentials=lambda: has_creds,
        get_trade_fee_tiers=_get_tiers), calls


def _om(feed, tolerance_bps=1.0, interval_hours=24.0, enabled=True,
       maker_fee_bps=25.0, taker_fee_bps=40.0, pairs=("ETHUSD",)):
    cfg = {"maker_fee_bps": maker_fee_bps, "taker_fee_bps": taker_fee_bps,
           "fee_recon": {"enabled": enabled, "tolerance_bps": tolerance_bps,
                        "interval_hours": interval_hours}}
    pair_meta = {p: {"price_decimals": 2, "lot_decimals": 8, "ordermin": 0.0}
                for p in pairs}
    return OrderManager(feed=feed, config=cfg, dry_run=True,
                        pair_meta=pair_meta)


def _audit_mark():
    p = get_audit().path
    return p, (p.read_text(encoding="utf-8") if p.exists() else "")


def _audit_new_codes(mark):
    path, before = mark
    after = path.read_text(encoding="utf-8") if path.exists() else ""
    new_lines = after[len(before):].strip().splitlines()
    return [json.loads(line)["code"] for line in new_lines if line.strip()]


# --------------------------------------------------------------------------
# deny-list untouched
# --------------------------------------------------------------------------
def test_deny_list_excludes_trade_volume_and_keeps_withdraw_entries():
    assert "TradeVolume" not in FORBIDDEN_PRIVATE_ENDPOINTS
    for ep in ("Withdraw", "WithdrawInfo", "WithdrawStatus", "WithdrawCancel",
               "WalletTransfer", "WithdrawMethods", "WithdrawAddresses"):
        assert ep in FORBIDDEN_PRIVATE_ENDPOINTS


# --------------------------------------------------------------------------
# mismatch beyond tolerance (safe direction: configured > actual, but by
# more than tolerance_bps) emits OM-080 exactly once per interval
# --------------------------------------------------------------------------
def test_mismatch_beyond_tolerance_emits_once_per_interval():
    tiers = {"ETHUSD": {"maker_bps": 22.0, "taker_bps": 40.0}}  # maker off by 3
    feed, calls = _feed(tiers=tiers)
    om = _om(feed, tolerance_bps=1.0, interval_hours=24.0)

    mark = _audit_mark()
    om.check_fee_reconciliation(now=1_000.0)
    codes = _audit_new_codes(mark)
    assert codes.count(Code.OM_FEE_RECON_MISMATCH.value) == 1
    assert om._fee_recon_result["verdict"] == "mismatch"
    assert om._fee_recon_result["pairs"]["ETHUSD"]["mismatch"] is True

    # a second call still inside the same interval must not re-emit
    mark2 = _audit_mark()
    om.check_fee_reconciliation(now=1_500.0)
    assert Code.OM_FEE_RECON_MISMATCH.value not in _audit_new_codes(mark2)
    assert len(calls) == 1, "the venue call itself is also gated to once/interval"


# --------------------------------------------------------------------------
# within tolerance (and safe direction) is silent
# --------------------------------------------------------------------------
def test_within_tolerance_is_silent():
    # both sides configured slightly ABOVE actual (safe direction), diff
    # 0.5bps < tolerance 1.0bps
    tiers = {"ETHUSD": {"maker_bps": 24.5, "taker_bps": 39.5}}
    feed, _calls = _feed(tiers=tiers)
    om = _om(feed, tolerance_bps=1.0)

    mark = _audit_mark()
    om.check_fee_reconciliation(now=1_000.0)

    assert Code.OM_FEE_RECON_MISMATCH.value not in _audit_new_codes(mark)
    assert om._fee_recon_result["verdict"] == "ok"
    assert om._fee_recon_result["pairs"]["ETHUSD"]["mismatch"] is False


# --------------------------------------------------------------------------
# configured < actual flags regardless of the tolerance magnitude check
# --------------------------------------------------------------------------
def test_configured_below_actual_flagged_even_within_tolerance_magnitude():
    # diff is only 0.05bps (far inside a 1.0bps tolerance), but configured
    # (25) < actual (25.05) - the dangerous, EV-underestimating direction -
    # must still flag.
    tiers = {"ETHUSD": {"maker_bps": 25.05, "taker_bps": 40.0}}
    feed, _calls = _feed(tiers=tiers)
    om = _om(feed, tolerance_bps=1.0)

    mark = _audit_mark()
    om.check_fee_reconciliation(now=1_000.0)

    assert Code.OM_FEE_RECON_MISMATCH.value in _audit_new_codes(mark)
    assert om._fee_recon_result["verdict"] == "mismatch"
    assert om._fee_recon_result["pairs"]["ETHUSD"]["mismatch"] is True


# --------------------------------------------------------------------------
# credential-less environment skips silently
# --------------------------------------------------------------------------
def test_credential_less_environment_skips_silently():
    feed, calls = _feed(tiers={"ETHUSD": {"maker_bps": 22.0,
                                          "taker_bps": 40.0}},
                       has_creds=False)
    om = _om(feed)

    mark = _audit_mark()
    om.check_fee_reconciliation(now=1_000.0)

    assert _audit_new_codes(mark) == []
    assert om._fee_recon_result is None
    assert calls == [], "no credentials -> the venue must never be called"


# --------------------------------------------------------------------------
# a malformed / garbage TradeVolume response skips silently
# --------------------------------------------------------------------------
def test_garbage_response_skips_silently():
    feed, _calls = _feed(tiers=None)     # get_trade_fee_tiers returns None
    om = _om(feed)

    mark = _audit_mark()
    om.check_fee_reconciliation(now=1_000.0)

    assert _audit_new_codes(mark) == []
    assert om._fee_recon_result is None


def test_unexpected_exception_from_feed_never_propagates():
    def _boom(pairs):
        raise RuntimeError("simulated malformed TradeVolume payload")

    feed = types.SimpleNamespace(has_private_credentials=lambda: True,
                                 get_trade_fee_tiers=_boom)
    om = _om(feed)

    mark = _audit_mark()
    om.check_fee_reconciliation(now=1_000.0)   # must not raise

    assert _audit_new_codes(mark) == []
    assert om._fee_recon_result is None


# --------------------------------------------------------------------------
# interval honored under injected now
# --------------------------------------------------------------------------
def test_interval_honored_under_injected_now():
    tiers = {"ETHUSD": {"maker_bps": 25.0, "taker_bps": 40.0}}
    feed, calls = _feed(tiers=tiers)
    om = _om(feed, interval_hours=1.0)   # 3600 sec

    om.check_fee_reconciliation(now=0.0)
    assert len(calls) == 1

    om.check_fee_reconciliation(now=3_599.0)   # still inside the interval
    assert len(calls) == 1, "must not re-query before the interval elapses"

    om.check_fee_reconciliation(now=3_601.0)   # interval elapsed
    assert len(calls) == 2, "must query again once the interval elapses"


def test_disabled_never_calls_the_venue():
    feed, calls = _feed(tiers={"ETHUSD": {"maker_bps": 22.0,
                                          "taker_bps": 40.0}})
    om = _om(feed, enabled=False)

    om.check_fee_reconciliation(now=1_000.0)

    assert calls == []
    assert om._fee_recon_result is None


# --------------------------------------------------------------------------
# stats dict carries the result
# --------------------------------------------------------------------------
def test_status_dict_carries_last_reconciliation_result():
    feed, _calls = _feed(tiers={"ETHUSD": {"maker_bps": 22.0,
                                           "taker_bps": 40.0}})
    om = _om(feed, tolerance_bps=1.0)

    assert om.status()["fee_recon"] is None    # nothing run yet

    om.check_fee_reconciliation(now=1_000.0)
    st = om.status()["fee_recon"]
    assert st["ts"] == 1_000.0
    assert st["verdict"] == "mismatch"
    assert st["pairs"]["ETHUSD"]["maker_configured_bps"] == 25.0
    assert st["pairs"]["ETHUSD"]["maker_actual_bps"] == 22.0


# --------------------------------------------------------------------------
# hourly_cycle isolation: a raising order manager must never starve the
# rest of hourly_cycle's refit work (mirrors _check_equity_truth's own
# isolation, and the explicit CLAUDE.md/brief "never raise into
# hourly_cycle" fail-safe).
# --------------------------------------------------------------------------
def test_hourly_cycle_isolates_a_raising_fee_reconciliation_call():
    import types as _types

    from core.state import PortfolioState
    from main import LiquidityBot
    from ml.monitor import ModelMonitor

    def _noop(*a, **k):
        return None

    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b.config = {"exchanges": {"okx": {"symbols": []},
                             "binanceus": {"symbols": []}}}
    b.symbol_map = {}
    b.daily_candles = {}
    b.corr = _types.SimpleNamespace(
        state=_types.SimpleNamespace(turbulence_pct=0.0),
        update_turbulence=_noop)
    b.macro = _types.SimpleNamespace(update=_noop)
    b.monitor = ModelMonitor({"min_trades_to_judge": 5, "window_trades": 30})
    b.meta = _types.SimpleNamespace(
        reload_if_changed=lambda: False, trained=True, oof_brier=0.2,
        model_id="m", feature_deciles=[])
    retrain_calls = []
    b._maybe_auto_retrain = lambda: retrain_calls.append(1)
    b.state = PortfolioState(starting_capital=10_000.0)

    def _raising_recon(now):
        raise RuntimeError("simulated blow-up")
    b.orders = _types.SimpleNamespace(open_orders=lambda: [],
                                      check_fee_reconciliation=_raising_recon)
    b.history = _types.SimpleNamespace(row_count=lambda: 0)
    b._equity = lambda: 10_000.0

    b.hourly_cycle(now=1000.0)   # must not raise

    # the rest of hourly_cycle still ran (proof the raise was isolated, not
    # just swallowed by an early return that happened to look harmless):
    # _maybe_auto_retrain is called well after the fee-recon call site.
    assert retrain_calls == [1]
