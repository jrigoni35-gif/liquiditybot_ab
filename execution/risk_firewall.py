"""
execution/risk_firewall.py — rev 2.0 (Assurance Build)

Independent venue-facing order screen in the SEC 15c3-5 sense, built
to safety-critical discipline (DO-178C-style traceability, NASA/JPL
Power-of-10 posture). Everything upstream is presumed wrong or
compromised; no order reaches the venue unscreened.

DESIGN RULES
  R1  FAIL CLOSED. Unverifiable input rejects the order — except
      exits, which fail SAFE: substituted/clamped, rejected only when
      no executable form exists.
  R2  NEVER RAISE AT RUNTIME. Internal errors latch a FAULT: entries
      reject, exits pass degraded, until reset_fault(). Init-time
      errors DO raise — refuse to arm on a bad configuration.
  R3  DETERMINISTIC AND BOUNDED. Fixed bounds on every loop and
      container; monotonic clock for all windows (wall time is audit
      stamps only).
  R4  TOTAL AUDIT. Every verdict: sequence number + reason codes from
      core.codes, one structured log line, hash-chained audit record
      for every reject/clamp/fault.

REQUIREMENT TRACE
  REQ-FW-01 input validation .... _validate()      FW-01x
  REQ-FW-02 reference integrity . _validate()      FW-060
  REQ-FW-03 rate limit .......... _check() step R  FW-020
  REQ-FW-04 duplicate suppress .. _check() step D  FW-030
  REQ-FW-05 price collar ........ _check() step C  FW-05x
  REQ-FW-06 notional ceilings ... _check() step N  FW-04x
  REQ-FW-07 fault containment ... check() wrapper  FW-09x
  REQ-FW-08 power-on self test .. self_test()      init

INVARIANTS PRESERVED FROM REV 1
  Exits never rejected by collar (clamped); exit notional shrinks to
  cap; exits get 2x rate budget and 2x pct-equity headroom; rejected
  orders consume no rate budget and leave no dupe record.
"""

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Tuple

from core.audit import _REGISTERED_CODES, get_audit
from core.codes import Code, tag

log = logging.getLogger("liquiditybot.execution.risk_firewall")

_EPS = 1e-12
_RECENT_CAP = 256
_SIDES = frozenset({"buy", "sell"})
_PURPOSES = frozenset({"entry", "exit", "hedge"})


class Disposition(str, Enum):
    ACCEPT = "ACCEPT"
    ACCEPT_MODIFIED = "ACCEPT_MODIFIED"
    REJECT = "REJECT"


@dataclass(frozen=True)
class FirewallVerdict:
    allowed: bool
    price: float
    size: float
    disposition: Disposition = Disposition.ACCEPT
    clamped: bool = False
    reasons: Tuple[str, ...] = ()
    seq: int = 0
    ts_wall: float = 0.0


@dataclass(frozen=True)
class Limits:
    enabled: bool
    entry_collar_bps: float
    exit_collar_bps: float
    max_order_usd: float
    max_order_pct_equity: float
    max_orders_per_min: int
    dupe_window_sec: float

    @classmethod
    def from_config(cls, cfg: dict) -> "Limits":
        cfg = cfg or {}

        def f(name, default, lo, hi):
            try:
                x = float(cfg.get(name, default))
            except (TypeError, ValueError):
                # `from None`: the swallowed conversion error carries no
                # information beyond what this FATAL config message states
                raise ValueError(
                    f"firewall config: {name} not numeric") from None
            if not math.isfinite(x) or not (lo <= x <= hi):
                raise ValueError(
                    f"firewall config: {name}={x} outside [{lo}, {hi}]")
            return x

        lim = cls(
            enabled=bool(cfg.get("enabled", True)),
            entry_collar_bps=f("entry_collar_bps", 100.0, 1.0, 5_000.0),
            exit_collar_bps=f("exit_collar_bps", 500.0, 1.0, 10_000.0),
            max_order_usd=f("max_order_usd", 25_000.0, 1.0, 1e9),
            max_order_pct_equity=f("max_order_pct_equity", 30.0, 0.1, 100.0),
            max_orders_per_min=int(f("max_orders_per_min", 30, 1, 600)),
            dupe_window_sec=f("dupe_window_sec", 3.0, 0.0, 60.0),
        )
        if lim.exit_collar_bps < lim.entry_collar_bps:
            raise ValueError("firewall config: exit collar tighter than "
                             "entry collar defeats fail-safe exits")
        return lim


class RiskFirewall:
    """Same public surface as rev 1: RiskFirewall(config, alerts);
    check(...) -> verdict with .allowed/.price/.size/.clamped/.reasons.
    Raises only from __init__ (refuse to arm)."""

    def __init__(self, config: dict, alerts=None, _shadow: bool = False):
        self.limits = Limits.from_config(config)
        self.alerts = alerts
        self._quiet = False   # suppressed alerting on the shadow self-test instance
        self._seq = 0
        self._fault: Optional[str] = None
        self._submits: deque = deque(maxlen=self.limits.max_orders_per_min * 2)
        self._recent: dict = {}
        self._counters: dict = {"screened": 0, "accepted": 0,
                                "accepted_modified": 0, "rejected": 0}
        if not _shadow:
            failures = self.self_test()
            if failures:
                raise RuntimeError(f"firewall PBIT failed: {failures}")
            log.info("firewall armed: PBIT pass, limits=%s", self.limits)

    # ------------------------------------------------------------------
    def check(self, *, pair: str, side: str, purpose: str, price: float,
              size: float, ref_price: float, equity: float,
              now: Optional[float] = None) -> FirewallVerdict:
        """REQ-FW-07: total containment — this method cannot raise."""
        try:
            return self._check(pair=pair, side=side, purpose=purpose,
                               price=price, size=size, ref_price=ref_price,
                               equity=equity, now=now)
        except Exception:
            log.critical("firewall INTERNAL FAULT — latching", exc_info=True)
            self._fault = "internal exception in _check"
            # counted=True: _fault_verdict below tag()s FW-090 into the
            # verdict reasons for this SAME emission — the tag bump is the
            # count; a bare bump here would double it
            get_audit().log("firewall", Code.FW_FAULT_REJECT,
                            "internal exception latched FAULT", {},
                            counted=True)
            return self._fault_verdict(purpose, price, size)

    def reset_fault(self):
        log.warning("firewall FAULT reset by operator (was: %s)", self._fault)
        self._fault = None

    def status(self) -> dict:
        return {"fault": self._fault, "seq": self._seq,
                "counters": dict(self._counters),
                "recent_fps": len(self._recent),
                "submits_in_window": len(self._submits)}

    # ------------------------------------------------------------------
    def _check(self, *, pair, side, purpose, price, size, ref_price,
               equity, now) -> FirewallVerdict:
        self._seq += 1
        seq = self._seq
        self._counters["screened"] += 1
        t = now if now is not None else time.monotonic()
        notes = []

        if not self.limits.enabled:
            return self._emit(seq, Disposition.ACCEPT, price, size, False,
                              ["screening disabled by config"],
                              pair, side, purpose)
        if self._fault is not None:
            return self._fault_verdict(purpose, price, size, seq=seq)

        is_exit = purpose == "exit"

        # ---- REQ-FW-01/02: positive validation of every input ---------
        ok, price, size, rej = self._validate(
            pair, side, purpose, price, size, ref_price, equity,
            is_exit, notes)
        if not ok:
            return self._reject(seq, rej, pair, side, purpose, price, size)
        ref_ok = isinstance(ref_price, (int, float)) and \
            math.isfinite(ref_price) and ref_price > 0
        eq_ok = isinstance(equity, (int, float)) and \
            math.isfinite(equity) and equity > 0

        # ---- REQ-FW-03: rate limit -------------------------------------
        cutoff = t - 60.0
        while self._submits and self._submits[0] < cutoff:
            self._submits.popleft()
        budget = self.limits.max_orders_per_min * (2 if is_exit else 1)
        if len(self._submits) >= budget:
            if is_exit:
                # INVARIANT #5: escapes are never rate-vetoed. A panic
                # flatten across a wide book plus escalation retries could
                # exhaust even the 2x budget and starve risk-REDUCING
                # orders for up to a minute in exactly the dislocated tape
                # the ladder exists for (audit EX-5 2026-07-17). The
                # override is loud and audited; entries keep starving
                # first because exits still consume budget below.
                notes.append(tag(Code.FW_RATE_EXIT_OVERRIDE,
                                 f"{len(self._submits)} orders in 60s >= "
                                 f"budget {budget} - exit allowed anyway"))
                self._count(Code.FW_RATE_EXIT_OVERRIDE)
            else:
                return self._reject(
                    seq, [tag(Code.FW_RATE_LIMIT,
                              f"{len(self._submits)} accepted orders in 60s "
                              f">= budget {budget}")],
                    pair, side, purpose, price, size, alert_key="rate_limit")

        # ---- REQ-FW-04: duplicate suppression ---------------------------
        fp = self._fingerprint(pair, side, purpose, price, size)
        age = t - self._recent.get(fp, -1e18)
        if age < self.limits.dupe_window_sec and is_exit:
            # INVARIANT #5 (EX-5): escapes are never dupe-vetoed. The
            # engine's one-live-exit dedup already prevents a double-submit
            # while an exit order is WORKING, so an identical exit can only
            # reach this window after its predecessor went terminal - i.e.
            # the escalation ladder deliberately retrying into a frozen
            # book, exactly when being vetoed hurts most. Note + count,
            # never reject.
            notes.append(tag(Code.FW_DUPLICATE,
                             f"identical exit {age:.1f}s ago - escape "
                             f"retried, never dupe-vetoed"))
            self._count(Code.FW_DUPLICATE)
        elif age < self.limits.dupe_window_sec:
            self._counters["rejected"] += 1
            self._count(Code.FW_DUPLICATE)
            if not getattr(self, "_quiet", False):
                log.warning("AUDIT seq=%06d disp=REJECT code=%s pair=%s side=%s "
                            "purpose=%s px=%.10g sz=%.10g dupe_age=%.2fs",
                            seq, Code.FW_DUPLICATE.value, pair, side,
                            purpose, price, size, age)
                # R4 total audit: every reject reaches the hash chain — this
                # path previously log-only, the sole disposition that did.
                # counted=True: the verdict below tag()s FW-030 into its
                # reasons for this SAME emission — that bump is the count
                get_audit().log("firewall", Code.FW_DUPLICATE,
                                f"{pair} {side} {purpose} identical order "
                                f"{age:.1f}s ago", {"seq": seq},
                                counted=True)
            return FirewallVerdict(
                allowed=False, price=price, size=size,
                disposition=Disposition.REJECT,
                reasons=(tag(Code.FW_DUPLICATE,
                             f"identical order {age:.1f}s ago"),),
                seq=seq, ts_wall=time.time())

        # ---- REQ-FW-05: price collar (before notional, so the notional
        # cap is enforced on the FINAL screened price) --------------------
        clamped = False
        if ref_ok:
            dev_bps = abs(price - ref_price) / ref_price * 1e4
            collar = (self.limits.exit_collar_bps if is_exit
                      else self.limits.entry_collar_bps)
            if dev_bps > collar:
                if is_exit:
                    lo = ref_price * (1 - collar / 1e4)
                    hi = ref_price * (1 + collar / 1e4)
                    new_price = min(max(price, lo), hi)
                    notes.append(tag(Code.FW_COLLAR_CLAMP,
                                     f"exit px {price:.10g} outside "
                                     f"{collar:.0f}bps of ref "
                                     f"{ref_price:.10g} -> {new_price:.10g}"))
                    self._count(Code.FW_COLLAR_CLAMP)
                    price, clamped = new_price, True
                else:
                    return self._reject(
                        seq, [tag(Code.FW_COLLAR_REJECT,
                                  f"px {price:.10g} deviates {dev_bps:.0f}bps"
                                  f" from ref {ref_price:.10g} "
                                  f"(> {collar:.0f}bps)")],
                        pair, side, purpose, price, size, alert_key="collar")
        # ref invalid: entries already rejected in _validate (FW-060);
        # exits proceed without collar screening, note attached.

        # ---- REQ-FW-06: notional ceilings --------------------------------
        cap = self.limits.max_order_usd
        if eq_ok:
            cap = min(cap, equity * self.limits.max_order_pct_equity / 100.0
                      * (2 if is_exit else 1))   # exits may close 2x legacy risk
        notional = price * size
        if notional > cap + _EPS:
            if is_exit:
                size = cap / max(price, _EPS)
                notes.append(tag(Code.FW_NOTIONAL_CLAMP,
                                 f"exit notional ${notional:,.0f} clamped "
                                 f"to ${cap:,.0f}"))
                self._count(Code.FW_NOTIONAL_CLAMP)
                clamped = True
            else:
                return self._reject(
                    seq, [tag(Code.FW_NOTIONAL_REJECT,
                              f"notional ${notional:,.0f} > cap "
                              f"${cap:,.0f}")],
                    pair, side, purpose, price, size, alert_key="notional")

        # ---- commit: only accepted orders consume budget / dupe slot -----
        self._submits.append(t)
        self._recent[fp] = t
        self._prune_recent(t)
        disp = Disposition.ACCEPT_MODIFIED if clamped else Disposition.ACCEPT
        return self._emit(seq, disp, price, size, clamped, notes,
                          pair, side, purpose)

    # ------------------------------------------------------------------
    def _validate(self, pair, side, purpose, price, size, ref_price,
                  equity, is_exit, notes):
        if not isinstance(pair, str) or not pair or side not in _SIDES \
                or purpose not in _PURPOSES:
            return False, price, size, [tag(
                Code.FW_INVALID_FIELD,
                f"pair/side/purpose = {pair!r}/{side!r}/{purpose!r}")]

        ref_ok = isinstance(ref_price, (int, float)) \
            and math.isfinite(ref_price) and ref_price > 0
        price_ok = isinstance(price, (int, float)) \
            and math.isfinite(price) and price > 0
        if not price_ok:
            if is_exit and ref_ok:
                notes.append(tag(Code.FW_EXIT_PRICE_SUB,
                                 f"invalid exit px {price!r} replaced with "
                                 f"ref {ref_price:.10g}"))
                self._count(Code.FW_EXIT_PRICE_SUB)
                price = float(ref_price)
            else:
                return False, price, size, [tag(
                    Code.FW_INVALID_PRICE,
                    f"price={price!r} not finite/positive and no valid "
                    f"reference to substitute")]

        if not (isinstance(size, (int, float)) and math.isfinite(size)
                and size > 0):
            return False, price, size, [tag(
                Code.FW_INVALID_SIZE, f"size={size!r} not finite/positive")]

        if not ref_ok:
            if is_exit:
                notes.append(tag(Code.FW_NO_REFERENCE,
                                 "no valid mark; exit passes without "
                                 "collar screening"))
            else:
                return False, price, size, [tag(
                    Code.FW_NO_REFERENCE,
                    f"ref_price={ref_price!r} invalid; entry refused "
                    f"(collar unverifiable, fail closed)")]

        if not (isinstance(equity, (int, float)) and math.isfinite(equity)
                and equity > 0):
            if is_exit:
                notes.append(tag(Code.FW_INVALID_EQUITY,
                                 f"equity={equity!r}; absolute USD cap only"))
            else:
                return False, price, size, [tag(
                    Code.FW_INVALID_EQUITY,
                    f"equity={equity!r}; pct-of-equity cap unverifiable, "
                    f"entry refused")]
        return True, float(price), float(size), []

    # ------------------------------------------------------------------
    @staticmethod
    def _fingerprint(pair, side, purpose, price, size):
        # scale-invariant 6-sig-fig quantization: round(x, 4) breaks on
        # 1e5 BTC prices and 1e-6 alt prices alike
        return (pair, side, purpose,
                float(f"{price:.6g}"), float(f"{size:.6g}"))

    def _prune_recent(self, t):
        cutoff = t - self.limits.dupe_window_sec
        stale = [k for k, ts in self._recent.items() if ts < cutoff]
        for k in stale:                              # bounded by table size
            del self._recent[k]
        while len(self._recent) > _RECENT_CAP:       # bounded: cap+1 max
            del self._recent[min(self._recent, key=lambda k: self._recent[k])]

    def _count(self, code: Code):
        self._counters[code.value] = self._counters.get(code.value, 0) + 1

    def _emit(self, seq, disp, price, size, clamped, notes,
              pair, side, purpose) -> FirewallVerdict:
        key = ("accepted_modified" if disp is Disposition.ACCEPT_MODIFIED
               else "accepted")
        self._counters[key] += 1
        quiet = getattr(self, "_quiet", False)
        lvl = logging.WARNING if clamped else logging.INFO
        if not quiet:
            log.log(lvl, "AUDIT seq=%06d disp=%s pair=%s side=%s purpose=%s "
                    "px=%.10g sz=%.10g notes=%s", seq, disp.value, pair,
                    side, purpose, price, size, notes or "-")
        if clamped and not quiet:
            # counted=True: every note was built with tag() at its own
            # emission point above (the FW-051/041 clamps plus any riding
            # exit notes) and is already in the tally — this audit record
            # summarizes the same emission(s)
            # a dual-clamped exit (collar AND notional in one check()) gets
            # ONE record whose top-level code prefers FW-051, so code-field
            # filters over audit.jsonl would miss the FW-041. "codes" is
            # EVERY REGISTERED CODE riding this emission - not only the
            # clamps: an advisory that also appended a note (FW-030
            # duplicate-exit, FW-021 rate-override) rides along too, and
            # codes[0] is therefore NOT necessarily the primary clamp.
            # Read it as a set, never positionally.
            # Membership-filtered against the Code registry (adversarial
            # review 2026-08-21, N3): the split is prose-scraping, so
            # "stale book at 12:30 UTC" minted a fake "stale book at 12"
            # code into a hash-chained record that verify_chain still
            # returns ok=True on and that can never be corrected in place.
            # All seven appenders route through tag() today - this keeps
            # that latent rather than trusting it.
            get_audit().log("firewall", Code.FW_COLLAR_CLAMP
                            if any("FW-051" in n for n in notes)
                            else Code.FW_NOTIONAL_CLAMP,
                            "; ".join(notes),
                            {"pair": pair, "side": side, "purpose": purpose,
                             "px": price, "sz": size, "seq": seq,
                             "codes": [c for c in dict.fromkeys(
                                 n.split(":", 1)[0] for n in notes
                                 if ":" in n) if c in _REGISTERED_CODES]},
                            counted=True)
        return FirewallVerdict(allowed=True, price=price, size=size,
                               disposition=disp, clamped=clamped,
                               reasons=tuple(notes), seq=seq,
                               ts_wall=time.time())

    def _reject(self, seq, reasons, pair, side, purpose, price, size,
                alert_key: str = "validation") -> FirewallVerdict:
        self._counters["rejected"] += 1
        for r in reasons:
            code = r.split(":", 1)[0]
            self._counters[code] = self._counters.get(code, 0) + 1
        msg = f"{pair} {side} {purpose} px={price!r} sz={size!r} :: " \
              + "; ".join(reasons)
        if not getattr(self, "_quiet", False):
            log.error("AUDIT seq=%06d disp=REJECT %s", seq, msg)
            # counted=True: every reason was built with tag() at its own
            # emission point (this SAME reject) and is already in the tally;
            # the audited code here is reasons[0]'s prefix re-passed as a
            # bare string, and re-bumping it would double-count the reject
            get_audit().log("firewall", reasons[0].split(":", 1)[0], msg,
                            {"seq": seq}, counted=True)
        if self.alerts is not None:
            self.alerts.fire(f"firewall_{alert_key}", msg, level="ERROR")
        return FirewallVerdict(allowed=False, price=price, size=size,
                               disposition=Disposition.REJECT,
                               reasons=tuple(reasons), seq=seq,
                               ts_wall=time.time())

    def _fault_verdict(self, purpose, price, size, seq=None):
        seq = seq if seq is not None else self._seq
        if purpose == "exit":
            # fail safe: a broken screen must not trap open risk
            self._counters["accepted_modified"] += 1
            self._count(Code.FW_FAULT_DEGRADED)
            log.warning("AUDIT seq=%06d disp=ACCEPT_MODIFIED code=%s "
                        "FAULT latched — exit passed UNSCREENED",
                        seq, Code.FW_FAULT_DEGRADED.value)
            return FirewallVerdict(
                allowed=True, price=price, size=size,
                disposition=Disposition.ACCEPT_MODIFIED,
                reasons=(tag(Code.FW_FAULT_DEGRADED,
                             "firewall FAULT — exit passed without "
                             "screening"),),
                seq=seq, ts_wall=time.time())
        self._counters["rejected"] += 1
        self._count(Code.FW_FAULT_REJECT)
        msg = tag(Code.FW_FAULT_REJECT,
                  f"firewall FAULT latched ({self._fault}); new risk "
                  f"refused until reset_fault()")
        log.error("AUDIT seq=%06d disp=REJECT %s", seq, msg)
        if self.alerts is not None:
            self.alerts.fire("firewall_fault", msg, level="ERROR")
        return FirewallVerdict(allowed=False, price=price, size=size,
                               disposition=Disposition.REJECT,
                               reasons=(msg,), seq=seq, ts_wall=time.time())

    # ------------------------------------------------------------------
    # REQ-FW-08: power-on built-in test on a shadow instance
    # ------------------------------------------------------------------
    def self_test(self) -> list:
        lim = replace(self.limits, enabled=True)
        shadow = RiskFirewall.__new__(RiskFirewall)
        shadow.limits = lim
        shadow.alerts = None
        shadow._quiet = True
        shadow._seq = 0
        shadow._fault = None
        shadow._submits = deque(maxlen=lim.max_orders_per_min * 2)
        shadow._recent = {}
        shadow._counters = {"screened": 0, "accepted": 0,
                            "accepted_modified": 0, "rejected": 0}
        eq = lim.max_order_usd * 1_000
        ref = 100.0
        good_sz = min(lim.max_order_usd * 0.5,
                      eq * lim.max_order_pct_equity / 100.0 * 0.5) / ref
        failures, t = [], 0.0

        def run(name, expect_allowed, expect_clamped=None, **kw):
            nonlocal t
            t += 1.0
            v = shadow.check(now=t, **kw)
            if v.allowed != expect_allowed or \
                    (expect_clamped is not None
                     and v.clamped != expect_clamped):
                failures.append(f"{name}: allowed={v.allowed} "
                                f"clamped={v.clamped} reasons={v.reasons}")

        run("sane entry passes", True, False, pair="PBIT-1/USD", side="buy",
            purpose="entry", price=ref, size=good_sz, ref_price=ref,
            equity=eq)
        run("collar violation rejects entry", False, pair="PBIT-2/USD",
            side="buy", purpose="entry", price=ref * 3, size=good_sz,
            ref_price=ref, equity=eq)
        run("NaN price rejects entry", False, pair="PBIT-3/USD", side="buy",
            purpose="entry", price=float("nan"), size=good_sz,
            ref_price=ref, equity=eq)
        run("NaN ref rejects entry", False, pair="PBIT-4/USD", side="buy",
            purpose="entry", price=ref, size=good_sz,
            ref_price=float("nan"), equity=eq)
        run("oversize exit clamps", True, True, pair="PBIT-5/USD",
            side="sell", purpose="exit", price=ref,
            size=lim.max_order_usd * 4 / ref, ref_price=ref, equity=eq)
        if lim.dupe_window_sec > 0:
            kw = dict(pair="PBIT-6/USD", side="buy", purpose="entry",
                      price=ref, size=good_sz, ref_price=ref, equity=eq)
            run("dupe first passes", True, **kw)
            run("dupe second rejects", False, **kw)
        return failures
