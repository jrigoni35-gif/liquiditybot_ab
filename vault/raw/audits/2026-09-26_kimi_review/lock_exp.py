import duckdb, subprocess, sys, time, os
db = sys.argv[1] + "/lock_exp.duckdb"
if os.path.exists(db): os.remove(db)
c = duckdb.connect(db); c.execute("create table t(x int)"); c.close()
child = r'''
import duckdb, sys
mode = sys.argv[2]
try:
    c = duckdb.connect(sys.argv[1], read_only=(mode=="ro"))
    if mode=="rw": c.execute("insert into t values (1)")
    print(mode, "OK")
except Exception as e:
    print(mode, "FAIL", type(e).__name__, str(e)[:160])
'''
py = sys.executable
def run(mode): return subprocess.run([py, "-c", child, db, mode], capture_output=True, text=True).stdout.strip()
print("CONTROL (no holder):", run("rw"))
holder = duckdb.connect(db, read_only=True)   # the bot's lifetime connection
print("while bot holds RO:", run("rw"), "|", run("ro"))
holder.close()
print("after release:", run("rw"))
