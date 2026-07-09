"""
core/alerts.py - webhook operator alerting for critical events.

POSTs a rate-limited JSON payload with both "text" and "content" keys
(Slack/Discord/Mattermost compatible). Disabled by default; when
enabled, alerts always land in the log too. Never raises, never blocks
meaningfully (fire-and-forget daemon thread with a short timeout).
"""

import logging
import threading
import time
from typing import Optional

log = logging.getLogger("liquiditybot.core.alerts")


class AlertSink:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.webhook_url = str(cfg.get("webhook_url", "") or "")
        self.min_interval_sec = float(cfg.get("min_interval_per_key_sec", 300))
        self.timeout_sec = float(cfg.get("timeout_sec", 4.0))
        self.prefix = str(cfg.get("prefix", "[liquiditybot]"))
        self._last_sent: dict = {}          # key -> ts
        self._lock = threading.Lock()
        if self.enabled and not self.webhook_url:
            log.warning("alerts.enabled=true but no webhook_url set - "
                        "alerts will only appear in the log")

    def fire(self, key: str, message: str, level: str = "CRITICAL") -> None:
        """Emit an operator alert. `key` deduplicates and rate-limits a
        recurring condition (e.g. 'stale_data:ETH'); `message` is human
        text. Always logs; only webhooks if configured. Never raises."""
        try:
            getattr(log, level.lower(), log.critical)(f"ALERT {key}: {message}")
            if not (self.enabled and self.webhook_url):
                return
            now = time.time()
            with self._lock:
                if now - self._last_sent.get(key, 0.0) < self.min_interval_sec:
                    return
                self._last_sent[key] = now
            text = f"{self.prefix} {level} {key}: {message}"[:1900]
            threading.Thread(target=self._post, args=(text,),
                             daemon=True).start()
        except Exception:                                       # noqa: BLE001
            log.debug("alert dispatch failed", exc_info=True)

    def _post(self, text: str) -> None:
        try:
            import requests
            requests.post(self.webhook_url,
                          json={"text": text, "content": text},
                          timeout=self.timeout_sec)
        except Exception:                                       # noqa: BLE001
            log.debug("alert webhook POST failed", exc_info=True)
