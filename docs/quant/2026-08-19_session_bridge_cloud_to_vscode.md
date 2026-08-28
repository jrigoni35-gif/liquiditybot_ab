# Session bridge: cloud → VS Code (2026-08-19)

Written by the cloud session (claude.ai/code, branch `claude/remote-control-e3h815`)
for the VS Code session sharing this repo. Facts verified against the
2026-08-19T00:25Z pc-live bundle (audit 45,605 records) and commit `c083f21c`
unless noted. Coordination rules in CLAUDE.md apply: pull --rebase before any
push; one session owns `main` fast-forwards at a time.

## 1. What the cloud session verified (do not redo)

**Task #148 — hedge-churn fix landing verification: CLEAN, but unexercised.**
- Zero FW-070 records in 45,225 audit records (bundle of 08-17). The latch has
  never fired live. Last hedge-related audit record: 2026-08-08 18:13Z — nine
  days with no hedging activity at all. Class-level signal (>2 unwinds/hour on
  any asset) clean by absence, not by load. Unit suite remains the only
  exercise of the gate.
- Warm-gate deadlock arithmetic measured, not assumed: `update_intraday` runs
  on the fast cycle (`main.py:4376`, `polling_interval_sec: 5`), so
  `corr_min_samples: 12` ≈ 60s to warm vs 0.50h median restart gap
  (306 startups, 25 in the last 7d). Warm reachable ~30× per median uptime.
- `rehedge_cooldown_sec: 600 < churn_window_sec: 900` — config_guard coherence
  FATAL satisfied.
- **Latent hazard, not a bug today:** `CorrState.samples` is NOT in
  `core/persistence.py` — the warm gate re-arms from zero on every restart
  (~25×/week). Harmless at 5s cadence; becomes the deadlock if
  `polling_interval_sec` is ever raised. If you touch the snapshot schema,
  consider carrying it; otherwise leave it.
- Your `30730d4a` tag() conversion of FW-070 (latch + release) reviewed from
  here: telemetry-only, moratorium-SAFE, keeps the latch/release semantics.

**Grafana fidelity audit (5-agent, adversarially verified 2026-08-17).**
Question: do the boards represent the bot? Verdict: values honest, silences
not loud enough. Trust list: status.json scalars are verbatim relays stamped
with the bot's own write-time; fail-stale (>120s → alarm batch, never
masquerade) is test-pinned; boards byte-deterministic from the generator.
Divergence list, ranked:
- **D2 (live defect, highest leverage): alert routing void.** `lb-telemetry-stale`
  and `lb-manip-high` route to an empty root receiver on the live instance.
  The repo's `notification_settings: {receiver: grafana-default-email}` is
  MANUAL-APPLY (your own header says so) and has NOT been applied: six deadman
  firings 08-16→17 paged nobody. Until the PUT lands on the PC, every alert is
  decorative. **When applying, decide the restart question consciously:** at
  ~25 restarts/week with ~8–11 min deadman timing, most restarts will page
  once routing works. Tune `for:` or accept the pages — at apply time, not as
  a surprise.
- **D1: fossil money tiles.** lastNotNull over 24h windows keeps dead-pipeline
  values rendering healthy up to a day. The Data age tile is the one honest
  clock.
- **D3: per-family silent absence.** One status section dying (ml/watchdog/
  positions/…) blanks or fossilizes its tiles and pages nothing — the deadman
  only watches whole-file age. This is the recorded 08-06→08-16 Brier dark
  spell shape. No substitute alert exists.
- **D5: counter resets.** No rate()/increase() anywhere, so restarts zero
  fills/faults/firewall counters silently — a crash-loop reads "0 faults."
- **Epoch rendering:** the 08-10 capital reset (4606→800) is a bare cliff;
  `starting_capital` is pushed but queried on NO panel; any long-range delta
  over it reads −$3,806 of "loss." One live-panel check owed: problems
  panel 35 `rp_drawdown_mtm_pct` — the high-water ratchet
  (`core/state.py:334-353`) has no epoch-reset path; if it shows ~83% it is
  measuring against the 4606-era peak forever.
Proposed SAFE-class fixes, in order: (1) apply the routing PUT on the PC,
(2) panel `starting_capital` + an epoch annotation on equity, (3) a
per-family absence alert. None started; claim them if you want them.

## 2. Bot state as of the 08-19 00:25Z bundle

- DRY_RUN, RUNNING, equity $798.79 vs $800 epoch capital (lifetime −$1.21,
  fees $3.13). Flat at noise size. Corpus 11,384 rows (11,050 candidate /
  334 live).
- **SD-002 model starvation loop** is the standing digest verdict: model cold
  (level 0, 334 live rows, brier n/a), 118 retrain requests, SZ-047 = 63% of
  non-routine audit. Self-sealing — retraining cannot fix missing data.
- **SD-003 liquidity vetoed feed-wide:** 'spoofy' on 60% of classified cycles
  suppresses sizing everywhere. Skimmer's own numbers argue miscalibration
  (XRP 0.1 bps spread, ADA 0.12 bps — no spoofing at a tenth of a bp).
  Cloud proposal (unclaimed, SAFE class): instrument the classifier against
  the near-zero-spread case — measurement only, no gate change without
  operator adjudication.
- Feed errors ~30× baseline (269/window vs 8–9 early-Aug; OKX/Binance.US
  read timeouts — read-only venues, execution unaffected). Faults 4–8/day
  since 08-08 vs 0–1 before. Worth a look if you're in the feed layer anyway.
- **Open and unexplained: negative edge at correct geometry (z = −4.14).**
  Upstream of the ML layer, in entry selection. SD-003's feed-wide veto is an
  untested candidate contributor. This is the question the era-4 cohort gate
  exists to answer — do not retune on accruing numbers.

## 3. Standing decisions parked with the operator (do not implement)

- Era threshold: cloud recommendation `min_new_era_rows = 640`
  (10 × 64 features, OF-7's own DoF floor). Operator has not ruled.
- `max_open_candidates`: 200 is sized for the old 8h horizon; Little's Law at
  the 36h horizon needs ~424 slots — ~53% of signals currently refused.
  Cloud recommendation ~1,200 + a config_guard coherence check vs
  `label_max_bars`. Interacts with the era threshold — ship together, after
  adjudication. NOT cohort-safe by default: touches which candidates are
  registered; treat as operator-adjudicated.
- ALGO-5 amendment (stop widths + time-decay ladder) stays PRE-NAMED as the
  next cohort-resetting adjudication (~30 uncensored paths).

## 4. Item only the VS Code session can do (PC filesystem)

The operator surfaced a third-party VS Code extension on the PC:
`hou80houzhu.dllc-vscode-extension` ("Dllc Develop Toolkit", ~53k installs,
no reviews, no public repo, category Other). Marketplace command list =
process spawn/kill ("cluster" of local dev services), `create project from
git`, global config edit. Panel showed it idle (no services, no project).
Nothing links it to the GitHub window storm (that was GCM prompting, fixed
at `f756676e` / DL-2). Unverifiable from the cloud. If the operator wants it
vetted: read
`%USERPROFILE%\.vscode\extensions\hou80houzhu.dllc-vscode-extension-1.0.0\package.json`
(activation events, command impls) and the JS it points at, and report where
`create project from git` / `Update Cluster` phone home. Do not uninstall
without the operator's word — it may be theirs.

## 5. Coordination ledger

- Sidecar no-prompt hardening (DL-2): yours, landed `61c3b5c1`, verified here.
  Cloud stands down permanently on it.
- Hedge-churn fix `cf454d5`: deployed, verified (§1). #148 stays open only
  for the "exercised under load" leg — nothing to do until hedging activity
  resumes; whichever session is live when it does should grep FW-070.
- Grafana overhaul (`bbdf8c06`…`c083f21c` incl. learning panel, owed metrics,
  deadman mirror, deploy-channel pin): yours; cloud audit above is the
  independent review of the result — the divergence list is feedback, not
  criticism; D2 routing is the only live defect found.
- Audit chain: 8 writer seams, hash-valid, tamper=False, benign — but the
  count grew 6→8 across the 15th. If it grows again, the instance lock is
  leaking; whoever sees it first files it.
- This bridge goes stale like any snapshot: dated facts above decay; trust
  the vault + fresh bundles over this file after ~a week.
