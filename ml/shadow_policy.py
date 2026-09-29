# ml/shadow_policy.py
"""Shadow policy store (items 1b + 3, operator ruling 2026-09-29).

WHY. The model is trained on a clean signal-quality label (the 2026-07-26
ruling keeps it that way: exit-policy labels leaked exit mechanics). But the
entry bar is derived from the LABEL payoff, while the traded payoff differs
(era-9: a_eff +85 / b_eff -140 bps -> fair-game p* ~0.82, vs the 0.6381 bar).
The honest unification is at the DECISION: enter when the PREDICTED TRADED
VALUE is positive. That rule must earn its place in shadow first.

WHAT. One row per registered candidate, written at registration with the
model's p AT THAT MOMENT (the corpus never stored p-at-entry; rescoring old
trades with today's champion would leak - it trained on them). Outcomes are
joined later by scripts/shadow_policy_report.py from signal_history.csv:
candidate rows (candidate_id -> label outcome) and live rows (candidate_id ->
traded outcome). The report fits the p -> value map WALK-FORWARD and grades
the rule against live, CS-1 reconciled.

CONTRACT. Report-only: nothing in the order path reads this file (pinned by
tests/test_shadow_policy.py). Append-only, fixed schema, never raises into
the engine - a failed write is counted, the trade path never sees it.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from core.runtime import durable_append

log = logging.getLogger("liquiditybot.ml.shadow_policy")

HEADER = ["ts", "candidate_id", "asset", "direction", "model_p",
          "decision_fp"]


class ShadowPolicyStore:
    def __init__(self, path: str = "outputs/shadow_policy.csv"):
        self.path = Path(path)
        self.dropped = 0

    def log(self, *, ts: float, candidate_id: str, asset: str,
            direction: str, model_p, decision_fp: str) -> bool:
        """Append one candidate row. Returns True on a real write; False
        (and counts it) on any failure. Never raises."""
        try:
            if not candidate_id:
                return False
            p = float(model_p)
            if not (0.0 <= p <= 1.0):
                return False
            self.path.parent.mkdir(parents=True, exist_ok=True)
            row = [f"{float(ts):.3f}", candidate_id, asset, direction,
                   f"{p:.6f}", decision_fp or ""]
            # durable_append (test_append_invariant): heals a torn tail so a
            # hard kill cannot weld two rows, writes the header on a
            # ZERO-LENGTH file too, fsyncs. Same pattern as HorizonShadowStore.
            ok = durable_append(self.path,
                                lambda f: csv.writer(f).writerow(row),
                                header=",".join(HEADER) + "\r\n")
            if not ok:
                self.dropped += 1
            return bool(ok)
        except Exception:  # noqa: BLE001 - telemetry never breaks the loop
            self.dropped += 1
            log.debug("shadow policy row dropped (dropped=%d)", self.dropped,
                      exc_info=True)
            return False
