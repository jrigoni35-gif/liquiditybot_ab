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


def _entry_sites_missing_book(src: str):
    """AST, not text (review 2026-09-26, C6): the old pin counted the
    literal, so a comment satisfied it and a NEW entry site was never
    checked. Walks every *.submit(..., purpose="entry") and resolves
    meta from a dict literal or an in-function dict / meta["book"]=."""
    import ast
    n, missing = 0, []
    for fn in ast.walk(ast.parse(src)):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        dicts: dict = {}
        for nd in ast.walk(fn):
            if not isinstance(nd, ast.Assign):
                continue
            for t in nd.targets:
                if isinstance(t, ast.Name) and isinstance(nd.value, ast.Dict):
                    dicts[t.id] = {k.value for k in nd.value.keys
                                   if isinstance(k, ast.Constant)}
                elif (isinstance(t, ast.Subscript)
                      and isinstance(t.value, ast.Name)
                      and isinstance(t.slice, ast.Constant)
                      and t.slice.value == "book"):
                    dicts.setdefault(t.value.id, set()).add("book")
        for nd in ast.walk(fn):
            if not (isinstance(nd, ast.Call)
                    and isinstance(nd.func, ast.Attribute)
                    and nd.func.attr == "submit"):
                continue
            kw = {k.arg: k.value for k in nd.keywords}
            pur = kw.get("purpose")
            if not (isinstance(pur, ast.Constant) and pur.value == "entry"):
                continue
            n += 1
            m = kw.get("meta")
            keys = ({k.value for k in m.keys if isinstance(k, ast.Constant)}
                    if isinstance(m, ast.Dict)
                    else dicts.get(m.id, set()) if isinstance(m, ast.Name)
                    else set())
            if "book" not in keys:
                missing.append((fn.name, nd.lineno))
    return n, missing


def test_each_5m_entry_meta_dict_stamps_book():
    n, missing = _entry_sites_missing_book(_MAIN_SRC)
    assert n >= 3, f"entry submit sites vanished? n={n}"
    assert missing == [], f"entry submit() without a book stamp: {missing}"


def test_book_pin_is_not_satisfied_by_a_comment():
    first = _MAIN_SRC.index('"book": "5m"')
    mutant = (_MAIN_SRC[:first] + '"bk": "5m"'
              + _MAIN_SRC[first + len('"book": "5m"'):]
              + '\n# "book": "5m"\n')
    assert _entry_sites_missing_book(mutant)[1], "AST pin went vacuous"


def test_fill_row_semantics_unchanged():
    assert _fill_book({"book": "5m"}) == "5m"
    assert _fill_book({"book": "long"}) == "long"
    assert _fill_book({}) == ""          # writer-knew-but-absent, preserved
