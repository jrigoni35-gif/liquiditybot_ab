"""Package: sentiment ingestion + narrative filter. These imports define
the public re-export surface pinned by __all__."""
from sentiment.scanner import SentimentScanner, SentimentSnapshot
from sentiment.fear_filter import NarrativeFilter, FilterVerdict
from sentiment.lexicon import score_text

__all__ = ["SentimentScanner", "SentimentSnapshot", "NarrativeFilter",
           "FilterVerdict", "score_text"]
