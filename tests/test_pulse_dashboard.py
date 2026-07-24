"""tests/test_pulse_dashboard.py — the Pulse hero composition's contract.

The Pulse is the Command board's opening screen — operator decision
2026-07-23 ("integrate it with my 4 boards, not a new one"): the board
family stays at four, the standalone liquiditybot-pulse uid is retired on
every import. It is THREE stacked transparent panels reading as one
composition:

  1. Business Text hero — state line, thousands-grouped equity numeral, P&L.
  2. NATIVE full-bleed equity strip (stat/area sparkline) — Grafana draws it
     itself, so the sanitizer that eats inline SVG (and <style>) can never
     blank it, and it self-scales to the dashboard range.
  3. Business Text rows — the four hairline truth rows + footer.

These pins guard the composition's placement and shape, the exact live
queries, honest fallbacks, the render-safety helper lint, and the
SANITIZER CONTRACT: Grafana Cloud strips <style> and <svg> out of panel
content (the board shipped once as unstyled plain text, and once with the
sparkline silently missing) — CSS must ride in the plugin's `styles`
option and the trend must be a native panel, never inline SVG.
"""
import re
from pathlib import Path

import scripts.build_trading_dashboard as gen
import scripts.grafana_import as gi

ROOT = Path(__file__).resolve().parents[1]


def _command():
    return gen.DASHBOARDS["liquiditybot_command.json"]


def _bt_panels(d=None):
    d = d or _command()
    return [p for p in d["panels"]
            if p["type"] == "marcusolsson-dynamictext-panel"
            and p["id"] != gen.INJ_ID]


def _top():
    tops = [p for p in _bt_panels() if "pulse-top" in p["options"]["content"]]
    assert len(tops) == 1, "exactly one pulse hero panel"
    return tops[0]


def _rows():
    rows = [p for p in _bt_panels() if "pulse-bot" in p["options"]["content"]]
    assert len(rows) == 1, "exactly one pulse rows panel"
    return rows[0]


def _spark():
    cands = [p for p in _command()["panels"]
             if p["type"] == "stat"
             and any("liquiditybot_equity" in t["expr"]
                     for t in p.get("targets", []))
             and p["options"].get("graphMode") == "area"
             and p["options"].get("textMode") == "none"]
    assert len(cands) == 1, "exactly one native equity strip (textMode none)"
    return cands[0]


# ---- placement: inside Command, not a fifth board ---------------------------
def test_no_standalone_pulse_board_anywhere():
    assert "liquiditybot_pulse.json" not in gen.DASHBOARDS, \
        "the family stays at FOUR boards — Pulse is a Command composition"
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


def test_pulse_composition_opens_the_command_board():
    top, spark, rows = _top(), _spark(), _rows()
    assert top["gridPos"]["y"] == 0 and top["gridPos"]["x"] == 0, \
        "the hero opens the board"
    for p in (top, spark, rows):
        assert p["gridPos"]["w"] == 24, "every pulse panel is full-width"
    # strict stack order: hero -> strip -> rows, no gaps
    assert spark["gridPos"]["y"] == top["gridPos"]["h"]
    assert rows["gridPos"]["y"] == spark["gridPos"]["y"] + spark["gridPos"]["h"]
    assert top["options"]["renderMode"] == "data"
    assert rows["options"]["renderMode"] == "data"


# ---- the sanitizer contract (why this shipped broken twice) ------------------
def test_pulse_css_rides_in_styles_option_never_in_content():
    for p in (_top(), _rows()):
        o = p["options"]
        assert "<style" not in o["content"], \
            "Grafana Cloud SANITIZES <style> out of content — CSS must " \
            "live in the plugin's `styles` option (this exact bug shipped)"
        assert o["styles"].strip(), "styles option empty — panel renders bare"
        assert ".pulse-wrap{" in o["styles"], "pulse CSS missing from styles"
        assert "styles" in o["editors"], "styles editor must be enabled"


def test_pulse_trend_is_native_never_inline_svg():
    # the sanitizer also eats <svg> in Business Text content (the sparkline
    # shipped once as an invisible hole) — the trend must be a NATIVE panel.
    for p in (_top(), _rows()):
        assert "<svg" not in p["options"]["content"], \
            "inline SVG gets sanitized — use the native strip panel"
    s = _spark()
    assert s["transparent"] is True
    assert s["options"]["textMode"] == "none", "strip shows no number"
    assert s["options"]["colorMode"] == "none"
    assert s["fieldConfig"]["defaults"]["noValue"], "honest empty state"
    t = s["targets"][0]
    assert t.get("range") is True and t.get("instant") is False, \
        "the strip must be a RANGE query (it IS the sparkline)"


def test_pulse_no_hardcoded_lookback_windows():
    # the strip self-scales to the dashboard range; nothing in the pulse
    # composition may pin a wall-clock window that diverges from it
    exprs = " ".join(t["expr"] for p in (_top(), _rows(), _spark())
                     for t in p["targets"])
    assert "[48h]" not in exprs and "[24h]" not in exprs


# ---- live queries ------------------------------------------------------------
def test_pulse_targets_hit_the_required_metrics():
    metrics = set()
    for p in (_top(), _rows(), _spark()):
        for t in p["targets"]:
            metrics |= set(re.findall(r"liquiditybot_[a-z_]+", t["expr"]))
    required = {"liquiditybot_running", "liquiditybot_status_age_sec",
                "liquiditybot_status_stale", "liquiditybot_equity",
                "liquiditybot_daily_pnl", "liquiditybot_weekly_pnl",
                "liquiditybot_code_count_detail", "liquiditybot_ml_labels",
                "liquiditybot_monitor_level", "liquiditybot_ml_use_model"}
    assert required <= metrics, f"missing pulse metrics: {required - metrics}"


def test_pulse_queries_the_exact_reason_codes():
    exprs = " ".join(t["expr"] for t in _rows()["targets"])
    # time-stop scratches = PT-060, probes held back = SZ-047
    assert 'code="PT-060"' in exprs
    assert 'code="SZ-047"' in exprs


def test_pulse_content_has_honest_fallbacks_and_stale():
    top, rows = _top()["options"], _rows()["options"]
    assert "--" in top["content"] and "--" in rows["content"], \
        "every value needs a '--' empty-state fallback"
    assert "stale" in top["content"].lower(), \
        "must honor liquiditybot_status_stale"
    for o in (top, rows):
        assert not o.get("afterRender"), "no afterRender JS dependency"


# ---- render-safety: the template must only call helpers that actually exist -
# Business Text v6 (marcusolsson-dynamictext-panel) registers EXACTLY these;
# Handlebars core adds the block/builtin set. A subexpression or {{helper ...}}
# whose name is outside this union hits Handlebars' helperMissing and throws
# "Missing helper", which aborts the WHOLE template render (hero, rows all
# vanish -> defaultContent). The board shipped once with an unregistered
# `gte`; this lint closes the entire class, not one symbol.
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
    for p in (_top(), _rows()):
        unknown = _helper_names(p["options"]["content"]) - _ALLOWED_HELPERS
        assert not unknown, (
            "Pulse template calls helper(s) not in Business Text v6 + "
            "Handlebars core -> 'Missing helper' blanks the whole panel: "
            f"{sorted(unknown)}")


def test_pulse_never_uses_comparison_helpers():
    # gte/gt/lt/lte are NOT shipped by Business Text; sign/level branching must
    # go through startsWith/eq (built-in) or PromQL, never a math helper.
    for p in (_top(), _rows()):
        c = p["options"]["content"]
        for bad in ("gte", "gt", "lte", " lt "):
            assert f"({bad.strip()} " not in c, \
                f"forbidden helper subexpr: {bad}"


# ---- money typography + honesty ----------------------------------------------
def test_pulse_hero_groups_thousands():
    # design C1: the one loud element must render $10,000.00, not $10000.00 —
    # grouping is pushed into PromQL (plugin has no math helpers).
    p = _top()
    exprs = " ".join(t["expr"] for t in p["targets"])
    assert "/ 1000" in exprs or "/1000" in exprs, "no thousands query"
    assert "% 1000" in exprs or "%1000" in exprs, "no remainder query"
    c = p["options"]["content"]
    # the hero must consume both grouping frames and emit the comma separator
    assert "data.[6]" in c and "data.[7]" in c, "hero ignores group frames"
    assert re.search(r"data\.\[6\][^\n]*?\}\},", c), "no comma between groups"


def test_pulse_pnl_strings_group_thousands():
    # design C1 extends to the P&L strings: daily/weekly money must group too
    # (same PromQL abs/floor/%1000 companions, frames 8-11), not just the
    # hero — a $1,234.56 week must not render "$1234.56".
    p = _top()
    exprs = " ".join(t["expr"] for t in p["targets"])
    assert "liquiditybot_daily_pnl" in exprs and "liquiditybot_weekly_pnl" \
        in exprs and "abs(" in exprs, "P&L grouping companions missing"
    # equity + daily + weekly each get a thousands and a remainder query
    assert exprs.count("/ 1000") + exprs.count("/1000") >= 3, \
        "expected thousands queries for equity + daily + weekly P&L"
    assert exprs.count("% 1000") + exprs.count("%1000") >= 3, \
        "expected remainder queries for equity + daily + weekly P&L"
    c = p["options"]["content"]
    for i in ("8", "9", "10", "11"):
        assert f"data.[{i}]" in c, f"P&L block ignores group frame data.[{i}]"


def test_pulse_flat_pnl_reads_neutral_not_a_loss():
    # design M6: a day/week that rounds to zero must render flat/gray, never a
    # red '-$0.00'. Detected via eq on the toFixed string ('0.00' / '-0.00').
    c = _top()["options"]["content"]
    assert '(eq (toFixed Value 2) "-0.00")' in c, \
        "no -0.00 flat guard — a ~flat down day would render red '-$0.00'"
    assert '(eq (toFixed Value 2) "0.00")' in c, "no 0.00 flat guard"
    assert 'class="flat">$0.00 today' in c, "flat day must be neutral $0.00"


def test_pulse_stopped_dot_is_not_green():
    # honesty C2: a cleanly stopped/paused bot (running=0, stale=0) must NOT
    # show the green all-go dot. The neutral 'idle' dot rule lives in the
    # styles option (CSS), the class application in content (template).
    o = _top()["options"]
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
    c = _top()["options"]["content"]
    assert 'class="loss">-- today' not in c, "'-- today' must not be red"
    assert 'class="flat">-- today' in c, "'-- today' must be neutral"


def test_pulse_desktop_scaleup_present():
    # the phone column reads as a postage stamp on a wide desktop without a
    # scale-up; the media query widens the column at >=900px.
    assert "@media (min-width:900px)" in _top()["options"]["styles"]
