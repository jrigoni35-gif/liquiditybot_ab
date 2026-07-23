"""tests/test_pulse_dashboard.py — the 5th "Pulse" board's contract.

Pulse is ONE full-width Business Text panel (marcusolsson-dynamictext-panel):
a single live "one screen, one truth" readout. It is generator-owned exactly
like the other four boards (generator == shipped JSON is enforced by
test_trading_dashboard.test_generator_matches_shipped_json). These pins guard
Pulse's identity, its single-panel shape, the exact live queries the template
reads, its honest "--" / stale fallbacks, and that it rides the shared nav +
CSS injector convention.
"""
import re
from pathlib import Path

import scripts.build_trading_dashboard as gen
import scripts.grafana_import as gi

ROOT = Path(__file__).resolve().parents[1]
FNAME = "liquiditybot_pulse.json"


def _board():
    return gen.DASHBOARDS[FNAME]


def _content_panel(d):
    # the single Business Text CONTENT panel = the marcusolsson tile that is
    # NOT the id-990 CSS injector
    cands = [p for p in d["panels"]
             if p["type"] == "marcusolsson-dynamictext-panel"
             and p["id"] != gen.INJ_ID]
    assert len(cands) == 1, "exactly one Business Text content panel"
    return cands[0]


def test_pulse_registered_in_both_lists():
    assert FNAME in gen.DASHBOARDS, "Pulse not registered in the generator"
    assert FNAME in gi.DASHBOARDS, "Pulse not in the grafana_import push list"


def test_pulse_json_file_shipped():
    assert (ROOT / "docs" / "grafana" / FNAME).exists(), \
        "regenerate: python scripts/build_trading_dashboard.py"


def test_pulse_uid_and_title():
    d = _board()
    assert d["uid"] == "liquiditybot-pulse"
    assert d["title"] == "Pulse"


def test_pulse_defaults_to_48h_window():
    # the sparkline reads the DASHBOARD time range; it must default to 48h
    assert _board()["time"] == {"from": "now-48h", "to": "now"}
    assert _board()["refresh"] == "30s"


def test_pulse_is_one_fullwidth_tall_business_text_panel():
    d = _board()
    content = [p for p in d["panels"]
               if p["type"] not in ("row",) and p["id"] != gen.INJ_ID]
    assert len(content) == 1, "Pulse is exactly one content panel"
    p = content[0]
    assert p["type"] == "marcusolsson-dynamictext-panel"
    gp = p["gridPos"]
    assert gp["x"] == 0 and gp["w"] == 24, "full width"
    assert gp["h"] >= 26, "hero-tall"
    assert p["options"]["renderMode"] == "data"
    assert p.get("pluginVersion") == "6.3.0"


def test_pulse_injector_present_and_single():
    inj = [p for p in _board()["panels"]
           if p["type"] == "marcusolsson-dynamictext-panel"
           and p["id"] == gen.INJ_ID]
    assert len(inj) == 1, "exactly one CSS injector (id 990)"


def test_pulse_targets_hit_the_required_metrics():
    p = _content_panel(_board())
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
    exprs = " ".join(t["expr"] for t in _content_panel(_board())["targets"])
    # Brief 2 §4: time-stop scratches = PT-060, probes held back = SZ-047
    assert 'code="PT-060"' in exprs
    assert 'code="SZ-047"' in exprs


def test_pulse_has_a_range_equity_sparkline():
    # the sparkline is a RANGE series on equity (instant:false, range:true)
    p = _content_panel(_board())
    rng = [t for t in p["targets"]
           if "liquiditybot_equity" in t["expr"]
           and t.get("range") is True and t.get("instant") is False]
    assert rng, "no range equity series for the sparkline"


def test_pulse_content_has_honest_fallbacks_and_stale():
    c = _content_panel(_board())["options"]["content"]
    assert "--" in c, "every value needs a '--' empty-state fallback"
    assert "stale" in c.lower(), "must honor liquiditybot_status_stale"
    # pure-Handlebars SVG sparkline (no afterRender/helpers dependency)
    assert "<svg" in c and "polyline" in c, "inline SVG sparkline expected"
    assert not _content_panel(_board())["options"].get("afterRender"), \
        "content panel must not depend on afterRender JS for the sparkline"


def test_pulse_in_shared_nav_on_every_board():
    for d in gen.DASHBOARDS.values():
        nav = {ln["url"] for ln in d["links"]}
        assert "/d/liquiditybot-pulse" in nav, \
            f'{d["uid"]}: Pulse missing from shared nav'


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
        _content_panel(_board())["options"]["content"]) - _ALLOWED_HELPERS
    assert not unknown, (
        "Pulse template calls helper(s) not in Business Text v6 + Handlebars "
        f"core -> 'Missing helper' blanks the whole panel: {sorted(unknown)}")


def test_pulse_never_uses_comparison_helpers():
    # gte/gt/lt/lte are NOT shipped by Business Text; sign/level branching must
    # go through startsWith/eq (built-in) or PromQL, never a math helper.
    c = _content_panel(_board())["options"]["content"]
    for bad in ("gte", "gt", "lte", " lt "):
        assert f"({bad.strip()} " not in c, f"forbidden helper subexpr: {bad}"


def test_pulse_hero_groups_thousands():
    # design C1: the one loud element must render $10,000.00, not $10000.00 —
    # grouping is pushed into PromQL (plugin has no math helpers).
    p = _content_panel(_board())
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
    p = _content_panel(_board())
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
    c = _content_panel(_board())["options"]["content"]
    assert '(eq (toFixed Value 2) "-0.00")' in c, \
        "no -0.00 flat guard — a ~flat down day would render red '-$0.00'"
    assert '(eq (toFixed Value 2) "0.00")' in c, "no 0.00 flat guard"
    assert 'class="flat">$0.00 today' in c, "flat day must be neutral $0.00"


def test_pulse_stopped_dot_is_not_green():
    # honesty C2: a cleanly stopped/paused bot (running=0, stale=0) must NOT
    # show the green all-go dot. A neutral 'idle' dot class must exist and the
    # state div must apply it when not running and not stale.
    c = _content_panel(_board())["options"]["content"]
    assert ".pulse-state.idle .pulse-dot{" in c, "no neutral idle dot rule"
    assert "#8E8E93" in c or "#8e8e93" in c, "idle dot must be neutral gray"
    assert "{{#unless data.[0].[0].Value}} idle" in c, \
        "idle class not applied when running=0"
    assert "{{else}}Stopped{{/if}}" not in c, \
        "must not label a possibly-PAUSED bot as 'Stopped'"


def test_pulse_daily_missing_is_neutral_not_loss():
    # honesty I1: absent daily P&L ('-- today') must not read red (a loss).
    c = _content_panel(_board())["options"]["content"]
    assert 'class="loss">-- today' not in c, "'-- today' must not be red"
    assert 'class="flat">-- today' in c, "'-- today' must be neutral"
