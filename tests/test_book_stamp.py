# tests/test_book_stamp.py
"""A2 pins: every 5m entry meta carries book='5m'; fill_row keeps its
three-way semantics (None pre-column / '' absent / value stamped)."""
from pathlib import Path
from types import SimpleNamespace

from core.fill_ledger import fill_row

_ROOT = Path(__file__).resolve().parents[1]
_MAIN_SRC = (_ROOT / "main.py").read_text(encoding="utf-8")


def _fill_book(meta):
    order = SimpleNamespace(purpose="entry", symbol="ETH/USD", side="buy",
                            ordertype="limit", post_only=True,
                            order_id="t-order", position_id="t-pos",
                            meta=meta, remaining=0.0)
    event = SimpleNamespace(fill_size=1.0, fill_price=2000.0)
    return fill_row(order, event, 0.0, 1_700_000_000.0)["book"]


def test_each_5m_entry_meta_dict_stamps_book():
    # the three 5m entry submit() sites (algo-child / main / grid rung):
    # each meta literal must carry "book": "5m" after this task
    assert _MAIN_SRC.count('"book": "5m"') >= 3


def test_fill_row_semantics_unchanged():
    assert _fill_book({"book": "5m"}) == "5m"
    assert _fill_book({"book": "long"}) == "long"
    assert _fill_book({}) == ""          # writer-knew-but-absent, preserved
