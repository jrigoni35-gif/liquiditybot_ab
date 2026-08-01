"""tests/test_goals_ledger_contamination.py — #123 regression.

ROOT CAUSE: `core/state.py`'s `PortfolioState.__post_init__` seeded
`_last_week_key` / `_last_month_key` from REAL wall-clock
`datetime.now(timezone.utc)` at construction time, instead of leaving
them at their dataclass default ("") and letting the ALREADY-EXISTING
lazy "fresh state: adopt, no phantom row" branch in `maybe_close_week` /
`maybe_close_month` seed them from whatever `now` the caller actually
drives the engine with.

Any replay/smoke/test path that constructs a fresh (`resume=False`)
`PortfolioState`/`LiquidityBot` and then drives it with an injected `now`
that is NOT the real wall-clock instant (true of essentially every
replay - `scripts/replay.py::run_replay` runs `now = meta["start_ts"]`,
the RECORDING's own historical timestamp) mismatched that eager
real-clock seed on the very first `maybe_close_week`/`maybe_close_month`
call. That mismatch takes the "period boundary crossed" branch instead of
the "fresh state, adopt" branch: a phantom closing summary is
synthesized, `main.py`'s `fast_cycle` logs a real `RP_WEEK_CLOSED` /
`RP_MONTH_CLOSED` audit entry, calls `capital.weekly_rollover`, and
appends a row to whatever `system.weekly_ledger_path` /
`monthly_ledger_path` resolves to - the repo's real
`outputs/{weekly,monthly}_ledger.csv` by default. Every contaminating row
shared one signature: cash/savings/reserve pinned at the fresh
`starting_capital` (no time elapsed to trade before the phantom close),
goal ungraded to 0.0/"untracked" (QA configs that never set
`capital_management.*_profit_goal_usd`), and a week/month label of
whatever the REAL calendar day happened to be when the harness ran - not
the replay's own historical date (`self._last_week_key`, the value
`__post_init__` mis-seeded, is exactly what a closing summary reports as
`"week"`/`"month"`).

Same bug CLASS as W2-18 (see tests/test_replay_parity.py): a field seeded
from `time.time()`/`datetime.now()` at construction diverges from the
caller's own injected `now` under replay. Same fix pattern: stop eagerly
seeding from wall-clock time in `__post_init__`; let the pre-existing
lazy first-call adopt do it from whatever `now` is actually used. This
is a pure `core/state.py` fix - no config-seam redirect anywhere is
needed once the phantom close cannot fire in the first place.
"""
from datetime import datetime, timezone
from pathlib import Path

from core.state import PortfolioState
from main import LiquidityBot, load_config
from scripts.smoke_test import MockBinanceUS, MockKraken, MockOKX, qa_redirect_paths

_ROOT = Path(__file__).resolve().parents[1]

# A date guaranteed to sit in a different ISO week/month than "real now"
# for the entire practical lifetime of this test suite.
_HISTORICAL = datetime(2020, 1, 6, 12, 0, tzinfo=timezone.utc).timestamp()


# ---------------------------------------------------------------------------
# 1. root-cause pin: PortfolioState itself, no engine/IO involved
# ---------------------------------------------------------------------------
def test_fresh_state_adopts_first_injected_week_not_a_phantom_close():
    s = PortfolioState(starting_capital=5000.0)
    result = s.maybe_close_week(_HISTORICAL)
    assert result is None, (
        "a freshly constructed PortfolioState must ADOPT the first `now` "
        "it is ever driven with (replay/test determinism), never "
        "synthesize a phantom week-close just because that now's ISO "
        "week differs from the real wall-clock week at construction "
        "time (#123)")
    assert s._last_week_key == "2020-W02"


def test_fresh_state_adopts_first_injected_month_not_a_phantom_close():
    s = PortfolioState(starting_capital=5000.0)
    result = s.maybe_close_month(_HISTORICAL)
    assert result is None, (
        "a freshly constructed PortfolioState must ADOPT the first "
        "injected `now`'s month, never a phantom month-close (#123)")
    assert s._last_month_key == "2020-01"


def test_fresh_state_still_closes_on_a_genuine_later_boundary():
    """The fix must not defeat real boundary detection - only the
    CONSTRUCTION-TIME phantom mismatch goes away."""
    s = PortfolioState(starting_capital=5000.0)
    assert s.maybe_close_week(_HISTORICAL) is None       # adopt
    s.record_realized_pnl(40.0)
    next_week = _HISTORICAL + 7 * 86400.0
    wk = s.maybe_close_week(next_week)
    assert wk is not None and wk["weekly_realized"] == 40.0
    assert wk["week"] == "2020-W02"


# ---------------------------------------------------------------------------
# 2. end-to-end regression pin: the real engine, real ledger-writing code
#    path (main.py fast_cycle -> _append_period_ledger), driven exactly the
#    way scripts/replay.py drives it (resume=False, a historical `now`).
#    The redirect below uses the config seam main.py ALREADY reads
#    (system.weekly_ledger_path/monthly_ledger_path) purely as a safety
#    net for the test itself - the actual fix lives in core/state.py and
#    means no ledger write happens AT ALL, redirected or not.
# ---------------------------------------------------------------------------
def _snapshot(path: Path):
    return path.read_bytes() if path.exists() else None


def test_replay_style_run_with_historical_now_never_touches_real_ledgers(
        tmp_path):
    real_weekly = _ROOT / "outputs" / "weekly_ledger.csv"
    real_monthly = _ROOT / "outputs" / "monthly_ledger.csv"
    real_context_history = _ROOT / "outputs" / "context_history.jsonl"
    before_weekly = _snapshot(real_weekly)
    before_monthly = _snapshot(real_monthly)
    before_context_history = _snapshot(real_context_history)

    cfg = load_config(str(_ROOT / "config.json"))
    cfg["capital_management"]["starting_capital_usd"] = 10_000
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg["context"]["enabled"] = False
    cfg["system"]["state_path"] = str(tmp_path / "state.json")
    cfg["ml"]["model_path"] = str(tmp_path / "none.json")
    cfg["ml"]["history_path"] = str(tmp_path / "hist.csv")
    # postmortem summary: the LAST unredirected outputs/ writer on this
    # path (found 2026-08-01 by conftest's outputs-write guard, which the
    # byte-comparison snapshot below could not see because the rewritten
    # content happened to be identical). A test named "never touches real
    # ledgers" must not itself append to outputs/postmortem_summary.csv -
    # scripts/smoke_test.py's qa_redirect_paths already redirects this key.
    cfg.setdefault("ml", {}).setdefault("postmortem", {})["summary_path"] = \
        str(tmp_path / "postmortem_summary.csv")
    # existing config seam, used here only as a test-side safety net
    redirected_weekly = tmp_path / "weekly_ledger.csv"
    redirected_monthly = tmp_path / "monthly_ledger.csv"
    cfg["system"]["weekly_ledger_path"] = str(redirected_weekly)
    cfg["system"]["monthly_ledger_path"] = str(redirected_monthly)

    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = LiquidityBot(cfg, okx=MockOKX(prices), binanceus=MockBinanceUS(prices),
                       kraken=MockKraken(prices), resume=False)

    t = _HISTORICAL          # a replay-style historical now, per scripts/replay.py
    for _ in range(3):
        bot.cycle_once(t)
        t += bot.poll_sec

    assert _snapshot(real_weekly) == before_weekly, \
        "real outputs/weekly_ledger.csv must stay byte-identical (#123)"
    assert _snapshot(real_monthly) == before_monthly, \
        "real outputs/monthly_ledger.csv must stay byte-identical (#123)"
    # root-cause pin, not just "the redirect worked": with the
    # core/state.py fix, the very first cycle ADOPTS the historical now's
    # week/month instead of synthesizing a phantom close, so even the
    # redirected tmp ledger files must stay unwritten.
    assert not redirected_weekly.exists(), (
        "no phantom week-close should fire on a fresh bot's first "
        "replay-driven cycle (#123 root cause, not just the redirect)")
    assert not redirected_monthly.exists(), (
        "no phantom month-close should fire on a fresh bot's first "
        "replay-driven cycle (#123 root cause, not just the redirect)")
    assert _snapshot(real_context_history) == before_context_history, (
        "real outputs/context_history.jsonl must stay byte-identical/"
        "absent - QA cycles must never poll the live context feed "
        "(whole-phase review: PIT file contamination, same class as #123)")


# ---------------------------------------------------------------------------
# 3. smoke_test.py and replay.py redirect helpers include ledger paths
# ---------------------------------------------------------------------------
def test_qa_redirect_paths_includes_weekly_and_monthly_ledger_paths(tmp_path):
    """qa_redirect_paths() must redirect system.weekly_ledger_path and
    system.monthly_ledger_path into the QA temp dir, not outputs/."""
    cfg = load_config(str(_ROOT / "config.json"))
    # ensure the paths are set (some configs may not have them explicitly)
    if "weekly_ledger_path" not in cfg["system"]:
        cfg["system"]["weekly_ledger_path"] = "outputs/weekly_ledger.csv"
    if "monthly_ledger_path" not in cfg["system"]:
        cfg["system"]["monthly_ledger_path"] = "outputs/monthly_ledger.csv"

    redirected = qa_redirect_paths(cfg, "test_ledger_redirect")
    weekly_path = Path(redirected["system"]["weekly_ledger_path"])
    monthly_path = Path(redirected["system"]["monthly_ledger_path"])

    # both must now point into the QA temp dir, not outputs/
    assert "smoke_out_test_ledger_redirect" in str(weekly_path)
    assert "smoke_out_test_ledger_redirect" in str(monthly_path)
    assert "outputs" not in str(weekly_path)
    assert "outputs" not in str(monthly_path)
