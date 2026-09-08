# Provenance

- Source: https://github.com/agiprolabs/claude-trading-skills (MIT, see LICENSE.md)
- Path in source: `skills/market-microstructure`
- Commit: 981e1d736cdc02bdc1c55c74ec9224e956414706 (2026-09-02)
- Installed: 2026-09-08, vendored unmodified. Scripts need `httpx` for live
  fetches (not added to repo requirements); `--demo` runs offline.

## Review performed before install

- SKILL.md and all three references read in full: methodology only, no
  embedded instructions, no credential requests.
- Scripts import only the Python standard library. Network hosts:
  `public-api.birdeye.so` (needs `BIRDEYE_API_KEY`, optional) and
  `api.dexscreener.com`. Both fall back to `--demo` synthetic data.
- Nothing here touches execution. Read-only analysis; CLAUDE.md invariants
  (Kraken sole venue, no withdrawals) are unaffected.

## Fit for this repo

The skill is written for Solana DEX trade tapes (Birdeye/DexScreener/Helius).
Its data plumbing does not apply to Kraken or Flow. What transfers is the
method: trade classification, buy/sell pressure ratios, size-distribution
skew, volume acceleration, and the wash-trading screen (uniform clip sizes,
self-trading windows, volume/liquidity ratio, unique-trader ratio). The
Kraken-native equivalents used in this repo live in `monitor/pass2.py`
(position + book) and `monitor/chain_check.py` (Flow EVM pause state).
