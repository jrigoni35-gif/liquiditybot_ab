"""
strategies/informed_flow.py — informed-flow signal engine, rev 3
(Evidence-Fusion Build)

rev 2 confirmed on a hard AND of five binary gates. That throws away
magnitude (a 5/5 of marginal passes outranked a 4/5 of screaming
passes) and makes recall a cliff function of five independent
thresholds. rev 3 keeps every economic idea — and every veto — but
fuses the DIRECTIONAL evidence continuously:

  E = Σ w_i · s_i,   s_i ∈ [-1, +1] signed component scores

  s_flow   EWMA of log book-imbalance (persistence *with* magnitude —
           Cont/Kukanov/Stoikov lineage)
  s_delta  fast-vs-slow imbalance EWMA spread: order-flow-imbalance
           CHANGE. New pressure, not just standing pressure.
  s_accum  volume-weighted close-location value over the lookback:
           net accumulation(+)/distribution(−) in [-1, 1].
  s_burst  robust (median/MAD) volume z, direction-signed by the
           latest bar's CLV. Informed bursts close at their extreme.
  s_trend  EMA(fast) − EMA(slow) distance normalized by bar vol —
           trend strength, not just trend sign.

A signal confirms only when ALL of:
  C1  |E| ≥ evidence_threshold
  C2  ≥ min_agree components materially agree with sign(E)
  C3  the flow component itself agrees and |s_flow| ≥ flow_min
      (this is an informed-FLOW engine; nothing fires without flow)
  V1  |funding| ≤ cap                                  (veto)
  V2  no absorption: material price move against material
      accumulation sign is the trap, not the trade      (veto)
  V3  data sufficiency (bars for slow EMA + AD lookback)

Confirmed signals emit confidence = 1.0 (contract preserved for the
cold-start prior downstream) and a continuous URGENCY in [0,1] built
from burst share, flow freshness and delta pressure — consumed by
execution/tactics.py exactly as before.

Interface-identical to rev 2 / SignalGateEngine:
    evaluate_asset(asset, view) -> SignalResult
Per-asset state is O(1) incremental (EMAs fold in only new bars).
Fully defensive: malformed views fail closed, never raise.
rev-2 config keys are all honored; new keys default to a strictness
at least equal to rev 2. Rollback: strategies.engine = "five_gate".
"""

import logging
import math
from collections import deque

from strategies.signal_gates import SignalResult

log = logging.getLogger("liquiditybot.strategies.informed_flow")


def _f(x, default=0.0) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _clv(candle: dict) -> float:
    """Close location value in [0,1]; 0.5 fail-safe for degenerate bars."""
    c = _f(candle.get("close"))
    h = _f(candle.get("high"), c)
    lo = _f(candle.get("low"), c)
    if h <= lo or c <= 0:
        return 0.5
    return min(max((c - lo) / (h - lo), 0.0), 1.0)


def _tanh(x: float) -> float:
    return math.tanh(x)


class _AssetState:
    """O(1) incremental per-asset state. EMAs fold in only bars that
    are new since the last evaluation; any history rewrite (shorter
    list / changed tail) triggers a clean full rebuild."""

    __slots__ = ("ema_f", "ema_s", "n_seen", "last_close", "last_len",
                 "imb_hist", "streak_dir", "streak")

    def __init__(self, imb_maxlen: int):
        self.ema_f = None
        self.ema_s = None
        self.n_seen = 0
        self.last_close = None
        self.last_len = 0
        self.imb_hist = deque(maxlen=imb_maxlen)
        self.streak_dir = 0
        self.streak = 0


def _short_gate(k: str) -> str:
    """Human-readable gate name for the per-asset scan line: strip the
    'if_N_' / 'v3_' family prefix ('if_1_flow_persistence' -> 'flow_persistence',
    'v3_evidence' -> 'evidence')."""
    p = k.split("_")
    if len(p) > 2 and p[0] == "if" and p[1].isdigit():
        return "_".join(p[2:])
    if p and p[0] and p[0][0] == "v" and p[0][1:].isdigit():
        return "_".join(p[1:])
    return k


class InformedFlowEngine:
    def __init__(self, config: dict):
        cfg = config or {}
        # ---- rev-2 keys, all honored --------------------------------
        self.persistence_evals = max(int(cfg.get("persistence_evals", 3)), 1)
        self.min_imbalance_ratio = max(
            _f(cfg.get("min_imbalance_ratio", 1.35), 1.35), 1.01)
        self.ad_lookback_bars = max(int(cfg.get("ad_lookback_bars", 24)), 4)
        self.vol_z_min = max(_f(cfg.get("vol_z_min", 2.0), 2.0), 0.5)
        self.clv_min = min(max(_f(cfg.get("clv_min", 0.60), 0.60), 0.5), 1.0)
        self.max_abs_funding = _f(cfg.get("max_abs_funding_rate", 0.01), 0.01)
        # Funding is a crowding VETO sourced only from OKX perps; Kraken (the
        # sole execution venue) is SPOT and pays no funding. So an unavailable
        # rate is a lost minor filter, never an unhedged cost — default to
        # PASSING the veto (keep trading) rather than starving entries on a
        # single-feed outage. Set false for strict fail-closed.
        self.funding_pass_when_unavailable = bool(
            cfg.get("funding_pass_when_unavailable", True))
        self.fast_period = max(int(cfg.get("fast_period", 9)), 2)
        self.slow_period = max(int(cfg.get("slow_period", 21)),
                               self.fast_period + 1)
        # ---- rev-3 fusion keys (defaults >= rev-2 strictness) --------
        self.evidence_threshold = max(
            _f(cfg.get("evidence_threshold", 1.15), 1.15), 0.05)
        self.min_agree = max(int(cfg.get("min_agree", 3)), 1)
        self.flow_min = min(max(_f(cfg.get("flow_min", 0.25), 0.25), 0.0), 1.0)
        self.absorption_ad_min = _f(cfg.get("absorption_ad_min", 0.15), 0.15)
        self.absorption_move_sigmas = _f(
            cfg.get("absorption_move_sigmas", 1.0), 1.0)
        # a component "votes" when |s_i| >= this (CLAUDE.md: no fitted-
        # looking literals in decision paths - lifted with identical
        # default, was module-level _MATERIAL = 0.10)
        self.material = min(max(
            _f(cfg.get("material_threshold", 0.10), 0.10), 0.0), 1.0)
        w = cfg.get("weights") or {}
        self.w = {
            "flow":  _f(w.get("flow", 1.00), 1.00),
            "delta": _f(w.get("delta", 0.60), 0.60),
            "accum": _f(w.get("accum", 0.90), 0.90),
            "burst": _f(w.get("burst", 0.80), 0.80),
            "trend": _f(w.get("trend", 0.70), 0.70),
        }
        # urgency composition (lifted literals, identical defaults): urgency =
        # base + w_burst*burst + w_fresh*fresh + w_delta*delta, clamped [0,1].
        # These drive the execution ladder (join/improve/taker in tactics), so
        # they are config knobs, not buried constants. fresh_decay_evals is the
        # streak span over which edge freshness decays to zero.
        u = cfg.get("urgency") or {}
        self.u_base = min(max(_f(u.get("base", 0.30), 0.30), 0.0), 1.0)
        self.u_w_burst = max(_f(u.get("w_burst", 0.40), 0.40), 0.0)
        self.u_w_fresh = max(_f(u.get("w_fresh", 0.20), 0.20), 0.0)
        self.u_w_delta = max(_f(u.get("w_delta", 0.10), 0.10), 0.0)
        self.u_fresh_decay = max(_f(u.get("fresh_decay_evals", 6.0), 6.0), 1.0)
        # opposing-flow tolerance: an opposing imbalance only counts against
        # confirmation past this fraction of the log-threshold
        self.opp_tol_frac = min(max(
            _f(cfg.get("opp_flow_tol_frac", 0.25), 0.25), 0.0), 1.0)
        # EWMA spans: fast = persistence window, slow = 4x (EMA definition —
        # structural, not fitted)
        self._k_imb_f = 2.0 / (self.persistence_evals + 1.0)
        self._k_imb_s = 2.0 / (self.persistence_evals * 4 + 1.0)
        self._log_thresh = math.log(self.min_imbalance_ratio)
        self._st: dict = {}     # asset -> _AssetState
        # OBSERVABILITY ONLY (default off): when on, emit a uniform
        # "IF3 scan" line for EVERY asset every cycle — confirmed, unconfirmed,
        # or data-short alike — so the operator sees each asset's evidence,
        # agreement and failing gates, not just the ones that confirm. It has
        # ZERO influence on the decision path (asserted in tests): the same
        # global thresholds are applied to every asset, and this flag only
        # controls whether that per-asset evaluation is logged.
        self.debug_all_signals = bool(cfg.get("debug_all_signals", False))

    # ------------------------------------------------------------------
    def _state(self, asset: str) -> _AssetState:
        st = self._st.get(asset)
        if st is None:
            st = _AssetState(imb_maxlen=max(16, self.persistence_evals * 4))
            self._st[asset] = st
        return st

    # ---- incremental EMA maintenance -----------------------------------
    def _update_emas(self, st: _AssetState, closes: list) -> None:
        n = len(closes)
        if n == 0:
            return
        rebuilt = (st.last_len == 0 or n < st.last_len or
                   (st.last_close is not None and
                    n == st.last_len and closes[-1] != st.last_close) or
                   n - st.last_len > 500)
        if not rebuilt and n > st.last_len and st.last_len > 0:
            # sanity: the bar we saw last must still be where we left it
            if closes[st.last_len - 1] != st.last_close:
                rebuilt = True
        if rebuilt:
            st.ema_f = st.ema_s = None
            st.n_seen = 0
            start = 0
        else:
            start = st.last_len if n > st.last_len else n  # n==last_len: no-op
        kf = 2.0 / (self.fast_period + 1.0)
        ks = 2.0 / (self.slow_period + 1.0)
        for i in range(start, n):
            c = closes[i]
            st.n_seen += 1
            st.ema_f = c if st.ema_f is None else c * kf + st.ema_f * (1 - kf)
            st.ema_s = c if st.ema_s is None else c * ks + st.ema_s * (1 - ks)
        st.last_len = n
        st.last_close = closes[-1]

    # ---- component scores ------------------------------------------------
    def _s_flow_and_delta(self, st: _AssetState) -> tuple:
        """(s_flow, s_delta, fresh) from the imbalance history EWMAs."""
        if len(st.imb_hist) < self.persistence_evals:
            return 0.0, 0.0, 0.0
        ef = es = None
        for li in st.imb_hist:
            ef = li if ef is None else li * self._k_imb_f + ef * (1 - self._k_imb_f)
            es = li if es is None else li * self._k_imb_s + es * (1 - self._k_imb_s)
        assert ef is not None and es is not None  # loop ran: imb_hist is non-empty here
        s_flow = _tanh(ef / self._log_thresh)
        s_delta = _tanh((ef - es) / (0.5 * self._log_thresh))
        # freshness: shorter streak beyond minimum = fresher edge
        fresh = 1.0 - min(max((st.streak - self.persistence_evals)
                              / self.u_fresh_decay, 0.0), 1.0)
        return s_flow, s_delta, fresh

    def _s_accum(self, candles: list) -> tuple:
        """(s_accum, price_move_dir, move_sigmas) over the AD lookback."""
        window = candles[-self.ad_lookback_bars:]
        num = den = 0.0
        rets = []
        prev = None
        for c in window:
            v = max(_f(c.get("volume")), 0.0)
            num += v * (2.0 * _clv(c) - 1.0)
            den += v
            px = _f(c.get("close"))
            if prev and prev > 0 and px > 0:
                rets.append(math.log(px / prev))
            prev = px
        s_accum = (num / den) if den > 0 else 0.0
        c0 = _f(window[0].get("close"))
        c1 = _f(window[-1].get("close"))
        move = math.log(c1 / c0) if c0 > 0 and c1 > 0 else 0.0
        if len(rets) >= 4:
            mu = sum(rets) / len(rets)
            sd = math.sqrt(sum((r - mu) ** 2 for r in rets) / len(rets))
        else:
            sd = 0.0
        move_sig = abs(move) / (sd * math.sqrt(max(len(window) - 1, 1)) + 1e-12) \
            if sd > 0 else 0.0
        return max(-1.0, min(1.0, s_accum)), (1 if move > 0 else -1), move_sig

    def _s_burst(self, candles: list) -> tuple:
        """(s_burst, z) — robust volume z (median/MAD, 48-bar window,
        12-bar rev-2 fallback) signed by the latest bar's CLV."""
        n = len(candles)
        if n < 13:
            return 0.0, 0.0
        w = min(48, n - 1)
        vols = sorted(_f(c.get("volume")) for c in candles[-(w + 1):-1])
        m = len(vols)
        med = vols[m // 2] if m % 2 else 0.5 * (vols[m // 2 - 1] + vols[m // 2])
        mad = sorted(abs(v - med) for v in vols)
        madv = mad[m // 2] if m % 2 else 0.5 * (mad[m // 2 - 1] + mad[m // 2])
        scale = 1.4826 * madv
        if scale <= 0:                       # flat window: mean/sd fallback
            mu = sum(vols) / m
            var = sum((v - mu) ** 2 for v in vols) / m
            scale, med = math.sqrt(var), mu
        latest = candles[-1]
        z = (_f(latest.get("volume")) - med) / scale if scale > 0 else 0.0
        if z <= 0:
            return 0.0, z
        dir_term = 2.0 * _clv(latest) - 1.0      # [-1, 1]
        return _tanh(z / self.vol_z_min) * dir_term, z

    def _s_trend(self, st: _AssetState, candles: list) -> float:
        if st.ema_f is None or st.ema_s is None or \
                st.n_seen < self.slow_period:
            return 0.0
        px = _f(candles[-1].get("close"))
        if px <= 0:
            return 0.0
        # normalize EMA spread by expected move over the slow span
        rets = []
        prev = None
        for c in candles[-33:]:
            p = _f(c.get("close"))
            if prev and prev > 0 and p > 0:
                rets.append(math.log(p / prev))
            prev = p
        if len(rets) >= 8:
            mu = sum(rets) / len(rets)
            sig = math.sqrt(sum((r - mu) ** 2 for r in rets) / len(rets))
        else:
            sig = 0.0
        denom = px * (sig * math.sqrt(self.slow_period) + 1e-9)
        return _tanh((st.ema_f - st.ema_s) / denom)

    # ------------------------------------------------------------------
    def evaluate_asset(self, base_asset: str, view: dict | None) -> SignalResult:
        view = view or {}
        symbol = view.get("kraken_symbol", base_asset)
        try:
            return self._evaluate(base_asset, symbol, view)
        except Exception:
            log.exception("informed-flow evaluation fault for %s — "
                          "signal fails closed", base_asset)
            return SignalResult(symbol=symbol, direction=None,
                                confidence=0.0, size=0.0,
                                all_confirmed=False, gates_passed={})

    def _evaluate(self, asset: str, symbol: str, view: dict) -> SignalResult:
        st = self._state(asset)
        candles = view.get("candles") or []
        closes = [_f(c.get("close")) for c in candles]

        # ---- imbalance history + streak (kept for urgency/freshness)
        ratio = max(_f(view.get("imbalance_ratio"), 1.0), 1e-3)
        li = math.log(ratio)
        st.imb_hist.append(li)
        d = 1 if li >= self._log_thresh else (-1 if li <= -self._log_thresh else 0)
        if d != 0 and d == st.streak_dir:
            st.streak += 1
        else:
            st.streak_dir, st.streak = d, (1 if d != 0 else 0)

        # ---- V3 data sufficiency ------------------------------------
        min_bars = max(self.slow_period + 2, self.ad_lookback_bars + 1, 14)
        if len(candles) < min_bars:
            if self.debug_all_signals:
                log.info("IF3 scan %-4s: WARMUP insufficient data "
                         "(bars=%d < %d) — not yet evaluated",
                         asset, len(candles), min_bars)
            return SignalResult(symbol=symbol, direction=None,
                                confidence=0.0, size=0.0,
                                all_confirmed=False,
                                gates_passed={"v3_data_sufficiency": False})

        self._update_emas(st, closes)

        # ---- components ----------------------------------------------
        s_flow, s_delta, fresh = self._s_flow_and_delta(st)
        s_accum, move_dir, move_sig = self._s_accum(candles)
        s_burst, vol_z = self._s_burst(candles)
        s_trend = self._s_trend(st, candles)
        comps = {"flow": s_flow, "delta": s_delta, "accum": s_accum,
                 "burst": s_burst, "trend": s_trend}

        evidence = sum(self.w[k] * v for k, v in comps.items())
        direction = "long" if evidence > 0 else "short"
        sgn = 1 if evidence > 0 else -1

        # ---- vetoes ----------------------------------------------------
        # unavailable funding (OKX perp feed down): explicit policy, not the
        # silent _f(None)->0 coincidence. Default passes (see __init__).
        if not view.get("funding_available", True) \
                and self.funding_pass_when_unavailable:
            funding_ok = True
        else:
            funding_ok = abs(_f(view.get("funding_rate"))) <= self.max_abs_funding
        absorption = (move_sig >= self.absorption_move_sigmas and
                      abs(s_accum) >= self.absorption_ad_min and
                      (1 if s_accum > 0 else -1) != move_dir)
        # trading INTO the absorbed side is the trap; fading it is not
        absorption_veto = absorption and (sgn == move_dir)

        # ---- confirmation ----------------------------------------------
        agree = sum(1 for v in comps.values()
                    if abs(v) >= self.material and (1 if v > 0 else -1) == sgn)
        # anti-spoof invariant (restores the rev-2 guarantee the fusion
        # rewrite lost): informed flow does not flip sides bar-to-bar —
        # spoofers do. Any MATERIALLY opposing print (>= 25% of the
        # imbalance threshold, against the EWMA's sign) inside the
        # persistence window disqualifies the flow gate outright, however
        # strong the final print leaves the average. Sub-material flutter
        # around 1.0 stays neutral and does not count against.
        opp_tol = self.opp_tol_frac * self._log_thresh
        window = list(st.imb_hist)[-self.persistence_evals:]
        opposing = any(li * s_flow < 0 and abs(li) >= opp_tol
                       for li in window) if s_flow != 0.0 else False
        flow_ok = abs(s_flow) >= self.flow_min and \
            (1 if s_flow > 0 else -1) == sgn and not opposing
        strength = abs(evidence)
        all_confirmed = (strength >= self.evidence_threshold and
                         agree >= self.min_agree and flow_ok and
                         funding_ok and not absorption_veto)

        gates = {
            "if_1_flow_persistence": abs(s_flow) >= self.flow_min and
                                     not opposing,
            "if_2_accumulation": abs(s_accum) >= self.material and
                                 not absorption_veto,
            "if_3_directional_burst": abs(s_burst) >= self.material,
            "if_4_funding_sanity": funding_ok,
            "if_5_trend_alignment": abs(s_trend) >= self.material,
            "v3_evidence": strength >= self.evidence_threshold,
            "v3_agreement": agree >= self.min_agree,
            "v3_no_absorption": not absorption_veto,
        }

        confidence = 1.0 if all_confirmed else \
            round(min(strength / self.evidence_threshold, 0.99), 3)

        if self.debug_all_signals:
            # uniform per-asset telemetry: SAME fields for every asset so no
            # name is privileged. Confirmed -> no FAIL suffix; otherwise the
            # exact gate(s) blocking it. Pure logging; the decision above is
            # already fully computed and unaffected.
            failed = [_short_gate(k) for k, v in gates.items() if not v]
            log.info("IF3 scan %-4s %-5s: E=%+.2f agree=%d/5 flow=%+.2f "
                     "delta=%+.2f accum=%+.2f burst=%+.2f trend=%+.2f "
                     "conf=%.2f gates=%d/%d%s",
                     asset, direction, evidence, agree, s_flow, s_delta,
                     s_accum, s_burst, s_trend, confidence,
                     sum(1 for v in gates.values() if v), len(gates),
                     "" if not failed else " FAIL:" + ",".join(failed))

        urgency = 0.0
        if all_confirmed:
            burst_pos = max(min(s_burst * sgn, 1.0), 0.0)
            delta_pos = max(min(s_delta * sgn, 1.0), 0.0)
            urgency = min(max(self.u_base + self.u_w_burst * burst_pos
                              + self.u_w_fresh * fresh
                              + self.u_w_delta * delta_pos, 0.0), 1.0)
            log.info("IF3 signal %s %s: E=%+.2f agree=%d/5 flow=%+.2f "
                     "delta=%+.2f accum=%+.2f burst=%+.2f trend=%+.2f "
                     "vol_z=%.1f urgency=%.2f", asset, direction, evidence,
                     agree, s_flow, s_delta, s_accum, s_burst, s_trend,
                     vol_z, urgency)

        return SignalResult(
            symbol=symbol,
            direction=direction if all_confirmed else None,
            confidence=confidence, size=0.0,
            all_confirmed=all_confirmed, gates_passed=gates,
            urgency=urgency)
