"""Fetch 1m spot klines from data.binance.vision for the era-9 universe.

SAFE-class measurement tooling (2026-09-19, 09-22 boundary prep): downloads
public, no-auth monthly + current-month daily kline zips, consolidates per
symbol into parquet (1m native + 5m resampled to the bot's decision cadence),
and emits a quality report + manifest. Nothing here touches the order path;
Binance is a read-only data venue per the repo's venue law.

Usage: .venv/Scripts/python.exe scripts/fetch_binance_vision_1m.py
"""

import io
import json
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research" / "corpus" / "binance_vision"
RAW = OUT / "raw_zips"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "LINKUSDT", "PAXGUSDT"]  # era-9 core universe (cut #11)
INTERVAL = "1m"
START = date(2024, 1, 1)  # completed months from here
MONTHLY_URL = "https://data.binance.vision/data/spot/monthly/klines/{s}/{i}/{s}-{i}-{ym}.zip"
DAILY_URL = "https://data.binance.vision/data/spot/daily/klines/{s}/{i}/{s}-{i}-{ymd}.zip"
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]


def month_range(start: date) -> list[str]:
    """YYYY-MM for every completed month from start up to last month."""
    out, y, m = [], start.year, start.month
    today = date.today()
    while (y, m) < (today.year, today.month):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def current_month_days() -> list[str]:
    today = date.today()
    first = today.replace(day=1)
    return [(first + timedelta(days=d)).isoformat()
            for d in range((today - first).days)]  # completed days only


def fetch(url: str) -> bytes | None:
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    return None


def norm_ms(ts: pd.Series) -> pd.Series:
    """Binance kline epochs: ms pre-2025, us post-2025. Normalize to ms."""
    return pd.Series(
        [v // 1000 if v > 10**14 else v for v in ts], index=ts.index)


def load_zip(blob: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            df = pd.read_csv(f, header=None, names=COLS)
    return df


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    months = month_range(START)
    days = current_month_days()
    jobs = [(s, MONTHLY_URL.format(s=s, i=INTERVAL, ym=ym), f"{s}-1m-{ym}.zip")
            for s in SYMBOLS for ym in months]
    jobs += [(s, DAILY_URL.format(s=s, i=INTERVAL, ymd=d), f"{s}-1m-{d}.zip")
             for s in SYMBOLS for d in days]
    print(f"jobs: {len(jobs)} ({len(months)} months + {len(days)} days x {len(SYMBOLS)} symbols)")

    missing: list[str] = []

    def work(job):
        sym, url, fname = job
        dest = RAW / fname
        if dest.exists():
            return sym, fname, "cached"
        blob = fetch(url)
        if blob is None:
            return sym, fname, "missing"
        dest.write_bytes(blob)
        return sym, fname, "ok"

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(work, jobs))
    for _sym, fname, status in results:
        if status == "missing":
            missing.append(fname)
    print(f"downloaded/cached: {sum(1 for r in results if r[2] != 'missing')}, missing: {len(missing)}")

    quality = {}
    for sym in SYMBOLS:
        zips = sorted(RAW.glob(f"{sym}-{INTERVAL}-*.zip"))
        dfs = [load_zip(z.read_bytes()) for z in zips]
        df = pd.concat(dfs, ignore_index=True)
        df["open_time"] = norm_ms(df["open_time"].astype("int64"))
        df["close_time"] = norm_ms(df["close_time"].astype("int64"))
        df = df.drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)
        for c in ["open", "high", "low", "close", "volume", "quote_volume",
                  "taker_buy_volume", "taker_buy_quote_volume"]:
            df[c] = df[c].astype("float64")
        df["count"] = df["count"].astype("int64")
        df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        # gap audit on the 1m grid
        diffs = df["open_time"].diff().dropna()
        gaps = diffs[diffs > 60_000]
        gap_minutes = float((gaps.sum() - 60_000 * len(gaps)) / 60_000) if len(gaps) else 0.0
        # write 1m parquet via duckdb (no pyarrow needed)
        p1 = OUT / f"klines_1m_{sym}.parquet"
        duckdb.sql(f"COPY (SELECT * FROM df) TO '{p1.as_posix()}' (FORMAT PARQUET)")  # nosec B608 - path from repo-local constants, no untrusted input
        # 5m resample = the bot's decision cadence
        r = df.set_index("ts").resample("5min").agg(
            open=("open", "first"), high=("high", "max"), low=("low", "min"),
            close=("close", "last"), volume=("volume", "sum"),
            quote_volume=("quote_volume", "sum"), count=("count", "sum"),
            taker_buy_quote_volume=("taker_buy_quote_volume", "sum"),
            source_bars=("close", "size")).dropna(subset=["close"]).reset_index()
        p5 = OUT / f"klines_5m_{sym}.parquet"
        duckdb.sql(f"COPY (SELECT * FROM r) TO '{p5.as_posix()}' (FORMAT PARQUET)")  # nosec B608 - path from repo-local constants, no untrusted input
        quality[sym] = {
            "rows_1m": int(len(df)), "rows_5m": int(len(r)),
            "first": str(df["ts"].iloc[0]), "last": str(df["ts"].iloc[-1]),
            "dupes_dropped": int(len(pd.concat(dfs)) - len(df)),
            "gap_events": int(len(gaps)), "gap_minutes_missing": gap_minutes,
            "parquet_1m": p1.name, "parquet_5m": p5.name,
            "files": len(zips),
        }
        print(sym, quality[sym])

    manifest = {
        "built_utc": pd.Timestamp.utcnow().isoformat(),
        "source": "https://data.binance.vision (Binance public spot klines, no auth)",
        "venue_role": "READ-ONLY data venue (repo law: Kraken sole execution venue)",
        "symbols": SYMBOLS, "interval_native": INTERVAL,
        "months": months, "current_month_days": days,
        "missing_files": missing, "quality": quality,
        "script": "scripts/fetch_binance_vision_1m.py",
        "purpose": "09-22 boundary prep - swing-mechanics research corpus for the era-9 universe",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("manifest written:", OUT / "manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
