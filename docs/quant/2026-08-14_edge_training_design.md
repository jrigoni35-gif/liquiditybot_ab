# Edge-training design — THALES-conditioned candidate selection (DESIGN ONLY)

Status: **UNCOMMITTED WORKING-TREE DESIGN — nothing here is shipped, wired,
or scheduled.** Era-4 accrual moratorium and the 2026-08-10 model freeze
bind every item; tiers are marked SAFE-NOW (measurement/report only) or
DOCKET (operator adjudication at/after the gate readout). Written
2026-08-14 against worktree HEAD `4609a1a9`; every file:line below was
read this session (zero-hallucination discipline; [K]=read, [I]=inferred,
[EXT]=external-to-repo provenance).

## 0. Provenance and law

- Corpus faults injected here were measured by the 2026-08-13 session
  audits (filed: llm-wiki `sources/session-2026-08-13-analyses`): champion
  trained 99.5% on retired geometry; h432 era ≈ 32 effective obs; ~1,064
  rows mis-tagged by `scripts/migrate_history.py`; calibrator mass ceiling
  0.2394 vs 0.55+ entry bars; realized-hold ≈ 8h vs 36h design (effective
  cost/σ ≈ 0.53); candidate-stream PT-share below the driftless null
  (z ≈ −3.7, n=799). **[EXT]** — the z=−3.7 number exists in no repo file
  (verified by grep); its derivation lives in the session workflow journal
  and the wiki source page. Anything built on it must first reproduce it
  in-repo (S2 below does exactly that).
- Overnight regime fact [K]: `outputs/meta_model.json` now carries
  `kind: logistic, rows: 211, feature_schema_version: 9` — the 10,217-row
  adaptive_gbt champion was superseded once era exclusion activated
  (2026-08-13T20:13Z). The predicted 07-29-style deadlock did not occur;
  the loop fell back. Consequence: the deployed model is trained on ~211
  rows ≈ tens of effective observations. Any "edge" it expresses is prior,
  not learning.

## 1. Why selection, not capacity

The repo's own measurements close the capacity question for now:
cost/σ is the binding constraint (docs/quant/2026-08-01_*), the learning
curve is flat ("representation-limited"), and the current-geometry corpus
is ~32 effective obs — no model family can extract edge from that. What
remains trainable **today** is the *selection* question: the candidate
stream itself resolves PT below a driftless null, i.e. the 5-gate
confirmed stream is adversely selected before any model sees it. The
anti-selection instrument already exists by design — the candidate
labeler writes every confirmed signal, taken or vetoed, at
`main.py:4439` (10,220 candidate rows) — and five THALES detector states
are frozen into every row at signal-build time (`main.py:5898` →
`ml/features.py:135-136`, cols `th_grid, th_metronome, th_clockwork,
th_stopzone, th_barclose`, non-zero on 97/72/55/2/2% of 10,546 rows [K]).

THALES is therefore the only per-candidate microstructure context already
joined to outcomes, and the THALES doctrine already contains the correct
training law (docs/THALES.md:212-234): **certificates before influence;
slow layers get veto rights, not alpha rights; a false shade costs
opportunity, a false boost costs money.** This design trains
*down-shades* (candidate vetoes) first, boosts never-until-certified.

Two facts temper enthusiasm, stated up front:
- The 2026-07-29 unit audit found **no dose-response** in the very columns
  this design conditions on (B-5: th_stopzone above/below 0.5 → −$0.164
  vs −$0.166/trade; manip buckets non-monotone). The nulls were then
  corrected (A-1/A-2) — the study must be re-run under the corrected
  nulls, not assumed to flip.
- THALES already steers decisions through the ML lane (th_* are model
  features; under the prior champion th_clockwork ranked #1 wf-importance
  on rows=211-era artifacts [K]). "Shadow" is true of the shade channel
  only. Any selection rule trained here must account for the feature-lane
  influence already present, or it double-counts.

## 2. The algorithm (offline study pipeline — SAFE-NOW as measurement)

All stages read files that exist today; no engine import, no new feed,
no config change, no row written to any production CSV. Output = one
report artifact per run under outputs/ (gitignored) or docs/quant/.

**S1 — Honest join.** signal_history.csv (10,546 rows) keyed by
position_id/candidate_id/ts; horizon_shadow.csv joins 58% via
candidate_id [K]. Era-fence by barrier-time FINGERPRINT (trimodal
tb_time deltas), never by the corrupted label_era tag (~1,064 mis-tags).
Weight rows by AFML uniqueness (the 0.05 floor REMOVED for analysis —
report both), report effective n per stratum, and refuse any cell with
effective n < 30 (print the refusal, never a number).

**S2 — Reproduce the anti-selection finding in-repo.** Resolved-PT share
vs the gambler's-ruin driftless null per pt_frac/sl_frac geometry, per
era-fingerprint stratum, per disp class (entered vs each SZ-* veto vs
capped). Deliverable: the z per stratum with Wilson CIs. This converts
the [EXT] z=−3.7 into a repo-native, re-runnable number — and localizes
WHERE in the pipeline the adverse selection concentrates (the disp
breakdown is the novel cut: if vetoed candidates out-resolve entered
ones, the gates are selecting wrong; if uniform, the stream itself is).

**S3 — Null-calibrated detector conditioning.** For each of the five
persisted th_* columns: outcome (label, net_ret via horizon_shadow join)
conditional on detector decile, against the A-1-corrected null (base
win rate for "up" advice, base loss rate for "down"), zeros EXCLUDED as
ambiguous (lapse-mute, disabled, and genuine-quiet collide at 0.0 [K]).
Sign convention per the asymmetry law: we are looking for down-shade
evidence (detector high → outcomes worse), not boost evidence.
Composites: the pairwise and triple interactions, PBO-guarded (S4).

**S4 — Validation battery (no new methodology, the repo's own).**
Purged walk-forward with uniqueness weights (ml/walkforward.py
conventions); shuffle-null (OF-2 form); selection-rule PBO on the RULE
this study would deploy (a down-shade threshold ladder), never argmax
(OF-3 form); DSR on any claimed composite. A rule survives only if it
beats the null out-of-sample AND survives PBO ≤ 0.55 AND its effect
size clears the cost floor it would save (a veto is worth its
opportunity cost only if the vetoed population's realized net is
negative beyond CI).

**S5 — Pre-registered promotion ladder (all DOCKET).** If S2-S4 produce
a surviving down-shade rule: register it as a shadow counter first
(fired/vindicated per the V2 ledger discipline, thales.py:228-292), with
promotion criteria written BEFORE accrual: n≥N fired, Wilson-LCB beats
the corrected null, OF battery green, G1-G5 green. Only then an operator
adjudication may wire it — as a candidate-stream veto (cohort-resetting,
boundary-minting) — never mid-cohort.

## 3. Instrumentation gaps the study needs closed (tiered)

| Gap [K, map §4.2] | Fix | Tier |
|---|---|---|
| spoof_bid/ask, feed_dirty, lapses have NO per-row history | persist as NON-feature forensic columns at candidate-registration time (outside FEATURE_NAMES → not model inputs → not a frozen-surface change) | SAFE-NOW, but adjudicate the "not a feature" reading with the operator before writing columns |
| clockwork_dir not persisted | same forensic-column route | same |
| would_mult/fired not on rows | same | same |
| th_* zero ambiguity (mute vs quiet vs disabled) | one status byte per row (lapse-muted flag) | same |
| events.jsonl 5MB single-backup rotation destroys shade history | rely on corpus rows, not events; optionally archive rotations | SAFE-NOW |
| thales_report.py "unexposed" bucket contaminated (neutral shades unlogged [K, map UNKNOWN-8]) | study uses corpus joins, not the report's ±8h exposure join | design choice, no change |

## 4. Hazards written down before anyone trades on this

- **Advise-mode double-count [I]:** flipping `thales.influence` to advise
  would enter the shade into p_win twice (via th_* AND via shaded
  gate_confidence, ml/features.py:154). Must be resolved before ANY
  advise promotion; not this design's business but recorded here because
  the map found it undocumented.
- **TH-015 defined, never emitted** (Code.TH_BARCLOSE_HERD, zero
  references outside codes.py [K]) — registry hygiene item.
- **Selection-on-selection:** S2's disp strata are themselves downstream
  of gates that used th_* via p_win (the ML lane). Strata must be
  computed within-era where the model was cold (pre-schema-9 rows) as a
  control.
- **The 07-29 B-5 no-dose-response result** stands until S3 overturns it
  under corrected nulls. Prior expectation: most detectors show nothing.
  The study's value is as much in killing the idea cleanly as in
  finding a veto.

## 5. Questions worth asking (behuman section — scored by measurable trace)

Each question is admitted only if its answer changes a number an
improvement stack can track (PnL-adjacent trace), per the operator's
2026-08-14 directive.

1. Does the vetoed-candidate population out-resolve the entered
   population? (S2 disp cut; trace: veto-quality → realized net of the
   counterfactual book.)
2. Is the adverse selection concentrated in a time-of-day or regime
   stratum the playbook already knows? (S2 strata; trace: stratum PnL.)
3. Do the two DOWN-only safety shades (spoof, feed) — the ones with no
   history — coincide with the worst realized outcomes? Unanswerable
   until the forensic columns exist; that is the argument for them.
4. What did the overnight champion swap (adaptive_gbt→logistic, 211
   rows) do to gate pass rates? (trace: entries/day, PT-* mix — readable
   from audit.jsonl now, SAFE.)
5. Is the $800-scale fee floor the real reason no cell pays, and would
   the SAME corpus at a maker-tier fee schedule show positive cells?
   (Re-run N5's horizon sweep at counterfactual fee rows — measurement,
   SAFE; decision DOCKET.)

## 5b. CDO review addendum (2026-08-14, verdict SHARPEN — conditions binding)

1. **N1 coupling:** the study's output feeds the readout decision table's
   candidate-repair branch — that branch must be added to N1 BEFORE S2
   runs, or the study drives no named decision.
2. **Forensic-column tier:** "not a feature = not frozen" is approved
   only with freeze-tripwire tests pinning every forensic column OUT of
   FEATURE_NAMES (promotion must require a visible test change). The
   write-path widening itself remains an operator adjudication.
3. **Boundary-#4 mask (hard filter in S1):** every S2/S3 stratum
   excludes rows at/after execution-era boundary #4 (2026-08-10T11:03:35Z)
   so no table can function as a back-door read of the accruing gate.

## 6. Verification (design vs map)

Every load-bearing claim above cites the map's [K] entries: candidate
registration site (main.py:4439), feature freeze path (main.py:5898 →
ml/features.py:135-136), non-zero shares, join rates (58%
horizon_shadow), A-1/A-2 null corrections (thales.py:228-292, 652-695),
B-4/B-5 audit results, certificate hierarchy (docs/THALES.md:169-234),
2026-07-18 adjudication record (docs/RESEARCH-20260718.md). External
finding flagged [EXT] with an in-repo reproduction stage (S2). No API,
column, or code invented; the five gaps in §3 are the map's own §4.2
gaps. Stories: 1/1 (this doc). OVERALL: COMPLETE as design; nothing
executable shipped.
