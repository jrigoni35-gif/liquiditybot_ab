"""core/venue_integrity.py - VENUE INTEGRITY measurements (conduct standard
section 3, gaps VG-1..VG-10). SAFE class: measurement only.

Every function here is PURE: it takes rows/records/venue JSON already in
memory and returns a report dict. Nothing here places, sizes, cancels,
reprices or exits an order, nothing gates entries, and nothing does network
I/O. The one engine-side hook is `note_venue_errors` / `note_order_query`,
which `data/kraken_feed.py` calls AFTER it has already decided its return
value: they bump counters (core.code_stats, surfaced in status.json and
Grafana) and never raise. The CLI is `scripts/venue_integrity_report.py`.

Posture discipline. In this repo every fill so far is simulator output
(dry-run). A venue check fed simulator rows is not a venue check. So each
row is attributed a POSTURE from the audit trail's session-start records
(`CG-000` carries `dry_run`): the governing session is the last CG-000 at or
before the row's timestamp. "live" is only ever claimed from a CG-000 that
says dry_run false; no CG-000 before the row means "unknown", never live.
A report whose input has no live rows says so with VI-001 - absent data is
not a clean result.

Provenance of venue facts used below (read 2026-09-27 from docs.kraken.com):
  * AddOrder `stptype` default is `cancel-newest` ("arriving order will be
    canceled") - https://docs.kraken.com/api-reference/trading/add-order [K].
  * AssetPairs `status` values online/cancel_only/post_only/limit_only/
    reduce_only - .../market-data/get-tradable-asset-pairs [K].
  * SystemStatus values online/maintenance/cancel_only/post_only -
    .../market-data/get-system-status [K].
  * TradesHistory rows carry ordertxid/price/cost/fee/vol/maker -
    .../account-data/get-trades-history [K]. ClosedOrders rows carry
    userref/status/reason - .../account-data/get-closed-orders [K].
  * The exact `reason` text of a venue-cancelled post-only order, and the
    synchronous error string for a crossing post-only order, are NOT in
    those pages [UNKNOWN]; matched loosely on "post" + "only" [I].
"""
from __future__ import annotations

import bisect
import hashlib
import math
import threading
from collections import Counter
from typing import Any, Iterable, Optional

from core import code_stats
from core.codes import Code
from core.venue_fees import binding_row

# ---------------------------------------------------------------- helpers


def _f(v: Any) -> Optional[float]:
    """Finite float or None ('' / None / garbage / NaN / inf -> None)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def userref_for(order_id: str) -> str:
    """The Kraken userref the order manager derives from an internal order
    id. MUST equal execution.order_manager.OrderManager._userref - a test
    pins the two against each other (duplicated here so this module does not
    import the execution layer)."""
    digest = hashlib.sha256(str(order_id).encode("utf-8")).digest()
    return str(int.from_bytes(digest[:4], "big") % 2_000_000_000)


def _quantile(xs: list, q: float) -> Optional[float]:
    """Linear-interpolated quantile (numpy 'linear' convention)."""
    if not xs:
        return None
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


# ---------------------------------------------------------------- posture


class Posture:
    """Session posture timeline from CG-000 session-start records."""

    def __init__(self, records: Iterable[Any]):
        pts = []
        for r in records:
            if not isinstance(r, dict) or r.get("code") != Code.CG_SESSION_START.value:
                continue
            ts = _f(r.get("ts"))
            data = r.get("data") or {}
            dry = data.get("dry_run") if isinstance(data, dict) else None
            if ts is None or not isinstance(dry, bool):
                continue
            pts.append((ts, dry, data))
        pts.sort(key=lambda p: p[0])
        self._ts = [p[0] for p in pts]
        self._dry = [p[1] for p in pts]
        self._data = [p[2] for p in pts]

    @property
    def sessions(self) -> int:
        return len(self._ts)

    def at(self, ts: Any) -> str:
        """'live' | 'dry' | 'unknown' for a timestamp."""
        t = _f(ts)
        if t is None:
            return "unknown"
        i = bisect.bisect_right(self._ts, t) - 1
        if i < 0:
            return "unknown"
        return "dry" if self._dry[i] else "live"

    def latest_booked_fees(self) -> Optional[tuple]:
        """(maker_bps, taker_bps) the most recent session booked, or None."""
        for d in reversed(self._data):
            m, t = _f(d.get("maker_fee_bps")), _f(d.get("taker_fee_bps"))
            if m is not None and t is not None:
                return (m, t)
        return None


def _no_live(report: dict, n_live: int) -> dict:
    if n_live == 0:
        report["codes"] = report.get("codes", []) + [Code.VI_NO_LIVE_DATA.value]
        report["verdict"] = "NO_LIVE_DATA"
    return report


# ------------------------------------------------------------ VG-1 fees


def fee_check(fills: Iterable[dict], posture: Posture,
              volume_30d_usd: Optional[float], aop_usd: Optional[float] = None,
              tol_bps: float = 1.0) -> dict:
    """Per-fill charged fee (fees_delta_usd / notional) against the published
    tier row that binds at the operator-supplied 30-day volume (and AoP).

    Maker/taker class from fills.csv is `post_only` (1 -> maker, 0 -> taker);
    a marketable limit can still rest and fill as maker, so class is [I] for
    post_only=0 rows - `trades_fee_check` uses the venue's own maker flag.
    Unknown volume -> the row is unresolvable (VI-011), never the bottom row.
    """
    row = binding_row(volume_30d_usd, aop_usd)
    out: dict = {"check": "VG-1 fee", "tol_bps": tol_bps,
                 "binding_row": list(row) if row else None,
                 "aop_known": aop_usd is not None, "by_posture": {},
                 "mismatches": [], "codes": []}
    by: Counter = Counter()
    n_live = 0
    for r in fills:
        size, px, fee = _f(r.get("fill_size")), _f(r.get("fill_price")), _f(r.get("fees_delta_usd"))
        if not size or not px or fee is None or size <= 0 or px <= 0:
            continue
        pos = posture.at(r.get("ts"))
        n_live += pos == "live"
        by[pos] += 1
        if row is None:
            continue
        cls = "maker" if str(r.get("post_only", "")).strip() == "1" else "taker"
        expected = row[0] if cls == "maker" else row[1]
        charged = fee / (size * px) * 1e4
        if abs(charged - expected) > tol_bps:
            out["mismatches"].append({
                "ts": r.get("ts"), "order_id": r.get("order_id"),
                "symbol": r.get("symbol"), "posture": pos, "class": cls,
                "exec_era": r.get("exec_era") or "pre-stamp",
                "charged_bps": round(charged, 4), "published_bps": expected})
    out["by_posture"] = dict(by)
    if row is None:
        out["codes"].append(Code.VI_FEE_UNRESOLVED.value)
        out["verdict"] = "UNRESOLVED"
        return _no_live(out, n_live)
    out["verdict"] = "MISMATCH" if out["mismatches"] else "CLEAN"
    out["codes"].append((Code.VI_FEE_MISMATCH if out["mismatches"]
                         else Code.VI_CLEAN).value)
    out["mismatch_by_posture"] = dict(Counter(m["posture"] for m in out["mismatches"]))
    out["mismatch_by_era"] = dict(Counter(m["exec_era"] for m in out["mismatches"]))
    return _no_live(out, n_live)


def _trade_rows(trades_json: Any) -> list:
    """TradesHistory result (or {"result": ...} wrapper) -> list of rows."""
    if isinstance(trades_json, dict) and "result" in trades_json:
        trades_json = trades_json["result"]
    if isinstance(trades_json, dict) and "trades" in trades_json:
        trades_json = trades_json["trades"]
    if not isinstance(trades_json, dict):
        return []
    rows = []
    for tid, t in trades_json.items():
        if isinstance(t, dict):
            rows.append(dict(t, trade_id_key=tid))
    return rows


def trades_fee_check(trades_json: Any, volume_30d_usd: Optional[float],
                     aop_usd: Optional[float] = None,
                     tol_bps: float = 1.0) -> dict:
    """VG-1 on the venue's own TradesHistory: fee/cost vs the published row
    for the venue-reported maker flag. These are real venue fills by
    construction (posture is not needed)."""
    row = binding_row(volume_30d_usd, aop_usd)
    rows = _trade_rows(trades_json)
    out: dict = {"check": "VG-1 fee (TradesHistory)", "tol_bps": tol_bps,
                 "binding_row": list(row) if row else None, "n": 0,
                 "mismatches": [], "codes": []}
    for t in rows:
        cost, fee = _f(t.get("cost")), _f(t.get("fee"))
        if not cost or fee is None or cost <= 0:
            continue
        out["n"] += 1
        if row is None:
            continue
        maker = t.get("maker")
        if not isinstance(maker, bool):
            continue
        expected = row[0] if maker else row[1]
        charged = fee / cost * 1e4
        if abs(charged - expected) > tol_bps:
            out["mismatches"].append({"trade": t.get("trade_id_key"),
                                      "pair": t.get("pair"), "maker": maker,
                                      "charged_bps": round(charged, 4),
                                      "published_bps": expected})
    if row is None:
        out["codes"].append(Code.VI_FEE_UNRESOLVED.value)
        out["verdict"] = "UNRESOLVED"
    else:
        out["verdict"] = "MISMATCH" if out["mismatches"] else "CLEAN"
        out["codes"].append((Code.VI_FEE_MISMATCH if out["mismatches"]
                             else Code.VI_CLEAN).value)
    return _no_live(out, out["n"])


# ------------------------------------------- VG-2 live fill acceptance

# REGISTERED 2026-09-27, BEFORE any live fill exists (operator approval
# "build the VG checks"; ratification of the values is an operator item on
# docs/law/pre_live_checklist.md). Not fitted: each bound is a formula on the
# BOOKED fee row or a definitional floor, and the n-floors are the house's
# registered read points (era-9 moratorium: n=50 lean, n=100 verdict). Never
# re-tune these on accruing fills - that is the overfit law. Report-only:
# nothing reads this to gate or size anything.
LIVE_FILL_ACCEPTANCE: dict = {
    "registered": "2026-09-27",
    "n_lean": 50,
    "n_verdict": 100,
    # entry slip p90 (bps, + = adverse vs arrival) must not exceed the fee
    # saved by resting: taker_bps - maker_bps of the booked row.
    "entry_slip_p90_max": "taker_bps - maker_bps",
    # mean 30s ALPHA mark-out (bps, + = market moved with us) must be no
    # worse than -maker_bps: adverse drift larger than the maker fee means the
    # passive fills are being picked off faster than the fee they save.
    "alpha_markout_30s_mean_min": "-maker_bps",
    # maker-first means a majority of entry fills are post-only.
    "entry_post_only_share_min": 0.5,
}


def fill_acceptance(fills: Iterable[dict], posture: Posture,
                    maker_bps: float, taker_bps: float,
                    alpha_markout_30s: Optional[list] = None,
                    include_postures: tuple = ("live",)) -> dict:
    """Grade entry fills against LIVE_FILL_ACCEPTANCE. Only rows whose
    posture is in `include_postures` count (default live only)."""
    reg = LIVE_FILL_ACCEPTANCE
    slips, po = [], []
    n_live = 0
    for r in fills:
        if str(r.get("purpose", "")) != "entry" or not _f(r.get("fill_size")):
            continue
        pos = posture.at(r.get("ts"))
        if pos not in include_postures:
            continue
        n_live += pos == "live"
        s = _f(r.get("slip_bps"))
        if s is not None:
            slips.append(s)
        po.append(str(r.get("post_only", "")).strip() == "1")
    marks = [x for x in (alpha_markout_30s or []) if _f(x) is not None]
    bounds = {"entry_slip_p90_max": taker_bps - maker_bps,
              "alpha_markout_30s_mean_min": -maker_bps,
              "entry_post_only_share_min": reg["entry_post_only_share_min"]}
    metrics = {
        "entry_slip_p90_max": (len(slips), _quantile(slips, 0.9)),
        "alpha_markout_30s_mean_min": (
            len(marks), (sum(float(x) for x in marks) / len(marks)) if marks else None),
        "entry_post_only_share_min": (len(po), (sum(po) / len(po)) if po else None),
    }
    rows, codes = [], []
    for k, (n, val) in metrics.items():
        b = bounds[k]
        if val is None or n < reg["n_lean"]:
            status = "UNDER_N"
        else:
            ok = val <= b if k.endswith("_max") else val >= b
            status = ("PASS" if ok else "BREACH") + (
                "" if n >= reg["n_verdict"] else "_LEAN")
        rows.append({"metric": k, "n": n, "value": val, "bound": b,
                     "status": status})
        if status.startswith("BREACH"):
            codes.append(Code.VI_FILL_ACCEPT_BREACH.value)
        elif status == "UNDER_N":
            codes.append(Code.VI_FILL_ACCEPT_UNDER_N.value)
    out = {"check": "VG-2 fill acceptance", "postures": list(include_postures),
           "registration": reg, "metrics": rows,
           "codes": sorted(set(codes)) or [Code.VI_CLEAN.value]}
    out["verdict"] = ("BREACH" if Code.VI_FILL_ACCEPT_BREACH.value in codes
                      else "UNDER_N" if codes else "PASS")
    out["live_rows"] = n_live
    graded = out["verdict"]
    _no_live(out, n_live)
    if tuple(include_postures) != ("live",):
        # simulator rows graded for reference only: never a live verdict
        out["verdict"] = f"SIM_REFERENCE({graded})"
    return out


# ------------------------------------------------- terminals (VG-3/6/8)


def terminals(records: Iterable[Any]) -> list:
    """Order terminal records (OM-000 filled/cancelled clean, OM-040 timeout)
    -> [{ts, order_id, pair, side, purpose, terminal, created_ts, sim}].
    `sim` is the message marker the simulator writes ('(sim ...)'); the
    session posture is attributed separately and is the authority."""
    out = []
    want = {Code.OM_CLEAN_TERMINAL.value, Code.OM_TIMEOUT_CANCEL.value}
    for r in records:
        if not isinstance(r, dict) or r.get("code") not in want:
            continue
        msg = str(r.get("msg", ""))
        head = msg.split(" ")
        data = r.get("data") or {}
        term = data.get("terminal")
        if term is None and "terminal=" in msg:
            term = msg.split("terminal=", 1)[1].split(" ", 1)[0]
        out.append({
            "ts": _f(r.get("ts")),
            "order_id": str(data.get("order_id") or (head[0] if head else "")),
            "side": str(data.get("side") or (head[1] if len(head) > 1 else "")),
            "pair": str(data.get("pair") or (head[2] if len(head) > 2 else "")),
            "purpose": str(data.get("purpose", "")),
            "terminal": str(term or ""),
            "created_ts": _f(data.get("created_ts")),
            "lb_cancel": "LB-02" in msg,
            # which lifecycle branch wrote it: the simulator's '(sim ...)',
            # the live poller's '(venue ...)' / '(timeout at fill_ratio...)',
            # or neither (cancel_order paths, e.g. LB-021 reprices)
            "path": ("sim" if "(sim " in msg else
                     "live" if ("(venue " in msg
                                or "(timeout at fill_ratio" in msg) else "other"),
        })
    return out


# ------------------------------------------------- VG-3 sim-vs-live gap


def sim_live_gap(records: list, posture: Posture, purpose: str = "entry") -> dict:
    """Fill rate (filled terminals / all terminals) per pair, split by
    posture. Per-LIQUIDITY-LABEL split: the terminal records do not carry the
    label and unfilled orders have no position to join through, so it is
    [UNKNOWN] from this corpus - named, not faked."""
    cells: dict = {}
    disagree = 0
    for t in terminals(records):
        if t["purpose"] != purpose:
            continue
        pos = posture.at(t["ts"])
        if (pos == "live" and t["path"] == "sim") or (
                pos == "dry" and t["path"] == "live"):
            disagree += 1
        c = cells.setdefault((pos, t["pair"]), Counter())
        c[t["terminal"]] += 1
    table = []
    for (pos, pair), c in sorted(cells.items()):
        n = sum(c.values())
        table.append({"posture": pos, "pair": pair, "n": n,
                      "filled": c.get("filled", 0),
                      "fill_rate": c.get("filled", 0) / n if n else None})
    gaps = []
    live = {r["pair"]: r for r in table if r["posture"] == "live"}
    for r in table:
        if r["posture"] == "dry" and r["pair"] in live:
            lr = live[r["pair"]]
            gaps.append({"pair": r["pair"], "sim_rate": r["fill_rate"],
                         "live_rate": lr["fill_rate"], "n_sim": r["n"],
                         "n_live": lr["n"],
                         "gap": (lr["fill_rate"] or 0.0) - (r["fill_rate"] or 0.0)})
    n_live = sum(r["n"] for r in table if r["posture"] == "live")
    out = {"check": "VG-3 sim-vs-live fill gap", "purpose": purpose,
           "table": table, "gaps": gaps,
           # live-path terminal in a dry session (or sim in live): a
           # corpus defect - e.g. a test's records in the production trail
           "marker_posture_disagreements": disagree,
           "liquidity_label_split": "UNKNOWN (label not in terminal records)",
           "codes": [Code.VI_SIM_LIVE_GAP.value] if gaps else []}
    out["verdict"] = "MEASURED" if gaps else "NO_GAP_MEASURED"
    return _no_live(out, n_live)


# -------------------------------------------- VG-4 venue error classes

_ERR_RULES: tuple = (
    (Code.VI_ERR_POST_ONLY, ("post only", "post-only")),
    (Code.VI_ERR_RATE_LIMIT, ("rate limit", "too many requests",
                              "temporary lockout")),
    (Code.VI_ERR_NONCE, ("invalid nonce",)),
    (Code.VI_ERR_FUNDS, ("insufficient funds", "insufficient margin",
                         "margin level too low", "margin allowance")),
    (Code.VI_ERR_PERMISSION, ("permission", "invalid key", "invalid signature",
                              "eauth:")),
    (Code.VI_ERR_UNAVAILABLE, ("eservice:", "internal error", "busy",
                               "deadline")),
    (Code.VI_ERR_ORDER_REJECT, ("eorder:",)),
)


def classify_venue_error(err: Any) -> Code:
    """One Kraken error string -> its registered VI-04x class. Rule order is
    load-bearing: 'EOrder:Rate limit exceeded' is a rate limit, not a generic
    order reject; a post-only cross is its own class (VG-5)."""
    s = str(err).lower()
    for code, needles in _ERR_RULES:
        if any(n in s for n in needles):
            return code
    return Code.VI_ERR_OTHER


_counts: Counter = Counter()
_lock = threading.Lock()
_seen_po: dict = {}
_SEEN_PO_CAP = 4096


def note_venue_errors(errors: Any) -> None:
    """Telemetry hook for data/kraken_feed.py: classify and count. NEVER
    raises and returns nothing - the caller's return value is decided before
    this runs."""
    try:
        errs = errors if isinstance(errors, (list, tuple)) else [errors]
        for e in errs:
            c = classify_venue_error(e).value
            code_stats.bump(c)
            with _lock:
                _counts[c] += 1
    except Exception:  # nosec B110 - telemetry must never raise into the feed
        pass


def note_transport_failure() -> None:
    """A private request that failed below the API (HTTP/connection)."""
    try:
        code_stats.bump(Code.VI_ERR_TRANSPORT.value)
        with _lock:
            _counts[Code.VI_ERR_TRANSPORT.value] += 1
    except Exception:  # nosec B110 - telemetry must never raise into the feed
        pass


def note_order_query(result: Any) -> None:
    """VG-5 telemetry hook: a QueryOrders/ClosedOrders result is scanned
    (read-only) for venue-cancelled post-only orders, counted once per txid.
    Never mutates `result`, never raises."""
    try:
        if not isinstance(result, dict):
            return
        closed = result.get("closed")
        rows: dict = closed if isinstance(closed, dict) else result
        for txid, info in rows.items():
            if not isinstance(info, dict) or not is_post_only_cancel(info):
                continue
            with _lock:
                if txid in _seen_po:
                    continue
                if len(_seen_po) >= _SEEN_PO_CAP:
                    _seen_po.pop(next(iter(_seen_po)))
                _seen_po[txid] = True
                _counts[Code.VI_POST_ONLY_CANCEL.value] += 1
            code_stats.bump(Code.VI_POST_ONLY_CANCEL.value)
    except Exception:  # nosec B110 - telemetry must never raise into the feed
        pass


def venue_error_counts() -> dict:
    with _lock:
        return dict(_counts)


def reset_venue_error_counts() -> None:
    with _lock:
        _counts.clear()
        _seen_po.clear()


def classify_log_lines(lines: Iterable[str]) -> dict:
    """Offline VG-4: classify the feed's existing warning lines
    ("Kraken private/public API error on <EP>: [...]") from a log file."""
    by_code: Counter = Counter()
    by_ep: dict = {}
    for ln in lines:
        for lane in ("private", "public"):
            needle = f"Kraken {lane} API error on "
            if needle not in ln:
                continue
            rest = ln.split(needle, 1)[1]
            ep, _, errs = rest.partition(": ")
            c = classify_venue_error(errs).value
            by_code[c] += 1
            by_ep.setdefault(ep.strip(), Counter())[c] += 1
        if "Kraken private request failed for " in ln:
            by_code[Code.VI_ERR_TRANSPORT.value] += 1
    return {"check": "VG-4 venue error classes", "by_code": dict(by_code),
            "by_endpoint": {k: dict(v) for k, v in by_ep.items()},
            "codes": sorted(by_code) or [Code.VI_CLEAN.value]}


# ---------------------------------------------- VG-5 post-only cancels


def is_post_only_cancel(info: dict) -> bool:
    status = str(info.get("status", "")).lower()
    reason = str(info.get("reason") or "").lower()
    return status == "canceled" and "post" in reason and "only" in reason


def post_only_cancels(closed_json: Any) -> dict:
    """Offline VG-5 over a ClosedOrders export: venue-cancelled post-only
    orders counted separately from every other cancel reason."""
    if isinstance(closed_json, dict) and "result" in closed_json:
        closed_json = closed_json["result"]
    if isinstance(closed_json, dict) and isinstance(closed_json.get("closed"), dict):
        closed_json = closed_json["closed"]
    reasons: Counter = Counter()
    po = 0
    n = 0
    for info in (closed_json or {}).values() if isinstance(closed_json, dict) else []:
        if not isinstance(info, dict):
            continue
        n += 1
        if is_post_only_cancel(info):
            po += 1
        elif str(info.get("status", "")).lower() == "canceled":
            reasons[str(info.get("reason") or "")] += 1
    out = {"check": "VG-5 post-only rejects", "closed_orders": n,
           "post_only_cancels": po, "other_cancel_reasons": dict(reasons),
           "codes": [Code.VI_POST_ONLY_CANCEL.value] if po else [Code.VI_CLEAN.value]}
    out["verdict"] = "COUNTED" if po else "NONE"
    return _no_live(out, n)


# --------------------------------------------------- VG-6 orphan orders


def orphan_diff(open_json: Any, known_order_ids: Iterable[str],
                terminal_order_ids: Iterable[str]) -> dict:
    """Venue OpenOrders vs what the bot knows. Read-only; NEVER cancels.

    ORPHAN   (VI-060): open at the venue, userref absent or not derived from
                       any order id the bot has recorded (manual order, other
                       client, or a lost submit).
    STRANDED (VI-061): userref maps to a bot order the audit already records
                       as TERMINAL - the bot believes it is gone, the venue
                       says it is resting. The dangerous one.
    """
    if isinstance(open_json, dict) and "result" in open_json:
        open_json = open_json["result"]
    if isinstance(open_json, dict) and isinstance(open_json.get("open"), dict):
        open_json = open_json["open"]
    refmap = {userref_for(o): o for o in known_order_ids}
    term = {userref_for(o) for o in terminal_order_ids}
    orphans, stranded, tracked = [], [], []
    for txid, info in (open_json or {}).items() if isinstance(open_json, dict) else []:
        if not isinstance(info, dict):
            continue
        ref = str(info.get("userref", "") or "")
        d = info.get("descr") or {}
        item = {"txid": txid, "userref": ref,
                "pair": d.get("pair") if isinstance(d, dict) else None,
                "order": d.get("order") if isinstance(d, dict) else None}
        if ref and ref in term:
            item["order_id"] = refmap.get(ref)
            stranded.append(item)
        elif ref and ref in refmap:
            item["order_id"] = refmap[ref]
            tracked.append(item)
        else:
            orphans.append(item)
    codes = ([Code.VI_ORPHAN_ORDER.value] if orphans else []) + (
        [Code.VI_STRANDED_ORDER.value] if stranded else [])
    n = len(orphans) + len(stranded) + len(tracked)
    return {"check": "VG-6 orphan orders", "venue_open": n,
            "orphans": orphans, "stranded": stranded, "tracked": tracked,
            "codes": codes or [Code.VI_CLEAN.value],
            "verdict": "FINDINGS" if codes else "CLEAN",
            "action": "none - report only (auto-cancel is COHORT-RESETTING)"}


# ------------------------------------------------ VG-7 reconciliation


def reconcile(fills: Iterable[dict], posture: Posture, closed_json: Any,
              trades_json: Any, qty_tol_rel: float = 1e-6,
              px_tol_bps: float = 1.0, fee_tol_usd: float = 0.01) -> dict:
    """fills.csv (live-posture rows) vs Kraken ClosedOrders + TradesHistory.

    Join: fills.order_id -> userref (the order manager's derivation) ->
    ClosedOrders txid -> TradesHistory rows by ordertxid. Per order: size,
    VWAP and fee are compared. Unmatched on either side is VI-071; a matched
    order that disagrees is VI-070. Dry and unknown-posture rows are excluded
    (the venue never saw a simulated fill) and counted."""
    if isinstance(closed_json, dict) and "result" in closed_json:
        closed_json = closed_json["result"]
    if isinstance(closed_json, dict) and isinstance(closed_json.get("closed"), dict):
        closed_json = closed_json["closed"]
    closed = closed_json if isinstance(closed_json, dict) else {}
    ref_to_tx = {str(v.get("userref")): k for k, v in closed.items()
                 if isinstance(v, dict) and v.get("userref") not in (None, "")}
    venue: dict = {}
    for t in _trade_rows(trades_json):
        ot = str(t.get("ordertxid", ""))
        vol, px, fee = _f(t.get("vol")), _f(t.get("price")), _f(t.get("fee"))
        if not ot or vol is None or px is None:
            continue
        a = venue.setdefault(ot, [0.0, 0.0, 0.0])
        a[0] += vol
        a[1] += vol * px
        a[2] += fee or 0.0
    bot: dict = {}
    skipped: Counter = Counter()
    for r in fills:
        pos = posture.at(r.get("ts"))
        if pos != "live":
            skipped[pos] += 1
            continue
        size, px, fee = _f(r.get("fill_size")), _f(r.get("fill_price")), _f(r.get("fees_delta_usd"))
        if not size or px is None:
            continue
        a = bot.setdefault(str(r.get("order_id", "")), [0.0, 0.0, 0.0])
        a[0] += size
        a[1] += size * px
        a[2] += fee or 0.0
    mism, unmatched = [], []
    claimed = set()
    for oid, (q, qp, fee) in sorted(bot.items()):
        tx = ref_to_tx.get(userref_for(oid))
        if tx is None or tx not in venue:
            unmatched.append({"side": "bot_only", "order_id": oid, "txid": tx})
            continue
        claimed.add(tx)
        vq, vqp, vfee = venue[tx]
        vw, bw = (vqp / vq if vq else 0.0), (qp / q if q else 0.0)
        bad = []
        if abs(q - vq) > qty_tol_rel * max(abs(vq), 1e-12) + 1e-12:
            bad.append("qty")
        if vw and abs(bw - vw) / vw * 1e4 > px_tol_bps:
            bad.append("price")
        if abs(fee - vfee) > fee_tol_usd:
            bad.append("fee")
        if bad:
            mism.append({"order_id": oid, "txid": tx, "fields": bad,
                         "bot": [q, bw, fee], "venue": [vq, vw, vfee]})
    for tx in sorted(set(venue) - claimed):
        unmatched.append({"side": "venue_only", "txid": tx})
    codes = ([Code.VI_RECON_MISMATCH.value] if mism else []) + (
        [Code.VI_RECON_UNMATCHED.value] if unmatched else [])
    out = {"check": "VG-7 fills vs venue", "bot_live_orders": len(bot),
           "venue_orders": len(venue), "skipped_non_live_rows": dict(skipped),
           "mismatches": mism, "unmatched": unmatched,
           "fee_currency_note": "[I] venue fee assumed quote-currency (USD)",
           "codes": codes or [Code.VI_CLEAN.value],
           "verdict": "FINDINGS" if codes else "CLEAN"}
    return _no_live(out, len(bot) + len(venue))


# --------------------------------------------------------- VG-8 STP


STP_DEFAULT = {
    "value": "cancel-newest",
    "meaning": "arriving order will be canceled",
    "source": "https://docs.kraken.com/api-reference/trading/add-order",
    "read_utc": "2026-09-27",
    "tag": "[K]",
}


def self_cross_scan(fills: Iterable[dict], posture: Posture,
                    window_sec: float = 1.0, px_tol_bps: float = 1.0) -> dict:
    """Pairs of OWN fills on the same symbol, opposite sides, different
    order ids, within `window_sec` and `px_tol_bps` of each other - the
    footprint a self-match would leave. Only live-posture rows can evidence a
    venue self-trade (the simulator cannot self-match); dry rows are scanned
    and reported separately so the scanner is exercised."""
    rows = []
    for r in fills:
        ts, px, sz = _f(r.get("ts")), _f(r.get("fill_price")), _f(r.get("fill_size"))
        if ts is None or not px or not sz:
            continue
        rows.append((ts, str(r.get("symbol", "")), str(r.get("side", "")),
                     str(r.get("order_id", "")), px, posture.at(ts)))
    rows.sort()
    hits = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if b[0] - a[0] > window_sec:
                break
            if (a[1] == b[1] and a[2] != b[2] and a[3] != b[3]
                    and abs(a[4] - b[4]) / a[4] * 1e4 <= px_tol_bps):
                hits.append({"ts": a[0], "symbol": a[1],
                             "orders": [a[3], b[3]], "posture": a[5]})
    live_hits = [h for h in hits if h["posture"] == "live"]
    n_live = sum(1 for r in rows if r[5] == "live")
    out = {"check": "VG-8 self-cross scan", "window_sec": window_sec,
           "px_tol_bps": px_tol_bps, "stp_default": STP_DEFAULT,
           "hits_live": live_hits,
           "hits_non_live": len(hits) - len(live_hits),
           "codes": [Code.VI_SELF_CROSS.value] if live_hits else [Code.VI_CLEAN.value]}
    out["verdict"] = "FINDINGS" if live_hits else "CLEAN"
    return _no_live(out, n_live)


def coexistence_scan(records: list, fills: Iterable[dict],
                     min_overlap_sec: float = 0.01) -> dict:
    """OD-9 measurement: exit orders whose lifetime overlapped an OPPOSITE-
    side resting ENTRY order on the same pair. This is decision-logic
    behaviour, which the simulator DOES exercise, so dry data is evidence
    here (the simulator cannot self-MATCH; it can still co-rest).

    Lifetime = [created_ts, end], end = the order's last fill time when it
    filled (the terminal record is written after the fill, in the same poll -
    using it would count an entry's own closing exit as an overlap), else
    the terminal time. `min_overlap_sec` absorbs fills.csv's millisecond ts
    rounding. Entry book comes from fills.csv `book`, or 'long' for an
    LB-021/LB-022 cancel; 'long' overlaps are the LB-022-guarded path, the
    '5m'/'unknown' ones are the unguarded OD-9 path. Exit marketability is
    known only when it filled (post_only=0 -> marketable [I])."""
    po: dict = {}
    book: dict = {}
    last_fill: dict = {}
    for r in fills:
        oid = str(r.get("order_id", ""))
        po[oid] = str(r.get("post_only", "")).strip()
        if r.get("book"):
            book[oid] = str(r.get("book"))
        t = _f(r.get("ts"))
        if t is not None:
            last_fill[oid] = max(t, last_fill.get(oid, t))
    ts_ = []
    for t in terminals(records):
        if not (t["created_ts"] and t["ts"] and t["created_ts"] > 1e9):
            continue
        end = t["ts"]
        if t["terminal"] == "filled" and t["order_id"] in last_fill:
            end = min(end, last_fill[t["order_id"]])
        ts_.append(dict(t, end=end))
    entries: dict = {}
    for t in ts_:
        if t["purpose"] == "entry":
            entries.setdefault(t["pair"], []).append(t)
    overlaps = []
    for x in ts_:
        if x["purpose"] != "exit":
            continue
        for e in entries.get(x["pair"], []):
            if e["side"] == x["side"]:
                continue
            ov = min(e["end"], x["end"]) - max(e["created_ts"], x["created_ts"])
            if ov > min_overlap_sec:
                eb = book.get(e["order_id"]) or ("long" if e["lb_cancel"] else "unknown")
                overlaps.append({"exit": x["order_id"], "entry": e["order_id"],
                                 "pair": x["pair"], "entry_book": eb,
                                 "overlap_sec": round(ov, 3),
                                 "exit_marketable": {"0": True, "1": False}.get(
                                     po.get(x["order_id"], ""))})
    exits = sum(1 for t in ts_ if t["purpose"] == "exit")
    unguarded = [o for o in overlaps if o["entry_book"] != "long"]
    return {"check": "OD-9 5m entry/exit coexistence",
            "exits_with_lifetime": exits, "overlaps": len(overlaps),
            "overlaps_by_entry_book": dict(Counter(o["entry_book"] for o in overlaps)),
            "unguarded_overlaps": len(unguarded),
            "unguarded_marketable_exit": sum(1 for o in unguarded if o["exit_marketable"]),
            "examples": overlaps[:10],
            "stp_consequence": ("under the venue default cancel-newest the "
                                "ARRIVING order is the one cancelled - for "
                                "this path that is the EXIT [I]"),
            "codes": ([Code.VI_SELF_CROSS.value] if unguarded
                      else [Code.VI_CLEAN.value])}


# ----------------------------------------------- VG-9 venue status


def venue_status(asset_pairs_json: Any, system_status_json: Any,
                 pairs: Iterable[str]) -> dict:
    """Pair `status` (AssetPairs) and SystemStatus. Any value other than
    'online' for a traded pair, or a missing pair, is VI-090. Report only:
    gating entries on it is COHORT-RESETTING (or an operator SAFETY ruling)."""
    ap = asset_pairs_json
    if isinstance(ap, dict) and "result" in ap:
        ap = ap["result"]
    ss = system_status_json
    if isinstance(ss, dict) and "result" in ss:
        ss = ss["result"]
    by_name: dict = {}
    for k, v in (ap or {}).items() if isinstance(ap, dict) else []:
        if isinstance(v, dict):
            for n in (k, v.get("altname"), v.get("wsname")):
                if n:
                    by_name[str(n).upper()] = v
    rows, flags = [], []
    for p in pairs:
        cands = {p.upper(), p.replace("/", "").upper(),
                 p.upper().replace("BTC", "XBT"),
                 p.replace("/", "").upper().replace("BTC", "XBT")}
        meta = next((by_name[c] for c in cands if c in by_name), None)
        st = str(meta.get("status", "")) if meta else "MISSING"
        rows.append({"pair": p, "status": st or "UNREPORTED"})
        if st != "online":
            flags.append(p)
    sys_st = str(ss.get("status", "")) if isinstance(ss, dict) else "UNKNOWN"
    if sys_st != "online":
        flags.append("SystemStatus")
    return {"check": "VG-9 venue status", "system_status": sys_st,
            "pairs": rows, "flagged": flags,
            "codes": [Code.VI_VENUE_STATUS.value] if flags else [Code.VI_CLEAN.value],
            "verdict": "FLAGGED" if flags else "ONLINE",
            "action": "none - report only"}


# ------------------------------------------------- VG-10 custody


def custody(on_venue_usd: Optional[float], target_usd: Optional[float]) -> dict:
    """Dollars held on the venue vs the operator's off-venue target (the most
    the operator wants resting on Kraken). Unknown either side -> UNKNOWN."""
    v, t = _f(on_venue_usd), _f(target_usd)
    out: dict = {"check": "VG-10 custody", "on_venue_usd": v, "target_usd": t}
    if v is None or t is None:
        out.update(verdict="UNKNOWN", codes=[Code.VI_NO_LIVE_DATA.value])
    elif v > t:
        out.update(verdict="OVER_TARGET", excess_usd=round(v - t, 2),
                   codes=[Code.VI_CUSTODY_OVER_TARGET.value])
    else:
        out.update(verdict="WITHIN_TARGET", headroom_usd=round(t - v, 2),
                   codes=[Code.VI_CLEAN.value])
    return out


def trade_balance_usd(tb_json: Any) -> Optional[float]:
    """TradeBalance result -> equivalent balance 'eb' (USD when asked with
    asset=ZUSD)."""
    if isinstance(tb_json, dict) and "result" in tb_json:
        tb_json = tb_json["result"]
    if not isinstance(tb_json, dict):
        return None
    return _f(tb_json.get("eb"))
