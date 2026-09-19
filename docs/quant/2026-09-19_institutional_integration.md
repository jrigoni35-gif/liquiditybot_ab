# Institutional integration — the desk's back office, sewn into the bot (2026-09-19, design; SAFE-plane)

**Point of view.** Era-9's numbers say this bot is a dealing desk with
traders and no back office. The organs already exist in-tree — an
Avellaneda-Stoikov engine with a structural fee floor
(`execution/market_maker.py` rev 2.0), an inventory discipline module
(`execution/inventory.py`: count caps, soft/hard caps, stale-inventory
purge), a beta-weighted hedger (`execution/hedging.py`), a markout tracker
(`execution/markout.py:76`), and a hash-chained decision ledger. What
institutions add around exactly these organs is *accounting*: every
decision captured with its decision price, every dollar of shortfall
decomposed and attributed, inventory guided by skew rather than only
capped, and a judge that reads ledgers instead of vibes. This design sews
that accounting into the bot's real seams. Everything here is
measurement-plane; anything that would move an order is named and fenced
as cohort-resetting.

## Seam 1 — Decision event capture (OMS-grade prerequisite)

**Institutional analogue:** the order-event store feeding TCA. Perold's
implementation shortfall needs a timestamped *decision price* per decision;
Quod's "three-system problem" (context lost between OMS/EMS/TCA) is
literally our gap.

**Today's hole, measured:** the entry sweep (audit `src:"entry_sweep"`,
main.py:1940) emits only the cumulative EN-000 vector; the 6,643 era-9
EN-030 skips have no per-decision record, and CV-010/030 evals carry no
price. 82.6% of era-9's decision population is ungradeable — delay cost
and opportunity cost are uncomputable for it.

**Design:** one audit record per sweep arrival —
`DE-010 decision_event {asset, ts, decision_mid, gates_digest}` — pure
logging beside the existing vector (SAFE; new registered code in
core/codes.py per invariant 6). No gate behavior changes; the record is
what the sweep already computed.

## Seam 2 — The implementation-shortfall ledger (TCA desk)

**Institutional analogue:** post-trade TCA with IS decomposition
(explicit / execution / delay / missed-opportunity).

**Design:** `scripts/is_ledger.py` — for every decision event: explicit =
`fees_delta_usd` (fills ledger); execution = `slip_bps` + MarkoutTracker
curves; delay = decision_mid → arrival → fill distance (the −15.1 bps
measured 09-01 is this leg's first reading); opportunity = the oracle
grader (`outputs/reports/oracle_regret_2026-09-19.py` promoted from
scratch) over unfilled/refused events. Output: per-era IS table cut by
asset × lane (probe/conviction) × regime — the leak ranking that tells
edge-hunting WHERE to hunt. Era-9's headline, already measured:
opportunity cost (87% PT-first in expired orders) > delay > explicit.
SAFE: reads ledgers and corpus, writes reports.

## Seam 3 — Shadow inventory governor (dealer skew, watch-lane pattern)

**Institutional analogue:** production "deformed A–S" — reservation-price
skew with hard bounds and a fee-adjusted spread floor.

**Today's tension, named not assumed:** `execution/inventory.py` runs a
*count/cap* philosophy; `market_maker.py` runs a *continuous-skew*
philosophy. Both are inventory control; nobody has measured which era-9
decisions they would have disagreed on.

**Design:** per decision event, compute the A–S reservation skew the
book's current inventory implies (parameters from measured vol/arrival,
fee floor already in-market_maker) and log `SG-010 shadow_governor
{asset, ts, skew_bps, sizer_action, skew_would}` — divergence only, never
input. This is the sanctioned watch-lane discipline (`core/watch_lane.py`:
shadow, mutation-pinned leaks, never feeds decisioning) applied to
inventory. The judge's "beneficial for inventory" criterion becomes a
number: a position is beneficial if it moves the book toward the
skew-target at a fee-covered spread. Any LIVE skew to sizing is
cohort-resetting — boundary docket.

## Seam 4 — Attribution and the central-risk-book view (profit pooling)

**Institutional analogue:** desk-level P&L attribution (Brinson
generalized) + internalization arithmetic.

**Blocking dependency, measured:** fills.csv has a `book` column since
09-05 that the writer never populates (`core/fill_ledger.py:239-249`) —
the SAFE half of the long-book docket row. Attribution across the three
desks (5m book / long book / hedger) is impossible until it lands; this
design makes that SAFE fix doubly demanded, pre-boundary eligible.

**Design:** `scripts/attribution.py` — net, fees, and heat-hours by
asset × book × lane; oracle-vs-held inventory mix (era-9: oracle drops
PAXG 11→1, LINK best-held at 78% PT-first with fewest entries); and the
netting report — the hedger burned $313.51 = 80.5% of lifetime fees
(edge-hunter 09-01); a central-risk-book pass prices what internal netting
across the three desks would have saved on our own ledger.

## Seam 5 — The judge reads ledgers (institutional memory)

The judge committee (`2026-09-19_institutional_judge_prep.md`, TradingAgents
PM/risk-committee shell) gets hard inputs: the IS ledger (Seam 2), the
shadow-governor divergence log (Seam 3), the attribution table (Seam 4),
the era readout. Verdicts stay structured (Materiality × Confidence ×
affected pool × action-class SAFE/boundary/refuse); decision records are
the memory. The judge never recommends from narrative — every claim cites
a ledger row it can be refuted against (the existing claim_check/mutation
discipline, promoted).

## Edge-hunting loop (how desks actually hunt)

IS leak ranking → hypothesis → corpus replay (the 1m swing-anatomy surface:
taker-buy imbalance, path shape) → SHADOW feature behind pre-registered
promotion criteria (the `ofi_event`/`basis_mom` pattern in config already
does exactly this) → measurement at the registered read points → boundary
docket. Nothing enters decisioning without the chain.

## Fences (don't cheat)

- No live skew, lane-mode, EV-multiple, bracket-geometry, or universe
  change: all cohort-resetting, all boundary-only.
- Oracle/IS numbers are direction, never capturable targets: they ignore
  the 79% non-fill rate and the trail overlay (09-16 audit: the give-back
  ratchet cannot pay a label-PT win).
- Every new instrument ships with a negative arm or self-test where it
  judges (instrument_contract C2), and EN-030-style aggregate-only
  shortcuts are the exact failure Seam 1 exists to end.

## Land order (all SAFE until marked)

1. `book` stamp on fills (SAFE half of long-book docket row) — unblocks 4.
2. DE-010 decision events (Seam 1) — unblocks 2's delay/opportunity legs.
3. `is_ledger.py` + `attribution.py` (Seams 2, 4) — report-plane.
4. SG-010 shadow governor (Seam 3) — shadow-only.
5. Judge committee over the four ledgers (Seam 5) — advisory.
→ Boundary-gated: anything the ledgers argue INTO decisioning.
