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
  SD-003 liquidity_veto      liquidity classified 'spoofy' most cycles ->
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

_LIQ_RE = re.compile(r"liquidity=(\w+)")
_ASSET_RE = re.compile(r"^\[(\w+)\]")

# SD-004 dominance is meant to catch a code BURYING others unexpectedly -
# not a code that is high-frequency BY DESIGN. ML-070 (dry-run active-
# learning exploration entries, see main.py._exploration_active) fires
# probabilistically every cycle by construction until explore_until_rows
# is reached, so it dominating early sessions is expected, not a fault.
# Excluded from the dominance calculation only; still counted in
# `records` and still fully present in `top_codes`, so nothing is hidden
# from the raw breakdown - only the false-positive WARN is suppressed.
_ROUTINE_NOISE_CODES = {"ML-070"}


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
def _audit_section(records: list, outputs: Path) -> dict:
    codes = Counter(r.get("code") for r in records)
    srcs = Counter(r.get("src") for r in records)
    total = len(records)
    # dominance is computed on non-routine codes only (see
    # _ROUTINE_NOISE_CODES) so expected-high-frequency background codes
    # can't false-positive SD-004; top_codes/records below stay unfiltered
    signal_codes = Counter({c: n for c, n in codes.items()
                            if c not in _ROUTINE_NOISE_CODES})
    signal_total = sum(signal_codes.values())
    top_code, top_n = (signal_codes.most_common(1)[0]
                       if signal_codes else (None, 0))
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
    return {
        "records": total,
        "signal_records": signal_total,
        "by_src": dict(srcs.most_common()),
        "top_codes": codes.most_common(12),
        "dominant_code": top_code,
        "dominant_frac": round(top_n / signal_total, 3) if signal_total else 0.0,
        "retrain_requests": codes.get("ML-032", 0),
        "kill_switch_events": codes.get("ML-050", 0),
        "chain_ok": chain.get("ok"),
        "chain_first_break": chain.get("first_break"),
        "chain_tamper": chain.get("tamper"),
        "chain_seams": chain.get("seams", 0),
    }


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
        "spoofy_frac": round(spoofy / liq_total, 3) if liq_total else 0.0,
        "cycles_estimate": max(per_asset_cycles.values()) if per_asset_cycles else 0,
        "feed_error_events": feed_errors,
    }


def _pnl_section(portfolio: dict, equity_rows: list) -> dict:
    eq_vals = [_f(r.get("equity")) for r in equity_rows if r.get("equity")]
    start = eq_vals[0] if eq_vals else _f(portfolio.get("starting_capital"))
    end = eq_vals[-1] if eq_vals else start
    lo, hi = (min(eq_vals), max(eq_vals)) if eq_vals else (start, end)
    return {
        "starting_capital": _f(portfolio.get("starting_capital")),
        "equity_start": round(start, 2),
        "equity_end": round(end, 2),
        "equity_min": round(lo, 2),
        "equity_max": round(hi, 2),
        "equity_range": round(hi - lo, 2),
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

    # SD-002 model starvation loop
    if model["cold"] and aud.get("retrain_requests", 0) >= 5:
        add(SD_MODEL_STARVATION, "warn", "model starvation loop",
            f"model is cold (live training rows={model['history_rows']}, "
            f"brier={model['brier']}) yet retrain was requested "
            f"{aud['retrain_requests']}x  -  with 0 entries there is no new data, "
            "so retraining can never clear the condition. Seed a model "
            "(scripts/train_meta.py) or supply history; this loop is also "
            f"{aud['dominant_frac']:.0%} of the audit trail")

    # SD-003 liquidity veto feed-wide
    if evt["spoofy_frac"] >= 0.5 and evt["cycles_estimate"] >= 10:
        add(SD_LIQUIDITY_VETO, "warn", "liquidity vetoed feed-wide",
            f"liquidity classified 'spoofy' on {evt['spoofy_frac']:.0%} of "
            "classified cycles, which suppresses sizing/taker on every asset. "
            "On a near-zero-spread feed this is likely a classifier "
            "miscalibration, not real spoofing  -  inspect the book source")

    # SD-004 audit noise (routine background codes excluded - see
    # _ROUTINE_NOISE_CODES; this now only fires on non-routine dominance)
    if aud.get("dominant_frac", 0) >= 0.30 and aud.get("signal_records", 0) >= 50:
        add(SD_AUDIT_NOISE, "warn", "audit trail dominated by one code",
            f"{aud['dominant_code']} is {aud['dominant_frac']:.0%} of "
            f"{aud['signal_records']} non-routine records  -  consequential "
            "dispositions are buried; rate-limit that emitter")

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
    cold = (history_rows == 0) or (brier in (None, "n/a"))
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


def build_digest(outputs_dir: "str | Path" = "outputs",
                 config: dict | None = None) -> dict:
    """Read every telemetry stream under `outputs_dir` and return one
    reconciled digest dict. Never raises; missing streams degrade to zeros."""
    o = Path(outputs_dir)
    audit = _read_jsonl(o / "audit.jsonl")
    events = _read_jsonl(o / "events.jsonl")
    equity_rows = _read_csv(o / "equity.csv")
    state = _read_json(o / "state.json")
    sig_rows = _read_csv(o / "signal_history.csv")
    pm_rows = _read_csv(o / "postmortem_summary.csv")
    portfolio = state.get("portfolio", {}) if isinstance(state, dict) else {}

    live_rows = sum(1 for r in sig_rows if r.get("source") == "live")
    digest = {
        "generated_at": time.time(),
        "outputs_dir": str(o),
        "window": _window(audit, events, equity_rows),
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
        "streams_present": {
            "audit.jsonl": bool(audit), "events.jsonl": bool(events),
            "equity.csv": bool(equity_rows), "state.json": bool(state),
            "signal_history.csv": bool(sig_rows),
            "postmortem_summary.csv": bool(pm_rows),
        },
    }
    digest["diagnostics"] = _detectors(digest, config or {})
    worst = digest["diagnostics"][0] if digest["diagnostics"] else {}
    digest["verdict"] = f"{worst.get('id', SD_OK)} {worst.get('title', 'ok')}"
    return digest


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
        f"- Equity: ${pnl['equity_start']:,.2f} -> ${pnl['equity_end']:,.2f} "
        f"(range ${pnl['equity_range']:,.2f}) | realized PnL "
        f"${pnl['realized_pnl_total']:,.2f} | fees ${pnl['fees_paid_total']:,.2f}",
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
        f"chain_ok={aud['chain_ok']} (tamper={aud.get('chain_tamper')}, "
        f"seams={aud.get('chain_seams', 0)}) | "
        f"retrain_requests {aud['retrain_requests']}",
        f"- Liquidity: spoofy {evt['spoofy_frac']:.0%} of classified cycles "
        f"| feed errors {evt['feed_error_events']}",
        "",
        "## Diagnostics",
    ]
    icon = {"error": "[ERR] ", "warn": "[WARN]", "info": "[INFO]"}
    for g in d["diagnostics"]:
        lines.append(f"- {icon.get(g['severity'], '*')} **{g['id']} "
                     f"{g['title']}**  -  {g['detail']}")
    return "\n".join(lines) + "\n"


def write_digest(outputs_dir: "str | Path" = "outputs",
                 config: dict | None = None) -> dict:
    """Build the digest and persist it as session_digest.{json,md}. Returns
    the digest dict. Best-effort writes: a write failure is logged, not raised."""
    o = Path(outputs_dir)
    d = build_digest(o, config)
    try:
        o.mkdir(parents=True, exist_ok=True)
        (o / "session_digest.json").write_text(
            json.dumps(d, indent=2, default=str), encoding="utf-8")
        (o / "session_digest.md").write_text(render_markdown(d), encoding="utf-8")
    except OSError:
        log.exception("session digest write failed (non-fatal)")
    return d
