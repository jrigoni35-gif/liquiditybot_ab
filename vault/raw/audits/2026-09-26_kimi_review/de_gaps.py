import json, re, datetime as dt
P=r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\audit.jsonl"
rx=re.compile(rb'"ts": ([0-9.]+)\}\s*$')
print("read_utc", dt.datetime.now(dt.timezone.utc).isoformat())
recs=[]; cg=[]
with open(P,'rb') as f:
    for line in f:
        if b'"code": "DE-010"' in line or b'"code": "CG-000"' in line:
            r=json.loads(line); ts=r['ts']
            (recs if r['code']=='DE-010' else cg).append((ts,r['seq'],len(r['data'].get('events',[])) if r['code']=='DE-010' else 0, r['prev'][:8]))
F=lambda t: dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime('%m-%dT%H:%M:%S')
boots=[c[0] for c in cg]
for a,b in zip(recs,recs[1:]):
    g=b[0]-a[0]
    if g<3590 or g>3700:
        nb=[F(x) for x in boots if a[0]<x<=b[0]]
        print(F(a[0]),'->',F(b[0]),'gap',round(g),'events_b',b[2],'boots_between',nb)
# ev ts range per record: min/max event ts within record vs record ts
