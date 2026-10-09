---
title: "Pyth Network evaluation — REFUTED as a free data source"
category: sources
status: SETTLED
summary: "Pyth is NOT usable keyless and nothing should be wired to it. Refutes a same-session claim of the page's own author (Hermes REST/SSE keyless; MCP endpoint keyless historical/OHLC) by RUNTIME probe, not by reading: metadata search returns 200 keyless (all 12 bot assets found as Crypto.<A>/USD) but real-time price, TradingView-shim OHLC and point-in-time updates return 401/404/401 — the free surface is feed METADATA ONLY, every actual price sits behind a Pyth Pro token. The pyth-plugin README's 'No auth' rows are contradicted by the backing REST and are UNVERIFIED (no MCP handshake attempted). Availability-failure-mode kill. Gating is vendor-mutable: the 401s are as-of 2026-08-30 ~21:31Z and a future free tier needs a fresh probe, not this page."
tags: [data-sources, availability, refuted-claims, pyth, keyless, the-method]
sources: 1
ingested: 2026-08-30
updated: 2026-08-30
---

# Pyth Network evaluation — REFUTED as a free data source (2026-08-30)

> [!note] **Frontmatter added 2026-08-30 by the cut-#9 / audit-wave filing pass**
> — the page shipped without it and the vault's iron rule 3 requires it. The
> frontmatter restates this page's own verdict and adds nothing; `status:
> SETTLED` reflects the runtime probes recorded below. The body is untouched.
> Related: [[concepts/availability-failure-mode]] ·
> [[synthesis/evidence-closed-register]] (**not** added as a register row —
> that is this page's author's call, and the gating is vendor-mutable) ·
> [[concepts/the-method]].

**Verdict: NOT USEFUL KEYLESS. Do not wire anything.** The claim it refutes
was my own, same session ("Hermes REST/SSE keyless, needs no library; MCP
endpoint keyless historical/OHLC") — killed by the runtime, not by reading
(the-method rule 2; measurements below, all stamped 2026-08-30 ~21:31Z).

## Measured (each one HTTP call, urllib, no auth header)

| Surface | Result |
|---|---|
| `hermes.pyth.network/v2/price_feeds` (metadata/search) | **200 keyless** — all 12 bot assets found as `Crypto.<A>/USD` (12/12 incl. MINA, FLOW, PAXG); also surfaced `FundingRate.Binance.*` feed class |
| `hermes.pyth.network/v2/updates/price/latest` (real-time) | **401 Unauthorized** |
| `benchmarks.pyth.network/v1/shims/tradingview/history` (OHLC) | **404** (endpoint gone/moved) |
| `benchmarks.pyth.network/v1/updates/price/<ts>` (point-in-time) | **401 Unauthorized** |

So the free surface = feed METADATA only. Every price — real-time,
historical, funding-rate — sits behind a "Pyth Pro" access token
(pyth.network/pricing). The org's `pyth-plugin` repo (a Cursor plugin
fronting `mcp.pyth.network/mcp`) documents `get_historical_price` /
`get_candlestick_data` as "No auth", but its backing REST answers 401/404 —
the README row is stale or the MCP proxies with its own gating; UNVERIFIED
either way (an MCP handshake was not attempted) and not to be cited as
access.

## Context that stays true

- Fence analysis unchanged: Pyth would be read-only data (venue-legal);
  display = SAFE; model input = freeze-gated. Moot while priced.
- The bot already has free price surfaces: Kraken public API (execution
  venue truth), OKX/Binance.US read-only feeds, coinpaprika MCP.
- Clone parked at `Documents\liquiditybot\pyth-plugin` (pyth-client-py
  v0.2.2, py>=3.9, hermes.py is a thin client for the now-gated service) —
  safe to delete; nothing depends on it.
- Re-derive before citing: pricing/gating is vendor-mutable; the 401s above
  are as-of the stamp, and a future free tier would need a fresh probe, not
  this page.
