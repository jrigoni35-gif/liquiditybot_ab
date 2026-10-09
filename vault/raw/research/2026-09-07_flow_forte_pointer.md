---
title: Flow "Forte" network upgrade — operator-flagged reference (2026-09-07)
type: raw/research pointer
status: FILED ON OPERATOR DIRECTIVE, verbatim: "Stop and include this no matter what" (2026-09-07)
source: https://developers.flow.com/blockchain-development-tutorials/forte  (fetched 2026-09-07, [K])
secondary: https://flow.com/forte  (fetched 2026-09-07, [K])
---

# Flow "Forte" — what the pages say (fetched 2026-09-07)

**Operator directive, verbatim:** *"Stop and include this no matter what."*
Filed as given. Nothing below is an assessment of relevance; the assessment
was stopped on the directive. The bot's execution venue is unchanged
(CLAUDE.md hard invariant 3 — Kraken sole venue); this page is a reference,
not a change.

## Tutorials hub (developers.flow.com/blockchain-development-tutorials/forte)

Forte = Flow network upgrade; "Now Live On Flow" per flow.com/forte (no
dates on either page). Three feature sets named on the hub:

1. **"Flow Actions"** — standardized interfaces for composable DeFi
   workflows. Connectors named on the page: swap-protocol connectors,
   **`ERC4626SinkConnectors`**, **`IncrementFiPoolLiquidityConnectors`**
   (liquidity provision), **`IncrementFiFlashloanConnectors`** (flash loans).
   Sub-pages: `/forte/flow-actions`, `/forte/flow-actions/intro-to-flow-actions`.
2. **"Scheduled Transactions"** — "the first of its kind, fully native
   onchain time scheduler": time-based smart-contract execution, cron-like
   automation, "DeFi rebalancing without external keepers". Sub-pages:
   `/forte/scheduled-transactions`,
   `/forte/scheduled-transactions/scheduled-transactions-introduction`.
3. **"Enhanced Composability"** — patterns for interconnected applications.

Also listed: **Passkeys** (WebAuthn device-backed auth) and
**High-Precision Fixed-Point Math** — `Fix128` / `UFix128`, UInt128-based
24-decimal arithmetic for DeFi (`/forte/fixed-point-128-bit-math`).

## flow.com/forte — the announcement's three pillars

- Developer experience: Scheduled Transactions; WebAuthn/passkeys;
  "AI-friendly Cadence error messages".
- Consumer adoption: "sub-cent transaction fee and native gas-less
  feature"; state optimisation cutting execution cost 6–18% via key
  de-duplication ("eliminating 53% of duplicate keys").
- Protocol robustness: integrity verification on inter-node messages;
  account-key de-duplication shrinking state ~6% (~21 GB); BadgerDB →
  PebbleDB (claimed up to 80% memory / 60% CPU improvement); near-real-time
  results from Access Nodes on pre-finalisation data.

## Operator-supplied excerpt (pasted 2026-09-07, from the tutorial's preamble)

> This tutorial assumes you have a modest knowledge of Cadence. If you
> don't, you can follow along, but you'll get more out of it if you
> complete our Cadence tutorials. Most developers find it easier than other
> blockchain languages and it's not hard to pick up.

Prerequisite named by the source: **Cadence** (Flow's resource-oriented
smart-contract language). Cadence tutorials: developers.flow.com →
"Cadence" section (not fetched). Nothing in this repo is written in
Cadence; the bot is Python against Kraken's REST API.

## Operator-supplied excerpt 2 (pasted 2026-09-07, the Flow EVM guides hub)

> Essential setup guides for Flow EVM development, which includes MetaMask
> integration and wallet configuration. Learn how to connect popular
> Ethereum tools to Flow's EVM-compatible network and prepare your
> development environment to build on Flow.
>
> **Frameworks** — Modern JavaScript and React frameworks to build Flow EVM
> applications. These guides cover popular blockchain libraries like
> ethers.js, web3.js, wagmi, and RainbowKit. They provide practical
> implementation patterns for frontend development on Flow.
>
> **Development Tools** — Professional Solidity development tools adapted
> for Flow EVM. Master Foundry's testing suite, Hardhat's TypeScript
> environment, and Remix's browser-based IDE for comprehensive smart
> contract development workflows on Flow.
>
> **Build a Fully-Onchain Image Gallery** — Create a decentralized image
> gallery that stores images directly on the blockchain with Flow's
> efficient gas pricing. This comprehensive tutorial demonstrates how to
> build smart contracts for onchain image storage, implement factory
> patterns for user galleries, and create a modern React frontend with
> wallet integration. Learn how Flow's low gas costs allow applications
> that would be prohibitively expensive on other chains.
>
> **Conclusion** — These EVM guides provide comprehensive coverage of the
> most popular Ethereum development tools and frameworks, adapted for Flow
> EVM development. Whether you want to migrate Ethereum applications or
> build new projects, these tutorials offer practical implementation
> patterns for wallet integration, contract deployment, and blockchain
> interaction on Flow's high-performance EVM-compatible network.

Two development surfaces named by the source, then: **Cadence** (native
Flow, the Forte Actions / Scheduled Transactions tutorials) and **Flow
EVM** (Solidity via Foundry / Hardhat / Remix; ethers.js / web3.js / wagmi /
RainbowKit; MetaMask). The EVM route means existing Ethereum tooling and
contracts run on Flow; the Cadence route is where the Forte-native
scheduling and Actions connectors live.

## Operator-supplied link 3 (pasted 2026-09-07): https://linktr.ee/flowonchain — fetched 2026-09-07 [K]

Page text, verbatim: **"The Home of Consumer DeFi"** — Flow "the
purpose-built L1 network for consumer DeFi with 1.1 Million monthly active
users and nearly 1 billion transactions." Account joined Linktree November
2025.

Links listed, in page order:
1. **Flow.com** → https://flow.com/
2. **Earn with Peak Money** → https://peak.money
3. **Liquidity on Flow** → http://liquidity.flow.com
4. **Flow Bridge** → https://bridge.flow.com
5. **Swap** → http://swap.flow.com
6. **Dune Dashboard** → https://dune.com/flow/overview

Socials: X, Telegram, Discord, YouTube, email. None of the six destinations
was fetched; the titles are the page's own. Items 3 and 5 (liquidity
provision, swap) are the surfaces the Forte "Flow Actions" connectors above
target; item 6 is an on-chain activity dashboard (Dune) — the kind of
source a volume/fee-tier or wash-trading check would read.

## Link 3 destinations, accessed 2026-09-07 on operator instruction ("Access it") — all [K] as fetched, static HTML only

| destination | what came back |
|---|---|
| liquidity.flow.com | **JS shell** — title only: "Liquidity on Flow \| Maximize your crypto earnings". No pools, fees, APRs, protocol names in static HTML. |
| swap.flow.com | **JS shell** — the word "Swap". No DEX name, pairs, fee tiers, API in static HTML. |
| peak.money | **HTTP 403 Forbidden** to the fetcher. Nothing read. |
| bridge.flow.com | **JS shell** — title "Flow Bridge \| Bridge Assets to and from Flow"; nav to Flow Wallet, Explorer, Developers. No chains/assets/fees in static HTML. |
| dune.com/flow/overview | **Rendered.** "Flow Stablecoin Marketcap" **$72,510,195.43**; "90-Day Average Daily Active Wallets" **42,332**; "Total Weekly Transactions" **998,756**; "Transactions Per Second (TPS)" **1,247.152** (as labelled; a weekly-tx figure of ~1M implies ~1.65 sustained TPS, so this is a peak or a differently-defined figure — not reconciled); "Monthly Active Wallets" most recent **August 2026: 312,496**; "Total Value Locked (TVL)" **$12,683,891**; "$FLOW Total Supply" **1,686,989,901.34**. Dashboard's own description: measures "demand for Flow DeFi, growth of on chain liquidity, and real usage of consumer finance apps." |
| flow.com | **Rendered.** "the leading consumer network trusted by millions of users"; "the future of consumer defi". Products named: **Bridge** (stargate.finance; providers **LayerZero**, **LiFi**), **Swap** (swap.flow.com), **Flow Wallet**, **Flow Actions**, **Flow VRF**, **Scheduled Transactions**, **Flow Credit Market** ("home equity lending"; "$600,000 available credit line" example). DEX: **Uniswap** partnership mentioned. Stablecoins "all-time high of **$74.6M**" (June 2026). "1 billionth transaction" milestone. Example trader-profile widget: "24% ROI", "68% win rate", "3,421 followers". Socials: X 200.4K, Discord 20.8K, GitHub 649. Dev docs: developers.flow.com. |

**Two-source discrepancy, recorded not resolved:** the Linktree says "1.1
Million monthly active users"; the Dune dashboard's own "Monthly Active
Wallets" for August 2026 reads 312,496, and 90-day average daily active
wallets 42,332. Different definitions (users vs wallets; which month) may
account for it; neither source defines its term on the page. TVL
$12.7M and stablecoin cap $72.5M are the liquidity-scale numbers a
provision strategy would be sized against — both [K] from Dune, as-of
2026-09-07.

## Behind the shells — the two developer pages, fetched 2026-09-07 [K]

**Flow Actions intro** (`/forte/flow-actions/intro-to-flow-actions`). Five
primitives, quoted: **Source** "Provides tokens on demand (withdraw from
vault, claim rewards, pull liquidity)"; **Sink** "Accepts tokens up to
capacity (deposit to vault, repay loan, add liquidity)"; **Swapper**
"Exchanges one token type for another (targeted DEX trades, multi-protocol
aggregated swaps)"; **PriceOracle** "Provides price data for assets";
**Flasher** "Provides flash loans with atomic repayment (arbitrage,
liquidations)". Named connectors: `FungibleTokenConnectors` (`VaultSource`,
`VaultSink`), `IncrementFiSwapConnectors` (wraps the **IncrementFi** DEX),
`IncrementFiFlashloanConnectors`, `BandOracleConnectors` (**Band Protocol**
oracle; "requires payment sourced from a token Source"). Composition:
"Withdraw from Source → Swap with Swapper → Deposit into Sink" in ONE
transaction, correlated by a `UniqueIdentifier`; **atomic** — "All
operations complete or fail together". Swappers quote both ways
(`quoteIn()` / `quoteOut()`); flash-loan fee via
`calculateFee(loanAmount: UFix64)`. Access: Sources need
`auth(FungibleToken.Withdraw)` capabilities, Sinks public receiver
capabilities; **no restriction on caller type** (bots/keepers/users) is
stated. So the DEX behind swap.flow.com's shell is, per this page,
**IncrementFi** (Uniswap is named on flow.com as a partnership; not named
here).

**Scheduled Transactions intro**
(`/forte/scheduled-transactions/scheduled-transactions-introduction`).
"Scheduled Transactions let smart contracts execute code at, or after, a
chosen time without an external transaction." Interface:
`FlowTransactionScheduler.TransactionHandler` with
`executeTransaction(id: UInt64, data: AnyStruct?)` under the
`FlowTransactionScheduler.Execute` entitlement; wrapper
`FlowTransactionSchedulerUtils.Manager` (`schedule()`,
`scheduleByHandler()`, cancellation referenced). Priority enum
`FlowTransactionScheduler.Priority` = High / Medium / Low. Fee:
`calculateFee(executionEffort: UInt64, priority: Priority, dataSizeMB:
UInt64)` in FLOW, paid from a `@FlowToken.Vault` at scheduling time. Timing:
absolute `timestamp: UFix64` (`getCurrentBlock().timestamp + delaySeconds`);
**"at, or after"** — no execution window, max delay, effort ceiling, retry
or failure semantics documented on this page. A time-scheduled on-chain
rebalancer is therefore possible in principle; its timing guarantee is
unspecified in the source read.

## Where it touches this project (pointer only — NOT assessed)

- FLOW/USD was in the bot's Kraken universe until cut #11 (2026-09-07)
  removed all alts; `data/` references to "flow" are the Kraken pair and
  order-flow variables, not the chain (grep 2026-09-07: 26 hits, 6 files).
- The conversation that produced this pointer had just named
  [[concepts/treynor-black-alpha-isolation]] §6 route 3 — *structural edge
  instead of statistical edge* (spread capture, liquidity provision,
  rebates). On-chain liquidity connectors and native scheduling are the
  kind of surface that route names. Whether any of it is usable is an
  OPERATOR adjudication under invariant 3, never a session decision.
- Related, already filed: the wash-trading-on-AMMs paper (Gan, Wang, Xue,
  Lin, ACM TOIT 2024, 10.1145/3689631) — AMM liquidity provision is also
  where that paper's five payoff channels live.
