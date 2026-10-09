import re, datetime as dt, sys
P=r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\runner.log"
print("read_utc", dt.datetime.now(dt.timezone.utc).isoformat())
rx=re.compile(rb'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) ')
prev=None; prevline=b''; gaps=[]; n=0; boot=dt.datetime(2026,9,23,18,0,0)
with open(P,'rb') as f:
    for line in f:
        m=rx.match(line)
        if not m: continue
        t=dt.datetime.strptime(m.group(1).decode(),'%Y-%m-%d %H:%M:%S')+dt.timedelta(milliseconds=int(m.group(2)))
        if t<boot: prev=t; prevline=line; continue
        n+=1
        if prev and (t-prev).total_seconds()>30:
            gaps.append(((t-prev).total_seconds(),prev,t,prevline[:220],line[:220]))
        prev=t; prevline=line
print("lines_since_boot",n,"gaps>30s",len(gaps))
for g in sorted(gaps,reverse=True)[:12]:
    print(round(g[0],1), g[1], '->', g[2]); print('   A:',g[3]); print('   B:',g[4])
