"""
core/codes.py — global reason-code registry (Assurance Build)

One canonical, stable vocabulary for every machine decision in the
system. Every reject, clamp, override, fault, and model-governance
action carries exactly one code from this registry, in the form
"XX-NNN: human detail". Codes are append-only: a code, once shipped,
is never renumbered or reused (audit trails must stay interpretable
forever).

Prefix map (subsystem of origin — every family with a registered member is
listed here, and nothing else: the map once advertised a WD (core.watchdog)
family that never had a single code — the same defect shape as the
unregistered-CG-000 bug (W2-19) — and omitted VN/RP/RT/DF, which all have
shipped members below. Registry-hygiene pass 2026-08-17):
  FW  execution.risk_firewall     PT  execution.pretrade
  OM  execution.order_manager     SZ  risk.position_sizer
  QT  execution.market_maker      FV  execution.fair_value
  VN  execution venue adapters (registration/eligibility gates)
  RP  risk.protocols (CVaR/gap/budget/heat overlay + period ledgers)
  ML  ml.* (contracts/registry/monitor)
  CG  core.config_guard
  FT  core.fault (system-level faults / state transitions)
  TP  risk.profit_tiers (exit-system dispositions)
  TH  strategies.thales (lazy-bot insecurity detectors / advice)
  RT  runner.py (runner lifecycle: single-instance lock)
  RC  scripts.remote_control (git command-bus dispositions)
  XV  execution-truth harness (replay gate + fill-model calibration)
  LT  regime.liquidity_regime (asset liquidity-tier isolation)
  CR  regime.correlation (cross-asset turbulence reading provenance)
  GL  execution.grid_ladder (logistic-armed grid entry ladder)
  HG  execution.hedging / main._hedge_actions (hedge-open new-risk gate)
  CV  risk.conviction (Compounder Phase A conviction formula)
  CX  data.context_engine (Compounder Phase B context feed)
  DF  data feeds (data/moomoo_feed.py freeze/degrade detectors)
  LB  risk.long_book (Compounder Phase C long-horizon book)
"""

from enum import Enum

from core import code_stats


class Code(str, Enum):
    # ---- risk firewall (FW) ------------------------------------------
    FW_INVALID_FIELD = "FW-010"
    FW_INVALID_PRICE = "FW-011"
    FW_INVALID_SIZE = "FW-012"
    FW_INVALID_EQUITY = "FW-013"
    FW_RATE_LIMIT = "FW-020"
    FW_RATE_EXIT_OVERRIDE = "FW-021"  # exit past rate budget allowed anyway (escapes never rate-vetoed)
    FW_DUPLICATE = "FW-030"
    FW_NOTIONAL_REJECT = "FW-040"
    FW_NOTIONAL_CLAMP = "FW-041"
    FW_COLLAR_REJECT = "FW-050"
    FW_COLLAR_CLAMP = "FW-051"
    FW_EXIT_PRICE_SUB = "FW-052"
    FW_NO_REFERENCE = "FW-060"
    FW_HEDGE_CHURN_LATCH = "FW-070"  # >=N hedge unwinds of one asset in the window: re-hedging frozen (opens only, auto-releases warm+window; 2026-08-07 ADA churn, -$318 in 147 laps)
    FW_STALE_BARS = "FW-080"         # venue bars accepted into the view whose LAST bar timestamp lags the engine clock (latency audit 2026-08-07: fetch age was checked, bar age never; detection only)
    FW_LABEL_BARS_STALE = "FW-081"   # an ACTIVE (symbol_map) asset's labeler
    #   bars cache (ml/history.py CandidateLabeler._bars) stopped
    #   accumulating: last cached bar older than ml.label_bars_stale_cycles
    #   slow-cycles. Complements FW-080, which only fires when a fresh-enough
    #   Kraken fetch EXISTS (main._augment_view_with_kraken skips absent/aged
    #   _kr_candles entries entirely) - FW-081 watches the CONSUMER side, so a
    #   fetch path that dies outright is still audible. Staleness audit
    #   2026-08-16: DOT/SOL caches sat 157h/36h stale with zero log lines -
    #   that instance was legitimate skimmer rotation (assets left the boot
    #   universe), which is why this checks ACTIVE assets only. Latched once
    #   per stale episode per asset, re-armed on fresh bars; detection only.
    FW_FAULT_REJECT = "FW-090"
    FW_FAULT_DEGRADED = "FW-091"

    # ---- pre-trade gate (PT) -----------------------------------------
    PT_INVALID_INPUT = "PT-010"
    PT_STALE_DATA = "PT-020"
    PT_SPREAD_WIDE = "PT-021"
    PT_SPOOFY_REGIME = "PT-022"
    PT_BOOK_SHALLOW = "PT-023"
    PT_PARTICIPATION_CLAMP = "PT-030"
    PT_BELOW_MIN_ORDER = "PT-031"
    PT_EV_NEGATIVE = "PT-040"        # fill-prob-weighted EV fails the bar
    PT_EDGE_RATIO = "PT-041"         # edge/cost ratio below minimum
    PT_EXPLORE_BYPASS = "PT-050"     # dry-run exploration bypassed the profit-EV
                                     # gate to acquire a real-fill label
    PT_APPROVED = "PT-000"
    PT_TIME_STOP = "PT-060"          # risk.profit_tiers time-stop (P2, 2026-07-23
                                     # P&L diagnosis): a position that never
                                     # reached min_mfe_frac_of_tier1 of the
                                     # tier-1 effective trigger within
                                     # max_bars_no_progress bars is scratched
                                     # full-close - continues the PT numbering
                                     # (next open decade after PT-050) per the
                                     # P2 task spec, even though it fires from
                                     # the exit path, not execution.pretrade
    PT_CLOSE_REASON = "PT-061"       # I0 (2026-07-31 era-deadlock debate):
                                     # names the VERBATIM close_reason on every
                                     # full close. The corpus `barrier` column
                                     # collapses everything that is not a
                                     # bracket leg to "realized", so the
                                     # training data cannot say WHAT closed a
                                     # position - and 3 of the 8 bracket probes
                                     # ever closed died at 20-36 min, too early
                                     # for PT-060 (180 min) AND too early for
                                     # the post-381e870 give-back arm. An
                                     # unnamed mechanism is ending probes; this
                                     # record is the instrument that names it.
                                     # Report-only: changes no exit decision.

    # ---- venue adapters (VN) -----------------------------------------
    VN_REGISTERED = "VN-000"         # adapter registered (may be disabled)
    VN_NOT_ENABLED = "VN-010"        # place() on a disabled adapter
    VN_NOT_IMPLEMENTED = "VN-011"    # connectivity stub, no live transport
    VN_ROGUE_EXECUTION = "VN-020"    # non-kraken adapter marked execution-eligible
    VN_CREDENTIAL_MISSING = "VN-030" # enabled adapter without resolved creds

    # ---- order manager (OM) ------------------------------------------
    OM_CLEAN_TERMINAL = "OM-000"     # order reached filled/cancelled cleanly
    OM_INVALID_INPUT = "OM-010"
    OM_MARKET_REFUSED = "OM-011"     # market order outside exit escalation
    OM_BELOW_ORDERMIN = "OM-012"
    OM_ZERO_AFTER_FORMAT = "OM-013"  # price/volume rounds to a venue string
                                     # that parses to zero (pair precision vs
                                     # a dust-but-nonzero raw value) - refused
                                     # before the venue call / dry-run registration
    OM_FIREWALL_REJECT = "OM-020"
    OM_VENUE_REJECT = "OM-021"
    OM_ILLEGAL_TRANSITION = "OM-030" # order state machine violation
    OM_TIMEOUT_CANCEL = "OM-040"
    OM_DEADMAN_FAIL = "OM-050"
    OM_EXIT_PREEMPT = "OM-060"       # risk-off exit cancelled a resting maker take
    OM_FILL_APPLY_FAILED = "OM-070"  # _handle_fill raised on one poll event; the
                                     # rest of the batch is still applied and
                                     # snapshotted (no book/venue desync, no lost fill)
    OM_LEDGER_DUP_REFUSED = "OM-085" # fill_ledger refused a row identical to
                                     # one already recorded - restart-replay
                                     # signature (snapshot restored a pre-fill
                                     # order, sim earned the fill again). The
                                     # ledger keeps the FIRST copy; the trade
                                     # itself is unaffected. Owed 62.
    OM_CANCEL_UNCONFIRMED = "OM-090" # a venue CancelOrder returned no
                                     # confirmation (rate limit / 5xx /
                                     # venue error - _private_post returns
                                     # None rather than raising) while local
                                     # state was forced terminal: the order
                                     # may STILL REST at the venue as a GTC
                                     # orphan invisible to open_orders(),
                                     # and a healthy bot's own deadman
                                     # refresh keeps the venue from
                                     # auto-cancelling it. Live-only signal
                                     # (dry-run never posts); leaving the
                                     # escape blocked would be worse, so the
                                     # terminal transition still happens -
                                     # this makes the residue AUDIBLE
    OM_FEE_RECON_MISMATCH = "OM-080" # W2-9 remainder: periodic TradeVolume check
                                     # found the account's ACTUAL Kraken fee tier
                                     # diverging from EITHER configured source -
                                     # order_manager.maker/taker_fee_bps (what OM
                                     # books fees at) OR pretrade.maker/
                                     # taker_fee_bps (the EV gate's cost stack) -
                                     # (configured < actual, or |diff| beyond
                                     # tolerance) - REPORT-ONLY, never mutates
                                     # config.json; the operator re-tunes it

    # ---- sizer (SZ) ---------------------------------------------------
    SZ_INVALID_INPUT = "SZ-010"
    SZ_COOLDOWN = "SZ-020"
    SZ_REGIME_BLOCK = "SZ-021"
    SZ_DIRECTION_BLOCK = "SZ-022"
    SZ_PWIN_BAR = "SZ-023"
    SZ_KELLY_ZERO = "SZ-030"
    SZ_MULT_ZERO = "SZ-031"
    SZ_INVENTORY = "SZ-040"
    SZ_LEVERAGE = "SZ-041"
    SZ_MIN_TICKET = "SZ-042"
    SZ_ASSET_CROWDED = "SZ-043"      # per-asset same-side position count cap (variety rule)
    SZ_EXPLORE_FLOOR = "SZ-044"      # exploration ticket floored to min ticket (label acquisition)
    SZ_MANIP_SUSPECT = "SZ-045"      # entry downsized/vetoed under manipulation suspicion
    SZ_CIRCUIT_BREAKER = "SZ-046"    # asset paused: consecutive-loss circuit breaker
    SZ_PROBE_THROTTLED = "SZ-047"    # P3 (2026-07-23 P&L diagnosis): exploration
                                     # probe denied - rolling share cap over the
                                     # last probe_share_window entry admissions,
                                     # or corpus-decayed admission rate; falls
                                     # through as an ordinary (conviction) entry
                                     # attempt, never a hard veto of the signal
    SZ_PROBE_FLOOR = "SZ-048"        # F0b (2026-07-25 livelock repair): drought-
                                     # scoped floor admission - the share cap was
                                     # the binding denial AND no admissions of any
                                     # kind flowed for >= drought_hours, so one
                                     # rate-bounded probe is admitted instead of
                                     # starving the label stream (grill C2)
    SZ_PROBE_BUDGET_EXHAUSTED = "SZ-049"
                                     # SPB-R (2026-07-30 design): TRANSITION
                                     # pair, mode="budget" only - the token
                                     # bucket crosses into ("engaged") / out of
                                     # ("released") the tokens <= 0 state. The
                                     # "released" payload carries
                                     # {arrivals_denied, span_s, tokens} so the
                                     # audit trail BRACKETS and COUNTS every
                                     # denied arrival without per-event spam
                                     # (the SZ-047 practice produced a measured
                                     # 1,517-events/12h storm; a failed budget
                                     # roll is a NON-disposition, like a failed
                                     # epsilon/taper roll - conscious,
                                     # documented semantic change, spec §4)
    SZ_DD_THROTTLE = "SZ-050"        # informational: drawdown scaling applied
    SZ_PROBE_PRICED = "SZ-051"       # SPB-R informational: attached beside the
                                     # ML_EXPLORATION/ML_EXPLORE_AGGRESSIVE
                                     # admission record on every budget-mode
                                     # ADMIT - {asset, regime, cost, w_asset,
                                     # w_regime, surcharge, p, u, tokens_before,
                                     # tokens_after}; cost = clip(1/S, 1, C),
                                     # S = max(scarcity weights), deducted at
                                     # PLACEMENT (a downstream veto costs zero)
    SZ_PROBE_REFUND = "SZ-052"       # SPB-R informational: an UNFILLED probe
                                     # entry reached its order terminal
                                     # (fill_ratio == 0) and its placement-time
                                     # cost was refunded to the bucket -
                                     # {asset, cost_refunded, tokens_after}.
                                     # Partial/full fills never refund (the
                                     # position exists; ML-073 realizes the
                                     # label). Order-terminal-keyed: OM bounds
                                     # every entry's lifetime, nothing waits on
                                     # an event that may never come
    SZ_PROBE_TUITION_GOVERNOR = "SZ-053"
                                     # SPB-R TRANSITION only: the tuition
                                     # governor factor engaged / released
                                     # (crossing 1.0 either way) -
                                     # {tuition_24h_usd, cap_usd, factor}.
                                     # Clipped realized probe losses over a
                                     # trailing 86400 engine-s window scale the
                                     # refill rate by clip(cap/X, floor, 1) -
                                     # a BOUND, not an estimator; floored,
                                     # unlatched, self-redeeming as the window
                                     # rolls (probation, never a life sentence)
    SZ_INV_AGGRO = "SZ-060"          # inventory-aware aggression scaling applied
    SZ_INV_SKEW = "SZ-061"           # A-S reservation skew: signed-inventory-increasing entry scaled
    SZ_APPROVED = "SZ-000"

    # ---- risk protocol stack (advanced overlay) --------------------------
    RP_VOL_TARGET = "RP-010"         # vol-target scaling applied
    RP_CVAR_CAP = "RP-020"           # expected-shortfall budget capped size
    RP_GAP_CAP = "RP-030"            # gap-at-risk shock cap applied
    RP_BUDGET_TAPER = "RP-040"       # loss-budget taper active
    RP_BUDGET_EXHAUSTED = "RP-041"   # daily/weekly loss budget spent: no new risk
    RP_BUDGET_REANCHORED = "RP-042"  # operator re-anchored a loss budget (audited override for bug-attributable consumption; reason required)
    RP_HEAT_CAP = "RP-050"           # portfolio heat headroom capped size
    RP_HEAT_FULL = "RP-051"          # portfolio heat at max: no new risk
    RP_WARMUP = "RP-060"             # component neutral: insufficient observations
    RP_WEEK_CLOSED = "RP-070"        # weekly ledger: week closed, pools rolled
    RP_MONTH_CLOSED = "RP-071"       # monthly ledger: month closed, goal graded
    RP_GOAL_ESCALATED = "RP-072"     # goal ladder ratcheted: a month closed at
                                     # >=100% attainment, next month's effective
                                     # goal = base x mult (x1.5 per met month,
                                     # never down; stressor regime 2026-08-11)

    # ---- quoter / fair value ------------------------------------------
    QT_FEE_FLOOR = "QT-010"          # half-spread raised to structural floor
    FV_NO_INPUT = "FV-010"
    FV_INNOVATION_GATED = "FV-020"   # jump beyond gate: adaptive damping

    # ---- ML governance (ML) -------------------------------------------
    ML_CONTRACT_VIOLATION = "ML-010" # inference input outside data contract
    ML_ARTIFACT_HASH_FAIL = "ML-011" # model file failed integrity check
    ML_ARTIFACT_MISSING = "ML-012"
    ML_SCHEMA_MISMATCH = "ML-013"
    ML_CALIBRATION_SKIPPED = "ML-014"  # isotonic PAV had <20 OOF points to
                                        # fit; artifact ships uncalibrated
    ML_DIRTY_LABEL = "ML-015"        # non-finite (NaN/inf) feature or label
                                      # refused at the store boundary
    ML_LADDER_GATED = "ML-016"       # selection rung skipped: label evidence
                                      # can't support that model complexity
    ML_FAILSAFE_PRIOR = "ML-020"     # inference bypassed -> cold-start prior
    ML_LEVEL_CHANGE = "ML-030"
    ML_DRIFT = "ML-031"
    ML_RETRAIN_REQUEST = "ML-032"
    ML_DEPLOY = "ML-040"
    ML_DEPLOY_REJECT = "ML-041"
    ML_CHAMP_RESCORED = "ML-042"     # incumbent rescored on fresh OOF; badge realigned before gating
    ML_KILL_SWITCH = "ML-050"        # model output disabled (level 2+)
    ML_REGISTERED = "ML-060"         # artifact registered
    ML_EXPLORATION = "ML-070"        # dry-run paper exploration entry (active learning)
    ML_UNTEACHABLE_UNWIND = "ML-071"  # learning-phase unwind: full book, zero pending labels
    ML_EXPLORE_AGGRESSIVE = "ML-072"  # conviction-scaled full-size exploration
                                      # (confident model + clean book, dry-run)
    ML_LABEL_REALIZE = "ML-073"       # learning-phase: a dry-run position held
                                      # past its label horizon has resolved its
                                      # triple-barrier outcome — close it to
                                      # bank the live label + free a teach slot
    ML_PRIOR_SKEW = "ML-074"          # trailing-window label prior diverges
                                      # hard from the corpus prior (one-sided
                                      # batch, e.g. an all-zero quiet weekend):
                                      # calibration drift risk — detection only
                                      # (comment continuation reunited
                                      # 2026-08-17: it had drifted below
                                      # ML-076 and read as that code's
                                      # semantics)
    ML_SHADOW_RECOVER = "ML-075"      # killed champion re-armed 2->1 on a clean
    #                                   telemetry-only shadow window (probation)
    ML_CHAMP_BADGE_SYNC = "ML-076"    # champion badge realigned to the loaded
    #                                   model at startup (stale snapshot ghost)
    ML_LINEAGE_AGREEMENT = "ML-077"  # dedup-twin proxy-vs-realized label
    #   agreement stat (T2.2b): simulator-fidelity telemetry over
    #   gate-passing signals only - detection-only, weights untouched
    ML_SIM_DIVERGENCE = "ML-078"  # candidate-vs-live label-mean divergence
    #   inside live-covered time windows + coverage stat (T2.2a, C4
    #   surviving form) - detection-only, no reweighting authority
    ML_LINKAGE_REPORT = "ML-079"  # FS-EM corpus linkage report emitted
    #   (T2.4): probabilistically-linked live/candidate pairs + expanded
    #   agreement stat - report-only, no weight authority (Phase-4 gated)
    ML_BARRIER_MIX_DRIFT = "ML-080"  # label-era instrumentation (DEEP DIVE,
    #   progress.md): recent-window exit-reason mix diverges (TVD) from
    #   the trailing corpus past a config-lifted threshold - the missing
    #   instrument for the `trail` 49.5%->0.0% mix shift that silently
    #   collapsed the label rate. Report-only: never gates training,
    #   blocks a retrain, or changes a label/weight/row.
    ML_ERA_EXCLUSION_ACTIVE = "ML-081"  # era-gated training exclusion
    #   (operator decision, docs/quant/2026-07-26_era_exclusion.md)
    #   transitioned INACTIVE -> ACTIVE: the corpus's new-era
    #   (LABEL_ERA_TRIPLE_BARRIER) row count crossed ml.era_exclusion.
    #   min_new_era_rows (or forced_on), so load_training_data now
    #   excludes every old-era row - INCLUDING live ones (the operator's
    #   explicit override of ml.epoch's live-rows-never rule) - from the
    #   training view. Logged once per transition, never once per load;
    #   a load-time VIEW only, no row is ever removed from disk.
    ML_CHAMPION_ERA_ORPHAN = "ML-083"  # 2026-07-29 deploy-deadlock unlock:
    #   the loaded champion's trained_rows watermark EXCEEDS the entire
    #   current training matrix (era exclusion rebuilt the corpus
    #   population under it), so the like-for-like fresh-row set
    #   (oof_idx >= trained_rows) is empty BY CONSTRUCTION - now and on
    #   every future retrain until the corpus regrows past a watermark
    #   from a population that no longer exists. An unfalsifiable badge
    #   may not gate forever (ML-076 doctrine, degenerate case): the
    #   deploy gate applies the COLD-START standard with the badge set
    #   aside entirely (should_deploy ignore_champion=True: Brier < 0.25
    #   + deploy_min_oof) - the orphaned badge is a Brier measured on
    #   the dead population's base rate and is not comparable to any
    #   current-corpus score. No gate is widened beyond cold-start
    #   parity; the incumbent stays loaded until a challenger clears it.
    ML_BRACKET_DIVERGENCE = "ML-082"  # geometry-alignment T6 (spec D6)
    #   PROOF instrument: at every bracket-traded close (barrier in
    #   tb_pt/tb_sl/tb_time), compares the REALIZED net return against
    #   the LABELED counterfactual its own stamped pt_frac/sl_frac would
    #   imply (tb_pt -> +pt_frac*100-cost, tb_sl -> -sl_frac*100-cost,
    #   tb_time -> realized itself, since a time-barrier close has no
    #   fixed-distance counterfactual to diverge from) - "is the traded
    #   bet's outcome the labeled bet's outcome". Logged ONCE per close,
    #   rolled into a bounded window surfaced at status["ml"]["bracket_
    #   divergence"] (ml/history.py's bracket_divergence_summary()).
    #   Report-only: never gates an entry/exit/size decision, never
    #   reweights a row - the divergence itself is what D4's cost model
    #   is judged against, not the other way around.
    ML_UNLABELED_CLOSE = "ML-084"  # a position closed with NO pending
    #   feature vector, so no training row was written. log_close's
    #   `if entry is None: return` was the one exit in the whole write
    #   path with no log line and no counter, which made ground-truth
    #   attrition invisible: resolving a suspected 10.9% hole on
    #   2026-08-06 required forensic reconstruction from fills.csv
    #   because the corpus itself emitted no signal (it turned out to be
    #   34 quarantined QA fills plus 3 legitimate FEATURE_SCHEMA_VERSION
    #   drops - i.e. nothing was wrong, and that took hours to establish).
    #   Report-only: the close itself is unaffected.
    ML_CAND_ZOMBIE_EVICT = "ML-085"  # unresolvable candidate CENSORED: it
    #   outlived label_max_bars + ml.candidate_evict_margin_bars on the
    #   engine clock while its asset's cached bars provably could not
    #   produce the label (stale or absent feed). Before this code, the
    #   only drop rule for an unlabelable candidate was the bar-window
    #   SLIDE (bar_time < cache head), which needs NEW bars - so a dead
    #   feed squatted pool slots forever (measured 2026-08-16 on live
    #   state.json: 32/187 pending slots older than 38h against the 36h
    #   horizon; DOT held 17 slots with its bars cache 156h stale).
    #   CENSORED means exactly that: NO label row is written - an
    #   unresolvable candidate is missing data, not a tb_time outcome.
    #   Labeling plane only; never touches orders, sizing, or fills.
    ML_CAND_RESTORE_TRUNCATED = "ML-086"  # restored candidate pool exceeded
    #   ml.max_open_candidates (a cap DECREASE between runs): truncated to
    #   the cap at restore by dropping the NEWEST restored candidates -
    #   the same eviction direction register() uses at cap (the head of
    #   the list is closest to resolving; killing it wastes the most
    #   waiting). register() alone only holds pool size CONSTANT at the
    #   restored size (pop-then-append), so without this a shrunk cap was
    #   never enforced against a larger restored pool.
    ML_UNPARSEABLE_ROW = "ML-087"  # training-load row dropped because a cell
    #   would not parse. csv.DictReader is built with NO restval, so a SHORT
    #   row - what an interrupted/torn append leaves - yields None for every
    #   missing trailing field, and float(None) is a TypeError. Before this
    #   code that TypeError was OUTSIDE load_training_data's except tuple, so
    #   one torn tail made the whole corpus unreadable to EVERY consumer
    #   (overfit_check - a definition-of-done gate - train_meta, learning
    #   curve, feature stability, interpret) until a human edited the CSV;
    #   durable_append isolates the fragment in place, so it never healed on
    #   its own. The drop is now counted (last_load_stats["dropped_parse"])
    #   and logged, exactly like its ML-015 finiteness sibling: a row that
    #   vanishes without a counter is indistinguishable from one never
    #   written. Corpus/labeling plane only - never touches orders, sizing,
    #   fills or fees.

    # ---- profit-tier exit system (TP) -----------------------------------
    # NOTE (cross-reference, registry hygiene 2026-08-17): two EXIT-path
    # dispositions that would read as TP-family live under PT numbering
    # instead — PT-060 (time-stop scratch) and PT-061 (verbatim close
    # reason) continue the PT decade sequence per the P2 task spec even
    # though both fire from risk.profit_tiers' exit path, not
    # execution.pretrade. See their own entries in the PT block above.
    TP_SIGNAL_DECAY = "TP-010"       # runner leash tightened: entry signal decayed
    TP_INV_COUPLING = "TP-011"       # tier close boosted by inventory pressure
    TP_CONVICTION_LEASH = "TP-012"   # runner leash tightened: low entry conviction

    # ---- system fault manager (FT) -------------------------------------
    FT_LATCHED = "FT-010"
    FT_CLEARED = "FT-011"
    FT_STATE_CHANGE = "FT-020"

    # ---- THALES lazy-bot insecurity model (TH) — docs/THALES.md ---------
    TH_SHADOW = "TH-000"             # assessment recorded, zero influence
    TH_GRID_LADDER = "TH-010"        # grid-bot ladder footprint detected
    TH_METRONOME_MM = "TH-011"       # clock-driven market-maker cadence
    TH_CLOCKWORK_FLOW = "TH-012"     # recurring scheduled flow window (null-tested)
    TH_STOP_SWEEP = "TH-013"         # stop-cluster sweep-and-revert event
    TH_FEED_INTEGRITY = "TH-014"     # sustained missing/rejected feed data (hostile/unreliable venue)
    TH_BARCLOSE_HERD = "TH-015"      # activity herding in the first seconds after bar boundaries
    TH_LAPSE = "TH-016"              # observation gap: continuity reset, advice muted through warmup
    TH_SPOOF_FLICKER = "TH-017"      # large top-of-book level pulled untraded: imbalance untrusted
    TH_CONF_SHADE = "TH-020"         # advise mode: bounded confidence shade applied
    TH_CONCENTRATION_SHADE = "TH-021"  # diffuse-and-marginal signal trimmed (averaging trap)

    # ---- runner lifecycle (RT) — runner.py single-instance lock ---------
    # (refiled out of the THALES section 2026-08-17: RT-010 fires from the
    # runner's SingleInstanceLock heartbeat, nothing to do with detectors)
    RT_DUPLICATE_RUNNER = "RT-010"   # lost the instance lock to a live peer: this runner self-terminates

    # ---- remote control (RC) — scripts/remote_control.py ----------------
    RC_APPLIED = "RC-010"            # remote command validated and forwarded to the runner's control queue
    RC_REJECTED = "RC-011"           # remote command refused (whitelist / stale / malformed)

    # ---- execution-truth harness (XV) — replay gate + fill calibration
    # + cost truth + gate truth -------------------------------------------
    XV_GATE_PASS = "XV-000"  # nosec B105 - reason code, not a secret (name has "PASS")
    XV_GATE_SKIP = "XV-001"          # no recordings present — gate dormant (not a fail)
    XV_DETERMINISM_FAIL = "XV-010"   # two replays of one recording disagree (engine regression)
    XV_RECONCILE_MISMATCH = "XV-011"  # self-contained recording: replay P&L != live delta
    XV_RECONCILE_WARN = "XV-012"     # replay P&L != live delta but recording not self-contained
    XV_CALIB_DEFERRED = "XV-020"     # fill calibration underpowered/not-near-touch: no recommendation
    XV_CALIB_RECOMMEND = "XV-021"    # fill calibration recommends a passive_base_prob change
    XV_CALIB_MISSPECIFIED = "XV-022"  # per-distance buckets disagree: forward model misspecified
    # XV-023 RESERVED (not yet a member): per-TTL fill-calibration verdict,
    # to be registered when calibrate_fills gains long-life recording
    # buckets — core/fill_calibration.py's module docstring and the
    # calibration_life_sec config _doc both cite it by number (registry
    # hygiene 2026-08-17: a cited-but-unregistered number is either
    # reserved HERE or it is a dangling reference)
    # cost_truth_report (T7, spec D4 "measured, never assumed") - report-only
    # verdicts comparing measured realized cost against configured
    # pretrade.maker_fee_bps/taker_fee_bps; never printed via tag() (a one-off
    # CLI report must not bump the live process's code_stats tally).
    XV_COST_INSUFFICIENT = "XV-030"  # a measured source has zero usable samples
    XV_COST_WITHIN_TOLERANCE = "XV-031"  # measured within D4's +/-20% tolerance
    XV_COST_OUTSIDE_TOLERANCE = "XV-032"  # outside tolerance, configured overestimates (conservative direction)
    XV_COST_DANGEROUS = "XV-033"     # measured EXCEEDS configured beyond tolerance - gate underprices real cost
    # gate_truth_report (gate-truth instrumentation, T5) - report-only verdict
    # comparing configured informed_flow.weights rank order against realized
    # per-component AUC (sg_* telemetry x direction, triple_barrier rows).
    XV_GATE_TRUTH_ALIGNED = "XV-040"     # gate weights rank-agree with realized component AUCs
    XV_GATE_TRUTH_MISALIGNED = "XV-041"  # weight order contradicts measured discrimination
    XV_GATE_TRUTH_THIN = "XV-042"        # < SG_MIN_ROWS instrumented era rows — no verdict
    # fill_hazard_report (TANK quant-2 Debate-1 L1) - report-only verdict
    # comparing the sim's CONSTANT per-poll maker-fill probability against
    # the fitted discrete hazard from recorded book frames; never tag()'d.
    XV_HAZARD_SHAPE_OK = "XV-050"        # constant-hazard shape within threshold at the timeout horizon (close L2)
    XV_HAZARD_MISSTATED = "XV-051"       # constant hazard misstates cumulative fill beyond threshold (L2 justified)
    XV_HAZARD_INSUFFICIENT = "XV-052"    # recordings underpowered for a hazard-shape verdict (L2 unadjudicated)

    # ---- liquidity-tier isolation (LT) — regime/liquidity_regime.py ------
    LT_TIER_ASSIGNED = "LT-010"      # asset (re)classified into a liquidity
                                     # cap-tier from its trailing-median depth;
                                     # the tier scales the executability floors
                                     # (depth / spread) so a low-volume asset is
                                     # judged on its own scale, never ETH/BTC's

    # ---- cross-asset correlation / turbulence (CR) — regime/correlation.py
    CR_TURBULENCE_HELD = "CR-010"    # update_turbulence could not recompute
                                     # (one of five early returns: too few
                                     # usable assets, no / bad day step, too
                                     # few shared daily bars, too few
                                     # returns) and the PREVIOUS reading
                                     # stands. That scalar feeds
                                     # regime/macro_regime.py's crisis
                                     # clause, so a held value keeps gating
                                     # the whole book while looking fresh
                                     # (2026-08-22 turbulence verification,
                                     # D6: no timestamp, no sample count,
                                     # no flag, no code existed). Latched:
                                     # ONE emission per hold episode - the
                                     # hourly recompute would otherwise
                                     # reprise SZ-047 (63% of a 35,530-line
                                     # audit trail). The live reason rides
                                     # status.correlation.hold_reason.
    CR_TURBULENCE_FRESH = "CR-011"   # a recompute succeeded after a CR-010
                                     # episode: reading live again, stamped
                                     # with computed_at + sample_count

    # ---- logistic-armed grid entry ladder (GL) — execution/grid_ladder.py -
    GL_PLANNED = "GL-000"            # ladder planned: N decay-sized maker rungs
    GL_ARMED = "GL-010"              # p(win) cleared the arm bar: laddering on
    GL_RETRACTED = "GL-011"          # ladder retracted (disarm / spoofy / manip
                                     # / direction flip / invalid inputs)
    GL_BELOW_ARM = "GL-020"          # single-entry fallback: p(win) below arm
    GL_RUNG_CAPPED = "GL-021"        # rung count capped by free position slots
                                     # / per-asset same-side inventory cap
    GL_RUNG_EV_VETO = "GL-022"       # W2-10: a rung past rung 0 re-checked the
                                     # gate's own p_fill-weighted EV at its
                                     # actual (deeper) offset distance and
                                     # came back below the floor -- skipped,
                                     # shallower already-accepted rungs stand

    # ---- hedge-open new-risk gate (HG) — main._hedge_actions ------------
    HG_OPEN_BLOCKED = "HG-010"       # hedge OPEN refused: a hedge open is NEW
                                     # risk (invariant #5), so it is held to
                                     # the same bar as entries - stale mark,
                                     # halt, fault manager, watchdog data-
                                     # quality block, or the entries kill
                                     # switch. Unwind/trim are risk reduction
                                     # and are never gated here.

    # ---- config guard (CG) — main.LiquidityBot.__init__ session start ---
    CG_SESSION_START = "CG-000"      # session fingerprint: config passed
                                     # enforce_config() and was armed under
                                     # this sha256/dry_run/fee combination
                                     # (W2-19: was a bare "CG-000" string,
                                     # unregistered despite the prefix map
                                     # advertising CG)

    # ---- conviction formula (CV) — risk/conviction.py (Compounder A) ----
    CV_ADMIT = "CV-000"              # all terms agree: conviction admitted
    CV_AGREEMENT_LOW = "CV-010"      # gate-stack agreement below floor
    CV_EV_MULTIPLE_LOW = "CV-020"    # edge fails ev_cost_mult x the pretrade
                                     # gate's MEASURED round-trip cost stack
    CV_REGIME_UNKNOWN = "CV-030"     # current regime below the T4 live-label
                                     # coverage floor (or unmapped): no
                                     # evidence, no conviction
    CV_CONTEXT_MISALIGNED = "CV-040" # long-book context term: emitted by the
                                     # formula; no engine call site passes
                                     # context_aligned until the context
                                     # engine (Phase B) + long book (Phase C)
    CV_CADENCE_HIGH = "CV-050"       # governor: admit share above share_hi -
                                     # the formula has gone vacuous (always-on)
    CV_CADENCE_LOW = "CV-051"        # governor: admit share below share_lo -
                                     # the formula is starving conviction flow

    # ---- context engine (CX) — data.context_engine (Compounder Phase B) --
    CX_POLL_OK = "CX-000"            # scheduled poll completed: context
                                     # snapshot refreshed (telemetry only -
                                     # no gate on this codebase reads it yet)
    CX_SOURCE_DARK = "CX-010"        # a context source went dark past its
                                     # grace window: component degrades to
                                     # known=False, a STATE, never a stale
                                     # value presented as fresh
    CX_STATE_CHANGE = "CX-020"       # a bucketed/discrete context state
                                     # (halving phase, event-window flag)
                                     # flipped since the last poll
    CX_CONTEXT_UNKNOWN = "CX-030"     # Phase C long-book context add-block
                                      # disposition: context stress dial
                                      # unknown and long_book.context.
                                      # require_known is true - the add is
                                      # blocked (rides along with LB-050 on
                                      # main._long_book_cycle's "context_
                                      # unknown" DenyReason from
                                      # LongBookEngine.decide_add)

    # ---- data feeds (DF) — data/moomoo_feed.py -----------------------
    DF_QUOTES_FROZEN = "DF-010"      # full-basket freeze: every per-ticker
                                     # return identical to the previous
                                     # poll (the closed-market signature -
                                     # three liquid names byte-identical is
                                     # not a quiet market). Window append
                                     # suppressed so the z holds its last
                                     # honest value instead of decaying
                                     # (input-feed audit 2026-08-07: 93% of
                                     # a closed day's polls were duplicate
                                     # appends, z decayed +0.39 -> 0.00;
                                     # weekends inject ~62h of it).
                                     # Latched: one log per episode.
    DF_QUOTES_RESUMED = "DF-011"     # basket moving again after a DF-010
                                     # episode: window appends resume
    DF_CONTEXT_DEGRADED = "DF-020"   # feature rows are being built while a
                                     # context source (webdata / moomoo
                                     # equity / moomoo options) is dark or
                                     # frozen - the affected features carry
                                     # neutral values byte-identical to
                                     # genuine neutral (input-feed audit
                                     # 2026-08-07: failure == neutral ==
                                     # padding on the ML path). Latched:
                                     # one log per degradation episode;
                                     # rows record avail_* flags.
    DF_CONTEXT_RECOVERED = "DF-021"  # every context source back and
                                     # unfrozen after a DF-020 episode

    # ---- long-horizon book (LB) — risk/long_book.py (Compounder C) ----
    LB_ADD_PLACED = "LB-000"         # accumulation add order placed (paper/live)
    LB_ADD_DENIED = "LB-010"         # add refused (detail names the gate:
                                     # conviction/ladder/inventory/sizer/risk)
    LB_ZONE_SHIFT = "LB-020"         # bid shifted off a TH-013 magnet zone
                                     # (ladder hygiene; price only ever moves
                                     # AWAY from the magnet, deeper)
    LB_BID_REPRICED = "LB-021"       # market-conduct pass (F8): resting
                                     # long-book bid cancelled-and-replaced
                                     # because it drifted past the
                                     # add_offset_pct + zone_buffer_pct +
                                     # zone_tol_pct staleness band vs mark
                                     # - a dedicated code, replacing the
                                     # prior LB_ADD_DENIED kind="reprice"
                                     # overload (nothing was denied: the
                                     # SAME add replaces at a fresh level
                                     # this same pass)
    LB_BID_CLEARED = "LB-022"        # market-conduct pass (F6): Rule 534
                                     # self-cross guard - own same-pair
                                     # resting long-book bid cancelled
                                     # before a marketable sell - cancel-
                                     # first so the exit is never delayed;
                                     # risk-reducing by construction (an
                                     # ENTRY is cancelled to clear an EXIT)
    LB_TIER_BANK = "LB-030"          # long-book tier take (partial bank)
    LB_THESIS_INVALIDATED = "LB-031" # structural stop hit: full close
    LB_RUNG_UP = "LB-040"            # evidence ladder rung upgrade (gated)
    LB_RUNG_DOWN = "LB-041"          # instant downgrade (dd breach)
    LB_ADVERSE_SURVIVED = "LB-042"   # a risk-off context episode ended with
                                     # the book holding exposure throughout
                                     # and drawdown staying under the
                                     # downgrade line - EvidenceLadder.
                                     # note_adverse_transition_survived()
                                     # (task C5, C4-review item 3(b)); NOT
                                     # LB-040 (rung up) - the rung itself
                                     # only rises later, once r3's full
                                     # gate (closed_live + pf + this count)
                                     # clears, which stays coded LB-040
    LB_PAUSED = "LB-050"             # add cadence paused (event window /
                                     # contraction phase / context unknown /
                                     # crisis regime - CX-030 rides along
                                     # for the unknown case)


def tag(code: Code, detail: str) -> str:
    """Canonical 'CODE: detail' string used in reasons lists and audit. Also
    bumps the process-global code tally (core.code_stats) so the FREQUENCY of
    every emitted code is countable — the central ledger the codes never had.
    The bump never raises, so telemetry cannot wedge a decision path.

    SECOND LANE (2026-08-17): AuditTrail.log() also bumps the tally for
    audit-only emissions (plain-msg records — the ML/OM/FT/RP-period lane
    that tag() never saw). One emission counts once either way: log()
    recognizes a tag()-built msg by its "CODE: " prefix and skips the
    re-bump, and call sites that tag() the code into a DIFFERENT string of
    the same emission pass log(..., counted=True). See core/audit.py."""
    code_stats.bump(code.value)
    return f"{code.value}: {detail}"
