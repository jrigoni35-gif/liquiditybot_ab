"""THE REMOTE PARTY MUST NEVER CHOOSE WHERE WE LOOK NEXT.

THE DEFECT CLASS. A validator accepts a record that carries BOTH the value
under scrutiny AND a field naming where to confirm it (`canonical_source`,
`docs_url`, `homepage`). The gate's escape hatch says "re-confirm against
canonical_source". The verifier fetches that URL, finds agreement, and reports
"verified against canonical documentation" - but the authority was supplied by
the party being checked. Agreement is guaranteed and carries zero evidential
weight, while the REPORT reads like independent confirmation. That is worse
than no check: it manufactures unearned confidence and terminates scrutiny.

CLAUDE.md already states the law this violates - "a gate's release condition
must never depend on the thing it blocks" - and records FOUR incidents in this
repo sharing that shape. This file pins the ingestion plane against a fifth.

MEASURED 2026-09-05, and this is a real negative rather than an unrun scan:
`sentiment.scanner.parse_rss_items` extracts ONLY title and pubDate; a
repo-wide grep for link/href extraction across sentiment/, context_engine and
webdata_feed returns nothing; every fetch site's URL derives from a module
constant or a config key. The property HOLDS today. These pins keep it true,
because the cheap way to break it is to add "follow the item's <link>" to a
parser and never notice that a hostile feed now steers our egress.

WHAT THIS DOES NOT CLAIM. It does not prove the system is unexploitable. It
pins one specific, mechanically-checkable property: no URL we fetch is read
out of a response we fetched. Prompt-injection through fetched CONTENT (as
opposed to fetched LOCATION) is a different problem and is not covered here.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Modules that parse REMOTE, third-party-controlled payloads.
_INGESTION_PARSERS = [
    ("sentiment/scanner.py", ("parse_rss_items", "parse_hn_posts")),
]

# Field names whose value is a LOCATION. If a parser of remote content reads
# one of these, the remote party has been handed influence over where we go
# next - which is the whole defect. Extraction is the tripwire; whether the
# value is fetched today is not the point, because the next edit is what
# fetches it.
_LOCATION_FIELDS = {
    "link", "links", "href", "url", "uri", "src", "location", "endpoint",
    "canonical", "canonical_source", "canonical_url", "docs_url", "homepage",
    "redirect", "redirect_url", "callback", "webhook", "next", "next_url",
}

# Every module in shipped scope permitted to open a network connection.
# An exact inventory, in the style this repo already uses for board panels:
# a NEW fetch site anywhere else reddens this and has to be justified.
#
# Covers HTTP *and* websocket egress. The first cut only matched HTTP verbs,
# and the inventory's own bidirectional half caught that immediately:
# data/ws_feed.py opens connections via `websockets.connect` against wss://
# constants and matched nothing, so it sat in the allowlist as a stale entry
# claiming coverage the regex did not provide. An egress inventory blind to a
# whole transport is exactly the kind of quiet allowlist this pin warns about.
_FETCH_CALLS = re.compile(
    r"\b(?:requests\.(?:get|post|put|patch|delete)|urlopen|_urlopen|"
    r"urlretrieve|session\.(?:get|post|put|patch|delete)|"
    r"websockets?\.connect|ws_connect)\s*\(|[\"']wss?://")
_ALLOWED_FETCH_MODULES = {
    "core/alerts.py",            # operator webhook, from config
    "core/venue_fees.py",        # hardcoded public schedule endpoint
    "data/context_engine.py",
    "data/kraken_feed.py",
    "data/webdata_feed.py",
    "data/_http.py",
    "data/ws_feed.py",
    "sentiment/scanner.py",
}
_SHIPPED = ("core", "data", "execution", "ml", "risk", "regime", "strategies",
            "sentiment", "api")


def _iter_shipped_py():
    for pkg in _SHIPPED:
        for p in sorted((ROOT / pkg).rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            yield p


# --------------------------------------------------------------- the pins
@pytest.mark.parametrize("relpath,funcs", _INGESTION_PARSERS)
def test_remote_payload_parsers_extract_no_location_field(relpath, funcs):
    """A parser of remote content must not read a URL-shaped field out of it.

    This is the tripwire, not the exploit: extracting the field is what makes
    the next edit ("...and fetch it") a one-liner nobody reviews.
    """
    tree = ast.parse((ROOT / relpath).read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in funcs:
            continue
        for sub in ast.walk(node):
            # findtext("link") / get("url") / hit["href"] / .find("link")
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                if sub.value.strip().lower() in _LOCATION_FIELDS:
                    offenders.append(f"{node.name}: string {sub.value!r}")
            if isinstance(sub, ast.Attribute) and \
                    sub.attr.lower() in _LOCATION_FIELDS:
                offenders.append(f"{node.name}: attribute .{sub.attr}")
    assert not offenders, (
        f"{relpath} parses a LOCATION field out of remote content: "
        f"{offenders}. A third party now influences where this process "
        f"connects next. If this is deliberate, the fetch must go through an "
        f"explicit allowlist and this pin must be amended with the reason.")


def test_fetch_sites_are_an_exact_inventory():
    """No new network egress in shipped scope without amending this list."""
    found = set()
    for p in _iter_shipped_py():
        if _FETCH_CALLS.search(p.read_text(encoding="utf-8")):
            found.add(p.relative_to(ROOT).as_posix())
    added = found - _ALLOWED_FETCH_MODULES
    removed = _ALLOWED_FETCH_MODULES - found
    assert not added, (
        f"new network fetch site(s) in shipped scope: {sorted(added)}. Add "
        f"them here deliberately, having checked the URL cannot be chosen by "
        f"a remote party.")
    assert not removed, (
        f"these modules no longer fetch: {sorted(removed)} - trim the "
        f"inventory so it keeps meaning something (a stale allowlist is how "
        f"an exact-inventory pin goes quiet).")


def test_venue_fee_source_is_a_constant_not_a_field():
    """core/venue_fees fetches the venue's fee schedule. Its endpoint must be
    a module constant, never read from the data being validated - otherwise a
    poisoned schedule could name its own confirming source, which is the exact
    shape this file exists to forbid."""
    src = (ROOT / "core" / "venue_fees.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "fetch_live_schedule")
    urlopen_args = [
        c.args[0] for c in ast.walk(fn)
        if isinstance(c, ast.Call) and c.args
        and ((isinstance(c.func, ast.Attribute) and c.func.attr == "urlopen")
             or (isinstance(c.func, ast.Name) and c.func.id == "urlopen"))
    ]
    assert urlopen_args, "no urlopen call found - has the fetch been renamed?"
    for arg in urlopen_args:
        assert isinstance(arg, ast.Name) and arg.id == "SCHEDULE_SOURCE", (
            "the fee-schedule endpoint is not the module constant "
            "SCHEDULE_SOURCE. If it ever becomes a value read from a payload, "
            "the schedule would be confirming itself.")


def test_location_field_set_is_not_empty():
    """ANTI-RUBBER-STAMP. If the field set were empty every pin above would
    pass on any implementation."""
    assert len(_LOCATION_FIELDS) > 10
    assert "canonical_source" in _LOCATION_FIELDS
