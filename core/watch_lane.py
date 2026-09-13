"""core/watch_lane.py - label assets we do NOT trade, to buy information.

WHY THIS EXISTS. Effective n is additive across ASSETS and in nothing else:
per-asset sum == pooled to 1e-6 on the h432 corpus. Rows are ~4x redundant
(every 4th candidate retains 92% of n_eff), and the horizon lever buys only
~1.47x and is cohort-resetting. Information flow has collapsed 4.4x since the
universe narrowed - 42.4 n_eff/day at 15 assets, 9.6 in era-9 at 4. Breadth is
the only lever that scales, and `core/skimmer.py:4-6` already says so.

The skimmer cannot be that lever during an accrual era, because it PROMOTES
into the trading universe, and the universe is a fenced axis. This lane
watches without trading: it scores and labels off-universe assets and writes
them to their OWN corpus, which is not read by the model.

WHAT MAKES IT SAFE, and each of these is pinned in tests/test_watch_lane.py
rather than asserted here. The naive version is NOT safe by construction -
four measured channels carry a watch row back into entry decisioning, and all
four are cut deliberately:

  1. GateStats. The engine's labeler is built with
     `on_label=self.gate_stats.note_label` (main.py:1006) and the resulting
     `weighted_confidence` is applied ON THE ENTRY PATH (main.py:4620), with
     eight of nine shipped weights currently off 1.0. This lane passes
     `on_label=None`. A watch row can never move a gate weight.
  2. HistoryStore.asset_counts(). It splits raw lines and counts the asset
     column with NO filter on book, source or era, and feeds the probe
     taper. A `book` tag would not close it. So this lane writes a SEPARATE
     FILE (WATCH_HISTORY_PATH) and never touches signal_history.csv.
  3. The shared candidate pool. `ml.max_open_candidates` is a single budget;
     overflow drops the NEWEST pending candidate, which would be a real
     universe candidate. This lane carries its own cap under
     `watch_lane.max_open_candidates` and never reads the ml key.
  4. The horizon shadow corpus. `shadow_store=None` keeps
     outputs/horizon_shadow.csv one population.

And the structural one: THE LANE HOLDS NO REFERENCE TO THE BOT. It takes a
config dict and a read-only feed, owns private engine instances, and is
constructed and ticked by the RUNNER, never the engine - mirroring
core/skimmer.AssetSkimmer. The order path is closed independently: every
`orders.submit(` site in main.py resolves through a `symbol_map` built once
at boot from `trading_pairs` and never mutated, so an asset that is not in
`trading_pairs` cannot be ordered. THIS LANE NEVER WRITES `trading_pairs`.

WHAT PHASE 1 DELIBERATELY DOES NOT DO. It does not feed the model. Watch rows
accrue in their own file and nothing loads them for training.

  A NOTE ON TAGGING, because the first draft of this docstring claimed
  something the data did not show. Watch rows are NOT tagged `book="watch"`:
  CandidateLabeler hardcodes `book = "5m"` (ml/history.py:1291) and `register`
  exposes no book parameter, so tagging would mean editing shared
  decision-path-adjacent code for a property the SEPARATE FILE already
  provides more strongly. A tag would only close the training gate;
  `asset_counts()` has no tag filter, so only a distinct path closes it. The
  file is the isolation. Verified on a written row: source=candidate,
  book=5m, label_era=triple_barrier_h432, 95 columns - the same schema as
  signal_history.csv, in a different file. That is not timidity, it is sequencing: watch rows carry a different
feature availability profile (no cross-asset correlation partner, market-wide
states shared rather than per-asset), so pooling them into training is a
CORPUS COMPOSITION change that deserves its own measurement and its own
decision. Accrue first, measure the composition, then decide.

COST. One asset per tick, round-robin, self-throttled by `eval_every_sec`.
Two REST calls per evaluated asset (book + candles) against the venue the bot
already polls. The runner's telemetry block shares the trading loop's thread
and its `elapsed` feeds one sleep, so work here eats cadence headroom
directly: `poll_sec` 5.0 against a ~0.22 s cycle and a 0.25 s sleep floor
leaves roughly 4.75 s before spacing slips. One asset per tick keeps this far
inside that.

SHIPS DISABLED. `watch_lane.enabled` defaults False.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

log = logging.getLogger("liquiditybot.watch_lane")

# The lane's own corpus. A SEPARATE FILE, not a tag on the shared one - see
# channel 2 above. Registered in tests/conftest.py's _REDIRECTED_PATH_ATTRS
# and in scripts/outputs_gc.py's NEVER set in the same commit that introduced
# it, per this repo's own leak-class rule.
WATCH_HISTORY_PATH = "outputs/watch_history.csv"

_DEF_EVAL_EVERY_SEC = 300.0
_DEF_MAX_OPEN = 400
_DEF_DEPTH = 20
_DEF_INTERVAL = 5


class WatchLane:
    """Watch-and-label, never trade. Runner-owned; holds no bot reference."""

    def __init__(self, config: dict, feed, core_pairs: Optional[list] = None):
        cfg = (config or {}).get("watch_lane") or {}
        self.enabled = bool(cfg.get("enabled", False))
        self._feed = feed
        self._eval_every = float(cfg.get("eval_every_sec",
                                         _DEF_EVAL_EVERY_SEC))
        self._depth = int(cfg.get("book_depth", _DEF_DEPTH))
        self._interval = int(cfg.get("candle_interval_min", _DEF_INTERVAL))
        self._last_eval = 0.0
        self._cursor = 0
        self._rows = 0
        self._evals = 0
        self._errors = 0
        self._last_error = ""

        # THE UNIVERSE IS EXCLUDED BY COMPUTATION, NOT BY TRUST. Whatever the
        # operator lists, anything currently traded is dropped - so a careless
        # config entry cannot make this lane shadow a live asset and
        # double-count it into a second corpus.
        traded = set(core_pairs or [])
        if not traded:
            traded = set((config or {}).get("exchanges", {})
                         .get("kraken", {}).get("trading_pairs", []) or [])
        self.core_pairs = sorted(traded)
        self.pairs = [p for p in (cfg.get("pairs") or []) if p not in traded]
        self.excluded = [p for p in (cfg.get("pairs") or []) if p in traded]

        self._store = None
        self._labeler = None
        self._engines_ok = False
        if self.enabled and self.pairs:
            self._build(config, cfg)

    # ------------------------------------------------------------------
    def _build(self, config: dict, cfg: dict) -> None:
        """Private engine instances. Imported lazily so a failure here costs
        the lane and nothing else - the runner already treats this as
        telemetry that must never block boot."""
        try:
            from execution.fair_value import FairValueEngine
            from ml.history import CandidateLabeler, HistoryStore
            from regime.liquidity_regime import LiquidityRegimeEngine
            from regime.macro_regime import MacroRegimeEngine
            from regime.vol_regime import VolRegimeEngine

            ml_cfg = dict((config or {}).get("ml") or {})
            # CHANNEL 3: the lane's own pool cap. Never ml.max_open_candidates.
            ml_cfg["max_open_candidates"] = int(
                cfg.get("max_open_candidates", _DEF_MAX_OPEN))

            self._store = HistoryStore(
                WATCH_HISTORY_PATH,
                max_bars=int(ml_cfg.get("label_max_bars", 432)))
            # CHANNELS 1 and 4: on_label=None cuts GateStats, shadow_store=None
            # keeps horizon_shadow.csv one population. Both are positional-safe
            # defaults; they are passed EXPLICITLY so the cut is visible at the
            # call site and a future signature change cannot reinstate them by
            # accident.
            self._labeler = CandidateLabeler(
                self._store, ml_cfg, on_label=None, shadow_store=None)

            self._fv = FairValueEngine((config or {}).get("fair_value", {}))
            self._vol = VolRegimeEngine((config or {}).get("vol_regime", {}))
            self._liq = LiquidityRegimeEngine(
                (config or {}).get("liquidity_regime", {}))
            self._macro = MacroRegimeEngine((config or {}).get("regime", {}))
            self._engines_ok = True
        except Exception as exc:            # pragma: no cover - boot safety
            self._engines_ok = False
            self._last_error = f"{type(exc).__name__}: {exc}"
            log.exception("watch_lane init failed - lane disabled this boot")

    # ------------------------------------------------------------------
    def _due(self, now: float) -> Optional[str]:
        if not (self.enabled and self._engines_ok and self.pairs):
            return None
        if now - self._last_eval < self._eval_every:
            return None
        pair = self.pairs[self._cursor % len(self.pairs)]
        self._cursor += 1
        self._last_eval = now
        return pair

    def tick(self, now: Optional[float] = None) -> str:
        """Evaluate at most ONE watch asset. Returns an outcome string.

        Never raises: this rides the trading loop's thread, and a watch-lane
        exception must not cost a cycle.
        """
        now = float(now if now is not None else time.time())
        try:
            pair = self._due(now)
            if pair is None:
                return "idle"
            return self._evaluate(pair, now)
        except Exception as exc:            # pragma: no cover - loop safety
            self._errors += 1
            self._last_error = f"{type(exc).__name__}: {exc}"
            log.exception("watch_lane tick failed on a watched asset")
            return "error"

    # ------------------------------------------------------------------
    def _evaluate(self, pair: str, now: float) -> str:
        feed = self._feed
        if feed is None:
            return "no-feed"
        labeler = self._labeler
        if labeler is None:              # _build() failed; _due() already
            return "not-ready"           # gates on _engines_ok, this narrows
        candles = feed.get_candles(pair, interval=self._interval)
        if not candles:
            return "no-candles"
        book = feed.get_order_book(pair, depth=self._depth) or {}
        # Daily bars are a THIRD call, and worth it: MacroRegimeEngine fits its
        # HMM on daily OHLCV, so without them every watch row would carry the
        # default regime one-hot and the rows would differ from live rows on a
        # feature the model actually uses. One asset per 5 min makes three
        # calls trivial against the cadence headroom.
        daily = feed.get_candles(pair, interval=1440) or []

        asset = pair.split("/")[0]
        labeler.update_candles(asset, candles)
        self._evals += 1

        # All four engines share the same shape - update(asset, ...) then
        # state(asset) - and each returns a neutral default for an asset it
        # has never seen, so a first tick degrades to defaults rather than
        # raising. venue_books is [] because this lane has no cross-venue
        # feed; fair value is then Kraken-only, which is a recorded
        # availability difference, not a silent one.
        vol_state = self._vol.update(asset, candles, daily)
        liq_state = self._liq.update(asset, book, book, now)
        self._macro.update(asset, daily)
        macro_state = self._macro.state(asset)
        self._fv.update(asset, [], book, now)
        fv_state = self._fv.state(asset)

        from ml.features import build_features
        view = {"candles": candles,
                "imbalance_ratio": _imbalance(book)}
        # corr_state and sentiment are MARKET-WIDE and live on the engine.
        # Reaching for them would need a bot reference, which is the one thing
        # this lane must not hold, so they are passed as None/absent and
        # build_features' documented defaults apply. That is a real feature
        # availability difference between a watch row and a live row, it is
        # the reason phase 1 does not feed the model, and it is recorded on
        # the row via `avail` rather than left for someone to discover.
        feats = build_features(
            asset=asset, direction="long", gate_confidence=0.0, view=view,
            fv_state=fv_state, vol_state=vol_state, liq_state=liq_state,
            macro_state=macro_state, corr_state=None, sentiment=None,
            smc_feats={}, other_asset=None, extras=None)

        appended = labeler.register(
            asset, "long", feats,
            sigma_bar=float(getattr(vol_state, "sigma_bar_pct", 0.0)) / 100.0,
            bar_time=candles[-1]["time"],
            spread_bps=float(_spread_bps(book)),
            avail={"lane": "watch", "corr": False, "sentiment": False,
                   "cross_venue_fv": False})
        written = labeler.poll(now)
        self._rows += int(written)
        return (f"watched {pair}"
                f"{' +1' if appended else ''}"
                f"{f' labeled {written}' if written else ''}")

    # ------------------------------------------------------------------
    def snapshot(self) -> dict:
        """Folded into status.json by the runner. Numbers only - no paths."""
        return {
            "enabled": bool(self.enabled),
            "ready": bool(self._engines_ok),
            "watched": len(self.pairs),
            "excluded_because_traded": len(self.excluded),
            "evaluations": int(self._evals),
            "rows_labeled": int(self._rows),
            "errors": int(self._errors),
            "last_error": self._last_error[:120],
            # the isolation properties, published so a board can watch them
            # rather than a reader having to trust this docstring
            "feeds_model": False,
            "separate_corpus": True,
        }


# ----------------------------------------------------------------------
def _imbalance(book: dict) -> float:
    bids = (book or {}).get("bids") or []
    asks = (book or {}).get("asks") or []
    bv = sum(float(r[1]) for r in bids[:10] if len(r) > 1)
    av = sum(float(r[1]) for r in asks[:10] if len(r) > 1)
    return (bv / av) if av > 0 else 1.0


def _spread_bps(book: dict) -> float:
    bids = (book or {}).get("bids") or []
    asks = (book or {}).get("asks") or []
    if not bids or not asks:
        return 0.0
    try:
        b, a = float(bids[0][0]), float(asks[0][0])
    except (TypeError, ValueError, IndexError):
        return 0.0
    mid = (a + b) / 2.0
    return ((a - b) / mid * 1e4) if mid > 0 else 0.0
