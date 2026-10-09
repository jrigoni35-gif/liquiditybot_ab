import re, datetime as dt, statistics
P=r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\runner.log"
print("read_utc", dt.datetime.now(dt.timezone.utc).isoformat())
rx=re.compile(rb'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) ')
boot=dt.datetime(2026,9,23,18,4,48)
T=lambda m: dt.datetime.strptime(m.group(1).decode(),'%Y-%m-%d %H:%M:%S')+dt.timedelta(milliseconds=int(m.group(2)))
start=None; durs=[]; nonret=[]
with open(P,'rb') as f:
    for line in f:
        m=rx.match(line)
        if not m: continue
        t=T(m)
        if t<boot: continue
        if b'liquiditybot.main: auto-retrain:' in line: start=t; continue
        if start and b'liquiditybot.main: health:' in line:
            durs.append(((t-start).total_seconds(), start)); start=None
print("n",len(durs))
d=[x[0] for x in durs]
print("retrain->health sec: min",min(d),"median",statistics.median(d),"max",max(d))
print("max at", max(durs)[1])
