"""
core/codes.py — global reason-code registry (Assurance Build)

One canonical, stable vocabulary for every machine decision in the
system. Every reject, clamp, override, fault, and model-governance
action carries exactly one code from this registry, in the form
"XX-NNN: human detail". Codes are append-only: a code, once shipped,
is never renumbered or reused (audit trails must stay interpretable
forever).

Prefix map (subsystem of origin):
  FW  execution.risk_firewall     PT  execution.pretrade
  OM  execution.order_manager     SZ  risk.position_sizer
  QT  execution.market_maker      FV  execution.fair_value
  ML  ml.* (contracts/registry/monitor)
  WD  core.watchdog               CG  core.config_guard
  FT  core.fault (system-level faults / state transitions)
  TP  risk.profit_tiers (exit-system dispositions)
  TH  strategies.thales (lazy-bot insecurity detectors / advice)
  RC  scripts.remote_control (git command-bus dispositions)
  XV  execution-truth harness (replay gate + fill-model calibration)
  LT  regime.liquidity_regime (asset liquidity-tier isolation)
  GL  execution.grid_ladder (logistic-armed grid entry ladder)
  HG  execution.hedging / main._hedge_actions (hedge-open new-risk gate)
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
    OM_FIREWALL_REJECT = "OM-020"
    OM_VENUE_REJECT = "OM-021"
    OM_ILLEGAL_TRANSITION = "OM-030" # order state machine violation
    OM_TIMEOUT_CANCEL = "OM-040"
    OM_DEADMAN_FAIL = "OM-050"
    OM_EXIT_PREEMPT = "OM-060"       # risk-off exit cancelled a resting maker take
    OM_FILL_APPLY_FAILED = "OM-070"  # _handle_fill raised on one poll event; the
                                     # rest of the batch is still applied and
                                     # snapshotted (no book/venue desync, no lost fill)

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
    SZ_DD_THROTTLE = "SZ-050"        # informational: drawdown scaling applied
    SZ_INV_AGGRO = "SZ-060"          # inventory-aware aggression scaling applied
    SZ_INV_SKEW = "SZ-061"           # A-S reservation skew: signed-inventory-increasing entry scaled
    SZ_APPROVED = "SZ-000"

    # ---- risk protocol stack (advanced overlay) --------------------------
    RP_VOL_TARGET = "RP-010"         # vol-target scaling applied
    RP_CVAR_CAP = "RP-020"           # expected-shortfall budget capped size
    RP_GAP_CAP = "RP-030"            # gap-at-risk shock cap applied
    RP_BUDGET_TAPER = "RP-040"       # loss-budget taper active
    RP_BUDGET_EXHAUSTED = "RP-041"   # daily/weekly loss budget spent: no new risk
    RP_HEAT_CAP = "RP-050"           # portfolio heat headroom capped size
    RP_HEAT_FULL = "RP-051"          # portfolio heat at max: no new risk
    RP_WARMUP = "RP-060"             # component neutral: insufficient observations
    RP_WEEK_CLOSED = "RP-070"        # weekly ledger: week closed, pools rolled
    RP_MONTH_CLOSED = "RP-071"       # monthly ledger: month closed, goal graded

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
    ML_SHADOW_RECOVER = "ML-075"      # killed champion re-armed 2->1 on a clean
    #                                   telemetry-only shadow window (probation)
    ML_CHAMP_BADGE_SYNC = "ML-076"    # champion badge realigned to the loaded
    #                                   model at startup (stale snapshot ghost)
                                      # hard from the corpus prior (one-sided
                                      # batch, e.g. an all-zero quiet weekend):
                                      # calibration drift risk — detection only

    # ---- profit-tier exit system (TP) -----------------------------------
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
    RT_DUPLICATE_RUNNER = "RT-010"   # lost the instance lock to a live peer: this runner self-terminates
    RC_APPLIED = "RC-010"            # remote command validated and forwarded to the runner's control queue
    RC_REJECTED = "RC-011"           # remote command refused (whitelist / stale / malformed)

    # ---- execution-truth harness (XV) — replay gate + fill calibration ---
    XV_GATE_PASS = "XV-000"  # nosec B105 - reason code, not a secret (name has "PASS")
    XV_GATE_SKIP = "XV-001"          # no recordings present — gate dormant (not a fail)
    XV_DETERMINISM_FAIL = "XV-010"   # two replays of one recording disagree (engine regression)
    XV_RECONCILE_MISMATCH = "XV-011"  # self-contained recording: replay P&L != live delta
    XV_RECONCILE_WARN = "XV-012"     # replay P&L != live delta but recording not self-contained
    XV_CALIB_DEFERRED = "XV-020"     # fill calibration underpowered/not-near-touch: no recommendation
    XV_CALIB_RECOMMEND = "XV-021"    # fill calibration recommends a passive_base_prob change
    XV_CALIB_MISSPECIFIED = "XV-022"  # per-distance buckets disagree: forward model misspecified

    # ---- liquidity-tier isolation (LT) — regime/liquidity_regime.py ------
    LT_TIER_ASSIGNED = "LT-010"      # asset (re)classified into a liquidity
                                     # cap-tier from its trailing-median depth;
                                     # the tier scales the executability floors
                                     # (depth / spread) so a low-volume asset is
                                     # judged on its own scale, never ETH/BTC's

    # ---- logistic-armed grid entry ladder (GL) — execution/grid_ladder.py -
    GL_PLANNED = "GL-000"            # ladder planned: N decay-sized maker rungs
    GL_ARMED = "GL-010"              # p(win) cleared the arm bar: laddering on
    GL_RETRACTED = "GL-011"          # ladder retracted (disarm / spoofy / manip
                                     # / direction flip / invalid inputs)
    GL_BELOW_ARM = "GL-020"          # single-entry fallback: p(win) below arm
    GL_RUNG_CAPPED = "GL-021"        # rung count capped by free position slots
                                     # / per-asset same-side inventory cap

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


def tag(code: Code, detail: str) -> str:
    """Canonical 'CODE: detail' string used in reasons lists and audit. Also
    bumps the process-global code tally (core.code_stats) so the FREQUENCY of
    every emitted code is countable — the central ledger the codes never had.
    The bump never raises, so telemetry cannot wedge a decision path."""
    code_stats.bump(code.value)
    return f"{code.value}: {detail}"
