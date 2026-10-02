# Pre-live checklist: venue-integrity items (before `ARM LIVE`)

**Operator sign-off 2026-09-27:** checklist adopted; VG-2 ratified. Items 1 and 3–6 are still to be done before arming.

Written 2026-09-27 under the operator's "build the VG checks" approval. Every
item is SAFE class: it measures, it never gates. Nothing here is read by the
engine. This list is the venue-integrity part of going live. It sits
alongside the four-step road to live in CLAUDE.md invariant 1 and does not
replace it. Authority for each item: `docs/law/conduct_standard.md` section 3.

Tool: `python scripts/venue_integrity_report.py <sub> [--json]`. Definitions
live in `core/venue_integrity.py`, codes are the `VI-*` family in
`core/codes.py`, and the pins are in `tests/test_venue_integrity.py`.

## Before arming (operator)

1. **VG-11: the API key cannot withdraw.** In the Kraken UI (Settings, API),
   open the key the bot uses and confirm that **Withdraw Funds** and every
   funding/transfer permission are **unchecked**. The key needs only query
   and trade permissions. The bot cannot check this itself: Kraken has no
   read-only "list my key's permissions" call, and probing with a withdrawal
   would violate invariant 4. The code-side deny-list (`data/kraken_feed.py`
   `_endpoint_is_forbidden`) stays untouched, and
   `tests/test_venue_integrity.py::test_vg11_checklist_item_and_deny_list_intact`
   pins it. The key permission is the second, venue-side lock, and only the
   operator can confirm it. Record the date checked: `____`.
2. **VG-2: ratify the live fill-acceptance registration below.** The values
   are registered as of 2026-09-27, before any live fill exists.
   **RATIFIED by the operator 2026-09-27, values unchanged.** After the first live fill, a change is a
   re-registration and must never be a retune (overfit law).
3. **VG-9: `venue-status --fetch`**. SystemStatus and every traded pair must
   be `online`.
4. **VG-10: `custody --fetch --target-usd <T>`**. Dollars on the venue must
   not exceed your off-venue target.
5. **VG-6: `orphans --fetch`**. There should be no orphan or stranded venue
   orders before the first live boot.
6. **VG-8: read the STP note below**, and rule on OD-9 if you want to.
   **Operator ruling 2026-09-27: leave `stptype` unset for now and
   revisit before `ARM LIVE`.** This item stays open until then.

7. **EDGE-1: a registered signal pays a round trip before any live TRIP
   book (added 2026-10-02, operator direction "all of them").** Run
   `python scripts/alpha_decay_report.py`. A live trip book (entries that
   exit back to flat) is armed only if at least one REGISTERED signal reads
   `TRADEABLE AS TRIPS`: 95% CI lower bound of total edge mu0*tau above the
   booked round trip 2c (45 bps at 15/30), in BOTH time halves, Holm across
   its family, measured on independent prices. As of 2026-10-02 **no signal
   does** - not the bot's 18 features (market-relative edge ~0), not five
   literature priors on 20 assets over 3.7 years, not the long-horizon
   family (`docs/quant/2026-10-02_alpha_decay_mu0_tau.md`,
   `docs/quant/2026-10-02_feature_program.md`). Dry-run exploration is NOT
   gated by this item: the 2026-09-28 ruling (keep exploring - paper
   tuition buys labels) stands. A holding book that pays no exit per idea is
   outside this item; it follows its own registration. Like every item
   here, this measures and never gates in code; arming without it is the
   operator's documented choice. Record the run and verdict: `____`.

## VG-2 live fill-acceptance registration (`LIVE_FILL_ACCEPTANCE`)

Report-only. Nothing sizes, gates or exits on these values. Acting on a
breach is an operator decision, and changing behavior because of one is
COHORT-RESETTING. Each bound is a formula on the **booked** fee row, or a
definitional floor. None is fitted to fill data. The n-floors are the
house's registered read points: **n=50 is the lean** (status `*_LEAN`) and
**n=100 is the verdict**. Below n=50 a metric reads `UNDER_N` (VI-021) and
gives no verdict.

| Metric (live entry fills) | Bound | Why this bound |
|---|---|---|
| `entry_slip_p90_max` (bps, + = adverse vs arrival) | `taker_bps - maker_bps` | Slipping more than the fee saved by resting makes maker-first worse than taking. |
| `alpha_markout_30s_mean_min` (bps, + = with us) | `-maker_bps` | Adverse drift larger than the maker fee means passive fills are being picked off faster than the fee they save. Input is the per-fill 30s alpha mark-out list (`--markout-json`). Without it the metric is UNDER_N. |
| `entry_post_only_share_min` | `0.5` | Maker-first means most entry fills are post-only. |

Command: `fill-accept`. It grades only fills whose governing session
(`CG-000` `dry_run`) was live. `--include-dry` grades simulator fills as a
labelled `SIM_REFERENCE(...)` and never produces a live verdict.

## VG-8: venue self-trade prevention [K]

Kraken AddOrder `stptype` defaults to **`cancel-newest`**, meaning "arriving
order will be canceled". Source: https://docs.kraken.com/api-reference/trading/add-order,
read 2026-09-27. The bot sends no `stptype`
(`execution/order_manager.py` AddOrder payload), so the default applies. On
the OD-9 path, where a marketable 5m exit sell arrives against the bot's
own resting 5m entry buy, the **exit** is the arriving order. The venue
would therefore cancel the exit, not the entry [I]. Exits are always
allowed under invariant 5, and this is a venue-side exception to that. The
operator should know it before arming. Measurement:
`self-cross` (the live self-match scan, plus the OD-9 coexistence scan over
the audit). Sending `stptype` or widening the LB-022 guard is
COHORT-RESETTING, and it is an operator ruling (OD-9).

## After the first live fills (report cadence, operator's choice)

| Item | Command | Code on finding |
|---|---|---|
| VG-1 fee vs published row | `fees --volume-30d V [--aop-usd A]`, or `--trades th.json` | VI-010 (VI-011 when the tier cannot be resolved) |
| VG-2 acceptance | `fill-accept [--markout-json m.json]` | VI-020 / VI-021 |
| VG-3 sim vs live fill rate | `fill-gap` | VI-030 |
| VG-4 venue error classes | live `VI-040..048` in `status.json` code tally; offline `errors --log <bot.log>` | VI-04x |
| VG-5 post-only cancels | live `VI-050` tally; offline `post-only --closed closed.json` | VI-050 |
| VG-6 orphans | `orphans --fetch` or `--open open.json` | VI-060 / VI-061 |
| VG-7 fills vs venue | `reconcile --closed closed.json --trades trades.json` | VI-070 / VI-071 |
| VG-8 self-match | `self-cross` | VI-080 |
| VG-9 status | `venue-status --fetch` | VI-090 |
| VG-10 custody | `custody --fetch --target-usd T` | VI-100 |

VI-001 on any report means the input held no live rows. That is an absent
verdict, not a clean one.
