"""Crown-jewel safety invariants, pinned at the pytest layer.

These are the CLAUDE.md HARD INVARIANTS that must never regress silently:

  #3  Kraken is the SOLE execution venue. VenueAdapter.execution_eligible
      requires name == "kraken", and a rival quote that lies about being
      eligible and is cheaper is still refused.
      READ THIS BEFORE TRUSTING THE #3 SECTION BELOW (measured 2026-09-05):
      the adapter/router layer these tests exercise is NOT ON THE PRODUCTION
      ORDER PATH. `import runner, main` succeeds with execution.venue_adapters
      made un-importable; `venue_adapters in sys.modules` is False after a
      real import; `.route(` appears repo-wide only in this file; main.py
      constructs `self.router` and never reads it, handing OrderManager the
      Kraken feed directly; and 26,973,374 B of outputs/audit.jsonl contains
      ZERO `VN-` codes (needle control OM-011|LB-000|CV-000 -> 264).
      So these are ADAPTER-CONTRACT pins: they prove the layer refuses a
      non-Kraken venue IF it is ever wired up. They do not prove the running
      bot consults it, because it does not. Wiring it is an order-lifecycle
      change and is docketed for operator adjudication (B4).
  #4  Withdrawals/transfers are impossible. The Kraken private-endpoint
      deny list blocks Withdraw/WalletTransfer/etc. BEFORE any network I/O.

Why this file exists: an audit (2026-07-21) measured coverage and found
these invariants were exercised only by scripts/smoke_test.py (the smoke
battery), never by pytest — and the LIVE router eligibility gate
(routing.SmartOrderRouter.route, execution/routing.py) was covered by
NOTHING. A refactor that relaxed the venue gate or dropped a deny-listed
endpoint would have sailed through `pytest tests/`. These are
characterization tests over the EXISTING (correct) behavior: they change
nothing, they just make the two invariants that matter most impossible to
break without a red test on the fast inner-loop surface.
"""
import pytest


# ===================================================================== #
# INVARIANT #4 — withdrawals/transfers are impossible (deny list)        #
# ===================================================================== #
def test_withdrawal_endpoints_are_blocked_before_any_network(monkeypatch):
    # A private call to a deny-listed endpoint must return None and must
    # NOT reach the rate limiter or the network. Credentials are set so the
    # call clears the "no creds" gate and genuinely reaches the deny check
    # (otherwise the test would pass for the wrong reason).
    from data.kraken_feed import KrakenFeed, FORBIDDEN_PRIVATE_ENDPOINTS

    feed = KrakenFeed({"rate_limit_per_sec": 99, "trading_pairs": []})
    feed.api_key = "k"
    feed.api_secret = "eA=="              # valid-base64 dummy  # nosec B105

    reached = []
    monkeypatch.setattr(feed.session, "post",
                        lambda *a, **k: reached.append("network"))
    monkeypatch.setattr(feed, "_throttle",
                        lambda: reached.append("throttle"))

    for ep in ("Withdraw", "WithdrawInfo", "WithdrawStatus", "WithdrawCancel",
               "WalletTransfer", "WithdrawMethods", "WithdrawAddresses"):
        assert ep in FORBIDDEN_PRIVATE_ENDPOINTS
        assert feed._private_post(ep, {"amount": "999999"}) is None
    # blocked at the deny list: neither the throttle nor the socket ran
    assert reached == []


def test_deny_list_covers_every_withdrawal_and_transfer_verb():
    # a static guard so nobody can quietly shrink the deny list
    from data.kraken_feed import FORBIDDEN_PRIVATE_ENDPOINTS
    required = {"Withdraw", "WithdrawInfo", "WalletTransfer", "WithdrawAddresses"}
    assert required <= FORBIDDEN_PRIVATE_ENDPOINTS


# ===================================================================== #
# INVARIANT #3 — Kraken is the sole execution venue (adapter contract)   #
# ===================================================================== #
_VCFG = {"venues": {"kraken": {"enabled": True}, "ibkr": {"enabled": False},
                    "dma": {"enabled": False}, "prime": {"enabled": False},
                    "ccxt": {"enabled": False}, "fix": {"enabled": False}}}


def test_only_kraken_is_execution_eligible():
    from execution.venue_adapters import VenueRegistry
    reg = VenueRegistry.from_config(_VCFG)
    assert reg.eligible_execution_venues() == ["kraken"]
    for name, ad in reg.adapters.items():
        assert ad.execution_eligible is (name == "kraken")


def test_flag_tamper_cannot_make_a_non_kraken_venue_eligible():
    # hostile flip of BOTH gate flags on a non-kraken adapter still fails,
    # because execution_eligible also requires name == the invariant venue.
    from execution.venue_adapters import VenueRegistry
    reg = VenueRegistry.from_config(_VCFG)
    ib = reg.get("ibkr")
    ib.enabled = True
    ib.can_be_execution_eligible = True
    assert ib.execution_eligible is False


def test_subclassing_cannot_bypass_the_kraken_gate():
    # invariant #3 forbids subclassing around the gate. A subclass that
    # forces can_be_execution_eligible True and enables itself STILL can't
    # execute, because the name-equality clause is not overridable by flags.
    from execution.venue_adapters import VenueAdapter

    class SneakyAdapter(VenueAdapter):
        name = "sneaky"
        transport = "native"
        can_be_execution_eligible = True

    s = SneakyAdapter({"enabled": True})
    assert s.execution_eligible is False
    from execution.venue_adapters import VenueNotEnabled, VenueOrder
    with pytest.raises(VenueNotEnabled):
        s.place(VenueOrder(pair="ETHUSD", side="buy", price=2000.0, size=0.01))


def test_place_raises_on_a_non_eligible_venue():
    from execution.venue_adapters import (VenueNotEnabled, VenueOrder,
                                          VenueRegistry)
    reg = VenueRegistry.from_config(_VCFG)
    with pytest.raises(VenueNotEnabled):
        reg.get("ibkr").place(
            VenueOrder(pair="ETHUSD", side="buy", price=2000.0, size=0.01))


def test_kraken_place_is_accepted_in_ack_only_mode():
    from execution.venue_adapters import VenueOrder, VenueRegistry
    reg = VenueRegistry.from_config(_VCFG)
    ack = reg.get("kraken").place(
        VenueOrder(pair="ETHUSD", side="buy", price=2000.0, size=0.01))
    assert ack.accepted


# ======================================================================= #
# INVARIANT #3 (ADAPTER CONTRACT) — the Smart Order Router routes only to  #
# Kraken. NOT the live path: see the module docstring. This section was     #
# headed "(LIVE PATH)" until 2026-09-05, which was false — the router is    #
# constructed and never read, and the audit trail carries zero VN- codes.   #
# ======================================================================= #
def _quote(venue, fee_bps, eligible, now):
    from execution.routing import VenueQuote
    return VenueQuote(venue=venue, best_bid=99.0, best_ask=100.0,
                      depth_usd=1e6, taker_fee_bps=fee_bps, ts=now,
                      execution_eligible=eligible)


def test_router_never_selects_a_cheaper_rival_that_claims_eligibility():
    # okx is cheaper AND falsely flags execution_eligible=True; kraken is the
    # expensive-but-only legal venue. The router must still pick kraken.
    from execution.routing import SmartOrderRouter
    sor = SmartOrderRouter({})            # defaults: eligible == ["kraken"]
    now = 1000.0
    quotes = [_quote("okx", 1.0, True, now), _quote("kraken", 40.0, True, now)]
    dec = sor.route("buy", 10_000.0, quotes, now=now)
    assert dec.venue == "kraken"
    assert dec.scoreboard["okx"]["eligible"] is False
    assert dec.scoreboard["kraken"]["eligible"] is True


def test_router_returns_no_venue_when_only_rivals_are_present():
    from execution.routing import SmartOrderRouter
    sor = SmartOrderRouter({})
    now = 1000.0
    dec = sor.route("buy", 10_000.0, [_quote("okx", 1.0, True, now)], now=now)
    assert dec.venue == ""
    assert any("SOR-010" in r for r in dec.reasons)
