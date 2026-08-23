"""Pins for scripts/fee_reprice.py.

The gate tests the right null (net > 0, i.e. edge beyond cost) but subtracts
the CONFIG constants 25/40 while the venue is 40/80 (first-party fetch
2026-08-22, recorded at cost_attribution.py:82-90). Repriced exactly, the
era-4 cohort moves +0.0584% (CONTINUE band) -> -0.5237% (INCONCLUSIVE band).
The fee constant moves the verdict, so the repricing arithmetic has to be
pinned to the fill's OWN post_only flag - never to an assumed leg mix, which
is what the earlier indicative estimate used.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "fee_reprice.py"


def _load():
    spec = importlib.util.spec_from_file_location("fee_reprice", _SRC)
    if spec is None or spec.loader is None:  # pragma: no cover
        pytest.skip("fee_reprice.py not importable")
    m = importlib.util.module_from_spec(spec)
    sys.modules["fee_reprice"] = m
    spec.loader.exec_module(m)
    return m


fr = _load()


def _row(size="2.0", price="100.0", post_only="0", fee="0.80"):
    return {"fill_size": size, "fill_price": price, "post_only": post_only,
             "fees_delta_usd": fee}


def test_taker_fill_is_priced_at_the_taker_rate():
    rows, _ = fr.reprice_rows([_row(post_only="0")], 40.0, 80.0)
    # notional 200 * 80bps = 1.60
    assert float(rows[0]["fees_delta_usd"]) == pytest.approx(1.60)


def test_maker_fill_is_priced_at_the_maker_rate():
    rows, _ = fr.reprice_rows([_row(post_only="1")], 40.0, 80.0)
    # notional 200 * 40bps = 0.80
    assert float(rows[0]["fees_delta_usd"]) == pytest.approx(0.80)


def test_the_fills_OWN_flag_decides_not_an_assumed_mix():
    """One maker and one taker in the same batch must price differently.
    An assumed leg mix would give them the same number."""
    rows, _ = fr.reprice_rows([_row(post_only="1"), _row(post_only="0")],
                              40.0, 80.0)
    assert float(rows[0]["fees_delta_usd"]) != float(rows[1]["fees_delta_usd"])


@pytest.mark.parametrize("flag,maker", [("1", True), ("true", True),
                                        ("True", True), ("0", False),
                                        ("", False), ("no", False)])
def test_post_only_parsing_is_explicit(flag, maker):
    rows, stats = fr.reprice_rows([_row(post_only=flag)], 40.0, 80.0)
    assert stats["maker_fills"] == (1 if maker else 0)
    assert stats["taker_fills"] == (0 if maker else 1)


def test_zero_fee_repricing_leaves_only_gross():
    rows, stats = fr.reprice_rows([_row(post_only="0")], 0.0, 0.0)
    assert float(rows[0]["fees_delta_usd"]) == pytest.approx(0.0)
    assert stats["true_fees_usd"] == pytest.approx(0.0)


def test_the_source_rows_are_not_mutated():
    """It must hand cohort_eval a COPY - mutating the caller's rows would
    corrupt any other reader in the same process."""
    src = [_row(post_only="0", fee="0.80")]
    fr.reprice_rows(src, 40.0, 80.0)
    assert src[0]["fees_delta_usd"] == "0.80"


def test_ratio_reports_the_understatement():
    """booked 0.80 on a 200 notional taker fill is 40bps; true is 80bps."""
    _, stats = fr.reprice_rows([_row(post_only="0", fee="0.80")], 40.0, 80.0)
    assert stats["booked_fees_usd"] == pytest.approx(0.80)
    assert stats["true_fees_usd"] == pytest.approx(1.60)
    assert stats["ratio"] == pytest.approx(2.0)


def test_repricing_at_the_booked_constants_is_a_no_op_in_ratio():
    """Sanity anchor: priced at 25/40 the ratio against a correctly-booked
    fill is 1.0, which proves the engine's ARITHMETIC is right and only its
    CONSTANT is wrong."""
    _, stats = fr.reprice_rows([_row(post_only="0", fee="0.80")], 25.0, 40.0)
    assert stats["ratio"] == pytest.approx(1.0)


def test_garbage_numerics_do_not_raise():
    rows, stats = fr.reprice_rows(
        [{"fill_size": "abc", "fill_price": None, "post_only": "0",
          "fees_delta_usd": "nope"}], 40.0, 80.0)
    assert float(rows[0]["fees_delta_usd"]) == pytest.approx(0.0)
    assert stats["booked_fees_usd"] == pytest.approx(0.0)


def test_true_constants_are_the_venue_not_the_config():
    """40/80 is Kraken spot Tier 1. If someone 'helpfully' syncs these to
    config.json's 25/40 the whole tool becomes a no-op that reports
    everything is fine."""
    assert fr.TRUE_MAKER_BPS == 40.0
    assert fr.TRUE_TAKER_BPS == 80.0
