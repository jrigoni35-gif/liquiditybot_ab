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
