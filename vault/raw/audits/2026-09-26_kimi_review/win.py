import json, re, datetime as dt, sys
lo=dt.datetime(2026,9,23,int(sys.argv[1]),int(sys.argv[2]),0,tzinfo=dt.timezone.utc).timestamp(); hi=lo+float(sys.argv[3])
rx=re.compile(rb'"ts": ([0-9.]+)\}\s*$')
P=r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\audit.jsonl"
print("read_utc", dt.datetime.now(dt.timezone.utc).isoformat())
with open(P,'rb') as f:
    for line in f:
        m=rx.search(line)
        if not m: continue
        ts=float(m.group(1))
        if lo<=ts<=hi:
            r=json.loads(line)
            print(dt.datetime.fromtimestamp(ts,dt.timezone.utc).strftime('%H:%M:%S.%f')[:-3], r['seq'], r['src'], r['code'], r['msg'][:110], len(line))
