# Execution & Connectivity — rev 4

Where each institutional capability lives, what is live code versus
groundwork, and the exact contract for adding real external
connectivity later. The system's oldest invariant is restated first
because everything below bends around it: **Kraken is the sole
execution venue; every other integration is read-only.**

## Implemented and running

**Execution algorithms — `execution/algos.py`.** VWAP, TWAP, POV and
Implementation Shortfall (Almgren-Chriss discretization) as
parent/child schedulers. Pure scheduling math; every child prints
through the unchanged hardened path (AS quote → tactics → firewall →
order_manager, limits-only entries). Child pacing floors at 30s so
slicing coexists with the FW-020 order budget — enforced again in
`config_guard`. Per-parent implementation-shortfall TCA against the
arrival price is computed on every fill and surfaced in `status.json →
exec_algos`. Parents are deliberately not persisted: a restart abandons
the unfilled remainder; filled children are ordinary positions already
managed by tiers, stops and inventory. Config: `execution.algos`
(default **disabled** — flipping it on is the only behavioral change).

**Smart order routing — `execution/routing.py`.** Venue scoring on
taker fee, half-spread, depth cover and staleness, with the full
scoreboard kept for the audit trail. Execution eligibility is
hard-filtered to `["kraken"]`; any other venue in that list is a FATAL
config error in live mode. Routing math being ready is preparation,
not permission.

**FIX protocol — `execution/fix_codec.py`.** Wire-exact FIX 4.4 codec:
BodyLength/CheckSum per spec, Logon/Heartbeat/TestRequest/Logout/
NewOrderSingle/OrderCancelRequest builders, ExecutionReport parsing,
sequence tracking with gap detection. Fully unit-tested, wired to
nothing — the protocol layer ships now so a future FIX session is an
adapter, not a rewrite.

**REST API — `api/rest_server.py`.** Stdlib-only HTTP surface on
127.0.0.1 (bind not configurable): status reads plus the risk-neutral/
risk-reducing control verbs. `arm_live`, `sim_*` and `stop` are not
exposed and cannot be added by config. Optional shared-secret header.
Config: `api_server.rest` (default disabled).

**gRPC API — `api/liquiditybot.proto` + `api/grpc_server.py`.** Same
surface, same exclusions, optional dependency (grpcio + generated
stubs); absence degrades with one warning, moomoo-style.

**CCXT — `data/ccxt_feed.py`.** Read-only market-data adapter with the
native feeds' interface, public endpoints only. Credential-shaped keys
in its config **refuse construction** (CCXT-001); there is no keyed
mode. Everything crosses `core/sanitize` before use. Config:
`exchanges.ccxt` (default disabled).

## Groundwork with an explicit onboarding contract

**Direct market access / Interactive Brokers / institutional prime
brokers.** These are account relationships before they are code. What
ships now is the seam they plug into — the `VenueAdapter` contract:

An execution venue adapter must provide, with these exact semantics:
`place_limit(pair, side, price, size, post_only) -> order_id`;
`cancel(order_id) -> bool`; `open_orders() -> list`; `balances() ->
dict`; `get_order_book(pair) / get_ticker_price(pair)` for marks; and
venue metadata (`precision`, `ordermin`, fee schedule). It must never
expose withdrawal or transfer endpoints — the deny-list invariant
applies to every venue, not just Kraken. Wiring order: implement the
adapter → register a `VenueQuote` with `execution_eligible=True` →
extend `execution.routing.eligible_venues` → accept that
`config_guard` makes this FATAL until the invariant line itself is
consciously amended, in code review, with eyes open.

For Interactive Brokers specifically: `ib_insync` against TWS/Gateway
is the sane client; equities/futures context could alternatively enter
as a *data* feed exactly like the moomoo integration (lazy import,
degrade on absence) without touching execution at all — that path
needs no invariant change and is the recommended first step. Prime
connectivity (FIX 4.4 sessions to a prime's OMS) rides the codec
already shipped; the missing pieces are credentials, a session
transport, and conformance testing against the counterparty's spec —
none of which should be faked in code.
