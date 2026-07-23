"""W2-3: reconcile_champion_badge must run on the reload-REJECTION path too.

main.py's hourly reload_if_changed() block only called
monitor.reconcile_champion_badge(...) at __init__/resume (main.py ~826). When
an externally-changed meta_model.json is REJECTED (schema/integrity),
meta.trained flips False but monitor.champion_brier keeps whatever badge it
already had - a future honest challenger then gates against a champion that
isn't actually loaded (the exact ML-076 deadlock, via a call site the
original ML-076 fix never patched). This drives hourly_cycle's reload block
directly (not just reconcile_champion_badge in isolation, which already had
passing unit coverage in test_champion_badge_sync.py) to prove the CALL SITE
is wired, mirroring the __init__ call's arguments in both branches.
"""
import types

from core.state import PortfolioState
from main import LiquidityBot
from ml.monitor import ModelMonitor

PAIR = "XETHZUSD"


def _noop(*a, **k):
    return None


def _bot(meta):
    """Minimal LiquidityBot sufficient to drive hourly_cycle's reload block -
    everything else in hourly_cycle is stubbed to a no-op."""
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b.config = {"exchanges": {"okx": {"symbols": []},
                              "binanceus": {"symbols": []}}}
    b.symbol_map = {}
    b.daily_candles = {}
    b.corr = types.SimpleNamespace(
        state=types.SimpleNamespace(turbulence_pct=0.0), update_turbulence=_noop)
    b.macro = types.SimpleNamespace(update=_noop)
    b.monitor = ModelMonitor({"min_trades_to_judge": 5, "window_trades": 30})
    b.meta = meta
    b._maybe_auto_retrain = _noop
    b.state = PortfolioState(starting_capital=10_000.0)
    b.orders = types.SimpleNamespace(open_orders=lambda: [])
    b.history = types.SimpleNamespace(row_count=lambda: 0)
    b._equity = lambda: 10_000.0
    return b


def _meta(reload_changed, trained, oof_brier, model_id="?"):
    return types.SimpleNamespace(
        reload_if_changed=lambda: reload_changed,
        trained=trained, oof_brier=oof_brier, model_id=model_id,
        feature_deciles=[])


def test_rejected_external_reload_reconciles_the_ghost_badge():
    """meta.trained flips False on a rejected reload; a ghost champion_brier
    better than the no-champion default must be discarded (ML-076 contract:
    reconcile_champion_badge(oof_brier=None, model_loaded=False))."""
    b = _bot(_meta(reload_changed=True, trained=False, oof_brier=None))
    b.monitor.champion_brier = 0.1441        # a good-looking ghost badge

    b.hourly_cycle(now=1000.0)

    assert b.monitor.champion_brier == 0.25, \
        "a rejected external reload must discard the ghost badge to the " \
        "no-champion default, same as the __init__ reconcile call"
    # the governor's level/kelly/records must be untouched by a badge fix
    assert b.monitor.level == 0 and b.monitor.use_model is True


def test_unchanged_reload_is_a_noop_for_the_badge():
    b = _bot(_meta(reload_changed=False, trained=True, oof_brier=0.20))
    b.monitor.champion_brier = 0.1441

    b.hourly_cycle(now=1000.0)

    # reload_if_changed() returned False -> the block never runs at all
    assert b.monitor.champion_brier == 0.1441


def test_accepted_external_reload_still_syncs_via_note_deployed():
    b = _bot(_meta(reload_changed=True, trained=True, oof_brier=0.18))
    b.monitor.champion_brier = 0.1441

    b.hourly_cycle(now=1000.0)

    assert b.monitor.champion_brier == 0.18
    assert b.monitor.level == 0 and b.monitor.use_model is True
