"""
data/darkpool_feed.py  — DROP-IN for liquiditybot_ab (see integration guide)

Read-only weekly dark-pool (FINRA ATS) context, keyed to the same risk
basket as the moomoo feed (COIN / MSTR / QQQ by default). NO EXECUTION,
by construction: this module only ever opens a DuckDB file read-only and
runs SELECTs; there is no network path and no write path.

Why dark-pool context in a crypto bot: institutional accumulation /
distribution in crypto-adjacent equities (COIN, MSTR) and the QQQ risk
proxy shows up in off-exchange venue volume weeks before it shows up in
price. This feed surfaces that as SHADOW features first (house law: a
new feature is measured before any decision path may read it).

Data source: the FINRA ATS weeklySummary mirror built outside the bot
(darkpool_db.mirror_cache -> darkpool.duckdb, table ats_venue_weekly).
Weekly granularity, publication-lagged 2-4 weeks; every value carries
its own timestamps (period_start/period_end/published_date/ingested_at)
so staleness is a first-class feature, not a hidden assumption.

Failure model (mirrors moomoo_feed.py): duckdb missing, DB file absent,
or query error -> snapshot reports available=False, flags cleared,
numeric fields neutral 0.0, `ts` NOT advanced (a degraded snapshot keeps
pointing at the last REAL observation). Weekly data repeats identically
across polls, so the closed-market freeze gate from moomoo_feed (DF-010)
is replicated here as `dp_frozen`: a full-repeat poll does not re-append
to the z windows.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

log = logging.getLogger("liquiditybot.data.darkpool")

EPS = 1e-9

# query: per-symbol dark-volume rollup for the newest complete period,
# plus the surge ratio vs that symbol's prior complete periods (same tier
# wave only — cross-wave comparisons fabricate surges; see darkpool_db)
_LATEST_PER_SYMBOL = """
-- NOTE: tier is deliberately NOT a partition key. Per-row tier values
-- scatter within a symbol-week (venue rows carry their own tier labels),
-- which fragments each symbol into bogus 1-venue partitions. For a
-- single liquid symbol, latest-period + prior-periods within that symbol
-- is the robust rollup; the tier-wave subtlety matters only for
-- market-wide scans (handled in darkpool_db.surge_scan instead).
WITH per_venue AS (
    -- date/timestamp columns are CAST to VARCHAR: DuckDB needs pytz to
    -- materialize DATE/TIMESTAMP values into Python objects, and the bot
    -- venv carries duckdb WITHOUT pytz - a missing optional module must
    -- not disable the feed. ISO strings sort chronologically (same
    -- lexicographic order), and the feed only ever stringifies them.
    SELECT symbol, CAST(period_start AS VARCHAR) AS period_start,
           CAST(period_end AS VARCHAR) AS period_end,
           CAST(published_date AS VARCHAR) AS published_date,
           CAST(ingested_at AS VARCHAR) AS ingested_at,
           data_age_days, venue_mpid, volume_shares,
           SUM(volume_shares) OVER (PARTITION BY symbol, period_start)
               AS sym_vol
    FROM ats_venue_weekly
    WHERE is_complete AND symbol = ?
),
rolled AS (
    -- group ONLY by (symbol, period): per-venue metadata (period_end,
    -- lastReportedDate, published_date) varies slightly across venue rows
    -- and was silently fragmenting each symbol into 1-venue groups
    SELECT symbol, period_start,
           MAX(period_end) AS period_end,
           MAX(published_date) AS published_date,
           MAX(ingested_at) AS ingested_at,
           MAX(data_age_days) AS data_age_days,
           SUM(volume_shares) AS dp_volume,
           COUNT(DISTINCT venue_mpid) AS dp_venue_count,
           SUM(POWER(volume_shares * 1.0 / NULLIF(sym_vol, 0), 2))
               AS dp_venue_hhi
    FROM per_venue
    GROUP BY symbol, period_start
),
with_rn AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY symbol
                                 ORDER BY period_start DESC) AS rn
    FROM rolled
)
SELECT cur.symbol, cur.period_start, cur.period_end,
       cur.published_date, cur.ingested_at, cur.data_age_days,
       cur.dp_volume, cur.dp_venue_count, cur.dp_venue_hhi,
       (SELECT AVG(prev.dp_volume) FROM with_rn prev
         WHERE prev.symbol = cur.symbol
           AND prev.rn BETWEEN 2 AND 5) AS prior_avg_volume
FROM with_rn cur WHERE cur.rn = 1
"""


@dataclass
class DarkPoolSnapshot:
    # cross-basket means (z-scored where history exists)
    dp_surge_z: float = 0.0        # z of per-symbol surge ratio, basket mean
    dp_vol_z: float = 0.0          # z of per-symbol log dark volume
    dp_hhi: float = 0.0            # venue concentration (mean, 0..1)
    # symbol -> {"surge_ratio","dp_volume","venue_count","hhi",
    #            "period_start","data_age_days"} for the dashboard
    per_ticker: dict = field(default_factory=dict)
    available: bool = False
    ts: float = field(default_factory=time.time)
    # weekly data repeats identically between publications: a full-repeat
    # poll is NOT a fresh observation. Same contract as quotes_frozen.
    dp_frozen: bool = False
    # data hygiene, first-class by design (this feed is publication-lagged)
    data_age_days: float = 0.0     # age of the newest period_end we hold
    is_complete: bool = False      # underlying periods passed completeness
    periods: int = 0               # distinct complete periods on file


class DarkPoolFeed:
    def __init__(self, config: dict, con=None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.db_path = str(cfg.get("duckdb_path", "darkpool.duckdb"))
        # weekly regulatory data: a slow cadence is honest; the frozen
        # gate makes faster polling harmless but pointless
        self.poll_sec = float(cfg.get("poll_minutes", 360.0)) * 60.0
        # [{"code": "US.COIN", "symbol": "COIN", "weight": 1.0}]
        self.tickers = cfg.get("tickers", [])
        self.min_prior_periods = int(cfg.get("min_prior_periods", 2))
        self._con = con            # injectable for tests
        self._db_ok = con is not None
        self._last_poll = 0.0
        self._surge_hist: deque = deque(maxlen=int(
            cfg.get("z_lookback_polls", 60)))
        self._vol_hist: deque = deque(maxlen=int(
            cfg.get("z_lookback_polls", 60)))
        self._last_per: dict = {}
        self._frozen = False
        self._snapshot = DarkPoolSnapshot()
        self._warned = False

    def snapshot(self) -> DarkPoolSnapshot:
        return self._snapshot

    # ------------------------------------------------------------------
    @staticmethod
    def _import_db():
        """Isolated import seam (same rationale as moomoo_feed._import_sdk:
        the smoke suite patches this to exercise the no-DB branch on every
        machine). duckdb is on the dependency-hygiene FORBIDDEN list
        (tests/test_dependency_hygiene.py: analysis stack, never a plain
        import statement at engine scope), so the seam routes through
        importlib - a lazy, optional, failure-tolerant import. READ-ONLY
        use only."""
        import importlib
        return importlib.import_module("duckdb")

    def _ensure_con(self) -> bool:
        if self._con is not None:
            return True
        if not self.enabled:
            return False
        try:
            if not Path(self.db_path).exists():
                if not self._warned:
                    log.info(f"darkpool DB not found at {self.db_path} "
                             f"- running without it")
                    self._warned = True
                return False
            duckdb = self._import_db()
            # read-only: the bot must never be able to mutate the mirror
            self._con = duckdb.connect(self.db_path, read_only=True)
            self._db_ok = True
            self._warned = False
            log.info(f"darkpool mirror opened read-only: {self.db_path}")
            return True
        except ImportError:
            if not self._warned:
                log.info("darkpool feed enabled but duckdb not installed "
                         "(pip install duckdb) - running without it")
                self._warned = True
        except Exception as e:
            if not self._warned:
                log.info(f"darkpool DB unusable at {self.db_path} ({e}) "
                         f"- running without it")
                self._warned = True
        return False

    def _degrade(self) -> None:
        """Unavailable contract, identical to moomoo_feed._degrade: flags
        cleared, numerics already neutral, ts keeps pointing at the last
        REAL observation."""
        self._snapshot.available = False
        self._snapshot.dp_frozen = False
        self._snapshot.is_complete = False

    def maybe_poll(self, now: float | None = None) -> DarkPoolSnapshot:
        now = now if now is not None else time.time()
        if not self.enabled or not self.tickers:
            return self._snapshot
        if now - self._last_poll < self.poll_sec:
            return self._snapshot
        self._last_poll = now
        if not self._ensure_con():
            self._degrade()
            return self._snapshot
        try:
            self._snapshot = self._poll(now)
        except Exception as e:
            log.warning(f"darkpool poll failed ({e}) - keeping last snapshot")
            self._degrade()
        return self._snapshot

    def _poll(self, now: float) -> DarkPoolSnapshot:
        assert self._con is not None
        periods = self._con.execute(
            "SELECT COUNT(DISTINCT period_start) FROM ats_venue_weekly "
            "WHERE is_complete").fetchone()[0]
        per, surges, vols = {}, [], []
        weights = {t["symbol"].upper(): float(t.get("weight", 1.0))
                   for t in self.tickers if t.get("symbol")}
        missing = []
        for t in self.tickers:
            sym = str(t.get("symbol", "")).upper()
            if not sym:
                continue
            row = self._con.execute(_LATEST_PER_SYMBOL, [sym]).fetchone()
            if row is None:
                missing.append(sym)
                continue
            (sym_out, pstart, pend, pub, ing, age,
             vol, vcount, hhi, prior_avg) = row
            surge = (vol / prior_avg) if (prior_avg and prior_avg > EPS) \
                else None
            per[sym_out] = {
                "surge_ratio": (round(float(surge), 3) if surge else None),
                "dp_volume": int(vol),
                "venue_count": int(vcount),
                "hhi": round(float(hhi), 4) if hhi is not None else None,
                "period_start": str(pstart),
                "period_end": str(pend),
                "published_date": str(pub),
                "data_age_days": int(age) if age is not None else None,
            }
            w = weights.get(sym_out, 1.0)
            if surge:
                surges.append(float(surge) * w)
            if vol and vol > 0:
                vols.append(float(np.log(vol)) * w)
        if not per:
            raise RuntimeError(f"no dark-pool rows for any configured "
                               f"symbol (missing: {missing})")

        # freeze gate: weekly rows are identical between publications, so a
        # repeat observation must not re-enter the z windows (DF-010 analog)
        fingerprint = {k: (v["surge_ratio"], v["dp_volume"])
                       for k, v in per.items()}
        frozen = bool(self._last_per) and fingerprint == self._last_per
        self._last_per = fingerprint
        if frozen:
            if not self._frozen:
                self._frozen = True
                log.info("darkpool rows unchanged since last poll "
                         "(weekly publication cadence); z-window appends "
                         "suspended, z holds")
        else:
            self._frozen = False
            if surges:
                self._surge_hist.append(float(np.mean(surges)))
            if vols:
                self._vol_hist.append(float(np.mean(vols)))

        def _z(vals: deque) -> float:
            arr = np.array(vals, float)
            sd = float(arr.std()) if len(arr) >= 8 else 0.0
            return (float(np.clip((vals[-1] - float(arr.mean())) / sd, -4, 4))
                    if sd > EPS and len(arr) >= 8 else 0.0)

        age_days = max((v["data_age_days"] or 0) for v in per.values())
        hhi_mean = float(np.mean([v["hhi"] for v in per.values()
                                  if v["hhi"] is not None])) \
            if any(v["hhi"] is not None for v in per.values()) else 0.0
        snap = DarkPoolSnapshot(
            dp_surge_z=_z(self._surge_hist),
            dp_vol_z=_z(self._vol_hist),
            dp_hhi=round(hhi_mean, 4),
            per_ticker=per,
            available=True, ts=now, dp_frozen=frozen,
            data_age_days=float(age_days),
            is_complete=True, periods=int(periods))
        log.info(f"darkpool: {len(per)} symbols, periods={periods}, "
                 f"age={age_days}d, surge_z={snap.dp_surge_z:+.2f}, "
                 f"vol_z={snap.dp_vol_z:+.2f}, hhi={snap.dp_hhi:.3f}"
                 + (f" | missing: {missing}" if missing else ""))
        return snap

    def to_dict(self) -> dict:
        """Serializable window/freeze state (same contract as
        moomoo_feed.to_dict): z windows and the freeze gate's comparison
        state survive a restart so a restart cannot silently rebuild the
        windows empty."""
        return {"surge_hist": [float(x) for x in self._surge_hist],
                "vol_hist": [float(x) for x in self._vol_hist],
                "last_per": dict(self._last_per),
                "frozen": bool(self._frozen)}

    def from_dict(self, d: dict) -> None:
        try:
            if not isinstance(d, dict):
                return
            for key, hist in (("surge_hist", self._surge_hist),
                              ("vol_hist", self._vol_hist)):
                vals = d.get(key) or []
                hist.clear()
                hist.extend(float(x) for x in vals)
            lp = d.get("last_per")
            self._last_per = ({str(k): tuple(v) for k, v in lp.items()}
                              if isinstance(lp, dict) else {})
            self._frozen = bool(d.get("frozen", False))
        except (TypeError, ValueError):
            self._surge_hist.clear()
            self._vol_hist.clear()
            self._last_per = {}
            self._frozen = False

    def close(self):
        if self._con is not None:
            try:
                self._con.close()
            except Exception:  # nosec B110 - shutdown close is best-effort
                log.debug("darkpool con close failed at shutdown")
            self._con = None
