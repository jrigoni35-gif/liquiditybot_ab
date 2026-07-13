"""
Regression for the moomoo options-positioning read (v4 features):
nearest-expiry near-the-money put/call VOLUME ratio (day hedging flow),
put/call OPEN-INTEREST ratio (standing positioning stock), and IV skew
(tail premium) - read precisely apart because they mean different
things. Pins the math, the NTM band, the OI-unentitled fallback, and
the fence: an options failure must never take down the equity snapshot.
No pandas dependency: a minimal fake mirrors the two DataFrame calls
the feed uses (.iloc[0][...], .iterrows() yielding dict-like rows).
"""
from data.moomoo_feed import MoomooFeed


class FakeDF:
    def __init__(self, rows):
        self._rows = rows

    def __len__(self):
        return len(self._rows)

    def iterrows(self):
        return iter(enumerate(self._rows))

    @property
    def iloc(self):
        return self._rows


def _chain_row(code, opt_type, strike):
    return {"code": code, "option_type": opt_type, "strike_price": strike}


class StubCtx:
    """Serves the four quote-context calls the feed makes."""

    def __init__(self, put_vol=300.0, call_vol=100.0, put_oi=40.0,
                 call_oi=80.0, put_iv=60.0, call_iv=50.0,
                 chain_fails=False):
        self.chain_fails = chain_fails
        self.put = dict(vol=put_vol, oi=put_oi, iv=put_iv)
        self.call = dict(vol=call_vol, oi=call_oi, iv=call_iv)

    def get_market_snapshot(self, codes):
        if any(c.startswith("US.COIN2506") for c in codes):   # option leg
            rows = []
            for c in codes:
                side = self.put if "P" in c.split("2506")[1] else self.call
                rows.append({"code": c, "volume": side["vol"] / 2,
                             "option_open_interest": side["oi"] / 2,
                             "option_implied_volatility": side["iv"]})
            return 0, FakeDF(rows)
        rows = [{"code": c, "last_price": 200.0, "prev_close_price": 195.0}
                for c in codes]
        return 0, FakeDF(rows)

    def get_option_expiration_date(self, code):
        return 0, FakeDF([{"strike_time": "2025-06-20"}])

    def get_option_chain(self, code, start=None, end=None, **kw):
        if self.chain_fails:
            return -1, "no entitlement"
        rows = [_chain_row("US.COIN250620C200", "CALL", 200.0),
                _chain_row("US.COIN250620C205", "CALL", 205.0),
                _chain_row("US.COIN250620P200", "PUT", 200.0),
                _chain_row("US.COIN250620P195", "PUT", 195.0),
                _chain_row("US.COIN250620C400", "CALL", 400.0)]  # far OTM
        return 0, FakeDF(rows)

    def get_global_state(self):
        return 0, {}

    def close(self):
        pass


def _feed(ctx, **opt_overrides):
    cfg = {"enabled": True, "poll_minutes": 0.0,
           "tickers": [{"code": "US.COIN", "weight": 1.0}],
           "options": {"enabled": True, "underlyings": ["US.COIN"],
                       "poll_minutes": 0.0, **opt_overrides}}
    return MoomooFeed(cfg, quote_ctx=ctx)


def test_pcr_oi_and_skew_math():
    feed = _feed(StubCtx())
    snap = feed.maybe_poll(1000.0)
    assert snap.available and snap.options_available
    assert abs(snap.opt_pcr - 3.0) < 1e-9        # 300 put vol / 100 call
    assert abs(snap.opt_oi_pcr - 0.5) < 1e-9     # 40 put OI / 80 call
    assert snap.opt_iv_skew == 1.0               # (60-50)/10, clipped


def test_far_otm_strikes_excluded_from_band():
    ctx = StubCtx()
    feed = _feed(ctx, ntm_band_pct=10.0)
    feed.maybe_poll(1000.0)
    # the 400-strike call sits far outside the 10% band around the median
    # strike (200): 4 contracts priced, not 5 (visible via snapshot rows
    # requested); asserted indirectly through the ratio staying 3.0
    assert abs(feed.snapshot().opt_pcr - 3.0) < 1e-9


def test_options_failure_never_breaks_equity_snapshot():
    feed = _feed(StubCtx(chain_fails=False))
    feed._poll_options = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    snap = feed.maybe_poll(1000.0)
    assert snap.available is True                # equity leg intact
    assert snap.options_available is False
    assert snap.opt_pcr_z == 0.0 and snap.opt_iv_skew == 0.0


def test_chain_refusal_yields_no_volume_error_and_neutral():
    feed = _feed(StubCtx(chain_fails=True))
    snap = feed.maybe_poll(1000.0)
    assert snap.available is True
    assert snap.options_available is False


def test_missing_open_interest_stays_neutral_without_killing_volume():
    feed = _feed(StubCtx(put_oi=0.0, call_oi=0.0))
    snap = feed.maybe_poll(1000.0)
    assert snap.options_available is True
    assert abs(snap.opt_pcr - 3.0) < 1e-9
    assert snap.opt_oi_pcr == 0.0 and snap.opt_oi_pcr_z == 0.0
