"""tests/test_pulse_dashboard.py — the Pulse hero panel's contract.

The Pulse is ONE full-width Business Text panel (marcusolsson-dynamictext-
panel): a single live "one screen, one truth" readout. It lives at the TOP
OF THE COMMAND BOARD — operator decision 2026-07-23 ("integrate it with my
4 boards, not a new one"): the board family stays at four, the standalone
liquiditybot-pulse uid is retired on every import, and the phone view is
Command's viewPanel+kiosk URL. These pins guard the panel's placement and
shape, the exact live queries the template reads, its honest "--" / stale
fallbacks, the render-safety helper lint, and the SANITIZER CONTRACT:
Grafana Cloud strips <style> out of panel content (the board shipped once
as unstyled plain text because of this), so the CSS must ride in the
plugin's dedicated `styles` option and never in `content`.
"""
import re
from pathlib import Path

import scripts.build_trading_dashboard as gen
import scripts.grafana_import as gi

ROOT = Path(__file__).resolve().parents[1]


def _command():
    return gen.DASHBOARDS["liquiditybot_command.json"]


def _pulse_panel(d=None):
    # the single Business Text CONTENT panel on the Command board = the
    # marcusolsson tile that is NOT the id-990 CSS injector
    d = d or _command()
    cands = [p for p in d["panels"]
             if p["type"] == "marcusolsson-dynamictext-panel"
             and p["id"] != gen.INJ_ID]
    assert len(cands) == 1, "exactly one Business Text content panel"
    return cands[0]


# ---- placement: inside Command, not a fifth board ---------------------------
def test_no_standalone_pulse_board_anywhere():
    assert "liquiditybot_pulse.json" not in gen.DASHBOARDS, \
        "the family stays at FOUR boards — Pulse is a Command panel"
    assert "liquiditybot_pulse.json" not in gi.DASHBOARDS
    assert not (ROOT / "docs" / "grafana" / "liquiditybot_pulse.json").exists()
    assert len(gi.DASHBOARDS) == 4


def test_standalone_pulse_uid_is_retired_on_import():
    # the uid shipped once (2026-07-23) — the import run must delete it
    assert "liquiditybot-pulse" in gi.RETIRED_UIDS


def test_pulse_absent_from_shared_nav():
    for d in gen.DASHBOARDS.values():
        nav = {ln["url"] for ln in d["links"]}
        assert "/d/liquiditybot-pulse" not in nav, \
            f'{d["uid"]}: nav still links the retired standalone board'
        assert len(nav) == 4, f'{d["uid"]}: nav must list exactly the 4 boards'


def test_pulse_opens_the_command_board():
    p = _pulse_panel()
    gp = p["gridPos"]
    assert gp["x"] == 0 and gp["y"] == 0 and gp["w"] == 24, \
        "the pulse hero is the board's full-width opening panel"
    assert gp["h"] >= 18, "hero-tall (content column needs ~600px)"
    assert p["options"]["renderMode"] == "data"
    assert p.get("pluginVersion") == "6.3.0"


# ---- the sanitizer contract (why the board once rendered as plain text) -----
def test_pulse_css_rides_in_styles_option_never_in_content():
    o = _pulse_panel()["options"]
    assert "<style" not in o["content"], \
        "Grafana Cloud SANITIZES <style> out of content — CSS must live in " \
        "the plugin's `styles` option (this exact bug shipped once)"
    assert o["styles"].strip(), "styles option empty — the panel renders bare"
    assert ".pulse-wrap{" in o["styles"], "pulse CSS missing from styles"
    assert "styles" in o["editors"], "styles editor must be enabled"


# ---- live queries ------------------------------------------------------------
def test_pulse_targets_hit_the_required_metrics():
    p = _pulse_panel()
    metrics = set()
    for t in p["targets"]:
        metrics |= set(re.findall(r"liquiditybot_[a-z_]+", t["expr"]))
    required = {"liquiditybot_running", "liquiditybot_status_age_sec",
                "liquiditybot_status_stale", "liquiditybot_equity",
                "liquiditybot_daily_pnl", "liquiditybot_weekly_pnl",
                "liquiditybot_code_count_detail", "liquiditybot_ml_labels",
                "liquiditybot_monitor_level", "liquiditybot_ml_use_model"}
    assert required <= metrics, f"missing pulse metrics: {required - metrics}"


def test_pulse_queries_the_exact_reason_codes():
    exprs = " ".join(t["expr"] for t in _pulse_panel()["targets"])
    # time-stop scratches = PT-060, probes held back = SZ-047
    assert 'code="PT-060"' in exprs
    assert 'code="SZ-047"' in exprs


def test_pulse_has_a_range_equity_sparkline():
    # the sparkline is a RANGE series on equity (instant:false, range:true)
    p = _pulse_panel()
    rng = [t for t in p["targets"]
           if "liquiditybot_equity" in t["expr"]
           and t.get("range") is True and t.get("instant") is False]
    assert rng, "no range equity series for the sparkline"


def test_pulse_sparkline_bounds_follow_the_dashboard_range():
    # the y-normalization window (refs N/O) must track the DASHBOARD range the
    # polyline covers — a hardcoded [48h] mis-scales the line on Command's
    # 24h default (and on any keepTime-carried range).
    exprs = " ".join(t["expr"] for t in _pulse_panel()["targets"])
    assert "[$__range]" in exprs, "sparkline bounds must use $__range"
    assert "[48h]" not in exprs, "hardcoded lookback diverges from the range"


def test_pulse_content_has_honest_fallbacks_and_stale():
    o = _pulse_panel()["options"]
    c = o["content"]
    assert "--" in c, "every value needs a '--' empty-state fallback"
    assert "stale" in c.lower(), "must honor liquiditybot_status_stale"
    # pure-Handlebars SVG sparkline (no afterRender/helpers dependency)
    assert "<svg" in c and "polyline" in c, "inline SVG sparkline expected"
    assert not o.get("afterRender"), \
        "content panel must not depend on afterRender JS for the sparkline"


# ---- render-safety: the template must only call helpers that actually exist -
# Business Text v6 (marcusolsson-dynamictext-panel) registers EXACTLY these;
# Handlebars core adds the block/builtin set. A subexpression or {{helper ...}}
# whose name is outside this union hits Handlebars' helperMissing and throws
# "Missing helper", which aborts the WHOLE template render (hero, sparkline,
# rows all vanish -> defaultContent). The board shipped once with an
# unregistered `gte`; this lint closes the entire class, not one symbol.
_BT_HELPERS = {"contains", "date", "eq", "join", "json", "split", "toFixed",
               "startsWith", "endsWith", "match", "variable", "variableValue"}
_HB_CORE = {"if", "unless", "each", "with", "lookup", "log"}
_ALLOWED_HELPERS = _BT_HELPERS | _HB_CORE


def _helper_names(content):
    """Every helper name invoked inside a {{...}} region: leading block/inline
    helper (a name followed by an argument) and any (subexpression ...)."""
    names = set()
    for expr in re.findall(r"\{\{[~#/>]?(.*?)~?\}\}", content, re.DOTALL):
        names |= set(re.findall(r"\(([A-Za-z_]\w*)\s", expr))
        m = re.match(r"([A-Za-z_]\w*)\s+\S", expr.strip())
        if m:
            names.add(m.group(1))
    return names


def test_pulse_uses_only_registered_helpers():
    unknown = _helper_names(
        _pulse_panel()["options"]["content"]) - _ALLOWED_HELPERS
    assert not unknown, (
        "Pulse template calls helper(s) not in Business Text v6 + Handlebars "
        f"core -> 'Missing helper' blanks the whole panel: {sorted(unknown)}")


def test_pulse_never_uses_comparison_helpers():
    # gte/gt/lt/lte are NOT shipped by Business Text; sign/level branching must
    # go through startsWith/eq (built-in) or PromQL, never a math helper.
    c = _pulse_panel()["options"]["content"]
    for bad in ("gte", "gt", "lte", " lt "):
        assert f"({bad.strip()} " not in c, f"forbidden helper subexpr: {bad}"


# ---- money typography + honesty ----------------------------------------------
def test_pulse_hero_groups_thousands():
    # design C1: the one loud element must render $10,000.00, not $10000.00 —
    # grouping is pushed into PromQL (plugin has no math helpers).
    p = _pulse_panel()
    exprs = " ".join(t["expr"] for t in p["targets"])
    assert "/ 1000" in exprs or "/1000" in exprs, "no thousands query"
    assert "% 1000" in exprs or "%1000" in exprs, "no remainder query"
    c = p["options"]["content"]
    # the hero must consume both grouping frames and emit the comma separator
    assert "data.[15]" in c and "data.[16]" in c, "hero ignores group frames"
    assert re.search(r"data\.\[15\][^\n]*?\}\},", c), "no comma between groups"


def test_pulse_pnl_strings_group_thousands():
    # design C1 extends to the P&L strings: daily/weekly money must group too
    # (same PromQL abs/floor/%1000 companions, refIds R-U == frames 17-20),
    # not just the hero — a $1,234.56 week must not render "$1234.56".
    p = _pulse_panel()
    exprs = " ".join(t["expr"] for t in p["targets"])
    assert "liquiditybot_daily_pnl" in exprs and "liquiditybot_weekly_pnl" \
        in exprs and "abs(" in exprs, "P&L grouping companions missing"
    # equity + daily + weekly each get a thousands and a remainder query
    assert exprs.count("/ 1000") + exprs.count("/1000") >= 3, \
        "expected thousands queries for equity + daily + weekly P&L"
    assert exprs.count("% 1000") + exprs.count("%1000") >= 3, \
        "expected remainder queries for equity + daily + weekly P&L"
    c = p["options"]["content"]
    for i in ("17", "18", "19", "20"):
        assert f"data.[{i}]" in c, f"P&L block ignores group frame data.[{i}]"


def test_pulse_flat_pnl_reads_neutral_not_a_loss():
    # design M6: a day/week that rounds to zero must render flat/gray, never a
    # red '-$0.00'. Detected via eq on the toFixed string ('0.00' / '-0.00').
    c = _pulse_panel()["options"]["content"]
    assert '(eq (toFixed Value 2) "-0.00")' in c, \
        "no -0.00 flat guard — a ~flat down day would render red '-$0.00'"
    assert '(eq (toFixed Value 2) "0.00")' in c, "no 0.00 flat guard"
    assert 'class="flat">$0.00 today' in c, "flat day must be neutral $0.00"


def test_pulse_stopped_dot_is_not_green():
    # honesty C2: a cleanly stopped/paused bot (running=0, stale=0) must NOT
    # show the green all-go dot. The neutral 'idle' dot rule lives in the
    # styles option (CSS), the class application in content (template).
    o = _pulse_panel()["options"]
    assert ".pulse-state.idle .pulse-dot{" in o["styles"], \
        "no neutral idle dot rule"
    assert "#8E8E93" in o["styles"] or "#8e8e93" in o["styles"], \
        "idle dot must be neutral gray"
    assert "{{#unless data.[0].[0].Value}} idle" in o["content"], \
        "idle class not applied when running=0"
    assert "{{else}}Stopped{{/if}}" not in o["content"], \
        "must not label a possibly-PAUSED bot as 'Stopped'"


def test_pulse_daily_missing_is_neutral_not_loss():
    # honesty I1: absent daily P&L ('-- today') must not read red (a loss).
    c = _pulse_panel()["options"]["content"]
    assert 'class="loss">-- today' not in c, "'-- today' must not be red"
    assert 'class="flat">-- today' in c, "'-- today' must be neutral"
