import sys, time
sys.path.insert(0, r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1")
SCR = sys.argv[1]
import logging; logging.basicConfig(level=logging.INFO)
from data.darkpool_feed import DarkPoolFeed
import json
cfg = json.load(open(r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1\config.json", encoding="utf-8"))["darkpool"]
cfg = dict(cfg, duckdb_path=SCR + "/dp_copy.duckdb")
f = DarkPoolFeed(cfg)
t0=time.perf_counter(); s=f.maybe_poll(1e9); t1=time.perf_counter()
print("first poll (open+query) %.3fs avail=%s" % (t1-t0, s.available))
for i in range(3):
    t0=time.perf_counter(); f._poll(1e9+i); print("warm _poll %.3fs" % (time.perf_counter()-t0))
con = f._con
print(con.execute("select count(*), max(period_end), max(published_date), max(ingested_at), min(data_age_days), max(data_age_days), count(distinct period_start) filter (where is_complete) from ats_venue_weekly").fetchall())
print(con.execute("select symbol, max(period_end), count(distinct period_start) from ats_venue_weekly where is_complete and symbol in ('COIN','MSTR','QQQ') group by 1").fetchall())
print(con.execute("select distinct period_start, is_complete from ats_venue_weekly order by 1").fetchall())
f.close()
