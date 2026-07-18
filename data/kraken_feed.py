"""
data/kraken_feed.py

Kraken client: market data, account state, and the signed transport that
execution/order_manager.py uses to place/cancel orders. Signing, nonce
management, rate limiting, and the withdrawal deny list live in exactly
one place - here. Also carries the venue-level safety endpoints:
CancelAllOrdersAfter (dead-man's switch) and CancelAll, plus AssetPairs
metadata (price/lot precision, minimum order size) so orders are always
formatted to what the venue will actually accept.
"""

import base64
import hashlib
import hmac
import logging
import os
import time
import urllib.parse
from typing import Optional

import requests
from core.sanitize import (clean_book, clean_candles, drop_forming_candles,
                           safe_float, loads_bounded)
from data._http import ThrottledRestClient

BASE_URL = "https://api.kraken.com"
API_VERSION = "0"

log = logging.getLogger("liquiditybot.data.kraken")

# Offline/altname-mismatch pair metadata. Kraken REJECTS orders whose price
# has more decimals than pair_decimals, and AssetPairs keys its response by
# ALTNAME (BTCUSD -> XBTUSD, DOGEUSD -> XDGUSD), so a pair whose altname
# differs from our compact name resolves from THIS table even online — that
# is the designed mechanism (see the BTC/XBT dual rows), not an edge case.
# Every tradable pair (core trading_pairs AND skimmer candidates) must have a
# row: the generic 2-decimal default silently grids sub-dollar prices
# (config_guard advises on gaps; tests/test_pair_meta_coverage.py enforces).
# Values verified against Kraken AssetPairs 2026-07-17. ordermin = BASE units.
PAIR_META_FALLBACK = {
    "ETHUSD": {"price_decimals": 2, "lot_decimals": 8, "ordermin": 0.002},
    "XBTUSD": {"price_decimals": 1, "lot_decimals": 8, "ordermin": 0.00005},
    "BTCUSD": {"price_decimals": 1, "lot_decimals": 8, "ordermin": 0.00005},
    "SUIUSD": {"price_decimals": 4, "lot_decimals": 5, "ordermin": 5.0},
    "ARBUSD": {"price_decimals": 4, "lot_decimals": 5, "ordermin": 60.0},
    "MINAUSD": {"price_decimals": 5, "lot_decimals": 8, "ordermin": 120.0},
    "FLOWUSD": {"price_decimals": 4, "lot_decimals": 8, "ordermin": 200.0},
    # skimmer candidate pool (AssetPairs-verified 2026-07-17)
    "SOLUSD": {"price_decimals": 2, "lot_decimals": 8, "ordermin": 0.06},
    "XRPUSD": {"price_decimals": 5, "lot_decimals": 8, "ordermin": 1.65},
    "ADAUSD": {"price_decimals": 6, "lot_decimals": 8, "ordermin": 20.0},
    "LINKUSD": {"price_decimals": 5, "lot_decimals": 8, "ordermin": 0.55},
    "DOGEUSD": {"price_decimals": 7, "lot_decimals": 8, "ordermin": 50.0},
    "XDGUSD": {"price_decimals": 7, "lot_decimals": 8, "ordermin": 50.0},
    "DOTUSD": {"price_decimals": 4, "lot_decimals": 8, "ordermin": 3.9},
    "AVAXUSD": {"price_decimals": 3, "lot_decimals": 8, "ordermin": 0.5},
    "LTCUSD": {"price_decimals": 2, "lot_decimals": 8, "ordermin": 0.1},
}

# Hard deny list: no code path in this bot may move funds off-exchange.
# Defense-in-depth on top of using an API key without withdrawal rights.
FORBIDDEN_PRIVATE_ENDPOINTS = frozenset({
    "Withdraw", "WithdrawInfo", "WithdrawStatus", "WithdrawCancel",
    "WalletTransfer", "WithdrawMethods", "WithdrawAddresses",
})


class KrakenFeed(ThrottledRestClient):
    def __init__(self, config: dict):
        super().__init__(config.get("rate_limit_per_sec", 1))
        # Credential resolution, most-secure source first, so real keys never
        # have to live in config.json (where they would sit in the repo / the
        # shipped zip). Precedence: the env var NAMED in config -> the
        # conventional KRAKEN_API_KEY/KRAKEN_API_SECRET env vars -> the literal
        # config value (legacy, discouraged). Only names are ever logged.
        self.api_key = self._resolve_cred(config, "api_key", "api_key_env",
                                          "KRAKEN_API_KEY")
        self.api_secret = self._resolve_cred(config, "api_secret",
                                             "api_secret_env",
                                             "KRAKEN_API_SECRET")
        # fail SAFE on a malformed secret: a non-base64 secret would otherwise
        # raise uncaught inside _sign() on the first private call (the decode
        # runs before _private_post's try). Disable private calls instead; the
        # deny is loud and never echoes the secret.
        if self.api_secret:
            try:
                base64.b64decode(self.api_secret)
            except (ValueError, TypeError):
                log.error("Kraken api_secret is not valid base64 - private "
                          "calls disabled until a correct secret is supplied")
                self.api_secret = ""  # nosec B105 - clearing the secret, not a literal
        self.trading_pairs = config.get("trading_pairs", [])
        self._last_nonce = 0
        # Kraken echoes its own internal pair names ("XETHZUSD") not the
        # altnames we request ("ETHUSD"); get_pair_meta populates this
        # internal->altname map from AssetPairs so a BATCHED Ticker response
        # (many pairs in one call) can be mapped back to our config pairs.
        self._internal_to_alt: dict = {}

    @staticmethod
    def _resolve_cred(config: dict, direct_key: str, env_name_key: str,
                      default_env: str) -> str:
        """Resolve one credential, env before config so secrets need never
        live in the JSON. Order: env var whose NAME is in config[env_name_key]
        -> conventional env var `default_env` -> literal config[direct_key].
        Returns '' if none is set. Logs nothing (no value, no name)."""
        env_name = str(config.get(env_name_key, "") or "")
        if env_name and os.environ.get(env_name):
            return os.environ[env_name]
        if os.environ.get(default_env):
            return os.environ[default_env]
        return str(config.get(direct_key, "") or "")

    # --- Low-level request plumbing ------------------------------------------
    def _sign(self, path: str, data: dict) -> str:
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data["nonce"]) + postdata).encode()
        message = path.encode() + hashlib.sha256(encoded).digest()
        signature = hmac.new(base64.b64decode(self.api_secret), message, hashlib.sha512)
        return base64.b64encode(signature.digest()).decode()

    def _public_get(self, endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
        # bounded parse (loads_bounded) instead of resp.json(): public
        # endpoints are untrusted input, cap the payload we will decode
        resp = self._get_raw(f"{BASE_URL}/{API_VERSION}/public/{endpoint}",
                             params, log, "Kraken")
        if resp is None:
            return None
        data = loads_bounded(resp.text)
        if data is None:
            return None
        if data.get("error"):
            log.warning(f"Kraken public API error on {endpoint}: {data['error']}")
            return None
        return data.get("result")

    def _private_post(self, endpoint: str, data: Optional[dict] = None) -> Optional[dict]:
        if not self.api_key or not self.api_secret:
            log.error(f"Kraken private call to {endpoint} blocked: no API credentials configured.")
            return None

        if endpoint in FORBIDDEN_PRIVATE_ENDPOINTS:
            log.critical(f"BLOCKED: private endpoint {endpoint} is on the "
                        f"permanent deny list (withdrawals/transfers are "
                        f"never allowed from this bot)")
            return None
        self._throttle()
        path = f"/{API_VERSION}/private/{endpoint}"
        data = data or {}
        # monotonic nonce: a backward NTP clock step can never emit a nonce
        # <= the previous one (Kraken rejects those with EAPI:Invalid nonce)
        nonce = int(time.time() * 1000)
        if nonce <= self._last_nonce:
            nonce = self._last_nonce + 1
        self._last_nonce = nonce
        data["nonce"] = str(nonce)

        headers = {
            "API-Key": self.api_key,
            "API-Sign": self._sign(path, data),
        }
        try:
            resp = self.session.post(f"{BASE_URL}{path}", headers=headers, data=data, timeout=10)
            resp.raise_for_status()
            result = loads_bounded(resp.text)
            if result is None:
                return None
            if result.get("error"):
                log.warning(f"Kraken private API error on {endpoint}: {result['error']}")
                return None
            return result.get("result")
        except requests.RequestException as e:
            log.error(f"Kraken private request failed for {endpoint}: {e}")
            return None

    # --- Public read-only data -------------------------------------------------
    def kraken_pair(self, symbol: str) -> str:
        """Convert 'ETH/USD' config format to Kraken's compact pair format 'ETHUSD'."""
        return symbol.replace("/", "")

    def get_ticker_price(self, pair: str) -> Optional[float]:
        """Last trade price for a pair, e.g. 'ETHUSD'."""
        result = self._public_get("Ticker", {"pair": pair})
        if not result:
            return None
        key = next(iter(result))  # Kraken echoes back its own internal pair name
        px = safe_float(result[key]["c"][0], default=0.0)  # 'c' = last trade
        return px if px > 0 else None

    @staticmethod
    def _alias_variants(pair: str) -> set:
        """Every spelling a pair might arrive as. Kraken denominates Bitcoin
        as XBT while our config (and most of the world) writes BTC, so a
        requested BTCUSD can come back keyed XBTUSD / XXBTZUSD. Return both
        spellings so the batched-ticker match doesn't silently miss BTC and
        drop it to a per-cycle fallback fetch (the 6->1 batch is the point)."""
        v = {pair}
        if "XBT" in pair:
            v.add(pair.replace("XBT", "BTC"))
        if "BTC" in pair:
            v.add(pair.replace("BTC", "XBT"))
        # Doge has the same split personality: config says DOGE, Kraken's
        # batched Ticker keys the response XDGUSD. Without both spellings a
        # promoted DOGE/USD paid a redundant per-cycle fallback fetch through
        # the throttled execution client (audit DL-4 2026-07-17).
        if "XDG" in pair:
            v.add(pair.replace("XDG", "DOGE"))
        if "DOGE" in pair:
            v.add(pair.replace("DOGE", "XDG"))
        return v

    def get_tickers(self, pairs: list) -> dict:
        """Batched last-trade prices: ONE Ticker call for many pairs (Kraken
        accepts a comma-separated pair list), returning {config_pair: price}.
        Collapses the fast cycle's per-pair ticker fetches (6 calls -> 1)
        without threading the shared, execution-carrying REST client past
        its rate limit. Never LESS correct than get_ticker_price: any pair
        the batch can't confidently map falls back to a single-pair fetch,
        so a stale name map degrades to the old behavior, only slower."""
        out: dict = {}
        pairs = [p for p in pairs if p]
        if not pairs:
            return out
        result = self._public_get("Ticker", {"pair": ",".join(pairs)})
        if result:
            # every alias spelling of each requested pair -> the caller's
            # exact string, so an XBTUSD/XXBTZUSD response resolves to BTCUSD
            want = {v: p for p in pairs for v in self._alias_variants(p)}
            for internal, info in result.items():
                # newer listings: internal name == altname; legacy pairs
                # (XETHZUSD/XXBTZUSD): resolve via the AssetPairs map
                alt = self._internal_to_alt.get(internal, internal)
                key = want.get(alt) or want.get(internal)
                if key:
                    px = safe_float((info.get("c") or [0])[0], default=0.0)
                    if px > 0:
                        out[key] = px
        # correctness backstop: single-pair fetch for anything unmapped
        for p in pairs:
            if p not in out:
                px = self.get_ticker_price(p)
                if px:
                    out[p] = px
        return out

    def get_order_book(self, pair: str, depth: int = 20) -> Optional[dict]:
        result = self._public_get("Depth", {"pair": pair, "count": depth})
        if not result:
            return None
        key = next(iter(result))
        book = result[key]
        return clean_book({
            "bids": [list(lvl) for lvl in book.get("bids", [])],
            "asks": [list(lvl) for lvl in book.get("asks", [])],
        })

    def get_candles(self, pair: str, interval: int = 5,
                    include_forming: bool = False) -> list:
        """interval in minutes: 1, 5, 15, 30, 60, 240, 1440, 10080, 21600.
        Committed bars only by default: Kraken's last OHLC row is the
        still-forming frame (its `last` field marks the committed
        boundary) and a mutating bar frozen into any append-only cache
        understates every intrabar range. include_forming=True restores
        the raw tail for consumers that want the partial bar (daily
        regime context)."""
        result = self._public_get("OHLC", {"pair": pair, "interval": interval})
        if not result:
            return []
        key = next((k for k in result if k != "last"), None)
        if key is None:
            return []
        # Kraken returns oldest-first already: [time, open, high, low, close, vwap, volume, count]
        out = clean_candles([
            {
                "time": int(row[0]),
                "open": row[1], "high": row[2], "low": row[3],
                "close": row[4], "volume": row[6],
            }
            for row in result[key]
        ])
        if include_forming:
            return out
        return drop_forming_candles(out, interval * 60)

    def get_daily_candles(self, pair: str, limit: int = 720) -> list:
        """Daily OHLCV, oldest-first (Kraken caps OHLC history at 720 rows).
        Keeps today's forming bar: the macro regime reads momentum/vol "as
        of now" and refreshes hourly, so the partial bar self-corrects."""
        candles = self.get_candles(pair, interval=1440, include_forming=True)
        return candles[-limit:] if candles else []

    # --- Private read-only data (account state, not orders) --------------------
    def get_account_balance(self) -> Optional[dict]:
        return self._private_post("Balance")

    def get_trade_balance(self) -> Optional[dict]:
        """TradeBalance: equity ('e'), free margin ('mf'), margin level ('ml', %).

        Margin level feeds the LeverageGovernor; Kraken begins liquidating
        margin positions around 40%, so the governor blocks new leveraged
        entries far above that.
        """
        return self._private_post("TradeBalance", {"asset": "ZUSD"})

    def get_margin_level_pct(self) -> float:
        result = self.get_trade_balance()
        if not result:
            return 0.0
        try:
            return safe_float(result.get("ml"), default=0.0, lo=0.0)
        except (TypeError, ValueError):
            return 0.0

    def get_open_orders(self) -> Optional[dict]:
        result = self._private_post("OpenOrders")
        return result.get("open") if result else None

    # --- Venue-level safety endpoints -------------------------------------
    def cancel_all_orders_after(self, timeout_sec: int) -> bool:
        """Kraken's dead-man's switch: the venue itself cancels every open
        order for this key if this call is not repeated within timeout_sec.
        If the bot, host, or network dies, resting orders die with it -
        no unsupervised limit orders sitting on the book. timeout_sec=0
        disarms the switch."""
        result = self._private_post("CancelAllOrdersAfter",
                                    {"timeout": str(int(timeout_sec))})
        return result is not None

    def cancel_all_orders(self) -> bool:
        """CancelAll: nuke every open order for this key. Used on clean
        shutdown so nothing rests unmanaged while the bot is offline."""
        result = self._private_post("CancelAll")
        if result is not None:
            log.warning(f"CancelAll: {result.get('count', '?')} order(s) "
                        f"cancelled at the venue")
            return True
        return False

    def get_server_time_skew_sec(self) -> Optional[float]:
        """Local clock minus Kraken server clock, in seconds. A skewed
        clock corrupts nonces, order timestamps, and staleness math -
        check it before trusting anything time-based."""
        result = self._public_get("Time")
        if not result:
            return None
        server = safe_float(result.get("unixtime"), default=0.0)
        if server <= 0:
            return None
        return time.time() - server

    def get_pair_meta(self, pairs: list) -> dict:
        """AssetPairs metadata: {config_pair: {price_decimals, lot_decimals,
        ordermin}}. Kraken REJECTS orders whose price has more decimals
        than pair_decimals (e.g. BTC/USD allows 1) - formatting every
        price to 2 decimals works for ETH and silently fails for BTC.
        Falls back to conservative known values offline."""
        # Offline/test fallback. Values verified against Kraken AssetPairs
        # (pair_decimals / lot_decimals / ordermin). Wrong price decimals =
        # guaranteed AddOrder rejection, so each traded pair needs its own
        # row; the generic default of 2 decimals would reject MINA (5) and
        # ARB/FLOW/SUI (4). ordermin is in BASE units.
        fallback = dict(PAIR_META_FALLBACK)
        meta = {}
        result = self._public_get("AssetPairs", {"pair": ",".join(pairs)}) \
            if pairs else None
        if result:
            for internal_key, info in result.items():
                alt = str(info.get("altname", ""))
                if alt:
                    self._internal_to_alt[internal_key] = alt
                meta[alt] = {
                    "price_decimals": int(safe_float(
                        info.get("pair_decimals"), default=2, lo=0, hi=10)),
                    "lot_decimals": int(safe_float(
                        info.get("lot_decimals"), default=8, lo=0, hi=10)),
                    "ordermin": safe_float(info.get("ordermin"),
                                           default=0.0, lo=0.0),
                }
        for p in pairs:
            if p not in meta:
                meta[p] = dict(fallback.get(
                    p, {"price_decimals": 2, "lot_decimals": 8,
                        "ordermin": 0.0}))
                log.info(f"pair meta for {p} from fallback table "
                         f"(AssetPairs unavailable)")
        return meta

    def get_market_data(self) -> dict:
        """Aggregate order book, candles, and price for all configured trading pairs."""
        result = {}
        for symbol in self.trading_pairs:
            pair = self.kraken_pair(symbol)
            order_book = self.get_order_book(pair)
            candles = self.get_candles(pair)
            price = self.get_ticker_price(pair)

            if order_book is None:
                log.warning(f"Kraken: skipping {symbol}, order book unavailable")
                continue

            result[symbol] = {
                "order_book": order_book,
                "candles": candles,
                "price": price,
            }
        return result
