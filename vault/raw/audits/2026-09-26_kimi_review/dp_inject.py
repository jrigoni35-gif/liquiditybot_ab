import sys, time, os, subprocess, json, logging
sys.path.insert(0, r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1")
logging.basicConfig(level=logging.WARNING)
from data.darkpool_feed import DarkPoolFeed
SCR = sys.argv[1]
base = json.load(open(r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1\config.json", encoding="utf-8"))["darkpool"]
good = SCR + "/dp_copy.duckdb"
def feed(path, **kw): return DarkPoolFeed(dict(base, duckdb_path=path, **kw))
def run(name, f, now=1e9):
    t0 = time.perf_counter()
    try:
        s = f.maybe_poll(now); err = None
    except Exception as e:
        s = None; err = f"RAISED {type(e).__name__}: {e}"
    dt = time.perf_counter() - t0
    print(f"{name:28s} {dt*1000:8.1f}ms", err or f"avail={s.available} hhi={s.dp_hhi} sz={s.dp_surge_z} ts={s.ts:.0f}")
    return f
run("CONTROL good copy", feed(good))
run("missing file", feed(SCR + "/nope.duckdb"))
corrupt = SCR + "/corrupt.duckdb"; open(corrupt, "wb").write(os.urandom(1 << 16))
run("corrupt file", feed(corrupt))
import duckdb
empty = SCR + "/empty.duckdb"
if os.path.exists(empty): os.remove(empty)
duckdb.connect(empty).close()
run("no table", feed(empty))
f = feed(good); f._import_db = staticmethod(lambda: (_ for _ in ()).throw(ImportError("x")))
run("duckdb import fails", f)
# locked RW by another process
lk = SCR + "/locked.duckdb"
import shutil; shutil.copy(good, lk)
holder = subprocess.Popen([sys.executable, "-c", "import duckdb,sys,time;c=duckdb.connect(sys.argv[1]);print('held',flush=True);time.sleep(30)", lk], stdout=subprocess.PIPE, text=True)
holder.stdout.readline()
run("locked RW by writer", feed(lk))
holder.kill()
# stale-numerics after degrade: real poll then failure
f = feed(good); run("real poll", f)
f._con.close()     # simulate an invalidated connection
run("after con invalidated", f, now=1e9 + 10*3600)
print("   snapshot numerics after degrade: hhi", f.snapshot().dp_hhi, "avail", f.snapshot().available)
run("next poll (file fine)", f, now=1e9 + 20*3600)
run("and again", f, now=1e9 + 30*3600)
