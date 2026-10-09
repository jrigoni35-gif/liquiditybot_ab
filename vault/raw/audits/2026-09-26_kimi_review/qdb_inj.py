import sys, json, pathlib, tempfile
sys.path.insert(0, r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1")
import duckdb
from scripts import quant_db as q
d=pathlib.Path(tempfile.mkdtemp())
db=d/"x.duckdb"; c=duckdb.connect(str(db)); c.execute("create table t(a int)"); c.close()
junk=d/"junk.duckdb"; junk.write_text("not a db")
cases={"control_ok":{"good":{"path":str(db),"tables":["t"]}},
       "alias_main":{"main":{"path":str(db),"tables":["t"]}},
       "alias_system":{"system":{"path":str(db),"tables":["t"]}},
       "missing_table":{"good":{"path":str(db),"tables":["nope"]}},
       "junk_file":{"j":{"path":str(junk),"tables":["t"]}},
       "same_file_twice":{"a1":{"path":str(db),"tables":["t"]},"a2":{"path":str(db),"tables":["t"]}}}
for name,reg in cases.items():
    rp=d/f"{name}.json"; rp.write_text(json.dumps(reg))
    con=duckdb.connect()
    try:
        out=q._attach_external(con, rp); print(name,"OK",out)
    except q.QuantDbRefusal as e: print(name,"REFUSAL",str(e)[:120])
    except Exception as e: print(name,"UNCAUGHT",type(e).__name__,str(e)[:140])
