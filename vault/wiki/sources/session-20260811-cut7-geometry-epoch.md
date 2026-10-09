---
title: "Cut #7 minted — the geometry epoch (e7d5ca1a): Osler semantic flip, ALGO-6 pins, and the CDO-review split"
category: source
summary: "The operator's cut-#7 timing adjudication landed as a CDO-review SPLIT: evidence-sufficient Tier-2 elements shipped at the free cohort reset (zero closes since the capital epoch), replay-parameterized widths deferred to a pre-named ALGO-5 amendment at ~30 uncensored paths. The verification sweep found the EXISTING Osler nudge had OPPOSITE semantics (tighten-above — any sweep TO a round level ejected the position, the exact shakeout the bull-readiness directive names), was nearly dormant (bracket sl leg stamped raw), and read a PHANTOM config block (risk_management does not exist — the knob was never read, masked by the coinciding 5.0 default). ALGO-6 shipped as PINS not duplicates (both halves already deployed). Battery 16 went RED on the package's own first pin — a ≤4 threshold from a head-truncated grep (main.py legitimately says tb_time six times) — the evidence-truncation class's second member. The exec_era bump landed one commit late (76030603), verified fill-free."
tags: [session, cut-7, geometry-epoch, osler, stop-placement, algo-6, algo-7, cdo-review, exec-era, battery]
sources: 1
source_path: "repo commits e7d5ca1a / 76030603 / ee7a94a2 (head at filing), risk/stop_placement.py, tests/test_algo6_time_limit_pins.py, tests/test_fill_ledger_provenance.py, config.json:186-188 — verified on the box at filing"
source_date: 2026-08
authors: [operator, session-agent]
ingested: 2026-08-10
updated: 2026-08-10
---

# Cut #7 minted — the geometry epoch (2026-08-11T01:33:50Z, `e7d5ca1a`)

**Dating.** Commit stamps are `2026-08-10 20:33..20:40 −05:00` = `2026-08-11T01:33..01:40Z`;
the boundary stamps at the **deploy instant 2026-08-11T01:33:50Z** (book flat and orderless
through the kill→relaunch window, so the boundary is ambiguity-free). Zone-stamped per domain
rule 9; same evening-boundary shape as [[sources/directive-20260811-grand-synthesis]].

**Boundary statement** ([[concepts/paper-real-boundary|rule 13]]): all three commits are
**repo-side**; every stop that the new geometry places is **sim-side** (nothing executes); the
Osler evidence is literature-side ([[sources/sweep-20260811-academic-stops]]).

## §0 — The adjudication: a CDO-review SPLIT, not a monolithic yes

The operator's pasted-back adjudication (2026-08-11, recorded verbatim in `e7d5ca1a`'s message)
did not adopt Tier 2 whole. It **split it along the evidence axis**:

- **LAND NOW** (evidence already sufficient, at the free cohort reset): ALGO-7's
  **widen-beyond direction** (Osler ESTABLISHED + the flip below) and ALGO-6 as **pins over
  already-deployed machinery** (§2).
- **DEFER** (parameterization data does not exist yet): replay-derived stop **widths** and the
  **time-decay ladder** — to an **ALGO-5 amendment at ~30 uncensored trade paths**, pre-named
  in the moratorium law itself (`ee7a94a2`) as **the next boundary-minting adjudication**.

The two sharpenings this forces on
[[synthesis/grand-synthesis-algorithm-package]] are filed there (§sharpenings): the page's
"one package, one adjudication, one boundary" is superseded by the split, and "cheapest at low
accrual" resolved to **free at zero accrual** — zero closes existed between the capital epoch
and the deploy, so the era-4 population is uniformly post-geometry **with no change to the
pre-registered cut**: `max(B4_TS, CAPITAL_EPOCH_TS)` and "after cut #7" select identical
populations by construction, forever.

## §1 — ALGO-7: the semantic flip (tighten-above → widen-beyond)

The verification sweep found an **existing Osler nudge** — `main.py
nudge_stop_off_round_number` — with **opposite semantics** to the evidence: it nudged stops to
the **near side** of a round level ("exit before the cascade detonates"), under which **any
sweep TO a round level ejects the position** — precisely the shakeout ejection the operator's
bull-readiness directive names. Three defects in one instrument, each independently masking
the others:

1. **Wrong direction** — tighten-above, the anti-Osler reading of "off round numbers."
2. **Nearly dormant** — only the rare non-bracket fallback path called it; the bracket sl leg
   (virtually every trade since geometry-alignment) was stamped raw. The wiki's own claim that
   "the bot's own stops are nudged off round numbers" ([[entities/osler]]) was **wrong on
   coverage as well as direction**.
3. **Phantom config read** — it read `config["risk_management"]`, a block that **does not
   exist**, so `stop_round_buffer_bps` was never actually read; only the coinciding 5.0
   default masked it (§3, filed in [[synthesis/documentation-drift-register]]).

**The fix** (`risk/stop_placement.py`, new module, pure functions): a stop within `band_bps`
of a half-step round level rests `offset_bps` **PAST** it (long below / short above) — the
herd's clustered stops fire first, ours only if the level actually breaks. Cost accepted
knowingly and stated in the module: a genuine break exits **into** the cascade; the escalation
ladder owns that path. The retired implementation's **half-step lattice is kept** (00/50
endings, scale-free step `10^(floor(log10(price))−1)`), so **cut #7 is direction-only**. The
nudge **only ever widens**, bounded by band+offset bps; degenerate inputs fail-inert, never
fail-tighter. Wired at **both** stop sites: the bracket sl leg back-derives `bracket_sl_frac`
from the nudged price — the traded bet stays the labeled bet (geometry-alignment law), `tb_sl`
threads unchanged — and `_stop_price_for`'s tail, whose old clamps (`max(nudged, stop)`)
**structurally enforced tighten-only** and were removed with the flip. The trigger side
needed no work: stops already evaluate on the trusted composite mark with single-tick
quarantine-and-confirm — ALGO-7's item (i) verified, placement was the missing half.

**The record of the flip is the tests changing sign**: the four Osler tests in
`tests/test_barclose_and_osler.py` flip direction — per the convention that a deliberate
behavior change lands **in the tests that pinned the old behavior**, never beside them.
23 tests (stop_placement + flipped osler).

## §2 — ALGO-6: pins, not duplicates

Both halves of the engineering world's convergent time-exit fix **already exist here**:
`tb_time` fires a **full, P&L-blind close** at each position's own `bracket_deadline_ts`
(hummingbot's time-limit barrier), and PT-060's no-progress scratch carries **local evidence**
(MFE 0.16% vs MAE −1.44%, recovered 0/17). So the package ships **four pins**
(`tests/test_algo6_time_limit_pins.py`): the full close; **per-position (never global-clock)
maturity**; the PT-060 config block still carrying its own evidence in-doc; and **exactly one
`tb_time` submit site** — a second time-exit path would be the two-paths-one-quantity defect.
The time-**decay** ladder is deliberately deferred to the ALGO-5 amendment: freqtrade's own
tracker documents aggressive decay tables **reproducing the exact near-TP/far-SL geometry**
they exist to fix ([[concepts/behavioral-isomorphism]]).

## §3 — The phantom `risk_management` knob

`config.json` documents `stop_round_buffer_bps` in the `risk` block; the reader looked it up
in `config["risk_management"]`, which has never existed. The knob was a **phantom — never
read** — and the failure was invisible because the hardcoded default (5.0) coincided with the
configured value. Fixed with the flip: the reader targets `config["risk"]`,
`stop_round_offset_bps` (5.0) added beside the buffer, and **pinned — nothing may read the
nonexistent `risk_management` block again.** Filed as a
[[synthesis/documentation-drift-register]] row: a config surface that presents as a live
tuning knob and is wired to nothing is the drift class's config-plane form
(cousin to [[concepts/false-green]]: turning the knob would have "worked" silently).

## §4 — Battery 16: the evidence-truncation class's second member

Battery 16 went **RED on this package's own first pin**: the ALGO-6 test's `<=4` threshold for
`tb_time` occurrences came from a **head-truncated grep** — `main.py` legitimately says
`tb_time` **six** times. Fixed to count **the submit call exactly**; the test's docstring
records its own first version's mistake. **Same evidence-truncation class as the
wrapper-exit-code error** (owed 44, battery 14, the same night) and filed with it in
[[concepts/false-green]] — with the polarity inverted: there, truncated evidence (wrapper exit
for `BATCH_EXIT`) hid a RED; here it **manufactured** one, a red on correct code. Common
mechanism: **a conclusion drawn from a truncated evidence stream**, and the fix is the same —
mechanical, exact reads (count the call site, check the marker), not vigilance. Final battery
after the fix: **ALL GREEN**.

## §5 — The exec_era bump landed one commit late

The minting rule says the `exec_era` bump **rides the boundary commit**; it landed one commit
late (`76030603`, six minutes after `e7d5ca1a`). **Verified before bumping: zero fills between
the deploy instant and the bump commit** — the book was flat through the whole window — so no
row was ever stamped `4-aeeaae36` on the era-7 side. The provenance pin
(`tests/test_fill_ledger_provenance.py`) moved in the same commit and now pins **the exact
constant** (`7-e7d5ca1a`) plus the `<era>-<8hex>` format, so the next bump can land neither
silently nor late without a red test. Recorded as minting-rule debt on
[[synthesis/comparability-boundaries]] — the rule survived its first exercise **by luck of a
flat book**, and the pin converts that luck into a gate.

## §6 — The re-fence (`ee7a94a2`)

`CLAUDE.md`'s moratorium law now names **stop/exit geometry (placement, nudges, time limits)
explicitly** in the cohort-resetting list — the cut-#7 lesson: **geometry changes trip
outcomes even when fill mechanics don't move** — and pre-names the ALGO-5 amendment as the
next adjudication that mints a boundary. Era-4 gate accrual: **0/50 from the capital epoch,
unchanged**, now uniformly post-geometry.

## Related

[[synthesis/comparability-boundaries]] · [[synthesis/grand-synthesis-algorithm-package]] ·
[[sources/directive-20260811-grand-synthesis]] · [[entities/osler]] ·
[[concepts/false-green]] · [[synthesis/documentation-drift-register]] ·
[[synthesis/owed-measurements]] · [[synthesis/governance-doctrine]] ·
[[concepts/behavioral-isomorphism]] · [[sources/sweep-20260811-academic-stops]] ·
[[sources/sweep-20260811-engineering-precedents]]
