"""
core/clock.py — mission clock (Assurance Build)

Single time authority. Two clocks, two jobs, never mixed:

  monotonic()  - ALL intervals, windows, timeouts, rate limits.
                 Immune to NTP steps, DST, and operator clock edits.
                 An interval measured on the wall clock can go
                 negative; one measured here cannot.
  wall()       - audit stamps and human-facing records ONLY. Never
                 used to compute a duration.

Injectable for tests and deterministic replay: construct with a
callable and every consumer sees the same frozen time.
"""

import time


class MissionClock:
    def __init__(self, mono_fn=None, wall_fn=None):
        self._mono = mono_fn or time.monotonic
        self._wall = wall_fn or time.time

    def monotonic(self) -> float:
        return float(self._mono())

    def wall(self) -> float:
        return float(self._wall())


_DEFAULT = MissionClock()


def get_clock() -> MissionClock:
    return _DEFAULT
