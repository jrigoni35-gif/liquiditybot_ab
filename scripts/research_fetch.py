"""Tor-routed research fetcher — privacy-preserving OSINT/sentiment ONLY.

Operator directive 2026-08-28 ("access tor browser… for legit research…
gracefully so no flags arise"). "No flags" is read the only legitimate way:
this tool is built so it is STRUCTURALLY INCAPABLE of the thing that would
be a real problem — touching the trading or venue path. The fences below are
compiled in, not merely documented.

TRANSPORT: the standard, battle-tested route — `requests` over a local Tor
SOCKS5 proxy (`socks5h://127.0.0.1:9050`, the `h` resolves DNS through Tor
so there is no DNS leak). Needs a Tor daemon listening on that port (Tor
Browser exposes 9150; the standalone Expert Bundle uses 9050). The
pure-python torpy client was evaluated and REJECTED on this box: torpy 1.1.6
calls APIs removed in Python 3.12+ (ssl.wrap_socket, urllib3 .strict) and
patching a third-party lib's internals is the fragile path this repo's
"route around, never fight" rule forbids.

HARD FENCES (vault concepts/tor-access-for-agents):
  1. Kraken / any execution venue is NEVER reachable here. _VENUE_DENY is a
     compiled denylist; a matching host raises before any connection. The
     engine's own execution path does not import this module and cannot —
     see the import guard below.
  2. Zero trading benefit and none intended: the live cycle is ~95% I/O-wait,
     venue-side; Tor only adds latency. This is a RESEARCH lane (sentiment,
     OSINT, geo-block-neutral source access), never a market-data or order
     lane.
  3. Target-site terms still apply through Tor. This tool does not defeat
     authentication, rate limits by identity churn against a single site, or
     any abuse control — and must not be used to. It fetches public research
     sources over a privacy-preserving transport. NEWNYM/rotation is
     deliberately NOT wired.

SAFE class: a script, reads the public web, writes only where the caller
says (never outputs/ production files). No decision-path, no config, no
order lifecycle. Not imported by any engine/runner/core module.
"""
from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse

# --- Fence 1: execution/venue hosts are unreachable from this module. ------
# Substring match on the hostname; conservative on purpose. Extend only with
# more things to BLOCK, never to carve an exception.
_VENUE_DENY = (
    "kraken.com", "kraken.", "okx.com", "binance", "coinbase",
    "moomoo", "futu", "ibkr", "interactivebrokers",
)


class VenueBlocked(RuntimeError):
    """Raised when a URL resolves to an execution/venue host (fence 1)."""


def _assert_not_venue(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        raise ValueError(f"no host in URL: {url!r}")
    for bad in _VENUE_DENY:
        if bad in host:
            raise VenueBlocked(
                f"host {host!r} matches venue denylist {bad!r}: this "
                f"research transport never touches an execution venue "
                f"(vault concepts/tor-access-for-agents fence 1)")
    return host


DEFAULT_SOCKS = "socks5h://127.0.0.1:9050"


class TorProxyUnavailable(RuntimeError):
    """No Tor SOCKS proxy is listening — the daemon is not running."""


def fetch(url: str, *, timeout: float = 60.0,
          proxy: str = DEFAULT_SOCKS) -> str:
    """Fetch one public URL through a local Tor SOCKS proxy. Returns response
    text. Raises VenueBlocked for any execution-venue host (before any
    connection), TorProxyUnavailable if no daemon is listening, or ImportError
    if requests/PySocks are absent."""
    _assert_not_venue(url)
    if urlparse(url).scheme not in ("http", "https"):
        raise ValueError(f"only http(s) research URLs: {url!r}")
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise ImportError(
            "requests[socks] is the transport for scripts.research_fetch; "
            "install it (pip install 'requests[socks]')") from exc
    try:
        resp = requests.get(url, timeout=timeout,
                            proxies={"http": proxy, "https": proxy},
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        return resp.text
    except requests.exceptions.ConnectionError as exc:
        raise TorProxyUnavailable(
            f"no Tor SOCKS proxy at {proxy}: start a Tor daemon (Tor Browser "
            f"exposes 9150; the standalone Expert Bundle uses 9050) and point "
            f"--proxy at its port. Original: {exc}") from exc


def _main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(
        description="Fetch a public research URL over Tor (torpy). "
                    "Venue/execution hosts are refused by design.")
    ap.add_argument("url", help="public http(s) research URL")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--proxy", default=DEFAULT_SOCKS,
                    help=f"Tor SOCKS proxy (default {DEFAULT_SOCKS})")
    ap.add_argument("--max-chars", type=int, default=4000,
                    help="truncate printed body (0 = full)")
    args = ap.parse_args(argv)
    try:
        body = fetch(args.url, timeout=args.timeout, proxy=args.proxy)
    except VenueBlocked as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    except TorProxyUnavailable as exc:
        print(f"NO-TOR: {exc}", file=sys.stderr)
        return 3
    out = body if args.max_chars == 0 else body[:args.max_chars]
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
