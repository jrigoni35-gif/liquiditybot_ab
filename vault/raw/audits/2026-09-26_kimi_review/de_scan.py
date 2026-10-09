import json, time, datetime as dt, collections
P=r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\audit.jsonl"
print("read_start_utc", dt.datetime.utcnow().isoformat())
n=0; de=[]
with open(P,"rb") as f:
    for line in f:
        n+=1
        if b'"DE-010"' in line:
            try: r=json.loads(line)
            except Exception as e: de.append((None,len(line),'BAD',None)); continue
            if r.get("code")!="DE-010": continue
            ev=r["data"].get("events",[])
            ab=collections.Counter(e.get("absorb") for e in ev)
            de.append((r["ts"],len(line),len(ev),dict(ab)))
print("lines_total",n,"de010_records",len(de))
for ts,ln,ne,ab in de[:3]+[("...",)*4]+de[-5:]:
    if ts=="...": print("..."); continue
    print(dt.datetime.utcfromtimestamp(ts).isoformat() if ts else None, "bytes",ln,"events",ne, ab)
sizes=[d[1] for d in de]; evs=[d[2] for d in de if isinstance(d[2],int)]
print("max_bytes",max(sizes),"mean_bytes",sum(sizes)//len(sizes),"max_events",max(evs),"sum_events",sum(evs))
# gaps
ts=[d[0] for d in de if d[0]]
gaps=[b-a for a,b in zip(ts,ts[1:])]
print("gap_min",min(gaps),"gap_max",max(gaps))
print("first",dt.datetime.utcfromtimestamp(ts[0]).isoformat(),"last",dt.datetime.utcfromtimestamp(ts[-1]).isoformat())
