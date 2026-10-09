import sys, json, logging
tree = sys.argv[1]; sys.path.insert(0, tree)
logging.disable(logging.CRITICAL)
from data.darkpool_feed import DarkPoolFeed
cfg = json.load(open(tree + "/config.json", encoding="utf-8"))["darkpool"]
st = json.load(open(r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\state.json", encoding="utf-8"))
def find(o):
    if isinstance(o, dict):
        if "darkpool_state" in o: return o["darkpool_state"]
        for v in o.values():
            x = find(v)
            if x is not None: return x
f = DarkPoolFeed(dict(cfg, duckdb_path=sys.argv[2]))
f.from_dict(find(st))
out = []
for k in range(6):
    s = f.maybe_poll(1790449000 + k * 6 * 3600)
    out.append((s.available, s.dp_surge_z, s.dp_vol_z, s.dp_hhi, s.dp_frozen))
print(json.dumps({"vec": out, "state": f.to_dict(), "age": s.data_age_days}))
f.close()
