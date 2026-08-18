"""
execution/venue_adapters.py — the VenueAdapter contract, rev 4

routing.py promised a "VenueAdapter contract" but only ever shipped the
scoring math. This module is the contract: one abstract surface every
execution venue must implement, a registry that builds adapters from
config, and the safety invariant made mechanical rather than
documentary —

    KRAKEN IS THE SOLE EXECUTION-ELIGIBLE VENUE.

Every other venue on your list — Interactive Brokers, a DMA sponsored
line, an institutional prime, a CCXT-fronted exchange, a raw FIX
session — is a first-class *registered* adapter so the OMS, router,
and audit trail can all reason about it uniformly. But each ships
`enabled=False` and `execution_eligible=False`, and its `place()`
raises `VenueNotEnabled`. Turning one on is a deliberate act: set
`enabled`, resolve credentials from the environment, add it to
`execution.routing.eligible_venues`, and clear the config-guard gate
(config_guard already makes any non-kraken eligible venue FATAL in
live). Routing math being ready is preparation, not permission — and
now the adapter layer enforces the same line the docs asserted.

Credentials are NEVER read from config. An enabled adapter resolves
`api_key` / `api_secret` from the env var *names* in config via
core.security, so secrets live in the process environment, never in
the JSON or the repo.

Nothing here opens a socket. These are the typed seams a live
integration fills; the disabled default is the whole point.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from core.codes import Code, tag

log = logging.getLogger("liquiditybot.execution.venue_adapters")

EXECUTION_INVARIANT_VENUE = "kraken"

# transport a venue speaks; informational for the registry/audit
_TRANSPORTS = {"native", "rest", "grpc", "fix", "ccxt", "ib_gateway",
               "sponsored_dma"}


class VenueNotEnabled(RuntimeError):
    """Raised when execution is attempted on a disabled/ineligible venue."""


class VenueNotImplemented(NotImplementedError):
    """Raised when a connectivity stub has no live transport wired."""


@dataclass
class VenueOrder:
    """Venue-agnostic child order handed to an adapter. Deliberately the
    same fields the hardened order path already validates upstream."""
    pair: str
    side: str                 # buy | sell
    price: float
    size: float
    purpose: str = "entry"    # entry | exit | hedge
    post_only: bool = True
    ordertype: str = "limit"
    client_ref: str = ""


@dataclass
class VenueAck:
    accepted: bool
    venue: str
    venue_order_id: str = ""
    reason: str = ""


@dataclass
class AdapterStatus:
    name: str
    transport: str
    enabled: bool
    execution_eligible: bool
    creds_resolved: bool
    note: str = ""


class VenueAdapter:
    """Abstract execution-venue contract. Concrete adapters implement
    `_place`; the base enforces the enabled/eligible gate so no subclass
    can accidentally route live while disabled."""

    name = "abstract"
    transport = "native"
    #: only kraken may ever flip this True; the registry re-checks it
    can_be_execution_eligible = False

    def __init__(self, config: dict):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.key_env = cfg.get("api_key_env", "")
        self.secret_env = cfg.get("secret_env", "")
        self.endpoint = cfg.get("endpoint", "")
        self.note = cfg.get("_note", "")
        self._creds = None

    # ---- credential resolution (env only, never config) --------------
    def resolve_credentials(self) -> bool:
        """Resolve api_key/secret from the *environment variable names*
        given in config — never from config values themselves, so
        secrets never live in the JSON or the repo."""
        if not self.enabled:
            return False
        if not self.key_env or not self.secret_env:
            return False
        import os
        k = os.environ.get(self.key_env) or None
        s = os.environ.get(self.secret_env) or None
        self._creds = (k, s) if (k and s) else None
        if self._creds is None:
            log.warning(tag(
                Code.VN_CREDENTIAL_MISSING,
                f"{self.name} enabled but credentials unresolved from "
                f"env ({self.key_env}/{self.secret_env})"))
        return self._creds is not None

    @property
    def creds_resolved(self) -> bool:
        return self._creds is not None

    @property
    def execution_eligible(self) -> bool:
        """A venue may execute only if it is (a) enabled, (b) structurally
        allowed to be eligible, and (c) the invariant venue. (c) makes the
        kraken-sole-execution rule impossible to bypass by subclassing."""
        return (self.enabled and self.can_be_execution_eligible
                and self.name == EXECUTION_INVARIANT_VENUE)

    # ---- the gate every order passes --------------------------------
    def place(self, order: VenueOrder) -> VenueAck:
        if not self.execution_eligible:
            raise VenueNotEnabled(
                f"{Code.VN_NOT_ENABLED.value}: venue '{self.name}' is not "
                f"execution-eligible (enabled={self.enabled}); Kraken is "
                f"the sole execution venue")
        return self._place(order)

    def _place(self, order: VenueOrder) -> VenueAck:      # pragma: no cover
        raise VenueNotImplemented(
            f"{Code.VN_NOT_IMPLEMENTED.value}: {self.name} has no live "
            f"transport wired")

    def status(self) -> AdapterStatus:
        return AdapterStatus(
            name=self.name, transport=self.transport, enabled=self.enabled,
            execution_eligible=self.execution_eligible,
            creds_resolved=self.creds_resolved, note=self.note)


# ----------------------------------------------------------------------
# concrete adapters
# ----------------------------------------------------------------------
class KrakenAdapter(VenueAdapter):
    """The one execution-eligible venue. Placement is delegated to the
    existing hardened order path (OrderManager -> KrakenFeed); this
    adapter is a thin conformance shim so routing/registry can treat
    Kraken through the same contract as everything else. When no live
    placement callback is injected, it operates in acknowledge-only mode
    (dry-run / tests) rather than opening a socket."""

    name = "kraken"
    transport = "native"
    can_be_execution_eligible = True

    def __init__(self, config: dict, place_fn=None):
        super().__init__(config)
        # kraken is enabled by default — it is the execution venue
        self.enabled = bool((config or {}).get("enabled", True))
        self._place_fn = place_fn        # injected OrderManager.submit bridge

    def _place(self, order: VenueOrder) -> VenueAck:
        if self._place_fn is None:
            return VenueAck(accepted=True, venue=self.name,
                            reason="ack-only (no live bridge injected)")
        return self._place_fn(order)


class _DisabledConnectivityAdapter(VenueAdapter):
    """Registered, reasoned-about, and hard-off. Shared body for every
    non-kraken venue: it can never be execution-eligible, and place()
    fails closed via the base gate before _place is ever reached."""

    can_be_execution_eligible = False

    def _place(self, order: VenueOrder) -> VenueAck:      # pragma: no cover
        raise VenueNotEnabled(
            f"{Code.VN_NOT_ENABLED.value}: {self.name} is a disabled "
            f"connectivity adapter (transport={self.transport}); wire a "
            f"live session and pass config_guard before enabling")


class IBKRAdapter(_DisabledConnectivityAdapter):
    """Interactive Brokers via the Client Portal / TWS gateway. Equities,
    futures, FX; read-only cross-asset context today, execution only
    after onboarding + config-guard clearance."""
    name = "ibkr"
    transport = "ib_gateway"


class DMAAdapter(_DisabledConnectivityAdapter):
    """Sponsored Direct Market Access line. Naked/filtered sponsored
    access sits behind a broker's 15c3-5 risk controls — this adapter
    is the client seam, disabled until that relationship exists."""
    name = "dma"
    transport = "sponsored_dma"


class PrimeBrokerAdapter(_DisabledConnectivityAdapter):
    """Institutional prime / prime-of-prime. Give-up and allocation flow,
    cross-margin, custody — none of which this bot touches by default.
    Withdrawals/transfers remain on the permanent deny list regardless."""
    name = "prime"
    transport = "fix"


class CCXTAdapter(_DisabledConnectivityAdapter):
    """CCXT-fronted exchange execution. The CCXT *data* feed
    (data/ccxt_feed.py) is public-read-only and independent; this
    execution adapter is the write side and stays disabled."""
    name = "ccxt"
    transport = "ccxt"


class FIXAdapter(_DisabledConnectivityAdapter):
    """Raw FIX 4.2/4.4 session. The codec + session bookkeeping ship in
    execution/fix_codec.py; this adapter is where a live acceptor would
    attach once credentials and a counterparty exist."""
    name = "fix"
    transport = "fix"


_ADAPTER_TYPES = {
    "kraken": KrakenAdapter,
    "ibkr": IBKRAdapter,
    "dma": DMAAdapter,
    "prime": PrimeBrokerAdapter,
    "ccxt": CCXTAdapter,
    "fix": FIXAdapter,
}


@dataclass
class VenueRegistry:
    adapters: dict = field(default_factory=dict)

    @classmethod
    def from_config(cls, execution_cfg: dict, kraken_place_fn=None):
        """Build the registry from config.execution.venues. Kraken is
        always registered (enabled by default); the rest register from
        their config blocks, disabled unless explicitly turned on — and
        even then never execution-eligible (the invariant)."""
        cfg = execution_cfg or {}
        venues_cfg = cfg.get("venues", {}) or {}
        adapters = {}
        # kraken first, always present
        kcfg = dict(venues_cfg.get("kraken", {}))
        adapters["kraken"] = KrakenAdapter(kcfg, place_fn=kraken_place_fn)
        for name, klass in _ADAPTER_TYPES.items():
            if name == "kraken":
                continue
            adapters[name] = klass(venues_cfg.get(name, {}))
        reg = cls(adapters=adapters)
        reg._enforce_invariant()
        for a in adapters.values():
            if a.enabled:
                a.resolve_credentials()
                log.info(tag(
                    Code.VN_REGISTERED,
                    f"venue '{a.name}' registered (transport={a.transport}, "
                    f"eligible={a.execution_eligible})"))
        return reg

    def _enforce_invariant(self):
        rogue = [a.name for a in self.adapters.values()
                 if a.execution_eligible and a.name != EXECUTION_INVARIANT_VENUE]
        if rogue:
            # defense in depth: the property already forbids this, so
            # reaching here means a subclass lied. Scream and hard-disable.
            log.critical(tag(
                Code.VN_ROGUE_EXECUTION,
                f"non-kraken venues claim execution eligibility "
                f"{rogue} — force-disabling; Kraken is the sole execution "
                f"venue"))
            for name in rogue:
                self.adapters[name].enabled = False

    def get(self, name: str) -> Optional[VenueAdapter]:
        return self.adapters.get(str(name).lower())

    def eligible_execution_venues(self) -> list:
        return [a.name for a in self.adapters.values()
                if a.execution_eligible]

    def status(self) -> dict:
        return {name: vars(a.status())
                for name, a in sorted(self.adapters.items())}
