import ast, pathlib, re
SRC = pathlib.Path(r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1\main.py").read_text(encoding="utf-8")

def entry_sites_missing_book(src):
    tree = ast.parse(src); missing = []; n = 0
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
        dict_assigns = {}
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        dict_assigns[t.id] = {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
            if isinstance(node, ast.Assign):
                for t in node.targets:   # meta["book"] = ...
                    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and isinstance(t.slice, ast.Constant) and t.slice.value == "book":
                        dict_assigns.setdefault(t.value.id, set()).add("book")
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "submit"): continue
            kw = {k.arg: k.value for k in node.keywords}
            p = kw.get("purpose")
            if not (isinstance(p, ast.Constant) and p.value == "entry"): continue
            n += 1
            m = kw.get("meta")
            keys = ({k.value for k in m.keys if isinstance(k, ast.Constant)} if isinstance(m, ast.Dict)
                    else dict_assigns.get(m.id, set()) if isinstance(m, ast.Name) else set())
            if "book" not in keys: missing.append((fn.name, node.lineno))
    return n, missing

print("CONTROL current source:", entry_sites_missing_book(SRC))
mut = SRC.replace('meta={"book": "5m",  # desk label for fills.csv attribution (A2)\n', 'meta={', 1)
assert mut != SRC
print("MUTANT (first stamp removed):", entry_sites_missing_book(mut))
# vacuity of the shipped textual pin: remove a real stamp, add a comment carrying the literal
mut2 = mut + '\n# "book": "5m"\n'
print("shipped pin count on mutant+comment:", mut2.count('"book": "5m"'), "(pin requires >= 3 -> passes vacuously)")
