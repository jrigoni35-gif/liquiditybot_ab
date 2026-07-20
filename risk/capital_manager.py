"""
risk/capital_manager.py

Enforces capital allocation rules: position sizing, max concurrent
positions, daily loss limit, savings/reinvestment split on realized
profit, and hard-stop drawdown. Reads config.json's "capital_management"
section.
"""

import logging

log = logging.getLogger("liquiditybot.risk.capital_manager")


class CapitalManager:
    def __init__(self, config: dict):
        # Accepts the full config or the bare capital_management section.
        # main.py historically passed the full config, so every .get()
        # below fell through to its default and config.json's section was
        # silently ignored (harmless only while the values matched).
        config = config.get("capital_management", config)
        self.savings_pct = config.get("savings_pct_of_profit", 20)
        # informational only: the reinvested share is IMPLICITLY
        # (100 - savings_pct) in record_realized_profit — this knob is never
        # read in the split. config_guard FATALs when the two knobs disagree
        # (savings + reinvestment != 100), so the config cannot silently lie
        # about where profit goes. Kept as an attribute for interface
        # stability (invariant #7).
        self.reinvestment_pct = config.get("reinvestment_pct_of_profit", 80)
        self.max_position_size_pct = config.get("max_position_size_pct_of_capital", 10)
        self.max_concurrent_positions = config.get("max_concurrent_positions", 3)
        self.daily_loss_limit_pct = config.get("daily_loss_limit_pct", 5)
        self.hard_stop_drawdown_pct = config.get("hard_stop_drawdown_pct", 15)

    def can_open_new_position(self, state, in_flight_entries: int = 0) -> bool:
        # A pending ENTRY order is committed risk that has not yet landed in
        # open_position_count() (positions are added on FILL, not on submit).
        # Counting only filled positions lets the concurrency cap be blown:
        # entries are limit orders (OM-011) that rest, and with one pending
        # entry allowed per asset the book can accumulate one-per-asset and
        # overfill max_concurrent when they fill. in_flight_entries reserves
        # a slot per resting entry so the cap bounds filled + pending, not
        # filled alone. Default 0 keeps every existing caller behaviour-exact.
        if (state.open_position_count() + max(0, int(in_flight_entries))
                >= self.max_concurrent_positions):
            log.info("Blocked: max concurrent positions reached "
                     "(filled + pending entries).")
            return False

        if state.starting_capital > 0:
            daily_loss_pct = -state.daily_realized_pnl / state.starting_capital * 100
            if daily_loss_pct >= self.daily_loss_limit_pct:
                log.info("Blocked: daily loss limit reached.")
                return False

        if self.hard_stop_triggered(state):
            return False

        return True

    def calculate_position_size(self, state, price: float) -> float:
        """Position size in base asset units, capped at max_position_size_pct_of_capital."""
        if price <= 0:
            return 0.0
        max_capital_for_trade = state.cash_balance * (self.max_position_size_pct / 100)
        return max_capital_for_trade / price

    def record_realized_profit(self, realized_pnl: float, state):
        """
        Applies a closed trade's PnL to portfolio state. On profit, splits
        the gain between savings (locked away) and reinvestment (stays in
        cash_balance, available for future position sizing).
        """
        state.record_realized_pnl(realized_pnl)

        if realized_pnl > 0:
            savings_amount = realized_pnl * (self.savings_pct / 100)
            state.savings_balance += savings_amount
            state.cash_balance -= savings_amount
            log.info(
                f"Realized profit {realized_pnl:.2f}: "
                f"{savings_amount:.2f} -> savings, "
                f"{realized_pnl - savings_amount:.2f} retained for reinvestment."
            )
        else:
            log.info(f"Realized loss {realized_pnl:.2f} recorded.")

    def hard_stop_triggered(self, state, mtm_equity=None) -> bool:
        # MARK-TO-MARKET drawdown when the caller supplies live equity: the
        # catastrophe backstop must see a book underwater on MARKS (stops unable
        # to fill in a gap), not only realized losses. Falls back to realized-
        # only for any caller without marks.
        drawdown = (state.drawdown_mtm_pct(mtm_equity)
                    if mtm_equity is not None else state.drawdown_pct())
        if drawdown >= self.hard_stop_drawdown_pct:
            log.warning(f"Hard stop drawdown triggered: {drawdown:.2f}% >= {self.hard_stop_drawdown_pct}%")
            return True
        return False
