"""core/skimmer.py — asset skimmer: watch a candidate pool beyond the core
six, rank tradability, and PROMOTE the best into the active universe.

Why it exists: the meta-model is GLOBAL (58 asset-relative features, no asset
identity), so every additional tradable asset multiplies label flow — breadth
is the cheapest learning accelerator. But risk capacity (5 slots, 35% heat) is
fixed, and the Kraken REST fallback budget caps a safe universe at ~12 pairs
(3 req/s: N books x 6 fast cycles + tickers + candles per 30s window). So the
skimmer scans WIDE and trades NARROW: core pairs are permanent, and at most
`max_extra` candidates are promoted on merit.

Design constraints (all deliberate):
  * WATCHING IS NEARLY FREE — one candidate is evaluated per call (round-robin,
    each at most once per eval_every_min), costing <= 2 REST calls (book +
    candles) per slow cycle regardless of pool size.
  * PROMOTION APPLIES AT BOOT, not mid-flight. evaluate() persists the
    promoted set to outputs/skimmer_active.json; runner.main() (the LIVE
    entrypoint ONLY) merges it into trading_pairs before the bot is built.
    Replay/smoke/overfit construct LiquidityBot(cfg) directly and can never
    see promotions — the quant battery stays pinned to its recorded universe.
    Mid-flight universe mutation in a live engine is a wedge factory (stale
    caches, partial WS subscriptions, iteration-during-mutation); a restart
    boundary makes activation atomic, and restarts already happen naturally
    (auto-updater, session hooks) with full snapshot/restore.
  * HYSTERESIS, NOT CHURN — promote at promote_score, demote only after
    demote_evals consecutive scores below demote_score, replace an incumbent
    only when beaten by replace_margin.
  * A demoted asset only stops taking NEW entries (it leaves the boot
    universe at the next restart); an open position's exits are never touched
    (invariant 5 — exits always run for whatever is on the book).
  * The skimmer never trades. Promoted assets enter through the SAME boot
    path as the core six and face every existing rail: pretrade EV gate,
    sizer, protocols, heat, firewall, manip gate.

Scoring (thresholds live in config, guarded in config_guard — no fitted
literals in the module):
  spread_score   1 at zero spread, 0 at spread_bps_max      (cost floor)
  depth_score    0 below min_depth_usd, saturates at 4x     (can we size in)
  activity_score avg 5m bar range vs activity_range_pct     (anything to capture)
  score = 0.40*spread + 0.35*depth + 0.25*activity — composition weights are
  structural (documented here), the THRESHOLDS are the tunables.
"""
import logging
import math
import time
from pathlib import Path

from core.runtime import atomic_write_json
from core.sanitize import safe_float as _f

log = logging.getLogger("liquiditybot.core.skimmer")

EPS = 1e-9
# structural composition of the three sub-scores (documented above)
_W_SPREAD, _W_DEPTH, _W_ACTIVITY = 0.40, 0.35, 0.25


def score_candidate(spread_bps, depth_usd, bar_range_pct, *,
                    spread_bps_max: float, min_depth_usd: float,
                    activity_range_pct: float) -> float:
    """Tradability score in [0, 1]. Pure — unit-tested directly."""
    spread_bps = _f(spread_bps, spread_bps_max)
    depth_usd = _f(depth_usd)
    bar_range_pct = _f(bar_range_pct)
    if depth_usd < min_depth_usd:            # can't even size a min ticket in
        return 0.0
    spread_score = min(max(1.0 - spread_bps / max(spread_bps_max, EPS), 0.0),
                       1.0)
    depth_score = min(depth_usd / max(4.0 * min_depth_usd, EPS), 1.0)
    activity_score = min(max(bar_range_pct, 0.0)
                         / max(activity_range_pct, EPS), 1.0)
    return round(_W_SPREAD * spread_score + _W_DEPTH * depth_score
                 + _W_ACTIVITY * activity_score, 4)


def book_metrics(book: dict) -> tuple:
    """(spread_bps, depth_usd) from a Kraken-style book; (None, 0) if unusable.
    Depth = summed notional of the top 10 levels BOTH sides."""
    try:
        bids, asks = book.get("bids") or [], book.get("asks") or []
        bb, ba = float(bids[0][0]), float(asks[0][0])
        if not (math.isfinite(bb) and math.isfinite(ba) and 0 < bb < ba):
            return None, 0.0
        mid = 0.5 * (bb + ba)
        spread_bps = (ba - bb) / mid * 1e4
        depth = 0.0
        for side in (bids, asks):
            for row in side[:10]:
                px, sz = float(row[0]), float(row[1])
                if math.isfinite(px) and math.isfinite(sz) and px > 0 < sz:
                    depth += px * sz
        return spread_bps, depth
    except (TypeError, ValueError, IndexError):
        return None, 0.0


def avg_bar_range_pct(candles: list, n: int = 48) -> float:
    """Mean (high-low)/close % over the last n 5m bars; 0 if unusable."""
    out = []
    for c in (candles or [])[-n:]:
        try:
            hi, lo, cl = float(c["high"]), float(c["low"]), float(c["close"])
            if math.isfinite(hi) and math.isfinite(lo) and math.isfinite(cl) \
                    and cl > 0 and hi >= lo:
                out.append((hi - lo) / cl * 100.0)
        except (TypeError, ValueError, KeyError):
            continue
    return sum(out) / len(out) if out else 0.0


class AssetSkimmer:
    def __init__(self, config: dict, feed, core_pairs: list,
                 active_path: str = "outputs/skimmer_active.json"):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.feed = feed
        self.core = [str(p) for p in (core_pairs or [])]
        self.active_path = Path(active_path)
        # candidate pool minus anything already core
        self.candidates = [str(p) for p in (cfg.get("candidates") or [])
                           if str(p) not in self.core]
        self.max_extra = max(int(cfg.get("max_extra", 6)), 0)
        self.eval_every_s = max(_f(cfg.get("eval_every_min", 60.0), 60.0),
                                1.0) * 60.0
        self.spread_bps_max = max(_f(cfg.get("spread_bps_max", 25.0), 25.0),
                                  1.0)
        self.min_depth_usd = max(_f(cfg.get("min_depth_usd", 5000.0), 5000.0),
                                 0.0)
        self.activity_range_pct = max(
            _f(cfg.get("activity_range_pct", 0.30), 0.30), 0.01)
        self.promote_score = min(max(
            _f(cfg.get("promote_score", 0.55), 0.55), 0.0), 1.0)
        self.demote_score = min(max(
            _f(cfg.get("demote_score", 0.35), 0.35), 0.0), self.promote_score)
        self.demote_evals = max(int(cfg.get("demote_evals", 3)), 1)
        self.replace_margin = max(_f(cfg.get("replace_margin", 0.10), 0.10),
                                  0.0)
        self._scores: dict = {}          # pair -> {"score","spread_bps",...}
        self._last_eval: dict = {}       # pair -> ts
        self._strikes: dict = {}         # pair -> consecutive weak evals
        self._promoted: list = []        # ordered, best-effort persisted
        self._rr = 0
        self._restore()

    # ------------------------------------------------------------------
    def _restore(self) -> None:
        """Adopt a previously persisted promotion set (validated)."""
        self._promoted = self.load_active(self.active_path, self.core,
                                          self.max_extra)

    @staticmethod
    def load_active(path, core_pairs: list, cap: int) -> list:
        """Validated promoted list from disk — the BOOT-MERGE reader. Never
        raises; anything malformed yields []. Only 'X/USD' spot strings that
        are not already core, capped at `cap`."""
        try:
            import json
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            raw = data.get("extra_pairs") or []
        except Exception:
            return []
        core = set(str(p) for p in (core_pairs or []))
        out = []
        for p in raw:
            if not isinstance(p, str) or p in core or p in out:
                continue
            base, sep, quote = p.partition("/")
            if sep and quote == "USD" and base.isalnum() and 2 <= len(base) <= 8:
                out.append(p)
        return out[:max(int(cap), 0)]

    # ------------------------------------------------------------------
    def _due(self, now: float) -> str | None:
        """Next candidate owed an evaluation (round-robin), or None."""
        n = len(self.candidates)
        for i in range(n):
            pair = self.candidates[(self._rr + i) % n]
            last = self._last_eval.get(pair)
            # never evaluated -> due NOW (a fresh candidate must not wait a
            # full eval interval measured from epoch zero)
            if last is None or now - last >= self.eval_every_s:
                self._rr = (self._rr + i + 1) % n
                return pair
        return None

    def evaluate(self, now: float | None = None) -> str:
        """Evaluate AT MOST ONE candidate (<= 2 REST calls). Returns an
        outcome string for logs/tests. Never raises."""
        if not (self.enabled and self.candidates and self.feed is not None):
            return "disabled"
        now = now if now is not None else time.time()
        pair = self._due(now)
        if pair is None:
            return "idle"
        self._last_eval[pair] = now
        try:
            rest_pair = self.feed.kraken_pair(pair)
            book = self.feed.get_order_book(rest_pair, depth=10)
            candles = self.feed.get_candles(rest_pair)
        except Exception:
            log.exception("skimmer: feed error evaluating %s", pair)
            return "feed_error"
        spread_bps, depth_usd = book_metrics(book or {})
        rng = avg_bar_range_pct(candles or [])
        if spread_bps is None:
            score = 0.0
        else:
            score = score_candidate(
                spread_bps, depth_usd, rng,
                spread_bps_max=self.spread_bps_max,
                min_depth_usd=self.min_depth_usd,
                activity_range_pct=self.activity_range_pct)
        self._scores[pair] = {
            "score": score,
            "spread_bps": round(spread_bps, 2) if spread_bps is not None
            else None,
            "depth_usd": round(depth_usd, 0),
            "bar_range_pct": round(rng, 4),
            "ts": round(now, 0),
        }
        return self._reconcile(pair, score, now)

    # ------------------------------------------------------------------
    def _reconcile(self, pair: str, score: float, now: float) -> str:
        """Apply promotion/demotion hysteresis for ONE fresh score."""
        changed = False
        if pair in self._promoted:
            if score < self.demote_score:
                self._strikes[pair] = self._strikes.get(pair, 0) + 1
                if self._strikes[pair] >= self.demote_evals:
                    self._promoted.remove(pair)
                    self._strikes.pop(pair, None)
                    changed, outcome = True, "demoted"
                    log.warning("skimmer: DEMOTED %s (score %.2f < %.2f for "
                                "%d evals) — leaves the universe at next "
                                "restart; open positions keep their exits",
                                pair, score, self.demote_score,
                                self.demote_evals)
                else:
                    outcome = "strike"
            else:
                self._strikes.pop(pair, None)
                outcome = "held"
        elif score >= self.promote_score:
            if len(self._promoted) < self.max_extra:
                self._promoted.append(pair)
                changed, outcome = True, "promoted"
                log.info("skimmer: PROMOTED %s (score %.2f) — active at next "
                         "restart", pair, score)
            else:
                worst = min(self._promoted,
                            key=lambda p: self._scores.get(p, {})
                            .get("score", 0.0))
                if score >= self._scores.get(worst, {}).get("score", 0.0) \
                        + self.replace_margin:
                    self._promoted.remove(worst)
                    self._promoted.append(pair)
                    self._strikes.pop(worst, None)
                    changed, outcome = True, "replaced"
                    log.info("skimmer: %s REPLACED %s (%.2f beats %.2f by "
                             ">= %.2f)", pair, worst, score,
                             self._scores.get(worst, {}).get("score", 0.0),
                             self.replace_margin)
                else:
                    outcome = "eligible_full"
        else:
            outcome = "scored"
        if changed:
            self._persist(now)
        return outcome

    def _persist(self, now: float) -> None:
        try:
            atomic_write_json(self.active_path, {
                "version": 1, "updated": round(now, 0),
                "extra_pairs": list(self._promoted),
                "scores": {p: self._scores.get(p, {}) for p in self._promoted},
            })
        except Exception:
            log.exception("skimmer: persist failed — promotions hold in "
                          "memory, retry on next change")

    # ------------------------------------------------------------------
    def snapshot(self) -> dict:
        return {"enabled": self.enabled,
                "candidates": len(self.candidates),
                "promoted": list(self._promoted),
                "max_extra": self.max_extra,
                "scores": dict(self._scores)}
