"""
OKXFeed.get_order_book: SWAP order-book size is in CONTRACTS, not coin
units. Without applying ctVal (contract value), price*size overstates USD
depth by 1/ctVal - the same class of unit mismatch that corrupted the
cross-venue imbalance ratio (fixed via per-venue ratio averaging in
strategies/liquidity_model.py), except liquidity_pool_usd has no ratio to
cancel the error, so it stayed wrong. This is a regression for the fix
that applies ctVal at the source so every downstream consumer (depth,
imbalance, cross-venue concatenation) sees coin-equivalent sizes.
"""
from data.okx_feed import OKXFeed


def _feed_with_responses(responses):
    feed = OKXFeed({"symbols": ["BTC-USDT-SWAP"]})
    calls = []

    def fake_get(path, params=None):
        calls.append((path, dict(params or {})))
        idx = len(calls) - 1
        return responses[idx] if idx < len(responses) else None

    setattr(feed, "_get", fake_get)
    return feed, calls


def test_swap_book_size_scaled_by_ctval():
    book_resp = [{"bids": [["50000", "10"]], "asks": [["50001", "8"]]}]
    instr_resp = [{"ctVal": "0.01"}]
    feed, calls = _feed_with_responses([book_resp, instr_resp])

    book = feed.get_order_book("BTC-USDT-SWAP")

    assert book is not None
    assert book["bids"] == [[50000.0, 0.1]]     # 10 contracts * 0.01 BTC/contract
    assert book["asks"] == [[50001.0, 0.08]]
    assert calls[1][0] == "/api/v5/public/instruments"
    assert calls[1][1] == {"instType": "SWAP", "instId": "BTC-USDT-SWAP"}


def test_ctval_cached_after_first_lookup():
    book_resp = [{"bids": [["50000", "10"]], "asks": [["50001", "8"]]}]
    instr_resp = [{"ctVal": "0.01"}]
    feed, calls = _feed_with_responses(
        [book_resp, instr_resp, book_resp, book_resp])

    feed.get_order_book("BTC-USDT-SWAP")
    feed.get_order_book("BTC-USDT-SWAP")

    # second call: only the book endpoint, no repeat instrument lookup
    assert len(calls) == 3
    assert calls[2][0] == "/api/v5/market/books"


def test_failed_ctval_lookup_falls_back_unscaled_and_is_not_cached():
    book_resp = [{"bids": [["50000", "10"]], "asks": [["50001", "8"]]}]
    feed, calls = _feed_with_responses([book_resp, None])

    book = feed.get_order_book("BTC-USDT-SWAP")

    assert book is not None
    assert book["bids"] == [[50000.0, 10.0]]    # unscaled fallback (ctVal=1.0)
    assert "BTC-USDT-SWAP" not in feed._ctval_cache  # not cached -> will retry


def test_spot_symbol_never_looks_up_ctval():
    book_resp = [{"bids": [["3000", "5"]], "asks": [["3001", "4"]]}]
    feed, calls = _feed_with_responses([book_resp])
    feed.symbols = ["ETH-USDT"]

    book = feed.get_order_book("ETH-USDT")

    assert book is not None
    assert book["bids"] == [[3000.0, 5.0]]      # unscaled: spot is already coin-denominated
    assert len(calls) == 1                       # no instrument lookup at all
