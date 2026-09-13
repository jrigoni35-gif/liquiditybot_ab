"""
core/config_guard.py

Startup config validation. The most likely catastrophic failure in a
mature system is not a bug - it is an operator editing config.json at
2am. This module checks the invariants that the rest of the system
silently assumes, and refuses to start live trading on a config that
violates them. In dry-run, violations warn instead of block (paper is
for finding exactly these mistakes).

Checks (each maps to a real historical failure mode somewhere):
  * fees vs Kraken's public floor - understating your fee tier makes
    the pre-trade edge gate approve trades that are net losers.
    Kraken spot bottom tier is 25 bps maker / 40 bps taker; a config
    below that is almost certainly wrong unless explicitly overridden.
  * fee consistency - pretrade and order_manager carry independent fee
    settings; if they drift apart, the gate and the PnL ledger disagree.
  * risk ladder ordering - daily_loss_limit < hard_stop_drawdown,
    soft inventory cap < hard cap, tier triggers strictly increasing,
    tier close percentages <= 100 total.
  * live capital - starting_capital_usd must be > 0 in live mode. The
    silent "0 means 10k paper default" behavior is dry-run only.
  * bounds - polling interval, slippage, leverage caps, stop widths
    all positive and sane.

Returns a list of (severity, message); severity is "FATAL" or "WARN".
`enforce()` raises ConfigError on any FATAL when live.
"""

import logging
import math
import re
from typing import Any

from regime.vol_regime import FAST_WARMUP_BARS

log = logging.getLogger("liquiditybot.core.config_guard")

# Kraken spot venue-true Tier-1 (cut #8, exec_era 8-ca55e2ba, 2026-08-28):
# 40/80 bps, the schedule the shipped config runs at and PnL books against.
# If configured fees are below this the operator either has real volume tier
# discounts (set allow_sub_floor_fees) or has misconfigured. This floor is
# the whole reason the FATAL below exists ("understated fees make the
# pre-trade gate approve net-losing trades") - it MUST sit at venue truth,
# not the retired public bottom tier (25/40, pre-cut-#8), or the gate would
# silently pass any config in [25/40, 40/80), i.e. up to half the true taker
# leg. Was 25/40 through cut #8; corrected to venue truth 2026-08-29
# (measured stale-floor finding, injection-confirmed). Strict `<` keeps the
# live 40/80 config passing exactly at the floor.
# CORRECTED 2026-09-05, AND THAT CORRECTION WAS ITSELF WRONG (2026-09-08).
#
# On 09-05 this block declared, from a read of /0/public/AssetPairs, that the
# rows were 25/40, 20/35, 14/24 ... and that "40/80 is not a row, and neither
# is 22/38". That endpoint was still serving Kraken's LEGACY ladder (by 09-08
# it serves no fee arrays at all); the venue's fee page and the operator's
# 2026-08-29 app screenshot both carry the CURRENT ladder: Tier 1 40/80 at
# $0, Tier 2 30/60 at $2.5K, Tier 3 22/38 at $10K, Tier 4 20/35 at $25K ...
# 0/5 at $500M, granted by the best of 30-day volume OR assets on platform.
# So 40/80 IS the zero-volume row after all (cut #8 had the row, not the
# account); 22/38 IS Tier 3 (cut #9 was right); and cut #10's E1 "correction"
# to 20/35 booked Tier 4, which needs $25,000 of volume or $50k on platform.
# The floor is DERIVED from core/venue_fees, which is diffed against the live
# PAGE by scripts/fee_drift_report.py - a constant that cannot confirm
# itself, read from the wrong source, is how this went wrong THREE times.
#
# The floor's meaning is unchanged: no spot account pays LESS than the
# zero-volume row unless it has earned a volume discount, which is exactly
# what pretrade.allow_sub_floor_fees declares.
from core.venue_fees import best_possible_row as _venue_best_row  # noqa: E402
from core.venue_fees import worst_row as _venue_worst_row  # noqa: E402

KRAKEN_SPOT_FLOOR_MAKER_BPS, KRAKEN_SPOT_FLOOR_TAKER_BPS = _venue_worst_row()

# Entry-signal engines main.py:540 can dispatch. NOT a tunable: this is a
# statement of what the code can construct, so it belongs beside the module
# it mirrors, not in config.json. Adding an engine means editing main.py's
# dispatch AND this tuple in the same change.
KNOWN_SIGNAL_ENGINES = ("informed_flow", "five_gate")
# main.py:540's own fallback when strategies.engine is absent. Mirrored (not
# chosen) so the guard reports on the engine that will actually run; it
# disagrees with config.json's shipped "informed_flow" on purpose - that
# disagreement is the finding, and the guard's job is to say so out loud.
_MAIN_ENGINE_FALLBACK = "five_gate"

# scripts/overfit_check.py load_dataset's rows-per-feature multiplier. The
# battery's corpus floor is len(FEATURE_NAMES) * this; under it the WHOLE OF
# battery silently substitutes a planted-signal SYNTHETIC benchmark. MIRRORED
# (not chosen), same contract as _MAIN_ENGINE_FALLBACK above: the guard must
# report on the floor that will actually run, so this tracks overfit_check's
# own `min_rows = len(FEATURE_NAMES) * 10` line and moves only when that line
# does (tests/test_config_guard_era_overfit_floor.py pins the pair). It is a
# measurement standard, NOT a tunable (CLAUDE.md) - lowering it so a gate
# reads "real" is exactly the widening the overfit discipline forbids. The
# feature count itself is deliberately NOT mirrored here: it is imported
# lazily at check time so the floor cannot go stale against the live feature
# contract.
_OVERFIT_ROWS_PER_FEATURE = 10

# ml/history.py CandidateLabeler's own fallback when ml.max_open_candidates
# is absent from config - MIRRORED (not chosen), same contract as
# _MAIN_ENGINE_FALLBACK above: the capacity check below must size the cap
# that will actually run, and a config that never declares the key runs
# this one. tests/test_candidate_capacity_guard.py regex-pins it against
# ml/history.py's own `cfg.get("max_open_candidates", N)` line so the
# mirror cannot drift silently.
_CAND_QUEUE_CODE_DEFAULT = 200

# ml/calibration.py calibration_gap()'s own `n_bins` default. MIRRORED (not
# chosen), same contract as _MAIN_ENGINE_FALLBACK / _OVERFIT_ROWS_PER_FEATURE
# above: calibration_gap RETURNS 0.0 - the perfectly-calibrated value, not a
# "no data" sentinel - for any window shorter than n_bins, and ml/monitor.py
# _judge feeds that raw into two of its three verdict clauses. So this is the
# sample count below which the governor's calibration test cannot convict,
# and the lower bound on min_trades_to_judge is exactly it.
# tests/test_config_guard_governor_floor_and_exit_leg.py regex-pins this
# against calibration_gap's own `def` line so the mirror cannot drift.
_CALIBRATION_MIN_BINS = 5

# Reference PEAK candidate arrival rate (registrations/hour) for the
# Little's-law capacity check below. MEASURED, not chosen: 659 offered
# registrations inside the densest 36h signal_ts window of the
# triple_barrier_h432 era (2026-08-13T04:45Z..2026-08-14T16:45Z), exact by
# candidate-id seq arithmetic over outputs/signal_history.csv (read
# 2026-08-16; the id embeds a monotone per-append seq, so the seq delta
# between two rows counts every registration between them - labeled,
# evicted, and dropped alike). 659/36h = 18.3/h sustained. The MEAN rate
# over the same era (5.5-9.3/h by two routes) is deliberately NOT the
# sizing basis: a queue sized to the mean saturates in every busy stretch,
# and the newest-pop eviction then refuses labeling to exactly the
# busy-hour signals. Re-derive from signal_history.csv the same way before
# moving this; it is a measurement, and moving it without a new
# measurement is how the 8h-era cap survived a 36h horizon.
_CAND_REF_PEAK_ARRIVALS_PER_H = 43.7
# MOVED AT CUT #10 (B6, 2026-09-06), and moved WITH ml.max_open_candidates
# (1200 -> 1800) in the same operator-adjudicated boundary. Re-derived the
# SAME WAY the docstring above demands - max seq-span over a rolling window of
# exactly the label horizon (36h = label_max_bars 432 x 5m), per lineage,
# full-width windows only (>= 95% of 36h) - on the full corpus at the time
# (outputs/signal_history.csv, 25,840 rows, 337 lineages, 7,528 qualifying
# windows): max 43.7/h (lineage 97211d06), p99 43.1, p95 42.5, median 37.5.
# Two independent derivations agree on 43.7 to the tenth. The shipped 18.3
# was the same statistic measured 2026-08-16 on a single 36h window three
# weeks earlier; the corpus outgrew it 2.4x. Demand at 43.7/h x 36h = 1574
# slots; the cap is set with ~15% headroom.
#
# WHAT WAS SETTLED FIRST, because the first attempt got it wrong: an hourly
# BIN of the same data reads peak 75/h, p95 46, MEDIAN 17 - which made 18.3
# look like "the median mislabelled as a peak". It is not. This check is
# Little's law over the HORIZON, so the horizon-window sustained rate is the
# statistic, and on that statistic 18.3 was simply stale. A sliding window
# that floored its span at 1s produced 21,600/h and was discarded as a broken
# scan. Re-derive on the horizon window, never on hour bins, before moving
# this again.


class ConfigError(RuntimeError):
    pass


def _f(cfg: dict, path: str, default: Any = None) -> Any:
    """Walk a dotted path through arbitrary JSON. Returns `default` on
    any missing segment. Return type is Any because config values can
    legitimately be any JSON scalar or nested structure; callers cast
    (float/bool/int) at the site where they know what they expect."""
    cur: Any = cfg
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _conviction_checks(config: dict) -> list:
    """Compounder Phase A conviction block coherence (spec §2/§6):
    FATAL = the formula would be vacuous or self-contradictory. An
    absent block is clean — risk/conviction.py module defaults apply."""
    out: list = []
    conv = _f(config, "conviction")
    if not isinstance(conv, dict) or not conv:
        return out
    mode = str(conv.get("mode", "report"))
    if mode not in ("report", "enforce"):
        out.append(("FATAL", f"conviction.mode '{mode}' must be "
                    "'report' or 'enforce'"))
    floor = float(conv.get("agreement_floor", 0.75))
    if not 0.0 <= floor <= 1.0:
        out.append(("FATAL", f"conviction.agreement_floor {floor} "
                    "outside [0, 1]"))
    mult = float(conv.get("ev_cost_mult", 2.0))
    base = float(_f(config, "pretrade.min_edge_cost_ratio", 1.3))
    if mult < base:
        out.append(("FATAL", f"conviction.ev_cost_mult {mult} below "
                    f"pretrade.min_edge_cost_ratio {base} — a conviction "
                    "bar under the pretrade bar is vacuous"))
    lo = float(conv.get("share_lo", 0.1))
    hi = float(conv.get("share_hi", 0.9))
    if not (0.0 <= lo < hi <= 1.0):
        out.append(("FATAL", f"conviction share band [{lo}, {hi}] must "
                    "satisfy 0 <= lo < hi <= 1"))
    window = int(conv.get("share_window", 40))
    min_n = int(conv.get("share_min_n", 20))
    if window < 1 or not 1 <= min_n <= window:
        out.append(("FATAL", f"conviction share_window {window} / "
                    f"share_min_n {min_n} incoherent (need window >= 1, "
                    "1 <= min_n <= window)"))
    return out


def _context_checks(config: dict) -> list:
    """Compounder Phase B context engine block coherence (spec §3,
    task-B3 brief): FATAL = the context feed would be structurally
    broken (a plaintext-http source url, an incoherent phase-bucket
    ladder, a degenerate scale/clip that zeroes clip_z, a negative
    event-window half-width). An absent block is clean —
    data/context_engine.py's own defaults apply; this phase is
    telemetry-only regardless of the block's presence."""
    out: list = []
    ctx = _f(config, "context")
    if not isinstance(ctx, dict) or not ctx:
        return out

    poll_hours = float(ctx.get("poll_hours", 6.0))
    if poll_hours < 1.0:
        out.append(("FATAL", f"context.poll_hours ({poll_hours}) must be "
                    ">= 1 - polling faster hammers free/keyless endpoints "
                    "(FRED/CFTC/DefiLlama) with no rate-limit headroom"))

    buckets = ctx.get("phase_bucket_days", {}) or {}
    order = ("accumulation", "expansion", "euphoria", "contraction")
    if not all(k in buckets for k in order):
        out.append(("FATAL", f"context.phase_bucket_days must have all "
                    f"four keys {order}"))
    elif list(buckets.keys()) != list(order):
        out.append(("FATAL", f"context.phase_bucket_days key order "
                    f"{list(buckets.keys())} must be exactly {list(order)} "
                    "- data/context_engine.py's phase_bucket() iterates "
                    "dict INSERTION order, not this canonical order, so a "
                    "reordered-but-value-monotonic dict would silently "
                    "mislabel every halving phase"))
    else:
        prev_v = float("-inf")
        for k in order:
            v = float(buckets[k])
            if v <= prev_v:
                out.append(("FATAL", f"context.phase_bucket_days not "
                            f"strictly increasing at '{k}' ({v} <= "
                            f"{prev_v}) - phase_bucket would clamp/skip a "
                            "bucket"))
            prev_v = v

    stress = ctx.get("stress", {}) or {}
    for key, default in (("dff_scale", 0.5), ("t10y2y_scale", 0.5),
                         ("vix_scale", 10.0), ("clip", 2.0)):
        v = float(stress.get(key, default))
        if v <= 0:
            out.append(("FATAL", f"context.stress.{key} ({v}) must be > 0 "
                        "- clip_z divides by scale/clips at this bound"))

    flow = ctx.get("flow", {}) or {}
    for key, default in (("cot_scale", 5000.0), ("stable_scale_pct", 2.0),
                         ("clip", 2.0)):
        v = float(flow.get(key, default))
        if v <= 0:
            out.append(("FATAL", f"context.flow.{key} ({v}) must be > 0 - "
                        "clip_z divides by scale/clips at this bound"))

    ew = ctx.get("event_window", {}) or {}
    for key, default in (("fomc_pre_h", 24.0), ("fomc_post_h", 6.0),
                         ("expiry_pre_h", 8.0), ("expiry_post_h", 2.0)):
        v = float(ew.get(key, default))
        if v < 0:
            out.append(("FATAL", f"context.event_window.{key} ({v}) must "
                        "be >= 0 - a negative half-width is nonsense"))

    urls = ctx.get("urls", {}) or {}
    for key, url in urls.items():
        if not (isinstance(url, str) and url.lower().startswith("https://")):
            out.append(("FATAL", f"context.urls.{key} ({url!r}) must be "
                        "https:// - free/keyless endpoints only, never "
                        "plaintext http"))
    return out


def _long_book_checks(config: dict) -> list:
    """Compounder Phase C long_book block coherence (task-C2 brief,
    risk/long_book.py): FATAL = the evidence ladder or the accumulation
    config would be structurally broken or exit-incoherent. An absent
    block is clean - risk/long_book.py's own defaults apply. Long-only
    by construction: this block has no direction/side key to check
    (long_book adds are unconditionally accumulation-side; a future
    spec must earn shorts per docs/superpowers/specs/
    2026-07-24-compounder-framework-design.md §5)."""
    out: list = []
    lb = _f(config, "long_book")
    if not isinstance(lb, dict) or not lb:
        return out

    # --- assets: non-empty, string-typed, subset of Kraken's configured
    # trading universe (base symbol before the "/", e.g. "BTC/USD" ->
    # "BTC") - fully derivable from config.json itself, no runtime data
    # needed, so this checks real membership rather than type-only.
    assets = lb.get("assets", []) or []
    if not assets:
        out.append(("FATAL", "long_book.assets must be non-empty - the "
                    "long book needs at least one asset to accumulate"))
    else:
        pairs = _f(config, "exchanges.kraken.trading_pairs", []) or []
        universe = {str(p).split("/")[0] for p in pairs}
        for a in assets:
            if not isinstance(a, str) or not a:
                out.append(("FATAL", f"long_book.assets entry {a!r} must "
                            "be a non-empty string"))
            elif universe and a not in universe:
                out.append(("FATAL", f"long_book.assets '{a}' is not in "
                            f"exchanges.kraken.trading_pairs' base-symbol "
                            f"universe {sorted(universe)} - the long book "
                            f"can only accumulate assets Kraken actually "
                            f"trades"))

    # --- spacing / offset / frac knobs: all strictly positive, or the
    # add path either never fires (0 spacing floods every cycle instead
    # of throttling) or sizes/offsets to nothing. zone_tol_pct/
    # zone_buffer_pct (task C3, LongBookEngine.shift_off_magnets) are new
    # knobs this task adds to the block - the brief's task-C2-shipped
    # block had no TH-013 hygiene knobs at all. order_ttl_hours/
    # retry_backoff_minutes (C4 review, Critical #1a / Important #3a) are
    # newer still: 0 or negative order_ttl_hours would submit an
    # instantly-expiring (or backwards-dated) bid, and 0/negative
    # retry_backoff_minutes would defeat the whole point of backing off a
    # repeatedly-failing asset (0 = immediate re-attempt, negative =
    # never backs off at all).
    for key in ("add_usd_frac_of_ceiling", "add_min_spacing_hours",
                "add_offset_pct", "zone_tol_pct", "zone_buffer_pct",
                "order_ttl_hours", "retry_backoff_minutes"):
        v = float(lb.get(key, 0.0))
        if v <= 0:
            out.append(("FATAL", f"long_book.{key} ({v}) must be positive"))

    # --- market-conduct pass (F6/F4 task): cadence knobs bounded well
    # above "merely positive". A floor-less config is one edit away from
    # turning the patient accumulation book into a touch-hugging flicker
    # quoter with NO code change - just retuning order_ttl_hours down to
    # seconds, add_min_spacing_hours down to near-zero, retry_backoff_
    # minutes down to an instant re-attempt loop, or the staleness band
    # down to a hair's width so the bid reprices on every tick. Each floor
    # below is a FATAL, not a WARN: this is the compliance-review pre-live
    # condition (docs/compliance_market_conduct.md Rule 575-A), not a
    # tuning preference.
    order_ttl_hours = float(lb.get("order_ttl_hours", 0.0))
    if order_ttl_hours < 1.0:
        out.append(("FATAL", f"long_book.order_ttl_hours ({order_ttl_hours}) "
                    "must be >= 1.0 - a shorter resting-bid lifetime risks "
                    "a touch-hugging flicker quoter (market-conduct pass)"))

    add_min_spacing_hours = float(lb.get("add_min_spacing_hours", 0.0))
    if add_min_spacing_hours < 1.0:
        out.append(("FATAL", f"long_book.add_min_spacing_hours "
                    f"({add_min_spacing_hours}) must be >= 1.0 - a tighter "
                    "add cadence risks a touch-hugging flicker quoter "
                    "(market-conduct pass)"))

    retry_backoff_minutes = float(lb.get("retry_backoff_minutes", 0.0))
    if retry_backoff_minutes < 5.0:
        out.append(("FATAL", f"long_book.retry_backoff_minutes "
                    f"({retry_backoff_minutes}) must be >= 5.0 - a shorter "
                    "post-failure backoff risks a re-attempt/re-audit "
                    "flicker loop (market-conduct pass)"))

    staleness_band_pct = (float(lb.get("add_offset_pct", 0.0))
                          + float(lb.get("zone_tol_pct", 0.0))
                          + float(lb.get("zone_buffer_pct", 0.0)))
    if staleness_band_pct < 0.3:
        out.append(("FATAL",
                    f"long_book add_offset_pct + zone_tol_pct + "
                    f"zone_buffer_pct ({staleness_band_pct:.3f}%) must be "
                    ">= 0.3% - a narrower staleness band reprices the "
                    "resting bid on nearly every mark tick, a touch-"
                    "hugging flicker quoter in all but name "
                    "(market-conduct pass)"))

    # --- TH-013 magnet-shift hygiene coherence (task C3): buffer_pct
    # must exceed tol_pct, or a bid shifted `buffer_pct` below a magnet
    # could still read as "within tol_pct" of that SAME magnet -
    # a non-idempotent shift (shift_off_magnets could re-flag its own
    # output as still-too-close on the very next evaluation).
    zone_tol = float(lb.get("zone_tol_pct", 0.0))
    zone_buf = float(lb.get("zone_buffer_pct", 0.0))
    if zone_tol > 0 and zone_buf > 0 and zone_buf <= zone_tol:
        out.append(("FATAL", f"long_book.zone_buffer_pct ({zone_buf}) must "
                    f"exceed long_book.zone_tol_pct ({zone_tol}) - "
                    "otherwise a hygiene-shifted bid can still read as "
                    "within tolerance of the same magnet it just moved "
                    "away from"))

    # --- price-collar coherence (task C4 discovery, engine integration):
    # the add's bid rests add_offset_pct below mark, and a TH-013 magnet
    # shift (task C3's shift_off_magnets) can push it up to a further
    # zone_buffer_pct + zone_tol_pct beyond that (the shift never moves
    # TOWARD price) - if that worst-case total deviation from mark
    # reaches the SHARED risk_firewall's entry_collar_bps, EVERY
    # long-book add is unconditionally FW-050 price-collar rejected
    # (execution/risk_firewall.py's collar screen runs before purpose/
    # post_only is even consulted - there is no maker exemption). This
    # is a dead-on-arrival feature, not a mere risk tradeoff: caught live
    # wiring task C4's engine integration, where the shipped task-C2
    # add_offset_pct=1.5% (150bps) exceeded the shipped
    # risk_firewall.entry_collar_bps=100bps on every single add.
    fw_collar_bps = float(_f(config, "risk_firewall.entry_collar_bps", 100.0))
    worst_dev_bps = (float(lb.get("add_offset_pct", 0.0))
                     + float(lb.get("zone_buffer_pct", 0.0))
                     + float(lb.get("zone_tol_pct", 0.0))) * 100.0
    if worst_dev_bps >= fw_collar_bps:
        out.append(("FATAL",
                    f"long_book add_offset_pct ({lb.get('add_offset_pct')}%)"
                    f" + zone_buffer_pct ({lb.get('zone_buffer_pct')}%) + "
                    f"zone_tol_pct ({lb.get('zone_tol_pct')}%) worst-case "
                    f"deviation ({worst_dev_bps:.0f}bps) >= risk_firewall."
                    f"entry_collar_bps ({fw_collar_bps:.0f}bps) - every "
                    f"long-book add would be unconditionally price-collar "
                    f"rejected (FW-050)"))

    # --- evidence ladder: ceilings strictly increasing and each <= the
    # SHARED risk_protocols.heat.max_portfolio_heat_frac (cross-block
    # read, same pattern as _conviction_checks' pretrade cross-read) -
    # the long book's own ceiling lives INSIDE the combined portfolio
    # heat cap, never its own risk stack (Global Constraint).
    ladder = lb.get("ladder", {}) or {}
    r1 = float(_f(ladder, "r1.ceiling_frac", 0.0))
    r2 = float(_f(ladder, "r2.ceiling_frac", 0.0))
    r3 = float(_f(ladder, "r3.ceiling_frac", 0.0))
    if not (0.0 < r1 < r2 < r3):
        out.append(("FATAL", f"long_book.ladder ceilings [{r1}, {r2}, "
                    f"{r3}] must be strictly increasing (0 < r1 < r2 < "
                    "r3) - a flat/inverted ladder either grants no extra "
                    "size for more evidence or grants LESS"))
    heat_cap = float(_f(config, "risk_protocols.heat.max_portfolio_heat_frac",
                        0.35))
    for name, v in (("r1", r1), ("r2", r2), ("r3", r3)):
        if v > heat_cap:
            out.append(("FATAL", f"long_book.ladder.{name}.ceiling_frac "
                        f"({v}) exceeds risk_protocols.heat."
                        f"max_portfolio_heat_frac ({heat_cap}) - the long "
                        f"book's ceiling cannot exceed the shared "
                        f"portfolio heat cap it lives inside"))
    dd = float(ladder.get("dd_downgrade_pct", 0.0))
    if dd <= 0:
        out.append(("FATAL", f"long_book.ladder.dd_downgrade_pct ({dd}) "
                    "must be positive - 0 or negative would never (or "
                    "always/immediately) trip the instant downgrade"))

    # --- adverse-transition episode minimum duration (task C5, C4-review
    # item 3(b)): a risk-off context episode must SUSTAIN stress >
    # stress_max_for_add for at least adverse_min_hours before it counts
    # as a survivable adverse transition at all - 0 or negative would
    # count every momentary stress flicker (or, negative, every cycle
    # unconditionally) as a "survived" episode, cheapening r3's evidence
    # gate.
    adverse_min_hours = float(_f(ladder, "adverse_min_hours", 24.0))
    if adverse_min_hours <= 0:
        out.append(("FATAL", f"long_book.ladder.adverse_min_hours "
                    f"({adverse_min_hours}) must be positive - 0 or "
                    "negative would count a momentary stress flicker as "
                    "a survived adverse transition"))

    # --- crisis cadence pause (task C5 item 4): a bool feature flag; a
    # non-bool would be silently bool()-coerced (Python bool("false") is
    # True) - a config author's "false" string would silently ENABLE the
    # pause rather than disable it. FATAL, matching this function's own
    # all-FATAL severity convention (unlike the ADVISORY precedent
    # elsewhere in this module for a similar ml.monitor.shadow_recovery
    # coercion risk - the long_book block's own docstring commits this
    # whole function to FATAL-only severity).
    pause_in_crisis = lb.get("context", {}).get("pause_in_crisis", True)
    if not isinstance(pause_in_crisis, bool):
        out.append(("FATAL", f"long_book.context.pause_in_crisis "
                    f"({pause_in_crisis!r}) must be a real boolean, not "
                    f"{type(pause_in_crisis).__name__} - bool() coercion "
                    "of a non-bool (e.g. the string 'false') silently "
                    "flips the pause on"))

    # --- euphoria give-back tightening (task C5 item 5): down-only by
    # design - euphoria_giveback_frac must be <= the base giveback_frac,
    # or the phase switch would LOOSEN protection during a euphoria
    # regime, inverting the evidence-backed disposition-effect rationale
    # (evidence pass 2 Section 1.1a) it exists to encode. Absent ->
    # risk/profit_tiers.py's own module default (== giveback_frac, exactly
    # inert) is never checked here.
    gb = lb.get("profit_taking", {}).get("give_back", {}) or {}
    if "euphoria_giveback_frac" in gb:
        euphoria_frac = float(_f(gb, "euphoria_giveback_frac", 0.0))
        base_frac = float(_f(gb, "giveback_frac", 0.40))
        if euphoria_frac > base_frac:
            out.append(("FATAL", "long_book.profit_taking.give_back."
                        f"euphoria_giveback_frac ({euphoria_frac}) must "
                        f"be <= giveback_frac ({base_frac}) - euphoria "
                        "tightening is down-only by design (evidence "
                        "pass 2 Section 1.1a); a looser euphoria fraction "
                        "would invert it"))

    # --- thesis stop: a plain bounds check. thesis_stop_pct is a DOWNSIDE
    # pct-of-entry-price magnitude (structural invalidation, LB-031) for a
    # spot long - it cannot be non-positive (0 or negative would never,
    # or always/immediately, trip the stop) or exceed 100% (a spot long
    # cannot lose more than its entry value). C2 review REMOVED the prior
    # thesis-stop-vs-tier_4 cross check entirely (see task-C2-report.md's
    # correction note): comparing a downside stop magnitude against the
    # tier ladder's unrelated upside trigger magnitude false-FATAL'd
    # coherent deep-stop configs (e.g. thesis_stop_pct=45 with the
    # shipped tier_4.trigger_pct_gain=40) with no genuine coherence
    # relationship between the two numbers to justify it.
    thesis_stop = float(lb.get("thesis_stop_pct", 0.0))
    if not (0.0 < thesis_stop <= 100.0):
        out.append(("FATAL", f"long_book.thesis_stop_pct ({thesis_stop}) "
                    "must be in (0, 100] - a downside pct of entry price "
                    "cannot be non-positive or exceed 100% for a spot long"))

    # --- time_stop design pin: PT-060 time-stop is OFF for the long book
    # by design (patience IS the strategy) - never armed, unlike the 5m
    # book's own optional time_stop.
    if bool(_f(lb, "profit_taking.time_stop.enabled", False)):
        out.append(("FATAL", "long_book.profit_taking.time_stop.enabled "
                    "must be false - PT-060 time-stop is OFF by design "
                    "for the long book (patience IS the strategy)"))

    return out


_ABSENT = object()


def _era_key_absence_checks(config: dict) -> list:
    """Era-booked keys whose ABSENCE reads a code default the era was never
    booked at (config debug 2026-09-08; the fee-key failure class, six more
    instances). Hoisted out of validate() on 2026-09-09 because pyright
    stopped analysing validate() for complexity. The consumer and its silent
    fallback, each read at HEAD on branch cut12 that day - line numbers rot,
    the needles do not:
      ml.label_round_trip_cost_pct  -> 0.5   ml/history.py
          cfg.get("label_round_trip_cost_pct", 0.5)
      order_manager.sim_fill.passive_base_prob -> 0.45
          execution/order_manager.py sf.get("passive_base_prob", 0.45)
          (the pre-XV-021 simulator: ~9x the measured passive fill rate)
      order_manager.sim_fill.queue_aware -> False
          execution/order_manager.py sf.get("queue_aware", False)
          (flat-Poisson fills; the starvation WARN ALSO disappears)
      position_sizer.min_ticket_usd -> 25.0  risk/position_sizer.py
          cfg.get("min_ticket_usd", 25.0) - and 15 in this file's probe-
          floor check: two consumers, two defaults, neither the booked $60
      ml.exploration.size_scale -> 0.25  main.py
          _ex.get("size_scale", 0.25) (a silent 4x probe shrink)
      hedging.enabled -> True  execution/hedging.py
          cfg.get("enabled", True) (the hedger, OFF since cut #11, ON again)
    Measured 2026-09-08 BEFORE this check, shipped config: deleting any of
    the first five -> 0 FATAL (queue_aware: 3 WARN -> 2); deleting
    hedging.enabled -> 0 FATAL. Pinned per key, with the fee keys as the
    positive control: tests/test_config_guard_absent_keys.py."""
    missing = [
        path for path in ("ml.label_round_trip_cost_pct",
                          "order_manager.sim_fill.passive_base_prob",
                          "order_manager.sim_fill.queue_aware",
                          "position_sizer.min_ticket_usd",
                          "ml.exploration.size_scale",
                          "hedging.enabled")
        if _f(config, path, _ABSENT) is _ABSENT]
    if not missing:
        return []
    return [("FATAL",
             f"era-booked key(s) absent from config: {', '.join(missing)}. "
             f"Each reads a code default the accruing era was never booked "
             f"at (core/config_guard._era_key_absence_checks names the "
             f"consumer and its fallback), so 'the operator did not say' "
             f"would silently become a value. State the key explicitly; "
             f"absence is not a value.")]


def _cost_stack_range_checks(config: dict) -> list:
    """The cost-stack knobs PreTradeGate SILENTLY CLAMPS, plus the one with no
    ceiling at all.

    THE SHAPE. `execution/pretrade.py:107-111` builds three of these with
    `min(max(float(cfg.get(...)), lo), hi)`. A config value outside that window
    is not rejected and not reported - it is rewritten. Set
    `adverse_selection_kappa: 99` and the gate runs at 2.0; set it to -5 and the
    gate runs at 0.0 with the adverse-selection term DISABLED. Either way the
    operator's stated intent and the deployed behaviour differ, permanently and
    silently, and every downstream number is computed against a value that
    appears nowhere. A clamp is the right defence inside the hot path; it is the
    wrong place to DECIDE, because nothing there can say so.

    `impact_eta` is the opposite defect: `:911` fatals only on negative, so it
    has no ceiling. `impact_bps = eta * sigma_daily * sqrt(Q/ADV)`, so the
    plausible typo is a decimal slip - `8.0` for `0.8` - which multiplies the
    impact term ten-fold and quietly vetoes entries that should clear. That
    failure reads as "the market got expensive", not "the config is wrong",
    which is the recurrence this repo keeps paying for. The 5.0 ceiling is a
    TYPO FENCE, not a tuned bound: published square-root-impact coefficients sit
    near 0.5-1.5, so 5.0 admits more than three times the top of any defensible
    view while still catching the slip it exists for. It was drafted at 10.0 and
    corrected before shipping - 10.0 would have let the very example above
    (8.0 for 0.8) through, i.e. the docstring would have claimed a fence the
    number did not build.

    ZERO IS REPORTED, NOT REFUSED. `impact_eta: 0` and
    `adverse_selection_kappa: 0` are inside every clamp and are legitimate
    choices ("switch this term off"), but they DELETE a cost term from the stack
    that gates entries, so they warn. The repo's standing position is that
    cost-stack completeness is not a tunable - see the round-trip fee check
    above, which uses the same wording - but a deliberate zero is a decision, and
    a guard that fatals on decisions gets deleted as noise.

    Verified against the shipped config before shipping this: eta 0.8,
    kappa 0.35, maker_fill_p0 0.45, p_fill_floor 0.05 - all interior, guard
    stays 0 FATAL.
    """
    out: list = []
    # (dotted key, lo, hi, what the term does). No default column on purpose:
    # this reads with `_f(..., None)` so an ABSENT key is skipped rather than
    # judged against a default the guard invented. Absence is pinned elsewhere
    # (tests/test_config_guard_absent_keys.py); range is this function's job.
    clamped = [
        ("pretrade.adverse_selection_kappa", 0.0, 2.0,
         "scales the adverse-selection charge on a passive fill"),
        ("pretrade.maker_fill_p0", 0.01, 1.0,
         "is the base maker fill probability the EV gate weighs"),
        ("pretrade.p_fill_floor", 0.001, 1.0,
         "floors that fill probability so EV can never divide by zero"),
        ("pretrade.impact_eta", 0.0, 5.0,
         "scales the square-root market-impact cost term"),
        # Added 2026-09-11 (red-team OBJ-16, conceded). execution/pretrade.py
        # :113-114 clamps this to [0.0, 20.0] exactly like the three above, and
        # the first cut of this guard covered three of the four. Injected to
        # confirm before fixing: miss_cost_bps=999 produced ZERO findings and
        # the gate ran at 20.0. Three of four is the shape that reads as
        # coverage and is not.
        ("pretrade.miss_cost_bps", 0.0, 20.0,
         "prices the opportunity cost of NOT filling, inside the same EV gate"),
    ]
    # GENERAL NON-FINITE SWEEP over the whole pretrade block (2026-09-13).
    # The bounded list below covers five knobs. It does NOT cover the four
    # THRESHOLDS the hard vetoes compare against (max_data_staleness_ms,
    # max_spread_bps / tier_max_spread_bps, min_order_usd,
    # max_participation_of_depth), and a non-finite threshold makes its veto
    # fail OPEN - measured: max_data_staleness_ms=NaN APPROVES a 1,000,000 ms
    # stale book in the exploring lane. Enumerating four more keys would leave
    # the same shape one key over, which is how this defect and the
    # 2026-09-11 miss_cost_bps one both arrived, so this closes the CLASS:
    # every numeric leaf under `pretrade`, including nested maps.
    _pre = config.get("pretrade") if isinstance(config, dict) else None
    if isinstance(_pre, dict):
        def _sweep(node, path):
            if isinstance(node, dict):
                for k, v in node.items():
                    if not str(k).startswith("_"):
                        _sweep(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    _sweep(v, f"{path}[{i}]")
            elif isinstance(node, (int, float)) and not isinstance(node, bool):
                # float() RAISES OverflowError on an int too large to convert,
                # and a 400-digit JSON integer literal parses to exactly that
                # (json.loads gives a Python int; only `1e400` gives inf).
                # Letting it propagate takes the WHOLE validator down, so every
                # other FATAL is lost with it - a crash instead of a diagnosis,
                # and a regression of the property 1d7e9e5f shipped by name
                # ("stop a typo crashing the validator"). An int beyond float
                # range is not finite in any sense a threshold comparison
                # cares about, so it is reported, not raised.
                try:
                    _ok = math.isfinite(float(node))
                except (OverflowError, ValueError):
                    _ok = False
                if not _ok:
                    out.append(("FATAL",
                                f"{path}={node!r} is not finite - every "
                                f"comparison against it comes out False, so "
                                f"any gate or veto reading it stops guarding "
                                f"SILENTLY while the config still reads as "
                                f"configured"))
        _sweep(_pre, "pretrade")

    for key, lo, hi, what in clamped:
        raw = _f(config, key, None)
        if raw is None:
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError, OverflowError):
            # OverflowError added 2026-09-13: float() raises it on an int too
            # large to convert, and a 400-digit JSON integer literal parses to
            # exactly that (only 1e400 gives inf). It was NOT in this tuple, so
            # validate() RAISED instead of returning findings and every other
            # FATAL was lost with it - a crash instead of a diagnosis. Found by
            # an adversarial review of the sweep added above, which had the
            # same hole; this one is older and was the live crash.
            out.append(("FATAL", f"{key}={raw!r} is not a number - it {what}"))
            continue
        # NON-FINITE FAILS OPEN, so it is refused BEFORE the range test
        # (2026-09-13). `val < lo or val > hi` is False for NaN, so every
        # bound in this list was permeable: injected, all five keys took a
        # NaN with ZERO findings. It is reachable rather than theoretical -
        # json.loads accepts a bare NaN AND json.dumps EMITS one, and the
        # era-cut stagers write config with json.dumps, so the repo's own
        # tooling can round-trip a NaN-bearing config silently.
        #
        # The consequence is a fail-OPEN in the decision path, measured on a
        # live PreTradeGate built from the shipped config: baseline
        # approved=False cost=54.300; with pretrade.impact_eta=NaN (or
        # adverse_selection_kappa=NaN) approved=TRUE with cost=nan, because
        # a NaN cost makes `edge < ratio*cost` False and PT-041 never fires.
        # Same shape as RP-052 (cut #10 B3, "NaN flowed max(nan,0)->nan
        # through"). Mirrors the isfinite idiom already used at :769.
        if not math.isfinite(val):
            out.append(("FATAL",
                        f"{key}={raw!r} is not finite - it {what}, and a "
                        f"non-finite value PASSES every range test (NaN "
                        f"compares False to both bounds), then makes the "
                        f"pre-trade cost NaN so the edge/cost gate PT-041 "
                        f"cannot fire and the entry is APPROVED with an "
                        f"unknown cost"))
            continue
        if val < lo or val > hi:
            where = ("execution/pretrade.py clamps it into "
                     f"[{lo:g}, {hi:g}] and says nothing"
                     if key != "pretrade.impact_eta"
                     else "nothing clamps it, so it applies in full")
            out.append((
                "FATAL",
                f"{key}={val:g} is outside [{lo:g}, {hi:g}] - it {what}, and "
                f"{where}. The deployed value would not be the configured one. "
                f"Fix the config rather than relying on the clamp."))
    for key in ("pretrade.impact_eta", "pretrade.adverse_selection_kappa"):
        raw = _f(config, key, None)
        try:
            if raw is not None and float(raw) == 0.0:
                out.append((
                    "WARN",
                    f"{key}=0 DISABLES a cost term the entry gate weighs. "
                    f"Legitimate as a deliberate choice, but every EV number "
                    f"below it is then computed without that charge - confirm "
                    f"this is intended and not a cleared field."))
        except (TypeError, ValueError, OverflowError):
            pass
    return out


def _label_cost_vs_booked_checks(config: dict) -> list:
    """THE HALF-APPLIED FEE STAGE (cut #12 adversarial review, 2026-09-08).
    Every fee cut (#9, #10, #12) moves the label cost WITH the booked
    maker+taker round trip - risk/profit_tiers.py names the hazard of a
    stage that moves one and not the other, and until this check nothing
    at runtime enforced it: fees 15/30 with the label left at 0.55 booted
    clean. A label cost BELOW the booked round trip is the dangerous
    direction (labels call net-losing trades wins); FATAL when the key is
    explicitly present. Over-costing the label is allowed."""
    raw = _f(config, "ml.label_round_trip_cost_pct", None)
    if raw is None:
        return []
    label_cost = float(raw)
    pt_maker = float(_f(config, "pretrade.maker_fee_bps", 25.0))
    pt_taker = float(_f(config, "pretrade.taker_fee_bps", 40.0))
    booked_rt_pct = (pt_maker + pt_taker) / 100.0
    if label_cost + 1e-9 >= booked_rt_pct:
        return []
    return [("FATAL",
             f"ml.label_round_trip_cost_pct={label_cost:.2f}% is below the "
             f"BOOKED round trip {booked_rt_pct:.2f}% (pretrade "
             f"{pt_maker:g}+{pt_taker:g} bps): a fee stage moved the fees "
             f"and not the label cost. The four fee-derived keys move "
             f"together (scripts/cut12_stage.py) or not at all.")]


def validate(config: dict) -> list:
    """Pure check: returns [(severity, message), ...]. No side effects."""
    findings = []
    fatal = lambda m: findings.append(("FATAL", m))       # noqa: E731

    # ---- rev-4: execution-routing invariant ---------------------------
    eligible = [str(v).lower() for v in (config.get("execution", {})
                .get("routing", {}).get("eligible_venues", ["kraken"]))]
    rogue = [v for v in eligible if v != "kraken"]
    if rogue:
        fatal(f"execution.routing.eligible_venues contains {rogue} — "
              f"Kraken is the sole execution venue by invariant; other "
              f"venues are read-only data sources. Remove them (routing "
              f"scores them for the audit trail regardless).")
    # any non-kraken venue adapter flipped enabled is a live-config FATAL:
    # the adapter layer refuses to execute on it, but an enabled disabled-
    # adapter signals intent that must not reach live silently.
    venues_cfg = config.get("execution", {}).get("venues", {}) or {}
    enabled_rogue = [name for name, v in venues_cfg.items()
                     if isinstance(v, dict) and name != "kraken"
                     and v.get("enabled")]
    if enabled_rogue:
        fatal(f"execution.venues has non-kraken adapters enabled "
              f"{enabled_rogue} — Kraken is the sole execution venue. These "
              f"adapters cannot execute (VenueNotEnabled) and must not be "
              f"enabled in a live config until onboarded and re-reviewed.")
    algos_cfg = config.get("execution", {}).get("algos", {})
    if algos_cfg.get("enabled") and \
            float(algos_cfg.get("min_interval_sec", 30)) < 15:
        fatal("execution.algos.min_interval_sec < 15s would collide with "
              "the risk-firewall per-minute order budget (FW-020); child "
              "slices must pace slower than the budget refills.")

    warn = lambda m: findings.append(("WARN", m))         # noqa: E731
    # ADVISORY: a config-coherence/hygiene note where the bot still trades
    # correctly (e.g. a phantom knob whose effective value differs). Logged at
    # INFO by enforce(), so it stays OFF the WARNING+ incidents stream - a
    # WARN there should mean a real operational concern, not a cosmetic note.
    advisory = lambda m: findings.append(("ADVISORY", m))  # noqa: E731

    # --- owed 57 / execution-era boundary #4: the fill-sim double-count.
    # Not FATAL: true is a LEGITIMATE reproduction mode for a pre-#4 cohort,
    # and a FATAL would make the old simulator unreachable. But it must never
    # be true by accident or to recover entry volume, so it is loud.
    if bool(_f(config, "order_manager.sim_fill.passive_hazard_with_book",
               False)):
        warn("order_manager.sim_fill.passive_hazard_with_book=true restores "
             "the PRE-BOUNDARY-#4 simulator, in which the passive hazard and "
             "_sim_maker_cross both model the same market crossing - a "
             "per-order fill rate of 2f-f^2 against a calibration target of "
             "f (22.0% vs 11.66%, ~1.88x at the touch). Legitimate ONLY for "
             "reproducing a pre-boundary-#4 cohort (commit aeeaae36, "
             "2026-08-10T11:03:35Z). It is not a tuning knob: "
             "every paper fill statistic produced under it carries a ~2x "
             "upward bias near the touch.")

    # --- cut #7 stop-placement knobs (2026-08-11 commits audit: these had
    # no guard at ship). nudge_stop_off_round clamps negatives to 0 and
    # fails inert, so a bad knob cannot crash - but an incoherent value
    # must not pass silently: band+offset is the maximum stop WIDENING in
    # bps of stop price, and a nonsensically large value is a geometry
    # change wearing a hygiene knob's name.
    for _k in ("stop_round_buffer_bps", "stop_round_offset_bps"):
        _v = _f(config, f"risk.{_k}", None)
        if _v is None:
            continue
        try:
            _fv = float(_v)
        except (TypeError, ValueError, OverflowError):
            fatal(f"risk.{_k} ({_v!r}) is not a number")
            continue
        if not math.isfinite(_fv) or _fv < 0:
            fatal(f"risk.{_k} ({_fv}) must be finite and >= 0 - the nudge "
                  f"clamps it inert at runtime, so this value is config "
                  f"noise that can only mislead")
        elif _fv > 25.0:
            warn(f"risk.{_k} ({_fv}bps) is far beyond the Osler cluster "
                 f"band (~5bps); band+offset is the maximum widening "
                 f"applied to every near-round stop, and at this size it "
                 f"is a stop-geometry change (cohort-resetting under the "
                 f"era-4 moratorium), not round-number hygiene.")

    dry_run = bool(_f(config, "system.dry_run", True))

    # --- fees ----------------------------------------------------------
    # These fallbacks (25/40, the retired pre-cut-#8 tier) sit DELIBERATELY
    # BELOW the venue-true floor (40/80): a config that DELETED the fee keys
    # falls back here and then TRIPS the sub-floor FATAL below - which is the
    # whole point (a missing fee key must not silently price at the old tier).
    # The shipped config carries the keys explicitly at 40/80, so these
    # fallbacks never fire in production. (The read-sites in
    # execution/pretrade.py and execution/order_manager.py still carry their
    # OWN stale 25/40 fallbacks - tracked separately; harmless while the keys
    # are present, but they should follow this floor to venue truth.)
    # ABSENT IS NOT ZERO AND IT IS NOT 25/40 EITHER.
    #
    # These four reads default to the venue's zero-volume row, which passes
    # every check below - so dropping the keys entirely produced ZERO fee
    # FATALs (measured 2026-09-05) while four consumers went on to substitute
    # four DIFFERENT fallback schedules. The realistic trigger is a
    # half-applied or reverted fee stage: fee_correction_stage.py and
    # boundary5_stage.py both rewrite all four keys together.
    #
    # A silently-defaulted fee is the same failure as a silently-defaulted
    # anything else in this repo: "the operator did not say" and "the operator
    # said 25/40" must not be the same bits. Absence is now named.
    _MISSING = object()
    # profit_taking.est_fee_bps joined this list at cut #10 (B2): its code
    # default was 0.0 ("fees are free") and computed a 6 bps break-even floor
    # against a booked 76. The code default is now the venue's worst taker
    # row, and this FATAL means production never reaches ANY default.
    _missing_fee_keys = [
        path for path in ("pretrade.maker_fee_bps", "pretrade.taker_fee_bps",
                          "order_manager.maker_fee_bps",
                          "order_manager.taker_fee_bps",
                          "profit_taking.est_fee_bps")
        if _f(config, path, _MISSING) is _MISSING]
    if _missing_fee_keys:
        fatal(f"fee key(s) absent from config: {', '.join(_missing_fee_keys)}. "
              f"The guard would default them to the venue's zero-volume row "
              f"while other consumers substitute different fallbacks, so the "
              f"EV gate and the PnL ledger would price the same trade "
              f"differently. State the fees explicitly.")
    # --- era-booked keys whose ABSENCE reads a default the era was never
    # booked at (config debug 2026-09-08; the fee-key failure class above,
    # six more instances). The consumer and its silent fallback, each read at
    # HEAD on branch cut12 that day - line numbers rot, the needles do not:
    #   ml.label_round_trip_cost_pct  -> 0.5   ml/history.py:2397
    #       cfg.get("label_round_trip_cost_pct", 0.5)
    #   order_manager.sim_fill.passive_base_prob -> 0.45
    #       execution/order_manager.py:236 sf.get("passive_base_prob", 0.45)
    #       (the pre-XV-021 simulator: ~9x the measured passive fill rate)
    #   order_manager.sim_fill.queue_aware -> False
    #       execution/order_manager.py:246 sf.get("queue_aware", False)
    #       (flat-Poisson fills; the starvation WARN below ALSO disappears)
    #   position_sizer.min_ticket_usd -> 25.0  risk/position_sizer.py:119
    #       cfg.get("min_ticket_usd", 25.0) - and 15 in THIS file's probe-
    #       floor check, _f(config, "position_sizer.min_ticket_usd", 15):
    #       two consumers, two defaults, neither the booked $60
    #   ml.exploration.size_scale -> 0.25  main.py:1066
    #       _ex.get("size_scale", 0.25) (a silent 4x probe shrink)
    #   hedging.enabled -> True  execution/hedging.py:49
    #       cfg.get("enabled", True) (the hedger, OFF since cut #11, ON again)
    # Measured 2026-09-08 BEFORE this block, shipped config: deleting any of
    # the first five -> 0 FATAL (queue_aware: 3 WARN -> 2); deleting
    # hedging.enabled -> 0 FATAL. Pinned per key, with the fee keys as the
    # positive control: tests/test_config_guard_absent_keys.py.
    findings.extend(_era_key_absence_checks(config))
    pt_maker = float(_f(config, "pretrade.maker_fee_bps", 25.0))
    pt_taker = float(_f(config, "pretrade.taker_fee_bps", 40.0))
    om_maker = float(_f(config, "order_manager.maker_fee_bps", 25.0))
    om_taker = float(_f(config, "order_manager.taker_fee_bps", 40.0))
    allow_low = bool(_f(config, "pretrade.allow_sub_floor_fees", False))

    if min(pt_maker, pt_taker, om_maker, om_taker) < 0:
        fatal("negative fee configured")
    if abs(pt_maker - om_maker) > 1e-9 or abs(pt_taker - om_taker) > 1e-9:
        fatal(f"fee mismatch: pretrade ({pt_maker}/{pt_taker}) != "
              f"order_manager ({om_maker}/{om_taker}) - the edge gate and "
              f"the PnL ledger would disagree about costs")

    # THE DISCOUNT FLAG NEEDS A FLOOR OF ITS OWN.
    #
    # allow_sub_floor_fees exists so an account with a genuine volume discount
    # can book below the zero-volume row, and cut #9 set it true to permit
    # 22/38. But it disabled the floor for ANY value: measured 2026-09-05 on
    # the shipped config, 0.0/0.0 and 1.0/1.0 both validated with ZERO fatals.
    # Understated fees are the highest-leverage silent defect available here -
    # they make the pre-trade EV gate admit net-losing trades while every
    # downstream number stays internally consistent.
    #
    # The honest bound is the venue's BEST published tier: nobody pays less
    # than that at any volume, ever. Note it is not a made-up positive number -
    # maker 0 IS a real Kraken row (>=$10M 30-day volume), so the check is
    # against the schedule, not against taste.
    _best_m, _best_t = _venue_best_row()
    if pt_maker < _best_m or pt_taker < _best_t:
        (fatal if not dry_run else warn)(
            f"configured fees {pt_maker:g}/{pt_taker:g} bps are below the "
            f"CHEAPEST tier Kraken publishes at any volume "
            f"({_best_m:g}/{_best_t:g}). No account pays less than this, so "
            f"allow_sub_floor_fees cannot license it - a discount flag is not "
            f"a licence for zero. Understated fees make the pre-trade gate "
            f"approve net-losing trades.")
    if not allow_low and (pt_maker < KRAKEN_SPOT_FLOOR_MAKER_BPS
                          or pt_taker < KRAKEN_SPOT_FLOOR_TAKER_BPS):
        msg = (f"configured fees {pt_maker:.0f}/{pt_taker:.0f} bps are below "
               f"Kraken's public spot floor "
               f"{KRAKEN_SPOT_FLOOR_MAKER_BPS:.0f}/"
               f"{KRAKEN_SPOT_FLOOR_TAKER_BPS:.0f} bps. Understated fees make "
               f"the pre-trade gate approve net-losing trades. Set your real "
               f"tier, or set pretrade.allow_sub_floor_fees=true if you "
               f"genuinely have volume discounts.")
        (fatal if not dry_run else warn)(msg)
    if pt_taker < pt_maker:
        warn("taker fee below maker fee - unusual; double-check the tier")
    # IS THE BOOKED PAIR A TIER THE VENUE ACTUALLY PUBLISHES?
    #
    # A maker/taker pair matching no row did not come from the schedule - it
    # came from a screenshot, an average, or a memory of an older tier - and
    # that provenance is the defect, independent of whether the number
    # happens to be conservative. (2026-09-08: this check is only as good as
    # the table behind it. With the legacy-ladder table it passed cut #10's
    # 20/35 and rejected cut #9's 22/38 - the reverse of the truth. It cannot
    # tell WHICH published row the account qualifies for; only a 30-day
    # volume / AoP reading can, and that is scripts/fee_drift_report.py's job.)
    #
    # WARN, not FATAL, deliberately: correcting the booked value is fee
    # policy, which is cohort-resetting and belongs to an operator
    # adjudication. A guard must not quietly force a boundary cut. Promoting
    # this to FATAL should ride that adjudication.
    from core.venue_fees import KRAKEN_SPOT_SCHEDULE as _rows
    from core.venue_fees import is_a_published_row as _is_row
    if not _is_row(pt_maker, pt_taker):
        head = ", ".join(f"{m:g}/{t:g}" for _v, m, t in _rows[:4])
        warn(f"configured fees {pt_maker:g}/{pt_taker:g} bps are not a "
             f"published Kraken tier (rows: {head}, ...). "
             f"A pair that matches no row did not come from the venue's "
             f"schedule. Run scripts/fee_drift_report.py; correcting the "
             f"booked value is an operator adjudication (cohort-resetting).")

    # --- fee-tier reconciliation (W2-9 remainder) -----------------------
    # order_manager.fee_recon periodically compares the CONFIGURED bps
    # above against Kraken's ACTUAL account fee tier (TradeVolume) and is
    # report-only (never mutates config). Bounds guard the two knobs that
    # govern it, checked whenever it's enabled (default True, matching the
    # shipped config) regardless of dry_run - both are structural config-
    # nonsense checks, same class as tier1_cost_floor's own bounds.
    fr = config.get("order_manager", {}).get("fee_recon", {}) or {}
    if fr.get("enabled", True):
        fr_tol = float(_f(config, "order_manager.fee_recon.tolerance_bps",
                          1.0))
        if not (0.0 < fr_tol <= 50.0):
            fatal(f"order_manager.fee_recon.tolerance_bps={fr_tol} must be "
                  f"in (0, 50] - at/below 0 the check would flag ordinary "
                  f"float noise every interval (drowning the one genuine "
                  f"dangerous case in duplicate WARNs); above 50bps it can "
                  f"no longer catch a real Kraken tier jump. 1.0 bps = the "
                  f"smallest Kraken tier step matters at our 20.5 bps "
                  f"measured cost stack (P1, 2026-07-23 P&L diagnosis)")
        fr_hrs = float(_f(config, "order_manager.fee_recon.interval_hours",
                          24.0))
        if not (1.0 <= fr_hrs <= 168.0):
            fatal(f"order_manager.fee_recon.interval_hours={fr_hrs} must be "
                  f"in [1, 168] - below hourly the private TradeVolume call "
                  f"would out-cadence hourly_cycle itself (the only place "
                  f"it's driven from); above a week (168h) a real tier "
                  f"change (the account crossing a 30-day volume threshold) "
                  f"could go undetected for a full trading week")

    # --- pretrade EV gate / participation clamp / staleness ----------------
    # min_edge_cost_ratio gates PT-041 as `edge < ratio * cost`; edge is a
    # sum of two max(., 0) terms so it is never negative, meaning ratio=0
    # makes `edge < 0` impossible and the entire edge-vs-cost gate silently
    # never fires. max_participation_of_depth=0 doesn't veto - it makes
    # max_units = depth_units * 0 = 0, which SKIPS the clamp on a size that
    # sizes to zero rather than blocking the order, the opposite of caution.
    pt_ratio = float(_f(config, "pretrade.min_edge_cost_ratio", 1.3))
    if pt_ratio < 1.0:
        fatal(f"pretrade.min_edge_cost_ratio={pt_ratio} must be >= 1 - below "
              f"1x the edge/cost gate (PT-041) can approve trades whose "
              f"edge doesn't even cover cost, and at 0 the gate never fires "
              f"at all (edge is a sum of max(.,0) terms, never negative)")
    # CEILING (2026-09-13). The guard above was ONE-SIDED for its whole life:
    # injected, min_edge_cost_ratio=13.0 AND =1000.0 both validated with ZERO
    # findings, while 0.5 correctly FATALed. A single decimal slip therefore
    # boots a 10x entry bar, the book silently stops entering, and the record
    # reads "the market gave us nothing". This is the same shape the `clamped`
    # list above was extended for on 2026-09-11 (miss_cost_bps=999 -> zero
    # findings); that list is for knobs the CODE clamps, and
    # execution/pretrade.py:89 reads this one with NO clamp - unlike its four
    # neighbours at :110-116 - so it needs its own bound.
    #
    # THE BOUND IS DERIVED, NOT CHOSEN. PT-041 demands E[edge] >= ratio*cost.
    # At the sigma floor the MAXIMUM payoff of the bet is
    # PT = pt_cost_mult*cost (ml/labeling.barrier_geometry). Requiring the
    # EXPECTED edge to reach the MAXIMUM payoff is unsatisfiable for any bet
    # with a nonzero loss probability, so `ratio >= pt_cost_mult` is an empty
    # acceptance region. Both sides scale with cost, so the bound is
    # COST-INVARIANT - it does not move at a fee re-book, which is the same
    # property that makes the floor's break-even a constant 4/7.
    #
    # The effective ratio includes the monitor's autonomous bump
    # (execution/pretrade.py:321 `ratio = self.min_edge_cost_ratio +
    # max(extra_edge_ratio, 0.0)`), which ceilings at
    # ml.monitor.edge_ratio_bump_max. Measured: the runner log carries ratios
    # in force of 1.30 .. 1.70, i.e. the bump HAS historically reached its
    # full 0.40 cap, so the effective ratio is the one to bound.
    _bump_max = float(_f(config, "ml.monitor.edge_ratio_bump_max", 0.4))
    _pt_cost_mult = float(_f(config, "ml.label_pt_cost_mult", 4.0))
    _eff_ratio = pt_ratio + max(_bump_max, 0.0)
    if _pt_cost_mult > 0.0 and _eff_ratio >= _pt_cost_mult:
        fatal(f"pretrade.min_edge_cost_ratio={pt_ratio} + "
              f"ml.monitor.edge_ratio_bump_max={_bump_max} = {_eff_ratio:g} "
              f">= ml.label_pt_cost_mult={_pt_cost_mult:g}: PT-041 would "
              f"require the EXPECTED edge to reach the bet's MAXIMUM payoff "
              f"(the profit target is pt_cost_mult x cost at the sigma "
              f"floor), which is an empty acceptance region - no candidate "
              f"can clear it. Cost-invariant bound: it does not move at a fee "
              f"re-book. If you meant to tighten the bar, raise it below "
              f"{_pt_cost_mult:g} - {_bump_max:g}")
    pt_part = float(_f(config, "pretrade.max_participation_of_depth", 0.15))
    if not (0.0 < pt_part <= 1.0):
        fatal(f"pretrade.max_participation_of_depth={pt_part} must be in "
              f"(0, 1] - 0 zeroes the depth-participation clamp itself "
              f"(silently sizing to zero instead of blocking), and >1 is "
              f"not a fraction of depth")
    pt_stale = float(_f(config, "pretrade.max_data_staleness_ms", 4000.0))
    if pt_stale <= 0:
        fatal(f"pretrade.max_data_staleness_ms={pt_stale} must be positive "
              f"- a non-positive staleness gate rejects every quote as "
              f"stale (or trusts a permanently dead one, at exactly 0)")
    # price_exit_leg: cost-stack COMPLETENESS, not a tunable. Every entry
    # must be unwound, and execution/pretrade.py adds that unwind leg
    # (taker fee + half the spread) to est_cost_bps. Falsy DELETES it:
    # measured 39.0-45.0 bps over spread 2-14 bps at the shipped 22/38
    # tier, which leaves the stack at ~40% of its true value and drops the
    # PT-041 edge bar with it (92.99 -> 37.09 bps at a 10bps spread). That
    # is the documented mechanism by which an 86%-hit-rate book still nets
    # red - entries priced entry-only never had to clear round-trip cost.
    # Checked against the READ-SITE's own coercion, `bool(cfg.get(...))`,
    # so 0 / 0.0 / "" turn the leg off exactly as false does and are caught
    # by the same clause; an `is False` test would wave them through. A
    # TRUTHY non-bool is equally a FATAL for the mirror-image reason (the
    # long_book.context.pause_in_crisis precedent): bool("false") is True,
    # so an author's "false" silently LEAVES THE LEG ON, the opposite of
    # what it says. Legitimate leg-off pricing exists only in bare-config
    # test construction, which never reaches this guard.
    _leg_raw = _f(config, "pretrade.price_exit_leg", True)
    if not isinstance(_leg_raw, bool):
        fatal(f"pretrade.price_exit_leg ({_leg_raw!r}) must be a real "
              f"boolean, not {type(_leg_raw).__name__} - execution/"
              f"pretrade.py reads it through bool(), where a string like "
              f"'false' is TRUE and a 0 is False, so a non-bool silently "
              f"prices the opposite of what it appears to say")
    elif not _leg_raw:
        # magnitude DERIVED from this config's own taker fee, never a
        # literal: the tier has moved twice (cut #8, cut #9) and a hardcoded
        # bps figure here would have become a false claim each time.
        fatal(f"pretrade.price_exit_leg=false deletes the unwind leg (taker "
              f"fee + half spread) from the pre-trade EV cost stack - at "
              f"this config's taker fee that is {pt_taker:.0f}bps before the "
              f"spread term even counts, so the stack under-prices every "
              f"entry and the PT-041 edge bar falls with it. Cost-stack "
              f"completeness is not a tunable: entries must clear "
              f"ROUND-TRIP cost, not entry-only")

    # pretrade.impact_eta is now owned end-to-end by _cost_stack_range_checks:
    # it covers the negative case this block used to, ADDS the missing ceiling,
    # and reports a non-numeric value instead of raising. The bare
    # `float(_f(...))` that stood here raised ValueError straight out of
    # validate() on a typo'd string, which took the WHOLE validator down - so a
    # single bad character disabled every other FATAL check in this file. Found
    # 2026-09-10 by the test written to assert the opposite.

    # label_mode coherence (2026-07-26 signal-quality task,
    # task-signalquality-brief.md): only two values are wired
    # (ml/history.py CandidateLabeler.__init__, scripts/train_meta.py).
    # Previously unvalidated - a config typo (e.g. "eixt_policy") never
    # matched CandidateLabeler's own `mode == "exit_policy"` dispatch check
    # and silently fell back to triple_barrier with no error, masking the
    # operator's actual intent. FATAL regardless of dry_run: this is a
    # structural config-nonsense check (which label definition trains the
    # model), not a live-risk bound.
    lbl_mode = _f(config, "ml.label_mode", "exit_policy")
    if lbl_mode not in ("exit_policy", "triple_barrier"):
        fatal(f"ml.label_mode={lbl_mode!r} must be 'exit_policy' or "
              f"'triple_barrier' - an unsupported value silently falls back "
              f"to triple_barrier (ml/history.py CandidateLabeler dispatch), "
              f"masking a config typo instead of erroring")

    # label cost coherence: the triple-barrier win/loss label subtracts a
    # round-trip cost. If it sits below the maker round-trip, labels call
    # net-losing trades "wins" and teach the meta-model to take them - the
    # label proxy diverges from realized profitability.
    label_cost = float(_f(config, "ml.label_round_trip_cost_pct", 0.5))
    maker_rt_pct = 2.0 * pt_maker / 100.0
    if label_cost + 1e-9 < maker_rt_pct:
        warn(f"ml.label_round_trip_cost_pct={label_cost:.2f}% is below the "
             f"maker round-trip {maker_rt_pct:.2f}% ({pt_maker:.0f}bps x2) - "
             f"triple-barrier labels understate cost and will mislabel "
             f"net-losing trades as wins, biasing the model to overtrade")
    findings.extend(_label_cost_vs_booked_checks(config))
    findings.extend(_cost_stack_range_checks(config))
    if float(_f(config, "ml.label_spread_cap_bps", 60.0)) < 0:
        fatal("ml.label_spread_cap_bps must be >= 0")

    # FW-081 labeler bars-cache staleness threshold coherence (staleness
    # audit 2026-08-16): the alert fires when an ACTIVE asset's labeler
    # cache is silent for label_bars_stale_cycles slow-cycles. The derived
    # threshold must clear 1200s - thin Kraken pairs legitimately omit
    # empty 5m intervals, and 4 bars is the measured cry-wolf floor the
    # FW-080 check settled on (latency audit 2026-08-07); an alert below
    # it would page on quiet listings. Non-positive is nonsense, not a
    # disable switch (silencing a staleness alarm should be loud: raise
    # the multiple instead).
    sbc = float(_f(config, "ml.label_bars_stale_cycles", 240))
    _slow_s = float(_f(config, "system.polling_interval_sec", 5)) \
        * float(_f(config, "system.slow_cycle_every_n", 6))
    if sbc <= 0:
        fatal(f"ml.label_bars_stale_cycles={sbc} must be > 0 - the FW-081 "
              f"staleness alert has no off switch by design; raise the "
              f"multiple instead of zeroing it")
    elif sbc * _slow_s <= 1200.0:
        fatal(f"ml.label_bars_stale_cycles={sbc} x slow-cycle "
              f"{_slow_s:.0f}s = {sbc * _slow_s:.0f}s threshold at or "
              f"under 1200s - thin Kraken pairs legitimately omit 4 empty "
              f"5m bars (FW-080 floor, latency audit 2026-08-07); this "
              f"alert would cry wolf on quiet listings")

    # cost-floored barrier geometry (spec D2/D5, 2026-07-27,
    # geometry-alignment task 2, docs/superpowers/specs/
    # 2026-07-27-geometry-alignment-design.md): ml.label_pt_cost_mult floors
    # the SIGMA INPUT ml/labeling.py's barrier_geometry() feeds both the
    # labeler and (Task 5) the live bracket-exit engine, so the profit
    # distance never falls below pt_cost_mult round-trip costs. 0 disables
    # the floor (legacy bare 8sigma/6sigma) - config nonsense outside
    # [0, 20], FATAL regardless of dry_run like the label_mode check above
    # (which label geometry trains the model, not a live-risk bound).
    pt_cost_mult = float(_f(config, "ml.label_pt_cost_mult", 0.0))
    if not (0.0 <= pt_cost_mult <= 20.0):
        fatal(f"ml.label_pt_cost_mult={pt_cost_mult} outside [0, 20] - 0 "
              f"disables the cost floor (legacy), values above 20 floor "
              f"sigma into an unrecognizable barrier")
    elif 0.0 < pt_cost_mult < 2.0:
        warn(f"ml.label_pt_cost_mult={pt_cost_mult} floors the profit "
             f"distance at under 2x round-trip cost - costs above 50% of "
             f"the profit distance, the bet the floor exists to prevent")

    # bracket exits (spec D1/D5, 2026-07-27, geometry-alignment task 5,
    # docs/superpowers/specs/2026-07-27-geometry-alignment-design.md):
    # a bracket position's exits trade the triple-barrier bet - incoherent
    # (and untested) if the model isn't even labeled that way. FATAL
    # regardless of dry_run, same class as the label_mode check above
    # (config-nonsense about which bet is traded, not a live-risk bound).
    if bool(_f(config, "bracket_exits.enabled", False)) \
            and lbl_mode != "triple_barrier":
        fatal(f"bracket_exits.enabled=true requires ml.label_mode="
              f"'triple_barrier' (got {lbl_mode!r}) - the bracket trades "
              f"the triple-barrier bet (barrier_geometry(), same helper "
              f"the candidate labeler calls); trading it while the model "
              f"is labeled under a different definition prices a bet "
              f"nobody is training on")
    sgf = float(_f(config, "ml.postmortem.stop_gap_factor", 2.0))
    if sgf <= 1.0:
        fatal(f"ml.postmortem.stop_gap_factor={sgf} must be > 1.0 - at or "
              f"below 1x every ordinary slippage-past-stop fill becomes an "
              f"'ops failure' and the cost/whipsaw governors go blind to "
              f"real execution problems")
    elif sgf > 5.0:
        warn(f"ml.postmortem.stop_gap_factor={sgf} above 5x will almost "
             f"never fire - unenforced-stop losses will keep polluting the "
             f"cost governor (the 2026-07-14 failure this knob exists for)")

    # multi-horizon shadow: every horizon must be a positive integer no
    # larger than the primary label horizon, or its outcome would never be
    # ready when the primary label fires (the shadow row would be silently
    # dropped, defeating the whole point of collecting the evidence)
    mh = config.get("ml", {}).get("multi_horizon", {}) or {}
    if mh.get("enabled", False):
        max_bars = int(_f(config, "ml.label_max_bars", 96))
        horizons = mh.get("horizons_bars", [])
        if not horizons:
            fatal("ml.multi_horizon.enabled but horizons_bars is empty")
        for h in horizons:
            if not isinstance(h, (int, float)) or int(h) <= 0:
                fatal(f"ml.multi_horizon.horizons_bars has non-positive {h!r}")
            elif int(h) > max_bars:
                fatal(f"ml.multi_horizon horizon {int(h)} > label_max_bars "
                      f"{max_bars} - would never be labeled")

    # State-Change Sampler: cusum_k is the sigma-multiple event threshold.
    # Below 1 sigma nearly every bar triggers - clock sampling by another
    # name, defeating the filter; above 6 events all but vanish and the
    # candidate corpus starves. Calibrated plateau is k in [1,4]; the
    # bound leaves headroom without allowing a self-defeating config.
    smp = config.get("ml", {}).get("sampling", {}) or {}
    if smp.get("cusum_enabled", False):
        cusum_k = float(smp.get("cusum_k", 3.0))
        if not (1.0 <= cusum_k <= 6.0):
            fatal(f"ml.sampling.cusum_k={cusum_k} outside [1.0, 6.0] - "
                  f"below 1 sigma the event filter degenerates to clock "
                  f"sampling (defeats the uniqueness win); above 6 it "
                  f"starves the training corpus")

    # adaptive_gbt (opt-in top ladder rung): bounds so an enabled config
    # can't degrade the learner. max_total_trees must sit comfortably above
    # a base GBT fit (~n_estimators, default 300) or warm_update would find
    # no room and continuous learning would silently never fire.
    ag = config.get("ml", {}).get("adaptive_gbt", {}) or {}
    if ag.get("enabled", False):
        bags = int(_f(config, "ml.adaptive_gbt.bags", 4))
        if not (1 <= bags <= 16):
            fatal(f"ml.adaptive_gbt.bags ({bags}) must be in [1, 16] - one "
                  f"bag is a plain gbt with overhead; >16 just burns train "
                  f"time for vanishing variance reduction")
        warm = int(_f(config, "ml.adaptive_gbt.warm_rounds", 25))
        if not (1 <= warm <= 200):
            fatal(f"ml.adaptive_gbt.warm_rounds ({warm}) must be in [1, 200] "
                  f"- <1 disables continuous learning, >200 lets one warm "
                  f"batch dominate the trained ensemble")
        cap = int(_f(config, "ml.adaptive_gbt.max_total_trees", 800))
        if cap < 400:
            fatal(f"ml.adaptive_gbt.max_total_trees ({cap}) must be >= 400 - "
                  f"below a base fit's ~300 trees, warm_update never has room "
                  f"and continuous learning silently never fires")

    # model-selection evidence gate: floors must be coherent or the ladder
    # admits complexity out of order (train adaptive_gbt but not gbt) or a
    # family enters selection on fewer TOTAL rows than the LIVE floor it just
    # cleared. Complexity order fixed: gbt <= blend <= mlp <= adaptive_gbt.
    ms = config.get("ml", {}).get("model_selection", {}) or {}
    if ms.get("enabled", False):
        _order = ("gbt", "blend", "mlp", "adaptive_gbt")
        for _key in ("min_live_rows", "min_total_rows"):
            floors = ms.get(_key, {}) or {}
            prev, prev_fam = -1, None
            for fam in _order:
                if fam not in floors:
                    continue
                val = int(floors[fam])
                if val < 0:
                    fatal(f"ml.model_selection.{_key}.{fam} ({val}) must be "
                          f">= 0")
                if val < prev:
                    fatal(f"ml.model_selection.{_key} non-monotonic: {fam}="
                          f"{val} < {prev_fam}={prev} - a more complex family "
                          f"would be admitted on LESS evidence than a simpler "
                          f"one, so the ladder could train {fam} but not "
                          f"{prev_fam}")
                prev, prev_fam = val, fam
        live_f = ms.get("min_live_rows", {}) or {}
        total_f = ms.get("min_total_rows", {}) or {}
        for fam in _order:
            if fam in live_f and fam in total_f and \
                    int(total_f[fam]) < int(live_f[fam]):
                fatal(f"ml.model_selection floors incoherent for {fam}: "
                      f"min_total_rows ({total_f[fam]}) < min_live_rows "
                      f"({live_f[fam]}) - total includes live, so the total "
                      f"floor can never bind and is a config typo")

    # --- ml.sample_weights: de Prado corrections (AFML ch.4) --------------
    sw = config.get("ml", {}).get("sample_weights", {}) or {}
    if sw:
        gsec = float(sw.get("uniqueness_grid_sec", 300))
        if not (30.0 <= gsec <= 3600.0):
            fatal(f"ml.sample_weights.uniqueness_grid_sec ({gsec}) outside "
                  f"[30, 3600]s - the grid must be near the signal cadence "
                  f"(finer burns CPU for nothing, coarser blurs concurrency)")
        ufl = float(sw.get("uniqueness_floor", 0.05))
        if not (0.0 <= ufl <= 1.0):
            fatal(f"ml.sample_weights.uniqueness_floor ({ufl}) outside "
                  f"[0, 1] - it bounds the uniqueness discount")
        tbw = float(sw.get("time_barrier_zero_weight", 1.0))
        if not (0.0 < tbw <= 1.0):
            fatal(f"ml.sample_weights.time_barrier_zero_weight ({tbw}) "
                  f"outside (0, 1] - 0 would erase every no-touch zero "
                  f"(discarding evidence); >1 would overweight the weakest "
                  f"label class")
        pw = float(sw.get("prior_skew_window_h", 24))
        if not (1.0 <= pw <= 168.0):
            fatal(f"ml.sample_weights.prior_skew_window_h ({pw}) outside "
                  f"[1, 168]h")
        pt = float(sw.get("prior_skew_threshold", 0.25))
        if not (0.05 <= pt <= 0.9):
            fatal(f"ml.sample_weights.prior_skew_threshold ({pt}) outside "
                  f"[0.05, 0.9] - below is noise, above never fires")
        pm = int(sw.get("prior_skew_min_rows", 30))
        if pm < 10:
            fatal(f"ml.sample_weights.prior_skew_min_rows ({pm}) < 10 - the "
                  f"window prior is meaningless on fewer rows")

    # --- ml.telemetry: report-only sim-to-live instruments (T2.2) ---------
    tele = config.get("ml", {}).get("telemetry", {}) or {}
    if tele:
        lmp = int(_f(config, "ml.telemetry.lineage_min_pairs", 10))
        if not (1 <= lmp <= 10000):
            fatal(f"ml.telemetry.lineage_min_pairs ({lmp}) outside "
                  f"[1, 10000] - reporting threshold, not a gate")
        dwh = float(_f(config, "ml.telemetry.divergence_window_h", 24.0))
        if not (1.0 <= dwh <= 168.0):
            fatal(f"ml.telemetry.divergence_window_h ({dwh}) outside "
                  f"[1, 168] hours - must bucket meaningfully within a "
                  f"trading week")
        # ML-080 barrier/exit-reason mix-drift alarm (label-era
        # instrumentation, DEEP DIVE progress.md) - report-only, same
        # bounds philosophy as the prior-skew detector above (a window
        # too short/long can't bucket meaningfully; a threshold too low
        # is noise, too high never fires).
        emdw = float(_f(config, "ml.telemetry.era_mix_drift_window_h", 24.0))
        if not (1.0 <= emdw <= 168.0):
            fatal(f"ml.telemetry.era_mix_drift_window_h ({emdw}) outside "
                  f"[1, 168] hours - must bucket meaningfully within a "
                  f"trading week")
        emmr = int(_f(config, "ml.telemetry.era_mix_drift_min_rows", 30))
        if emmr < 10:
            fatal(f"ml.telemetry.era_mix_drift_min_rows ({emmr}) < 10 - the "
                  f"recent-window mix is meaningless on fewer rows")
        emt = float(_f(config, "ml.telemetry.era_mix_drift_tvd_threshold",
                      0.3))
        if not (0.05 <= emt <= 0.9):
            fatal(f"ml.telemetry.era_mix_drift_tvd_threshold ({emt}) "
                  f"outside [0.05, 0.9] - below is noise, above never "
                  f"fires (TVD is bounded [0, 1])")
        # ML-082 labeled-vs-realized bracket comparator (geometry-alignment
        # T6, spec D6) - report-only, same bounds philosophy: a tolerance
        # too tight flags every close as "disagree" on ordinary fee/
        # slippage noise, too loose never flags a genuine execution gap; a
        # window too short (< 10) is a coin flip, absurdly long buries a
        # recent regression under stale history.
        bdt = float(_f(config, "ml.telemetry.bracket_divergence_tolerance_pct",
                      0.15))
        if not (0.01 <= bdt <= 5.0):
            fatal(f"ml.telemetry.bracket_divergence_tolerance_pct ({bdt}) "
                  f"outside [0.01, 5.0] percentage points - below is noise "
                  f"on ordinary fee/slippage rounding, above never flags a "
                  f"real execution gap")
        bdw = int(_f(config, "ml.telemetry.bracket_divergence_window_n", 100))
        if not (10 <= bdw <= 5000):
            fatal(f"ml.telemetry.bracket_divergence_window_n ({bdw}) "
                  f"outside [10, 5000] - too few closes is a coin flip, "
                  f"too many buries a recent regression under stale "
                  f"history")

    # --- ml.linkage: T2.4 FS-EM record-linkage report (scripts/
    # corpus_linkage_report.py) - report-only, no weight authority ---------
    lk = config.get("ml", {}).get("linkage", {}) or {}
    if lk:
        thr = float(_f(config, "ml.linkage.posterior_threshold", 0.9))
        if not (0.5 <= thr <= 0.999):
            fatal(f"ml.linkage.posterior_threshold ({thr}) outside "
                  f"[0.5, 0.999] - below 0.5 links majority-non-match "
                  f"patterns; 1.0 links nothing")
        lseed = _f(config, "ml.linkage.seed", 7)
        if not isinstance(lseed, int) or isinstance(lseed, bool) or lseed < 0:
            fatal(f"ml.linkage.seed ({lseed!r}) must be a non-negative "
                  f"integer - EM init determinism")

    # --- ml.epoch: T3.6a config-derivation-boundary marker (report-only,
    # scripts/overfit_check.py's --epoch-ab experiment arm reads it; never a
    # production-path row exclusion) --------------------------------------
    ep = config.get("ml", {}).get("epoch", {}) or {}
    if ep:
        cutoff = ep.get("candidate_cutoff_ts")
        if not isinstance(cutoff, (int, float)) or isinstance(cutoff, bool):
            fatal(f"ml.epoch.candidate_cutoff_ts ({cutoff!r}) must be a "
                  f"number (epoch seconds)")
        elif not (1752000000 <= float(cutoff) <= 1900000000):
            fatal(f"ml.epoch.candidate_cutoff_ts ({cutoff}) outside the "
                  f"corpus's plausible range [1752000000, 1900000000] - not "
                  f"a real config-derivation-boundary timestamp")
        # T3.6 production loader seam (ml/history.py load_training_data's
        # epoch_cfg, SHIPPED OFF - exclude_old_candidates: false): the
        # existing checks above already require a valid cutoff whenever
        # this block is present at all (the report-only --epoch-ab
        # experiment arm needs one too), but the flag that actually
        # activates a PRODUCTION training-corpus filter earns its own
        # explicit, purpose-named FATAL rather than riding the report-
        # only block's coattails - a future edit that relaxes the block-
        # presence check must not silently let exclude_old_candidates:
        # true ship with no real cutoff.
        excl_old = ep.get("exclude_old_candidates", False)
        if not isinstance(excl_old, bool):
            fatal(f"ml.epoch.exclude_old_candidates ({excl_old!r}) must "
                  f"be a boolean")
        elif excl_old and (not isinstance(cutoff, (int, float))
                           or isinstance(cutoff, bool)):
            fatal(f"ml.epoch.exclude_old_candidates is true but "
                  f"ml.epoch.candidate_cutoff_ts ({cutoff!r}) is missing/"
                  f"invalid - the production epoch filter (T3.6) cannot "
                  f"activate without a real cutoff")

    # --- ml.era_exclusion: era-gated training exclusion (operator
    # decision, 2026-07-26, docs/quant/2026-07-26_era_exclusion.md) -
    # threshold-armed, reversible LOAD-TIME view over ml/history.py's
    # load_training_data. A DIFFERENT mechanism from ml.epoch above
    # (era-based via label_era_of, never a clock; covers LIVE rows too -
    # an explicit operator override of the epoch filter's "live rows
    # never" rule) - see the doc for the full rationale. Unlike ml.epoch
    # (shipped false forever until a conscious future flip), this feature
    # auto-activates on the DATA alone once wired, so its coherence must
    # be enforced NOW, not deferred to some later flip-day commit. ------
    era_ex = config.get("ml", {}).get("era_exclusion", {}) or {}
    if era_ex:
        min_new = era_ex.get("min_new_era_rows", 150)
        if isinstance(min_new, bool) or not isinstance(min_new, (int, float)) \
                or min_new < 0:
            fatal(f"ml.era_exclusion.min_new_era_rows ({min_new!r}) must "
                  f"be a non-negative number - the new-era row-count floor "
                  f"that arms the filter")
        else:
            # OBJ-8: the arming floor and the OVERFIT battery's corpus floor
            # are two INDEPENDENT measurement standards over the SAME corpus,
            # and nothing orders them. min_new_era_rows arms this filter (all
            # old-era rows dropped) at a loaded-row count that can still sit
            # BELOW scripts/overfit_check.py load_dataset's substitution
            # floor - and in that window the bot trains on a clean single-era
            # corpus while the whole OF battery is measuring a planted-signal
            # SYNTHETIC benchmark instead of the market. Both greens are real;
            # they are just answers to different questions, and only the
            # battery's own corpus line distinguishes them.
            #   NOT a FATAL: this is the SHIPPED, intentional configuration
            # (150 < 640 as shipped), and it recurs at EVERY horizon
            # migration - a new label era restarts the new-era count at zero,
            # so the window reopens by design each time. Refusing to start the
            # bot over a known, correct config would be strictly worse than
            # trading with the instrument honestly labelled, which is what
            # this WARN does. FEATURE_NAMES is imported lazily here for the
            # same module-purity reason as the gbt_mono / label-era imports in
            # this function (zero in-repo imports at MODULE level).
            from ml.features import FEATURE_NAMES
            of_floor = len(FEATURE_NAMES) * _OVERFIT_ROWS_PER_FEATURE
            if min_new < of_floor:
                warn(f"ml.era_exclusion.min_new_era_rows ({min_new:g}) is "
                     f"BELOW scripts/overfit_check.py's synthetic-"
                     f"substitution floor ({of_floor} = "
                     f"{len(FEATURE_NAMES)} features x "
                     f"{_OVERFIT_ROWS_PER_FEATURE} rows/feature) - a "
                     f"{of_floor - min_new:g}-row window in which the era "
                     f"filter is ARMED (>= {min_new:g} new-era rows, so "
                     f"every old-era row is dropped from the training view) "
                     f"while the loaded corpus is still under {of_floor} and "
                     f"the OF battery has substituted its planted-signal "
                     f"SYNTHETIC benchmark. Inside that window the battery "
                     f"validates the MACHINERY, not the market: its green is "
                     f"NOT evidence the deployed strategy is un-overfit, and "
                     f"OF-4/OF-5 may additionally be inert. This reopens at "
                     f"EVERY horizon migration. BOTH numbers are MEASUREMENT "
                     f"STANDARDS, not tunables - do NOT raise "
                     f"min_new_era_rows and do NOT lower the overfit floor "
                     f"to silence this warning; moving either one so a gate "
                     f"reads 'real' is the widening the overfit discipline "
                     f"forbids. The correct response is to read the overfit "
                     f"battery's corpus line on EVERY run and to treat a "
                     f"SYNTHETIC green as UNPROVEN until the loaded corpus "
                     f"clears {of_floor} rows on its own.")
        forced_off = era_ex.get("forced_off", False)
        if not isinstance(forced_off, bool):
            fatal(f"ml.era_exclusion.forced_off ({forced_off!r}) must be "
                  f"a boolean")
        forced_on = era_ex.get("forced_on", False)
        if not isinstance(forced_on, bool):
            fatal(f"ml.era_exclusion.forced_on ({forced_on!r}) must be a "
                  f"boolean")
        if isinstance(forced_off, bool) and isinstance(forced_on, bool) \
                and forced_off and forced_on:
            fatal("ml.era_exclusion.forced_on and forced_off are both "
                  "true - contradictory operator intent (force the filter "
                  "active vs force it inactive); the rollback lever and "
                  "the manual-override lever cannot both be pulled")
        # forced_off carried only a TYPE check while forced_on carried a
        # semantic one - an asymmetry with no justification: forced_off is
        # the lever with the larger blast radius of the two, because it is
        # the one that silently makes the corpus BIGGER. Parity, as a WARN
        # rather than a FATAL: true is a LEGITIMATE rollback mode (the same
        # shape as the passive_hazard_with_book warn above - a FATAL would
        # make the pre-exclusion view unreachable, which is the one thing a
        # rollback lever may never be). It must simply never be true by
        # accident, or as a way to make a starved corpus look fed.
        if isinstance(forced_off, bool) and forced_off:
            warn("ml.era_exclusion.forced_off=true forces the era filter "
                 "OFF regardless of min_new_era_rows - config.json's own "
                 "_era_exclusion_doc: 'the rollback lever - forces the "
                 "filter OFF regardless of the threshold; flipping it (+ "
                 "restart) restores the pre-exclusion training set "
                 "exactly'. That restored view POOLS every label era on "
                 "disk, i.e. several different label DEFINITIONS trained as "
                 "one target - the exact mixing era exclusion exists to "
                 "prevent. Measured 2026-08-15 on the 10,671-row corpus: "
                 "five eras spanning ~40x in base rate (exit_sim_time_stop "
                 "0.65% ... legacy 26.1%), loaded rows 365 -> 10,534. It is "
                 "a ROLLBACK lever, never a way to recover corpus size or "
                 "entry volume: it adds no new-era row, so it can lift the "
                 "overfit battery off its SYNTHETIC benchmark while making "
                 "the corpus LESS comparable, not more - a REAL-corpus "
                 "green bought this way is worth less than the synthetic "
                 "one it replaced.")
        if isinstance(forced_on, bool) and forced_on:
            # lazy import - config_guard is deliberately kept free of
            # in-repo cross-package imports AT MODULE SCOPE (see the
            # gbt_mono check above for the established rationale/
            # precedent; this is another such load-time-only import).
            from ml.history import LABEL_ERA_TRIPLE_BARRIER
            era_label_mode = str(config.get("ml", {}).get(
                "label_mode", "exit_policy"))
            if era_label_mode != LABEL_ERA_TRIPLE_BARRIER:
                fatal(f"ml.era_exclusion.forced_on is true but "
                      f"ml.label_mode ({era_label_mode!r}) is not "
                      f"{LABEL_ERA_TRIPLE_BARRIER!r} - the labeler can "
                      f"never produce the era this filter selects for "
                      f"under this label mode (the era tag it needs is "
                      f"unavailable), so a forced-on filter would train "
                      f"on zero rows forever")

    # --- ml.gbt_mono: T3.4 monotone-constrained GBT ladder rung (shipped
    # disabled - ml/models.py GradientBoostedStumps.monotone_constraints).
    # Constraint names are validated against the CURRENT feature contract
    # even while the rung is off: a typo should FATAL at config-load time,
    # not silently surface only after an operator later flips enabled:true.
    # FEATURE_NAMES is imported HERE, lazily, inside the check - NOT at
    # module scope - because config_guard is deliberately kept free of
    # in-repo cross-package imports AT MODULE SCOPE (guard purity: it must
    # be importable before the rest of the package is fully wired). This
    # is not the only such lazy, load-time-only in-repo import in this
    # file (see e.g. the skimmer pair-meta check's `from data.kraken_feed
    # import PAIR_META_FALLBACK` and the exploration/sizer breakeven
    # checks' `from risk.position_sizer import payoff_ratio_from_config`,
    # further down) - the invariant this file actually holds is ZERO
    # in-repo imports at MODULE level, not "at most one in-repo import
    # anywhere in the file".
    gm = config.get("ml", {}).get("gbt_mono", {}) or {}
    constraints = gm.get("constraints", {}) or {}
    if constraints:
        from ml.features import FEATURE_NAMES
        if len(constraints) > 12:
            warn(f"ml.gbt_mono.constraints has {len(constraints)} entries "
                 f"(>12) - sign confidence for this many a priori economic "
                 f"priors at once is unlikely to hold for all of them; "
                 f"re-derive from first principles, don't just add more")
        for name, sign in constraints.items():
            if name not in FEATURE_NAMES:
                fatal(f"ml.gbt_mono.constraints has unknown feature "
                      f"{name!r} - not in FEATURE_NAMES (ml/features.py); "
                      f"the monotone rung cannot resolve it to a column "
                      f"index")
            elif isinstance(sign, bool) or sign not in (1, -1):
                fatal(f"ml.gbt_mono.constraints[{name!r}] = {sign!r} must "
                      f"be 1 (non-decreasing) or -1 (non-increasing)")

    # --- markout: post-fill mark-out measurement (execution/markout.py) ---
    # window <= 0 makes MarkoutTracker's _obs a deque(maxlen<=0): 0 is a
    # silent blackhole (every observation discarded on append, the tracker
    # runs but never accumulates); a negative maxlen isn't validated by
    # collections.deque until the FIRST lazy defaultdict access mid-cycle,
    # where it raises ValueError - a crash-loop discovered only in
    # production, not at boot. horizons_sec must be non-empty with every
    # entry positive when the tracker is enabled, or record_fill/poll are
    # no-ops that silently measure nothing.
    mk = config.get("markout", {}) or {}
    if bool(mk.get("enabled", True)):
        mk_window = int(mk.get("window", 200))
        if mk_window < 1:
            fatal(f"markout.window={mk_window} must be >= 1 - 0 silently "
                  f"discards every observation (a blackhole deque), "
                  f"negative raises ValueError lazily on first mid-cycle "
                  f"access")
        mk_hz = mk.get("horizons_sec", [5.0, 30.0, 60.0]) or []
        if not mk_hz:
            fatal("markout.enabled but horizons_sec is empty - nothing to "
                  "measure")
        elif any(not isinstance(h, (int, float)) or float(h) <= 0
                 for h in mk_hz):
            fatal(f"markout.horizons_sec={mk_hz!r} has a non-positive entry "
                  f"- every horizon must be > 0 seconds")
        mk_grace = float(mk.get("grace_sec", 15.0))
        if mk_grace < 0:
            fatal(f"markout.grace_sec={mk_grace} must be >= 0")

    # --- watchdog: tail-event sentry (core/watchdog.py) --------------------
    # inverted/equal warn-vs-critical un-blocks entries on a dead feed: the
    # critical trip (operator alert, "stops are blind") can only ever fire
    # AFTER the warn trip in evaluate(), so warn >= critical means critical
    # never has room to fire above warn (or fires simultaneously, which is
    # not "graduated" tail handling - it's a single silent step). The pnl-
    # velocity/tick-quarantine/equity-drift knobs are all rate/magnitude
    # gates that must be positive or the corresponding trip either fires on
    # every cycle (0 threshold) or never resets (0 cooldown).
    wd = config.get("watchdog", {}) or {}
    if bool(wd.get("enabled", True)):
        wd_warn = float(wd.get("stale_warn_sec", 30))
        wd_crit = float(wd.get("stale_critical_sec", 120))
        if not (0.0 < wd_warn < wd_crit):
            fatal(f"watchdog stale thresholds incoherent: stale_warn_sec="
                  f"{wd_warn} must be > 0 and strictly below "
                  f"stale_critical_sec={wd_crit} - inverted/equal leaves the "
                  f"critical trip (operator alert, stops blind) unable to "
                  f"fire after the warn trip")
        wd_vel_window = float(wd.get("pnl_velocity_window_sec", 900))
        if wd_vel_window <= 0:
            fatal(f"watchdog.pnl_velocity_window_sec={wd_vel_window} must be "
                  f"positive - it is the rolling window the velocity trip "
                  f"measures equity drop over")
        wd_vel_drop = float(wd.get("pnl_velocity_max_drop_pct", 6.0))
        if wd_vel_drop <= 0:
            fatal(f"watchdog.pnl_velocity_max_drop_pct={wd_vel_drop} must be "
                  f"positive - <= 0 trips the velocity halt on ordinary "
                  f"equity noise")
        wd_vel_cd = float(wd.get("pnl_velocity_cooldown_sec", 1800))
        if wd_vel_cd <= 0:
            fatal(f"watchdog.pnl_velocity_cooldown_sec={wd_vel_cd} must be "
                  f"positive - <= 0 means the velocity trip never latches "
                  f"(re-arms on the very next healthy tick)")
        wd_tick = float(wd.get("tick_jump_quarantine_pct", 8.0))
        if wd_tick <= 0:
            fatal(f"watchdog.tick_jump_quarantine_pct={wd_tick} must be "
                  f"positive - <= 0 quarantines every tick, holding stops "
                  f"one cycle forever")
        wd_drift = float(wd.get("max_equity_drift_pct", 2.0))
        if wd_drift <= 0:
            fatal(f"watchdog.max_equity_drift_pct={wd_drift} must be "
                  f"positive - <= 0 flags the live equity-truth check on "
                  f"ordinary rounding noise")

    # --- fair_value: Kraken-touch staleness bound (W2-23) ------------------
    # at 0, `(now - kraken_touch_ts) > 0` is true on every cycle except the
    # exact instant the touch was stamped, so the touch never holds even
    # across a single missed poll - zeroing basis_bps/edge_bps constantly.
    fv_stale = float(_f(config, "fair_value.kraken_stale_sec", 120.0))
    if fv_stale <= 0:
        fatal(f"fair_value.kraken_stale_sec={fv_stale} must be positive - "
              f"at 0 the Kraken touch never holds across even a single "
              f"missed poll, so basis_bps/edge_bps read zero every cycle")

    # --- capital / risk ladder ------------------------------------------
    start_cap = float(_f(config, "capital_management.starting_capital_usd", 0))
    if start_cap <= 0 and not dry_run:
        fatal("capital_management.starting_capital_usd must be > 0 in live "
              "mode (the dry-run '0 -> $10k paper' default never applies to "
              "real money)")
    daily = float(_f(config, "capital_management.daily_loss_limit_pct", 5))
    hard = float(_f(config, "capital_management.hard_stop_drawdown_pct", 15))
    # profit-split parity: the reinvested share is IMPLICITLY
    # (100 - savings_pct) in CapitalManager.record_realized_profit; the
    # reinvestment knob is informational. If an operator sets the two to
    # numbers that don't sum to 100, the config is lying about where profit
    # goes — refuse rather than silently honoring only savings_pct.
    sav = float(_f(config, "capital_management.savings_pct_of_profit", 20))
    resv = float(_f(config, "capital_management.reserve_pct_of_profit", 0))
    reinv = float(_f(config, "capital_management.reinvestment_pct_of_profit",
                     100 - sav - resv))
    if not (0.0 <= sav <= 100.0):
        fatal(f"capital_management.savings_pct_of_profit ({sav}) outside "
              f"[0, 100]")
    if not (0.0 <= resv <= 50.0):
        fatal(f"capital_management.reserve_pct_of_profit ({resv}) outside "
              f"[0, 50] - above half of every win into the shock "
              f"absorber starves both compounding and savings")
    if abs(sav + resv + reinv - 100.0) > 1e-9:
        fatal(f"capital_management profit split incoherent: savings "
              f"({sav}) + reserve ({resv}) + reinvestment ({reinv}) "
              f"must sum to 100 - the split silently lies about "
              f"where profit goes otherwise")
    if daily <= 0 or hard <= 0:
        fatal("loss limits must be positive")
    elif daily >= hard:
        fatal(f"daily_loss_limit_pct ({daily}) must be below "
              f"hard_stop_drawdown_pct ({hard}) - the daily brake must "
              f"engage before the parachute")

    max_conc = int(_f(config, "capital_management.max_concurrent_positions", 3))
    if max_conc < 1:
        fatal(f"capital_management.max_concurrent_positions ({max_conc}) "
              f"must be >= 1 - at 0 can_open_new_position vetoes every "
              f"entry and the bot idles silently")

    # profit goals (measurement only): a target must be a non-negative
    # number; 0 disables grading for that period. Negative is nonsense
    # (a "goal" of losing money), and a goal above the hard-stop loss
    # bound is unreachable by construction - flag it rather than grade
    # every period a guaranteed miss.
    wkg = float(_f(config, "capital_management.weekly_profit_goal_usd", 0))
    mog = float(_f(config, "capital_management.monthly_profit_goal_usd", 0))
    cap_ceiling = start_cap * hard / 100.0    # a period can't out-earn the
    for _name, _v in (("weekly_profit_goal_usd", wkg),
                      ("monthly_profit_goal_usd", mog)):
        if _v < 0.0:
            fatal(f"capital_management.{_name} ({_v}) is negative - a "
                  f"profit goal is a target to beat, not a loss budget")
        if cap_ceiling > 0 and _v > cap_ceiling * 4.0:
            fatal(f"capital_management.{_name} ({_v}) is unreachable: "
                  f"above 4x the hard-stop loss bound ({cap_ceiling:.0f}) "
                  f"every period grades a guaranteed miss - set a real "
                  f"target or 0 to disable grading")

    soft = float(_f(config, "inventory.soft_cap_pct_of_equity", 15))
    hardc = float(_f(config, "inventory.hard_cap_pct_of_equity", 25))
    if soft >= hardc:
        fatal(f"inventory soft cap ({soft}) must be below hard cap ({hardc})")

    mss = int(_f(config, "inventory.max_same_side_positions_per_asset", 2))
    if mss < 1:
        fatal(f"inventory.max_same_side_positions_per_asset ({mss}) must be "
              f">= 1 - at 0 every entry is vetoed as crowded")
    n_pairs = len(_f(config, "exchanges.kraken.trading_pairs", []) or [])
    if n_pairs and mss * 2 * n_pairs < max_conc:
        warn(f"max_concurrent_positions ({max_conc}) can never be reached: "
             f"{n_pairs} pairs x {mss} same-side cap x 2 directions = "
             f"{mss * 2 * n_pairs} slots. Not dangerous, just unreachable.")

    ex_share = float(_f(config, "ml.exploration.max_asset_share", 0.5))
    if not (0.0 < ex_share <= 1.0):
        fatal(f"ml.exploration.max_asset_share ({ex_share}) must be in "
              f"(0, 1] - at 0 exploration never fires once any asset has a "
              f"labeled row; 1 disables the share check")
    if int(_f(config, "ml.exploration.share_min_rows", 10)) < 1:
        fatal("ml.exploration.share_min_rows must be >= 1")
    # ML-073 label realization: the maturity horizon must be at least one full
    # label window (the barrier has to have fired) and not absurdly long, or a
    # position never matures and the starvation loop never clears.
    rls = float(_f(config, "ml.exploration.realize_after_label_spans", 1.0))
    if bool(_f(config, "ml.exploration.realize_mature_labels", True)) and \
            not (1.0 <= rls <= 6.0):
        fatal(f"ml.exploration.realize_after_label_spans ({rls}) must be in "
              f"[1, 6] label spans - below 1 closes positions before the "
              f"triple-barrier label window even resolves; above 6 they sit so "
              f"long the SD-002 starvation loop never clears")
    # fastpath: only binds when the book is FULL (buying a teach slot). A
    # shortened-hold realized label is honest ground truth of that hold —
    # but below a quarter-span the holds get so short the labels are churn,
    # not outcomes. 0 disables; otherwise [0.25, realize_after_label_spans].
    rfp = float(_f(config, "ml.exploration.realize_fastpath_spans", 0.0))
    if bool(_f(config, "ml.exploration.realize_mature_labels", True)) and \
            rfp != 0.0 and not (0.25 <= rfp <= rls):
        fatal(f"ml.exploration.realize_fastpath_spans ({rfp}) must be 0 "
              f"(disabled) or in [0.25, realize_after_label_spans={rls}] - "
              f"shorter holds than a quarter-span teach churn, and a "
              f"fastpath above the full horizon never fires")
    # drought extension: arms the fastpath with FREE slots after this many
    # hours without an admitted entry. Meaningless without a fastpath; sane
    # only between "one label span" scale and "a day" (longer = never fires
    # inside a weekend, the exact drought it was built for).
    rdh = float(_f(config, "ml.exploration.realize_drought_h", 0.0))
    if bool(_f(config, "ml.exploration.realize_mature_labels", True)) and \
            rdh != 0.0:
        if rfp == 0.0:
            fatal(f"ml.exploration.realize_drought_h ({rdh}) needs "
                  f"realize_fastpath_spans enabled - the drought extension "
                  f"only chooses WHEN the fastpath horizon applies")
        if not (0.25 <= rdh <= 24.0):
            fatal(f"ml.exploration.realize_drought_h ({rdh}) must be 0 "
                  f"(disabled) or in [0.25, 24] hours")

    # P3 corpus-aware probe throttle (2026-07-23 P&L diagnosis, SZ-047):
    # probes were 69% of live closes and -$22.87 of -$31.68 measured net
    # PnL - the corpus (3.3k rows / 214 live) has grown past the point
    # marginal probe value justifies the base admission rate. TWO
    # throttles, both toward a floor/cap (never to zero - the learner
    # keeps a trickle): a rolling SHARE CAP over the last
    # probe_share_window entry admissions, and a CORPUS DECAY scaling the
    # base epsilon down as live_labels grows past corpus_target_live.
    mps = float(_f(config, "ml.exploration.max_probe_share", 0.35))
    if not (0.0 < mps <= 1.0):
        fatal(f"ml.exploration.max_probe_share ({mps}) must be in (0, 1] - "
              f"at 0 the share cap denies every probe outright; 1 disables "
              f"the cap entirely")
    psw = int(_f(config, "ml.exploration.probe_share_window", 40))
    if not (10 <= psw <= 500):
        fatal(f"ml.exploration.probe_share_window ({psw}) must be in "
              f"[10, 500] - below 10 admissions the share binds/releases on "
              f"noise; above 500 it takes too many admissions to react to a "
              f"real change in probe demand")
    # F0b drought floor (grill C2): floor must stay a trickle, never a hose
    dfh = float(_f(config, "ml.exploration.drought_floor.drought_hours", 8.0))
    dfs = float(_f(config,
                   "ml.exploration.drought_floor.min_spacing_hours", 2.0))
    if dfh < 1.0:
        fatal(f"ml.exploration.drought_floor.drought_hours ({dfh}) must be "
              ">= 1.0 - a sub-hour 'drought' would fire the floor on "
              "ordinary quiet spells, not deadlocks")
    if dfs < 0.5:
        fatal(f"ml.exploration.drought_floor.min_spacing_hours ({dfs}) must "
              "be >= 0.5 - the floor is a trickle, not a stream")
    if dfs < dfh / 8.0:
        fatal(f"ml.exploration.drought_floor.min_spacing_hours ({dfs}) must "
              f"be >= drought_hours/8 ({dfh / 8.0:.2f}) - more than 8 floor "
              "probes per drought span exceeds the label-horizon bound "
              "(C2: <= K probes per 8h horizon)")
    cff = float(_f(config, "ml.exploration.corpus_decay.floor_frac", 0.25))
    if not (0.0 < cff <= 1.0):
        fatal(f"ml.exploration.corpus_decay.floor_frac ({cff}) must be in "
              f"(0, 1] - at 0 a mature corpus fully starves exploration "
              f"(the learner must keep a trickle); 1 disables the decay")
    ctl = int(_f(config, "ml.exploration.corpus_decay.corpus_target_live",
                300))
    dmo = int(_f(config, "ml.monitor.deploy_min_oof", 30))
    if ctl < dmo:
        warn(f"ml.exploration.corpus_decay.corpus_target_live ({ctl}) is "
             f"below ml.monitor.deploy_min_oof ({dmo}) - the probe throttle "
             f"would already be decaying admission below the model's own "
             f"OOF deploy floor; confirm this is intended")
    # the corpus decay only reaches its floor_frac floor once
    # live_labels >= corpus_target_live / floor_frac; until_live_rows hard-
    # offs exploration entirely at that row count, so if it fires BEFORE
    # the floor threshold, the decay's promised trickle-to-floor never
    # happens (decay only ever ranges [1.0, corpus_target_live /
    # until_live_rows), stopping short of floor_frac) - WARN, not FATAL:
    # ml.exploration.enabled=false makes this unreachable dead config.
    ulr = int(_f(config, "ml.exploration.until_live_rows", 1200))
    floor_reach_rows = ctl / cff if cff > 0 else float("inf")
    if ulr < floor_reach_rows:
        warn(f"ml.exploration.until_live_rows ({ulr}) hard-offs exploration "
             f"before the corpus decay can reach its floor_frac floor "
             f"(binds at corpus_target_live/floor_frac = {ctl}/{cff} = "
             f"{floor_reach_rows:.0f} live rows) - the decay's trickle "
             f"floor is unreachable; raise until_live_rows to at least "
             f"{floor_reach_rows:.0f} or the promised trickle never exists")

    # Task 4 (#103) regime-coverage hold: the decay above pools ALL
    # regimes into one live-label count, but probe value is regime-local
    # (a diagnostic found 227/234 live-labeled rows in a SINGLE regime).
    # regime_floor_live holds the decay term at 1.0 for whichever regime
    # is CURRENTLY under this per-regime floor. Derivation: corpus_target_
    # live (300) / 5 regime classes = 60 per-regime target.
    rfl = int(_f(config, "ml.exploration.corpus_decay.regime_floor_live", 60))
    if not (0 <= rfl <= ctl):
        fatal(f"ml.exploration.corpus_decay.regime_floor_live ({rfl}) must "
              f"be in [0, corpus_target_live={ctl}] - 0 disables the "
              f"regime-coverage hold (byte-identical P3 decay); above "
              f"corpus_target_live the per-regime floor could never be "
              f"crossed even once the GLOBAL corpus is fully mature, "
              f"permanently holding decay at 1.0")
    if rfl * 5 > ulr * cff:
        warn(f"ml.exploration.corpus_decay.regime_floor_live ({rfl}) x 5 "
             f"regime classes ({rfl * 5}) exceeds until_live_rows ({ulr}) "
             f"x floor_frac ({cff}) = {ulr * cff:.0f} - the regime floor "
             f"would still dominate the decay it modifies even once every "
             f"regime is EQUALLY represented at graduation; confirm this "
             f"is intended")

    # SPB-R probe-admission budget (docs/superpowers/specs/2026-07-30-
    # probe-budget-spbr-design.md §2). LANDED DARK: mode ships "share_cap"
    # (the byte-identical SZ-047 path); "budget" is the scarcity-priced
    # token bucket. Note (spec, C2's "FATAL zero-quota"): a zero-quota
    # check is structurally moot here - refill is CONTINUOUS (tokens/
    # engine-second), there is no integer quota to round to 0.
    adm_mode = str(_f(config, "ml.exploration.admission.mode", "share_cap"))
    if adm_mode not in ("share_cap", "budget"):
        fatal(f"ml.exploration.admission.mode ({adm_mode!r}) must be "
              f"'share_cap' (the shipped SZ-047 deque path, byte-identical) "
              f"or 'budget' (SPB-R scarcity-priced token bucket)")
    tpd = float(_f(config,
                   "ml.exploration.admission.budget.tokens_per_day", 15))
    if not (0.0 < tpd <= 100.0):
        fatal(f"ml.exploration.admission.budget.tokens_per_day ({tpd}) must "
              f"be in (0, 100] - 0 starves the learner outright; above 100 "
              f"the 'budget' stops being one")
    abh = float(_f(config,
                   "ml.exploration.admission.budget.burst_hours", 8.0))
    if not (1.0 <= abh <= 24.0):
        fatal(f"ml.exploration.admission.budget.burst_hours ({abh}) must be "
              f"in [1, 24] - the capacity window is a fraction of the day, "
              f"anchored on the labeler's own horizon")
    mcp = int(_f(config, "capital_management.max_concurrent_positions", 5))
    book_ceiling = mcp * 24.0 / abh if abh > 0 else float("inf")
    if tpd > book_ceiling:
        warn(f"ml.exploration.admission.budget.tokens_per_day ({tpd}) "
             f"exceeds the book conversion ceiling "
             f"(max_concurrent_positions {mcp} x 24/burst_hours {abh} = "
             f"{book_ceiling:.1f}/day) - budget above this buys tokens the "
             f"book cannot convert to labels")
    if dfh > 0 and tpd < 24.0 / dfh:
        warn(f"ml.exploration.admission.budget.tokens_per_day ({tpd}) is "
             f"below the SZ-048 drought-floor pace (24/drought_hours "
             f"{dfh} = {24.0 / dfh:.1f}/day) - the backstop would out-rate "
             f"the budget; the floor must be the exception, never the "
             f"governor")
    # capacity should mirror the labeler's horizon (label_max_bars x 5m
    # bars; BAR_SECONDS=300 is the harness convention, see cvar.bar_sec)
    lmb = int(_f(config, "ml.label_max_bars", 96))
    horizon_h = lmb * 300.0 / 3600.0
    if abs(abh - horizon_h) > 1e-9:
        warn(f"ml.exploration.admission.budget.burst_hours ({abh}) != the "
             f"labeler's own horizon (label_max_bars {lmb} x 5m = "
             f"{horizon_h:.1f}h) - capacity should mirror the label "
             f"horizon; confirm this divergence is intended")
    asf = _f(config,
             "ml.exploration.admission.budget.scarcity_floor", None)
    if asf is not None and not (0.0 < float(asf) <= 1.0):
        fatal(f"ml.exploration.admission.budget.scarcity_floor ({asf}) must "
              f"be null (reuse corpus_decay.floor_frac) or in (0, 1]")
    tfm = float(_f(config, "ml.exploration.admission.budget.governor."
                           "tuition_daily_frac_max", 0.001))
    if not (0.0 < tfm <= 0.005):
        fatal(f"ml.exploration.admission.budget.governor."
              f"tuition_daily_frac_max ({tfm}) must be in (0, 0.005] - the "
              f"tuition governor is a bound on realized probe losses, not "
              f"a wish")
    elif tfm > 0.002:
        warn(f"ml.exploration.admission.budget.governor."
             f"tuition_daily_frac_max ({tfm}) > 0.002 (20 bps equity/day "
             f"of probe tuition) - twice the designed 10 bps bound; "
             f"confirm this is intended")
    ocd = float(_f(config, "ml.exploration.admission.budget.governor."
                           "outlier_clip_div", 3))
    if not (1.0 <= ocd <= 10.0):
        fatal(f"ml.exploration.admission.budget.governor.outlier_clip_div "
              f"({ocd}) must be in [1, 10] - the per-close clip exists so "
              f"one probe is never evidence")
    elif dfh > 0 and ocd != round(24.0 / dfh):
        warn(f"ml.exploration.admission.budget.governor.outlier_clip_div "
             f"({ocd}) != round(24/drought_hours) = {round(24.0 / dfh)} - "
             f"the clip divisor is the floor pace (the governor may never "
             f"engage on fewer probes than the guaranteed daily floor "
             f"admits); confirm the divergence is intended")
    awz = float(_f(config, "ml.exploration.admission.budget.surcharge."
                           "wilson_z", 1.96))
    if not (1.0 <= awz <= 3.0):
        fatal(f"ml.exploration.admission.budget.surcharge.wilson_z ({awz}) "
              f"must be in [1, 3] - 1.96 is the standard 95% bound, "
              f"mandated by the small-n stats law, not tuned")
    amsur = float(_f(config, "ml.exploration.admission.budget.surcharge."
                             "max_surcharge", 2.0))
    asc_on = bool(_f(config,
                     "ml.exploration.admission.budget.surcharge.enabled",
                     False))
    if amsur < 1.0:
        fatal(f"ml.exploration.admission.budget.surcharge.max_surcharge "
              f"({amsur}) must be >= 1 - a surcharge below 1 would DISCOUNT "
              f"proven-worse arms")
    # coupled upper bound (spec §2): a surcharge must never exceed what
    # the scarcity floor could redeem (1/floor). FATAL only when the
    # surcharge is ENABLED: while it ships dark it computes nothing and
    # the price is clamped at C in code regardless - a legacy config
    # legitimately running floor_frac=1.0 (decay disabled) must not turn
    # FATAL through an unrelated dark knob's merge default.
    _adm_floor = float(asf) if asf is not None else cff
    _sur_cap = 1.0 / _adm_floor if _adm_floor > 0 else float("inf")
    if asc_on and amsur > _sur_cap:
        fatal(f"ml.exploration.admission.budget.surcharge.max_surcharge "
              f"({amsur}) must be in [1, 1/scarcity floor = {_sur_cap:.1f}]"
              f" while the surcharge is enabled - it may at most double a "
              f"price and never exceed what the scarcity floor could "
              f"redeem")
    if asc_on and _f(config, "ml.exploration.admission.budget."
                             "surcharge.era_min_ts", None) is None:
        fatal("ml.exploration.admission.budget.surcharge.enabled is true "
              "while era_min_ts is null - the Wilson-UPPER surcharge is "
              "era-filtered (post-PT-060 outcomes only) and REQUIRES the "
              "deploy epoch; set era_min_ts or keep the surcharge dark")
    if adm_mode == "budget" and \
            not bool(_f(config, "ml.exploration.enabled", False)):
        warn("ml.exploration.admission.mode is 'budget' while "
             "ml.exploration.enabled is false - dead config: the budget "
             "path is only ever reached when exploration itself is on")

    # Label horizon vs the exit ladder's no-progress scratch (2026-07-31
    # era-deadlock fix). `label_max_bars` is BOTH the label's vertical and
    # the live bracket deadline (main.py deadline_ts). If the ladder
    # scratches a position before the vertical can be reached, no live row
    # can ever carry a tb_* barrier -> every live label lands in an old
    # label era -> era exclusion drops it -> live_clean 0 -> the evidence
    # gate is pinned to logistic forever. That exact ordering was live
    # from 2026-07-26 to 2026-07-31; it must never return.
    # Scoped to configs that actually DECLARE a horizon: a fragment with
    # no ml block is making no claim about labeling and must not turn
    # FATAL through a default it never opted into (the same discipline as
    # the SPB-R surcharge bound). The shipped config always carries the
    # key, so the real pairing is always checked.
    _lmb_raw = _f(config, "ml.label_max_bars", None)
    if _lmb_raw is not None:
        lmb_g = int(_lmb_raw)
        if not (4 <= lmb_g <= 500):
            fatal(f"ml.label_max_bars ({lmb_g}) must be in [4, 500] bars")
        _ts_on = bool(_f(config, "profit_taking.time_stop.enabled", False))
        _ts_bars = int(_f(config,
                          "profit_taking.time_stop.max_bars_no_progress",
                          36))
        if _ts_on and lmb_g >= _ts_bars:
            fatal(f"ml.label_max_bars ({lmb_g}) must be BELOW "
                  f"profit_taking.time_stop.max_bars_no_progress "
                  f"({_ts_bars}): a vertical at or beyond the no-progress "
                  f"scratch is unreachable, so no live row can ever carry "
                  f"a tb_* barrier and the evidence gate starves (the "
                  f"2026-07-31 era deadlock)")

    # Candidate-queue capacity vs the label horizon (2026-08-16 label-
    # throughput fix). The labeler's pool is a Little's-law queue: slots
    # required = offered arrivals/h x slot residence, and with
    # multi_horizon shadows enabled residence is the FULL horizon for
    # EVERY candidate (ml/history.py poll() retains early-labeled
    # candidates until the shadow path completes). The 200 default was
    # sized for the 8h horizon and survived the 24->432 migration
    # unresized: at 36h it sat AT mean demand with zero headroom and 3.3x
    # under the measured peak, and because eviction pops the NEWEST
    # pending candidate, the signals refused labeling were exactly the
    # busy-hour ones (measured 2026-08-16: 84% of registrations on
    # fully-resolved launch spans produced no labeled row).
    _moc_raw = _f(config, "ml.max_open_candidates", None)
    _moc_ok = None
    if _moc_raw is not None:
        if isinstance(_moc_raw, bool) or \
                not isinstance(_moc_raw, (int, float)) or \
                int(_moc_raw) != _moc_raw:
            fatal(f"ml.max_open_candidates ({_moc_raw!r}) must be an "
                  f"integer - it is a queue slot count")
        elif not (8 <= int(_moc_raw) <= 10000):
            fatal(f"ml.max_open_candidates ({int(_moc_raw)}) must be in "
                  f"[8, 10000]: every pending candidate is persisted into "
                  f"EACH state.json snapshot (~KBs apiece), so an "
                  f"unbounded pool is an I/O and memory hazard, and a "
                  f"pool under 8 cannot hold even one bar of a "
                  f"multi-asset scan")
        else:
            _moc_ok = int(_moc_raw)
    _moc_lmb = int(_lmb_raw) if _lmb_raw is not None else None
    if _moc_lmb is not None and 4 <= _moc_lmb <= 500 and \
            (_moc_ok is not None or _moc_raw is None):
        _moc_eff = _moc_ok if _moc_ok is not None \
            else _CAND_QUEUE_CODE_DEFAULT
        _moc_src = "" if _moc_ok is not None \
            else ", the undeclared-key code default"
        _moc_h = _moc_lmb * 300.0 / 3600.0
        _moc_demand = math.ceil(_CAND_REF_PEAK_ARRIVALS_PER_H * _moc_h)
        _mh_c = config.get("ml", {}).get("multi_horizon", {}) or {}
        _shadow_retained = bool(_mh_c.get("enabled", False)) and any(
            isinstance(h, (int, float)) and 0 < int(h) <= _moc_lmb
            for h in (_mh_c.get("horizons_bars") or []))
        if _moc_eff < _moc_demand:
            _moc_msg = (
                f"ml.max_open_candidates ({_moc_eff}{_moc_src}) "
                f"is below the Little's-law demand of the configured "
                f"label horizon: ceil({_CAND_REF_PEAK_ARRIVALS_PER_H}/h "
                f"peak arrivals x label_max_bars {_moc_lmb} x 5m = "
                f"{_moc_h:.1f}h) = {_moc_demand} slots. A pool smaller "
                f"than the horizon's worth of peak arrivals saturates, "
                f"and the newest-pop eviction then refuses labeling to "
                f"exactly the busy-hour signals - the 36h-migration "
                f"regression (200 was the 8h-era size). Raise "
                f"ml.max_open_candidates; do NOT shorten label_max_bars "
                f"to satisfy this check. The reference rate is MEASURED "
                f"(peak 36h window of outputs/signal_history.csv "
                f"candidate-id seq spans, 2026-08-16) - re-derive it the "
                f"same way before moving it.")
            if _shadow_retained:
                fatal(_moc_msg + " FATAL because multi_horizon shadows "
                      "retain every candidate for the FULL horizon, so "
                      "the demand is structural, not market-dependent.")
            else:
                warn(_moc_msg + " WARN (not FATAL) because shadows are "
                     "off, so early labels release slots before the "
                     "horizon; time-barrier candidates still hold the "
                     "full horizon - confirm the cap is intended.")

    # Zombie-eviction margin (2026-08-16 defect-A fix; companion to the
    # capacity check above - capacity sizes the pool, this bounds how
    # long a provably-unresolvable candidate may keep a slot in it).
    # ml/history.py poll() censors a candidate (ML-085, no label row)
    # only when engine-clock age passes label_max_bars + this margin AND
    # the cached bars provably cannot produce the label, so the margin is
    # a LIVENESS bound, not a signal threshold - it never decides a
    # label, only how long dead weight squats. Validation only when
    # declared; the undeclared-key default (24 bars) lives in
    # ml/history.py and needs no mirror here because no capacity math
    # consumes it.
    _cem_raw = _f(config, "ml.candidate_evict_margin_bars", None)
    if _cem_raw is not None:
        if isinstance(_cem_raw, bool) or \
                not isinstance(_cem_raw, (int, float)) or \
                int(_cem_raw) != _cem_raw:
            fatal(f"ml.candidate_evict_margin_bars ({_cem_raw!r}) must be "
                  f"an integer - it is a bar count of eviction grace past "
                  f"the label window end")
        elif not (0 <= int(_cem_raw) <= 8640):
            fatal(f"ml.candidate_evict_margin_bars ({int(_cem_raw)}) must "
                  f"be in [0, 8640]: 0 censors an unresolvable candidate "
                  f"at its window end; 8640 bars is 30 days of grace at "
                  f"5m, beyond which the margin re-creates the "
                  f"zombie-slot squatting it exists to end (do NOT widen "
                  f"this to keep dead candidates - fix the feed instead)")

    # OF-5 DSR trials count (Debate-1 item A config-lift): the Harvey-Liu
    # deflation is only as honest as this number. Raising it deflates
    # harder (conservative); dropping below the shipped 7 weakens the
    # hard OF-5 gate without a recorded rationale.
    dnt = float(_f(config, "ml.overfit.dsr_n_trials", 7))
    if not (1.0 <= dnt <= 10000.0) or dnt != int(dnt):
        fatal(f"ml.overfit.dsr_n_trials ({dnt}) must be an integer in "
              f"[1, 10000] - the count of trials the observed max Sharpe "
              f"was selected over")
    elif dnt < 7:
        warn(f"ml.overfit.dsr_n_trials ({int(dnt)}) is below the shipped "
             f"baseline 7 - weaker deflation on the hard OF-5 gate; only "
             f"lower this with a recorded rationale in docs/quant/")

    # give-back vol-scaled arm: 0 = static arm_gain_pct; else the arm is
    # mult * sigma_bar. Below 0.5 sigma the ratchet arms inside ordinary
    # bar noise (churn); above 6 sigma it can never arm on a real move.
    gbm = float(_f(config, "profit_taking.give_back.arm_vol_mult", 0.0))
    if bool(_f(config, "profit_taking.give_back.enabled", False)) and \
            gbm != 0.0 and not (0.5 <= gbm <= 6.0):
        fatal(f"profit_taking.give_back.arm_vol_mult ({gbm}) must be 0 "
              f"(static arm) or in [0.5, 6] sigma_bar multiples")

    max_pos = float(_f(config,
                       "capital_management.max_position_size_pct_of_capital", 10))
    if not (0 < max_pos <= 100):
        fatal("max_position_size_pct_of_capital out of (0, 100]")

    # capital_management.max_position_size_pct_of_capital is NOT what
    # actually caps a live entry - risk/position_sizer.py's PositionSizer
    # reads its own position_sizer.max_position_size_pct_of_capital copy
    # (risk/capital_manager.py's calculate_position_size, which reads the
    # capital_management copy, is dead code - never called from main.py).
    # Same failure mode as the pretrade/order_manager fee split above: two
    # independent copies of one number silently drift apart. Enforce parity
    # rather than pick a canonical source, so either being edited catches it.
    # Resolved with a None SENTINEL, never with the other copy as its
    # default: `_f(..., max_pos)` made an ABSENT sizer key compare equal to
    # the capital_management copy forever, so this parity FATAL could not
    # detect the one failure it exists for. That is not hypothetical - the
    # operator's deliberate 10 -> 25 raise (6e57ebd7) was deleted from the
    # position_sizer block by an unrelated commit (ae4b5314), the live entry
    # cap silently reverted to PositionSizer's 10.0 code default, and this
    # check reported clean the whole time. A default can never detect a
    # missing key.
    sizer_raw = _f(config, "position_sizer.max_position_size_pct_of_capital")
    cap_raw = _f(config, "capital_management.max_position_size_pct_of_capital")
    if sizer_raw is None:
        # Only FATAL when the operator HAS expressed a cap in
        # capital_management: with both keys absent the two code defaults
        # (PositionSizer 10.0 / CapitalManager 10) genuinely agree and
        # nothing has silently drifted - that is a bare/partial config, not
        # a half-reverted decision.
        if cap_raw is not None:
            fatal(f"position_sizer.max_position_size_pct_of_capital is "
                  f"MISSING while capital_management sets it ({max_pos}) - "
                  f"the position_sizer copy is the ONLY one that caps a live "
                  f"entry (risk/position_sizer.py), so the bot would silently "
                  f"run at PositionSizer's 10.0 code default and every "
                  f"report of the capital_management number would be a lie. "
                  f"Restore the key to the position_sizer block.")
    else:
        sizer_max_pos = float(sizer_raw)
        if not (0 < sizer_max_pos <= 100):
            fatal(f"position_sizer.max_position_size_pct_of_capital "
                  f"({sizer_max_pos}) out of (0, 100] - this is the cap that "
                  f"actually bounds a live entry")
        if abs(max_pos - sizer_max_pos) > 1e-9:
            fatal(f"max_position_size_pct_of_capital mismatch: "
                  f"capital_management ({max_pos}) != position_sizer "
                  f"({sizer_max_pos}) - only the position_sizer copy actually "
                  f"caps live entries; the capital_management copy is checked "
                  f"here but not enforced at runtime")

    # THIRD copy: main.py builds a SECOND PositionSizer for the long book
    # from long_book.position_sizer, and the parity check above has never
    # covered it - the block shipped absent, so that sizer has ALWAYS capped
    # at PositionSizer's 10.0 code default regardless of what either key
    # above says. Bounds it when present. Absent is only an ADVISORY, not a
    # FATAL: unlike the 5m sizer copy there is no second key to drift from,
    # the effective value is the documented code default, and the long book
    # is EvidenceLadder-bounded rather than Kelly-bounded - so an absent key
    # is under-specified config, not a half-reverted operator decision.
    lb_cap_raw = _f(config,
                    "long_book.position_sizer.max_position_size_pct_of_capital")
    if lb_cap_raw is None:
        if _f(config, "long_book"):
            advisory("long_book.position_sizer.max_position_size_pct_of_"
                     "capital is unset - main.py's long-book PositionSizer "
                     "silently runs at the 10.0 code default and no parity "
                     "check covers it. State it explicitly (10 preserves "
                     "today's behaviour exactly).")
    else:
        lb_cap = float(lb_cap_raw)
        if not (0 < lb_cap <= 100):
            fatal(f"long_book.position_sizer.max_position_size_pct_of_capital "
                  f"({lb_cap}) out of (0, 100]")

    # untradeable-by-construction check: if the largest permitted position
    # is below every minimum ticket, the bot will veto 100% of entries and
    # burn API quota doing nothing. Not dangerous - just pointless.
    min_ticket = max(float(_f(config, "position_sizer.min_ticket_usd", 15)),
                     float(_f(config, "pretrade.min_order_usd", 15)))
    if start_cap > 0:
        max_ticket = start_cap * max_pos / 100.0
        if max_ticket < min_ticket:
            warn(f"max position {max_pos}% of ${start_cap:,.0f} = "
                 f"${max_ticket:,.0f} is below the ${min_ticket:,.0f} "
                 f"minimum ticket - NO entry can ever be approved. Raise "
                 f"max_position_size_pct_of_capital or add capital.")

    # --- exploration floor multiplier (lifted 2026-08-27, config audit) ---
    # Probe tickets floor at max(min_ticket_usd, pretrade.min_order_usd *
    # explore_floor_mult) (risk/position_sizer.py, SZ-044). Below 1.0 the
    # floor undercuts the pre-trade minimum: the sizer floors at the MARK
    # while the gate recomputes notional at the QUOTE, so the floored
    # ticket lands under min_order and dies PT-031 - the exact death the
    # knob exists to prevent. Above 5.0 it stops being a floor margin and
    # becomes a probe SIZING lever in disguise.
    efm = float(_f(config, "position_sizer.explore_floor_mult", 1.2))
    if not (1.0 <= efm <= 5.0):
        fatal(f"position_sizer.explore_floor_mult={efm} outside [1.0, 5.0] "
              f"- below 1.0 the exploration floor undercuts "
              f"pretrade.min_order_usd after the maker-quote gap (the "
              f"PT-031 death it exists to prevent); above 5.0 it is probe "
              f"sizing, not a floor margin")

    # --- profit tiers -----------------------------------------------------
    # ProfitTierEngine closes close_pct of the CURRENT (remaining) size at each
    # tier, not the original, so closes compound geometrically:
    #     cumulative retired = 1 - prod(1 - close_i/100)
    # That asymptotes to 100% and can never exceed it. The old check summed the
    # four closes and warned above 100% "of the ORIGINAL" - both the label and
    # the impossible >100% state were wrong. The condition actually worth
    # flagging is the opposite: if the tiers together retire only a little, most
    # of the position becomes a permanent RUNNER left on the trailing/give-back
    # floor after the last tier.
    prev = 0.0
    remaining = 1.0
    for i in range(1, 5):
        t = _f(config, f"profit_taking.tier_{i}", {}) or {}
        trig = float(t.get("trigger_pct_gain", 0))
        close = float(t.get("close_pct_of_position", 0))
        if trig <= prev:
            fatal(f"tier_{i} trigger {trig}% not strictly above tier_{i-1} "
                  f"({prev}%)")
        if not (0 < close <= 100):
            fatal(f"tier_{i} close_pct_of_position out of (0, 100]")
        prev = trig
        remaining *= (1.0 - close / 100.0)
    if remaining > 0.5:
        warn(f"profit tiers retire only {(1.0 - remaining) * 100:.0f}% of the "
             f"position across all four (closes are % of CURRENT size); "
             f"{remaining * 100:.0f}% rides the trailing/give-back floor after "
             f"the last tier - confirm that floor is tight enough to protect a "
             f"runner that large.")

    # tier-1 cost-multiple floor (P1, 2026-07-23 P&L diagnosis): floors
    # tier-1's effective trigger at mult x the entry's own estimated
    # round-trip cost (Position.est_cost_bps). Derivation: the 2026-07-23
    # live-close audit (209 closes) measured avg win $0.05 vs avg loss $0.19
    # and a ~20.5bps cost overrun - tier-1 was banking LESS than one
    # round-trip cost unit. Shipped 3.0x makes the first take bank >= 2 net
    # cost-units after paying one. Below 1.0x the floor could not even
    # guarantee covering a single cost unit (defeats its own purpose);
    # above 10.0x tier-1 would almost never fire in an ordinary vol regime.
    mtcm = float(_f(config, "profit_taking.min_trigger_cost_mult", 3.0))
    if not (1.0 <= mtcm <= 10.0):
        fatal(f"profit_taking.min_trigger_cost_mult ({mtcm}) must be in "
              f"[1.0, 10.0] - it floors tier-1's effective trigger at mult x "
              f"the entry's estimated round-trip cost (est_cost_bps); below "
              f"1x the floor can't even guarantee covering one cost unit, "
              f"above 10x tier-1 would almost never fire")

    # time-stop (P2, 2026-07-23 P&L diagnosis, PT-060): scratches a
    # position that has NOT reached min_mfe_frac_of_tier1 of tier-1's
    # effective trigger within max_bars_no_progress bars. Derivation: the
    # no-progress cohort measured MFE 0.16% vs MAE -1.44% and
    # recovered_after_stop 0/17 - no early favorable excursion
    # overwhelmingly resolves to a full-stop loss. Bounds only bind while
    # the knob is armed (disabled = fully inert, same as give_back/
    # signal_decay above).
    if bool(_f(config, "profit_taking.time_stop.enabled", False)):
        ts_bars = float(_f(config,
                          "profit_taking.time_stop.max_bars_no_progress", 36))
        if not (6 <= ts_bars <= 500):
            fatal(f"profit_taking.time_stop.max_bars_no_progress "
                  f"({ts_bars}) must be in [6, 500] - below 6 bars scratches "
                  f"a position before even one confirmable bar of adverse "
                  f"noise settles; above 500 bars (~41h at 5m bars) "
                  f"'no progress' stops meaning anything distinct from "
                  f"'very patient'")
        ts_frac = float(_f(config,
                          "profit_taking.time_stop.min_mfe_frac_of_tier1",
                          0.5))
        if not (0.0 < ts_frac <= 1.0):
            fatal(f"profit_taking.time_stop.min_mfe_frac_of_tier1 "
                  f"({ts_frac}) must be in (0, 1] - <= 0 inverts the whole "
                  f"test (any MFE, even negative, would 'clear' it); above "
                  f"1 demands MORE favorable excursion than tier 1's own "
                  f"trigger, which tier 1 would already have closed on")
        # coherence: the time-stop scratches a no-progress position before
        # the trail's own time-tightening decay window (TIME TIGHTENING,
        # risk/profit_tiers.py: tighten_after_bars) ever gets a chance to
        # engage for it. Informational only - the shipped defaults (36 vs
        # 96) sit inside this band deliberately.
        tighten_after = float(_f(config, "profit_taking.tighten_after_bars",
                                 96))
        if ts_bars < tighten_after:
            warn(f"profit_taking.time_stop.max_bars_no_progress "
                 f"({ts_bars:.0f}) sits below profit_taking."
                 f"tighten_after_bars ({tighten_after:.0f}) - the "
                 f"time-stop shadows tighten_after_bars for exactly the "
                 f"no-progress trade class it targets (scratched before "
                 f"the trail's own time-tightening window ever engages); "
                 f"confirm this overlap is intended")

    # --- stops / slippage / cadence --------------------------------------
    if float(_f(config, "risk.stop_loss_pct", 2.0)) <= 0:
        fatal("risk.stop_loss_pct must be positive")
    if float(_f(config, "risk.max_slippage_pct", 0.5)) <= 0:
        fatal("risk.max_slippage_pct must be positive")
    poll = float(_f(config, "system.polling_interval_sec", 5))
    if poll <= 0:
        fatal("system.polling_interval_sec must be positive")
    elif poll > 60:
        warn(f"polling_interval_sec={poll:.0f}s: stops are only enforced "
             f"once per cycle - this is a long time to be blind")

    # C1b: the loop-progress bound the lock heartbeat withholds on. Guarded
    # because BOTH directions are silent failures with real consequences: too
    # LOW and a merely-slow cycle stops the heartbeat, re-creating the false
    # takeover that produced two audit-chain forks; too HIGH and a hung runner
    # squats the lock long enough that no healthy replacement can ever start.
    # Only checked when declared - an absent key keeps runner.py's own 300.0
    # default, so every existing config and test fixture is unaffected.
    _lpms_raw = _f(config, "system.lock_progress_max_stall_sec", None)
    if _lpms_raw is not None:
        _lpms = float(_lpms_raw)
        if not (60.0 <= _lpms <= 3600.0):
            fatal(f"system.lock_progress_max_stall_sec ({_lpms:g}) must be in "
                  f"[60, 3600] - below 60s a normal slow cycle reads as a hang "
                  f"(88.1s measured live), above 3600s a hung runner holds "
                  f"outputs/runner.lock for an hour")
        # Mirror runner.main()'s OWN derivation exactly - there is no
        # lock_stale_after_sec key, and inventing one here would guard a
        # number the runner never uses:
        #     SingleInstanceLock(stale_after_sec=max(poll * 5, 30.0))
        _stale = max(poll * 5.0, 30.0)
        if _lpms <= 2.0 * _stale:
            fatal(f"system.lock_progress_max_stall_sec ({_lpms:g}) must exceed "
                  f"2x the lock stale window ({_stale:g}s) - at or below it the "
                  f"heartbeat stops before a peer could even consider the lock "
                  f"stale, so the bound only ever costs availability")

    # system.deploy_branch: the channel scripts/auto_update.py follows. Only
    # checked when declared (absent key keeps the updater's own
    # follow-the-checkout behavior). FATAL on a malformed name: the updater
    # would silently ignore it (its fail-safe) and the box would quietly
    # follow the checkout while the operator believes it follows the pin —
    # a divergence nobody sees until a deploy never arrives. Mirror of the
    # updater's own _BRANCH_RE (leading '-' would parse as a git option).
    _db_raw = _f(config, "system.deploy_branch", None)
    if _db_raw is not None and (
            not isinstance(_db_raw, str)
            or not re.match(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$", _db_raw)):
        fatal(f"system.deploy_branch ({_db_raw!r}) must be a plain git "
              f"branch name ([A-Za-z0-9._/-], no leading '-') - the "
              f"updater ignores malformed pins and silently falls back "
              f"to following the checkout")

    cfh = int(_f(config, "system.cycle_fail_halt", 10))
    if cfh < 1:
        fatal("system.cycle_fail_halt must be >= 1 - the runner halts new "
              "risk after this many consecutive cycle failures")
    elif cfh < 3:
        warn(f"system.cycle_fail_halt={cfh}: halting new risk after so few "
             f"consecutive failures will trip on a transient feed blip")

    # main.py does `self._cycle % self.slow_every` every fast cycle - 0
    # raises ZeroDivisionError on the very first cycle, every cycle after.
    slow_every = int(_f(config, "system.slow_cycle_every_n", 6))
    if slow_every < 1:
        fatal(f"system.slow_cycle_every_n={slow_every} must be >= 1 - 0 "
              f"raises ZeroDivisionError on `cycle % slow_cycle_every_n` "
              f"every cycle")

    # order_manager.order_timeout_sec must exceed the poll cadence: an order
    # is only checked for timeout when the runner polls, so a timeout at or
    # below the cadence expires the order before it can ever be evaluated
    # once (born already dead).
    om_timeout = float(_f(config, "order_manager.order_timeout_sec", 25.0))
    if om_timeout <= poll:
        fatal(f"order_manager.order_timeout_sec ({om_timeout}) must exceed "
              f"system.polling_interval_sec ({poll}) - at/below the poll "
              f"cadence every order expires before the runner can check it "
              f"even once")
    om_reprices = int(_f(config, "order_manager.max_reprices", 1))
    if om_reprices < 0:
        fatal(f"order_manager.max_reprices={om_reprices} must be >= 0")
    om_fill_ratio = float(_f(config, "order_manager.min_fill_ratio", 0.10))
    if not (0.0 <= om_fill_ratio <= 1.0):
        fatal(f"order_manager.min_fill_ratio={om_fill_ratio} must be in "
              f"[0, 1] - it is graded against a filled/requested ratio")

    lev = float(_f(config, "leverage.region_max_leverage", 10))
    if lev < 1:
        fatal("leverage.region_max_leverage below 1")
    lev_use_margin = bool(_f(config, "leverage.use_margin", False))
    if lev_use_margin and dry_run is False:
        warn("margin ENABLED in live config - confirm this is intentional")
    # target_vol_annual_pct feeds `lev = target_vol/vol` BEFORE the
    # use_margin branch even runs (risk/leverage.py allowed_leverage) - at 0
    # every allowed-leverage computation floors to 0 and every entry is
    # silently blocked regardless of margin being on or off. min_leverage
    # is a floor applied to that same pre-margin ladder, so it must not be
    # negative either. Unconditional (not gated on use_margin), matching
    # the code path both actually run on.
    lev_target_vol = float(_f(config, "leverage.target_vol_annual_pct", 35.0))
    if lev_target_vol <= 0:
        fatal(f"leverage.target_vol_annual_pct={lev_target_vol} must be "
              f"positive - lev = target_vol/realized_vol runs regardless of "
              f"use_margin; 0 zeroes allowed leverage and silently blocks "
              f"every entry")
    lev_min = float(_f(config, "leverage.min_leverage", 0.25))
    if lev_min < 0:
        fatal(f"leverage.min_leverage={lev_min} must be >= 0")
    # margin_scale_below_pct/margin_block_below_pct are read ONLY inside the
    # `elif self.use_margin:` branch (risk/leverage.py) - gate this check on
    # use_margin so a purely-spot config with stale/unused margin fields
    # isn't flagged for a band that code path never reads.
    if lev_use_margin:
        m_scale = float(_f(config, "leverage.margin_scale_below_pct", 200))
        m_block = float(_f(config, "leverage.margin_block_below_pct", 150))
        if m_block >= m_scale:
            fatal(f"leverage.margin_block_below_pct ({m_block}) must be "
                  f"below margin_scale_below_pct ({m_scale}) - an inverted/"
                  f"equal band divides by zero in the scaling fraction (at "
                  f"equal) or creates a leverage cliff at the margin "
                  f"boundary (inverted)")

    # --- live credentials -------------------------------------------------
    # Resolved through the SAME precedence data/kraken_feed.py actually uses
    # (env var NAMED in config -> conventional KRAKEN_API_KEY/SECRET ->
    # literal config value). Reading the dict alone made this gate both
    # unnecessary AND insufficient for its own stated purpose: it FATAL'd a
    # correctly-configured env-only live start (the documented, secure path
    # that tests/test_credential_resolution.py pins), while a config literal
    # shadowed by a stale env var passed the gate and then failed every
    # private call. KrakenFeed._resolve_cred is a @staticmethod over the
    # exchange sub-dict; imported lazily here per this module's guard-purity
    # rule (zero in-repo imports at MODULE scope), with the same optional-
    # third-party fallback as the pair-meta check below - `requests` may be
    # absent in a bare env, and a missing HTTP lib must not blind the guard.
    kraken_cfg = _f(config, "exchanges.kraken", {}) or {}
    lit_key = str(kraken_cfg.get("api_key", "") or "")
    lit_secret = str(kraken_cfg.get("api_secret", "") or "")
    try:
        from data.kraken_feed import KrakenFeed
        res_key = KrakenFeed._resolve_cred(kraken_cfg, "api_key",
                                           "api_key_env", "KRAKEN_API_KEY")
        res_secret = KrakenFeed._resolve_cred(kraken_cfg, "api_secret",
                                              "api_secret_env",
                                              "KRAKEN_API_SECRET")
    except ImportError:      # no requests -> fall back to the literals only
        res_key, res_secret = lit_key, lit_secret
    if not dry_run and (not res_key or not res_secret):
        fatal("live mode requires Kraken api_key and api_secret to RESOLVE "
              "at startup - neither the env var named in exchanges.kraken."
              "api_key_env/api_secret_env, nor KRAKEN_API_KEY/"
              "KRAKEN_API_SECRET, nor a literal in exchanges.kraken supplied "
              "one; every private call would silently fail")
    # REVERSE direction, and the one that actually costs something if it is
    # ever wrong: config.json is git-tracked (`git ls-files` lists it, it is
    # not in .gitignore) and ships inside the deliverable zip, so a literal
    # here is a secret in version control - exactly what
    # docs/SECURITY_AUDIT.md forbids. Unconditional (not dry-run gated): a
    # key committed while paper-trading is just as leaked. enforce() still
    # only REFUSES TO START on live, so a dry-run operator gets a loud
    # CRITICAL log and a chance to rotate rather than a dead bot.
    leaked = [n for n, v in (("api_key", lit_key),
                             ("api_secret", lit_secret)) if v]
    if leaked:
        fatal(f"exchanges.kraken {leaked} hold literal value(s) - config.json "
              f"is version-controlled and ships in the deliverable, so a real "
              f"credential here is a committed secret. Clear the literal(s) "
              f"and supply the credential via KRAKEN_API_KEY/"
              f"KRAKEN_API_SECRET (or the env var names in "
              f"exchanges.kraken.api_key_env/api_secret_env); "
              f"data/kraken_feed.py resolves env FIRST. If a real key was "
              f"ever committed, rotate it on Kraken - removing it from the "
              f"file does not remove it from git history.")

    # --- new hardening sections (defaults are fine; nonsense is not) ------
    dm = float(_f(config, "order_manager.deadman_timeout_sec", 60))
    if dm and (dm < 15 or dm > 3600):
        fatal("order_manager.deadman_timeout_sec must be 0 (off) or in "
              "[15, 3600] - below the poll cadence it flaps, above an hour "
              "it protects nothing")
    # DRY-RUN sim fill realism (MP-7): probabilities in [0,1], fraction
    # window ordered, queue tolerance non-negative. A base prob of 0 would
    # make passive orders NEVER fill in the sim (no candidate labels at
    # all); flag it loud rather than silently starving the learner.
    sf_base = float(_f(config, "order_manager.sim_fill.passive_base_prob",
                       0.45))
    if not (0.0 < sf_base <= 1.0):
        fatal(f"order_manager.sim_fill.passive_base_prob={sf_base} must be "
              f"in (0, 1] - zero starves candidate labels, >1 is not a "
              f"probability")
    sf_lo = float(_f(config, "order_manager.sim_fill.fill_frac_min", 0.3))
    sf_hi = float(_f(config, "order_manager.sim_fill.fill_frac_max", 1.0))
    if not (0.0 < sf_lo <= sf_hi <= 1.0):
        fatal(f"order_manager.sim_fill fill_frac window [{sf_lo}, {sf_hi}] "
              f"must satisfy 0 < min <= max <= 1")
    sf_tol = float(_f(config, "order_manager.sim_fill.queue_tol_frac", 1.0))
    if sf_tol < 0.0:
        fatal(f"order_manager.sim_fill.queue_tol_frac={sf_tol} negative - "
              f"it is a multiple of order size, the front-of-queue yardstick")
    sf_drain = float(_f(config, "order_manager.sim_fill.queue_drain_frac",
                        0.20))
    if not (0.0 <= sf_drain <= 1.0):
        fatal(f"order_manager.sim_fill.queue_drain_frac={sf_drain} must be "
              f"in [0, 1] - it is the per-poll geometric turnover fraction; "
              f"0 starves fills on static-snapshot replays")
    sf_sref = float(_f(config, "order_manager.sim_fill.sigma_ref_bps", 30.0))
    if sf_sref <= 0.0:
        fatal(f"order_manager.sim_fill.sigma_ref_bps={sf_sref} must be "
              f"positive - it normalizes the vol-scaled queue turnover")
    # STARVATION caveat (review finding): with queue_aware on, the geometric
    # turnover clears at most ~1/(1-drain*sigma/sigma_ref) of the queue per
    # poll, and only ~order_timeout_sec/poll_cadence polls exist before an
    # unfilled order expires. At the default drain/sigma_ref a wall more than
    # a few multiples of the order size never clears in-window, so a book bot
    # resting behind real depth generates ZERO passive labels. It is now ON by
    # default (execution-truth harness): calibrate drain/sigma_ref against the
    # live poll cadence via scripts/calibrate_fills.py and confirm fills are not
    # starved before trusting the labels.
    if bool(_f(config, "order_manager.sim_fill.queue_aware", False)):
        warn("order_manager.sim_fill.queue_aware=true: verify passive fills "
             "are not starved at your live sigma/poll-cadence before trusting "
             "the labels — the queue turnover must clear a typical wall inside "
             "order_timeout_sec or every behind-the-wall entry expires unfilled")
    esc = _f(config, "risk.exit_escalation", {}) or {}
    mult = float(esc.get("widen_mult", 2.0))
    if mult < 1.0:
        fatal("risk.exit_escalation.widen_mult must be >= 1")
    # the escalation ladder computes slip_pct = min(base * widen_mult**n,
    # cap); if cap sits BELOW the base max_slippage_pct, even attempt 0
    # clamps to the cap - an exit that should be marketable at the ordinary
    # slippage tolerance instead pins at a TIGHTER (unfillable) price than
    # a normal order would ever use.
    esc_cap = float(esc.get("max_slippage_cap_pct", 3.0))
    base_slip = float(_f(config, "risk.max_slippage_pct", 0.5))
    if esc_cap < base_slip:
        fatal(f"risk.exit_escalation.max_slippage_cap_pct ({esc_cap}) must "
              f"be >= risk.max_slippage_pct ({base_slip}) - a cap below the "
              f"base tolerance pins every escalated exit at a TIGHTER "
              f"(less fillable) price than an ordinary order ever uses")
    esc_market_after = int(esc.get("market_after_attempts", 3))
    if not (0 <= esc_market_after <= 20):
        fatal(f"risk.exit_escalation.market_after_attempts="
              f"{esc_market_after} must be in [0, 20] - negative is not an "
              f"attempt count, and past ~20 the ladder never reaches its "
              f"market-order failsafe rung within a position's lifetime")
    mark_stale = float(_f(config, "risk.mark_stale_sec", 20.0))
    if mark_stale <= 0:
        fatal(f"risk.mark_stale_sec={mark_stale} must be positive - at 0, "
              f"`(now - mark_ts) <= 0` is false for every mark except the "
              f"exact instant it was stamped, so every mark reads STALE "
              f"permanently (profit tiers, inventory derisk and the "
              f"equity-peak/hard-stop all lose their trusted mark)")

    # --- anti-scalp manip gate (new-entry downsize/veto band) --------------
    mg = _f(config, "risk.manip_gate", {}) or {}
    if bool(mg.get("enabled", True)):
        d_at = float(mg.get("downsize_at", 0.6))
        v_at = float(mg.get("veto_at", 0.9))
        m_sc = float(mg.get("min_scale", 0.25))
        if not (0.0 <= d_at <= 1.0) or not (0.0 <= v_at <= 1.0):
            fatal("risk.manip_gate.downsize_at/veto_at must be in [0, 1] - "
                  "manip_suspect_score is a [0, 1] suspicion level")
        if v_at <= d_at:
            fatal(f"risk.manip_gate.veto_at ({v_at}) must be strictly above "
                  f"downsize_at ({d_at}) - the downsize band collapses "
                  f"otherwise and entries jump straight from full size to a "
                  f"hard veto")
        if not (0.0 <= m_sc <= 1.0):
            fatal("risk.manip_gate.min_scale must be in [0, 1] - it is the "
                  "floor of a multiplicative size scale (1.0 = no downsize)")

    # --- input-drift window vs PSI stability ------------------------------
    # decile-PSI on too small a live window fabricates drift from pure
    # sampling noise (null-tested: a 40-row window reads ~19% mean / 28% p95
    # "drift" on an in-distribution sample, nearly tripping the retrain vote).
    # WARN (never fatal - the bot trades correctly, it just retrains on noise).
    dmr = int(_f(config, "ml.monitor.drift_min_rows", 100))
    if dmr < 80:
        warn(f"ml.monitor.drift_min_rows={dmr} is below ~80: a 10-bin PSI at "
             f"that window fabricates false drift from in-distribution noise "
             f"(null p95 ~28% at 40 rows vs the {float(_f(config, 'ml.monitor.drift_frac_features', 0.30)):.0%} "
             f"retrain trigger). Raise it so a fired ML-031 means a real shift.")

    # ML-075 shadow-recovery is a bool feature flag; a non-bool would be
    # coerced by bool() and silently mean something the operator didn't intend.
    _sr = _f(config, "ml.monitor.shadow_recovery", True)
    if not isinstance(_sr, bool):
        advisory(f"ml.monitor.shadow_recovery={_sr!r} is not a boolean; it is "
                 f"coerced by bool() - set true/false explicitly.")

    # W2-17: de-escalation deadband. Below 1 the deadband is disabled outright
    # (every healthy window de-escalates instantly - reopens the L0<->1 flap
    # the knob exists to fix); above 10 a genuinely recovered model stays
    # throttled far longer than the evidence warrants.
    dhw = int(_f(config, "ml.monitor.deescalate_healthy_windows", 3))
    if not (1 <= dhw <= 10):
        fatal(f"ml.monitor.deescalate_healthy_windows ({dhw}) must be in "
              f"[1, 10] - <1 disables the de-escalation deadband (reopens "
              f"the L0<->L1 flap on window-churn noise), >10 leaves a "
              f"recovered model throttled long past the evidence")

    # --- model governor judge window / shrinkage-kelly-stop ordering ------
    # _windows() slices `recs = [...][-window_trades:]` then requires
    # `len(recs) >= min_trades_to_judge` - recs can never exceed
    # window_trades, so min_trades_to_judge > window_trades makes the
    # governor NEVER judge (never escalates OR de-escalates on live
    # evidence). shrinkage ramps base (healthy) -> max (killed) as level
    # rises (_evaluate); an inverted pair reverses that ramp. kelly_mult
    # starts at 1.0 and floors at kelly_mult_min as level rises; stop_widen
    # starts at 1.0 and ceilings at stop_widen_max.
    mon_window = int(_f(config, "ml.monitor.window_trades", 30))
    mon_min_judge = int(_f(config, "ml.monitor.min_trades_to_judge", 15))
    if mon_window < 1:
        fatal(f"ml.monitor.window_trades={mon_window} must be >= 1")
    if mon_min_judge > mon_window:
        fatal(f"ml.monitor.min_trades_to_judge ({mon_min_judge}) must be <= "
              f"window_trades ({mon_window}) - the judged window is capped "
              f"at window_trades, so a higher min can never be reached and "
              f"the governor never judges")
    # LOWER bound (this key had only the upper bound above). The floor is
    # the calibration binning count, not a taste: ml/calibration.py's
    # calibration_gap() returns 0.0 for any window shorter than n_bins, and
    # 0.0 is the PERFECTLY-CALIBRATED value, not a "not enough data"
    # sentinel. ml/monitor.py _judge consumes it raw in two of its three
    # verdict clauses (`gap > calibration_gap_max` for degraded, and the
    # `hit_deficit and gap > ...` conjunct for failing). So a floor below
    # n_bins lets the governor OPEN its judged window on 1..n_bins-1 scored
    # closes and, on exactly those windows, the calibration test cannot
    # convict - it reads clean rather than reading unavailable. Measured on
    # the real consumer: min_trades_to_judge=4 with four promised-0.99
    # all-loss closes publishes calibration_gap=0.0; the same evidence at 5
    # publishes 0.99. This is a measurement-standard floor, NOT a tunable -
    # the fix for a governor that judges too slowly is more evidence, never
    # a lower bar.
    if mon_min_judge < _CALIBRATION_MIN_BINS:
        fatal(f"ml.monitor.min_trades_to_judge ({mon_min_judge}) must be >= "
              f"{_CALIBRATION_MIN_BINS} - ml/calibration.py calibration_gap "
              f"bins into n_bins={_CALIBRATION_MIN_BINS} and returns 0.0, the "
              f"PERFECTLY-CALIBRATED value, on any shorter window. The "
              f"governor would judge {mon_min_judge}-close windows with its "
              f"calibration clause silently reading 'perfect' instead of "
              f"'unknown', so miscalibration could never convict there")
    mon_shrink_base = float(_f(config, "ml.monitor.shrinkage_base", 0.35))
    mon_shrink_max = float(_f(config, "ml.monitor.shrinkage_max", 0.70))
    if not (0.0 <= mon_shrink_base <= mon_shrink_max <= 1.0):
        fatal(f"ml.monitor shrinkage bounds incoherent: need 0 <= "
              f"shrinkage_base ({mon_shrink_base}) <= shrinkage_max "
              f"({mon_shrink_max}) <= 1 - shrinkage ramps base (healthy) up "
              f"to max (killed) as the governor escalates; inverted reverses "
              f"that ramp")
    mon_kelly_min = float(_f(config, "ml.monitor.kelly_mult_min", 0.40))
    if not (0.0 < mon_kelly_min <= 1.0):
        fatal(f"ml.monitor.kelly_mult_min={mon_kelly_min} must be in "
              f"(0, 1] - kelly_mult starts at 1.0 (healthy) and floors here "
              f"as the governor escalates; 0 would zero every sized entry "
              f"at the worst level")
    mon_stop_widen_max = float(_f(config, "ml.monitor.stop_widen_max", 1.5))
    if mon_stop_widen_max < 1.0:
        fatal(f"ml.monitor.stop_widen_max={mon_stop_widen_max} must be >= 1 "
              f"- stop_widen starts at 1.0 and ceilings here; below 1 it "
              f"would TIGHTEN the stop on a degrading model instead of "
              f"widening it")

    # --- post-hoc interpretability report (ml/interpret.py) ---------------
    # analysis knobs, not decision-path tunables — but nonsense values make
    # the report LIE (a background too thin makes interventional SHAP noise;
    # a cluster threshold at the extremes silently degenerates clustered
    # permutation into the exact Hooker/de-Prado failure modes it exists
    # to fix). Fail loud rather than emit a confident wrong report.
    it_bg = int(_f(config, "ml.interpret.background_rows", 64))
    if it_bg < 16:
        fatal(f"ml.interpret.background_rows={it_bg} below 16: the "
              f"interventional value function is an average over the "
              f"background - this few rows makes exact SHAP precisely "
              f"wrong about a noisy expectation")
    it_ct = float(_f(config, "ml.interpret.corr_cluster_thr", 0.7))
    if not (0.3 <= it_ct <= 0.99):
        fatal(f"ml.interpret.corr_cluster_thr={it_ct} outside [0.3, 0.99]: "
              f"near 1.0 nothing clusters (substitution effects return), "
              f"below 0.3 everything clusters (importance of one blob)")
    it_ef = float(_f(config, "ml.interpret.eval_frac", 0.3))
    if not (0.1 <= it_ef <= 0.5):
        fatal(f"ml.interpret.eval_frac={it_ef} outside [0.1, 0.5]: the "
              f"held-out tail must exist AND leave a training majority")
    if int(_f(config, "ml.interpret.n_repeats", 5)) < 3:
        fatal("ml.interpret.n_repeats below 3: one permutation draw is an "
              "anecdote, not an importance estimate")
    it_dc = float(_f(config, "ml.interpret.drift_cos_warn", 0.8))
    if not (0.0 < it_dc <= 1.0):
        fatal(f"ml.interpret.drift_cos_warn={it_dc} must be in (0, 1] - "
              f"it is a cosine similarity floor")

    # --- risk protocol stack (rev 4 sizing overlay) ------------------------
    sf = float(_f(config, "risk_protocols.stack_floor_mult", 0.10))
    if not (0.0 < sf <= 1.0):
        fatal("risk_protocols.stack_floor_mult must be in (0, 1] - it is "
              "the last defense against a multiplicative collapse to zero")
    fmax = float(_f(config, "webdata.fear_greed_fear_max", 15))
    emin = float(_f(config, "webdata.fear_greed_euphoria_min", 85))
    if not (0 <= fmax < emin <= 100):
        fatal("webdata fear/euphoria thresholds must satisfy "
              f"0 <= fear_max({fmax}) < euphoria_min({emin}) <= 100 - "
              "inverted thresholds make sentiment context fire backwards")

    # --- vol_regime / sentiment ordering (shading-only paths) --------------
    # Mirrors the webdata fear/euphoria check above, but WARN not FATAL: a
    # miscalibrated percentile/threshold band here mis-classifies a regime
    # or a mood, it does not open the bot to a hard failure mode (the trade
    # path still executes correctly) - a FATAL would be disproportionate to
    # a shading-only misconfiguration, so it is caught loud without
    # refusing to start.
    vr_low = float(_f(config, "vol_regime.low_pct", 30.0))
    vr_elev = float(_f(config, "vol_regime.elevated_pct", 70.0))
    vr_ext = float(_f(config, "vol_regime.extreme_pct", 90.0))
    if not (0.0 <= vr_low < vr_elev < vr_ext <= 100.0):
        warn(f"vol_regime percentile thresholds incoherent: need 0 <= "
             f"low_pct({vr_low}) < elevated_pct({vr_elev}) < "
             f"extreme_pct({vr_ext}) <= 100 - inverted/equal bands "
             f"misclassify the vol regime shading")
    se_calm = float(_f(config, "sentiment.filter.stress_calm_threshold", 0.3))
    se_confirm = float(_f(config,
                          "sentiment.filter.stress_confirm_threshold", 0.6))
    if se_calm > se_confirm:
        warn(f"sentiment.filter.stress_calm_threshold ({se_calm}) must be "
             f"<= stress_confirm_threshold ({se_confirm}) - inverted "
             f"hysteresis makes the stress filter confirm before it can "
             f"even calm")
    se_fear = float(_f(config, "sentiment.fear_threshold", -0.35))
    se_euphoria = float(_f(config, "sentiment.euphoria_threshold", 0.45))
    if not (se_fear < 0.0 < se_euphoria):
        warn(f"sentiment fear_threshold ({se_fear}) / euphoria_threshold "
             f"({se_euphoria}) must satisfy fear_threshold < 0 < "
             f"euphoria_threshold - a wrong-signed threshold fires the "
             f"fear/euphoria spike flags backwards")

    a = float(_f(config, "risk_protocols.cvar.alpha", 0.975))
    if not (0.5 < a < 1.0):
        fatal("risk_protocols.cvar.alpha must be in (0.5, 1) - it is a "
              "tail-confidence level, not a percentage")
    esb = float(_f(config, "risk_protocols.cvar.es_budget_frac", 0.010))
    if not (0.0 < esb <= 0.05):
        fatal("risk_protocols.cvar.es_budget_frac must be in (0, 0.05] - "
              "budgeting >5% of equity to one entry's expected shortfall "
              "is not a cap, it is a wish")
    # bar_sec (2026-07-29 CVaR bar-clock fix, wave-1 adversarial-verify
    # coverage gap): the stack samples log returns on this clock so live
    # measures what quant-trials/smoke baseline at BAR_SECONDS=300.
    # Bounds keep it a bar clock: below 60s it degenerates back toward
    # the per-poll cadence the fix removed (the ~sqrt(60) ES deflation);
    # above 1800s min_obs=120 bars means DAYS of RP-040-neutral warmup.
    cbs = float(_f(config, "risk_protocols.cvar.bar_sec", 300.0))
    if not (60.0 <= cbs <= 1800.0):
        fatal(f"risk_protocols.cvar.bar_sec ({cbs}) must be in [60, 1800] "
              f"seconds - it is the CVaR sampling bar clock (300 = the "
              f"5m bar the harness baselines)")
    if cbs != 300.0:
        warn(f"risk_protocols.cvar.bar_sec ({cbs}) != 300: live CVaR "
             f"then measures a different clock than the quant-trials/"
             f"smoke baseline - re-baseline consciously before trusting "
             f"the gates")
    ts = float(_f(config, "risk_protocols.budget.taper_start", 0.5))
    fl = float(_f(config, "risk_protocols.budget.floor_mult", 0.15))
    if not (0.0 <= ts < 1.0) or not (0.0 <= fl < 1.0):
        fatal("risk_protocols.budget taper_start and floor_mult must be "
              "in [0, 1)")
    d_b = float(_f(config, "risk_protocols.budget.daily_loss_budget_pct",
                   2.5))
    w_b = float(_f(config, "risk_protocols.budget.weekly_loss_budget_pct",
                   6.0))
    if d_b > 0 and w_b > 0 and w_b < d_b:
        fatal("risk_protocols.budget weekly budget below the daily budget "
              "- the weekly gate would bind before a single bad day ends")
    hard = float(_f(config, "capital_management.hard_stop_drawdown_pct", 15))
    if d_b > 0 and hard > 0 and d_b >= hard:
        fatal("risk_protocols.budget.daily_loss_budget_pct must sit below "
              "capital_management.hard_stop_drawdown_pct - the taper must "
              "engage before the kill switch")
    ht = float(_f(config, "risk_protocols.heat.max_portfolio_heat_frac",
                  0.35))
    if not (0.0 < ht <= 1.0):
        fatal("risk_protocols.heat.max_portfolio_heat_frac must be in "
              "(0, 1]")
    corr = float(_f(config, "risk_protocols.heat.assumed_corr", 0.9))
    if not (0.0 <= corr <= 1.0):
        fatal("risk_protocols.heat.assumed_corr must be in [0, 1]")
    gshock = float(_f(config, "risk_protocols.gap.gap_shock_pct", 15.0))
    gloss = float(_f(config, "risk_protocols.gap.max_equity_loss_pct", 4.0))
    if gshock <= 0 or gloss <= 0:
        fatal("risk_protocols.gap shock and max loss must be positive")
    if bool(_f(config, "risk_protocols.vol_target.enabled", False)):
        vt_lo = float(_f(config, "risk_protocols.vol_target.min_mult", 0.25))
        vt_hi = float(_f(config, "risk_protocols.vol_target.max_mult", 1.15))
        if not (0.0 < vt_lo <= vt_hi):
            fatal("risk_protocols.vol_target min_mult/max_mult malformed")
        warn("risk_protocols.vol_target ENABLED - it overlaps the leverage "
             "governor's vol input; confirm the paper A/B before live")

    # --- give-back ratchet (rev 4 exit floor) -------------------------------
    if bool(_f(config, "profit_taking.give_back.enabled", False)):
        gbf = float(_f(config, "profit_taking.give_back.giveback_frac",
                       0.40))
        tgf = float(_f(config, "profit_taking.give_back.tight_frac", 0.25))
        arm = float(_f(config, "profit_taking.give_back.arm_gain_pct", 1.5))
        tgn = float(_f(config, "profit_taking.give_back.tighten_gain_pct",
                       0.0))
        if not (0.0 < gbf < 1.0) or not (0.0 < tgf < 1.0):
            fatal("profit_taking.give_back fractions must be in (0, 1)")
        elif tgf > gbf:
            fatal("profit_taking.give_back.tight_frac above giveback_frac "
                  "- the ratchet would LOOSEN as the trade improves")
        if arm <= 0:
            fatal("profit_taking.give_back.arm_gain_pct must be positive")
        if tgn > 0 and tgn <= arm:
            fatal("profit_taking.give_back.tighten_gain_pct must exceed "
                  "arm_gain_pct (or be 0 to disable the second rung)")
        # arm-vs-break-even coherence: flag a ratchet that arms inside the
        # fee/break-even buffer (its locked share would be fee noise). Lives
        # here — where `arm` is bound — not under the unrelated pos_cap>heat_cap
        # branch, where `arm` may be undefined (NameError) and the check would
        # only fire for the wrong reason.
        be_buf_bps = float(_f(config, "profit_taking.be_buffer_bps", 6.0)) \
            + 2.0 * float(_f(config, "profit_taking.est_fee_bps", 0.0))
        # THE EFFECTIVE ARM, NOT THE RAW KNOB (2026-09-06). This WARN fired on
        # every boot since cut #9 by comparing the STATIC arm_gain_pct to the
        # buffer - but risk/profit_tiers._give_back_candidate has carried an
        # ARM COST FLOOR since 2026-07-30: arm = max(arm, cost_pct/(1-frac)),
        # where cost_pct is the position's round-trip fee (maker+taker bps,
        # stamped at entry). At 20/35 and frac 0.4 the effective arm is
        # 0.55/0.6 = 0.917%, comfortably above the 0.76% buffer, so the WARN
        # was a stale instrument reading a knob the runtime no longer arms on
        # directly (GB-1 was refuted at HEAD on exactly this). Mirror the
        # runtime's own formula so the guard warns about the arm that ACTUALLY
        # fires; a raw knob below the floor is simply inert, not a defect.
        rt_fee_pct = (float(_f(config, "pretrade.maker_fee_bps", 0.0))
                      + float(_f(config, "pretrade.taker_fee_bps", 0.0))) / 100.0
        eff_arm = max(arm, rt_fee_pct / max(1.0 - gbf, 0.05))
        if eff_arm * 100.0 <= be_buf_bps:
            warn(f"give_back EFFECTIVE arm {eff_arm:.3f}% (raw arm_gain_pct="
                 f"{arm}%, cost floor {rt_fee_pct:.2f}%/(1-{gbf})) arms inside "
                 f"the break-even buffer ({be_buf_bps:.0f}bps) - the locked "
                 f"share of such small moves is fee noise")

    # --- conviction runner (rev 6 entry-conviction leash) -------------------
    if bool(_f(config, "profit_taking.conviction_runner.enabled", False)):
        ncf = float(_f(config, "profit_taking.conviction_runner.neutral_conf",
                       0.70))
        mcf = float(_f(config, "profit_taking.conviction_runner.min_conf",
                       0.55))
        tml = float(_f(config, "profit_taking.conviction_runner.min_trail_mult",
                       0.60))
        if not (0.0 < mcf < ncf <= 1.0):
            fatal("profit_taking.conviction_runner needs 0 < min_conf < "
                  "neutral_conf <= 1 (the leash tightens BELOW neutral)")
        if not (0.1 <= tml <= 1.0):
            fatal("profit_taking.conviction_runner.min_trail_mult must be in "
                  "[0.1, 1.0] - it can only tighten the runner, never loosen it")

    # --- v8 anti-predation batch -----------------------------------------
    # stop-magnet band: the nudge widens a trailing stop by up to band_bps
    # past a round level. Negative is nonsense; above 100bps (1%) the
    # "nudge" rivals the trail distance itself and the labeler divergence
    # (ml/labeling.py mirrors trails in percent space, magnets are price-
    # anchored) stops being ignorable. 0 = off.
    mgb = float(_f(config, "profit_taking.stop_magnet.band_bps", 0.0))
    if not (0.0 <= mgb <= 100.0):
        fatal(f"profit_taking.stop_magnet.band_bps={mgb} outside [0, 100] - "
              f"negative bands are nonsense and past 100bps the anti-hunt "
              f"nudge rivals the trail distance itself (and the label sim, "
              f"which cannot mirror price-anchored magnets, diverges "
              f"materially)")
    # imbalance distance decay: 0 = legacy equal-weight; above 200bps the
    # e-folding covers the whole tracked book and the decay is a no-op
    # wearing a knob (every level weighted ~1), which lies about intent.
    idb = float(_f(config, "liquidity_regime.imbalance_decay_bps", 15.0))
    if not (0.0 <= idb <= 200.0):
        fatal(f"liquidity_regime.imbalance_decay_bps={idb} outside [0, 200] "
              f"- negative inverts the weighting (rewarding painted far "
              f"depth); above 200bps every tracked level weighs ~1 and the "
              f"decay is a silent no-op (set 0 to disable explicitly)")
    # venue-candle refresh: below 30s the throttled refresh burns the 3
    # req/s Kraken REST budget the trading path depends on for nothing (5m
    # bars can't change that fast); above 600s (2 full bars) the cached
    # bars lag the external feed enough to skew volume_z at bar rollover.
    crs = float(_f(config, "exchanges.kraken.candle_refresh_sec", 150.0))
    if not (30.0 <= crs <= 600.0):
        fatal(f"exchanges.kraken.candle_refresh_sec={crs} outside [30, 600] "
              f"- below 30s the candle refresh eats the Kraken REST budget "
              f"for identical 5m bars; above 600s (2 bars) venue-grounded "
              f"features lag the market they price")

    # --- v9 shadow-feature batch (TANK quant-2 K/N) ----------------------
    # both knobs measure against the slow-cycle poll gap: the view build
    # (and fair_value update) samples once per polling_interval_sec x
    # slow_cycle_every_n, so any window/staleness bound at or below that
    # gap makes the derived feature structurally dead - a knob lying
    # about intent, the exact incoherence class this guard exists for.
    poll_gap = (float(_f(config, "system.polling_interval_sec", 5.0))
                * float(_f(config, "system.slow_cycle_every_n", 6)))
    ofi_tau = float(_f(config, "liquidity_regime.ofi.ewma_tau_sec", 60.0))
    if not (5.0 <= ofi_tau <= 600.0):
        fatal(f"liquidity_regime.ofi.ewma_tau_sec={ofi_tau} outside "
              f"[5, 600] - below 5s the EWMA is an unsmoothed per-poll "
              f"tick (cadence aliasing, the THALES A-3 failure); above "
              f"600s the 'event' signal is slower than the snapshot "
              f"imbalance it complements")
    ofi_dtau = float(_f(config, "liquidity_regime.ofi.depth_tau_sec", 300.0))
    if not (30.0 <= ofi_dtau <= 3600.0):
        fatal(f"liquidity_regime.ofi.depth_tau_sec={ofi_dtau} outside "
              f"[30, 3600] - the depth scale must move slower than the "
              f"flow it normalizes (below one poll it IS the flow) and "
              f"faster than a regime (above 1h it normalizes today's "
              f"events by yesterday's book)")
    ofi_stale = float(_f(config, "liquidity_regime.ofi.stale_sec", 120.0))
    if not (10.0 <= ofi_stale <= 900.0):
        fatal(f"liquidity_regime.ofi.stale_sec={ofi_stale} outside "
              f"[10, 900] - the same 'past this, treat as absent' bound "
              f"class as fair_value.kraken_stale_sec; above 15min a "
              f"dead feed's last flow reading survives a whole regime")
    elif ofi_stale <= poll_gap:
        fatal(f"liquidity_regime.ofi.stale_sec={ofi_stale} at/below the "
              f"slow-cycle poll gap ({poll_gap:.0f}s) - every poll reads "
              f"as stale, the EWMA resets each cycle and the feature is "
              f"structurally dead")
    bmw = float(_f(config, "fair_value.basis_mom_window_sec", 60.0))
    if not (5.0 <= bmw <= 600.0):
        fatal(f"fair_value.basis_mom_window_sec={bmw} outside [5, 600] - "
              f"the perp lead-lag this measures lives at sub-minute-to-"
              f"minutes horizons; a longer window is a slow trend "
              f"restating basis_dir, not momentum")
    elif bmw <= poll_gap:
        fatal(f"fair_value.basis_mom_window_sec={bmw} at/below the "
              f"slow-cycle poll gap ({poll_gap:.0f}s) - the window can "
              f"never hold two samples, so the momentum is structurally "
              f"zero forever")

    # --- urgency composition vs the execution ladder --------------------------
    ub = float(_f(config, "informed_flow.urgency.base", 0.30))
    uw = (float(_f(config, "informed_flow.urgency.w_burst", 0.40))
          + float(_f(config, "informed_flow.urgency.w_fresh", 0.20))
          + float(_f(config, "informed_flow.urgency.w_delta", 0.10)))
    u_max = ub + uw
    taker_at = float(_f(config, "execution_tactics.taker_at_urgency", 0.88))
    join_at = float(_f(config, "execution_tactics.join_at_urgency", 0.40))
    if not (0.0 <= ub <= 1.0) or uw < 0:
        fatal("informed_flow.urgency: base must be in [0,1] and weights "
              "non-negative")
    if u_max < taker_at:
        advisory(f"informed_flow.urgency: max reachable urgency "
                 f"{u_max:.2f} is below execution_tactics.taker_at_urgency "
                 f"{taker_at:.2f} - the taker rung can never fire")
    if ub >= join_at:
        advisory(f"informed_flow.urgency.base {ub:.2f} >= join_at_urgency "
                 f"{join_at:.2f} - EVERY confirmed signal at least joins the "
                 f"touch (no pure spread-capture rung)")
    # thin-book precision: the improve fraction must stay strictly inside
    # the spread (a full-spread rest is a cross, which defeats maker-only).
    tif = float(_f(config, "execution_tactics.thin_improve_spread_frac", 0.4))
    if not (0.0 <= tif < 0.5):
        fatal(f"execution_tactics.thin_improve_spread_frac={tif} must be in "
              f"[0, 0.5) - at 0.5+ the resting price reaches/crosses the "
              f"opposite touch, which is a taker fill, not maker precision")

    # --- sizer vol scaling + tier reach (lifted literals) --------------------
    vsmin = float(_f(config, "position_sizer.vol_scalar_min", 0.3))
    vsmax = float(_f(config, "position_sizer.vol_scalar_max", 1.5))
    vtgt = float(_f(config, "position_sizer.vol_target_ann_pct", 35.0))
    if not (0.0 <= vsmin <= vsmax):
        fatal("position_sizer vol_scalar bounds incoherent: need "
              "0 <= vol_scalar_min <= vol_scalar_max")
    if vtgt <= 0:
        fatal("position_sizer.vol_target_ann_pct must be positive")
    trd = float(_f(config, "position_sizer.tier_reach_decay", 0.65))
    if not (0.05 <= trd <= 1.0):
        fatal("position_sizer.tier_reach_decay must be in [0.05, 1.0] - it "
              "derives the payoff ratio b/b_net and the Kelly breakeven")
    if bool(_f(config, "risk_protocols.vol_target.enabled", False)):
        advisory("risk_protocols.vol_target is enabled ON TOP of the sizer's "
                 "own vol scaling (position_sizer.vol_target_ann_pct) - two "
                 "vol-targeting layers compound; confirm that is intended")

    # --- per-asset circuit breaker -------------------------------------------
    if bool(_f(config, "circuit_breaker.enabled", True)):
        ls = int(_f(config, "circuit_breaker.loss_streak", 4))
        ch = float(_f(config, "circuit_breaker.cooldown_hours", 6))
        if ls < 2:
            fatal("circuit_breaker.loss_streak < 2 would pause an asset on a "
                  "single loss - that's not a breaker, that's a coin flip")
        if not (0.25 <= ch <= 168):
            fatal("circuit_breaker.cooldown_hours must be in [0.25, 168]")
        if ls > 10:
            advisory(f"circuit_breaker.loss_streak={ls} is so high the "
                     f"breaker will likely never fire (portfolio budgets "
                     f"bind first)")

    # --- asset skimmer (scan wide, trade narrow) -----------------------------
    if bool(_f(config, "skimmer.enabled", False)):
        core = _f(config, "exchanges.kraken.trading_pairs", []) or []
        cands = _f(config, "skimmer.candidates", []) or []
        max_extra = int(_f(config, "skimmer.max_extra", 6))
        # the REST-fallback envelope: with the WS down, N pairs cost
        # ~N*6 book calls + tickers + candles per 30s against 3 req/s (=90).
        # Past ~12 active pairs the fallback falls behind exactly when the
        # primary feed is already degraded. `core` here already includes any
        # promotions merge_skimmer_universe wrote back into trading_pairs, so
        # subtract them (via the runtime-only _merged_promoted marker) before
        # charging max_extra again — they already consumed the promotion
        # budget once (2026-07-25 false FATAL: 6 core + 6 merged read as 18).
        promoted = set(_f(config, "skimmer._merged_promoted", []) or [])
        base = [c for c in core if c not in promoted]
        if len(base) + max_extra > 12:
            fatal(f"skimmer: base ({len(base)}) + max_extra ({max_extra}) "
                  f"exceeds the 12-pair REST-fallback envelope - a WS outage "
                  f"would starve the book poll at 3 req/s")
        pscore = float(_f(config, "skimmer.promote_score", 0.55))
        dscore = float(_f(config, "skimmer.demote_score", 0.35))
        if not (0.0 < dscore < pscore <= 1.0):
            fatal("skimmer: needs 0 < demote_score < promote_score <= 1 "
                  "(equal or inverted bands churn the universe)")
        if float(_f(config, "skimmer.eval_every_min", 60)) < 5:
            fatal("skimmer.eval_every_min below 5 min - candidate polling "
                  "would eat the REST budget the trading path depends on")
        overlap = [c for c in cands if c in base]
        if overlap:
            advisory(f"skimmer: candidates already in trading_pairs are "
                     f"ignored: {overlap}")
        bad = [c for c in cands
               if not (isinstance(c, str) and c.endswith("/USD"))]
        if bad:
            fatal(f"skimmer: candidates must be Kraken 'X/USD' spot pairs "
                  f"(execution venue + quote-currency invariant): {bad}")
        # every tradable pair needs an offline pair-meta row: the generic
        # 2-decimal default silently grids sub-dollar prices (and AssetPairs
        # keys by ALTNAME, so DOGE-style pairs fall back even online)
        try:
            from data.kraken_feed import PAIR_META_FALLBACK
            nometa = [p for p in list(core) + [c for c in cands
                                               if isinstance(c, str)]
                      if p.replace("/", "") not in PAIR_META_FALLBACK]
            if nometa:
                advisory(f"pairs without an offline pair-meta fallback row "
                         f"(would run on the generic 2-decimal default): "
                         f"{nometa} - add them to data/kraken_feed.py "
                         f"PAIR_META_FALLBACK with AssetPairs-verified values")
        except ImportError:
            pass

    # --- entry cap vs the outer rails (coherence, not a hard stop) ----------
    # the position cap should sit at/under the per-order firewall cap and the
    # portfolio heat cap; if it pokes above, those rails still bind, but the
    # position cap is then dead config that reads as bigger than it can act.
    pos_cap = float(_f(config, "position_sizer.max_position_size_pct_of_capital",
                       10.0))
    fw_cap = float(_f(config, "risk_firewall.max_order_pct_equity", 30.0))
    heat_cap = 100.0 * float(_f(config,
                                "risk_protocols.heat.max_portfolio_heat_frac",
                                0.35))
    if pos_cap > fw_cap:
        advisory(f"position cap {pos_cap:.0f}% exceeds the firewall order cap "
                 f"{fw_cap:.0f}% - the firewall will clamp entries first")
    if pos_cap > heat_cap:
        advisory(f"position cap {pos_cap:.0f}% exceeds the portfolio heat cap "
                 f"{heat_cap:.0f}% - a single max position can't fit under heat")

    # --- regime ensemble thresholds -------------------------------------
    mom_bear = float(_f(config, "regime.momentum_bear_max", -0.34))
    mom_bull = float(_f(config, "regime.momentum_bull_min", 0.67))
    if not (-1.0 <= mom_bear < 0.0 < mom_bull <= 1.0):
        fatal(f"regime momentum thresholds incoherent: momentum_bear_max="
              f"{mom_bear} must be in [-1, 0) and momentum_bull_min="
              f"{mom_bull} in (0, 1] (TSMOM score is a mean of signs)")

    # --- crisis percentile + the correlation/turbulence block -------------
    # Both were entirely unguarded (2026-08-22 turbulence verification, §4):
    # zero occurrences of crisis_vol_pct / turbulence / correlation. in this
    # file, while the neighbouring regime.momentum_* and all of vol_regime.*
    # are bounded. crisis_vol_pct is the ONE constant that decides
    # regime/macro_regime.py's crisis label, which sets allow_new: False for
    # the whole book, so a value outside the percentile domain is not a
    # shading error - it is an always-on or never-on safety gate.
    crisis_pct = float(_f(config, "regime.crisis_vol_pct", 95.0))
    if not (0.0 < crisis_pct <= 100.0):
        fatal(f"regime.crisis_vol_pct={crisis_pct} is not a percentile - it "
              f"is compared against vol_percentile and turbulence_pct, both "
              f"0-100 ranks, so <= 0 labels EVERY asset crisis (allow_new: "
              f"False feed-wide) and > 100 can never fire")
    bull_vol_pct = float(_f(config, "regime.bull_volatile_vol_pct", 70.0))
    if crisis_pct <= bull_vol_pct:
        warn(f"regime.crisis_vol_pct={crisis_pct} sits at/below "
             f"bull_volatile_vol_pct={bull_vol_pct} - the crisis cut must be "
             f"the more extreme of the two or the volatile band is dead "
             f"config that crisis always swallows first")

    # correlation block: EWMA decay pair + the turbulence window. The
    # lookback bound is not a taste call - regime/correlation.py takes
    # days = shared[-(lookback + 1):] and then hard-floors the return
    # matrix at 40 rows, so any lookback under 40 makes that floor
    # unreachable and the index NEVER recomputes (it would hold its
    # initial 50.0 forever while reading as a live number).
    turb_lb = _f(config, "correlation.turbulence_lookback_days", 250)
    try:
        turb_lb = int(turb_lb)
    except (TypeError, ValueError, OverflowError):
        fatal(f"correlation.turbulence_lookback_days ({turb_lb!r}) is not an "
              f"integer number of days")
        turb_lb = 250
    if turb_lb < 40:
        fatal(f"correlation.turbulence_lookback_days={turb_lb} is below the "
              f"40-return floor regime/correlation.py enforces - the "
              f"turbulence index could never recompute, and a permanently "
              f"held reading is indistinguishable from a live one at the "
              f"crisis comparison")
    lam_fast = float(_f(config, "correlation.lambda_fast", 0.94))
    lam_slow = float(_f(config, "correlation.lambda_slow", 0.997))
    for _name, _lam in (("lambda_fast", lam_fast), ("lambda_slow", lam_slow)):
        if not (0.0 < _lam < 1.0):
            fatal(f"correlation.{_name}={_lam} must be in (0, 1) - it is a "
                  f"RiskMetrics EWMA decay; outside that the estimator "
                  f"either never updates or never forgets")
    if lam_fast >= lam_slow:
        warn(f"correlation.lambda_fast={lam_fast} >= lambda_slow={lam_slow} "
             f"- the fast estimator must decay FASTER (smaller lambda) or "
             f"the fast-minus-slow correlation shift signal is inverted/dead")
    shift_thr = float(_f(config, "correlation.shift_threshold", 0.25))
    if not (0.0 < shift_thr <= 2.0):
        warn(f"correlation.shift_threshold={shift_thr} is outside (0, 2] - "
             f"the shift is a difference of two correlations, so <= 0 marks "
             f"the book shifted on every update and > 2 can never fire "
             f"(telemetry/logging only, hence WARN not FATAL)")

    # --- liquidity regime: whiplash detector coherence --------------------
    # whiplash is the std of an imbalance ratio clamped to [0, 3], so it is
    # structurally bounded by 1.5. Outside (0, 1.5) the detector is not a
    # detector: <= 0 fires always (size_mult=0 -> vetoes EVERY entry),
    # >= 1.5 can never fire. Healthy books at the ~30s book-sampling
    # cadence measure p50~1.1 (45h live evidence), so low thresholds
    # reproduce the always-on failure in practice as well.
    wt = float(_f(config, "liquidity_regime.imbalance_whiplash_threshold",
                  1.45))
    if wt <= 0.0:
        fatal(f"liquidity_regime.imbalance_whiplash_threshold={wt} fires on "
              f"every cycle - the 'spoofy' label zeroes sizing, so this "
              f"blocks 100% of entries structurally")
    elif wt >= 1.5:
        warn(f"liquidity_regime.imbalance_whiplash_threshold={wt} exceeds "
             f"the metric's ceiling (std of a [0,3]-clamped ratio is "
             f"bounded by 1.5) - the whiplash detector can never fire")
    elif wt < 1.0:
        warn(f"liquidity_regime.imbalance_whiplash_threshold={wt} is below "
             f"the healthy-book baseline (p50~1.1 at the 30s book cadence; "
             f"45h evidence in outputs/monitor/liquidity_dist.jsonl) - "
             f"expect near-constant 'spoofy' labels vetoing all entries")
    # manip_suspect's whiplash component normalizes the raw std against
    # [healthy_p95, threshold]; a p95 at/above the threshold collapses the
    # ramp into a 0/1 step, and a p95 at/below the healthy MEDIAN re-creates
    # the saturation bug this knob exists to prevent (manip pegged 1.0 on
    # ordinary quiet books, halving healthy rows' training weight)
    wp95 = float(_f(config, "liquidity_regime.whiplash_healthy_p95", 1.27))
    if wp95 >= wt:
        fatal(f"liquidity_regime.whiplash_healthy_p95={wp95} >= "
              f"imbalance_whiplash_threshold={wt} - the manip_suspect "
              f"whiplash ramp needs healthy_p95 strictly below the spoofy "
              f"threshold")
    elif wp95 <= 1.1:
        warn(f"liquidity_regime.whiplash_healthy_p95={wp95} sits at/below "
             f"the healthy-book median (p50~1.1) - manip_suspect will read "
             f"elevated on ordinary quiet books")

    # --- spoof EWMA smoothing weight (lifted 2026-08-27, config audit) ----
    # spoof_score = 1 - exp(-3 * ewma), ewma updated with this weight every
    # snapshot; the score hard-vetoes books at the spoofy thresholds above.
    # Outside (0, 1] it is not an EWMA weight: <= 0 freezes the score at
    # its seed forever (the veto never updates on evidence), > 1
    # overshoots. Above 0.5 the smoothing is effectively off - a
    # near-per-snapshot reading, defeating the sustained-evidence
    # semantics the SD-003 healthy-book bar was derived under (0.85
    # requires a sustained ~0.63 events/cycle EWMA at alpha 0.06).
    sea = float(_f(config, "liquidity_regime.spoof_ewma_alpha", 0.06))
    if not (0.0 < sea <= 1.0):
        fatal(f"liquidity_regime.spoof_ewma_alpha={sea} outside (0, 1] - "
              f"not an EWMA weight: <=0 freezes the spoof score at its "
              f"seed forever (the veto never updates), >1 overshoots")
    elif sea > 0.5:
        warn(f"liquidity_regime.spoof_ewma_alpha={sea} > 0.5 - smoothing "
             f"effectively off (near-per-snapshot spoof score); the SD-003 "
             f"healthy-book bar derivation assumed sustained-evidence "
             f"semantics at alpha 0.06")

    # --- v9 liquidity-tier isolation coherence ----------------------------
    # The cap-tiers scale ONLY the categorical executability floors. Two
    # invariants keep them coherent: CORE must reproduce the legacy flat floors
    # exactly (else enabling tiers silently retunes ETH/BTC and quant_trials/
    # overfit), and a THINNER tier must never be STRICTER than a richer one
    # (lower depth floor => wider spread ceiling), else the isolation gates
    # low-volume assets harder than the majors — the opposite of its purpose.
    lr = config.get("liquidity_regime", {}) or {}
    tcfg = lr.get("tiers") or {}
    if tcfg.get("enabled"):
        base_depth = float(lr.get("min_depth_usd", 150_000))
        base_spread = float(lr.get("max_spread_bps", 12.0))
        order = tcfg.get("order") or ["core", "mid", "micro"]
        rows = [(str(n),
                 float((tcfg.get(n) or {}).get("min_depth_usd", base_depth)),
                 float((tcfg.get(n) or {}).get("max_spread_bps", base_spread)))
                for n in order]
        core = next((r for r in rows if r[0] == "core"), None)
        if core is None:
            fatal("liquidity_regime.tiers.enabled but no 'core' tier defined - "
                  "core anchors the majors to the legacy floors")
        elif abs(core[1] - base_depth) > 1e-6 or \
                abs(core[2] - base_spread) > 1e-6:
            fatal(f"liquidity_regime.tiers.core "
                  f"({core[1]:.0f}/{core[2]:.0f}) must equal the legacy flat "
                  f"floors min_depth_usd/max_spread_bps "
                  f"({base_depth:.0f}/{base_spread:.0f}) - core is the majors' "
                  f"anchor; drift here silently retunes ETH/BTC")
        if any(r[1] <= 0 or r[2] <= 0 for r in rows):
            fatal("liquidity_regime.tiers floors must be positive")
        srt = sorted(rows, key=lambda r: r[1], reverse=True)
        for a, b in zip(srt, srt[1:], strict=False):
            if b[2] < a[2] - 1e-6:
                fatal(f"liquidity_regime.tiers: tier '{b[0]}' has a thinner "
                      f"depth floor than '{a[0]}' but a TIGHTER spread ceiling "
                      f"({b[2]:.0f} < {a[2]:.0f}); a thinner tier must allow a "
                      f"WIDER spread, else isolation is incoherent")

    # pretrade per-tier spread ceiling: core must match the flat cap, and the
    # ceiling must not tighten as tiers thin (mirror of the depth-tier rule).
    pt = config.get("pretrade", {}) or {}
    pt_tms = pt.get("tier_max_spread_bps") or {}
    if pt_tms:
        pt_base = float(pt.get("max_spread_bps", 15.0))
        vals = {str(k): float(v) for k, v in pt_tms.items()
                if not str(k).startswith("_")}
        if "core" in vals and abs(vals["core"] - pt_base) > 1e-6:
            fatal(f"pretrade.tier_max_spread_bps.core ({vals['core']:.0f}) must "
                  f"equal pretrade.max_spread_bps ({pt_base:.0f}) - core is the "
                  f"majors' spread ceiling")
        if any(v <= 0 for v in vals.values()):
            fatal("pretrade.tier_max_spread_bps values must be positive")
        # monotonicity is FATAL here (unlike the size-only depth-tier ordering):
        # this ceiling is the LIVE-ORDER veto (PT-021). Check it against the SAME
        # depth-tier order the classifier uses, generically over whatever tiers
        # are declared (not hardcoded core/mid/micro), and flag any declared
        # liquidity tier missing a pretrade cap (it silently falls back to flat).
        lr_tiers = lr.get("tiers") or {}
        if lr_tiers.get("enabled"):
            lr_base_depth = float(lr.get("min_depth_usd", 150_000))
            t_order = lr_tiers.get("order") or ["core", "mid", "micro"]
            depth_of = {n: float((lr_tiers.get(n) or {}).get(
                "min_depth_usd", lr_base_depth)) for n in t_order}
            richest_first = sorted(t_order, key=lambda n: depth_of[n],
                                   reverse=True)
            prev_n, prev_cap = None, None
            for n in richest_first:
                cap = vals.get(n)
                if cap is None:
                    warn(f"pretrade.tier_max_spread_bps has no entry for tier "
                         f"'{n}' (declared in liquidity_regime.tiers) — it falls "
                         f"back to the flat max_spread_bps={pt_base:.0f}, which "
                         f"may gate that tier's assets too hard")
                    continue
                if prev_cap is not None and cap < prev_cap - 1e-6:
                    fatal(f"pretrade.tier_max_spread_bps: tier '{n}' is thinner "
                          f"than '{prev_n}' but has a TIGHTER spread ceiling "
                          f"({cap:.0f} < {prev_cap:.0f}) — the live-order veto "
                          f"would gate low-volume assets HARDER than the majors")
                prev_n, prev_cap = n, cap
        else:
            c, m, mi = vals.get("core"), vals.get("mid"), vals.get("micro")
            if c is not None and m is not None and mi is not None \
                    and not (mi >= m >= c):
                warn(f"pretrade.tier_max_spread_bps not monotonic "
                     f"core<=mid<=micro ({c:.0f}/{m:.0f}/{mi:.0f})")

    # --- v10 grid ladder coherence ----------------------------------------
    gl = config.get("grid_ladder", {}) or {}
    if gl.get("enabled"):
        gl_rungs = int(gl.get("rungs", 3))
        gl_decay = float(gl.get("size_decay", 0.7))
        gl_arm = float(gl.get("p_win_arm", 0.60))
        gl_disarm = float(gl.get("p_win_disarm", 0.55))
        gl_mult = float(gl.get("spacing_vol_mult", 0.35))
        gl_floor = float(gl.get("min_spacing_bps", 8.0))
        if not (1 <= gl_rungs <= 6):
            fatal(f"grid_ladder.rungs={gl_rungs} out of [1, 6] - a deeper "
                  f"ladder than the position-slot budget (5) can never fill "
                  f"and only bloats the resting book")
        if not (0.0 < gl_decay <= 1.0):
            fatal(f"grid_ladder.size_decay={gl_decay} must be in (0, 1] - "
                  f">1 loads the LARGEST size furthest from the signal")
        if not (gl_disarm < gl_arm <= 1.0):
            fatal(f"grid_ladder p_win_disarm={gl_disarm} must be strictly "
                  f"below p_win_arm={gl_arm} (<= 1) - equal/inverted bars "
                  f"remove the hysteresis and the ladder flaps every cycle")
        if gl_mult <= 0.0 or gl_floor <= 0.0:
            fatal("grid_ladder spacing (spacing_vol_mult, min_spacing_bps) "
                  "must be positive - zero spacing stacks every rung at one "
                  "price (a single entry pretending to be a ladder)")
        gl_min_pwin = float(_f(config, "position_sizer.min_p_win", 0.55))
        if gl_arm < gl_min_pwin:
            # config-honesty note, not an operational concern (the bot trades
            # correctly): the sizer's own p(win) floor screens entries first,
            # so an arm bar below it simply arms on every approved entry.
            # (Compared against the min_p_win FLOOR, not the derived bar:
            # in derived mode the effective bar is higher still, so the
            # note only understates - it never false-alarms.)
            advisory(f"grid_ladder.p_win_arm={gl_arm} sits below the sizer's "
                     f"entry floor ({gl_min_pwin}) - the ladder arms on "
                     f"every approved entry (hysteresis still applies)")

    # --- rev-5 adaptive blocks: aggression / gate learning / exit coupling
    ia = _f(config, "position_sizer.inventory_aggression", {}) or {}
    if isinstance(ia, dict) and ia.get("enabled"):
        lb = float(ia.get("light_boost", 1.10))
        hc = float(ia.get("heavy_cut", 0.65))
        if not (1.0 <= lb <= 1.5):
            fatal(f"inventory_aggression.light_boost={lb} must be in "
                  f"[1.0, 1.5] - below 1 punishes an empty book, above "
                  f"1.5 overrides Kelly by half again")
        if not (0.2 <= hc <= 1.0):
            fatal(f"inventory_aggression.heavy_cut={hc} must be in "
                  f"[0.2, 1.0] - 0 would silently veto every entry at a "
                  f"full book (that is the inventory cap's job)")
        if float(ia.get("short_window_hours", 6)) <= 0:
            fatal("inventory_aggression.short_window_hours must be positive")
        fh = float(ia.get("full_book_heat_frac", 0.35))
        if not (0.05 <= fh <= 1.0):
            fatal(f"inventory_aggression.full_book_heat_frac={fh} out of "
                  f"[0.05, 1.0]")
    if bool(_f(config, "profit_taking.signal_decay.enabled", False)):
        sd_t = float(_f(config, "profit_taking.signal_decay.tighten_factor",
                        0.5))
        if not (0.1 <= sd_t <= 1.0):
            fatal(f"profit_taking.signal_decay.tighten_factor={sd_t} must "
                  f"be in [0.1, 1.0] - below it is an instant exit, above "
                  f"it would LOOSEN the leash on a dead thesis")
    if bool(_f(config, "profit_taking.inventory_coupling.enabled", False)):
        icb = float(_f(config, "profit_taking.inventory_coupling.max_boost",
                       0.5))
        if not (0.0 <= icb <= 1.0):
            fatal(f"profit_taking.inventory_coupling.max_boost={icb} must "
                  f"be in [0, 1] - doubling a tier close at full pressure "
                  f"is the sane ceiling")
    lw = _f(config, "signal_gates.learned_weights", {}) or {}
    if isinstance(lw, dict) and lw.get("enabled"):
        if int(lw.get("min_samples", 40)) < 5:
            warn("signal_gates.learned_weights.min_samples < 5: the Wilson "
                 "bound on so few labeled passes is noise, not evidence")
        st = float(lw.get("strength", 2.0))
        if not (0.0 <= st <= 5.0):
            fatal(f"signal_gates.learned_weights.strength={st} out of "
                  f"[0, 5]")

    # --- strategies.engine: which entry-signal engine actually runs -------
    # main.py:540 dispatches InformedFlowEngine on an EXACT "informed_flow"
    # match and falls through to the rev-1 SignalGateEngine for literally
    # anything else. Both expose the same evaluate_asset signature and the
    # call site uses defensive getattr, so a typo ("informed-flow",
    # "informedflow", "5gate") does not crash - it silently swaps the entire
    # entry-signal engine and every real-money entry with it. This key had
    # ZERO validation while the structurally identical ml.label_mode typo
    # already FATALs. Aggravated by ml/history.py:782: under five_gate the
    # sg_* feature columns are written as 0.0, so the learning corpus
    # accumulates zero-filled rows indistinguishable from pre-instrumentation
    # ones - a silent engine swap poisons the ML corpus too, not just entries.
    eng_raw = _f(config, "strategies.engine")
    if eng_raw is None:
        # NOT a default here: mirror main.py's ACTUAL fallback so the guard
        # never reports on an engine other than the one that will run. The
        # code default ("five_gate") is the opposite of config.json's shipped
        # value ("informed_flow") and of main.py's own module docstring -
        # deleting the key silently rolls the bot back to rev-1.
        advisory(f"strategies.engine unset - main.py falls back to "
                 f"'{_MAIN_ENGINE_FALLBACK}' (the rev-1 rollback stack) "
                 f"while config.json ships 'informed_flow'. Set it "
                 f"explicitly; an absent key is a silent engine swap.")
    elif str(eng_raw) not in KNOWN_SIGNAL_ENGINES:
        fatal(f"strategies.engine '{eng_raw}' is not a known engine "
              f"{sorted(KNOWN_SIGNAL_ENGINES)} - main.py dispatches "
              f"InformedFlowEngine on an EXACT 'informed_flow' match and "
              f"silently falls through to the rev-1 SignalGateEngine for "
              f"every other value, so a typo swaps the entire entry-signal "
              f"engine (and zero-fills the sg_* learning features) with no "
              f"error anywhere")

    # --- informed_flow (rev-3 fusion engine) coherence --------------------
    # strategies.engine defaults to "informed_flow" (config.json's shipped
    # default) - unlike signal_gates.learned_weights above, this section had
    # NO guard coverage even though it is the active decision path, not the
    # five_gate rollback. Checked unconditionally (like learned_weights) so
    # switching strategies.engine later stays covered too.
    N_COMPONENTS = 5  # flow, delta, accum, burst, trend - see evaluate_asset
    if_min_agree = int(_f(config, "informed_flow.min_agree", 3))
    if not (1 <= if_min_agree <= N_COMPONENTS):
        fatal(f"informed_flow.min_agree={if_min_agree} must be in "
              f"[1, {N_COMPONENTS}] - the engine fuses {N_COMPONENTS} "
              f"components (flow/delta/accum/burst/trend); a value outside "
              f"that range can never be satisfied or is not a real bar")
    if_evidence = float(_f(config, "informed_flow.evidence_threshold", 1.15))
    if if_evidence <= 0:
        fatal("informed_flow.evidence_threshold must be positive - it "
              "gates confirmation on |sum(w_i * s_i)|")
    if_flow_min = float(_f(config, "informed_flow.flow_min", 0.25))
    if not (0.0 <= if_flow_min <= 1.0):
        fatal(f"informed_flow.flow_min={if_flow_min} must be in [0, 1] - "
              f"s_flow is a tanh score bounded there")
    if_material = float(_f(config, "informed_flow.material_threshold", 0.10))
    if not (0.0 <= if_material <= 1.0):
        fatal(f"informed_flow.material_threshold={if_material} must be in "
              f"[0, 1] - components vote on |s_i| >= this")
    if_persist = int(_f(config, "informed_flow.persistence_evals", 3))
    if if_persist < 1:
        fatal("informed_flow.persistence_evals must be >= 1")
    if_fast = int(_f(config, "informed_flow.fast_period", 9))
    if_slow = int(_f(config, "informed_flow.slow_period", 21))
    if if_fast < 2:
        fatal("informed_flow.fast_period must be >= 2")
    if if_slow <= if_fast:
        fatal(f"informed_flow.slow_period ({if_slow}) must exceed "
              f"fast_period ({if_fast}) - EMA cross is meaningless "
              f"otherwise (the engine silently clamps this at runtime, "
              f"which is not the same as the configured intent being sane)")
    # V3 sufficiency floor must cover the vol estimator's warmup: signals
    # (and the bracket geometry they price) may only evaluate once
    # VolState.measured is true, i.e. >= FAST_WARMUP_BARS candles. The
    # engine's floor is max(slow_period+2, ad_lookback_bars+1, 14) AFTER
    # its runtime clamps (fast>=2, slow>fast, ad>=4) - mirrored here so
    # the guard judges the numbers the engine will actually run. Below
    # the warmup, entry decisions would do arithmetic on the VolState
    # placeholder (the cold-sigma failure class of LINK 3ea2a851,
    # 2026-07-28 - the exit side is gated in code; this pins the entry
    # side, which is warm-by-construction only while this holds).
    if_ad = int(_f(config, "informed_flow.ad_lookback_bars", 24))
    eff_fast = max(if_fast, 2)
    eff_slow = max(if_slow, eff_fast + 1)
    eff_ad = max(if_ad, 4)
    if_min_bars = max(eff_slow + 2, eff_ad + 1, 14)
    if if_min_bars < FAST_WARMUP_BARS:
        fatal(f"informed_flow V3 sufficiency floor {if_min_bars} bars "
              f"(max(slow_period+2, ad_lookback_bars+1, 14)) is below the "
              f"vol estimator's {FAST_WARMUP_BARS}-bar warmup - signals "
              f"would evaluate on an UNMEASURED VolState placeholder "
              f"(sigma 0.05), pricing entry/bracket geometry off a "
              f"fabricated number")
    if_weights = _f(config, "informed_flow.weights", {}) or {}
    if isinstance(if_weights, dict):
        neg = [k for k, v in if_weights.items()
              if isinstance(v, (int, float)) and v < 0]
        if neg:
            warn(f"informed_flow.weights has negative entries {neg} - this "
                 f"INVERTS that component's contribution to the evidence "
                 f"sum; confirm that is intentional, not a sign typo")
    if_amove = float(_f(config, "informed_flow.absorption_move_sigmas", 1.0))
    if if_amove <= 0:
        fatal("informed_flow.absorption_move_sigmas must be positive")
    if_aad = float(_f(config, "informed_flow.absorption_ad_min", 0.15))
    if not (0.0 <= if_aad <= 1.0):
        fatal(f"informed_flow.absorption_ad_min={if_aad} must be in [0, 1]")

    # --- THALES lazy-bot insecurity model (docs/THALES.md) ----------------
    th_infl = str(_f(config, "thales.influence", "shadow")).lower()
    th_enabled = bool(_f(config, "thales.enabled", False))
    if th_infl not in ("off", "shadow", "advise"):
        fatal(f"thales.influence='{th_infl}' unknown - must be off, shadow, "
              f"or advise (the engine would silently fall back to shadow, "
              f"which is not the same as the configured intent being sane)")
    if th_infl == "advise" and not th_enabled:
        fatal("thales.influence=advise with thales.enabled=false is "
              "incoherent - advice requires a running detector bank")
    th_shade = float(_f(config, "thales.max_conf_shade", 1.15))
    if not (1.0 <= th_shade <= 1.5):
        fatal(f"thales.max_conf_shade={th_shade} must be in [1.0, 1.5] - "
              f"the advice channel is a SHADE on gate confidence, not a "
              f"signal source; beyond 1.5 it overrides the gates")
    if th_infl == "advise" and th_shade == 1.0:
        warn("thales.influence=advise with max_conf_shade=1.0 is a no-op - "
             "advice can never move confidence")
    # TH-021 evidence-concentration shade coherence (a DOWN-only trim of
    # diffuse-and-marginal confidence). Nonsense bounds silently degrade it.
    if bool(_f(config, "thales.evidence_concentration.enabled", False)):
        ec_pivot = float(_f(config, "thales.evidence_concentration.conc_pivot", 0.35))
        ec_atten = float(_f(config, "thales.evidence_concentration.max_atten", 0.15))
        ec_hi = float(_f(config, "thales.evidence_concentration.marginal_conf", 0.65))
        ec_lo = float(_f(config, "thales.evidence_concentration.floor_conf", 0.50))
        if not (0.0 < ec_pivot <= 1.0):
            fatal(f"thales.evidence_concentration.conc_pivot={ec_pivot} must be "
                  f"in (0, 1] - it is the concentration BELOW which a signal "
                  f"counts as diffuse")
        if not (0.0 <= ec_atten <= 0.5):
            fatal(f"thales.evidence_concentration.max_atten={ec_atten} must be "
                  f"in [0, 0.5] - it is a bounded confidence TRIM, not a veto")
        if not ec_hi > ec_lo:
            fatal(f"thales.evidence_concentration.marginal_conf={ec_hi} must "
                  f"exceed floor_conf={ec_lo} - the marginality ramp is "
                  f"degenerate otherwise (every signal trimmed equally)")
    th_z = float(_f(config, "thales.clockwork.z_thr", 2.33))
    if th_z < 1.5:
        fatal(f"thales.clockwork.z_thr={th_z} below 1.5 disables the "
              f"significance gate on time-of-day flow - that gate is the "
              f"anti-overfit teeth (OF-2 discipline); mining unsignificant "
              f"seasonality is exactly the lazy-bot sin this model hunts")
    for knob in ("grid.gain", "metronome.gain", "clockwork.gain",
                 "stops.pre_gain", "stops.post_gain",
                 "feed_integrity.gain", "spoof.gain"):
        gv = float(_f(config, f"thales.{knob}", 0.0))
        if gv < 0.0:
            fatal(f"thales.{knob}={gv} negative - inverted advice; flip "
                  f"the detector's exploit thesis in code, not via sign")
    # A-S inventory skew (position_sizer.inventory_skew): an unknown mode
    # silently disables a risk overlay the operator believes is on; a
    # gamma above ~2 can floor EVERY same-direction entry (the floor then
    # hides the misconfiguration); sigma_ref at/below zero divides by it.
    sk_mode = str(_f(config, "position_sizer.inventory_skew.mode",
                     "shadow")).lower()
    if sk_mode not in ("off", "shadow", "active"):
        fatal(f"position_sizer.inventory_skew.mode='{sk_mode}' unknown - "
              f"must be off, shadow, or active")
    sk_g = float(_f(config, "position_sizer.inventory_skew.gamma", 0.5))
    if sk_g < 0.0:
        fatal(f"position_sizer.inventory_skew.gamma={sk_g} negative - "
              f"inverted skew would REWARD piling onto inventory")
    elif sk_g > 2.0:
        warn(f"position_sizer.inventory_skew.gamma={sk_g} above 2: most "
             f"same-direction entries will sit at floor_mult - the skew "
             f"becomes a step function, not a gradient")
    sk_ref = float(_f(config, "position_sizer.inventory_skew.sigma_ref_pct",
                      60.0))
    if sk_ref <= 0.0:
        fatal(f"position_sizer.inventory_skew.sigma_ref_pct={sk_ref} must "
              f"be positive - it normalizes the sigma^2 amplifier")
    sk_fl = float(_f(config, "position_sizer.inventory_skew.floor_mult",
                     0.25))
    if not (0.05 <= sk_fl <= 1.0):
        fatal(f"position_sizer.inventory_skew.floor_mult={sk_fl} must be "
              f"in [0.05, 1.0] - zero would silently veto entries (that "
              f"is the inventory MANAGER's job, with its own code)")

    # TH-017 spoof-flicker coherence: a big_ratio near 1 calls ordinary
    # depth churn a spoof (every MM reprice flickers); drop/decay/thr
    # outside their unit ranges make the EWMA either never fire or latch.
    sp_br = float(_f(config, "thales.spoof.big_ratio", 3.0))
    if sp_br < 1.5:
        fatal(f"thales.spoof.big_ratio={sp_br} below 1.5 - a level barely "
              f"above median depth is ordinary MM churn, not layering; "
              f"this would shade on every reprice")
    sp_df = float(_f(config, "thales.spoof.drop_frac", 0.8))
    if not (0.0 < sp_df <= 1.0):
        fatal(f"thales.spoof.drop_frac={sp_df} must be in (0, 1] - the "
              f"fraction of a level that must vanish to count as pulled")
    sp_dc = float(_f(config, "thales.spoof.decay", 0.85))
    if not (0.0 < sp_dc < 1.0):
        fatal(f"thales.spoof.decay={sp_dc} must be in (0, 1) - at 0 the "
              f"EWMA has no memory, at 1 it never forgets a flicker")
    sp_st = float(_f(config, "thales.spoof.score_thr", 0.35))
    if not (0.0 < sp_st < 1.0):
        fatal(f"thales.spoof.score_thr={sp_st} must be in (0, 1)")
    if int(_f(config, "thales.spoof.top_levels", 5)) < 2:
        fatal("thales.spoof.top_levels below 2 cannot compute a median "
              "depth to compare against")

    # V2 reliability: min_fired is the cold-start fence. Below ~5 grades a
    # Wilson LCB is pure noise and weights would flap trade-to-trade; a
    # huge value silently disables the vindication loop (weights pinned at
    # the prior forever while claiming to be evidence-based).
    th_mf = int(_f(config, "thales.reliability.min_fired", 20))
    if th_mf < 5:
        fatal(f"thales.reliability.min_fired={th_mf} below 5 grades a "
              f"detector on a sample where the Wilson bound is noise - "
              f"weights would flap on every trade")
    elif th_mf > 500:
        warn(f"thales.reliability.min_fired={th_mf} over 500: at this "
             f"corpus's trade rate the vindication loop would never "
             f"activate - evidence-weighting in name only")
    # TH-014 feed_integrity bounds: a threshold outside [0,1] or a min_obs
    # not inside [1, window] makes the detector either never fire or fire on
    # noise. Fail loud rather than shade on a nonsense config.
    fi_thr = float(_f(config, "thales.feed_integrity.dirty_frac_thr", 0.25))
    if not (0.0 <= fi_thr <= 1.0):
        fatal(f"thales.feed_integrity.dirty_frac_thr={fi_thr} must be a "
              f"fraction in [0, 1] - it gates on a rejected-data RATE")
    fi_win = int(_f(config, "thales.feed_integrity.window", 40))
    fi_min = int(_f(config, "thales.feed_integrity.min_obs", 20))
    if fi_win < 1:
        fatal(f"thales.feed_integrity.window={fi_win} must be >= 1")
    if not (1 <= fi_min <= fi_win):
        fatal(f"thales.feed_integrity.min_obs={fi_min} must be in "
              f"[1, window={fi_win}] - beyond the window the detector can "
              f"never accumulate enough samples to ever judge")
    # TH-016 lapse hygiene: a non-positive gap threshold makes EVERY cycle
    # a lapse (permanent warmup = the engine silently disabled); negative
    # durations are nonsense; a bar fence below 2 spacings fires on ordinary
    # venue jitter and erases healthy swing context.
    lp_gap = float(_f(config, "thales.lapse.fast_gap_sec", 600.0))
    if lp_gap <= 0:
        fatal(f"thales.lapse.fast_gap_sec={lp_gap} must be > 0 - at zero "
              f"every observation counts as a lapse and THALES mutes itself "
              f"forever (a silent disable disguised as hygiene)")
    elif lp_gap < 60:
        warn(f"thales.lapse.fast_gap_sec={lp_gap} below 60s: fast cadence "
             f"is ~5s and ordinary proxy flaps last seconds - this would "
             f"spend most of its life in warmup")
    lp_wu = float(_f(config, "thales.lapse.warmup_sec", 900.0))
    if lp_wu < 0:
        fatal(f"thales.lapse.warmup_sec={lp_wu} negative - a lapse cannot "
              f"end before it is detected")
    lp_bg = float(_f(config, "thales.lapse.bar_gap_bars", 3.0))
    if lp_bg < 2:
        fatal(f"thales.lapse.bar_gap_bars={lp_bg} must be >= 2 - one "
              f"missing bar is venue jitter, not a hole; fencing on it "
              f"erases healthy swing/sweep context daily")
    lp_skew = float(_f(config, "thales.lapse.clock_skew_tol_sec", 1.0))
    if lp_skew < 0:
        fatal(f"thales.lapse.clock_skew_tol_sec={lp_skew} negative - "
              f"tolerance is a magnitude")
    elif lp_skew >= lp_gap:
        warn(f"thales.lapse.clock_skew_tol_sec={lp_skew} >= "
             f"fast_gap_sec={lp_gap}: tolerating a bigger backwards clock "
             f"jump than the forward gap called a lapse silently disables "
             f"the counter-rollback arm (the 2026-07-14 incident class)")

    # --- Smart Money Concepts features (docs/SMC.md) ----------------------
    smc_enabled = bool(_f(config, "smc.enabled", True))
    if smc_enabled:
        for fast_path, slow_path in (
                ("smc.mtf.ltf_fast_period", "smc.mtf.ltf_slow_period"),
                ("smc.mtf.htf_fast_period", "smc.mtf.htf_slow_period")):
            mtf_fast = int(_f(config, fast_path, 9))
            mtf_slow = int(_f(config, slow_path, 21))
            if mtf_fast < 2:
                fatal(f"{fast_path} must be >= 2")
            if mtf_slow <= mtf_fast:
                fatal(f"{slow_path} ({mtf_slow}) must exceed {fast_path} "
                      f"({mtf_fast}) - EMA cross is meaningless otherwise")
        for path, lo, hi in (
                ("smc.liquidity.pull_max_pct", 0.0, 100.0),
                ("smc.fvg.pull_max_pct", 0.0, 100.0),
                ("smc.fvg.min_gap_pct", 0.0, 100.0),
                ("smc.fvg.confluence_tol_pct", 0.0, 100.0),
                ("smc.volume_profile.poc_dist_cap_pct", 0.0, 100.0)):
            v = float(_f(config, path, 1.0))
            if not (lo < v <= hi):
                fatal(f"{path}={v} must be in ({lo}, {hi}] - zero or "
                      f"negative disables the feature as a silent no-op "
                      f"instead of an explicit smc.enabled=false")
        va_pct = float(_f(config, "smc.volume_profile.value_area_pct", 0.68))
        if not (0.0 < va_pct <= 1.0):
            fatal(f"smc.volume_profile.value_area_pct={va_pct} must be in "
                  f"(0, 1] - it is a fraction of total profile volume")
        n_bins = int(_f(config, "smc.volume_profile.n_bins", 24))
        if n_bins < 3:
            fatal(f"smc.volume_profile.n_bins={n_bins} must be >= 3 - a "
                  f"POC/Value-Area needs bins either side of the mode")
        for path in ("smc.pd_zone.lookback", "smc.liquidity.lookback",
                     "smc.fvg.lookback_bars",
                     "smc.volume_profile.lookback_bars"):
            lb = int(_f(config, path, 8))
            if lb < 8:
                fatal(f"{path}={lb} must be >= 8 - below that the swing/"
                      f"profile window can't distinguish structure from "
                      f"noise (matches strategies/swing_points.MIN_BARS)")

    # --- live websocket data feed (data/ws_feed.py) ----------------------
    if bool(_f(config, "websockets.enabled", False)):
        max_age = float(_f(config, "websockets.max_book_age_sec", 2.0))
        poll = float(_f(config, "system.polling_interval_sec", 5))
        if max_age <= 0:
            fatal(f"websockets.max_book_age_sec={max_age} must be > 0 - a "
                  f"non-positive staleness gate would trust a dead socket "
                  f"forever")
        if max_age > poll:
            # a cache older than one poll interval buys no freshness over
            # REST - the whole point is a book fresher than a poll cycle
            findings.append(("WARN",
                             f"websockets.max_book_age_sec={max_age} exceeds "
                             f"system.polling_interval_sec={poll} - live "
                             f"books can be older than a REST cycle, negating "
                             f"the latency edge"))
        interval = int(_f(config, "websockets.interval_ms", 100))
        if interval < 100:
            findings.append(("WARN",
                             f"websockets.interval_ms={interval} is below "
                             f"Binance.US's 100ms floor - it will be clamped "
                             f"venue-side"))
        depth = int(_f(config, "websockets.depth", 20))
        if depth not in (5, 10, 20):
            fatal(f"websockets.depth={depth} must be 5, 10, or 20 - the "
                  f"Binance.US partial-depth stream only offers those levels")
        if not (_f(config, "websockets.binanceus_symbols", []) or []):
            fatal("websockets.enabled but websockets.binanceus_symbols is "
                  "empty - nothing to subscribe to")

    # --- Kraken v2 live book stream (data/ws_feed.KrakenV2BookStream) -----
    # Wired INDEPENDENTLY of websockets.enabled (main.py gates it on
    # websockets.kraken_enabled), so its knobs need their OWN validation.
    #
    # SEMANTICS CHANGED 2026-08-09 (owed 42a, commit 36fcfd6e). Books now
    # carry their own receive stamp (recv_ts) and the engine stamps
    # book_ts from it, so book_ts is DATA time, not read time. The old
    # hazard was "a stale book reads FRESH and defeats the watchdog"; that
    # is now inverted - an old book reports its true age, which the
    # pre-trade gate ACTS on. The knob therefore has a new, tighter
    # binding constraint checked below.
    if bool(_f(config, "websockets.kraken_enabled", False)):
        k_age = float(_f(config, "websockets.kraken_max_book_age_sec", 5.0))
        poll = float(_f(config, "system.polling_interval_sec", 5))
        stale_ms = float(_f(config, "pretrade.max_data_staleness_ms", 4000.0))
        if k_age <= 0:
            fatal(f"websockets.kraken_max_book_age_sec={k_age} must be > 0 - a "
                  f"non-positive staleness gate would trust a dead socket "
                  f"forever")
        # THE COHERENCE RELATION (2026-08-09): the ws cache serves any book
        # younger than k_age, and the pre-trade gate vetoes any book older
        # than max_data_staleness_ms. If k_age*1000 >= stale_ms there is a
        # band of book ages that the feed SERVES and the decision path then
        # VETOES (PT-020) - and because main.py only falls back to REST when
        # the ws returns None, that served-but-doomed book PREEMPTS a REST
        # read that would have been fresh. The result is entries silently
        # refused while a good data source sits one call away. Measured on
        # the 2026-08-08 config (5.0s vs 4000ms): a 1000ms-wide dead band,
        # hitting the thinnest pairs hardest (~3% of evaluations) and so
        # skewing which assets can ever accumulate fill labels.
        if k_age * 1000.0 >= stale_ms:
            fatal(f"websockets.kraken_max_book_age_sec={k_age}s "
                  f"(={k_age * 1000.0:.0f}ms) must be < "
                  f"pretrade.max_data_staleness_ms={stale_ms:.0f}ms - books "
                  f"in the overlap are SERVED by the ws cache and then "
                  f"vetoed by the pre-trade staleness gate (PT-020), "
                  f"preempting a REST read that would have been fresh. "
                  f"Lower the book age (preferred) rather than raising the "
                  f"veto ceiling")
        if k_age > 30.0:
            fatal(f"websockets.kraken_max_book_age_sec={k_age} must be <= 30s - "
                  f"a book that stale is far past any plausible decision "
                  f"horizon; since 42a its true age reaches the pre-trade "
                  f"gate, so this only guarantees vetoed entries")
        elif k_age > poll:
            findings.append(("WARN",
                             f"websockets.kraken_max_book_age_sec={k_age} "
                             f"exceeds system.polling_interval_sec={poll} - live "
                             f"books can be older than a REST cycle"))
        k_depth = int(_f(config, "websockets.kraken_depth", 10))
        if k_depth not in (10, 25, 100, 500, 1000):
            fatal(f"websockets.kraken_depth={k_depth} must be one of "
                  f"10/25/100/500/1000 - the Kraken v2 book channel only "
                  f"offers those depths")
        # W2-28 checksum-mismatch resubscribe backoff knobs (see
        # KrakenV2BookStream.__init__'s derivation): bounds RECONNECT
        # CHURN only, never data availability - a non-positive base would
        # resubscribe at zero delay again (the exact bug this fixes), and
        # a cap below base would make the "doubling" schedule shrink.
        ck_base = float(_f(config, "websockets.kraken_checksum_backoff_base_s",
                          1.0))
        ck_cap = float(_f(config, "websockets.kraken_checksum_backoff_cap_s",
                         60.0))
        if ck_base <= 0:
            fatal(f"websockets.kraken_checksum_backoff_base_s={ck_base} must "
                  f"be > 0 - a non-positive base resubscribes at zero delay "
                  f"again, the exact churn this backoff exists to bound")
        if ck_cap < ck_base:
            fatal(f"websockets.kraken_checksum_backoff_cap_s={ck_cap} must "
                  f"be >= kraken_checksum_backoff_base_s={ck_base} - the "
                  f"doubling schedule cannot shrink")
        if ck_cap > 300.0:
            findings.append(("WARN",
                             f"websockets.kraken_checksum_backoff_cap_s="
                             f"{ck_cap} exceeds 300s - a systematic desync "
                             f"could go uncorrected for a long time"))

    # --- moomoo equities context (optional, read-only) -------------------
    # Degrades to neutral on any failure, so bad config can't stop the bot -
    # but a nonsense port/interval/weight silently yields no data forever
    # instead of failing loud, so validate it like every other feed block.
    if bool(_f(config, "moomoo.enabled", False)):
        m_port = int(_f(config, "moomoo.opend_port", 11111))
        if not (1 <= m_port <= 65535):
            fatal(f"moomoo.opend_port={m_port} is not a valid TCP port "
                  f"(1-65535)")
        m_poll = float(_f(config, "moomoo.poll_minutes", 5.0))
        if m_poll <= 0:
            fatal(f"moomoo.poll_minutes={m_poll} must be > 0")
        m_to = float(_f(config, "moomoo.connect_timeout_sec", 5.0))
        if m_to <= 0:
            fatal(f"moomoo.connect_timeout_sec={m_to} must be > 0 - a "
                  f"non-positive TCP-probe timeout never completes")
        tickers = _f(config, "moomoo.tickers", []) or []
        if not tickers:
            findings.append(("WARN",
                             "moomoo.enabled but moomoo.tickers is empty - "
                             "the basket will always be unavailable/neutral"))
        for t in tickers:
            if not isinstance(t, dict) or not t.get("code"):
                fatal(f"moomoo.tickers entry {t!r} missing a 'code'")
            elif float(t.get("weight", 1.0)) < 0:
                fatal(f"moomoo ticker {t.get('code')} has negative weight "
                      f"{t.get('weight')} - flip the basket thesis in code, "
                      f"not via a negative weight")

    # --- hedging ---------------------------------------------------------
    h_beta_floor = float(_f(config, "hedging.beta_floor", 0.1))
    h_eq_frac = float(_f(config, "hedging.max_equity_frac", 0.5))
    if not (0.0 <= h_beta_floor < 1.0):
        fatal(f"hedging.beta_floor={h_beta_floor} must be in [0, 1) - "
              f"betas at/above 1 are never 'unreliable'")
    if not (0.0 < h_eq_frac <= 1.0):
        fatal(f"hedging.max_equity_frac={h_eq_frac} must be in (0, 1] - "
              f"a single hedge larger than equity is leverage in disguise")
    # churn guards (2026-08-07 ADA churn, docs/quant/2026-08-07_ada_hedge_
    # churn_HANDOFF.md deadlock discipline rule 4: size every window against
    # the MEASURED restart cadence, median 0.5h / p90 4h)
    h_min_samp = int(_f(config, "hedging.corr_min_samples", 12))
    h_cool = float(_f(config, "hedging.rehedge_cooldown_sec", 900.0))
    h_churn_n = int(_f(config, "hedging.churn_max_unwinds", 3))
    h_churn_w = float(_f(config, "hedging.churn_window_sec", 900.0))
    if not (2 <= h_min_samp <= 1000):
        fatal(f"hedging.corr_min_samples={h_min_samp} must be in [2, 1000] - "
              f"below 2 a cold EWMA's |rho|~1 artifact gates nothing; above "
              f"1000 warmup exceeds any plausible uptime (p90 is 4h) and "
              f"re-hedging deadlocks on a healthy book")
    if not (0.0 <= h_cool <= 6 * 3600.0):
        fatal(f"hedging.rehedge_cooldown_sec={h_cool} must be in [0, 21600] - "
              f"a cooldown past 6h outlives the p90 uptime and degrades into "
              f"'hedging off until the operator notices'")
    if not (2 <= h_churn_n <= 100):
        fatal(f"hedging.churn_max_unwinds={h_churn_n} must be in [2, 100] - "
              f"1 would latch on every legitimate unwind")
    if not (60.0 <= h_churn_w <= 24 * 3600.0):
        fatal(f"hedging.churn_window_sec={h_churn_w} must be in [60, 86400]")
    if h_cool >= h_churn_w:
        fatal(f"hedging.rehedge_cooldown_sec ({h_cool}) must be BELOW "
              f"churn_window_sec ({h_churn_w}) - with the cooldown at/past "
              f"the latch window the rate-latch can never observe enough "
              f"unwinds to fire and the backstop is structurally dead")

    # --- exploration coherence: a DRY-RUN learning entry bumps p_win to
    # exploration.p_win for SIZING; if that sits at/below the net-Kelly
    # breakeven the sizer SZ-030-vetoes EVERY exploration entry and the
    # learning lane goes silent. Observed 2026-07-15: the cost-honest
    # rt_cost (maker+taker) raised the breakeven to ~0.632 while p_win stayed
    # 0.62 -> zero exploration trades, flat equity, model starved of labels.
    if bool(_f(config, "ml.exploration.enabled", False)):
        ep = float(_f(config, "ml.exploration.p_win", 0.62))
        try:
            from risk.position_sizer import payoff_ratio_from_config
            pt = config.get("pretrade", {}) or {}
            rt = (float(pt.get("maker_fee_bps", 25.0))
                  + float(pt.get("taker_fee_bps", 40.0))) / 100.0
            b_net = payoff_ratio_from_config(
                config.get("profit_taking", {}) or {},
                config.get("risk", {}) or {}, rt_cost_pct=rt)
            breakeven = 1.0 / (1.0 + b_net)
        except Exception:
            breakeven = None
        if breakeven is not None and ep <= breakeven:
            fatal(f"ml.exploration.p_win={ep:.3f} is at/below the net-Kelly "
                  f"breakeven {breakeven:.3f} (maker+taker round-trip cost) - "
                  f"every exploration entry SZ-030-vetoes and the DRY-RUN "
                  f"learning lane goes silent. Raise p_win above the breakeven.")

        # geometry-alignment T5 (spec D5): extend the probe-clearance
        # interlock to the WORST-CASE FLOORED bracket - the tightest bet
        # a bracket-sized entry can ever demand (barrier_geometry's cost
        # floor, ml.label_pt_cost_mult, pins pt/sl at their absolute
        # minimum regardless of sigma; the sizer's own worst-case
        # maker+taker rt_cost then eats the LARGEST possible share of
        # that minimum pt/sl, which is the HIGHEST possible breakeven -
        # b_net rises, never falls, as sigma grows past the floor). WARN
        # (not FATAL): a probe that only barely clears this bar risks
        # going net-thin the moment the bracket floor binds - a real
        # operational concern, but the bot still trades correctly report-
        # mode, unlike the FATAL above. COMPUTED, never hardcoded (0.614
        # at the shipped config, docs/superpowers/specs/
        # 2026-07-27-geometry-alignment-design.md spec D2's own worked
        # example: (2.0-0.65)/(1.5+0.65)=0.628 -> bar 1/1.628=0.614).
        # Only meaningful under the SAME label_mode=triple_barrier gate
        # the FATAL above requires, and only when the floor is actually
        # armed (pt_cost_mult>0, pt_vol_mult>0) - 0 disables the floor
        # (legacy bare sigma-scaling has no fixed worst case to compute).
        if lbl_mode == "triple_barrier":
            pcm = float(_f(config, "ml.label_pt_cost_mult", 0.0))
            ptm = float(_f(config, "ml.label_pt_vol_mult", 8.0))
            slm = float(_f(config, "ml.label_sl_vol_mult", 6.0))
            lbl_rt = float(_f(config, "ml.label_round_trip_cost_pct", 0.5))
            if pcm > 0.0 and ptm > 0.0:
                pt_floor_pct = pcm * lbl_rt
                sl_floor_pct = (slm / ptm) * pt_floor_pct
                sizer_rt_pct = (float(_f(config, "pretrade.maker_fee_bps",
                                        25.0))
                               + float(_f(config, "pretrade.taker_fee_bps",
                                         40.0))) / 100.0
                b_net_worst = max(
                    (pt_floor_pct - sizer_rt_pct)
                    / max(sl_floor_pct + sizer_rt_pct, 1e-9), 1e-9)
                worst_bar = 1.0 / (1.0 + b_net_worst)
                ep2 = float(_f(config, "ml.exploration.p_win", 0.62))
                clearance = ep2 - worst_bar
                if bool(_f(config, "ml.exploration.enabled", False)) \
                        and clearance < 0.005:
                    warn(f"ml.exploration.p_win={ep2:.3f} clears the "
                         f"worst-case floored-bracket breakeven "
                         f"{worst_bar:.3f} by only {clearance:.3f} "
                         f"(< 0.005) - a small config drift (fees, the "
                         f"cost floor, or p_win itself) silences probe "
                         f"admission once the bracket floor binds")

    # --- sizer entry-bar coherence: min_p_win is the EARLY p(win) gate, but the
    # net-Kelly step floors size at 0 below the breakeven (SZ-030) regardless.
    # If min_p_win sits BELOW that breakeven it is a PHANTOM bar — the headline
    # "minimum win prob" is not the effective one (the breakeven is), and every
    # signal in [min_p_win, breakeven) passes the gate only to die SZ-030 a step
    # later. WARN (not fatal — the bot trades correctly) so the configured
    # number is honest. exploration.p_win IS guarded above; min_p_win was not.
    mpw = float(_f(config, "position_sizer.min_p_win", 0.55))
    pb_mode = str(_f(config, "position_sizer.p_bar_mode", "absolute"))
    pb_margin = float(_f(config, "position_sizer.p_bar_edge_margin", 0.0))
    if pb_mode not in ("absolute", "derived"):
        fatal(f"position_sizer.p_bar_mode={pb_mode!r} must be 'absolute' or "
              f"'derived' - an unknown mode silently falls back and the "
              f"operator's intended bar is not the one running")
    if not (0.0 <= pb_margin <= 0.2):
        fatal(f"position_sizer.p_bar_edge_margin={pb_margin} must be in "
              f"[0, 0.2] - negative re-creates the phantom bar; above 0.2 "
              f"demands breakeven+20pp and no plausible model ever enters")
    try:
        from risk.position_sizer import payoff_ratio_from_config
        pt = config.get("pretrade", {}) or {}
        rt = (float(pt.get("maker_fee_bps", 25.0))
              + float(pt.get("taker_fee_bps", 40.0))) / 100.0
        be = 1.0 / (1.0 + payoff_ratio_from_config(
            config.get("profit_taking", {}) or {},
            config.get("risk", {}) or {}, rt_cost_pct=rt,
            reach_decay=float(_f(config,
                                 "position_sizer.tier_reach_decay", 0.65))))
    except Exception:
        be = None
    if pb_mode == "absolute":
        # phantom-bar honesty note applies ONLY to the absolute mode: in
        # derived mode the bar is pinned at/above the breakeven by
        # construction and min_p_win's role is the floor, not the bar.
        if be is not None and mpw < be - 1e-6:
            advisory(
                f"position_sizer.min_p_win={mpw:.3f} is below the net-Kelly "
                f"breakeven {be:.3f}, so the EFFECTIVE entry bar is {be:.3f} "
                f"(the sizer floors Kelly at 0 below it, SZ-030) - the "
                f"configured min_p_win is not the real minimum. Raise it to "
                f">= the breakeven, or switch p_bar_mode to 'derived' to pin "
                f"the bar to the geometry permanently.")
    elif be is not None:
        derived_bar = max(be + pb_margin, mpw)
        # PROBE-STRANGULATION INTERLOCK: the exploration synthetic p is the
        # F0b trickle's ticket through the bar. Geometry drift (tier/fee/stop
        # changes) that pushes the derived bar into the synthetic p kills the
        # only entry flow a distrusted model allows - the exact shape of the
        # Jul-24 drought, re-created from the bar side. Scream BEFORE it
        # binds: WARN when clearance falls under 0.005.
        exp_p = float(_f(config, "ml.exploration.p_win", 0.62))
        if exp_p < derived_bar + 0.005:
            warn(f"ml.exploration.p_win={exp_p:.3f} has less than 0.005 "
                 f"clearance over the derived entry bar {derived_bar:.4f} "
                 f"(breakeven {be:.4f} + margin {pb_margin}) - probes die at "
                 f"SZ-023 the moment geometry drift closes the gap, "
                 f"extinguishing the F0b learning trickle. Raise "
                 f"exploration.p_win or improve the payoff geometry.")
        if derived_bar > 0.90:
            warn(f"derived entry bar {derived_bar:.3f} exceeds 0.90 - the "
                 f"payoff geometry (tiers/stop/fees) is so cost-heavy that "
                 f"no plausible model clears it; fix the geometry, the bar "
                 f"is only reporting it")

    findings.extend(_conviction_checks(config))
    findings.extend(_context_checks(config))
    findings.extend(_long_book_checks(config))
    return findings


def enforce(config: dict, alerts=None) -> list:
    """Run validation; log everything; raise ConfigError on FATAL findings
    when the config is live. Dry-run downgrades FATAL to a loud warning -
    paper trading exists to catch exactly these mistakes."""
    findings = validate(config)
    dry_run = bool(_f(config, "system.dry_run", True))
    fatals = [m for s, m in findings if s == "FATAL"]
    _levels = {"FATAL": log.critical, "WARN": log.warning,
               "ADVISORY": log.info}
    for sev, msg in findings:
        _levels.get(sev, log.warning)(f"config: {msg}")
    if fatals and alerts is not None:
        alerts.fire("config_fatal", f"{len(fatals)} fatal config finding(s); "
                    f"first: {fatals[0]}")
    if fatals and not dry_run:
        raise ConfigError(
            f"{len(fatals)} fatal config finding(s) - refusing to start "
            f"live. First: {fatals[0]}")
    return findings
