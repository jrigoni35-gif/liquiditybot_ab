"""
data/moomoo_feed.py

Read-only cross-asset context from moomoo (Futu) OpenAPI. NO EXECUTION,
by construction: this module only ever imports/opens OpenQuoteContext.
The trade context class is never imported anywhere in this codebase, so
there is no code path through which moomoo could place an order.

Why an equities feed in a crypto bot: crypto trades like a risk asset.
A basket of crypto-adjacent equities and risk proxies (COIN, MSTR, QQQ
by default) gives an external read on risk appetite that crypto-native
data can't fake - useful both as an ML feature (equity_risk_z) and as a
structural-stress input to the narrative filter (an equity selloff is
real confirmation that "fear" headlines aren't just noise).

Requirements (all optional - the bot runs fine without any of it):
  1. moomoo account (free) with the OpenD gateway running locally
     (default 127.0.0.1:11111). OpenD handles login; this module never
     sees credentials.
  2. pip install moomoo-api  (imported lazily; absence = feed disabled)
Basic US delayed/realtime snapshot quotes are available to account
holders; check your own quote rights in the moomoo app.

Failure model: SDK missing, OpenD down, or no quote rights -> snapshot
reports available=False and everything downstream uses neutral values.
"OpenD down" is enforced by us, not trusted to the SDK: the SDK's sync
constructor retries a dead gateway forever inside __init__ (observed
live 2026-07-09: it froze the whole cycle loop). A bounded TCP probe
runs before any SDK code, and the context is opened async with a sync-
query timeout so every later call fails with ret != 0 instead of
blocking.
"""

import logging
import socket
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger("liquiditybot.data.moomoo")

EPS = 1e-9


@dataclass
class MoomooSnapshot:
    risk_z: float = 0.0               # basket session return, z vs own history
    basket_ret_pct: float = 0.0       # weighted session return, %
    per_ticker: dict = field(default_factory=dict)   # code -> session ret %
    available: bool = False
    ts: float = field(default_factory=time.time)


class MoomooFeed:
    def __init__(self, config: dict, quote_ctx=None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.host = cfg.get("opend_host", "127.0.0.1")
        self.port = int(cfg.get("opend_port", 11111))
        self.poll_sec = float(cfg.get("poll_minutes", 5.0)) * 60.0
        self.connect_timeout = float(cfg.get("connect_timeout_sec", 5.0))
        self.tickers = cfg.get("tickers", [])   # [{"code":"US.COIN","weight":1.0}]
        self._ctx = quote_ctx                    # injectable for tests
        self._sdk_ok = quote_ctx is not None
        self._last_poll = 0.0
        self._ret_hist: deque = deque(maxlen=int(cfg.get("z_lookback_polls", 60)))
        self._snapshot = MoomooSnapshot()
        self._warned = False

    def snapshot(self) -> MoomooSnapshot:
        return self._snapshot

    # ------------------------------------------------------------------
    @staticmethod
    def _import_sdk():
        """The SDK import, isolated as a seam. The smoke suite patches
        this to raise ImportError so the no-SDK branch is exercised
        deterministically on EVERY machine — including ones where
        moomoo-api is installed and OpenD is live. (A sys.modules
        sentinel was tried first and was bypassed by at least one
        Windows interpreter's import hooks, causing the test to open a
        real gateway connection; a direct seam has no machinery to
        route around.) QUOTE context only — the trade context class is
        deliberately never imported anywhere in this codebase."""
        from moomoo import OpenQuoteContext
        return OpenQuoteContext

    def _probe_port(self) -> bool:
        """Bounded TCP reachability check that runs BEFORE any SDK code.

        OpenQuoteContext's sync constructor never returns while the
        gateway is down (auto-reconnect loop inside __init__ with no
        retry cap), so reaching the SDK with a dead OpenD would block
        the caller — and the caller is the engine's cycle loop."""
        try:
            with socket.create_connection((self.host, self.port),
                                          timeout=self.connect_timeout):
                return True
        except OSError:
            return False

    def _ensure_ctx(self) -> bool:
        if self._ctx is not None:
            return True
        if not self._probe_port():
            if not self._warned:
                log.warning(f"moomoo OpenD unreachable at {self.host}:"
                            f"{self.port} - running without it")
                self._warned = True
            return False
        try:
            # Silence the SDK's own logger (WSAECONNREFUSED spam on
            # Windows when OpenD isn't running is what the wrapper is
            # for) BEFORE constructing anything.
            for name in ("moomoo", "futu", "open_context_base"):
                lg = logging.getLogger(name)
                lg.setLevel(logging.ERROR)
                lg.propagate = False
            OpenQuoteContext = self._import_sdk()
            # async connect + bounded sync-query wait: the default sync
            # constructor loops forever if OpenD dies between the port
            # probe and here (or accepts TCP without speaking the
            # protocol). Async returns immediately, and the query
            # timeout turns "not connected" into ret != 0 below.
            ctx = OpenQuoteContext(host=self.host, port=self.port,
                                   is_async_connect=True)
            ctx.set_sync_query_connect_timeout(self.connect_timeout)
            # Probe once with a get_global_state call; if the gateway
            # isn't usable, release the context immediately so the
            # background retry loop cannot spam our stderr.
            try:
                ret, _ = ctx.get_global_state()
            except Exception:
                ret = -1
            if ret != 0:
                try:
                    ctx.close()
                except (OSError, RuntimeError, AttributeError):
                    # SDK is already tearing down its socket; best-effort
                    # close either way — the caller only cares that we
                    # release our reference so background threads exit
                    pass
                if not self._warned:
                    log.warning(f"moomoo OpenD unreachable at {self.host}:"
                                f"{self.port} - running without it")
                    self._warned = True
                return False
            self._ctx = ctx
            self._sdk_ok = True
            # re-arm the one-shot warning: a later outage after this
            # recovery should warn again, not go silent
            self._warned = False
            log.info(f"moomoo OpenD connected at {self.host}:{self.port}")
            return True
        except ImportError:
            if not self._warned:
                log.warning("moomoo feed enabled but moomoo-api not installed "
                            "(pip install moomoo-api) - running without it")
                self._warned = True
        except Exception as e:
            if not self._warned:
                log.warning(f"moomoo OpenD unreachable at {self.host}:"
                            f"{self.port} ({e}) - running without it")
                self._warned = True
        return False

    def maybe_poll(self, now: float | None = None) -> MoomooSnapshot:
        now = now if now is not None else time.time()
        if not self.enabled or not self.tickers:
            return self._snapshot
        if now - self._last_poll < self.poll_sec:
            return self._snapshot
        self._last_poll = now
        if not self._ensure_ctx():
            self._snapshot.available = False
            return self._snapshot
        try:
            self._snapshot = self._poll(now)
        except Exception as e:
            log.warning(f"moomoo poll failed ({e}) - keeping last snapshot")
            self._snapshot.available = False
            # drop the context so the next poll reconnects cleanly
            try:
                if self._ctx is not None:
                    self._ctx.close()
            except Exception:
                log.debug("moomoo ctx close failed during error recovery")
            self._ctx = None
        return self._snapshot

    def _poll(self, now: float) -> MoomooSnapshot:
        codes = [t["code"] for t in self.tickers if t.get("code")]
        assert self._ctx is not None  # _poll runs only after _ensure_ctx() succeeds
        ret, df = self._ctx.get_market_snapshot(codes)
        if ret != 0:                    # RET_OK == 0 in the SDK
            raise RuntimeError(f"get_market_snapshot ret={ret}: {df}")

        per, num, den = {}, 0.0, 0.0
        weights = {t["code"]: float(t.get("weight", 1.0)) for t in self.tickers}
        for _, row in df.iterrows():  # type: ignore  # SDK stubs type df as str; it is a DataFrame after the ret==0 guard
            code = row.get("code")
            last = float(row.get("last_price") or 0.0)
            prev = float(row.get("prev_close_price") or 0.0)
            if last <= EPS or prev <= EPS:
                continue
            r = (last / prev - 1.0) * 100.0
            per[code] = round(r, 3)
            w = weights.get(code, 1.0)
            num += r * w
            den += w
        if den <= EPS:
            raise RuntimeError("no usable quotes in snapshot")

        basket = num / den
        self._ret_hist.append(basket)
        arr = np.array(self._ret_hist, float)
        sd = float(arr.std()) if len(arr) >= 8 else 0.0
        z = float(np.clip((basket - float(arr.mean())) / sd, -4, 4)) if sd > EPS else 0.0

        snap = MoomooSnapshot(risk_z=z, basket_ret_pct=round(basket, 3),
                            per_ticker=per, available=True, ts=now)
        log.info(f"moomoo: basket {basket:+.2f}% (z={z:+.2f}) {per}")
        return snap

    def close(self):
        if self._ctx is not None:
            try:
                self._ctx.close()
            except Exception:  # nosec B110 - shutdown close is best-effort
                log.debug("moomoo ctx close failed at shutdown")
            self._ctx = None
