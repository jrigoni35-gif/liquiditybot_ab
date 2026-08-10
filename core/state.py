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
    entry_fees_usd: float = 0.0       # entry-leg fees only (pro-rated into exit nets)
    leverage: float = 1.0             # leverage used at entry (1 = spot)
    high_water: Optional[float] = None  # best favorable price since entry (chandelier anchor)
    is_probe: bool = False            # PT-050 exploration probe (EV gate bypassed to buy a
                                      # label) - OF-5 grades conviction trades separately
    # P1 (2026-07-23 P&L diagnosis): the pretrade gate's estimated round-trip
    # cost (maker entry leg + exit leg + spread, execution/pretrade.py's
    # PreTradeDecision.est_cost_bps) at the moment this position was opened.
    # Threaded onto the Position so risk/profit_tiers.py can floor tier-1's
    # trigger at a guarded multiple of the entry's OWN cost stack. Default 0.0
    # -> the floor is exactly inert for legacy/restored positions that predate
    # this field.
    est_cost_bps: float = 0.0
    # Compounder Phase C: which strategy book opened this position - "5m"
    # (the existing scalping flow) or "long" (the long-horizon accumulation
    # book, risk/long_book.py). Default keeps every pre-C construction site
    # (and every restored legacy snapshot) exactly "5m" - zero 5m
    # contamination by construction.
    book: str = "5m"
    # geometry-alignment T5 (spec D1, docs/superpowers/specs/
    # 2026-07-27-geometry-alignment-design.md): "the traded bet is the
    # labeled bet". A model-lane entry (conviction AND probe alike) taken
    # under bracket_exits.enabled carries the triple-barrier bracket
    # (ml/labeling.py's barrier_geometry() - the SAME helper the candidate
    # labeler calls) computed at fill time from this entry's own sigma_bar
    # and the pretrade decision's own cost estimate. bracket_pt_frac/
    # bracket_sl_frac are FRACTIONS of entry_price (0.02 = 2%, matching
    # ml/history.py's persisted pt_frac/sl_frac columns); the exit-
    # evaluation seam (main._manage_open_position) reads
    # bracket_pt_frac > 0 as "this position's exits are the bracket, not
    # the tier engine". bracket_deadline_ts is the epoch second the
    # vertical (time) barrier closes the remainder (entry_ts +
    # ml.label_max_bars bars). Defaults 0.0 are LEGACY-INERT: any
    # pre-T5 construction site, any restored snapshot, and every position
    # opened while bracket_exits.enabled=false never sets these, so the
    # bracket branch is unreachable for them and behavior is byte-
    # identical to before this task (the long book, book=="long", never
    # sets these either - brackets are a 5m/model-lane concept only).
    bracket_pt_frac: float = 0.0
    bracket_sl_frac: float = 0.0
    bracket_deadline_ts: float = 0.0

    def unrealized_pnl_pct(self, current_price: float) -> float:
        """Unrealized PnL in PERCENT of entry price, sign-correct for
        shorts (positive = in profit); 0.0 on a zero entry price."""
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
    # drawdown RESERVE: profit slice that refills trading cash after a
    # losing week, so a bad week borrows from past wins before it can
    # shrink the working baseline. Savings stays untouchable; reserve
    # is the shock absorber between trading and savings.
    reserve_balance: float = 0.0
    realized_pnl_total: float = 0.0
    daily_realized_pnl: float = 0.0
    weekly_realized_pnl: float = 0.0
    monthly_realized_pnl: float = 0.0
    fees_paid_total: float = 0.0
    # Opening-leg (entry + hedge) fees, accumulated separately because
    # record_entry_fee debits them STRAIGHT TO CASH and they are therefore
    # netted into NO P&L figure - not realized_pnl_total, not the daily/
    # weekly/monthly counters. Found 2026-08-09 when the operator noticed
    # all-time P&L disagreeing with equity: the invisible population was
    # $185.94 of $382.59 lifetime fees (49%), so the bot reported -$208.31
    # against a true all-time change of -$383.26. Closing-leg fees are
    # already netted inside realized_pnl_total by record_realized_pnl, so
    # this is exactly the missing half of the cost stack.
    # BOOKKEEPING ONLY - no decision path reads it; it exists so
    # net_pnl_all_time / realized_net_all_in can be reported honestly.
    entry_fees_total: float = 0.0
    # Goal-ladder multiplier (2026-08-11 stressor regime, operator-adjudicated):
    # the effective MONTHLY profit goal is config's monthly_profit_goal_usd x
    # this. Ratchets x1.5 on each month that CLOSES at >=100% attainment
    # (RP-072), never de-escalates, resets to 1.0 only with a capital reset.
    # Grading/telemetry only - no trading decision reads it.
    goal_ladder_mult: float = 1.0
    _positions: dict = field(default_factory=dict)
    _last_pnl_reset_date: str = field(default="", init=False)
    _last_week_key: str = field(default="", init=False)
    _last_month_key: str = field(default="", init=False)

    def __post_init__(self):
        self.cash_balance = self.starting_capital
        self._last_pnl_reset_date = datetime.now(timezone.utc).date().isoformat()
        # _last_week_key / _last_month_key deliberately stay at their "" default
        # here (#123, same bug class as W2-18 / tests/test_replay_parity.py):
        # eagerly seeding them from datetime.now(timezone.utc) at construction
        # diverges from whatever `now` the caller actually drives the engine
        # with under replay/test (a historical or injected time), so the FIRST
        # maybe_close_week/maybe_close_month call took the "boundary crossed"
        # branch instead of "fresh state: adopt" - a phantom week/month close,
        # a real RP_WEEK_CLOSED/RP_MONTH_CLOSED audit entry, a real
        # capital.weekly_rollover call, and a synthetic row appended to the
        # repo's real outputs/{weekly,monthly}_ledger.csv. Leaving these at ""
        # lets the pre-existing lazy adopt in maybe_close_week/maybe_close_month
        # seed them from the caller's OWN first `now` - live and replay alike -
        # with zero live-runner behavior change (a live boot's construction and
        # its first fast_cycle(now) both happen at essentially the same real
        # wall-clock instant either way).
        # peak mark-to-market equity, for a TRUE (unrealized-aware, peak-based)
        # drawdown backstop — realized-only drawdown_pct is blind to a book that
        # is deep underwater on marks but not yet closed.
        self._equity_high_water = self.starting_capital

    # --- Position management -------------------------------------------------
    def add_position(self, position: Position):
        """Register an open Position, keyed by position_id (upsert)."""
        self._positions[position.position_id] = position

    def remove_position(self, position_id: str):
        """Drop a position from the book (no-op when the id is unknown)."""
        self._positions.pop(position_id, None)

    def get_position(self, position_id: str) -> Optional[Position]:
        """The open Position for this id, or None."""
        return self._positions.get(position_id)

    def open_positions(self) -> list:
        """Snapshot list of all open Position objects (hedges included)."""
        return list(self._positions.values())

    def open_position_count(self) -> int:
        """Number of open positions (hedges included)."""
        return len(self._positions)

    # --- Exposure helpers (v2) --------------------------------------------------
    def gross_exposure_usd(self, mark_prices: Optional[Dict[str, float]] = None) -> float:
        """Sum of size*mark in USD across open positions, direction-blind
        (longs and shorts both add); entry price when no mark is given."""
        total = 0.0
        for pos in self._positions.values():
            px = (mark_prices or {}).get(pos.symbol) or pos.entry_price
            total += pos.size * px
        return total

    def net_delta_usd(self, mark_prices: Optional[Dict[str, float]] = None) -> float:
        """Signed net exposure in USD (long positive, short negative);
        entry price when no mark is given."""
        total = 0.0
        for pos in self._positions.values():
            px = (mark_prices or {}).get(pos.symbol) or pos.entry_price
            sgn = 1.0 if pos.direction == "long" else -1.0
            total += sgn * pos.size * px
        return total

    def record_fees(self, amount: float):
        """Accumulate venue fees (USD) into the running lifetime total."""
        self.fees_paid_total += amount

    def record_entry_fee(self, amount: float):
        """Entry-leg fees are REAL CASH out the door at fill time. Cash is
        PnL-settled (no debit at open for the position itself), but without
        this debit every round trip overstated equity by the entry fee leg —
        the sizer priced 65bps RT while the ledger charged only the exit leg
        (audit MP-2 2026-07-17). Exit fees stay netted inside realized PnL.

        The accumulator (2026-08-09) is what makes the debit REPORTABLE:
        cash felt it immediately, but no P&L line ever showed it, so
        `realized_pnl_total` understated the true all-time loss by this
        entire population. See entry_fees_total's field comment."""
        self.cash_balance -= amount
        self.entry_fees_total += amount

    def net_pnl_all_time(self,
                         mark_prices: Optional[Dict[str, float]] = None
                         ) -> float:
        """TRUE all-time net P&L: every fee, realized and unrealized.

        Defined as the equity identity rather than as a sum of counters,
        so it cannot drift from the money: total_equity already carries
        cash (which absorbed the opening fees), the pools, and open
        marks. Any future cash path that bypasses a counter shows up here
        automatically - the counters are the thing that can lie, equity
        is not."""
        return self.total_equity(mark_prices) - self.starting_capital

    def realized_net_all_in(self) -> float:
        """Realized P&L net of BOTH fee legs - the closing legs already
        netted inside realized_pnl_total, plus the opening legs that only
        ever hit cash. Excludes open positions (that is what
        net_pnl_all_time is for)."""
        return self.realized_pnl_total - self.entry_fees_total

    # --- Capital tracking ------------------------------------------------------
    def total_equity(self, mark_prices: Optional[Dict[str, float]] = None) -> float:
        """Cash + savings + RESERVE + unrealized PnL of open positions.

        Cash is PnL-settled: it is NOT debited when a position opens (only
        realized PnL is booked to it on close). So equity is cash + savings +
        the marked-to-market *gain/loss* of each open position, NOT + its full
        notional (size*price) - that would double-count the capital, inflating
        equity by the cost basis of open inventory and, through the equity-scaled
        sizer/caps/watchdog, loosening every risk control the more you hold.
        Sign-correct for shorts. Matches scripts/quant_trials.py mark-to-market.
        """
        equity = (self.cash_balance + self.savings_balance
                  + self.reserve_balance)
        if mark_prices:
            for pos in self._positions.values():
                price = mark_prices.get(pos.symbol)
                if price:
                    sgn = 1.0 if pos.direction == "long" else -1.0
                    equity += sgn * (price - pos.entry_price) * pos.size
        return equity

    def record_realized_pnl(self, amount: float):
        """Book realized PnL (USD, net of exit fees) into the lifetime/
        daily/weekly totals AND settle it into cash_balance."""
        self.realized_pnl_total += amount
        self.daily_realized_pnl += amount
        self.weekly_realized_pnl += amount
        self.monthly_realized_pnl += amount
        self.cash_balance += amount

    def reset_daily_pnl(self):
        """Zero the daily realized-PnL counter (UTC day rollover)."""
        self.daily_realized_pnl = 0.0

    def maybe_reset_daily_pnl(self, now: Optional[float] = None):
        """Call once per cycle. Resets daily_realized_pnl at the UTC day
        boundary. `now` is the injected engine time (replay determinism:
        a wall-clock read here made historical replays reset on the
        machine's day, not the recording's); wall clock is the fallback
        for callers without one."""
        _dt = (datetime.fromtimestamp(now, tz=timezone.utc)
               if now is not None else datetime.now(timezone.utc))
        today = _dt.date().isoformat()
        if today != self._last_pnl_reset_date:
            self.reset_daily_pnl()
            self._last_pnl_reset_date = today

    def maybe_close_week(self, now: Optional[float] = None):
        """Detect the ISO-week boundary (UTC) exactly once, restart-safe
        (_last_week_key is persisted). Returns the CLOSING summary dict
        for the week that just ended - the caller owns the rollover
        actions (reserve refill, ledger, audit) - or None mid-week.
        weekly_realized_pnl resets here and only here."""
        _dt = (datetime.fromtimestamp(now, tz=timezone.utc)
               if now is not None else datetime.now(timezone.utc))
        _iso = _dt.isocalendar()
        wk = f"{_iso[0]}-W{_iso[1]:02d}"
        if wk == self._last_week_key:
            return None
        if not self._last_week_key:      # fresh state: adopt, no phantom
            self._last_week_key = wk     # week-0 ledger row
            return None
        summary = {
            "week": self._last_week_key,
            "weekly_realized": round(self.weekly_realized_pnl, 2),
            "cash": round(self.cash_balance, 2),
            "savings": round(self.savings_balance, 2),
            "reserve": round(self.reserve_balance, 2),
            "realized_total": round(self.realized_pnl_total, 2),
        }
        self._last_week_key = wk
        self.weekly_realized_pnl = 0.0
        return summary

    def maybe_close_month(self, now: Optional[float] = None):
        """Calendar-month twin of maybe_close_week (UTC), restart-safe
        via the persisted _last_month_key. Returns the CLOSING summary
        for the month that just ended, or None mid-month. Reporting only
        - unlike the week, the month runs NO reserve rollover (the
        drawdown shock-absorber is weekly by design); the month is a
        goal-grading period. monthly_realized_pnl resets here and only
        here."""
        _dt = (datetime.fromtimestamp(now, tz=timezone.utc)
               if now is not None else datetime.now(timezone.utc))
        mk = f"{_dt.year}-{_dt.month:02d}"
        if mk == self._last_month_key:
            return None
        if not self._last_month_key:     # fresh state: adopt, no phantom
            self._last_month_key = mk
            return None
        summary = {
            "month": self._last_month_key,
            "monthly_realized": round(self.monthly_realized_pnl, 2),
            "cash": round(self.cash_balance, 2),
            "savings": round(self.savings_balance, 2),
            "reserve": round(self.reserve_balance, 2),
            "realized_total": round(self.realized_pnl_total, 2),
        }
        self._last_month_key = mk
        self.monthly_realized_pnl = 0.0
        return summary

    def drawdown_pct(self) -> float:
        """Drawdown from starting capital, based on cash + savings only."""
        current = self.cash_balance + self.savings_balance
        if self.starting_capital == 0:
            return 0.0
        return (self.starting_capital - current) / self.starting_capital * 100

    def note_equity(self, mtm_equity: float) -> None:
        """Ratchet the peak mark-to-market equity (call once per cycle with the
        MTM equity). The peak is the high-water for drawdown_mtm_pct."""
        try:
            self._equity_high_water = max(self._equity_high_water,
                                          float(mtm_equity))
        except (TypeError, ValueError):
            pass

    def drawdown_mtm_pct(self, mtm_equity: float) -> float:
        """TRUE drawdown %: peak-to-current on MARK-TO-MARKET equity (includes
        unrealized loss) — the basis the catastrophe hard-stop + sizer throttle
        use so a book underwater on marks (stops unable to fill in a gap) trips
        the halt. peak is the high-water, floored at starting capital."""
        peak = max(self._equity_high_water, self.starting_capital, 1e-9)
        try:
            cur = float(mtm_equity)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, (peak - cur) / peak * 100.0)
