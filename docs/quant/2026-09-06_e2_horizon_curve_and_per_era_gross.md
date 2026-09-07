# E2 horizon curve, per-era gross, E3 control — closing the open measurements

**Date:** 2026-09-06/07
**Class:** SAFE — measurements only. Nothing here changes which orders are
placed or how they fill. Every number is as-of a stamped read; re-derive
commands are given per section.

---

## 1. Per-era GROSS — the "unreconciled sign" resolved into a table

The Simons pass (2026-09-05) found the session quoting gross **+$0.0255/trade**
while the vault held negative gross on other corpora, and called the sign
**open**. It is open because it was being asked as ONE number. Per
`exec_era`, closed round trips only, hedge legs excluded, straddling trips
(entry and exit in different eras) excluded, `outputs/fills.csv` 196,642 B
read 2026-09-07T00:08Z:

| era | n | gross/trip | 95% CI (trip-bootstrap) | verdict |
|---|---|---|---|---|
| `(blank)` pre-stamp, eras 1–6 pooled | 239 | −$0.0142 | [−0.094, +0.062] | spans zero *(not one series)* |
| `7-e7d5ca1a` geometry epoch | 56 | **+$0.1665** | **[+0.029, +0.341]** | POSITIVE |
| `8-ca55e2ba` | 3 | −$0.2636 | n<25 | — |
| `9-16ec821e` Tier-3 fees | 29 | −$0.0605 (median −$0.16) | [−0.225, +0.110] | **spans zero** |
| MIXED (straddling) | 14 | excluded | | |

**Verdict.** Era-7 is the only era whose gross clears zero, and only on a
trip-bootstrap that ignores day clustering (optimistic by `√(n/n_eff)`).
**Era-9's gross is indistinguishable from zero** at n=29. The +$0.0255
belongs to no era. Net per trip is negative in every era but era-7
(−$0.26, +$0.05, −$0.50, −$0.21). Era-7 (`7-e7d5ca1a`) accrued at 25/40
booked fees and the pre-cut-8 geometry; its positive gross is a fact about
that regime and may not be pooled forward.

Re-derive: the fills-based script in this session's transcript; group
`fills.csv` by `position_id`, gross = Σsell − Σbuy, single-era trips only.

## 2. E2 — MFE/MAE versus holding horizon, entry-agnostic, no Gaussian

Every 5m bar on the stored tape (`outputs/candles/parquet/*_300.parquet`,
MANIFEST `written_at 1788391520`, 51.0 d, 15 pairs) treated as a hypothetical
long entry at its close; MFE(h) = max high over the next h bars / close − 1;
MAE(h) symmetric on lows. Fee round trip **55 bps** (20/35), break-even
buffer **76 bps**. `indep~` = span/h, the honest independent-window count.

| pair | median MFE first ≥ 55 bps (fees) | first ≥ 76 bps (BE) | median MFE at h=432 (36h) | p90 at 432 | indep @432 |
|---|---|---|---|---|---|
| PAXG | h=192 (16 h) | h=288 (24 h) | 104 | 333 | 27 |
| ETH | **h=96 (8 h)** | h=192 | 178 | 586 | 33 |
| BTC | h=192 (16 h) | h=192 | 132 | 451 | 33 |
| SUI | h=48 (4 h) | h=96 | 178 | 690 | 31 |
| ARB | h=24 (2 h) | h=24 | 316 | 2052 | 17 |
| MINA | h=12 (1 h) | h=24 | 697 | 2058 | 14 |
| FLOW | h=12 (1 h) | h=24 | 525 | 1691 | 11 |

**The Simons pass's expected null did NOT obtain.** It predicted *"median MFE
never crosses ~40–55 bps at any h out to 30 days"* → "these instruments cannot
pay this rake at any horizon". On every core pair the oracle-MFE median clears
the fee line within a day, and at the shipped 36 h horizon it sits at 1.4–2.3×
the fee on the majors. **So the instruments CAN pay the rake; the question is
selection.**

**Three readings that matter:**

1. **MAE is symmetric with MFE** at every horizon (ETH h=96: +66 / −57;
   BTC h=192: +81 / −62). This is the random-walk shape. The oracle's
   best-case up-move and worst-case down-move are the same size, so
   without a selector the median trade's realised outcome is cost-negative
   regardless of exit policy. E2 does not find edge; it finds that edge
   *would be harvestable* if it existed.
2. **The take-profit barrier sits above the median oracle move.** At the
   cost floor `pt = 8σ_eff = 2.4% = 240 bps`. At h=432 the median MFE on
   BTC/ETH/PAXG is 132–178 bps — **below 240** — so by construction the
   median path cannot reach TP inside the horizon; only paths above roughly
   the 70th–75th percentile can (p90 = 333–586). That is the 30–35%
   shadow win rate at 432 bars, derived from the tape rather than from
   labels. **This is barrier geometry — ALGO-5 territory, adjudicated
   "do not arm" 2026-09-02. Filed, not acted on.**
3. **The alt tail is a different asset class on this axis.** MINA/FLOW/ARB
   clear fees inside 1–2 h and show 5–7× the majors' MFE at 36 h — with
   proportionally larger MAE. That is volatility, not edge; it is why
   the why-losing deep dive found the alt tail −$3.67 on 27 trips.

What E2 cannot see: 51 days, one regime; longer horizons rest on ≤ 7
independent windows and are reported for shape only; longs only (shorts are
the mirror on this symmetric tape); no spread term (adds ~15–30 bps to the
line, moving every crossing one rung later on the majors).

Re-derive: the E2 script in this session's transcript (`swv` forward-max per
horizon); numbers change with the tape.

## 3. E3 — random-entry MFE-percentile control, re-run on today's book

`scripts/random_entry_control.py --json` (seed 7, K=200 matched random
entries per real trade, same asset / duration / direction), 2026-09-07,
wall 107 s:

| | original (`8062f46a`) | today |
|---|---|---|
| trades scored | 51 | **48** |
| mean MFE percentile vs controls | 0.516 [0.439, 0.594] | **0.5256** (SE 0.046 → ≈[0.435, 0.616]) |
| P(real beats control median) | — | 0.54 [0.40, 0.67] |
| median real MFE / control MFE | — | 0.92% / 0.76% |
| median real MAE | — | −1.98% |

**The null holds: no entry-timing signal.** The bot's real entries sit at the
53rd percentile of random entries on the same asset for the same duration —
indistinguishable from 50.

**The instrument is starved, and that is the finding to carry.** 500 closed
trips were offered; **452 were skipped for coverage** because the harness
reconstructs prices from `outputs/recordings/session_*.jsonl`, and recording
retention (the S3 defect — prune counted sessions, and a restart-churning box
evicted ~1.3 days of history per 9 minutes) had already discarded most trade
spans. Fixed forward on 2026-09-06; the past is gone. n went 51 → 48 while
the book went 51 → 341 closed trips. **Owed:** point the harness at the
51-day parquet tape (`outputs/candles/parquet/*_300`), which covers every
trip in `fills.csv`, and re-run at n≈340 — and at E2's crossing horizons
(h=96/192 on the majors) rather than each trade's own duration, which is
what the Simons pass specified. Not done here: that is a harness change,
and this pass was measurements only.

What survives regardless of n: real MAE (−1.98%) is twice real MFE (+0.92%)
at the trades' own durations — the same asymmetry the payoff-asymmetry page
records, now on a matched-control footing.

## 4. The bridge branch — kept, not merged, and why

`claude/vscode-bridge-5548d1` (4 commits, 999 insertions, tooling only:
`scripts/vscode_bridge.py`, `docs/VSCODE_BRIDGE.md`, `.vscode/tasks.json`,
`.claude/settings.json`). Its only conflict with main was the settings
allowlist, where main already carried every Windows entry the branch added.
Merged behind gates; **bandit flagged B404/B603** (subprocess use without the
fixed-argv `# nosec` annotations every other subprocess caller in the repo
carries), which would redden the DoD. The merge was reverted
(`git reset --hard ORIG_HEAD`); branch and worktree retained; unmerged work
preserved. Merge path when wanted: annotate the two subprocess sites the way
`scripts/auto_update.py` does, re-run bandit, merge with `-X ours` on
`.claude/settings.json`.
