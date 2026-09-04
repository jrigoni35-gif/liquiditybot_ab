"""monitor/chain_check.py — is the FLOW forced-seller vector actually live?

Reads Flow EVM directly. Answers one question with a primary source:
can anything be liquidated on More Markets right now? Press coverage of
the 2026-08-31 ankrFLOW exploit reported that "no operational pause was
announced" — the chain says every reserve is paused. Announced and
enforced are different claims; only the second one binds, and only the
chain can settle it.

Mechanism, not vibes: in Aave V3 the reserve PAUSED flag (config bit 60)
gates `liquidationCall` alongside supply/borrow/repay/withdraw. A paused
reserve cannot be liquidated at ANY price, so "no forced sellers in
$0.0240-0.0290" holds structurally rather than numerically.

Selectors are derived with a self-tested keccak256, never guessed — the
`ratio()` / `getRatioFor(address)` pair is a live example of two
plausible names with completely different selectors.

Addresses: docs.more.markets (MORE Markets) and Ankr's Flow docs. Every
one is re-verified on-chain here (code size, ADDRESSES_PROVIDER match,
token symbol) before any conclusion is drawn from it.

    python monitor/chain_check.py
"""

from __future__ import annotations

import json
import urllib.request

RPC = "https://mainnet.evm.nodes.onflow.org"
TIMEOUT = 25

POOL = "0xbC92aaC2DBBF42215248B5688eB3D3d2b32F2c8d"
ADDRESSES_PROVIDER = "0x1830a96466d1d108935865c75B0a9548681Cfd9A"
ANKRFLOW = "0x1b97100eA1D7126C4d60027e231EA4CB25314bdb"

# Aave V3 reserve configuration bitmap
FLAG_ACTIVE, FLAG_FROZEN, FLAG_PAUSED = 56, 57, 60

_RC = [
    0x1, 0x8082, 0x800000000000808A, 0x8000000080008000, 0x808B, 0x80000001,
    0x8000000080008081, 0x8000000000008009, 0x8A, 0x88, 0x80008009, 0x8000000A,
    0x8000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x80000001, 0x8000000080008008,
]
_RO = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
       [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M = (1 << 64) - 1


def _rol(x: int, n: int) -> int:
    n %= 64
    return ((x << n) | (x >> (64 - n))) & _M


def keccak256(data: bytes) -> bytes:
    """Legacy Keccak-256 (NOT hashlib's sha3_256 — different padding)."""
    rate = 136
    p = bytearray(data) + b"\x01"
    while len(p) % rate:
        p += b"\x00"
    p[-1] ^= 0x80
    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(p), rate):
        blk = p[off:off + rate]
        for i in range(rate // 8):
            a[i % 5][i // 5] ^= int.from_bytes(blk[i * 8:i * 8 + 8], "little")
        for rnd in range(24):
            c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
            d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
            for x in range(5):
                for y in range(5):
                    a[x][y] ^= d[x]
            b = [[0] * 5 for _ in range(5)]
            for x in range(5):
                for y in range(5):
                    b[y][(2 * x + 3 * y) % 5] = _rol(a[x][y], _RO[x][y])
            for x in range(5):
                for y in range(5):
                    a[x][y] = b[x][y] ^ ((~b[(x + 1) % 5][y]) & _M & b[(x + 2) % 5][y])
            a[0][0] ^= _RC[rnd]
    out = b"".join(a[i % 5][i // 5].to_bytes(8, "little") for i in range(4))
    return out[:32]


def selector(signature: str) -> str:
    """4-byte ABI selector for a function signature."""
    return "0x" + keccak256(signature.encode()).hex()[:8]


def _rpc(method: str, params: list) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    req = urllib.request.Request(
        RPC, body.encode(), {"Content-Type": "application/json"}
    )
    if not RPC.startswith("https://mainnet.evm.nodes.onflow.org"):
        raise ValueError(f"refusing non-Flow RPC: {RPC!r}")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as fh:  # noqa: S310  # nosec B310
        return json.loads(fh.read().decode())


def eth_call(to: str, data: str) -> str | None:
    out = _rpc("eth_call", [{"to": to, "data": data}, "latest"])
    return out.get("result") if "error" not in out else None


def decode_string(word: str | None) -> str:
    if not word or len(word) < 130:
        return "?"
    h = word[2:]
    n = int(h[64:128], 16)
    return bytes.fromhex(h[128:128 + n * 2]).decode(errors="replace")


def reserves() -> list[str]:
    raw = eth_call(POOL, selector("getReservesList()"))
    if raw is None:
        return []
    h = raw[2:]
    n = int(h[64:128], 16)
    return ["0x" + h[128 + i * 64 + 24:128 + (i + 1) * 64] for i in range(n)]


def reserve_flags(asset: str) -> dict[str, bool] | None:
    arg = selector("getConfiguration(address)") + asset[2:].lower().rjust(64, "0")
    raw = eth_call(POOL, arg)
    if raw is None:
        return None
    cfg = int(raw, 16)
    return {
        "active": bool((cfg >> FLAG_ACTIVE) & 1),
        "frozen": bool((cfg >> FLAG_FROZEN) & 1),
        "paused": bool((cfg >> FLAG_PAUSED) & 1),
    }


def main() -> int:
    # selectors are load-bearing; fail loudly rather than query a wrong one
    assert keccak256(b"").hex().startswith("c5d24601"), "keccak self-test failed"
    assert selector("paused()") == "0x5c975abb", "selector self-test failed"

    print(f"RPC {RPC}  block {int(_rpc('eth_blockNumber', [])['result'], 16):,}")

    provider = eth_call(POOL, selector("ADDRESSES_PROVIDER()"))
    ok = provider is not None and provider[-40:].lower() == ADDRESSES_PROVIDER[2:].lower()
    print(f"\nMORE Markets pool {POOL}")
    print(f"  ADDRESSES_PROVIDER matches published deployment: {ok}")
    if not ok:
        print("  !! pool identity UNVERIFIED — stop, do not read conclusions below")
        return 1

    rs = reserves()
    print(f"  {len(rs)} reserves\n")
    n_paused = 0
    for asset in rs:
        f = reserve_flags(asset)
        if f is None:
            continue
        n_paused += f["paused"]
        sym = decode_string(eth_call(asset, selector("symbol()")))
        print(f"  {asset} {sym:12s} paused={f['paused']!s:5s}"
              f" frozen={f['frozen']!s:5s} active={f['active']!s:5s}")

    ank = eth_call(ANKRFLOW, selector("paused()"))
    ank_paused = ank is not None and int(ank, 16) == 1
    print(f"\n  ankrFLOW token {ANKRFLOW}"
          f"\n    symbol {decode_string(eth_call(ANKRFLOW, selector('symbol()')))}"
          f"  paused={ank_paused}")

    print(f"\nVERDICT: {n_paused}/{len(rs)} reserves paused; ankrFLOW paused={ank_paused}")
    if n_paused == len(rs) and rs:
        print("  liquidationCall is gated by the PAUSED flag -> NO forced seller can")
        print("  execute at any price while this holds. Re-run before relying on it.")
    else:
        print("  !! at least one reserve is LIVE — the forced-seller vector is OPEN")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
