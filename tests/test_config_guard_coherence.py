"""config_guard coherence-check fixes (whole-codebase cleanup batch 1):
1. the give-back arm-vs-break-even check must live where `arm` is bound, so a
   config with position cap > heat cap AND give_back DISABLED no longer
   NameErrors validate() at startup (it did before — `arm` was only bound in
   the give_back.enabled block).
2. the daily-budget vs kill-switch guard must read the REAL kill switch key
   (capital_management.hard_stop_drawdown_pct), not a phantom risk.* key that
   silently defaulted to 15.
"""
from core.config_guard import validate


def _sev(cfg, sev):
    return [m for s, m in validate(cfg) if s == sev]


def test_pos_cap_over_heat_with_giveback_disabled_does_not_crash():
    # pos_cap 50 > heat_cap 35, give_back absent (disabled) -> used to NameError
    cfg = {"system": {"dry_run": True},
           "position_sizer": {"max_position_size_pct_of_capital": 50},
           "risk_protocols": {"heat": {"max_portfolio_heat_frac": 0.35}}}
    assert isinstance(validate(cfg), list)          # must not raise


def test_giveback_arm_inside_be_buffer_warns_when_enabled():
    cfg = {"system": {"dry_run": True},
           "profit_taking": {"be_buffer_bps": 6.0, "est_fee_bps": 0.0,
                             "give_back": {"enabled": True, "giveback_frac": 0.4,
                                           "tight_frac": 0.25,
                                           "arm_gain_pct": 0.02}}}  # 2bps <= 6bps
    assert any("break-even buffer" in m for m in _sev(cfg, "WARN"))


def test_giveback_arm_above_buffer_no_warn():
    cfg = {"system": {"dry_run": True},
           "profit_taking": {"be_buffer_bps": 6.0, "est_fee_bps": 0.0,
                             "give_back": {"enabled": True, "giveback_frac": 0.4,
                                           "tight_frac": 0.25,
                                           "arm_gain_pct": 1.5}}}  # 150bps > 6bps
    assert not any("break-even buffer" in m for m in _sev(cfg, "WARN"))


def test_daily_budget_checked_against_real_kill_switch():
    cfg = {"system": {"dry_run": True},
           "capital_management": {"hard_stop_drawdown_pct": 15,
                                  "daily_loss_limit_pct": 5},
           "risk_protocols": {"budget": {"daily_loss_budget_pct": 20.0,
                                         "weekly_loss_budget_pct": 30.0}}}
    # daily budget 20 >= real hard stop 15 -> FATAL
    assert any("daily_loss_budget_pct must sit below" in m
               for m in _sev(cfg, "FATAL"))
    # raise the REAL kill switch above the budget -> that FATAL clears (proves
    # it reads capital_management.*, not the phantom risk.* default of 15)
    cfg["capital_management"]["hard_stop_drawdown_pct"] = 25
    assert not any("daily_loss_budget_pct must sit below" in m
                   for m in _sev(cfg, "FATAL"))


def test_profit_split_parity_fatals_on_incoherent_knobs():
    """The reinvested share is IMPLICITLY 100-savings; a config where the
    two knobs disagree is lying about where profit goes -> FATAL."""
    cfg = {"system": {"dry_run": True},
           "capital_management": {"savings_pct_of_profit": 20,
                                  "reinvestment_pct_of_profit": 70}}
    assert any("profit split incoherent" in m for m in _sev(cfg, "FATAL"))
    cfg["capital_management"]["reinvestment_pct_of_profit"] = 80
    assert not any("profit split incoherent" in m for m in _sev(cfg, "FATAL"))
    # reinvestment omitted -> defaults to the coherent complement: no fatal
    del cfg["capital_management"]["reinvestment_pct_of_profit"]
    assert not any("profit split incoherent" in m for m in _sev(cfg, "FATAL"))


def test_realize_fastpath_spans_bounds():
    """VOI fastpath: 0 disables; otherwise it must sit in
    [0.25, realize_after_label_spans] — shorter holds than a quarter-span
    teach churn, and a fastpath above the full horizon never fires."""
    def _cfg(rfp):
        return {"system": {"dry_run": True},
                "ml": {"exploration": {"realize_mature_labels": True,
                                       "realize_after_label_spans": 1.0,
                                       "realize_fastpath_spans": rfp}}}
    assert any("realize_fastpath_spans" in m for m in _sev(_cfg(0.1), "FATAL"))
    assert any("realize_fastpath_spans" in m for m in _sev(_cfg(1.5), "FATAL"))
    assert not any("realize_fastpath_spans" in m
                   for m in _sev(_cfg(0.5), "FATAL"))   # deployed value
    assert not any("realize_fastpath_spans" in m
                   for m in _sev(_cfg(0.0), "FATAL"))   # disabled
    # realization off entirely -> the knob is inert, no fatal
    off = _cfg(0.1)
    off["ml"]["exploration"]["realize_mature_labels"] = False
    assert not any("realize_fastpath_spans" in m for m in _sev(off, "FATAL"))
