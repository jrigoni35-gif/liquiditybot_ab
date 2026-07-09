"""
data/webdata_feed.py

Free, keyless crypto market context from public web APIs:

  * CoinGecko /api/v3/global - total market cap and BTC dominance.
    Dominance *shifts* are a rotation/regime tell (money flowing
    into/out of BTC vs alts); the delta feeds the ML feature set.
  * alternative.me /fng/ - the Crypto Fear & Greed Index (0-100).
    Extremes (<=15 or >=85) are blended into the narrative filter's
    fear/euphoria detection in main; the raw value is an ML feature.

Both endpoints are free with no API key. Polling is slow (default 10
min - these numbers move slowly), responses are cached, and any failure
degrades to the last snapshot then to a neutral default. A dead website
can never touch the trading loop.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from core.sanitize import loads_bounded, safe_float

log = logging.getLogger("liquiditybot.data.webdata")

try:
    import requests
except ImportError:                     # pragma: no cover
    requests = None

_UA = {"User-Agent": "liquiditybot/2.0 (research; contact: none)"}


@dataclass
class WebDataSnapshot:
    fear_greed: float = 50.0          # 0 extreme fear .. 100 extreme greed
    fear_greed_yesterday: float = 50.0
    btc_dominance: float = 0.0        # percent
    dominance_delta: float = 0.0      # pct-points vs previous poll
    total_mcap_usd: float = 0.0
    available: bool = False
    ts: float = field(default_factory=time.time)


def _default_fetch(url: str, timeout: float = 10.0) -> Optional[str]:
    if requests is None:
        return None
    resp = requests.get(url, headers=_UA, timeout=timeout)
    resp.raise_for_status()
    return resp.text


class WebDataFeed:
    FNG_URL = "https://api.alternative.me/fng/?limit=2"
    GLOBAL_URL = "https://api.coingecko.com/api/v3/global"

    def __init__(self, config: dict,
                fetch: Callable[[str], Optional[str]] | None = None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.poll_sec = float(cfg.get("poll_minutes", 10.0)) * 60.0
        self.fetch = fetch or _default_fetch
        self._last_poll = 0.0
        self._prev_dominance: Optional[float] = None
        self._snapshot = WebDataSnapshot()

    def snapshot(self) -> WebDataSnapshot:
        return self._snapshot

    def maybe_poll(self, now: float | None = None) -> WebDataSnapshot:
        now = now if now is not None else time.time()
        if not self.enabled or now - self._last_poll < self.poll_sec:
            return self._snapshot
        self._last_poll = now
        snap = WebDataSnapshot(ts=now)
        got_any = False

        # --- Fear & Greed ---
        try:
            raw = self.fetch(self.FNG_URL)
            parsed = loads_bounded(raw)
            if parsed:
                rows = parsed.get("data", []) or []
                if rows:
                    # Fear&Greed is a bounded 0-100 index; clamp defensively
                    snap.fear_greed = safe_float(rows[0].get("value"),
                                                default=50.0, lo=0.0, hi=100.0)
                    if len(rows) > 1:
                        snap.fear_greed_yesterday = safe_float(
                            rows[1].get("value"), default=50.0, lo=0.0, hi=100.0)
                    got_any = True
        except Exception as e:
            log.warning(f"fear/greed fetch failed: {e}")
            snap.fear_greed = self._snapshot.fear_greed
            snap.fear_greed_yesterday = self._snapshot.fear_greed_yesterday

        # --- CoinGecko global ---
        try:
            raw = self.fetch(self.GLOBAL_URL)
            parsed = loads_bounded(raw)
            if parsed:
                d = parsed.get("data", {}) or {}
                # dominance is a 0-100 percentage; mcap is non-negative and
                # capped well above any plausible real value to catch Inf
                snap.btc_dominance = safe_float(
                    (d.get("market_cap_percentage") or {}).get("btc"),
                    default=0.0, lo=0.0, hi=100.0)
                snap.total_mcap_usd = safe_float(
                    (d.get("total_market_cap") or {}).get("usd"),
                    default=0.0, lo=0.0, hi=1e15)
                if self._prev_dominance is not None and snap.btc_dominance > 0:
                    snap.dominance_delta = safe_float(
                        snap.btc_dominance - self._prev_dominance,
                        default=0.0, lo=-100.0, hi=100.0)
                if snap.btc_dominance > 0:
                    self._prev_dominance = snap.btc_dominance
                    got_any = True
        except Exception as e:
            log.warning(f"coingecko global fetch failed: {e}")
            snap.btc_dominance = self._snapshot.btc_dominance
            snap.dominance_delta = 0.0
            snap.total_mcap_usd = self._snapshot.total_mcap_usd

        snap.available = got_any or self._snapshot.available
        if got_any:
            log.info(f"webdata: F&G={snap.fear_greed:.0f} "
                    f"BTC.D={snap.btc_dominance:.1f}% "
                    f"(Δ{snap.dominance_delta:+.2f}pp) "
                    f"mcap=${snap.total_mcap_usd / 1e12:.2f}T")
        self._snapshot = snap
        return snap
