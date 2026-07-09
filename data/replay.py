"""
data/replay.py

Record-and-replay backtesting for the ACTUAL bot - not a translation of
its logic into a framework. Bar-based backtesters can't validate this
system because the edge lives in microstructure (books, spreads, maker
fills, spoof events) that candles don't contain, and porting the logic
into someone else's engine tests the port, not the bot. This harness
records what the feeds returned during a live dry-run session and
replays those exact frames through the unmodified engine.

FeedRecorder  - transparent wrapper around any feed object. Every
                public method call's (feed, method, args, result) is
                appended as one JSON line to the session file. Private
                methods pass through unrecorded (dry-run never calls
                them anyway).
FeedPlayer    - serves recorded results back in FIFO order per
                (feed, method, args) key. When a queue runs dry it
                raises ReplayExhausted (end of session) after first
                falling back to the last seen value for a grace count,
                so tiny call-count differences don't abort a run.

Determinism: the dry-run fill simulator is seeded, the engine is
loop-free, and frames are keyed by call signature - two replays of the
same recording with the same config produce identical fills and PnL.
Replay with the same cadence settings the recording was made with.
"""

import copy
import json
import logging
import time
from collections import defaultdict, deque
from pathlib import Path

log = logging.getLogger("liquiditybot.data.replay")


class ReplayExhausted(Exception):
    pass


def _key(feed: str, method: str, args: tuple, kwargs: dict) -> str:
    return json.dumps([feed, method, list(args),
                    sorted(kwargs.items())], default=str)


class FeedRecorder:
    """Wraps a feed; records every public call's result."""

    def __init__(self, feed, name: str, sink_path: str):
        self._feed = feed
        self._name = name
        self._sink = Path(sink_path)
        self._sink.parent.mkdir(parents=True, exist_ok=True)

    def __getattr__(self, attr):
        target = getattr(self._feed, attr)
        if attr.startswith("_") or not callable(target):
            return target

        def wrapper(*args, **kwargs):
            result = target(*args, **kwargs)
            try:
                with open(self._sink, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "t": round(time.time(), 3), "feed": self._name,
                        "method": attr, "args": list(args),
                        "kwargs": kwargs, "result": result,
                    }, default=str) + "\n")
            except (OSError, TypeError) as e:
                log.warning(f"record skip {self._name}.{attr}: {e}")
            return result
        return wrapper


class FeedPlayer:
    """One recorded feed, replayed. Construct via load_session()."""

    def __init__(self, name: str, frames_by_key: dict, grace: int = 3):
        self._name = name
        self._q = frames_by_key            # key -> deque of results
        self._last = {}                    # key -> last served result
        self._dry_counts = defaultdict(int)
        self._grace = grace
        self.calls = 0

    def _serve(self, method, args, kwargs):
        self.calls += 1
        k = _key(self._name, method, args, kwargs)
        q = self._q.get(k)
        if q:
            result = q.popleft()
            self._last[k] = result
            return copy.deepcopy(result)
        # queue dry: brief grace on last value, then end the session
        if k in self._last and self._dry_counts[k] < self._grace:
            self._dry_counts[k] += 1
            return copy.deepcopy(self._last[k])
        raise ReplayExhausted(f"{self._name}.{method}{args} exhausted")

    def __getattr__(self, attr):
        if attr.startswith("_"):
            raise AttributeError(attr)
        return lambda *a, **kw: self._serve(attr, a, kw)

    # engine expects these on the kraken feed object
    def kraken_pair(self, symbol: str) -> str:
        return symbol.replace("/", "")


def load_session(path: str) -> dict:
    """Returns {feed_name: FeedPlayer}. Also reports session stats."""
    frames = defaultdict(deque)
    names = set()
    n = 0
    t0, t1 = None, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            names.add(rec["feed"])
            frames[_key(rec["feed"], rec["method"],
                        tuple(rec["args"]), rec.get("kwargs") or {})
                ].append(rec["result"])
            t0 = rec["t"] if t0 is None else t0
            t1 = rec["t"]
            n += 1
    players = {}
    for name in names:
        sub = {k: q for k, q in frames.items()
            if json.loads(k)[0] == name}
        players[name] = FeedPlayer(name, sub)
    dur_min = ((t1 or 0) - (t0 or 0)) / 60.0
    log.info(f"session loaded: {n} frames, feeds={sorted(names)}, "
            f"~{dur_min:.1f} min of market data")
    players["_meta"] = {"frames": n, "duration_min": dur_min,
                        "start_ts": t0 or time.time()}
    return players
