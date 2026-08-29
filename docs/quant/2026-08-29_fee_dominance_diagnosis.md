# Focused-fix DIAGNOSE — why the bot doesn't make money (the out-of-the-box root cause)

Operator invoked /focused-fix, target "out of the box complexity." Treated
"the bot makes money" as the broken feature. Phases 1-3 (scope/trace/
diagnose) below; Phase 4 is an **architecture escalation**, not a patch —
the fix is structural and adjudication-scale, so it is proposed, never
shipped here. SAFE class: pure measurement/diagnosis, no decision-path/
config/order-lifecycle change. Numbers fresh-derived 2026-08-29T05:5xZ from
`outputs/signal_history.csv` (n=19,151) + the code trace cited inline.

## Phase 1-2: SCOPE + TRACE — the economic model, as actually wired

- `execution/market_maker.py` holds an **Avellaneda-Stoikov two-sided quote
  engine** (the bot's namesake heritage), invariant `half_spread >=
  maker_fee + min_profit_bps`. It is instantiated (`main.py:795`).
- BUT it is **not run as a two-sided market maker.** The live entry path
  (`main.py:1479`) is `tactics.plan_entry(parent.direction, quote, ...)`
  then places ONE side (`main.py:1500`, `side=parent.side`). The model
  picks a **direction** first; the quoter only prices a single directional
  maker-limit. Exit is a bracket (stop/TP), with a maker-first profit-exit
  that the fee anatomy measured **mostly misses** (18/492 exits fill maker →
  taker escalation). The code says so itself at `main.py:2448`: "The 35-54bps
  that bled 8/8 live trades IS this exit leg."
- **So the bot is economically a DIRECTIONAL PREDICTOR, not a market maker.**

## Phase 3: DIAGNOSE — the root cause, confirmed by two routes

A directional predictor profits only if gross edge exceeds the round-trip
fee. A market maker profits without any directional edge, by earning a
spread wider than its fee. The bot is in the **worst** cell: it takes
directional risk (needs edge) AND pays the spread on exit (taker). Measured:

**Mode 1 — DIRECTIONAL (live):** needs gross > **120bps** taker round-trip
(true fees 40/80). Measured gross ≈ **0** (clustered t=0.51, indistinguishable
from zero — fee anatomy + era-8 replay, two routes). Models lose to the null
on OOF Brier (OF-1). **Fails by ~120bps.**

**Mode 2 — MARKET-MAKING (the quoter's native purpose, dormant):** needs
spread > **~82bps** maker round-trip (40+40+margin). Actual raw spreads on
the traded pairs (feature `spread_bps` = clip(raw,0,60)/10, decoded ×10;
0.7% clipped at the 60bps ceiling):

| pair | raw median spread | gap to 82bps MM floor |
|---|---|---|
| FLOW | 35.9 bps | −46 |
| MINA | 15.9 bps | −66 |
| ARB | 11.4 bps | −71 |
| ADA | 2.5 bps | −80 |
| SUI / LINK / LTC | ~2.3 bps | −80 |
| corpus median | 1.3 bps | −81 |

p99 = 41bps, still half the MM floor. **The widest pair clears less than
half the maker fee. Two-sided MM is NOT a fee escape on any pair the bot
trades — rewriting the quoter to run two-sided would not help.** (Caveat:
the 0.7% clipped tail >60bps is unknowable; it cannot rescue a median of
1.3bps.)

**Mode 3 — FEE TIER (the only lever that moves BOTH modes):** Kraken 40/80
is Tier-1 (<$50k 30-day volume). At $800 dry-run equity with $0 real venue
volume, a lower tier is **permanently unreachable**. Not a tunable.

### Root cause (one sentence)
**The bot is fee-dominated in every economic mode available to it at Kraken
Tier-1 fees, on liquid pairs, at this capital scale** — directional edge
(≈0) is below the 120bps taker floor, and spread (≤36bps) is below the 82bps
maker floor, and the fee tier that would move both is locked by volume the
system cannot generate. The "−1%/trip, every cohort, every era, COST_BOUND"
that every session has hit is **not a bug, a bad model, or a tuning miss —
it is the arithmetic signature of this cell.** It is the market being
boring and the fee schedule being real, exactly as the-method predicts.

## Phase 4: ESCALATION (not a patch) — the fix is architecture

Per focused-fix's 3-strike rule, this is an architectural condition, not a
bug collection. Every "fix" is structural and adjudication/operator-scale:

1. **Fee tier via real volume** — moves both modes, but requires real
   capital + turnover the $800 paper system cannot produce. A business
   decision, not code. The dominant lever, out of code's reach.
2. **Two-sided MM rewrite** — REFUTED as a fix by the spread table above.
   Do not build it for these pairs; it cannot clear the maker floor.
3. **Wider-spread / illiquid pairs** — the only place MM math could close,
   but even FLOW (36bps) is below 82bps; reaching >82bps means genuinely
   illiquid alts with heavy adverse-selection and inventory risk. Asset-
   discipline docket; needs a raw-spread census first (owed instrument —
   `spread_bps` is clipped at 60).
4. **Fewer, LARGER directional wins** — within the fences, the ONLY path to
   positive expectancy: pay one 120bps fee against a multi-hundred-bps move
   instead of churning small ones. This VALIDATES cut #8's direction (bar
   0.8335, probe-dominated book) and names **GB-1 + ALGO-5** (give-back arm
   above the fee floor; let winners run) as the only viable in-fence lever.
   Directional-edge improvement itself is frozen (model moratorium).
5. **Honest reframe** — at $800 + Tier-1 + liquid Kraken spot, the system is
   fee-dominated in every mode. Its deliverable at this scale is the
   MACHINERY and the LEARNING, not the P&L. That is not defeat; it is
   naming what the instrument is for.

## What this diagnosis could not see
- Raw spreads above 60bps (feature clip) — 0.7% tail, cannot move a 1.3bps
  median. A true raw-spread census from the book/fills is owed.
- Effective-n: spreads/returns overlap; the gross≈0 is pooled across ≥5
  eras (fee re-price is the era-invariant half). Directional conclusion is
  robust; exact magnitudes are not.
- Whether GB-1/ALGO-5's "larger wins" lever actually clears the floor in
  sim — that is the next measurement, and it is adjudication-gated to run
  against live geometry.
