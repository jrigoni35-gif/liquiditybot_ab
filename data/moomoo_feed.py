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

from core.codes import Code

log = logging.getLogger("liquiditybot.data.moomoo")

EPS = 1e-9


@dataclass
class MoomooSnapshot:
    risk_z: float = 0.0               # basket session return, z vs own history
    basket_ret_pct: float = 0.0       # weighted session return, %
    per_ticker: dict = field(default_factory=dict)   # code -> session ret %
    available: bool = False
    ts: float = field(default_factory=time.time)
    # full-basket repeat of the previous poll (closed-market signature).
    # The quote is REAL, so available stays True; this flag says the
    # z-window append was suppressed to stop stale-repeat decay
    # (DF-010/DF-011). Additive field, defaults False (interface rule 7).
    quotes_frozen: bool = False
    # options positioning on the same risk basket (nearest expiry, NTM):
    # put/call volume-ratio z vs own history (crowd fear when high) and
    # the put-minus-call IV skew (tail-hedging premium). Read-only quote
    # data; neutral 0.0 whenever chains are unavailable/unentitled.
    opt_pcr_z: float = 0.0            # put/call VOLUME ratio, z (day flow)
    opt_oi_pcr_z: float = 0.0         # put/call OPEN-INTEREST ratio, z (stock)
    opt_iv_skew: float = 0.0          # put-minus-call IV, points/10, clipped
    opt_pcr: float = 0.0              # raw volume ratio, for the dashboard
    opt_oi_pcr: float = 0.0           # raw OI ratio, for the dashboard
    options_available: bool = False


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
        # frozen-quote gate state (input-feed audit 2026-08-07, item 41a)
        self._last_per: dict = {}       # previous poll's per-ticker returns
        self._frozen = False            # latched: one DF-010 per episode
        self._last_opt_raw: tuple | None = None   # previous (pcr, oi_pcr)
        ocfg = cfg.get("options", {}) or {}
        self.opt_enabled = bool(ocfg.get("enabled", True))
        self.opt_underlyings = list(ocfg.get("underlyings", [])) or \
            [t["code"] for t in self.tickers if t.get("code")][:2]
        self.opt_poll_sec = float(ocfg.get("poll_minutes", 15.0)) * 60.0
        self.opt_max_contracts = int(ocfg.get("max_contracts", 60))
        self.opt_ntm_pct = float(ocfg.get("ntm_band_pct", 10.0))
        self._opt_hist: deque = deque(maxlen=int(ocfg.get("z_lookback_polls",
                                                          40)))
        self._opt_oi_hist: deque = deque(maxlen=int(ocfg.get(
            "z_lookback_polls", 40)))
        self._last_opt_poll = 0.0
        # (pcr_z, oi_pcr_z, iv_skew, raw_pcr, raw_oi_pcr)
        self._opt_vals = (0.0, 0.0, 0.0, 0.0, 0.0)
        self._opt_available = False
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
        from moomoo import OpenQuoteContext  # type: ignore[import-not-found]  # optional SDK, absent by default
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
                log.info(f"moomoo OpenD unreachable at {self.host}:"
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
                    # NOT "unreachable": _probe_port() already returned True
                    # above, so the gateway IS listening. Saying unreachable
                    # here sent a 2026-08-15 diagnosis down a dead end (port
                    # 11111 open, feed still unavailable). Name the real state
                    # and carry `ret`, which is the only value that separates
                    # not-logged-in from no-quote-rights from a slow handshake.
                    log.info(f"moomoo OpenD is LISTENING at {self.host}:"
                             f"{self.port} but get_global_state returned "
                             f"ret={ret} (not logged in, no quote rights, or "
                             f"handshake slower than the sync-query timeout) "
                             f"- running without it")
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
                log.info("moomoo feed enabled but moomoo-api not installed "
                         "(pip install moomoo-api) - running without it")
                self._warned = True
        except Exception as e:
            if not self._warned:
                log.info(f"moomoo OpenD unreachable at {self.host}:"
                            f"{self.port} ({e}) - running without it")
                self._warned = True
        return False

    def _degrade(self) -> None:
        """Mark the snapshot unavailable AND clear every sibling flag.

        Both degradation paths used to set `available = False` alone, leaving
        `options_available` and `quotes_frozen` at their last-LIVE values. A
        corpus row written during a dead session therefore recorded
        `avail_options="1"` — a flag asserting the options chain was live at
        an instant the gateway was gone. The numeric fields already read as
        neutral 0.0 downstream; the FLAGS are how a reader separates "neutral
        because unavailable" from "neutral because the market was flat", which
        is the only job those columns have.

        `ts` is deliberately NOT advanced. A degraded snapshot's timestamp
        should keep pointing at the last REAL observation — stamping it `now`
        would make a dead feed look freshly polled to any staleness check.
        """
        self._snapshot.available = False
        self._snapshot.options_available = False
        self._snapshot.quotes_frozen = False

    def maybe_poll(self, now: float | None = None) -> MoomooSnapshot:
        now = now if now is not None else time.time()
        if not self.enabled or not self.tickers:
            return self._snapshot
        if now - self._last_poll < self.poll_sec:
            return self._snapshot
        self._last_poll = now
        if not self._ensure_ctx():
            self._degrade()
            return self._snapshot
        try:
            self._snapshot = self._poll(now)
        except Exception as e:
            log.warning(f"moomoo poll failed ({e}) - keeping last snapshot")
            self._degrade()
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
        # Frozen-quote gate (input-feed audit 2026-08-07, #1 CRITICAL):
        # moomoo has no market-hours guard, so a closed market re-serves
        # the same last/prev pair every poll and each duplicate append
        # shrank the window's std and dragged its mean onto the frozen
        # value - the z decayed +0.39 -> 0.00 over one closed day (93%
        # duplicate polls) and a weekend injects ~62h of it. A FULL-basket
        # repeat is the closed-market signature; one name moving while
        # another sits still is a market, not a freeze. On a frozen poll
        # the window is not appended, so the z computed from the
        # unpolluted history holds its last honest value.
        frozen = bool(self._last_per) and per == self._last_per
        self._last_per = per
        if frozen:
            if not self._frozen:
                self._frozen = True
                log.info(f"{Code.DF_QUOTES_FROZEN.value}: moomoo basket "
                         f"frozen - every per-ticker return matches the "
                         f"previous poll (closed-market signature); "
                         f"z-window appends suspended, z holds")
        else:
            if self._frozen:
                log.info(f"{Code.DF_QUOTES_RESUMED.value}: moomoo basket "
                         f"moving again - z-window appends resume")
            self._frozen = False
            self._ret_hist.append(basket)
        arr = np.array(self._ret_hist, float)
        sd = float(arr.std()) if len(arr) >= 8 else 0.0
        z = float(np.clip((basket - float(arr.mean())) / sd, -4, 4)) if sd > EPS else 0.0

        # options ride the same connection on their own slower cadence; a
        # chain failure must never take down the equity snapshot, so this
        # is fully fenced and merely reuses the last good option values.
        if self.opt_enabled and now - self._last_opt_poll >= self.opt_poll_sec:
            self._last_opt_poll = now
            try:
                self._opt_vals = self._poll_options()
                self._opt_available = True
            except Exception as e:
                log.warning(f"moomoo options poll failed ({e}) - options "
                            f"context neutral until next attempt")
                self._opt_available = False

        pcr_z, oi_z, skew, pcr, oi_pcr = self._opt_vals \
            if self._opt_available else (0.0, 0.0, 0.0, 0.0, 0.0)
        snap = MoomooSnapshot(risk_z=z, basket_ret_pct=round(basket, 3),
                            per_ticker=per, available=True, ts=now,
                            quotes_frozen=frozen,
                            opt_pcr_z=pcr_z, opt_oi_pcr_z=oi_z,
                            opt_iv_skew=skew, opt_pcr=pcr,
                            opt_oi_pcr=oi_pcr,
                            options_available=self._opt_available)
        log.info(f"moomoo: basket {basket:+.2f}% (z={z:+.2f}) {per}"
                 + (f" | options vol-pcr={pcr:.2f} (z={pcr_z:+.2f}) "
                    f"oi-pcr={oi_pcr:.2f} (z={oi_z:+.2f}) "
                    f"skew={skew:+.2f}" if self._opt_available else ""))
        return snap

    def _poll_options(self) -> tuple:
        """Nearest-expiry, near-the-money put/call positioning across the
        configured underlyings - quote-context reads only (expiries ->
        chain -> market snapshot on the contract codes). Two ratios are
        read PRECISELY apart because they mean different things:
        VOLUME put/call = today's hedging flow; OPEN-INTEREST put/call =
        the standing stock of positioning. IV skew = the tail-hedging
        premium. Returns (pcr_z, oi_pcr_z, iv_skew, raw_pcr, raw_oi_pcr);
        raises on gateway/data problems (the caller fences it)."""
        assert self._ctx is not None
        put_vol = call_vol = put_oi = call_oi = 0.0
        put_iv, call_iv = [], []
        for code in self.opt_underlyings:
            ret, exp = self._ctx.get_option_expiration_date(code)
            if ret != 0 or exp is None or len(exp) == 0:
                continue
            expiry = str(exp.iloc[0]["strike_time"])  # type: ignore  # SDK stubs type the payload as str; DataFrame after ret==0
            ret, chain = self._ctx.get_option_chain(code, start=expiry,
                                                    end=expiry)
            if ret != 0 or chain is None or len(chain) == 0:  # type: ignore  # same SDK stub union
                continue
            rows = list(chain.iterrows())  # type: ignore  # DataFrame after the ret==0 guard
            strikes = sorted(float(r.get("strike_price") or 0.0)
                             for _, r in rows if r.get("strike_price"))
            if not strikes:
                continue
            # median strike anchors the near-the-money band: chains are
            # listed densest around spot, so the median tracks it without
            # needing a separate quote round-trip
            mid = strikes[len(strikes) // 2]
            band = mid * self.opt_ntm_pct / 100.0
            picked = [(str(r.get("code")), str(r.get("option_type")))
                      for _, r in rows
                      if r.get("code")
                      and abs(float(r.get("strike_price") or 0.0) - mid)
                      <= band]
            picked = picked[: self.opt_max_contracts]
            if not picked:
                continue
            ret, snapdf = self._ctx.get_market_snapshot(
                [c for c, _ in picked])
            if ret != 0:
                raise RuntimeError(f"option snapshot ret={ret}: {snapdf}")
            types = dict(picked)
            for _, row in snapdf.iterrows():  # type: ignore  # DataFrame after the ret==0 guard
                c = str(row.get("code"))
                vol = float(row.get("volume") or 0.0)
                oi = float(row.get("option_open_interest") or 0.0)
                iv = float(row.get("option_implied_volatility") or 0.0)
                if types.get(c) == "PUT":
                    put_vol += vol
                    put_oi += oi
                    if iv > EPS:
                        put_iv.append(iv)
                else:
                    call_vol += vol
                    call_oi += oi
                    if iv > EPS:
                        call_iv.append(iv)
        if call_vol <= EPS and put_vol <= EPS:
            raise RuntimeError("no option volume in NTM band")

        pcr = put_vol / max(call_vol, 1.0)
        # OI may be unentitled/zero on some plans: neutral, never fatal
        oi_pcr = (put_oi / max(call_oi, 1.0)) \
            if (put_oi > EPS or call_oi > EPS) else 0.0

        # Same freeze gate as the equity basket, on the RAW ratio pair:
        # option volume/OI are cumulative day totals, so a closed market
        # re-serves them byte-identical and every duplicate append is what
        # pinned opt_oi_pcr_z at a permanent 0.00 in the audit. On a
        # repeat, skip the appends; the z from the unpolluted history
        # holds. (No DF log here: the basket gate above already carries
        # the episode, and options ride the same closed market.)
        opt_frozen = (pcr, oi_pcr) == self._last_opt_raw
        self._last_opt_raw = (pcr, oi_pcr)

        def _z(ratio: float, hist: deque) -> float:
            if not opt_frozen:
                hist.append(ratio)
            if not hist:            # defensive: frozen before any append
                return 0.0
            arr = np.array(hist, float)
            sd = float(arr.std()) if len(arr) >= 8 else 0.0
            return float(np.clip((ratio - float(arr.mean())) / sd,
                                 -4, 4)) if sd > EPS else 0.0

        pcr_z = _z(pcr, self._opt_hist)
        oi_z = _z(oi_pcr, self._opt_oi_hist) if oi_pcr > EPS else 0.0
        skew = 0.0
        if put_iv and call_iv:
            # IV points (e.g. 65 vs 58 -> +7): /10, clip [-3, 3] (30 IV
            # points). The original [-1, 1] censored 43% of options-
            # available corpus rows at -1.0: the crypto-proxy basket
            # routinely runs call IV 10+ points OVER puts (speculative
            # upside bid), so the model saw only "inverted", never how
            # hard. Unit is unchanged (points/10) - only the censoring
            # bound moved; ml/features.py and ml/contracts.py carry the
            # same bound (the feed clip is the binding one).
            skew = float(np.clip(
                (sum(put_iv) / len(put_iv) - sum(call_iv) / len(call_iv))
                / 10.0, -3.0, 3.0))
        return (pcr_z, oi_z, skew, round(pcr, 3), round(oi_pcr, 3))

    def to_dict(self) -> dict:
        """Serializable window/freeze state (owed 41c). The z windows and
        the freeze gate's comparison state survive a restart, closing the
        fleet-measured hole where every rolling window rebuilt empty at
        the measured median 0.5h restart cadence (~3.5h/day of context z
        fabricated back toward neutral by an empty history). Poll
        timestamps are deliberately NOT persisted: an immediate re-poll
        on restart is wanted, and the restored _last_per lets 41a's gate
        classify that first poll honestly (still-frozen market -> frozen,
        moved market -> append)."""
        return {"ret_hist": [float(x) for x in self._ret_hist],
                "opt_hist": [float(x) for x in self._opt_hist],
                "opt_oi_hist": [float(x) for x in self._opt_oi_hist],
                "last_per": dict(self._last_per),
                "frozen": bool(self._frozen),
                "last_opt_raw": (list(self._last_opt_raw)
                                 if self._last_opt_raw else None),
                "opt_vals": [float(x) for x in self._opt_vals],
                "opt_available": bool(self._opt_available)}

    def from_dict(self, d: dict) -> None:
        """Restore window/freeze state. Extend-with-defaults and fail-
        soft: a malformed/pre-41c section leaves the feed exactly at its
        clean-boot state (empty windows), never raises into the caller -
        persistence restore must not be able to take down the feed."""
        try:
            if not isinstance(d, dict):
                return
            for key, hist in (("ret_hist", self._ret_hist),
                              ("opt_hist", self._opt_hist),
                              ("opt_oi_hist", self._opt_oi_hist)):
                vals = d.get(key) or []
                hist.clear()
                hist.extend(float(x) for x in vals)
            lp = d.get("last_per")
            self._last_per = ({str(k): float(v) for k, v in lp.items()}
                              if isinstance(lp, dict) else {})
            self._frozen = bool(d.get("frozen", False))
            raw = d.get("last_opt_raw")
            self._last_opt_raw = ((float(raw[0]), float(raw[1]))
                                  if isinstance(raw, (list, tuple))
                                  and len(raw) == 2 else None)
            ov = d.get("opt_vals")
            if isinstance(ov, (list, tuple)) and len(ov) == 5:
                self._opt_vals = tuple(float(x) for x in ov)
            self._opt_available = bool(d.get("opt_available", False))
        except (TypeError, ValueError):
            # partial garbage: reset to clean-boot rather than run on a
            # half-restored window
            self._ret_hist.clear()
            self._opt_hist.clear()
            self._opt_oi_hist.clear()
            self._last_per = {}
            self._frozen = False
            self._last_opt_raw = None
            self._opt_vals = (0.0, 0.0, 0.0, 0.0, 0.0)
            self._opt_available = False

    def close(self):
        if self._ctx is not None:
            try:
                self._ctx.close()
            except Exception:  # nosec B110 - shutdown close is best-effort
                log.debug("moomoo ctx close failed at shutdown")
            self._ctx = None
