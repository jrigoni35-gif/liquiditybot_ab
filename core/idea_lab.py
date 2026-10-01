"""core/idea_lab.py - a market-reactive hypothesis population (SHADOW; never promotes).

WHAT THIS IS. The operator asked for an algorithm that keeps generating new
ideas as the market changes and as the book comes under pressure. Done
naively that is a strategy-mining loop, and a strategy-mining loop is an
overfit machine: the best of N tries looks good by construction. This
module is the version the overfit law allows:

  1. FINITE, PRE-DECLARED FAMILY. Every idea the lab can ever have is a
     point on the config grid (gamma x aim_rate x weighting x tilt source).
     Nothing is invented at run time, so the trial count is known.
  2. MARKET-REACTIVE BIRTH. Each step the lab reads the market (cross-
     sectional relative-return autocorrelation -> reverting / trending /
     neutral; short/long volatility -> shock) and the baseline book's
     pressure. When the reading CHANGES, or the baseline is under pressure,
     ideas whose premise matches the new reading are born into paper books.
     An id is born at most once, ever: a retired idea is not retried.
  3. FORWARD-ONLY GRADING. An idea is graded only on bars AFTER its birth,
     decided at close t with data <= t and filled on bar t+1 (maker limit,
     trade-through required). Pinned by a mutation test.
  4. DEFLATED EVIDENCE. Excess return over equal-weight buy-and-hold since
     birth; Sharpe deflated (Bailey & Lopez de Prado) with n_trials = every
     idea ever born. Retired when the excess is negative after
     retire_after_steps.
  5. NEVER PROMOTES. IL-020 "evidence met" is a report line. Promotion into
     the order path is an operator decision record (the
     docs/law/shadow_policy_promotion.md pattern), and forks the cohort.

CLASSIFICATION - SAFE (shadow). Pure computation, no I/O, no audit writes;
the deflated-Sharpe function is injected by the caller so this module does
not import ml/. Imported by no decision module (pinned).
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from core.codes import Code
from core.target_book import (BookParams, PressureLimits,
                              asset_floor_breached, base_weights, plan,
                              pressure_from, tilted_targets)

TILT_SOURCES = ("none", "xs_reversal", "xs_momentum")


# ------------------------------------------------------------- market data
@dataclass
class Bars:
    """Aligned OHLC closes per asset: every list has the same length and
    index i is the same bar for every asset."""
    t: list
    high: dict
    low: dict
    close: dict

    def __len__(self) -> int:
        return len(self.t)


@dataclass(frozen=True)
class MarketReading:
    state: str                  # "reverting" | "trending" | "neutral"
    shock: bool
    xs_autocorr: float | None
    vol_ratio: float | None
    n: int


def _rets(c: list) -> list:
    return [c[i] / c[i - 1] - 1.0 for i in range(1, len(c)) if c[i - 1] > 0]


def _sd(x: list) -> float | None:
    if len(x) < 2:
        return None
    m = sum(x) / len(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def read_market(bars: Bars, i: int, window: int, short: int,
                shock_ratio: float) -> MarketReading:
    """Reading at bar i from bars[: i + 1] only.

    Cross-sectional relative returns r_it - mean_j r_jt; their pooled lag-1
    autocorrelation says whether leaders keep leading (trending) or give
    back (reverting). The cut is the null standard error 1/sqrt(n) at 2
    sigma - structural, not fitted."""
    lo = max(0, i + 1 - window - 1)
    rets = {a: _rets(bars.close[a][lo:i + 1]) for a in bars.close}
    n = min((len(r) for r in rets.values()), default=0)
    if n < 3 or len(rets) < 2:
        return MarketReading("neutral", False, None, None, n)
    rel = {a: [r[k] - sum(rets[b][k] for b in rets) / len(rets)
               for k in range(n)] for a, r in rets.items()}
    num = den = 0.0
    pairs = 0
    for x in rel.values():
        for k in range(1, n):
            num += x[k] * x[k - 1]
            pairs += 1
        den += sum(v * v for v in x)
    ac = num / den if den > 0 else 0.0
    se = 1.0 / math.sqrt(max(pairs, 1))
    state = "reverting" if ac < -2 * se else "trending" if ac > 2 * se else "neutral"
    ratios = []
    for r in rets.values():
        s_long, s_short = _sd(r), _sd(r[-short:])
        if s_long and s_short:
            ratios.append(s_short / s_long)
    vr = sum(ratios) / len(ratios) if ratios else None
    return MarketReading(state, vr is not None and vr > shock_ratio, ac, vr, n)


# ------------------------------------------------------------------ ideas
@dataclass(frozen=True)
class Idea:
    gamma: float
    aim_rate: float
    weighting: str
    tilt: str

    @property
    def id(self) -> str:
        return f"g{self.gamma:g}-a{self.aim_rate:g}-{self.weighting}-{self.tilt}"


def family(cfg: dict) -> list:
    """Every idea the lab can ever hold, in a fixed order."""
    return [Idea(float(g), float(a), str(w), str(t))
            for g, a, w, t in itertools.product(
                cfg["gamma_grid"], cfg["aim_grid"], cfg["weightings"],
                cfg["tilt_sources"])]


def premise_matches(idea: Idea, reading: MarketReading, aim_grid: list) -> bool:
    """Which ideas a reading argues for. Reverting cross-sections favour
    plain rebalancing and reversal tilts; trending ones favour momentum
    tilts; a volatility shock favours patience (the slower half of the aim
    grid). 'none' is always admissible - the rebalancer needs no forecast."""
    if reading.state == "reverting" and idea.tilt == "xs_momentum":
        return False
    if reading.state == "trending" and idea.tilt == "xs_reversal":
        return False
    if reading.state == "neutral" and idea.tilt != "none":
        return False
    if reading.shock:
        mid = sorted(aim_grid)[(len(aim_grid) - 1) // 2]
        return idea.aim_rate <= mid
    return True


# ----------------------------------------------------------- paper books
@dataclass
class ShadowBook:
    idea: Idea
    born_i: int
    cash: float
    units: dict
    peak: float
    rets: list = field(default_factory=list)
    bench_rets: list = field(default_factory=list)
    attempts: int = 0
    fills: int = 0
    fees: float = 0.0
    traded_usd: float = 0.0
    markouts: list = field(default_factory=list)
    codes: dict = field(default_factory=dict)
    alive: bool = True
    status: str = "accruing"
    pressured: bool = False     # pressure seen since the lab last proposed
    bench_units: dict = field(default_factory=dict)  # buy-and-hold twin
    bench_cash: float = 0.0

    def equity(self, prices: dict) -> float:
        return self.cash + sum(u * prices[a] for a, u in self.units.items())

    def note(self, code: str) -> None:
        self.codes[code] = self.codes.get(code, 0) + 1


def _tilts(bars: Bars, i: int, source: str, lookback: int) -> dict:
    if source == "none" or i < lookback:
        return {}
    r = {a: c[i] / c[i - lookback] - 1.0 for a, c in bars.close.items()
         if c[i - lookback] > 0}
    if len(r) < 2:
        return {}
    m = sum(r.values()) / len(r)
    sd = _sd(list(r.values()))
    if not sd:
        return {}
    sign = 1.0 if source == "xs_momentum" else -1.0
    # z/2 maps +-2 sigma onto the tilt range; tilt_cap bounds it after.
    return {a: sign * (v - m) / sd / 2.0 for a, v in r.items()}


def _sigmas(bars: Bars, i: int, lookback: int) -> dict:
    out = {}
    for a, c in bars.close.items():
        s = _sd(_rets(c[max(0, i - lookback):i + 1]))
        if s:
            out[a] = s
    return out


def book_params(idea: Idea, base: BookParams) -> BookParams:
    return BookParams(gamma=idea.gamma, aim_rate=idea.aim_rate,
                      tilt_cap=base.tilt_cap, weighting=idea.weighting,
                      invest_frac=base.invest_frac,
                      min_order_usd=base.min_order_usd,
                      maker_fee_bps=base.maker_fee_bps)


def decide(book: ShadowBook, bars: Bars, i: int, base: BookParams,
           cfg: dict, lim: PressureLimits):
    """The decision at close i. Reads bars[: i + 1] ONLY - pinned by a test
    that hands it bars truncated at i. Returns (plan, prices at i)."""
    idea = book.idea
    params = book_params(idea, base)
    px = {a: c[i] for a, c in bars.close.items()}
    assets = sorted(px)
    w = base_weights(assets, _sigmas(bars, i, int(cfg["sigma_lookback_bars"])),
                     params.weighting, params.invest_frac)
    tgt = tilted_targets(w, _tilts(bars, i, idea.tilt,
                                   int(cfg["tilt_lookback_bars"])),
                         params.tilt_cap)
    flb, fdd = int(cfg["floor_lookback_bars"]), float(cfg["asset_floor_drawdown"])
    for a in assets:
        if asset_floor_breached(bars.close[a][max(0, i - flb):i + 1], fdd):
            tgt[a] = 0.0
            book.note(Code.TB_ASSET_FLOOR.value)
    eq = book.equity(px)
    fee = params.maker_fee_bps / 1e4
    if not book.rets and not book.units and eq > 0:
        # Seed at target on the birth close (maker fee paid) so a grade
        # measures the rebalancing POLICY, not a cash ramp-up.
        for a in assets:
            usd = eq * tgt.get(a, 0.0)
            if usd > 0:
                book.units[a] = usd / px[a]
                book.cash -= usd * (1.0 + fee)
                book.fees += usd * fee
        eq = book.equity(px)
    if not book.bench_units:
        # Benchmark twin: the same cash, invest_frac bought equal-weight at
        # the birth close and never touched (frictionless, so the twin is
        # the generous bar - a book must beat holding, fees and all).
        per = eq * params.invest_frac / len(assets)
        book.bench_units = {a: per / px[a] for a in assets}
        book.bench_cash = eq - per * len(assets)
    book.peak = max(book.peak, eq)
    win = int(cfg["pressure_window_orders"])
    fr = (book.fills / book.attempts) if book.attempts >= win else None
    mk = (sum(book.markouts[-win:]) / len(book.markouts[-win:])
          if len(book.markouts) >= win else None)
    rd = read_market(bars, i, int(cfg["sigma_lookback_bars"]),
                     int(cfg["vol_short_bars"]), lim.vol_shock_ratio)
    dd = 1.0 - eq / book.peak if book.peak > 0 else None
    pr = pressure_from(fr, mk, rd.vol_ratio, dd, lim)
    p = plan(book.units, book.cash, px, tgt, params, pr)
    if p.pressure:
        book.note(p.pressure)
        book.pressured = True
    for c in p.holds.values():
        book.note(c)
    return p, px


def step_book(book: ShadowBook, bars: Bars, i: int, base: BookParams,
              cfg: dict, lim: PressureLimits) -> None:
    """Decide at close i (data <= i), fill on bar i+1, mark at close i+1."""
    p, px = decide(book, bars, i, base, cfg, lim)
    eq = book.equity(px)
    fee = base.maker_fee_bps / 1e4
    off = float(cfg["quote_offset_bps"]) / 1e4
    j = i + 1
    for o in p.orders:
        book.note(o.code)
        book.attempts += 1
        a = o.asset
        if o.side == "buy":
            lim_px = px[a] * (1.0 - off)
            if not bars.low[a][j] < lim_px:
                continue
            qty = o.notional_usd / lim_px
            cost = qty * lim_px * (1.0 + fee)
            if cost > book.cash:
                qty = book.cash / (lim_px * (1.0 + fee))
                cost = book.cash
            if qty <= 0:
                continue
            book.cash -= cost
            book.units[a] = book.units.get(a, 0.0) + qty
            book.markouts.append((bars.close[a][j] / lim_px - 1.0) * 1e4)
        else:
            lim_px = px[a] * (1.0 + off)
            if not bars.high[a][j] > lim_px:
                continue
            qty = min(o.notional_usd / lim_px, book.units.get(a, 0.0))
            if qty <= 0:
                continue
            book.cash += qty * lim_px * (1.0 - fee)
            book.units[a] = book.units.get(a, 0.0) - qty
            book.markouts.append((1.0 - bars.close[a][j] / lim_px) * 1e4)
        book.fills += 1
        book.fees += qty * lim_px * fee
        book.traded_usd += qty * lim_px
    px1 = {a: c[j] for a, c in bars.close.items()}
    eq1 = book.equity(px1)
    book.rets.append(eq1 / eq - 1.0 if eq > 0 else 0.0)
    b0 = book.bench_cash + sum(u * px[a] for a, u in book.bench_units.items())
    b1 = book.bench_cash + sum(u * px1[a] for a, u in book.bench_units.items())
    book.bench_rets.append(b1 / b0 - 1.0 if b0 > 0 else 0.0)


def grade(book: ShadowBook, n_trials: int, dsr_fn=None) -> dict:
    """Excess-over-benchmark summary; DSR only when a function is injected."""
    ex = [r - b for r, b in zip(book.rets, book.bench_rets, strict=True)]
    n = len(ex)
    out = {"id": book.idea.id, "born_i": book.born_i, "steps": n,
           "status": book.status, "fills": book.fills,
           "attempts": book.attempts, "fees_usd": round(book.fees, 4),
           "traded_usd": round(book.traded_usd, 2),
           "cum_return": _cum(book.rets), "cum_bench": _cum(book.bench_rets),
           "mean_excess": (sum(ex) / n) if n else None,
           "sharpe_excess": None, "dsr": None, "codes": dict(book.codes)}
    sd = _sd(ex)
    if sd and n:
        sr = (sum(ex) / n) / sd
        out["sharpe_excess"] = sr
        if dsr_fn is not None and n >= 20:
            res = dsr_fn(sr, n, n_trials=max(n_trials, 1))
            out["dsr"] = res.get("dsr") if isinstance(res, dict) else res
    return out


def _cum(r: list) -> float:
    v = 1.0
    for x in r:
        v *= 1.0 + x
    return v - 1.0


# -------------------------------------------------------------------- lab
@dataclass
class IdeaLab:
    cfg: dict                   # target_book.idea_lab + shared book keys
    base: BookParams
    limits: PressureLimits
    start_cash: float
    books: dict = field(default_factory=dict)        # id -> ShadowBook
    born: list = field(default_factory=list)         # ids in birth order
    events: list = field(default_factory=list)       # (i, code, id, detail)
    last_state: tuple | None = None
    baseline_id: str = ""

    def __post_init__(self) -> None:
        self._family = family(self.cfg)
        base_idea = Idea(self.base.gamma, self.base.aim_rate,
                         self.base.weighting, "none")
        self.baseline_id = base_idea.id
        self._baseline = base_idea

    @property
    def n_trials(self) -> int:
        return len(self.born)

    def _birth(self, idea: Idea, i: int, why: str) -> None:
        self.books[idea.id] = ShadowBook(idea, i, self.start_cash, {},
                                         self.start_cash)
        self.born.append(idea.id)
        self.events.append((i, Code.IL_BORN.value, idea.id, why))

    def step(self, bars: Bars, i: int) -> None:
        """Advance every live book from bar i to i+1, then read, retire and
        propose. Requires bar i+1 to exist; reads nothing beyond it."""
        if i + 1 >= len(bars):
            raise IndexError("step(i) needs bar i+1")
        if not self.books:
            self._birth(self._baseline, i, "baseline")
        for b in self.books.values():
            if b.alive:
                step_book(b, bars, i, self.base, self.cfg, self.limits)
        self._retire_and_flag(i)
        rd = read_market(bars, i, int(self.cfg["reading_window_bars"]),
                         int(self.cfg["vol_short_bars"]),
                         self.limits.vol_shock_ratio)
        bl = self.books[self.baseline_id]
        pressured = bl.pressured
        state = (rd.state, rd.shock)
        if state != self.last_state or pressured:
            why = f"{rd.state}{'+shock' if rd.shock else ''}" \
                  f"{'+pressure' if pressured else ''}"
            self._propose(rd, i, why)
            self.last_state = state
            bl.pressured = False

    def _propose(self, rd: MarketReading, i: int, why: str) -> None:
        alive = sum(1 for b in self.books.values() if b.alive)
        births = 0
        for idea in self._family:
            if births >= int(self.cfg["max_births_per_reading"]):
                break
            if idea.id in self.books:
                continue
            if not premise_matches(idea, rd, self.cfg["aim_grid"]):
                continue
            if alive >= int(self.cfg["max_alive"]):
                self.events.append((i, Code.IL_BIRTH_REFUSED.value, idea.id,
                                    "population full"))
                return
            self._birth(idea, i, why)
            alive += 1
            births += 1

    def _retire_and_flag(self, i: int) -> None:
        for b in self.books.values():
            if not b.alive or b.idea.id == self.baseline_id:
                continue
            n = len(b.rets)
            ex = sum(r - x for r, x in zip(b.rets, b.bench_rets, strict=True))
            if n >= int(self.cfg["retire_after_steps"]) and ex < 0:
                b.alive, b.status = False, "retired"
                self.events.append((i, Code.IL_RETIRED.value, b.idea.id,
                                    f"excess {ex:+.4f} after {n} steps"))

    def report(self, dsr_fn=None) -> dict:
        rows = [grade(b, self.n_trials, dsr_fn) for b in self.books.values()]
        bar = float(self.cfg["dsr_bar"])
        min_n = int(self.cfg["min_evidence_steps"])
        for r in rows:
            if (r["dsr"] is not None and r["dsr"] >= bar
                    and r["steps"] >= min_n and r["status"] != "retired"):
                r["status"] = "evidence (NOT a promotion)"
                r["code"] = Code.IL_EVIDENCE.value
        alive = sum(1 for b in self.books.values() if b.alive)
        return {"n_trials": self.n_trials, "family_size": len(self._family),
                "alive": alive, "retired": self.n_trials - alive,
                "baseline": self.baseline_id, "ideas": rows,
                "events": self.events}
