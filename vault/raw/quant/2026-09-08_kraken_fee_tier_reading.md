---
title: Operator's Kraken-app fee-tier reading — 2026-09-08 17:51 (device local time)
type: raw/quant — primary artifact
image: raw/quant/2026-09-08_kraken_fee_tier_screenshot.png  (operator-supplied, filed verbatim)
supplied by: operator, in chat, in reply to the FEE-4 request
---

# What the app shows (transcribed from the screenshot, [K])

- **Your fee tier: Tier 5**
- **Your 30-day spot volume: 69,652.65 USD** · 30-day futures volume: 0.00 USD
- **Your assets on platform (AoP): 822.24 USD**
- "Generate **30,348.35 USD** (equivalent) more spot volume or generate
  40,000,001.00 USD more futures volume or increase assets on platform by
  **199,178.76 USD** to reach the next tier and reduce your fees further."
- Ladder shown (maker / taker / min spot volume / or min futures volume / or
  AoP, AoP column partly cut off at the right edge):
  0.40/0.80 — · 0.30/0.60 2,501 (fut 5,000,001) · 0.22/0.38 10,001
  (10,000,001; AoP "20…") · 0.20/0.35 25,001 (15,000,001; "50…") ·
  **0.15/0.30 50,001 (25,000,001; "10…") ← highlighted, the account's row** ·
  0.12/0.25 100,001 (40,000,001; "20…") · 0.10/0.22 250,001 · 0.08/0.20
  500,001 · 0.06/0.18 1,000,001 · 0.04/0.15 2,500,001 · 0.02/0.12 5,000,001 ·
  0.00/0.10 10,000,001 (300,000,001).

# Reproduction against `core/venue_fees.py` (2026-09-08T22:52Z)

- `binding_row(69652.65, aop_usd=822.24)` → **(15.0, 30.0)** = Tier 5. ✔
- Next tier by volume: 100,001 − 69,652.65 = **30,348.35** — the app's figure
  to the cent. ✔  Next tier by AoP: 200,001 − 822.24 = **199,178.76** — the
  app's figure to the cent, so the table's Tier-6 AoP threshold (200k) is
  confirmed by a third route. ✔
- `scripts/fee_drift_report.py --volume-30d 69652.65`: *config books 20/35
  but the binding tier is 15/30 — **OVER-stating the round trip by 10 bps
  (22.2%)**.* Live page AGREES with the reference table.

# What this settles, and what it moves

- The ladder filed this morning is the account's ladder — three routes now
  (page raw text, 08-29 screenshot, 09-08 screenshot), and the AoP column is
  confirmed numerically.
- **The account is Tier 5, not Tier 3.** The 30-day spot volume has risen
  from $17,482 (08-29) to $69,652 (09-08): the tier is ROLLING and driven by
  the operator's real trading, not by the bot (the sim's fills count toward
  nothing — [[concepts/paper-real-boundary]]).
- So the booked 20/35 (cut #10) now **over-states** cost by 10 bps per round
  trip ($0.06 on a $60 ticket) rather than under-stating it as this
  morning's record assumed from the 08-29 volume. The era-8 readout is
  CONSERVATIVE, not optimistic. Direction corrected on HANDOFF and in
  `docs/quant/2026-09-08_fee_ladder_correction.md` the same session.
- FEE-4's inputs are now supplied. Re-booking to 15/30 is cohort-resetting
  (operator adjudication). A rolling tier argues for booking the row at each
  boundary from a fresh reading, never chasing it mid-era.
