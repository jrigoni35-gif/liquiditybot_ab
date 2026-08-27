# THALES vs. freqtrade / Hummingbot — footprint reference

> **Registry (2026-08-27):** each footprint here has a governed entry in
> `docs/thales/REGISTRY.md` (contract: `docs/thales/README.md`).

What predictable behaviours the two most-deployed open-source retail
bots leave in **public market data** when run on or near their
documented defaults, which THALES detector recognises each, and whether
that detector is calibrated to catch it. This is intelligence for
*anticipating* predictable order flow — never for inducing it. THALES's
hard boundary stands: detect-and-react only; it never places, spaces, or
times an order to trigger anyone else's stops (`strategies/thales.py`).

## Documented default footprints

**Hummingbot Pure Market Making** (v1 PMM, the most-copied config):

- `order_refresh_time` — the strategy cancels and replaces its resting
  orders every N seconds on a timer. Common template value **30s**. This
  is a *clock*, not event-driven flow: top-of-book gets replaced at a
  near-constant cadence with low interval variance.
- `bid_spread` / `ask_spread` — fixed, usually symmetric (template
  examples 0.5%–2%). Resting quotes sit at a constant offset from mid.
- `order_levels` — N orders per side at evenly-spaced `order_level_spread`
  increments, often uniform `order_amount`. An N>1 config paints an
  even, size-uniform ladder on both sides.

**freqtrade** (default/template strategy):

- `minimal_roi` — a time-since-**entry** exit ladder, e.g.
  `{"40":0.0,"30":0.01,"20":0.02,"0":0.04}`: take profit at 4%, decaying
  to break-even by 40 minutes held.
- `stoploss` — a single fixed percentage, template values **-0.5%** and
  **-3%** are common. Many bots on the same strategy → stop orders
  clustered a fixed % below entries, and at round numbers / recent swing
  extremes.
- `trailing_stop_positive` / `_offset` — trailing stop arms at a fixed
  profit offset.

Sources: Hummingbot PMM docs (order-refresh-time, order-levels,
strategy-configs); freqtrade stoploss & strategy-customization docs.

## Detector mapping and calibration check

| Framework footprint | THALES detector | Calibrated to catch it? |
| --- | --- | --- |
| Hummingbot `order_refresh_time` ~30s timer | **TH-011 metronome_mm** | **Yes.** Detector flags low coefficient-of-variation of top-of-book replacement intervals with a `min_interval_sec` floor of 8s — a 30s refresh sits comfortably above the floor and reads as near-zero CV (clock-quoting). |
| Hummingbot `order_levels` even ladder | **TH-010 grid_ladder** | **Yes.** Detector scores even spacing + size uniformity + level persistence (Jaccard) of resting levels. |
| freqtrade fixed `stoploss` clustering | **TH-013 stop_herding** | **Yes, and it is the one firing live** (see report below). Stops cluster at round numbers / swing extremes; detector scores proximity + sweep-and-revert. |
| freqtrade `minimal_roi` time-since-entry exits | **TH-012 clockwork_flow** — *partial* | **Gap, largely non-actionable.** clockwork_flow finds recurring time-**of-day** flow; `minimal_roi` fires N minutes after each trade's *own* entry, which is not observable from public data without tracking a counterparty's entry timestamps. Left uncovered on purpose rather than faked. |

## What the live shadow run actually shows

`scripts/thales_report.py` against the current session: of the four
footprints, **only TH-013 stop_herding is present** on Kraken BTC/ETH
(100% of THALES advice events; grid and metronome ~0). The venue's major
books are not dominated by default-config retail MM/grid bots, so the
Hummingbot-targeting detectors correctly stay quiet — that is calibration
working, not calibration missing. The freqtrade-style stop-cluster
footprint is real and recurring, and THALES is shading *down* to avoid
being the lemming caught in the cascade.

## Why no thresholds were retuned

The detectors already admit the documented framework defaults (table
above), so tuning them to the current tape would be fitting to noise —
exactly the overfit sin `CLAUDE.md` forbids. Promotion `shadow -> advise`
is gated on **counterfactual evidence joined to trade outcomes**, not on
firing frequency. TH-013 has now cleared the frequency bar; the honest
next step is a shadow-vs-advise A/B on that single detector once enough
labeled trades accrue — driven by evidence, decided by a human.
