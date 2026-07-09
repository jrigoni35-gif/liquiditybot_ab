"""
sentiment/scanner.py

Free, keyless influencer/CEO and crowd sentiment - replaces the X
scanner (paid API). Same hard constraint, enforced identically: this is
a FILTER input only. Its only consumers are sentiment/fear_filter.py
(clamped risk multiplier + confidence tilt) and two feature columns.
It cannot open, close, size, or flip a trade.

Sources (all free, no API keys):

figures  - Google News RSS search per tracked name, e.g.
            https://news.google.com/rss/search?q="Michael Saylor"+(bitcoin OR crypto)
            Captures public statements BY and coverage OF high-ranking
            CEOs/officials as reported across the press - broader and
            more durable than any single platform, and immune to one
            platform's API pricing. Each figure carries a config weight.
news     - Crypto outlet RSS headlines (CoinDesk, Cointelegraph,
            Decrypt, Bitcoin Magazine by default; list is config).
            Recency-decayed lexicon score.
crowd    - Hacker News via the Algolia public search API (keyless,
            stable). Title scores weighted by log-points; story volume
            feeds the volume z-score that gates fear/euphoria spikes.
            (Replaced reddit's JSON listings, which now 403 for
            unauthenticated clients - permanently dead air.)

All fetching goes through one injectable fetch(url) -> text function so
tests run fully offline, and every source degrades independently: a
dead feed logs once and contributes nothing - the trading loop can
never be stalled or broken by a news site.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Callable, Optional
from urllib.parse import quote_plus

from core.sanitize import loads_bounded, safe_float
from sentiment.lexicon import score_text

log = logging.getLogger("liquiditybot.sentiment.scanner")

try:
    import requests
except ImportError:                     # pragma: no cover
    requests = None

_UA = {"User-Agent": "liquiditybot/2.0 (research; contact: none)"}


@dataclass
class SentimentSnapshot:
    score: float = 0.0            # [-1, 1] blended sentiment
    volume: int = 0               # items scored this poll
    volume_z: float = 0.0         # vs trailing average item count
    fear_spike: bool = False
    euphoria_spike: bool = False
    available: bool = False
    ts: float = field(default_factory=time.time)
    per_source: dict = field(default_factory=dict)   # source -> score
    per_figure: dict = field(default_factory=dict)   # name -> score


def _default_fetch(url: str, timeout: float = 10.0) -> Optional[str]:
    if requests is None:
        return None
    resp = requests.get(url, headers=_UA, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_rss_items(xml_text: str) -> list:
    """[(title, age_seconds)] from an RSS feed; malformed items skipped."""
    from core.sanitize import safe_rss_root
    out = []
    root = safe_rss_root(xml_text)
    if root is None:
        return out
    now = time.time()
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        age = 0.0
        pub = item.findtext("pubDate")
        if pub:
            try:
                age = max(now - parsedate_to_datetime(pub).timestamp(), 0.0)
            except (TypeError, ValueError):
                pass
        out.append((title, age))
    return out


def parse_hn_posts(json_obj: dict) -> list:
    """[(title, points, age_seconds)] from a Hacker News Algolia search
    response (https://hn.algolia.com/api/v1/ - public, no key, stable).
    Replaces the Reddit listing parser: reddit.com's public JSON now returns
    403 to unauthenticated clients, so that crowd source was permanently
    dead air. Same signal shape: title + community score + age."""
    out = []
    now = time.time()
    try:
        for hit in json_obj.get("hits") or []:
            if not isinstance(hit, dict):
                continue
            title = (hit.get("title") or "").strip()
            if not title:
                continue
            pts = int(safe_float(hit.get("points"), default=0.0, lo=0.0,
                                 hi=1e9))
            created = safe_float(hit.get("created_at_i"), default=now)
            out.append((title, pts, max(now - created, 0.0)))
    except (KeyError, TypeError):
        pass
    return out


class SentimentScanner:
    def __init__(self, config: dict,
                fetch: Callable[[str], Optional[str]] | None = None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.fetch = fetch or _default_fetch
        self.poll_sec = float(cfg.get("poll_minutes", 15.0)) * 60.0
        self.decay_halflife_s = float(cfg.get("decay_halflife_hours", 12.0)) * 3600.0
        self.fear_threshold = float(cfg.get("fear_threshold", -0.35))
        self.euphoria_threshold = float(cfg.get("euphoria_threshold", 0.45))
        self.keywords = cfg.get("figure_keywords",
                                "bitcoin OR crypto OR ethereum OR markets")
        self.figures = cfg.get("figures", [])          # [{"name","weight"}]
        self.news_feeds = cfg.get("news_feeds", [])    # [{"url","weight"}]
        # crowd source: Hacker News Algolia queries [{"query","weight"}]
        # (replaced reddit subreddit listings - 403 for unauthenticated
        # clients since the API lockdown; HN Algolia is public and keyless)
        self.crowd_queries = cfg.get("crowd_queries", [])
        srcs = cfg.get("source_weights", {})
        self.w_figures = float(srcs.get("figures", 0.5))
        self.w_news = float(srcs.get("news", 0.3))
        self.w_crowd = float(srcs.get("crowd", srcs.get("reddit", 0.2)))
        self._last_poll = 0.0
        self._snapshot = SentimentSnapshot()
        self._volume_hist: list = []
        self._dead: dict = {}          # url -> last failure ts (log once/hour)

    def snapshot(self) -> SentimentSnapshot:
        return self._snapshot

    # ------------------------------------------------------------------
    def maybe_poll(self, now: float | None = None) -> SentimentSnapshot:
        now = now if now is not None else time.time()
        if not self.enabled:
            return self._snapshot
        if now - self._last_poll < self.poll_sec:
            return self._snapshot
        self._last_poll = now
        try:
            self._snapshot = self._poll(now)
        except Exception as e:          # never break the trading loop
            log.warning(f"sentiment poll failed, keeping last snapshot: {e}")
            self._snapshot.available = False
        return self._snapshot

    def _get(self, url: str) -> Optional[str]:
        try:
            return self.fetch(url)
        except Exception as e:
            last = self._dead.get(url, 0.0)
            if time.time() - last > 3600:
                log.warning(f"source unavailable ({e.__class__.__name__}): {url}")
                self._dead[url] = time.time()
            return None

    def _decay(self, age_s: float) -> float:
        return 0.5 ** (age_s / self.decay_halflife_s)

    # ------------------------------------------------------------------
    def _poll(self, now: float) -> SentimentSnapshot:
        per_source, per_figure = {}, {}
        blended_num, blended_den, volume = 0.0, 0.0, 0

        # --- figures via Google News RSS ---
        f_num, f_den = 0.0, 0.0
        for fig in self.figures:
            name = fig.get("name", "").strip()
            if not name:
                continue
            weight = float(fig.get("weight", 1.0))
            q = quote_plus(f'"{name}" ({self.keywords})')
            url = (f"https://news.google.com/rss/search?q={q}"
                f"&hl=en-US&gl=US&ceid=US:en")
            xml_text = self._get(url)
            if not xml_text:
                continue
            s_num, s_den = 0.0, 0.0
            for title, age in parse_rss_items(xml_text)[:15]:
                w = self._decay(age)
                s_num += score_text(title) * w
                s_den += w
                volume += 1
            if s_den > 0:
                fs = s_num / s_den
                per_figure[name] = round(fs, 3)
                f_num += fs * weight
                f_den += weight
        if f_den > 0:
            per_source["figures"] = f_num / f_den
            blended_num += per_source["figures"] * self.w_figures
            blended_den += self.w_figures

        # --- crypto news RSS ---
        n_num, n_den = 0.0, 0.0
        for feed in self.news_feeds:
            xml_text = self._get(feed.get("url", ""))
            if not xml_text:
                continue
            fw = float(feed.get("weight", 1.0))
            for title, age in parse_rss_items(xml_text)[:25]:
                w = fw * self._decay(age)
                n_num += score_text(title) * w
                n_den += w
                volume += 1
        if n_den > 0:
            per_source["news"] = n_num / n_den
            blended_num += per_source["news"] * self.w_news
            blended_den += self.w_news

        # --- crowd via Hacker News (Algolia public search, keyless) ---
        c_num, c_den = 0.0, 0.0
        for q in self.crowd_queries:
            query = str(q.get("query", "")).strip()
            if not query:
                continue
            url = ("https://hn.algolia.com/api/v1/search_by_date?query="
                   f"{quote_plus(query)}&tags=story&hitsPerPage=25")
            text = self._get(url)
            if not text:
                continue
            parsed = loads_bounded(text)
            if not parsed:
                continue
            qw = float(q.get("weight", 1.0))
            for title, pts, age in parse_hn_posts(parsed):
                w = qw * (1.0 + math.log1p(max(pts, 0))) * self._decay(age)
                c_num += score_text(title) * w
                c_den += w
                volume += 1
        if c_den > 0:
            per_source["crowd"] = c_num / c_den
            blended_num += per_source["crowd"] * self.w_crowd
            blended_den += self.w_crowd

        score = blended_num / blended_den if blended_den > 0 else 0.0
        self._volume_hist.append(volume)
        self._volume_hist = self._volume_hist[-48:]
        mu = sum(self._volume_hist) / len(self._volume_hist)
        sd = (sum((v - mu) ** 2 for v in self._volume_hist)
              / max(len(self._volume_hist), 1)) ** 0.5 or 1.0
        vol_z = (volume - mu) / sd

        snap = SentimentSnapshot(
            score=score, volume=volume, volume_z=vol_z,
            fear_spike=(score <= self.fear_threshold and vol_z >= 1.0),
            euphoria_spike=(score >= self.euphoria_threshold and vol_z >= 1.0),
            available=blended_den > 0, ts=now,
            per_source={k: round(v, 3) for k, v in per_source.items()},
            per_figure=per_figure,
        )
        log.info(f"sentiment: score={score:+.2f} items={volume} "
                f"sources={snap.per_source} figures={per_figure}")
        return snap
