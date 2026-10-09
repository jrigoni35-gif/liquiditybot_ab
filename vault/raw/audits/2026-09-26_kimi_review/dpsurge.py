import sys, json, glob, os, datetime as dt
sys.path.insert(0, r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1")
from data.darkpool_feed import DarkPoolFeed, _LATEST_PER_SYMBOL
import duckdb
con = duckdb.connect(sys.argv[1] + "/dp_copy.duckdb", read_only=True)
for s in ("COIN","MSTR","QQQ"):
    r = con.execute(_LATEST_PER_SYMBOL, [s]).fetchone()
    prior = con.execute("""select cast(period_start as varchar), sum(volume_shares) from ats_venue_weekly where is_complete and symbol=? group by 1 order by 1""", [s]).fetchall()
    print(s, "cur", r[1], "vol", r[6], "prior_avg", r[9], "surge", (r[6]/r[9]) if r[9] else None, "periods", prior)
print("now UTC", dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
for p in glob.glob(r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\*.json"):
    try:
        if os.path.getsize(p) > 50_000_000: continue
        txt = open(p, encoding="utf-8").read()
    except Exception: continue
    if "darkpool_state" in txt:
        d = json.loads(txt)
        def find(o):
            if isinstance(o, dict):
                if "darkpool_state" in o: return o["darkpool_state"]
                for v in o.values():
                    x = find(v)
                    if x is not None: return x
        print(os.path.basename(p), dt.datetime.fromtimestamp(os.path.getmtime(p), dt.timezone.utc).isoformat(timespec="seconds"), find(d))
