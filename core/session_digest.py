"""
core/session_digest.py  -  reconciled, machine-readable run summary.

The engine already emits six telemetry streams (audit.jsonl, events.jsonl,
equity.csv, state.json, signal_history.csv, postmortem_summary.csv). They are
each faithful to their own subsystem, but they live in six shapes, disagree at
the edges, and none of them answers the one question an operator (or an agent
picking the work back up next session) actually asks first:

    did it trade, did it make money, and if not, WHY not?

This module reads those streams and produces one artifact that answers exactly
that  -  `outputs/session_digest.json` (for machines) and `.md` (for humans).
It is a strict READER: it never writes to the audit chain, never makes a
trading decision, and never raises into a caller (a broken/partial outputs dir
degrades to a partial digest, flagged as such).

Beyond summarising, it runs a set of DETECTORS that encode the failure modes
this bot has actually exhibited in paper, each with a stable SD-* id so a
recurring condition has a durable name across sessions:

  SD-001 no_activity        ran a meaningful window with zero entries/fills
  SD-002 model_starvation    model cold (0 training rows) AND retraining
                             requested repeatedly -> a loop that cannot close
  SD-003 liquidity_veto      liquidity 'spoofy' most NON-LIQUID cycles ->
                             sizing/taker suppressed feed-wide
  SD-004 audit_noise         a single reason code dominates the audit trail
  SD-005 stream_inconsistency postmortem realized% contradicts the equity/
                             portfolio ledger (fabricated-% notional artifact)
  SD-006 config_capital_stale fresh-start capital would be untradeable and/or
                             disagrees with the live account equity
  SD-007 audit_chain_break   the hash chain is broken (tamper/corruption:
                             an edited record or a dangling prev)
  SD-008 flat_equity         equity did not move across the whole window
  SD-009 feed_degraded       repeated external data-source errors
  SD-010 audit_writer_seam   hash-valid concurrent-writer fork(s) in the
                             chain (dual-runner window) - benign, nothing
                             committed altered; informational only
  SD-011 audit_fork_divergence duplicated seq numbers whose rows DISAGREE
                             (different code/hash) - a forked writer put
                             its own payload into the shared ledger, and
                             any instrument reading rows by seq/code can
                             consume the wrong branch as truth (measured
                             2026-08-29: a planted OM-080 fee reading on
                             a 62s fork was cited as venue truth for two
                             days). Data-driven: fires only on divergent
                             payloads, never on idempotent double-writes
  SD-012 era_pooling_hazard  rows stamped with MORE THAN ONE execution era
                             (`exec_era`) sit in one file. CLAUDE.md's
                             accrual moratorium forbids pooling across the
                             cut-#9 fee correction; the digest names the
                             per-era counts so a reader segments before it
                             averages. Standing condition on a lifetime
                             ledger - informational to the era, WARN to the
                             reader

SD-000 is emitted when nothing fired. Severities: "info" | "warn" | "error".
These ids are report diagnostics, not audit dispositions, so they live here as
documented constants rather than in core/codes.py (which governs the chain).
"""

import csv
import json
import logging
import re
import time
from collections import Counter
from pathlib import Path

from core.sanitize import safe_float as _f

log = logging.getLogger("liquiditybot.core.session_digest")

# --- detector ids (append-only; never renumber) ---------------------------
SD_OK = "SD-000"
SD_NO_ACTIVITY = "SD-001"
SD_MODEL_STARVATION = "SD-002"
SD_LIQUIDITY_VETO = "SD-003"
SD_AUDIT_NOISE = "SD-004"
SD_STREAM_INCONSISTENCY = "SD-005"
SD_CONFIG_CAPITAL_STALE = "SD-006"
SD_AUDIT_CHAIN_BREAK = "SD-007"
SD_FLAT_EQUITY = "SD-008"
SD_FEED_DEGRADED = "SD-009"
SD_AUDIT_WRITER_SEAM = "SD-010"
SD_FORK_DIVERGENCE = "SD-011"
SD_ERA_POOLING_HAZARD = "SD-012"

# exec_era bucket names for rows that carry NO stamp (mirrors the three-way
# classification scripts/cohort_eval.py applies to the same column):
#   csv.DictReader restval None -> the writer's COLS predate the stamp
#   ""                          -> stamp-aware writer, pre-stamp row
ERA_ABSENT = "absent(stale-binary)"
ERA_PRESTAMP = "prestamp"

_LIQ_RE = re.compile(r"liquidity=(\w+)")
_ASSET_RE = re.compile(r"^\[(\w+)\]")

# SD-004 dominance is meant to catch a code BURYING others unexpectedly -
# not a code that is high-frequency BY DESIGN. ML-070 (dry-run active-
# learning exploration entries, see main.py._exploration_active) fires
# probabilistically every cycle by construction until explore_until_rows
# is reached, so it dominating early sessions is expected, not a fault.
# SZ-051/SZ-052 are the SPB-R probe-budget accounting pair (priced /
# refunded), documented "informational" in core/codes.py and attached
# beside every probe by construction - one probe, one or two records -
# so while exploration runs they dominate exactly as ML-070 does
# (measured 2026-08-18: SZ-051 41% of the 48h non-routine tally on a
# healthy run). Excluded from the dominance calculation only; still
# counted in `records` and still fully present in `top_codes`, so
# nothing is hidden from the raw breakdown - only the false-positive
# WARN is suppressed.
_ROUTINE_NOISE_CODES = {"ML-070", "SZ-051", "SZ-052"}


def _read_jsonl(path: Path) -> list:
    out = []
    if not path.exists():
        return out
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return out


def _read_csv(path: Path) -> list:
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8", newline="") as f:
            # DROP MALFORMED ROWS. A torn final append (a crash mid-write on a
            # live CSV) leaves a fragment that DictReader returns as a normal
            # dict with restval=None for the missing tail — so "1786000000,98"
            # parsed as a real equity sample and reported equity_min 98.0 on a
            # ~$800 book, and a truncated epoch like "17860" put the window
            # start in 1970 with duration_h in the hundreds of thousands.
            # A short row is not a small observation; it is half an
            # observation, and averaging it in is worse than dropping it.
            #   None in r          -> restkey: the row had EXTRA fields
            #   None in r.values() -> restval: the row was SHORT
            return [r for r in csv.DictReader(f)
                    if None not in r and None not in r.values()]
    except OSError:
        return []


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        val = json.loads(path.read_text(encoding="utf-8"))
        return val if isinstance(val, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


# --------------------------------------------------------------------------
def _audit_counts(records: list) -> dict:
    """Counter-derived audit fields, computable on ANY record slice (whole
    window or the recent lens). Chain fields live only in _audit_section:
    integrity is a whole-file property, never a windowed one."""
    codes = Counter(r.get("code") for r in records)
    srcs = Counter(r.get("src") for r in records)
    # dominance is computed on non-routine codes only (see
    # _ROUTINE_NOISE_CODES) so expected-high-frequency background codes
    # can't false-positive SD-004; top_codes/records below stay unfiltered
    signal_codes = Counter({c: n for c, n in codes.items()
                            if c not in _ROUTINE_NOISE_CODES})
    signal_total = sum(signal_codes.values())
    top_code, top_n = (signal_codes.most_common(1)[0]
                       if signal_codes else (None, 0))
    return {
        "records": len(records),
        "signal_records": signal_total,
        "by_src": dict(srcs.most_common()),
        "top_codes": codes.most_common(12),
        "dominant_code": top_code,
        "dominant_frac": round(top_n / signal_total, 3) if signal_total else 0.0,
        "retrain_requests": codes.get("ML-032", 0),
        "kill_switch_events": codes.get("ML-050", 0),
    }


def _audit_section(records: list, outputs: Path) -> dict:
    # chain integrity via the real verifier — and it MUST be verify_chain().
    # Constructing an AuditTrail is a WRITE: its _adopt_tail heals a torn tail
    # by truncating it and appending a newline. This digest runs hourly from
    # scripts/checkin.py against the LIVE outputs/audit.jsonl, so the previous
    # `AuditTrail(...).verify()` could DELETE a just-appended record mid-write
    # and latch tamper=True permanently — evidence destruction from a module
    # whose own docstring promises it "never writes to the audit chain".
    # verify_chain is read-only by contract; scripts/session_import.py:176
    # already uses it for exactly this reason.
    chain = {"ok": None}
    try:
        from core.audit import verify_chain
        chain = verify_chain(str(outputs / "audit.jsonl"))
    except Exception:  # pragma: no cover - verifier must never break the digest
        chain = {"ok": None, "error": "verifier unavailable"}
    out = _audit_counts(records)
    out.update({
        "chain_ok": chain.get("ok"),
        "chain_first_break": chain.get("first_break"),
        "chain_tamper": chain.get("tamper"),
        "chain_seams": chain.get("seams", 0),
        # additive passthroughs so the headline can name the two states that
        # are neither OK nor tamper: a benign torn tail, and a file the
        # verifier could not read at all (verify_chain reports the latter as
        # tamper=True; "the stream is missing" and "a record was edited" are
        # different operator actions and deserve different words)
        "chain_torn_tail": chain.get("torn_tail", False),
        "chain_error": chain.get("error"),
    })
    # Fork-payload legibility (AUDIT-SEAM-0829, 2026-09-01). verify_chain
    # counts hash-valid writer seams; these additive keys name WHAT rode
    # them, because "10 seams, benign" gave an operator no way to find the
    # one forked row (a planted OM-080 fee reading) that downstream
    # instruments then consumed as venue truth. Divergence is data-driven:
    # a seq is divergent only when its rows DISAGREE on (code, h) - an
    # idempotent double-write of the same record stays SD-010-benign.
    seq_rows: dict = {}
    for r in records:
        s = r.get("seq")
        if s is not None:
            seq_rows.setdefault(s, []).append(r)
    dup = {s: rs for s, rs in seq_rows.items() if len(rs) > 1}
    divergent = {s: rs for s, rs in dup.items()
                 if len({(x.get("code"), x.get("h")) for x in rs}) > 1}
    div_codes = Counter(str(x.get("code")) for rs in divergent.values()
                        for x in rs)
    out.update({
        "dup_seqs": len(dup),
        "fork_divergent_seqs": len(divergent),
        # COMPLETE code histogram, deliberately uncapped: a top-N cut hid
        # the motivating case on its first live run (the planted OM-080,
        # count 1, fell below an 8-code cutoff - the exact row this
        # instrument exists to surface). Bounded by distinct codes riding
        # forks, which is small by construction.
        "fork_codes": dict(div_codes.most_common()),
        "fork_examples": [
            {"seq": s,
             "codes": sorted({str(x.get("code")) for x in rs}),
             "ts": sorted(round(_f(x.get("ts"), 0.0), 3) for x in rs)[:3]}
            for s, rs in sorted(divergent.items())[:5]],
    })
    return out


def _events_section(records: list) -> dict:
    levels = Counter(e.get("level") for e in records)
    warn_err = Counter(
        e.get("msg", "")[:140] for e in records
        if e.get("level") in ("WARNING", "ERROR", "CRITICAL"))
    # liquidity classification tally across cycles
    liq = Counter()
    per_asset_cycles = Counter()
    for e in records:
        msg = e.get("msg", "")
        m = _LIQ_RE.search(msg)
        if m:
            liq[m.group(1)] += 1
            a = _ASSET_RE.match(msg)
            per_asset_cycles[a.group(1) if a else "?"] += 1
    liq_total = sum(liq.values())
    spoofy = liq.get("spoofy", 0)
    # external-feed failures (data degraded, not a trading fault)
    feed_errors = sum(c for m, c in warn_err.items()
                      if "unavailable" in m.lower() or "request failed" in m.lower()
                      or "httperror" in m.lower())
    return {
        "records": len(records),
        "by_level": dict(levels.most_common()),
        "top_warnings": warn_err.most_common(10),
        "liquidity_tally": dict(liq.most_common()),
        # DENOMINATOR (2026-08-27): liquidity_regime logs the liquidity=
        # line ONLY when label != "liquid" (liquidity_regime.py:358), so
        # this is the spoofy share of NON-LIQUID (degraded) cycles, not of
        # all cycles. A 54% here is compatible with 1/12 assets spoofy in
        # the same status snapshot — which is exactly how it misread a
        # session on 2026-08-27. Key name kept for consumers; the lens key
        # and every rendered string now say what the denominator is.
        "spoofy_frac": round(spoofy / liq_total, 3) if liq_total else 0.0,
        "liq_lens": "non_liquid_cycles_only",
        "cycles_estimate": max(per_asset_cycles.values()) if per_asset_cycles else 0,
        "feed_error_events": feed_errors,
    }


# A capital reset (scripts/reset_paper_capital.py) is a step discontinuity,
# not a market move: consecutive equity samples arrive seconds apart, so a
# jump of half the book between two of them is an operator action. Measured
# on the live ledger 2026-08-23: the four real resets moved -83%, +530%,
# +301% and -99% sample-to-sample, while the worst transient bad read moved
# 0.8%. The threshold sits between those populations with an order of
# magnitude of clearance on each side.
_EPOCH_JUMP_FRAC = 0.5


def _pnl_section(portfolio: dict, equity_rows: list) -> dict:
    """Equity stats on the CURRENT CAPITAL EPOCH, with lifetime kept aside.

    The whole-file read this replaces produced the digest's worst false
    alarm: "$25,000 -> $803.87 (range $99,208.70)" — a 97% wipeout headline
    over a series that actually contains four paper-capital resets and a
    current epoch quietly holding +0.3%. Same instrument-lens disease the
    recent-hours windowing fixed for the audit counts (a lens spanning the
    whole run reports cured history as current state); this is the equity
    row's turn.

    The `equity_*` keys now describe the slice after the LAST reset — the
    only span over which start/min/max/range are statements about one book.
    Lifetime extremes stay available under `lifetime_*`, labelled as what
    they are. SD-008 (flat equity) inherits the epoch lens for free, which
    also un-breaks it: on the lifetime lens a post-reset flatline could
    never fire, because the range was permanently inflated by history.
    """
    eq_vals = [_f(r.get("equity")) for r in equity_rows if r.get("equity")]
    life_start = eq_vals[0] if eq_vals else _f(portfolio.get("starting_capital"))
    life_lo, life_hi = ((min(eq_vals), max(eq_vals)) if eq_vals
                        else (life_start, life_start))
    # last reset = last consecutive pair jumping more than the threshold
    epoch_first = 0
    for i in range(1, len(eq_vals)):
        prev = eq_vals[i - 1]
        if prev > 0 and abs(eq_vals[i] - prev) / prev > _EPOCH_JUMP_FRAC:
            epoch_first = i
    epoch = eq_vals[epoch_first:]
    epochs = 1 + sum(
        1 for i in range(1, len(eq_vals))
        if eq_vals[i - 1] > 0
        and abs(eq_vals[i] - eq_vals[i - 1]) / eq_vals[i - 1] > _EPOCH_JUMP_FRAC)
    start = epoch[0] if epoch else life_start
    end = epoch[-1] if epoch else start
    lo, hi = (min(epoch), max(epoch)) if epoch else (start, end)
    return {
        "starting_capital": _f(portfolio.get("starting_capital")),
        "equity_start": round(start, 2),
        "equity_end": round(end, 2),
        "equity_min": round(lo, 2),
        "equity_max": round(hi, 2),
        "equity_range": round(hi - lo, 2),
        "capital_epochs": epochs,
        "epoch_samples": len(epoch),
        "lifetime_equity_start": round(life_start, 2),
        "lifetime_equity_min": round(life_lo, 2),
        "lifetime_equity_max": round(life_hi, 2),
        "lifetime_equity_range": round(life_hi - life_lo, 2),
        # NETTING (2026-08-27): the runner's realized accumulator is net of
        # the CLOSING fee leg only (runner.py, _record_realized) while
        # fees_paid_total carries BOTH legs. Ratioing these two lines
        # double-counts the close leg — a "fees 1.7x realized" was misread
        # from exactly this juxtaposition on 2026-08-27. Keys unchanged;
        # the rendered labels now carry the netting.
        "realized_pnl_total": round(_f(portfolio.get("realized_pnl_total")), 2),
        "fees_paid_total": round(_f(portfolio.get("fees_paid_total")), 4),
        "open_positions": len(portfolio.get("positions") or []),
        "samples": len(eq_vals),
    }


def _window(audit: list, events: list, equity_rows: list) -> dict:
    ts = [r.get("ts") for r in audit if isinstance(r.get("ts"), (int, float))]
    ts += [e.get("ts") for e in events if isinstance(e.get("ts"), (int, float))]
    ts += [_f(r.get("ts")) for r in equity_rows if r.get("ts")]
    ts = [t for t in ts if t]
    if not ts:
        return {"start": None, "end": None, "duration_h": 0.0}
    return {"start": min(ts), "end": max(ts),
            "duration_h": round((max(ts) - min(ts)) / 3600.0, 2)}


# --------------------------------------------------------------------------
def _detectors(digest: dict, config: dict) -> list:
    """Encode the failure modes this bot has actually shown. Returns a list
    of {id, severity, title, detail} ordered most-severe first."""
    out = []
    pnl = digest["pnl"]
    aud = digest["audit"]
    evt = digest["events"]
    model = digest["model"]
    win = digest["window"]
    dur = win.get("duration_h") or 0.0

    def add(sd, sev, title, detail):
        out.append({"id": sd, "severity": sev, "title": title, "detail": detail})

    # SD-007 chain break (most severe: integrity) - TAMPER only: an edited
    # record or a dangling prev. Benign anomalies (writer seams) must not
    # fire the alarm every session or the operator learns to ignore it.
    if aud.get("chain_tamper"):
        add(SD_AUDIT_CHAIN_BREAK, "error", "audit chain broken",
            f"hash chain first breaks at record {aud.get('chain_first_break')}"
            "  -  a record was edited or removed (own-hash mismatch or "
            "dangling prev) past that point")
    # SD-010 writer seam(s): hash-valid concurrent-writer fork(s), benign
    # (dual-runner window; nothing committed altered). Informational so the
    # condition keeps a durable name without desensitizing SD-007.
    elif aud.get("chain_seams"):
        add(SD_AUDIT_WRITER_SEAM, "info", "audit writer seam(s)",
            f"{aud.get('chain_seams')} hash-valid concurrent-writer fork(s) "
            "in the chain - benign (no committed record altered); "
            "prevention: runner instance lock + one-bot mode")
    # SD-011 fork divergence: fires INDEPENDENTLY of (and usually alongside)
    # SD-010 - the seam itself is benign, but rows that share a seq while
    # DISAGREEING on payload mean a forked writer put its own data into the
    # shared ledger, and any consumer selecting rows by seq/code can read
    # the wrong branch as truth. Warn, not error: the chain itself is
    # intact; it is the READERS that are at risk (measured 2026-08-29: a
    # 62-second fork's planted OM-080 was cited as a venue fee reading for
    # two days before operator testimony overturned it).
    if aud.get("fork_divergent_seqs"):
        _fc = aud.get("fork_codes") or {}
        _ex = aud.get("fork_examples") or []
        add(SD_FORK_DIVERGENCE, "warn",
            "audit fork carries divergent payloads",
            f"{aud['fork_divergent_seqs']} duplicated seq(s) whose rows "
            f"disagree on (code, hash) - codes riding forks: {_fc}; "
            f"first examples: {_ex[:3]}. Instruments consuming audit rows "
            "must not treat forked-seq rows as unique venue truth; find "
            "the writer (an unredirected script/harness - configure_audit "
            "exists for exactly this) and quarantine, never delete")

    # SD-012 era pooling hazard: more than one execution era's rows share
    # one file. Whole-window by nature (a ledger is one file). The detail
    # carries the per-era counts and the source they were counted on, so
    # the operator segments BEFORE averaging; CLAUDE.md's moratorium
    # forbids pooling across the cut-#9 fee correction.
    eras = digest.get("eras") or {}
    if eras.get("pooling_hazard"):
        _src = eras.get("pooling_hazard_source")
        _counts = (eras.get("rows_per_era")
                   if _src == "signal_history.exec_era"
                   else eras.get("fills_per_era")) or {}
        _sig_stamp = ("present"
                      if "unavailable" not in (eras.get("rows_per_era") or {})
                      else "ABSENT - segment by ts against the boundary table")
        add(SD_ERA_POOLING_HAZARD, "warn",
            "rows from more than one execution era share one file",
            f"{len([k for k, n in _counts.items() if n > 0])} exec_era keys "
            f"on {_src}: {_counts}; current era {eras.get('current_era')}. "
            "Do NOT pool across eras (CLAUDE.md accrual moratorium) - any "
            "statistic over this file must segment by exec_era first "
            f"(signal_history.csv exec_era: {_sig_stamp})")

    # SD-005 stream inconsistency: a postmortem realized% that its OWN excursion
    # columns contradict. A position that never moved adverse (MAE ~ 0) cannot
    # realize a multi-percent loss -> the % is a scaling artifact (entry_usd ~ 0
    # divided into a sub-dollar PnL), not a market outcome. Internal check, so
    # it holds regardless of the equity ledger.
    pm = digest["postmortems"]
    if pm["impossible_count"]:
        add(SD_STREAM_INCONSISTENCY, "error",
            "postmortem realized% contradicts its own excursions",
            f"{pm['impossible_count']} of {pm['count']} postmortem(s) report a "
            f"realized loss (worst {pm['worst_realized_pct']:.1f}%) while max "
            "adverse excursion was ~0% - impossible for a real fill. The % is "
            "fabricated from a ~$0 notional (ml/postmortem.py entry_usd guard); "
            "do NOT let ml/monitor.py train or auto-adjust on these causes")

    # STATE-LIKE detectors (SD-002/003/004) read the RECENT lens, not the
    # whole run. Measured 2026-08-18: the whole-window lens re-flagged three
    # CURED conditions every session (SD-002 "cold" while the live model was
    # trained and improving; SD-003 spoofy 68% and SD-004 SZ-047 63% — both
    # ZERO in the trailing 48h) — a digest that keeps describing history
    # teaches the operator to ignore it. Integrity/accounting detectors
    # (SD-005/006/007/010) stay whole-window: a broken chain or fabricated
    # postmortem anywhere in the run is always reportable.
    rec = digest.get("recent") or {}
    rec_aud = rec.get("audit") or aud
    rec_evt = rec.get("events") or evt
    rec_h = rec.get("hours")
    lens = f"last {rec_h:.0f}h" if rec_h else "whole window"

    # SD-002 model starvation loop
    if model["cold"] and rec_aud.get("retrain_requests", 0) >= 5:
        add(SD_MODEL_STARVATION, "warn", "model starvation loop",
            f"model is cold (live training rows={model['history_rows']}, "
            f"brier={model['brier']}) yet retrain was requested "
            f"{rec_aud['retrain_requests']}x ({lens})  -  with 0 entries there "
            "is no new data, so retraining can never clear the condition. "
            "Seed a model (scripts/train_meta.py) or supply history")

    # SD-003 liquidity veto feed-wide
    if rec_evt.get("spoofy_frac", 0.0) >= 0.5 \
            and rec_evt.get("cycles_estimate", 0) >= 10:
        add(SD_LIQUIDITY_VETO, "warn", "liquidity vetoed feed-wide",
            f"liquidity classified 'spoofy' on {rec_evt['spoofy_frac']:.0%} of "
            f"NON-LIQUID cycles ({lens}; liquid cycles are unlogged, so this "
            "is a share of degraded cycles, not of all cycles - cross-check "
            "status regimes for absolute prevalence). Spoofy suppresses "
            "sizing/taker on the affected asset. On a near-zero-spread feed "
            "this is likely a classifier miscalibration, not real spoofing "
            " -  inspect the book source")

    # SD-004 audit noise (routine background codes excluded - see
    # _ROUTINE_NOISE_CODES; this now only fires on non-routine dominance)
    if rec_aud.get("dominant_frac", 0) >= 0.30 \
            and rec_aud.get("signal_records", 0) >= 50:
        add(SD_AUDIT_NOISE, "warn", "audit trail dominated by one code",
            f"{rec_aud['dominant_code']} is {rec_aud['dominant_frac']:.0%} of "
            f"{rec_aud['signal_records']} non-routine records ({lens})  -  "
            "consequential dispositions are buried; rate-limit that emitter")

    # SD-001 no activity
    traded = pnl["open_positions"] or model["history_rows"] or pm["count"] \
        or abs(pnl["realized_pnl_total"]) >= 0.01
    if dur >= 1.0 and not traded:
        add(SD_NO_ACTIVITY, "info", "no trading activity",
            f"{dur:.1f}h window with 0 entries, 0 open positions and no "
            "realized PnL")

    # SD-008 flat equity
    if pnl["samples"] >= 10 and pnl["equity_range"] < 0.01:
        add(SD_FLAT_EQUITY, "info", "equity did not move",
            f"equity held ${pnl['equity_end']:.2f} across {pnl['samples']} "
            "samples  -  no open inventory marked to market the whole window")

    # SD-006 config capital staleness / fresh-start untradeability
    cap = config.get("capital_management", {}) if isinstance(config, dict) else {}
    ps = config.get("position_sizer", {}) if isinstance(config, dict) else {}
    pt = config.get("pretrade", {}) if isinstance(config, dict) else {}
    start_cap = _f(cap.get("starting_capital_usd"))
    max_pos = _f(cap.get("max_position_size_pct_of_capital"), 10.0)
    min_ticket = max(_f(ps.get("min_ticket_usd"), 25.0), _f(pt.get("min_order_usd"), 25.0))
    if start_cap > 0:
        fresh_max = start_cap * max_pos / 100.0
        live = pnl["equity_end"]
        if fresh_max < min_ticket:
            add(SD_CONFIG_CAPITAL_STALE, "info",
                "config capital is fresh-start untradeable",
                f"starting_capital_usd=${start_cap:,.0f} x {max_pos:.0f}% = "
                f"${fresh_max:,.0f} < ${min_ticket:,.0f} min ticket: a FRESH "
                f"start cannot trade. This run used a restored equity of "
                f"${live:,.0f}, so it was not the binding constraint here  -  but "
                "reconcile config vs the live account so a cold start behaves")

    if not out:
        add(SD_OK, "info", "no anomalies detected", "all detectors passed")
    sev_rank = {"error": 0, "warn": 1, "info": 2}
    out.sort(key=lambda d: sev_rank.get(d["severity"], 3))
    return out


def _model_section(state: dict, history_rows: int) -> dict:
    mon = state.get("monitor", {}) if isinstance(state, dict) else {}
    brier = mon.get("brier")
    # "cold" = NO trained model. A live judge brier of n/a only means the
    # judge's recent-close window is thin; a present champion_brier proves a
    # trained champion is deployed. The old definition (judge-brier n/a alone
    # = cold) called a trained, improving model "cold" every session
    # (measured 2026-08-18: SD-002 fired at 333 live rows, champion 0.169).
    champion = mon.get("champion_brier")
    has_champion = isinstance(champion, (int, float)) and champion > 0
    cold = (history_rows == 0) or (brier in (None, "n/a") and not has_champion)
    return {
        "monitor_level": mon.get("level"),
        "use_model": mon.get("use_model"),
        "kelly_mult": mon.get("kelly_mult"),
        "champion_brier": mon.get("champion_brier"),
        "brier": brier if brier is not None else "n/a",
        "history_rows": history_rows,
        "cold": bool(cold),
    }


def _postmortem_section(rows: list) -> dict:
    realized = [_f(r.get("realized_pct")) for r in rows if r.get("realized_pct")]
    causes = Counter(r.get("cause") for r in rows)
    # a realized loss the excursion columns cannot explain: MAE ~ 0 means price
    # never went against the fill, so a multi-percent realized loss is an
    # accounting artifact, not a market outcome.
    impossible = sum(
        1 for r in rows
        if _f(r.get("realized_pct")) <= -5.0 and _f(r.get("mae_pct")) >= -1.0)
    return {
        "count": len(rows),
        "causes": dict(causes.most_common()),
        "worst_realized_pct": round(min(realized), 3) if realized else 0.0,
        "impossible_count": impossible,
    }


def _csv_header(path: Path) -> list:
    """Column names of a CSV, from its first line only (never the body)."""
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return next(csv.reader(f), [])
    except (OSError, csv.Error):
        return []


def _iso(t: float) -> "str | None":
    """ISO-8601 UTC, or None when the epoch is outside the platform's
    range (Windows gmtime raises OSError on a millisecond epoch - the
    unit-mixing class the data-quality audit measured; a reader must never
    take the digest down over one bad cell)."""
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
    except (OverflowError, OSError, ValueError):
        return None


def _era_bucket(val) -> str:
    """exec_era cell -> era key. None (missing trailing field) and "" are
    distinct pre-stamp populations and stay distinct keys."""
    if val is None:
        return ERA_ABSENT
    s = str(val).strip()
    return s if s else ERA_PRESTAMP


def _eras_section(sig_rows: list, outputs: Path) -> dict:
    """Execution-era provenance of the corpus in `outputs` (2026-08-31,
    operator-authorized). Pure reader; every branch degrades to a value.

    `current_era` is the CODE constant every fill written by this binary
    carries (core/fill_ledger.EXEC_ERA) - the stamp is in code, not in any
    status/config file (measured 2026-09-01: zero `exec_era` keys in
    status.json, state.json, config.json).

    `rows_per_era` counts signal_history.csv rows by `exec_era` IF that
    column exists. Measured 2026-09-01 it does NOT (95-column schema; the
    only era column there is `label_era`, the LABEL-definition axis of
    ml/history.py:label_era_of, a different thing) - so the key reports
    `{"unavailable": <reason>}` rather than an empty dict a reader would
    mistake for "one era". `rows_per_label_era` carries that other axis
    under its own name so the two are never confused.

    `fills_per_era` is the same count over outputs/fills.csv, the ONE
    on-disk stream that carries the execution stamp (core/fill_ledger.COLS,
    last column). Streamed row by row; never loaded whole. Rows with the
    stamp field MISSING (a stale binary's COLS) and rows with it BLANK
    (stamp-aware writer, pre-stamp row) are kept as distinct buckets, the
    three-way rule scripts/cohort_eval.py applies to the same column.

    `pooling_hazard` is True when the era source in use holds >1 era key
    with count>0: rows from different execution eras share one file, and
    CLAUDE.md forbids pooling across the fee correction. The source is
    named (`pooling_hazard_source`) so the bool is never read as a claim
    about a file it did not measure. signal_history's stamp is preferred
    when it exists; fills.csv is the fallback; neither -> False + None.

    The span keys (`corpus_first_ts` / `corpus_last_ts` / `corpus_rows`)
    come from `signal_ts` (the corpus' own signal-time anchor;
    ml/history.py sorts on it) over the rows already loaded - one pass,
    no second read of the MB-scale file. They describe EVERY ROW ON DISK
    and are therefore the RAW file span, NOT the span the champion is
    scored on: the production loader drops rows by era exclusion and by
    `label_era`, so the trained span is strictly shorter (measured
    2026-09-01: 50.33d raw vs 23.73d trained, a 2.1x gap). Anything that
    divides by a span - MinBTL, the standard error of an annualized
    Sharpe - must use the TRAINED one from
    scripts/champion_skill_report.py --json (`corpus_span_days`). The
    rendered line says so; do not shorten it to "corpus span".
    """
    out: dict = {
        "current_era": None,
        "era_source": "core.fill_ledger.EXEC_ERA",
        "rows_per_era": {"unavailable": "signal_history.csv not present"},
        "rows_per_label_era": {},
        "fills_rows": 0,
        "fills_torn_rows": 0,
        "fills_per_era": {},
        "pooling_hazard": False,
        "pooling_hazard_source": None,
        "corpus_rows": len(sig_rows),
        "corpus_first_ts": None,
        "corpus_last_ts": None,
        "corpus_span_days": None,
        "signal_ts_missing": 0,
    }
    try:
        from core.fill_ledger import EXEC_ERA
        out["current_era"] = str(EXEC_ERA)
    except Exception:  # pragma: no cover - a missing stamp must not break the digest
        out["current_era"] = None

    # --- signal_history.csv: era columns + calendar span ------------------
    sig_path = outputs / "signal_history.csv"
    header = _csv_header(sig_path)
    if header:
        if "exec_era" in header:
            out["rows_per_era"] = dict(Counter(
                _era_bucket(r.get("exec_era")) for r in sig_rows).most_common())
        else:
            out["rows_per_era"] = {
                "unavailable": f"signal_history.csv has no exec_era column "
                               f"({len(header)} columns; label_era present="
                               f"{'label_era' in header}, a label-definition "
                               f"axis, not the execution era)"}
        if "label_era" in header:
            out["rows_per_label_era"] = dict(Counter(
                (r.get("label_era") or "").strip() or "blank"
                for r in sig_rows).most_common())
    lo = hi = None
    missing = 0
    for r in sig_rows:
        raw = r.get("signal_ts")
        t = _f(raw, 0.0) if raw not in (None, "") else 0.0
        if t <= 0.0:
            missing += 1
            continue
        lo = t if lo is None else min(lo, t)
        hi = t if hi is None else max(hi, t)
    out["signal_ts_missing"] = missing
    if lo is not None and hi is not None:
        out["corpus_first_ts"] = _iso(lo)
        out["corpus_last_ts"] = _iso(hi)
        out["corpus_span_days"] = round((hi - lo) / 86400.0, 2)

    # --- fills.csv: the stream that actually carries the stamp -----------
    fills_path = outputs / "fills.csv"
    per_era: Counter = Counter()
    n_fills = torn = 0
    if fills_path.exists():
        try:
            with open(fills_path, encoding="utf-8", newline="") as f:
                rdr = csv.DictReader(f)
                if rdr.fieldnames and "exec_era" in rdr.fieldnames:
                    for r in rdr:
                        # a row short in ANY field but exec_era is a torn
                        # append (live file, crash mid-write) - half an
                        # observation, dropped and counted, same rule as
                        # _read_csv. Short in exec_era ONLY = a stale
                        # binary's 16-column COLS = the ABSENT bucket.
                        if any(v is None for k, v in r.items()
                               if k != "exec_era"):
                            torn += 1
                            continue
                        n_fills += 1
                        per_era[_era_bucket(r.get("exec_era"))] += 1
                else:
                    for _ in rdr:
                        n_fills += 1
                    per_era[ERA_ABSENT] = n_fills
        except (OSError, csv.Error):
            per_era = Counter()
            n_fills = 0
    out["fills_rows"] = n_fills
    out["fills_torn_rows"] = torn
    out["fills_per_era"] = dict(per_era.most_common())

    # --- pooling hazard: >1 era key with rows, on the named source --------
    rpe = out["rows_per_era"]
    if "unavailable" not in rpe:
        src, counts = "signal_history.exec_era", rpe
    elif per_era:
        src, counts = "fills.exec_era", out["fills_per_era"]
    else:
        src, counts = None, {}
    live_keys = [k for k, n in counts.items()
                 if isinstance(n, int) and n > 0]
    out["pooling_hazard"] = len(live_keys) > 1
    out["pooling_hazard_source"] = src
    return out


def build_digest(outputs_dir: "str | Path" = "outputs",
                 config: dict | None = None,
                 recent_hours: float = 48.0) -> dict:
    """Read every telemetry stream under `outputs_dir` and return one
    reconciled digest dict. Never raises; missing streams degrade to zeros.

    `recent_hours` sizes the RECENT lens the state-like detectors
    (SD-002/003/004) read; the whole-window sections are unchanged and the
    cut anchors to the DATA's window end (not wall clock), so an imported or
    replayed outputs dir windows against its own timeline. <=0 disables the
    lens (detectors fall back to whole-window, the pre-2026-08-18 behavior)."""
    o = Path(outputs_dir)
    audit = _read_jsonl(o / "audit.jsonl")
    events = _read_jsonl(o / "events.jsonl")
    equity_rows = _read_csv(o / "equity.csv")
    state = _read_json(o / "state.json")
    sig_rows = _read_csv(o / "signal_history.csv")
    pm_rows = _read_csv(o / "postmortem_summary.csv")
    portfolio = state.get("portfolio", {}) if isinstance(state, dict) else {}

    win = _window(audit, events, equity_rows)
    recent: dict = {}
    if recent_hours > 0 and win.get("end"):
        cut = float(win["end"]) - recent_hours * 3600.0
        r_audit = [r for r in audit
                   if isinstance(r.get("ts"), (int, float)) and r["ts"] >= cut]
        r_events = [e for e in events
                    if isinstance(e.get("ts"), (int, float)) and e["ts"] >= cut]
        recent = {"hours": recent_hours,
                  "audit": _audit_counts(r_audit),
                  "events": _events_section(r_events)}

    live_rows = sum(1 for r in sig_rows if r.get("source") == "live")
    digest = {
        "generated_at": time.time(),
        "outputs_dir": str(o),
        "window": win,
        "recent": recent,
        "pnl": _pnl_section(portfolio, equity_rows),
        "activity": {
            "signal_rows_total": len(sig_rows),
            "live_labeled_trades": live_rows,
            "candidate_rows": sum(1 for r in sig_rows
                                  if r.get("source") == "candidate"),
        },
        "audit": _audit_section(audit, o),
        "events": _events_section(events),
        "model": _model_section(state, live_rows),
        "postmortems": _postmortem_section(pm_rows),
        "eras": _eras_section(sig_rows, o),
        "streams_present": {
            "audit.jsonl": bool(audit), "events.jsonl": bool(events),
            "equity.csv": bool(equity_rows), "state.json": bool(state),
            "signal_history.csv": bool(sig_rows),
            "postmortem_summary.csv": bool(pm_rows),
            "fills.csv": (o / "fills.csv").exists(),
        },
    }
    digest["diagnostics"] = _detectors(digest, config or {})
    worst = digest["diagnostics"][0] if digest["diagnostics"] else {}
    digest["verdict"] = f"{worst.get('id', SD_OK)} {worst.get('title', 'ok')}"
    return digest


def _chain_word(aud: dict) -> str:
    """One word the operator can trust at a glance — display only, the JSON
    keys (`chain_ok`/`chain_tamper`/`chain_seams`) are untouched and
    scripts/checkin.py keeps reading those.

    The old headline printed `chain_ok=False (tamper=False, seams=8)` at the
    top of every digest for a condition the SAME report classifies as benign
    eight lines later (SD-010). A field that reads as an alarm every day is
    unreadable on the one day it matters; SD-007's own comment makes exactly
    this argument for the detector, and the headline was undoing it.

      UNREADABLE(err)        the file could not be opened at all
      TAMPER(first_break=N)  an edited/removed record — the real alarm
      OK                     clean verify
      SEAMS(n, benign)       hash-valid concurrent-writer fork(s) only
      TORN_TAIL(...)         crashed final append, nothing valid after
      UNVERIFIED             verifier unavailable
    """
    if aud.get("chain_error"):
        return f"UNREADABLE({aud['chain_error']})"
    if aud.get("chain_tamper"):
        return f"TAMPER(first_break={aud.get('chain_first_break')})"
    if aud.get("chain_ok"):
        return "OK"
    if aud.get("chain_seams"):
        return f"SEAMS({aud['chain_seams']}, benign)"
    if aud.get("chain_torn_tail"):
        return "TORN_TAIL(benign crash-append)"
    return "UNVERIFIED"


def render_markdown(d: dict) -> str:
    pnl, aud, evt, mdl = d["pnl"], d["audit"], d["events"], d["model"]
    win = d["window"]

    def _ts(t):
        return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(t)) if t else "n/a"

    lines = [
        "# Session digest",
        "",
        f"**Verdict: {d['verdict']}**",
        "",
        f"- Window: {_ts(win['start'])} -> {_ts(win['end'])} "
        f"({win['duration_h']}h, ~{evt['cycles_estimate']} cycles)",
        f"- Equity (current capital epoch): ${pnl['equity_start']:,.2f} -> "
        f"${pnl['equity_end']:,.2f} (range ${pnl['equity_range']:,.2f})"
        + (f" | {pnl['capital_epochs']} epochs lifetime, range "
           f"${pnl['lifetime_equity_range']:,.2f}"
           if pnl.get('capital_epochs', 1) > 1 else "")
        + f" | realized PnL (post-close-fee) ${pnl['realized_pnl_total']:,.2f} "
        f"| fees (all legs) ${pnl['fees_paid_total']:,.2f}",
        f"- Activity: {pnl['open_positions']} open | "
        f"{d['activity']['live_labeled_trades']} live labeled trades | "
        f"{d['activity']['candidate_rows']} candidates | "
        f"{d['postmortems']['count']} postmortems",
        f"- Model: level {mdl['monitor_level']} | use_model={mdl['use_model']} "
        f"| brier {mdl['brier']} | history_rows {mdl['history_rows']} "
        f"| cold={mdl['cold']}",
        f"- Audit: {aud['records']} records ({aud['signal_records']} "
        f"non-routine) | dominant {aud['dominant_code']} "
        f"({aud['dominant_frac']:.0%} of non-routine) | "
        f"chain={_chain_word(aud)} | "
        f"retrain_requests {aud['retrain_requests']}",
        f"- Liquidity: spoofy {evt['spoofy_frac']:.0%} of non-liquid cycles "
        f"| feed errors {evt['feed_error_events']}",
    ]
    rec = d.get("recent") or {}
    if rec:
        ra, re_ = rec.get("audit", {}), rec.get("events", {})
        lines.append(
            f"- Recent ({rec['hours']:.0f}h lens): {ra.get('records', 0)} audit "
            f"records | dominant {ra.get('dominant_code')} "
            f"({ra.get('dominant_frac', 0.0):.0%} of non-routine) | "
            f"retrain_requests {ra.get('retrain_requests', 0)} | spoofy "
            f"{re_.get('spoofy_frac', 0.0):.0%} (non-liquid)")
    eras = d.get("eras") or {}
    if eras:
        rpe = eras.get("rows_per_era") or {}
        rpe_txt = (f"unavailable ({rpe['unavailable']})"
                   if "unavailable" in rpe else str(rpe))
        span = eras.get("corpus_span_days")
        lines.append(
            f"- Eras: current {eras.get('current_era')} | signal_history "
            f"exec_era: {rpe_txt} | fills per exec_era: "
            f"{eras.get('fills_per_era') or {}} ({eras.get('fills_rows', 0)} "
            f"rows) | pooling_hazard={eras.get('pooling_hazard')} "
            f"(source {eras.get('pooling_hazard_source')})")
        lines.append(
            f"- RAW signal-file span (signal_ts, all "
            f"{eras.get('corpus_rows', 0)} rows on disk): "
            f"{eras.get('corpus_first_ts') or 'n/a'} -> "
            f"{eras.get('corpus_last_ts') or 'n/a'} "
            f"({span if span is not None else 'n/a'}d"
            + (f", {eras['signal_ts_missing']} rows without signal_ts"
               if eras.get("signal_ts_missing") else "")
            + ") - NOT the TRAINED corpus span: era exclusion + the "
            "label_era filter drop rows, so the span the champion is "
            "SCORED on is shorter. For that one (the MinBTL / Sharpe-SE "
            "denominator) run scripts/champion_skill_report.py --json -> "
            "corpus_span_days")
    lines += [
        "",
        "## Diagnostics",
    ]
    icon = {"error": "[ERR] ", "warn": "[WARN]", "info": "[INFO]"}
    for g in d["diagnostics"]:
        lines.append(f"- {icon.get(g['severity'], '*')} **{g['id']} "
                     f"{g['title']}**  -  {g['detail']}")
    return "\n".join(lines) + "\n"


def write_digest(outputs_dir: "str | Path" = "outputs",
                 config: dict | None = None,
                 recent_hours: float = 48.0) -> dict:
    """Build the digest and persist it as session_digest.{json,md}. Returns
    the digest dict. Best-effort writes: a write failure is logged, not raised."""
    o = Path(outputs_dir)
    d = build_digest(o, config, recent_hours=recent_hours)
    try:
        o.mkdir(parents=True, exist_ok=True)
        (o / "session_digest.json").write_text(
            json.dumps(d, indent=2, default=str), encoding="utf-8")
        (o / "session_digest.md").write_text(render_markdown(d), encoding="utf-8")
    except OSError:
        log.exception("session digest write failed (non-fatal)")
    return d
