"""Dry-run active-learning exploration: with no proven edge the sizer's
net-Kelly bar (p_win > ~0.60) vetoes every confirmed signal, so the bot never
trades and never gathers live labels. Exploration takes a fraction of confirmed
signals as small paper trades to bootstrap real-fill data.

HARD INVARIANT under test: exploration is dry_run ONLY - it must never fire in
live mode, whatever the config. Also: epsilon-gated, and auto-off once enough
training rows exist.
"""
import types

from main import LiquidityBot


def _stub_bot(dry_run, enabled=True, epsilon=1.0, until=120, rows=0,
              live=None):
    """A LiquidityBot shell with only the fields _exploration_active reads -
    avoids constructing the full engine graph / hitting the network. When
    `live` is given the stub exposes source_counts() (real HistoryStore
    does), so graduation is tested on the LIVE split; otherwise only
    row_count() exists and the code falls back to total rows."""
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = dry_run
    b.explore_enabled = enabled
    b.explore_epsilon = epsilon
    b.explore_until_rows = until
    b.explore_max_asset_share = 1.0            # variety taper off for these
    b._explore_rng = __import__("random").Random(1)
    hist = types.SimpleNamespace(row_count=lambda: rows)
    if live is not None:
        hist.source_counts = lambda: {"live": live, "candidate": rows - live}
    setattr(b, "history", hist)
    return b


def test_exploration_never_fires_in_live_mode():
    b = _stub_bot(dry_run=False, enabled=True, epsilon=1.0)   # epsilon=1 = always
    assert b._exploration_active(0.0) is False                # but live -> never


def test_exploration_fires_in_dry_run_when_enabled():
    b = _stub_bot(dry_run=True, enabled=True, epsilon=1.0)
    assert b._exploration_active(0.0) is True


def test_exploration_off_when_disabled():
    b = _stub_bot(dry_run=True, enabled=False, epsilon=1.0)
    assert b._exploration_active(0.0) is False


def test_exploration_auto_disables_once_enough_rows():
    b = _stub_bot(dry_run=True, enabled=True, epsilon=1.0, until=120, rows=120)
    assert b._exploration_active(0.0) is False                # data acquired
    b2 = _stub_bot(dry_run=True, enabled=True, epsilon=1.0, until=120, rows=119)
    assert b2._exploration_active(0.0) is True


def test_graduation_counts_LIVE_rows_not_proxy_inflated_total():
    # 2026-07-18: exploration retired at 1370 TOTAL rows while only 35 were
    # real closed trades (the rest triple-barrier candidate proxies),
    # silently starving the model of live-outcome data. Graduation must
    # count the LIVE split so a proxy-heavy corpus keeps exploring.
    b = _stub_bot(dry_run=True, enabled=True, epsilon=1.0, until=500,
                  rows=1370, live=35)
    assert b._exploration_active(0.0) is True     # 35 live < 500 -> keep learning
    # once REAL closed trades clear the bar, it graduates
    b2 = _stub_bot(dry_run=True, enabled=True, epsilon=1.0, until=500,
                   rows=2000, live=500)
    assert b2._exploration_active(0.0) is False
    # no source split available -> falls back to total (legacy behavior)
    b3 = _stub_bot(dry_run=True, enabled=True, epsilon=1.0, until=500,
                   rows=600)                       # live=None
    assert b3._exploration_active(0.0) is False


def test_epsilon_zero_never_fires():
    b = _stub_bot(dry_run=True, enabled=True, epsilon=0.0)
    assert not any(b._exploration_active(0.0) for _ in range(50))


def test_epsilon_is_a_fraction_not_always():
    b = _stub_bot(dry_run=True, enabled=True, epsilon=0.25)
    fires = sum(b._exploration_active(0.0) for _ in range(2000))
    assert 350 < fires < 650          # ~25% (seeded, deterministic band)


def test_sizer_veto_on_exploration_entry_logs_at_info(caplog):
    """An exploration entry exists ONLY to generate a training label; a
    sizer veto there is a learning outage and must be visible at INFO
    (a DEBUG-only veto once hid 45h of total entry starvation)."""
    import logging
    b = LiquidityBot.__new__(LiquidityBot)
    with caplog.at_level(logging.DEBUG, logger="liquiditybot.main"):
        b._log_sizer_veto("ETH", ["SZ-031: a multiplier zeroed the trade "
                                  "(liq=spoofy)"], explored=True)
    recs = [r for r in caplog.records if "sizer veto" in r.getMessage()]
    assert recs and recs[-1].levelno == logging.INFO
    assert "SZ-031" in recs[-1].getMessage()


def test_sizer_veto_on_ordinary_entry_stays_debug(caplog):
    import logging
    b = LiquidityBot.__new__(LiquidityBot)
    with caplog.at_level(logging.DEBUG, logger="liquiditybot.main"):
        b._log_sizer_veto("BTC", ["SZ-042: $12 below minimum"],
                          explored=False)
    recs = [r for r in caplog.records if "sizer veto" in r.getMessage()]
    assert recs and recs[-1].levelno == logging.DEBUG
