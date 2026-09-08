---
name: flow-position-analysis
description: Kraken FLOW/USD margin position and market read using the repo's own instruments - carry clock (monitor/pass2.py), trade tape screens in the market-microstructure record shape (monitor/tape.py), order-book structure (monitor/book.py), Flow EVM pause tells (monitor/chain_check.py), and the Flow mainnet wallet scan (monitor/flow_transfers.py). Use for "update", "check the tape", "order book analysis", "wallet search", "is it manipulation", "where is my margin call", or any FLOW position question. Read-only; public endpoints; no keys.
---

# FLOW position analysis (Kraken + Flow chain)

This is the Kraken/Flow adapter for the vendored `market-microstructure`
skill. That skill's data plumbing is Solana DEX; its METHOD (trade
classification, buy/sell pressure, size skew, wash screens, momentum
score) runs here on Kraken's public tape via `monitor/tape.py`, which
emits records in the skill's shape. The order book and the on-chain
wallet scan are the two halves the DEX skill cannot supply.

## Standing rules (from CLAUDE.md, restated for this task)

- The instrument is the first suspect. A surprising number gets its
  instrument verified before it gets a theory. Corroborate with a second
  route (Kraken vs aggregate price; tape vs book; chain read vs Safe
  transaction service) before the word "signal".
- Never cite the liquiditybot's own numbers as market evidence unless
  independently corroborated.
- Exchange wallets on Flow have no labels. Say "exchange-pattern", never
  an exchange name, unless a second route names it.
- Kraken `b`/`s` is the TAKER side. `wallet` in tape records is a
  quantity fingerprint, not an account. Say so whenever it drives a
  conclusion.
- Do not compute or present a plan to move price with the operator's own
  orders. Buying to mark a position up is manipulation; the arithmetic
  showing it fails is fine, an execution plan is not.

## Instruments (all read-only, all pin their host)

| Question | Command | What to read |
|---|---|---|
| Position, call price, runway | `python monitor/pass2.py --units U --avg A --used-margin IM --equity E --equity-px P --carry C --as-of DATE` | SNAPSHOT vs LIVE; carry clock; call(t) slope. Second margin positions share the collateral: their IM makes every number optimistic until included. |
| Tape: pressure, clips, self-trade analogue, same-second crosses | `python monitor/tape.py --pair FLOWUSD --hours 24` | net taker USD, market share, repeated exact quantities, fingerprints on BOTH sides (AT-COST flag = volume with no P&L), buys+sells inside one second, hourly buckets, momentum inputs |
| Book: bands, walls, slippage, exit | `python monitor/book.py --pair FLOWUSD --watch-seconds 75 --exit-units U --avg A` | bracket walls and their distance, wall dynamics (new/pulled/grew/shrank), sell-vs-buy impact asymmetry, far-ask overhang, exit P&L at market |
| Chain: More Markets + ankrFLOW pause | `python monitor/chain_check.py` | 9/9 reserves PAUSED flag, ankrFLOW paused(). liquidationCall is gated by PAUSED. |
| Chain: wallet search | `python monitor/flow_transfers.py --hours 24 --min-flow 1000` (7d: `--hours 168 --min-flow 5000`) | hubs by unique counterparties, net in/out, balances, largest transfers, daily net into hubs |

Unpause tells that are not yet in `chain_check.py` (read them by hand
with `monitor.chain_check.selector` + an `eth_call`): Ankr Safe
`0x2a369e0a05F31Dff22d155aFDFeA8d2C96DB607D` `nonce()`; FlowStakingPool
proxy `0xFE8189A3016cb6A3668b8ccdAC520CE572D4287a` EIP-1967 impl slot;
ankrFLOW `ratio()` on `0x1b97100eA1D7126C4d60027e231EA4CB25314bdb`; WFLOW
`balanceOf(aWFLOW 0x02bf4bd075c1b7c8d85f54777eaaa3638135c059)`. Safe
history: `https://transaction.safe.flow.com/api/v1/safes/<EIP-55>/multisig-transactions/`.

## Procedure for an "update"

1. `pass2.py` with the latest screenshot figures. State which figures are
   SNAPSHOT and which are LIVE. Collateral in ETH/BTC moves the call price;
   read their 24h change.
2. `tape.py --hours 24` and `--hours 3`. Report net taker flow, the
   largest prints, any fingerprint on both sides, any same-second cross.
   A price move on tiny volume with net BUYING is a maker re-quote, not
   selling: say so.
3. `book.py --watch-seconds 75`. Report the bracket (bid wall / ask wall
   distance and size), whether it re-centred up or down, and the sell-side
   impact. Between price and the call price, list every real bid.
4. `chain_check.py` plus the unpause tells. Any change in nonce, impl, or
   ratio is a fact to report with its timestamp from the Safe service.
5. Corroborate the Kraken price against an aggregate feed before calling a
   move Kraken-specific.
6. Restate outstanding inputs the operator has not supplied (e.g. the
   second position's Details tab and the open Orders list).

## Reading rules that have already been bought

- A 24h volume figure that halves at a fixed time is a burst rolling out
  of the window, not a trade.
- "Support that is quoted" moves with the maker's reference; "support
  that is bid" absorbs prints. Only the second is proven.
- Doubles in the peer cohort mostly revert; the largest FLOW run since
  2024 was 2.26x. Take-profit orders above that are decoration.
- Sell impact exceeds buy impact on this book at every size; an exit
  estimate at market is the honest cushion number, not the mark.

## Outputs

Terminal tables, numbers out of prose, denominators stated. For a
document, `docs/quant/<date>_flow_position_<topic>.md` with the commands
run and their raw headline lines pasted, so the next session can re-run
the same instrument instead of trusting the summary.
