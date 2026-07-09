"""sentiment/lexicon.py - crypto-tuned sentiment scorer shared by all
sources (news RSS, Reddit, figure statements). Negation flips within a
3-token window, intensifiers scale, tanh squash to [-1, 1] per text."""

import math
import re

BULLISH = {
    "bullish": 1.0, "moon": 0.8, "breakout": 0.8, "accumulate": 0.9,
    "accumulating": 0.9, "long": 0.5, "longs": 0.4, "rally": 0.8,
    "pump": 0.6, "ath": 0.7, "undervalued": 0.8, "buy": 0.6,
    "buying": 0.7, "bottom": 0.5, "bottomed": 0.8, "reversal": 0.4,
    "support": 0.3, "strength": 0.5, "strong": 0.4, "higher": 0.4,
    "recovery": 0.6, "bid": 0.3, "send": 0.4, "🚀": 0.8, "📈": 0.6,
}
BEARISH = {
    "bearish": -1.0, "crash": -1.0, "dump": -0.8, "capitulation": -0.9,
    "liquidated": -0.7, "liquidation": -0.6, "breakdown": -0.8,
    "short": -0.5, "shorts": -0.4, "sell": -0.6, "selling": -0.7,
    "selloff": -0.9, "fear": -0.6, "panic": -0.9, "bubble": -0.7,
    "top": -0.3, "topped": -0.7, "overvalued": -0.8, "rug": -0.9,
    "scam": -0.8, "collapse": -1.0, "bleed": -0.7, "weak": -0.4,
    "lower": -0.4, "rekt": -0.8, "📉": -0.6, "🩸": -0.8,
}
NEGATORS = {"not", "no", "never", "isn't", "isnt", "aint", "don't", "dont", "won't", "wont"}
INTENSIFIERS = {"very": 1.5, "extremely": 1.8, "massive": 1.6, "huge": 1.5,
                "mega": 1.6, "insane": 1.6, "so": 1.3}
_TOKEN_RE = re.compile(r"[a-zA-Z']+|[\U0001F300-\U0001FAFF]")


def score_text(text: str) -> float:
    tokens = _TOKEN_RE.findall(text.lower())
    total = 0.0
    for i, tok in enumerate(tokens):
        w = BULLISH.get(tok, 0.0) + BEARISH.get(tok, 0.0)
        if w == 0.0:
            continue
        window = tokens[max(i - 3, 0):i]
        if any(t in NEGATORS for t in window):
            w = -w
        for t in window:
            if t in INTENSIFIERS:
                w *= INTENSIFIERS[t]
        total += w
    return math.tanh(total / 3.0)
