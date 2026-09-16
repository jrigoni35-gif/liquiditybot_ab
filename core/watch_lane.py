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

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("liquiditybot.watch_lane")

# The lane's own corpus. A SEPARATE FILE, not a tag on the shared one - see
# channel 2 above. Registered in tests/conftest.py's _REDIRECTED_PATH_ATTRS
# and in scripts/outputs_gc.py's NEVER set in the same commit that introduced
# it, per this repo's own leak-class rule.
WATCH_HISTORY_PATH = "outputs/watch_history.csv"
_DEF_EVAL_EVERY_SEC = 300.0
#: How often the pending pool is written. Not a tuning knob: the pool only
#: changes on an evaluation, and evaluations are throttled to
#: _DEF_EVAL_EVERY_SEC per pair, so anything shorter rewrites an unchanged
#: file. 600 s bounds the worst-case loss to two evaluations.
_DEF_SAVE_EVERY_SEC = 600.0

#: Bar width the candidate horizon is counted in. MUST equal
#: ml.walkforward.BAR_SECONDS; duplicated rather than imported because
#: _load_state runs at boot and an unrelated import failure there would cost
#: the pool it exists to restore. The duplication is PINNED, not trusted -
#: see test_the_bar_width_here_matches_the_labellers.
_BAR_SEC = 300.0

#: A restored pool older than the candidate horizon is DROPPED. A candidate
#: resolves within label_max_bars (36 h at 432 x 5 m); past that its vertical
#: barrier has already expired in wall-clock terms and restoring it would
#: feed the labeller bars separated from its own by a gap the size of the
#: outage. Measured 2026-09-15: a 2.5-day-old pool written by a mutation
#: test's planted defect was sitting in outputs/ at exactly the moment this
#: restore path was about to ship, which is how this guard got written.
#: Clock skew gets an hour of slack in the other direction; a stamp further
#: in the FUTURE than that is a fabricated or corrupt file, not a clock.
_CLOCK_SKEW_TOL_SEC = 3600.0
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
        self._save_every = float(cfg.get("save_every_sec",
                                         _DEF_SAVE_EVERY_SEC))
        self._last_save = 0.0
        self._restored = 0
        self._saves = 0
        self._stale_dropped = 0
        # default mirrors _build's own ml.label_max_bars fallback; set for
        # real in _build, but _load_state must never read an absent attribute
        self._max_bars = 432
        # NOT resolved here. See _state_path().
        self._state_path_cfg = str(cfg.get("state_path") or "")

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

            self._max_bars = int(ml_cfg.get("label_max_bars", 432))
            self._store = HistoryStore(
                WATCH_HISTORY_PATH, max_bars=self._max_bars)
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
            self._load_state()
        except Exception as exc:            # pragma: no cover - boot safety
            self._engines_ok = False
            self._last_error = f"{type(exc).__name__}: {exc}"
            log.exception("watch_lane init failed - lane disabled this boot")

    # ------------------------------------------------------------------
    def _state_path(self) -> str:
        """The pending pool lives BESIDE the corpus, resolved at call time.

        Not bound in __init__, and that is the whole point. WATCH_HISTORY_PATH
        is a module constant that callers redirect by monkeypatching the
        module (tests/test_watch_lane.py:184, :256); a state path frozen at
        construction does not follow that redirect, so a tmp_path test wrote
        outputs/watch_lane_state.json into the PRODUCTION tree. conftest's
        tripwire caught it on the first run - the ELEVENTH instance of this
        repo's QA-writes-production class, and the first committed by the
        session that catalogued the other ten.

        Deriving from the corpus path means one redirect covers both, which
        is also what the data wants: the pending pool and the corpus it
        drains into are the same lane's state.

        In production this resolves to outputs/watch_history_state.json.
        That value is deliberately NOT also a module constant. A constant
        nothing reads, holding a production path, is bait: conftest redirects
        only the attribute names it has REGISTERED, so the first caller to
        reach for the obvious-looking constant instead of this method writes
        into the operator's tree with nothing flagging it - the same class
        this method's existence was bought by. One such constant was written
        here and deleted before it shipped.

        Deliberately NOT core/persistence.py either: that module hands the
        ENGINE its state, and channel 3 of the isolation contract above is
        that this lane's pool never meets the engine's.

        KNOWN GAP, deliberately not widened here (mid-accrual): neither
        WATCH_HISTORY_PATH nor this path appears in config.json, so
        tests/test_qa_isolation.py's generic *_path walk cannot see either -
        the exact "absence of a key is not absence of a write" trap its own
        docstring names. Lifting both into config is a separate change.
        """
        if self._state_path_cfg:
            return self._state_path_cfg
        base = Path(WATCH_HISTORY_PATH)
        return str(base.with_name(base.stem + "_state.json"))

    # ------------------------------------------------------------------
    def _load_state(self) -> None:
        """Restore the pending candidate pool across a restart.

        WHY. A watch candidate needs up to label_max_bars (36 h at 432 x 5 m)
        to resolve and this process does not live that long, so before this
        every restart discarded the pending pool.

        The cost is not merely a smaller corpus. A pool that dies with the
        process keeps only the candidates that resolve INSIDE one process
        lifetime, which selects on SHORT TIME TO RESOLUTION - i.e. on
        volatility, which this repo's own resolution-vs-direction work
        identifies as the half of the triple-barrier label carrying no
        directional information. An unpersisted pool does not just lose rows;
        it BIASES the ones it keeps, in the exact direction that makes them
        worthless. That argument is from MECHANISM and needs no row count.

        NO ROW COUNT IS WRITTEN HERE, DELIBERATELY. An earlier version of
        this docstring said "the lane had written 12 rows in total", carried
        in from a workflow summary and never re-derived. It was refuted the
        same day by two independent routes - the live snapshot's
        rows_labeled and outputs/watch_history.csv's own line count - which
        disagree with each other by 9 and with 12 by two orders of
        magnitude. Re-derive from those two; do not re-cite 12.

        Fail-soft by construction: any error leaves an empty pool, which is
        precisely the pre-fix behaviour. CandidateLabeler.restore() does its
        own FEATURE_SCHEMA_VERSION check and drops a stale-semantics pool.
        """
        try:
            if self._labeler is None:
                return
            p = Path(self._state_path())
            if not p.exists():
                return
            d = json.loads(p.read_text(encoding="utf-8"))
            lab = (d or {}).get("labeler") or {}
            if not lab:
                return
            # AGE GATE. restore() checks the feature SCHEMA; nothing checked
            # the CLOCK. A pool older than the candidate horizon holds only
            # candidates whose vertical barrier has already expired, and
            # feeding them to the labeller resumes a bar series across a gap
            # the size of the outage - a silent corruption of exactly the
            # rows this persistence exists to win. Dropping is fail-soft to
            # the pre-2026-09-15 behaviour, and it is COUNTED so a reader can
            # tell "nothing to restore" from "refused to restore".
            saved_at = float((d or {}).get("saved_at") or 0.0)
            age = time.time() - saved_at
            horizon = float(self._max_bars) * _BAR_SEC
            if saved_at <= 0.0 or age > horizon or age < -_CLOCK_SKEW_TOL_SEC:
                self._stale_dropped = len(lab.get("cands") or [])
                self._last_error = (
                    f"restore: pool age {age / 3600.0:.1f}h outside "
                    f"[-1.0, {horizon / 3600.0:.1f}]h - dropped "
                    f"{self._stale_dropped} candidate(s)")
                log.warning("watch_lane: %s", self._last_error)
                return
            self._labeler.restore(lab)
            self._restored = len(lab.get("cands") or [])
            if self._restored:
                log.info("watch_lane: restored %d pending candidate(s)",
                         self._restored)
        except Exception as exc:            # pragma: no cover - boot safety
            self._last_error = f"restore: {type(exc).__name__}: {exc}"
            log.warning("watch_lane: pending pool not restored (%s) - "
                        "starting empty, the pre-2026-09-15 behaviour", exc)

    # ------------------------------------------------------------------
    def _save_state(self, now: float) -> None:
        """Atomically write the pending pool. Never raises.

        Atomic because a torn file would be restored at the next boot as a
        partial pool WITHOUT complaining - the same silent-corruption shape
        the repo's snapshot machinery exists to prevent.
        """
        try:
            if self._labeler is None:
                return
            p = Path(self._state_path())
            p.parent.mkdir(parents=True, exist_ok=True)
            payload = {"schema": 1, "saved_at": now,
                       "labeler": self._labeler.to_dict()}
            fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh)
                os.replace(tmp, p)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
            self._saves += 1
            self._last_save = now
        except Exception as exc:            # pragma: no cover - loop safety
            self._last_error = f"save: {type(exc).__name__}: {exc}"
            log.warning("watch_lane: pending pool not saved (%s)", exc)

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
            out = self._evaluate(pair, now)
            if now - self._last_save >= self._save_every:
                self._save_state(now)
            return out
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
            # pending-pool persistence (2026-09-15). `pending` is how many
            # candidates are awaiting a barrier right now; before the pool was
            # persisted this was discarded on every restart, so the corpus was
            # selected on fast resolution. Read `restored_on_boot` after a
            # relaunch to confirm the fix is live rather than trusting it.
            "pending": int(len(getattr(self._labeler, "_cands", []) or []))
            if self._labeler is not None else 0,
            "restored_on_boot": int(self._restored),
            # DROPPED, not missing: distinguishes "there was no pool" from
            # "there was one and it was too old to trust".
            "stale_dropped": int(self._stale_dropped),
            "saves": int(self._saves),
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
