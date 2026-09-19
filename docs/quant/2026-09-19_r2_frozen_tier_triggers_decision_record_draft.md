# R2 — Frozen tier 2–4 triggers: DECISION RECORD (draft for the 2026-09-22 boundary)

**Status:** DRAFT, awaiting operator ruling. Prepared 2026-09-19 by the
Kimi session. Nothing in this document is decided; it exists so the
operator's decision on 2026-09-22 is a ruling, not a research project.

## The change

`Position.tier_trigger_snapshots` freezes the effective trigger for each
not-yet-fired profit tier (2–4) at the moment the preceding tier fires,
so a post-fire vol spike can no longer retroactively move an open
position's remaining targets. Persisted via `core/persistence.py`;
legacy positions default to empty = live recompute, byte-identical to
today's behavior.

Held on `fix/decisioning-coupling-r123` @ `bc9e3856` since 2026-09-19.
R1 and R3 shipped to main on 2026-09-19 (`f3b5f9e1`); R2 was split out
precisely because it is the one of the three that touches when exits
fire.

## Why it is not exempt

The moratorium allows exactly two boundary-breakers: a **safety
invariant** (hard invariants 1–7) and a **WRONG VENUE CONSTANT**. R2 is
neither. It therefore requires a discretionary mint, and the moratorium
(since 2026-09-16) requires that mint to be **justified in writing
against the price of a mint**, in this record, before it is called.

## The price of this mint (measured, AS-OF 2026-09-19)

1. **The accrual clock goes to zero.** Era-9's n=40 (of 50) banked trips
   leave the gate. If the 09-22 lean reads STOP, this cost is moot — the
   era ends anyway and R2 rides the same boundary the verdict mandates.
   If the lean reads CONTINUE, minting for R2 discards a readable cohort
   at 40/50, four days short of the lean.
2. **Trips already banked leave the gate** — measured 71.5% of stamped
   trips refused by the era gate today (`scripts/discard_ledger.py`;
   the law's 77.9–78.2% is a different reader-side view — both are
   instrument claims, not facts).
3. **Trips in flight are censored** at a rate that rises as eras shorten
   (the law's censoring ladder; the 09-19 peak-recovery instrument
   (`06799f4c`) REFUTES the strong form of the censoring theory for
   closed-trip peaks, read that record before citing the ladder).

## The case FOR minting (at the 09-22 boundary)

- The defect is real and pre-named in spirit: "no moving targets under
  an open position" is the documented discipline of the PT-060 virgin
  gate; R2 extends the same discipline to tier triggers 2–4, which today
  recompute live every cycle and CAN be moved by a post-fire vol spike.
- Post-fire vol spikes are exactly the regime in which tiers 2–4 fire —
  the position just banked a tier, vol is elevated, the remaining
  triggers inflate, and the position holds through a give-back it would
  otherwise have exited. This is the same 10.6:1 trail/bracket asymmetry
  family the 09-16 firing audit documented (RECENTLY SETTLED).
- Shipping cost is prepaid: 9/9 surface tests green, full chunked battery
  ran with zero branch-introduced failures, pyright 0 errors on changed
  files. Merge is mechanical.

## The case AGAINST minting

- Every mint so far that was NOT a wrong venue constant is how the
  project got to 12 boundaries in 37.9 days (median 2.43 d measured,
  09-19). Four of the last five were fee re-bookings; R2 would be the
  first discretionary geometry mint since the price was named. The law
  exists to make this feel expensive.
- Legacy default (empty snapshots = live recompute) means the status quo
  is not broken-looking; the defect manifests only under post-fire vol
  spikes, which era-9's quiet tape may not even have demonstrated at
  n=40.
- If the 09-22 verdict is STOP, the next era's configuration is a
  docket question anyway — R2 could ride THAT boundary with a fresh
  cohort accruing under the corrected geometry from day one, which is
  the cleaner experimental design (one change per era).

## Alternatives the operator may prefer

- **A. Mint at 09-22 with the verdict** (R2 enters the next era's
  geometry from day one; accrual restarts either way).
- **B. Hold to the next boundary** (if verdict is STOP, R2 rides the
  re-configuration bundle; if CONTINUE, era-9 runs to n=100 with the
  known defect documented, R2 mints after).
- **C. Refuse** (live recompute stands; the defect is documented drift,
  like the four mechanisms the 09-18 audit named).

## Evidence pointers

- Branch: `fix/decisioning-coupling-r123` @ `bc9e3856` (worktree
  `.claude/worktrees/decisioning-r123`)
- Tests: `tests/test_coupling_r123.py` (9 tests: snapshot-at-fire,
  survives-spike, live-recompute fallback, persistence roundtrip,
  legacy-default)
- Analysis: `docs/quant/2026-09-19_decisioning_coupling_analysis.md`
- Battery evidence: appendix of the analysis doc (6 chunks, ~5,470
  passed, all failures pre-existing on main and verified as such)

## Ruling (operator fills on 2026-09-22)

Decision: ____ (A / B / C)    Era-9 lean at ruling: ____ (STOP / CONTINUE)
Signature: __________________  n at ruling: ____
