"""Audit batch "config-risk": H10, H15, M6, M9.

H10  position_sizer.max_position_size_pct_of_capital had been DELETED from
     config.json by an unrelated commit (ae4b5314), so the only cap that
     bounds a live entry silently ran at PositionSizer's 10.0 code default
     instead of the operator's deliberate 25 (6e57ebd7). config_guard's
     parity FATAL - which exists to catch exactly that - was defeated by its
     own default: it resolved the sizer copy with the capital_management copy
     as the fallback, so an ABSENT key could never differ from the value it
     was compared against. Both halves must land together or startup breaks.
     long_book.position_sizer was likewise absent and never covered at all.

H15  The live-credential FATAL read the config dict only, so a correctly
     configured env-var-only live start was refused while a config literal
     shadowed by a stale env var passed and then failed every private call.
     config.json is git-tracked, so the guard was pushing operators to commit
     secrets - the exact opposite of docs/SECURITY_AUDIT.md.

M6   strategies.engine had zero validation. main.py dispatches
     InformedFlowEngine on an EXACT match and silently falls through to the
     rev-1 SignalGateEngine otherwise, so a typo swaps the entire entry-signal
     engine (and zero-fills the sg_* learning features) with no error.

M9   The realized-only hard-stop basis excluded reserve_balance while
     record_realized_profit funds the reserve by DEBITING cash, so
     drawdown_pct() == true drawdown + reserve/starting*100. A profitable
     account could walk that phantom into the 15% hard stop and never come
     back: weekly_rollover only drains the reserve on a LOSING week, and a
     hard-stopped book goes flat, so weekly_realized stays 0 forever.
"""
import copy
import json
from pathlib import Path

import pytest

from core.config_guard import KNOWN_SIGNAL_ENGINES, validate
from core.state import PortfolioState
from risk.capital_manager import CapitalManager
from risk.position_sizer import PositionSizer

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"


@pytest.fixture(scope="module")
def shipped():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _no_ambient_kraken_creds(monkeypatch):
    """validate() now resolves credentials through the SAME env-first
    precedence data/kraken_feed.py uses, so every test in this module must
    pin the environment or it would silently depend on the operator's box."""
    for var in ("KRAKEN_API_KEY", "KRAKEN_API_SECRET"):
        monkeypatch.delenv(var, raising=False)


def _sev(cfg, sev):
    return [m for s, m in validate(cfg) if s == sev]


# ---------------------------------------------------------------------------
# H10 - the entry cap and the parity FATAL that is supposed to protect it
# ---------------------------------------------------------------------------

def test_shipped_config_carries_the_sizer_entry_cap(shipped):
    # the deleted key itself: absent, PositionSizer runs at 10.0 and the
    # operator's configured number is enforced nowhere
    assert (shipped["position_sizer"]["max_position_size_pct_of_capital"]
            == shipped["capital_management"]
                      ["max_position_size_pct_of_capital"] == 25)


def test_shipped_sizer_actually_caps_at_the_configured_pct(shipped):
    # end-to-end: the value that reaches the object that clips a live entry
    sizer = PositionSizer(shipped["position_sizer"], shipped["profit_taking"],
                          shipped["risk"], pretrade_cfg=shipped["pretrade"],
                          capital_cfg=shipped["capital_management"])
    assert sizer.max_position_pct == 25.0


def test_missing_sizer_copy_is_fatal_not_silent_parity():
    # THE regression: with the cap_mgmt copy set and the sizer copy absent,
    # the old guard resolved the sizer copy TO the cap_mgmt value and
    # reported clean while the bot capped entries at 10%.
    cfg = {"system": {"dry_run": True},
           "capital_management": {"max_position_size_pct_of_capital": 25}}
    fatals = _sev(cfg, "FATAL")
    assert any("position_sizer.max_position_size_pct_of_capital is MISSING"
               in m for m in fatals)


def test_missing_sizer_copy_on_shipped_config_is_fatal(shipped):
    cfg = copy.deepcopy(shipped)
    del cfg["position_sizer"]["max_position_size_pct_of_capital"]
    assert any("is MISSING" in m for m in _sev(cfg, "FATAL"))


def test_both_copies_absent_is_not_flagged():
    # a bare/partial config expresses no cap at all and the two code defaults
    # (PositionSizer 10.0 / CapitalManager 10) genuinely agree - nothing has
    # drifted, so the sentinel must not false-positive here
    cfg = {"system": {"dry_run": True},
           "capital_management": {"max_concurrent_positions": 5}}
    assert not any("max_position_size_pct_of_capital" in m
                   for m in _sev(cfg, "FATAL"))


def test_mismatch_between_the_two_copies_still_fatal():
    # the pre-existing half of the check must survive the sentinel rewrite
    cfg = {"system": {"dry_run": True},
           "capital_management": {"max_position_size_pct_of_capital": 25},
           "position_sizer": {"max_position_size_pct_of_capital": 10}}
    assert any("max_position_size_pct_of_capital mismatch" in m
               for m in _sev(cfg, "FATAL"))


def test_sizer_copy_out_of_range_is_fatal():
    cfg = {"system": {"dry_run": True},
           "capital_management": {"max_position_size_pct_of_capital": 0},
           "position_sizer": {"max_position_size_pct_of_capital": 0}}
    assert any("position_sizer.max_position_size_pct_of_capital" in m
               and "(0, 100]" in m for m in _sev(cfg, "FATAL"))


def test_shipped_config_has_no_fatal_findings(shipped):
    # config + guard MUST land together: a restored key without the sentinel
    # is pointless, a sentinel without the key refuses to start.
    assert _sev(shipped, "FATAL") == []


# --- H10, second surface: the long book's own (third) sizer copy -----------

def test_long_book_sizer_cap_is_stated_in_shipped_config(shipped):
    # main.py's self.long_sizer is a SECOND PositionSizer; the block used to
    # be absent entirely so it always ran at the 10.0 code default, invisible
    # to the parity check. Lifted at the IDENTICAL default: still 10.0.
    lb = shipped["long_book"]["position_sizer"]
    assert lb["max_position_size_pct_of_capital"] == 10
    sizer = PositionSizer(lb, shipped["long_book"]["profit_taking"],
                          shipped["risk"], pretrade_cfg=shipped["pretrade"],
                          capital_cfg=shipped["capital_management"])
    assert sizer.max_position_pct == 10.0


def test_long_book_sizer_cap_absent_is_advised(shipped):
    cfg = copy.deepcopy(shipped)
    del cfg["long_book"]["position_sizer"]
    assert any("long_book.position_sizer.max_position_size_pct_of_capital"
               in m for m in _sev(cfg, "ADVISORY"))


def test_long_book_sizer_cap_out_of_range_is_fatal(shipped):
    cfg = copy.deepcopy(shipped)
    cfg["long_book"]["position_sizer"]["max_position_size_pct_of_capital"] = 0
    assert any("long_book.position_sizer.max_position_size_pct_of_capital"
               in m and "(0, 100]" in m for m in _sev(cfg, "FATAL"))


# ---------------------------------------------------------------------------
# H15 - credentials resolve env-first; literals in a git-tracked file refused
# ---------------------------------------------------------------------------

def _live(**kraken):
    return {"system": {"dry_run": False},
            "capital_management": {"starting_capital_usd": 5000},
            "exchanges": {"kraken": dict(kraken)}}


def _cred_fatals(cfg):
    return [m for m in _sev(cfg, "FATAL")
            if "api_key and api_secret" in m]


def test_env_supplied_credentials_satisfy_the_live_gate(monkeypatch):
    # the whole point of KrakenFeed._resolve_cred: real keys never have to
    # live in config.json. The old guard FATAL'd this exact (correct) setup.
    monkeypatch.setenv("KRAKEN_API_KEY", "envkey")
    monkeypatch.setenv("KRAKEN_API_SECRET", "ZW52c2VjcmV0")
    assert _cred_fatals(_live(api_key="", api_secret="")) == []


def test_named_env_var_credentials_satisfy_the_live_gate(monkeypatch):
    monkeypatch.setenv("MY_KRAKEN_KEY", "namedkey")
    monkeypatch.setenv("MY_KRAKEN_SECRET", "bmFtZWQ=")
    cfg = _live(api_key="", api_secret="", api_key_env="MY_KRAKEN_KEY",
                api_secret_env="MY_KRAKEN_SECRET")
    assert _cred_fatals(cfg) == []


def test_no_credentials_anywhere_still_fatal_in_live():
    # the guard must not become a no-op: unresolvable creds still refuse live
    assert _cred_fatals(_live(api_key="", api_secret=""))


def test_half_resolved_credentials_still_fatal_in_live(monkeypatch):
    monkeypatch.setenv("KRAKEN_API_KEY", "envkey")      # secret missing
    assert _cred_fatals(_live(api_key="", api_secret=""))


def test_literal_credentials_in_the_tracked_config_are_fatal():
    # REVERSE direction: config.json is git-tracked and ships in the zip, so
    # a literal here is a committed secret. The old guard DEMANDED this.
    fatals = _sev({"system": {"dry_run": True},
                   "exchanges": {"kraken": {"api_key": "PLACEHOLDER",
                                            "api_secret": ""}}}, "FATAL")
    assert any("hold literal value(s)" in m and "api_key" in m
               for m in fatals)


def test_literal_secret_is_fatal_even_when_env_also_set(monkeypatch):
    # env winning at runtime does not un-commit the literal
    monkeypatch.setenv("KRAKEN_API_KEY", "envkey")
    monkeypatch.setenv("KRAKEN_API_SECRET", "ZW52")
    fatals = _sev(_live(api_key="AAAA", api_secret="BBBB"), "FATAL")
    assert any("hold literal value(s)" in m for m in fatals)


def test_shipped_config_ships_no_literal_credentials(shipped):
    kr = shipped["exchanges"]["kraken"]
    assert kr["api_key"] == "" and kr["api_secret"] == ""
    assert not any("hold literal value(s)" in m for m in _sev(shipped, "FATAL"))


# ---------------------------------------------------------------------------
# M6 - strategies.engine
# ---------------------------------------------------------------------------

def test_unknown_engine_name_is_fatal():
    for typo in ("informed-flow", "informedflow", "5gate", "", "five gate"):
        cfg = {"system": {"dry_run": True}, "strategies": {"engine": typo}}
        assert any("is not a known engine" in m for m in _sev(cfg, "FATAL")), \
            f"typo {typo!r} silently swapped the entry-signal engine"


@pytest.mark.parametrize("engine", KNOWN_SIGNAL_ENGINES)
def test_known_engine_names_are_clean(engine):
    cfg = {"system": {"dry_run": True}, "strategies": {"engine": engine}}
    assert not any("strategies.engine" in m for m in _sev(cfg, "FATAL"))


def test_absent_engine_key_is_advised_because_the_code_default_differs():
    # main.py:540 falls back to five_gate while config.json ships
    # informed_flow - deleting the key is a silent rev-1 rollback
    cfg = {"system": {"dry_run": True}}
    assert any("strategies.engine unset" in m and "five_gate" in m
               for m in _sev(cfg, "ADVISORY"))


def test_shipped_engine_is_a_known_engine(shipped):
    assert shipped["strategies"]["engine"] in KNOWN_SIGNAL_ENGINES
    assert not any("strategies.engine" in m for m in _sev(shipped, "FATAL"))


# ---------------------------------------------------------------------------
# M9 - the realized-basis hard stop must count the drawdown reserve
# ---------------------------------------------------------------------------

def _cm(shipped):
    return CapitalManager(shipped["capital_management"])


def _churn_winning_weeks(cm, state, weeks=12, gross_win=1250.0,
                         gross_loss=1187.5):
    """Thin-edge churn: every week nets a small PROFIT, but gross losses are
    ~95% of gross wins, so the reserve (funded from gross wins) grows far
    faster than net equity does."""
    for _ in range(weeks):
        cm.record_realized_profit(gross_win, state)
        cm.record_realized_profit(-gross_loss, state)


def test_twelve_winning_weeks_do_not_lock_out_the_entry_gate(shipped):
    cm = _cm(shipped)
    state = PortfolioState(starting_capital=5000.0)
    _churn_winning_weeks(cm, state)

    # the account is genuinely UP and flat on marks ...
    assert state.total_equity() == pytest.approx(5750.0)
    assert state.drawdown_mtm_pct(state.total_equity()) == pytest.approx(0.0)
    # ... yet the reserve-blind metric reads a full hard-stop drawdown
    assert state.drawdown_pct() == pytest.approx(15.0)
    # the reserve is the entire phantom (identity from the finding)
    assert state.drawdown_pct() - state.reserve_balance / 5000.0 * 100.0 \
        == pytest.approx(cm._realized_drawdown_pct(state))
    # so the gate must stay OPEN
    assert cm.hard_stop_triggered(state) is False
    assert cm.can_open_new_position(state) is True


def test_weekly_rollover_does_not_move_the_hard_stop_basis(shipped):
    # the refill moves money between two pools that both count as capital -
    # it is bookkeeping, so the drawdown it feeds must not budge
    cm = _cm(shipped)
    state = PortfolioState(starting_capital=5000.0)
    _churn_winning_weeks(cm, state, weeks=4)
    before = cm._realized_drawdown_pct(state)
    moved = cm.weekly_rollover(state, {"week": "2026-W30",
                                       "weekly_realized": -200.0})
    assert moved == pytest.approx(200.0)          # reserve -> cash
    assert cm._realized_drawdown_pct(state) == pytest.approx(before)
    # the reserve-blind metric, by contrast, jumps by the refill
    assert state.drawdown_pct() == pytest.approx(
        before + state.reserve_balance / 5000.0 * 100.0)


def test_a_real_realized_drawdown_still_halts(shipped):
    # fail-safe direction preserved: the fix must not blind the hard stop
    cm = _cm(shipped)
    state = PortfolioState(starting_capital=5000.0)
    cm.record_realized_profit(-800.0, state)      # -16% realized, no reserve
    assert state.reserve_balance == 0.0
    assert cm._realized_drawdown_pct(state) == pytest.approx(16.0)
    assert cm.hard_stop_triggered(state) is True
    assert cm.can_open_new_position(state) is False


def test_reserve_free_state_is_bit_identical(shipped):
    # no reserve pool -> the correction term is exactly zero, so every
    # pre-existing caller keeps its old number
    cm = _cm(shipped)
    state = PortfolioState(starting_capital=5000.0)
    for pnl in (-100.0, -250.0, -50.0):
        state.record_realized_pnl(pnl)            # bypass the profit split
    assert state.reserve_balance == 0.0
    assert cm._realized_drawdown_pct(state) == pytest.approx(
        state.drawdown_pct())


def test_mtm_path_is_untouched(shipped):
    # main.py:2209 passes MTM equity; that branch must not change at all
    cm = _cm(shipped)
    state = PortfolioState(starting_capital=5000.0)
    state.note_equity(5000.0)
    assert cm.hard_stop_triggered(state, 4000.0) is True    # -20% on marks
    assert cm.hard_stop_triggered(state, 4900.0) is False   # -2% on marks
