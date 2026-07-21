"""Weekly profit pools + rollover (the resurfaced equity-management plan).

Three pools on every realized win: savings (locked, untouchable), reserve
(drawdown shock absorber), reinvestment (compounds sizing). At each ISO-week
boundary (RP-070, restart-safe): a LOSING week refills its realized loss
from reserve into trading cash BEFORE the working baseline can shrink; the
week's signed record lands in the audit chain and outputs/weekly_ledger.csv.
Reserve only ever moves INTO cash; savings never moves at all.
"""
from datetime import datetime, timezone

from core.config_guard import validate
from core.state import PortfolioState
from risk.capital_manager import CapitalManager

MON = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc).timestamp()
NEXT_MON = datetime(2026, 7, 27, 0, 5, tzinfo=timezone.utc).timestamp()


def _cm(sav=20, resv=10):
    return CapitalManager({"savings_pct_of_profit": sav,
                           "reserve_pct_of_profit": resv,
                           "max_concurrent_positions": 5,
                           "hard_stop_drawdown_pct": 15})


def _state():
    s = PortfolioState(starting_capital=5000.0)
    s.maybe_close_week(MON)          # adopt the current week key
    return s


# --- three-way split ---------------------------------------------------------
def test_profit_splits_three_ways():
    s, cm = _state(), _cm()
    cm.record_realized_profit(100.0, s)
    assert abs(s.savings_balance - 20.0) < 1e-9
    assert abs(s.reserve_balance - 10.0) < 1e-9
    # cash gained the reinvestment share only: +100 pnl, -30 skimmed
    assert abs(s.cash_balance - 5070.0) < 1e-9
    # equity conserves the full gain across all pools
    assert abs(s.total_equity({}) - 5100.0) < 1e-9


def test_losses_touch_no_pool():
    s, cm = _state(), _cm()
    cm.record_realized_profit(-50.0, s)
    assert s.savings_balance == 0.0 and s.reserve_balance == 0.0
    assert abs(s.cash_balance - 4950.0) < 1e-9


def test_reserve_zero_is_legacy_two_pool():
    s, cm = _state(), _cm(resv=0)
    cm.record_realized_profit(100.0, s)
    assert s.reserve_balance == 0.0
    assert abs(s.savings_balance - 20.0) < 1e-9


# --- weekly close + rollover -------------------------------------------------
def test_week_closes_once_and_resets_weekly_pnl():
    s = _state()
    s.record_realized_pnl(40.0)
    assert s.maybe_close_week(MON) is None          # mid-week: nothing
    wk = s.maybe_close_week(NEXT_MON)
    assert wk is not None and wk["weekly_realized"] == 40.0
    assert s.weekly_realized_pnl == 0.0             # new week starts clean
    assert s.maybe_close_week(NEXT_MON) is None     # once per boundary


def test_fresh_state_adopts_without_phantom_week():
    s = PortfolioState(starting_capital=5000.0)
    s._last_week_key = ""                            # pre-upgrade snapshot
    assert s.maybe_close_week(MON) is None           # adopt, no week-0 row
    assert s._last_week_key


def test_losing_week_refills_from_reserve():
    s, cm = _state(), _cm()
    s.reserve_balance = 25.0
    s.record_realized_pnl(-40.0)                     # a bad week
    wk = s.maybe_close_week(NEXT_MON)
    cash_before = s.cash_balance
    refill = cm.weekly_rollover(s, wk)
    assert refill == 25.0                            # capped at the reserve
    assert s.reserve_balance == 0.0
    assert abs(s.cash_balance - (cash_before + 25.0)) < 1e-9


def test_winning_week_rolls_untouched():
    s, cm = _state(), _cm()
    s.reserve_balance = 25.0
    s.record_realized_pnl(60.0)
    wk = s.maybe_close_week(NEXT_MON)
    assert cm.weekly_rollover(s, wk) == 0.0
    assert s.reserve_balance == 25.0                 # reserve keeps growing


def test_refill_covers_partial_loss():
    s, cm = _state(), _cm()
    s.reserve_balance = 100.0
    s.record_realized_pnl(-30.0)
    wk = s.maybe_close_week(NEXT_MON)
    assert cm.weekly_rollover(s, wk) == 30.0         # only the loss, not all
    assert s.reserve_balance == 70.0


# --- guard: three-way parity -------------------------------------------------
def _sev(cfg, sev):
    return [m for s, m in validate(cfg) if s == sev]


def test_three_pool_parity_guard():
    def _cfg(sav, resv, reinv):
        return {"system": {"dry_run": True},
                "capital_management": {"savings_pct_of_profit": sav,
                                       "reserve_pct_of_profit": resv,
                                       "reinvestment_pct_of_profit": reinv}}
    assert not any("profit split" in m for m in _sev(_cfg(20, 10, 70), "FATAL"))
    assert any("profit split" in m for m in _sev(_cfg(20, 10, 75), "FATAL"))
    assert any("reserve_pct_of_profit" in m
               for m in _sev(_cfg(20, 60, 20), "FATAL"))   # >50 starves


# --- persistence + ledger + surfaces ----------------------------------------
def test_pools_survive_snapshot_roundtrip():
    s = _state()
    s.reserve_balance, s.weekly_realized_pnl = 12.5, -3.0
    # round-trip through the snapshot dict shape used by StateStore
    d = {"reserve_balance": s.reserve_balance,
         "weekly_realized_pnl": s.weekly_realized_pnl,
         "last_week_key": s._last_week_key}
    s2 = PortfolioState(starting_capital=5000.0)
    s2.reserve_balance = float(d.get("reserve_balance", 0.0))
    s2.weekly_realized_pnl = float(d.get("weekly_realized_pnl", 0.0))
    if d.get("last_week_key"):
        s2._last_week_key = str(d["last_week_key"])
    assert s2.reserve_balance == 12.5 and s2._last_week_key == s._last_week_key
    # and the real persistence module serializes all three keys
    from pathlib import Path as _P
    psrc = (_P(__file__).resolve().parents[1] / "core" /
            "persistence.py").read_text(encoding="utf-8")
    for key in ("reserve_balance", "weekly_realized_pnl", "last_week_key"):
        assert psrc.count(key) >= 2, f"{key} must be saved AND restored"


def test_weekly_ledger_appends_with_header(tmp_path):
    from main import _append_period_ledger
    cols = ["week", "weekly_realized", "reserve_refill", "cash",
            "savings", "reserve", "realized_total"]
    p = tmp_path / "ledger.csv"
    row = {"week": "2026-W29", "weekly_realized": -12.0,
           "reserve_refill": 12.0, "cash": 4988.0, "savings": 20.0,
           "reserve": 8.0, "realized_total": -4.0}
    _append_period_ledger(p, row, cols)
    _append_period_ledger(p, dict(row, week="2026-W30"), cols)
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("week,weekly_realized,reserve_refill")
    assert len(lines) == 3 and "2026-W30" in lines[2]


def test_surfaces_carry_the_pools():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    runner = (root / "runner.py").read_text(encoding="utf-8")
    assert '"reserve"' in runner and '"weekly_pnl"' in runner
    pusher = (root / "scripts" / "gc_pusher.py").read_text(encoding="utf-8")
    assert '"weekly_pnl"' in pusher and '"savings"' in pusher
    assert '"reserve"' in pusher
    reset = (root / "scripts" /
             "reset_paper_capital.py").read_text(encoding="utf-8")
    assert "reserve_balance" in reset and "weekly_realized_pnl" in reset
    # the engine wires close -> rollover -> audit -> ledger
    eng = (root / "main.py").read_text(encoding="utf-8")
    assert "maybe_close_week(now)" in eng
    assert "Code.RP_WEEK_CLOSED" in eng
    assert "_append_period_ledger(" in eng
