"""core/performance.py — rolling trade-performance analytics (telemetry only).

Neither existing store is a complete P&L ledger: the postmortem engine records
only UNDERPERFORMERS (ml/postmortem.py), and ml/monitor keeps win/loss LABELS
without magnitudes. So there was no honest source for win-rate / profit-factor /
expectancy. This tracker logs EVERY closed trade — win and loss, realized $ and
%, plus R-multiple (realized% ÷ entry-stop%) — into a bounded rolling window and
derives the desk metrics, portfolio-wide and per asset:

  win-rate (+ Wilson lower bound) · profit factor · expectancy ($ and R) ·
  payoff ratio · per-trade Sharpe & Sortino · current / max losing streak.

TELEMETRY ONLY. Nothing here feeds a trading decision, so it cannot move the
market, trip a gate, or change sizing — a corrupt stat can only mis-draw a
panel. Restart-safe: the window round-trips through the state snapshot.
"""
import math
from collections import defaultdict, deque

EPS = 1e-9
_PF_CAP = 99.0          # "no losing trades" sentinel — keeps profit_factor finite/JSON-safe


def _wilson_lcb(wins: int, n: int, z: float = 1.96) -> float:
    """Lower bound of the win rate — the honest floor, not the point estimate,
    so a lucky 3/3 doesn't read as a 100% edge."""
    if n <= 0:
        return 0.0
    p = wins / n
    denom = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    margin = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)
    return max(0.0, (centre - margin) / denom)


class PerformanceTracker:
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.window = max(int(cfg.get("perf_window_trades", 200)), 10)
        self._trades: deque = deque(maxlen=self.window)

    # ------------------------------------------------------------------
    def record_close(self, asset: str, realized_usd: float, entry_usd: float,
                     entry_price: float = 0.0, stop_price=None,
                     now: float = 0.0, is_probe: bool | None = None) -> None:
        """Log one COMPLETED trade (call once per full close, hedges excluded by
        the caller). realized_usd is the whole trade's cumulative net P&L.

        is_probe splits two populations that must not be pooled. A probe is a
        deliberately small exploratory ticket; a conviction trade is the real
        thesis. Averaging them yields an expectancy describing NEITHER - the
        probes drag the mean toward zero while the conviction trades carry the
        variance, and the blended number is the one an operator would read as
        "how is the strategy doing". Pass None (the default) only when the
        provenance is genuinely unknown, e.g. a trade restored from a snapshot
        written before this field existed; those land in their own bucket
        rather than silently counting as conviction."""
        realized_usd = float(realized_usd)
        entry_usd = float(entry_usd)
        ret_pct = (realized_usd / entry_usd * 100.0) if entry_usd > EPS else 0.0
        r_mult = None
        try:
            if stop_price and entry_price and entry_price > 0:
                stop_pct = abs(float(entry_price) - float(stop_price)) \
                    / float(entry_price) * 100.0
                if stop_pct > EPS:
                    r_mult = ret_pct / stop_pct
        except (TypeError, ValueError):
            r_mult = None
        self._trades.append({
            "asset": str(asset), "usd": realized_usd, "ret_pct": ret_pct,
            "r": r_mult, "win": realized_usd > 0.0, "ts": float(now),
            "probe": None if is_probe is None else bool(is_probe)})

    # ------------------------------------------------------------------
    @staticmethod
    def _stats(trades: list) -> dict:
        n = len(trades)
        if n == 0:
            return {"trades": 0}
        wins = [t for t in trades if t["win"]]
        losses = [t for t in trades if not t["win"]]
        gross_win = sum(t["usd"] for t in wins)
        gross_loss = -sum(t["usd"] for t in losses)         # positive magnitude
        net = sum(t["usd"] for t in trades)
        rets = [t["ret_pct"] for t in trades]
        mean = net / n
        mean_ret = sum(rets) / n
        std = math.sqrt(sum((x - mean_ret) ** 2 for x in rets) / n)
        dstd = math.sqrt(sum(min(x, 0.0) ** 2 for x in rets) / n)
        avg_win = gross_win / len(wins) if wins else 0.0
        avg_loss = gross_loss / len(losses) if losses else 0.0
        # current + max consecutive losing streak (window is oldest→newest)
        cur = mx = 0
        for t in trades:
            cur = cur + 1 if not t["win"] else 0
            mx = max(mx, cur)
        rmults = [t["r"] for t in trades if t["r"] is not None]
        if gross_loss > EPS:
            pf = round(min(gross_win / gross_loss, _PF_CAP), 3)
        else:
            pf = _PF_CAP if gross_win > EPS else 0.0
        return {
            "trades": n,
            "win_rate": round(len(wins) / n, 4),
            "win_rate_lcb": round(_wilson_lcb(len(wins), n), 4),
            "profit_factor": pf,
            "expectancy_usd": round(mean, 4),
            "expectancy_r": round(sum(rmults) / len(rmults), 4) if rmults else None,
            "avg_win_usd": round(avg_win, 4),
            "avg_loss_usd": round(-avg_loss, 4),            # signed (negative)
            "payoff_ratio": round(avg_win / avg_loss, 3) if avg_loss > EPS else None,
            "sharpe": round(mean_ret / std, 3) if std > EPS else 0.0,
            "sortino": round(mean_ret / dstd, 3) if dstd > EPS else 0.0,
            "cur_loss_streak": cur,
            "max_loss_streak": mx,
            "gross_profit_usd": round(gross_win, 2),
            "gross_loss_usd": round(gross_loss, 2),
            "net_usd": round(net, 2),
        }

    def snapshot(self) -> dict:
        trades = list(self._trades)
        buckets: dict = defaultdict(list)
        for t in trades:
            buckets[t["asset"]].append(t)
        # Probe and conviction tickets are separate populations - see
        # record_close. "unknown" holds pre-upgrade restored trades and
        # drains as the rolling window turns over; it is reported rather
        # than folded into either side.
        conv: dict = {"probe": [], "conviction": [], "unknown": []}
        for t in trades:
            p = t.get("probe")
            conv["unknown" if p is None
                 else ("probe" if p else "conviction")].append(t)
        return {"overall": self._stats(trades),
                "by_asset": {a: self._stats(ts) for a, ts in buckets.items()},
                "by_conviction": {k: self._stats(v) for k, v in conv.items()}}

    # --- persistence hooks -------------------------------------------
    def to_dict(self) -> dict:
        return {"trades": list(self._trades)}

    def restore(self, d: dict) -> None:
        if not d:
            return
        for t in (d.get("trades") or [])[-self.window:]:
            if isinstance(t, dict) and "usd" in t:
                # A snapshot written before the probe split has no such key.
                # Absent != conviction: setdefault(None) keeps it in the
                # honest "unknown" bucket instead of inflating one side.
                t.setdefault("probe", None)
                self._trades.append(t)
