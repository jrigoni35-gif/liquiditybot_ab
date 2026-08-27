"""Context-availability wiring (input-feed audit 2026-08-07, owed 41b).

THE DEFECT: the extras dict consulted no `.available` flags, and a dead
feed's neutral zeros are byte-identical to genuine neutral AND to the
historical padding neutrals (ml/features.py CONTEXT_NEUTRAL) - the model
and every offline consumer were structurally unable to distinguish
"options feed down" from "options flat" from "row predates the feature".

THE FIX (0 model DoF - the 2026-08-08 DoF adjudication keeps the feature
ledger closed): _feature_extras captures an `avail` truth dict at build
time; it rides candidate rows, order meta and pending tuples into four
trailing BOOKKEEPING columns (AVAIL_COLS), with "" reserved for UNKNOWN
(legacy rows / uncarried paths) - never conflated with "0" = feed was
genuinely down. DF-020/DF-021 latch the degradation episode in the log,
once per transition, same discipline as DF-010/FW-080.
"""
import csv
import logging
from types import SimpleNamespace

import numpy as np

from main import LiquidityBot, _context_avail_check
from ml.features import FEATURE_NAMES
from ml.history import AVAIL_COLS, CandidateLabeler, HistoryStore


# ---------------------------------------------------------------- helpers
def _shell_bot() -> LiquidityBot:
    """test_feature_trio's _shell_bot: only what _feature_extras reads."""
    b = LiquidityBot.__new__(LiquidityBot)
    b.view = {}
    b.kraken_books = {}
    b._last_imb = {}
    b._regime_since = {}
    b._manip_scores = {}
    b._wl_p95, b._wl_thr = 1.27, 1.45
    b.liq = SimpleNamespace(state=lambda a: SimpleNamespace(
        spoof_score=0.0, imbalance_whiplash=0.0, depth_ratio=1.0))
    b.thales = SimpleNamespace(feature_scores=lambda a, now: {})
    return b


def _snapshots(web_up=True, eq_up=True, opt_up=True, frozen=False):
    web = SimpleNamespace(fear_greed=50.0, dominance_delta=0.0,
                          available=web_up)
    risk = SimpleNamespace(risk_z=0.0, opt_pcr_z=0.0, opt_oi_pcr_z=0.0,
                           opt_iv_skew=0.0, available=eq_up,
                           options_available=opt_up, quotes_frozen=frozen)
    return web, risk


def _rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


_FEATS = np.zeros(len(FEATURE_NAMES))


# ------------------------------------------------------------ extras truth
def test_extras_carry_feed_availability_truth():
    bot = _shell_bot()
    web, risk = _snapshots(web_up=True, eq_up=False, opt_up=True,
                           frozen=True)
    extras = bot._feature_extras("BTC", {}, web, risk, None, 1e9)
    assert extras["avail"] == {"web": True, "equity": False,
                               "options": True, "frozen": True}


def test_extras_default_unavailable_on_flagless_snapshots():
    """A snapshot double without the flags (pre-41a shapes) must read as
    NOT available - never as silently fine."""
    bot = _shell_bot()
    web = SimpleNamespace(fear_greed=50.0, dominance_delta=0.0)
    risk = SimpleNamespace(risk_z=0.0, opt_pcr_z=0.0, opt_oi_pcr_z=0.0,
                           opt_iv_skew=0.0)
    extras = bot._feature_extras("BTC", {}, web, risk, None, 1e9)
    assert extras["avail"] == {"web": False, "equity": False,
                               "options": False, "frozen": False}


# ------------------------------------------------------------ DF-020 latch
def test_degradation_logs_df020_once_per_episode(caplog):
    bot = SimpleNamespace()
    down = {"web": False, "equity": True, "options": True, "frozen": False}
    up = {"web": True, "equity": True, "options": True, "frozen": False}
    with caplog.at_level(logging.INFO, logger="liquiditybot.main"):
        _context_avail_check(bot, down)     # episode begins -> DF-020
        _context_avail_check(bot, down)     # same state -> silent
        _context_avail_check(bot, down)
        _context_avail_check(bot, up)       # recovery -> DF-021
        _context_avail_check(bot, up)       # still up -> silent
    msgs = [r.getMessage() for r in caplog.records]
    assert sum("DF-020" in m for m in msgs) == 1
    assert sum("DF-021" in m for m in msgs) == 1


def test_degradation_composition_change_relogs(caplog):
    """{web} -> {web, options} is NEW information, not the same episode."""
    bot = SimpleNamespace()
    with caplog.at_level(logging.INFO, logger="liquiditybot.main"):
        _context_avail_check(bot, {"web": False, "equity": True,
                                   "options": True, "frozen": False})
        _context_avail_check(bot, {"web": False, "equity": True,
                                   "options": False, "frozen": False})
    msgs = [r.getMessage() for r in caplog.records]
    assert sum("DF-020" in m for m in msgs) == 2
    assert "options" in msgs[-1]


def test_frozen_counts_as_degraded(caplog):
    bot = SimpleNamespace()
    with caplog.at_level(logging.WARNING, logger="liquiditybot.main"):
        _context_avail_check(bot, {"web": True, "equity": True,
                                   "options": True, "frozen": True})
    assert any("DF-020" in r.getMessage() and "frozen" in r.getMessage()
               for r in caplog.records)


# ------------------------------------------------------------ corpus rows
def test_header_ends_with_avail_columns(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    # label_ret_pct (schema 94, 2026-08-24) appended after the avail
    # block. control_arm (schema 95, 2026-08-27) appended after THAT -
    # append-at-END discipline, so avail is now third-from-last.
    assert hs._header[-1] == "control_arm"
    assert hs._header[-2] == "label_ret_pct"
    assert hs._header[-2 - len(AVAIL_COLS):-2] == list(AVAIL_COLS)


def test_live_row_roundtrips_avail_flags(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("p1", "BTC", "long", _FEATS,
                 avail={"web": True, "equity": True, "options": False,
                        "frozen": True})
    hs.log_close("p1", 5.0)
    row = _rows(hs.path)[0]
    assert [row[c] for c in AVAIL_COLS] == ["1", "1", "0", "1"]


def test_uncarried_paths_write_blank_unknown_never_false(tmp_path):
    """"" = UNKNOWN. Writing "0" for an unrecorded row would claim the
    feed was measured down when nothing measured anything."""
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("p1", "BTC", "long", _FEATS)          # no avail kwarg
    hs.log_close("p1", -1.0)
    # legacy 8-tuple pending: a pre-41b snapshot restored post-upgrade
    hs._pending["p2"] = ("ETH", "short", _FEATS.copy(), 123.0, False,
                         "", "5m", {})
    hs.log_close("p2", 2.0)
    for row in _rows(hs.path):
        assert [row[c] for c in AVAIL_COLS] == ["", "", "", ""]


def test_candidate_register_stores_avail_for_label_time(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    lab = CandidateLabeler(hs, {})
    flags = {"web": False, "equity": True, "options": True,
             "frozen": False}
    assert lab.register("BTC", "long", np.arange(len(FEATURE_NAMES),
                                                 dtype=float),
                        0.01, 1000.0, avail=flags)
    assert lab._cands[-1]["avail"] == flags
    # and a legacy candidate dict (no key) forwards None -> blanks
    assert {"disp": "confirmed"}.get("avail") is None
