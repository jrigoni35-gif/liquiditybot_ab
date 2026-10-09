import sys, json, time, tempfile, os, statistics
sys.path.insert(0, r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1")
from core.audit import AuditTrail
from core.codes import Code
P=r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\audit.jsonl"
last=None
with open(P,'rb') as f:
    for line in f:
        if b'"code": "DE-010"' in line: last=line
ev=json.loads(last)['data']['events']; print("events",len(ev))
d=tempfile.mkdtemp()
for fs in (True, False):
    a=AuditTrail(os.path.join(d,f"a{fs}.jsonl"), fsync=fs)
    a.log("x", Code.DE_DECISION_EVENTS, "warm", {})
    ts=[]
    for i in range(20):
        t=time.perf_counter(); a.log("entry_sweep", Code.DE_DECISION_EVENTS, "b", {"events": list(ev)}); ts.append(time.perf_counter()-t)
    print("fsync",fs,"median_ms",round(statistics.median(ts)*1e3,1),"max_ms",round(max(ts)*1e3,1))
# small record baseline
a=AuditTrail(os.path.join(d,"s.jsonl"), fsync=True); ts=[]
for i in range(20):
    t=time.perf_counter(); a.log("x", Code.DE_DECISION_EVENTS, "s", {"k":1}); ts.append(time.perf_counter()-t)
print("small fsync median_ms",round(statistics.median(ts)*1e3,2))
