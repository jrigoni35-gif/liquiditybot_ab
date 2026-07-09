"""
core/state.py

In-memory portfolio state: capital, open positions, realized/unrealized PnL.
This is the single source of truth that other modules (executor, profit_tiers,
capital_manager) read from and update.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict


@dataclass
class Position:
    position_id: str
    symbol: str
    direction: str  # "long" or "short"
    entry_price: float
    size: float               # current open size (units of base asset)
    original_size: float      # size at time of entry, for tier % calculations
    opened_at: datetime
    tier_closed: int = 0      # how many profit tiers have already fired (0-4)
    trailing_stop_price: Optional[float] = None
    # --- v2 fields (defaults keep v1 call sites working) ---
    is_hedge: bool = False            # hedge positions: no tiers, no stale purge
    stop_price: Optional[float] = None  # hard protective stop (vol/regime scaled)
    confidence: float = 0.0           # meta-model p(win) at entry
    edge_bps: float = 0.0             # pre-trade estimated edge at entry
    fees_paid_usd: float = 0.0        # cumulative fees attributed to this position
    leverage: float = 1.0             # leverage used at entry (1 = spot)
    high_water: Optional[float] = None  # best favorable price since entry (chandelier anchor)

    def unrealized_pnl_pct(self, current_price: float) -> float:
        if self.entry_price == 0:
            return 0.0
        if self.direction == "long":
            return (current_price - self.entry_price) / self.entry_price * 100
        else:
            return (self.entry_price - current_price) / self.entry_price * 100


@dataclass
class PortfolioState:
    starting_capital: float
    cash_balance: float = field(init=False)
    savings_balance: float = 0.0
    realized_pnl_total: float = 0.0
    daily_realized_pnl: float = 0.0
    fees_paid_total: float = 0.0
    _positions: dict = field(default_factory=dict)
    _last_pnl_reset_date: str = field(default="", init=False)

    def __post_init__(self):
        self.cash_balance = self.starting_capital
        self._last_pnl_reset_date = datetime.now(timezone.utc).date().isoformat()

    # --- Position management -------------------------------------------------
    def add_position(self, position: Position):
        self._positions[position.position_id] = position

    def remove_position(self, position_id: str):
        self._positions.pop(position_id, None)

    def get_position(self, position_id: str) -> Optional[Position]:
        return self._positions.get(position_id)

    def open_positions(self) -> list:
        return list(self._positions.values())

    def open_position_count(self) -> int:
        return len(self._positions)

    # --- Exposure helpers (v2) --------------------------------------------------
    def gross_exposure_usd(self, mark_prices: Optional[Dict[str, float]] = None) -> float:
        total = 0.0
        for pos in self._positions.values():
            px = (mark_prices or {}).get(pos.symbol) or pos.entry_price
            total += pos.size * px
        return total

    def net_delta_usd(self, mark_prices: Optional[Dict[str, float]] = None) -> float:
        total = 0.0
        for pos in self._positions.values():
            px = (mark_prices or {}).get(pos.symbol) or pos.entry_price
            sgn = 1.0 if pos.direction == "long" else -1.0
            total += sgn * pos.size * px
        return total

    def record_fees(self, amount: float):
        self.fees_paid_total += amount

    # --- Capital tracking ------------------------------------------------------
    def total_equity(self, mark_prices: Optional[Dict[str, float]] = None) -> float:
        """Cash + savings + unrealized PnL of open positions (if mark_prices).

        Cash is PnL-settled: it is NOT debited when a position opens (only
        realized PnL is booked to it on close). So equity is cash + savings +
        the marked-to-market *gain/loss* of each open position, NOT + its full
        notional (size*price) - that would double-count the capital, inflating
        equity by the cost basis of open inventory and, through the equity-scaled
        sizer/caps/watchdog, loosening every risk control the more you hold.
        Sign-correct for shorts. Matches scripts/quant_trials.py mark-to-market.
        """
        equity = self.cash_balance + self.savings_balance
        if mark_prices:
            for pos in self._positions.values():
                price = mark_prices.get(pos.symbol)
                if price:
                    sgn = 1.0 if pos.direction == "long" else -1.0
                    equity += sgn * (price - pos.entry_price) * pos.size
        return equity

    def record_realized_pnl(self, amount: float):
        self.realized_pnl_total += amount
        self.daily_realized_pnl += amount
        self.cash_balance += amount

    def reset_daily_pnl(self):
        self.daily_realized_pnl = 0.0

    def maybe_reset_daily_pnl(self):
        """Call once per cycle. Resets daily_realized_pnl automatically at UTC day boundary."""
        today = datetime.now(timezone.utc).date().isoformat()
        if today != self._last_pnl_reset_date:
            self.reset_daily_pnl()
            self._last_pnl_reset_date = today

    def drawdown_pct(self) -> float:
        """Drawdown from starting capital, based on cash + savings only."""
        current = self.cash_balance + self.savings_balance
        if self.starting_capital == 0:
            return 0.0
        return (self.starting_capital - current) / self.starting_capital * 100
