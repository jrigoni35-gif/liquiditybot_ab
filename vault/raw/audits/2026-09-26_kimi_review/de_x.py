import json, datetime as dt, collections
P=r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\audit.jsonl"
print("read_utc", dt.datetime.now(dt.timezone.utc).isoformat())
seq=[]
with open(P,'rb') as f:
    for line in f:
        if b'"code": "DE-010"' in line or b'"code": "EN-000"' in line or b'"code": "CG-000"' in line:
            seq.append(json.loads(line))
print({c:sum(1 for r in seq if r['code']==c) for c in ('DE-010','EN-000','CG-000')})
print("EN-000 data keys sample:", list(seq[[r['code'] for r in seq].index('EN-000')]['data'].keys())[:12])
# walk
last_en=None; ok=bad=0; mism=[]; nomid=0; tot=0; strlvl=0
ab_tot=collections.Counter()
for r in seq:
    if r['code']=='CG-000': last_en=None; continue
    if r['code']=='EN-000':
        cur=r['data']; 
        prev=last_en; last_en=cur; pend=(prev,cur); continue
    if r['code']=='DE-010':
        ev=r['data']['events']; tot+=len(ev)
        nomid+=sum(1 for e in ev if not e.get('mid_available'))
        ab_tot.update(e.get('absorb') for e in ev)
        if pend and pend[0] is not None:
            a0=pend[0].get('counts',pend[0]).get('arrivals',None) if isinstance(pend[0],dict) else None
            a1=pend[1].get('counts',pend[1]).get('arrivals',None)
            if a0 is not None and a1 is not None:
                if a1-a0==len(ev): ok+=1
                else: bad+=1; mism.append((r['ts'],a1-a0,len(ev)))
        pend=None
print("match",ok,"mismatch",bad, mism[:5])
print("events_total",tot,"mid_unavailable",nomid, dict(ab_tot))
