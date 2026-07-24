"""tests/test_context_parsers.py — Compounder Phase B context engine:
source parsers (FRED CSV, DefiLlama stablecoins, CFTC COT) and the two
dial functions (`stress_dial`, `flow_dials`). No `ContextFeed` class yet
(later task) — these are pure, network-free functions exercised against
REAL fetched fixtures (type/range assertions only, never a pinned market
value — those change) plus crafted malformed/edge-case fixtures and
synthetic exact-math inputs for the dials.

Real fixtures were fetched 2026-07-24 (see
`tests/fixtures/context/README.md` for the exact curl commands, byte
sizes, and the CFTC column-position verification method).
"""
import csv
import io
import math
from pathlib import Path

import pytest

from data.context_engine import (
    flow_dials,
    parse_cot_btc_lev_net,
    parse_fred_csv,
    parse_stablecoin_total,
    stress_dial,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "context"


def _read(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


# ---- parse_fred_csv: real fixtures (type/range only) ----------------------

def test_parse_fred_csv_dff_real_fixture_plausible_range():
    value = parse_fred_csv(_read("fred_dff.csv"))
    assert isinstance(value, float)
    assert math.isfinite(value)
    assert 0.0 <= value <= 25.0            # effective fed funds rate, %


def test_parse_fred_csv_t10y2y_real_fixture_plausible_range():
    value = parse_fred_csv(_read("fred_t10y2y.csv"))
    assert isinstance(value, float)
    assert math.isfinite(value)
    assert -5.0 <= value <= 5.0             # 10y-2y spread, percentage points


def test_parse_fred_csv_vixcls_real_fixture_plausible_range():
    value = parse_fred_csv(_read("fred_vixcls.csv"))
    assert isinstance(value, float)
    assert math.isfinite(value)
    assert 5.0 <= value <= 150.0


# ---- parse_fred_csv: header tolerance + "." skip (documented format) ------

def test_parse_fred_csv_tolerates_real_header_spelling():
    # the real fixtures' header is "observation_date,<ID>", not the
    # interface doc's "DATE,<ID>" — the parser must not depend on the
    # header's literal text, only on skipping row 0.
    text = "observation_date,DFF\n2026-01-01,5.25\n"
    assert parse_fred_csv(text) == 5.25


def test_parse_fred_csv_skips_dot_missing_marker():
    text = "DATE,DFF\n2026-01-01,5.25\n2026-01-02,.\n"
    assert parse_fred_csv(text) == 5.25


def test_parse_fred_csv_all_missing_returns_none():
    text = "DATE,DFF\n2026-01-01,.\n2026-01-02,.\n"
    assert parse_fred_csv(text) is None


# ---- parse_fred_csv: malformed/empty -> None, never raise -----------------

def test_parse_fred_csv_empty_returns_none():
    assert parse_fred_csv(_read("fred_malformed_empty.csv")) is None
    assert parse_fred_csv("") is None


def test_parse_fred_csv_truncated_returns_none():
    assert parse_fred_csv(_read("fred_malformed_truncated.csv")) is None


def test_parse_fred_csv_html_error_page_returns_none():
    assert parse_fred_csv(_read("fred_malformed_html.csv")) is None


def test_parse_fred_csv_none_input_returns_none():
    assert parse_fred_csv(None) is None


# ---- parse_stablecoin_total: real fixture (type/range only) --------------

def test_parse_stablecoin_total_real_fixture_plausible_range():
    value = parse_stablecoin_total(_read("stablecoins.json"))
    assert isinstance(value, float)
    assert math.isfinite(value)
    assert 5e10 <= value <= 5e12


# ---- parse_stablecoin_total: tolerant-skip / shape edge cases -------------

def test_parse_stablecoin_total_tolerates_missing_circulating_key():
    text = (
        '{"peggedAssets": ['
        '{"name": "A", "circulating": {"peggedUSD": 100.0}},'
        '{"name": "B"},'
        '{"name": "C", "circulating": {}},'
        '{"name": "D", "circulating": {"peggedUSD": 50.0}}'
        ']}'
    )
    assert parse_stablecoin_total(text) == 150.0


def test_parse_stablecoin_total_missing_peggedassets_key_returns_none():
    assert parse_stablecoin_total('{"chains": []}') is None


def test_parse_stablecoin_total_empty_peggedassets_returns_none():
    assert parse_stablecoin_total('{"peggedAssets": []}') is None


# ---- parse_stablecoin_total: malformed/empty -> None, never raise --------

def test_parse_stablecoin_total_empty_returns_none():
    assert parse_stablecoin_total(_read("stablecoins_malformed_empty.json")) is None
    assert parse_stablecoin_total("") is None


def test_parse_stablecoin_total_truncated_returns_none():
    assert parse_stablecoin_total(
        _read("stablecoins_malformed_truncated.json")) is None


def test_parse_stablecoin_total_html_error_page_returns_none():
    assert parse_stablecoin_total(_read("stablecoins_malformed_html.json")) is None


def test_parse_stablecoin_total_none_input_returns_none():
    assert parse_stablecoin_total(None) is None


def test_parse_stablecoin_total_garbage_json_returns_none():
    assert parse_stablecoin_total("not json at all { [ ") is None


# ---- parse_cot_btc_lev_net: real fixture (type/finite only) --------------

def test_parse_cot_btc_lev_net_real_fixture_finite_float():
    value = parse_cot_btc_lev_net(_read("cot_finfut.txt"))
    assert isinstance(value, float)
    assert math.isfinite(value)


# ---- parse_cot_btc_lev_net: exact math + row-selection, synthetic --------

def test_parse_cot_btc_lev_net_exact_math_synthetic_row():
    # columns located BY DOCUMENTED POSITION (0-indexed): market name=0,
    # Lev_Money_Positions_Long_All=14, _Short_All=15 — verified against
    # the real fixture (see tests/fixtures/context/README.md). Synthetic
    # 87-field row (same as the real fixture shape); padding fields 1-13
    # and 16-86 are irrelevant to the math.
    fields = (
        ['"BITCOIN - CHICAGO MERCANTILE EXCHANGE"'] +
        list(map(str, range(1, 14))) +
        ['4015', '11506'] +
        ['x'] * 71
    )
    row = ','.join(fields)
    assert parse_cot_btc_lev_net(row) == 4015.0 - 11506.0


def test_parse_cot_btc_lev_net_takes_first_matching_row_not_second():
    # Both rows are 87-field synthetic rows; first row (MICRO) qualifies as
    # BITCOIN+CHICAGO MERCANTILE too — the FIRST such row wins.
    micro_fields = (
        ['"MICRO BITCOIN - CHICAGO MERCANTILE EXCHANGE"'] +
        list(map(str, range(1, 14))) +
        ['100', '200'] +
        ['x'] * 71
    )
    bitcoin_fields = (
        ['"BITCOIN - CHICAGO MERCANTILE EXCHANGE"'] +
        list(map(str, range(1, 14))) +
        ['4015', '11506'] +
        ['x'] * 71
    )
    micro_first = ','.join(micro_fields) + '\n' + ','.join(bitcoin_fields) + '\n'
    assert parse_cot_btc_lev_net(micro_first) == 100.0 - 200.0


def test_parse_cot_btc_lev_net_skips_non_matching_rows():
    # Both rows are 87-field synthetic rows; first doesn't match, second matches.
    swiss_fields = (
        ['"SWISS FRANC - CHICAGO MERCANTILE EXCHANGE"'] +
        list(map(str, range(1, 14))) +
        ['999', '999'] +
        ['x'] * 71
    )
    bitcoin_fields = (
        ['"BITCOIN - CHICAGO MERCANTILE EXCHANGE"'] +
        list(map(str, range(1, 14))) +
        ['4015', '11506'] +
        ['x'] * 71
    )
    text = ','.join(swiss_fields) + '\n' + ','.join(bitcoin_fields) + '\n'
    assert parse_cot_btc_lev_net(text) == 4015.0 - 11506.0


def test_parse_cot_btc_lev_net_wrong_exchange_not_matched():
    text = ('"BITCOIN PERP - COINBASE DERIVATIVES, LLC",1,2,3,4,5,6,7,8,9,'
        '10,11,12,13,100,200\n')
    assert parse_cot_btc_lev_net(text) is None


# ---- parse_cot_btc_lev_net: malformed/empty/no-match -> None -------------

def test_parse_cot_btc_lev_net_empty_returns_none():
    assert parse_cot_btc_lev_net(_read("cot_malformed_empty.txt")) is None
    assert parse_cot_btc_lev_net("") is None


def test_parse_cot_btc_lev_net_truncated_returns_none():
    assert parse_cot_btc_lev_net(_read("cot_malformed_truncated.txt")) is None


def test_parse_cot_btc_lev_net_html_error_page_returns_none():
    assert parse_cot_btc_lev_net(_read("cot_malformed_html.txt")) is None


def test_parse_cot_btc_lev_net_no_bitcoin_row_returns_none():
    # real, complete rows from the real fixture (CAD/CHF/GBP/JPY/EUR) —
    # none mention BITCOIN.
    assert parse_cot_btc_lev_net(_read("cot_no_bitcoin.txt")) is None


def test_parse_cot_btc_lev_net_none_input_returns_none():
    assert parse_cot_btc_lev_net(None) is None


def test_parse_cot_btc_lev_net_malformed_numeric_field_returns_none():
    text = ('"BITCOIN - CHICAGO MERCANTILE EXCHANGE",1,2,3,4,5,6,7,8,9,10,'
        '11,12,13,NOTANUMBER,11506\n')
    assert parse_cot_btc_lev_net(text) is None


# ---- parse_cot_btc_lev_net: schema drift guard (strict 87-field shape) -----

def test_cot_real_fixture_has_verified_field_count():
    """Pins _COT_EXPECTED_FIELDS=87 against the real fixture. If this
    fails, the fixture's shape has drifted — STOP and report BLOCKED with
    the actual count instead of changing the test."""
    text = _read("cot_finfut.txt")
    rows = list(csv.reader(io.StringIO(text)))
    for row in rows:
        if "BITCOIN" in row[0].upper() and "CHICAGO MERCANTILE" in row[0].upper():
            assert len(row) == 87
            return
    # If we reach here, the fixture has no Bitcoin row — also a shape drift
    pytest.fail("No BITCOIN + CHICAGO MERCANTILE row found in fixture")


def test_cot_row_with_wrong_field_count_returns_none():
    """A row with "BITCOIN" and "CHICAGO MERCANTILE" but wrong field count
    (old minimum-length guard would have passed ~20 fields) must return
    None; the strict 87-field shape guard prevents silent schema drift."""
    text = ('"BITCOIN - CHICAGO MERCANTILE EXCHANGE",1,2,3,4,5,6,7,8,9,'
        '10,11,12,13,4015,11506')
    # This is a 16-field row; the real fixture has 87. Old guard would pass
    # it; new guard must skip it -> returns None.
    assert parse_cot_btc_lev_net(text) is None


def test_cot_real_fixture_still_parses():
    """Verify the real fixture still parses to a finite float after
    tightening the shape guard."""
    value = parse_cot_btc_lev_net(_read("cot_finfut.txt"))
    assert isinstance(value, float)
    assert math.isfinite(value)


# ---- stress_dial: exact math -----------------------------------------------

def test_stress_dial_exact_math_defaults():
    # dff_term = clip_z(0.25, 0, 0.5, 2.0) = 0.5
    # curve_term = clip_z(-(-0.3), 0, 0.5, 2.0) = clip_z(0.3,0,0.5,2.0)=0.6
    # vix_term = clip_z(25.0, 20.0, 10.0, 2.0) = 0.5
    # mean = (0.5+0.6+0.5)/3
    result = stress_dial(0.25, -0.3, 25.0, {})
    assert result == pytest.approx((0.5 + 0.6 + 0.5) / 3.0)


def test_stress_dial_inversion_reads_as_positive_stress():
    # an inverted curve (negative t10y2y) must contribute POSITIVELY to
    # the stress mean (sign-flip requirement) — isolate the effect by
    # zeroing the other two terms at their centers.
    inverted = stress_dial(0.0, -1.0, 20.0, {})
    normal = stress_dial(0.0, 1.0, 20.0, {})
    assert inverted is not None and normal is not None
    assert inverted > 0.0
    assert normal < 0.0


def test_stress_dial_clips_at_bound():
    # t10y2y very negative (deeply inverted) so its sign-flipped term also
    # clips to +2.0, matching the other two maxed-out terms.
    result = stress_dial(100.0, -100.0, 1000.0, {})
    assert result == pytest.approx(2.0)


def test_stress_dial_cfg_overrides_anchor():
    default_result = stress_dial(1.0, 0.0, 20.0, {})
    custom_result = stress_dial(1.0, 0.0, 20.0, {"dff_delta_scale": 1.0})
    assert default_result != custom_result
    assert custom_result == pytest.approx((1.0 + 0.0 + 0.0) / 3.0)


# ---- stress_dial: None propagation (no partial dials) ---------------------

def test_stress_dial_dff_none_propagates():
    assert stress_dial(None, 0.0, 20.0, {}) is None


def test_stress_dial_t10y2y_none_propagates():
    assert stress_dial(0.0, None, 20.0, {}) is None


def test_stress_dial_vix_none_propagates():
    assert stress_dial(0.0, 0.0, None, {}) is None


def test_stress_dial_all_none_propagates():
    assert stress_dial(None, None, None, {}) is None


# ---- flow_dials: exact math ------------------------------------------------

def test_flow_dials_exact_math_defaults():
    # cot_delta_z = clip_z(15000-10000, 0, 5000.0, 2.0) = 1.0
    # stable_wk_pct = 100*(1.05e11-1.0e11)/1.0e11 = 5.0
    cot_delta_z, stable_wk_pct = flow_dials(15000.0, 10000.0, 1.05e11, 1.0e11, {})
    assert cot_delta_z == pytest.approx(1.0)
    assert stable_wk_pct == pytest.approx(5.0)


def test_flow_dials_cfg_overrides_cot_scale():
    cot_delta_z, _ = flow_dials(15000.0, 10000.0, 1.0e11, 1.0e11,
                                {"cot_delta_scale": 10000.0, "clip": 3.0})
    assert cot_delta_z == pytest.approx(0.5)


# ---- flow_dials: independent None-propagation (that dial only) -----------

def test_flow_dials_missing_cot_prev_blanks_only_cot():
    cot_delta_z, stable_wk_pct = flow_dials(15000.0, None, 1.05e11, 1.0e11, {})
    assert cot_delta_z is None
    assert stable_wk_pct == pytest.approx(5.0)


def test_flow_dials_missing_cot_now_blanks_only_cot():
    cot_delta_z, stable_wk_pct = flow_dials(None, 10000.0, 1.05e11, 1.0e11, {})
    assert cot_delta_z is None
    assert stable_wk_pct == pytest.approx(5.0)


def test_flow_dials_missing_stable_prev_blanks_only_stable():
    cot_delta_z, stable_wk_pct = flow_dials(15000.0, 10000.0, 1.05e11, None, {})
    assert cot_delta_z == pytest.approx(1.0)
    assert stable_wk_pct is None


def test_flow_dials_missing_stable_now_blanks_only_stable():
    cot_delta_z, stable_wk_pct = flow_dials(15000.0, 10000.0, None, 1.0e11, {})
    assert cot_delta_z == pytest.approx(1.0)
    assert stable_wk_pct is None


def test_flow_dials_stable_prev_zero_or_negative_blanks_stable():
    _, stable_wk_pct_zero = flow_dials(15000.0, 10000.0, 1.05e11, 0.0, {})
    _, stable_wk_pct_neg = flow_dials(15000.0, 10000.0, 1.05e11, -5.0, {})
    assert stable_wk_pct_zero is None
    assert stable_wk_pct_neg is None


def test_flow_dials_all_none_returns_none_none():
    assert flow_dials(None, None, None, None, {}) == (None, None)
