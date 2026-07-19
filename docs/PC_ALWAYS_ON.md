# Always-on on your PC + edit from your phone

The cloud (Claude Code on the web) container **pauses when the session goes
idle** — that is what caused the multi-hour gaps. There is no setting to keep it
awake. The fix is to run the **bot** on your always-on Windows PC and use Claude
only to **edit** it. Two independent pieces:

- **Part A — the bot runs 24/7 on your PC**, headless and self-healing, started
  automatically at logon. (Files in `scripts/`.)
- **Part B — you steer/edit it from your phone** with Claude Code **Remote
  Control** — Claude runs on your PC, you drive it from the mobile app.

They are decoupled on purpose: the bot never depends on Claude being connected.

---

## Part A — Keep the bot running 24/7 (headless autostart)

### What it installs
A hidden **supervisor** (`scripts/pc_supervisor.py`) that, every 30 s, checks
the runner and the two Grafana pushers are alive and relaunches any that died —
with **no console windows** (the reason the old keep-alive annoyed you). Windows
Task Scheduler starts the supervisor at logon and restarts it if it ever exits.
Liveness is heartbeat-based (`status.json` / pusher log freshness), so there is
no extra dependency and a relaunch is safe even if a process is merely hung (the
runner's single-instance lock refuses a duplicate).

### One-time setup
1. **Install deps** (if you haven't): double-click `install.bat`.
2. **Grafana token for the dashboard** (optional — skip if you don't want the
   phone dashboard from the PC). Set it once as a *user* environment variable so
   it survives reboots and never enters git:
   ```
   setx GC_OTLP_TOKEN     "glc_...your OTLP token..."
   setx GC_OTLP_URL       "https://otlp-gateway-prod-us-east-3.grafana.net/otlp/v1/metrics"
   setx GC_INSTANCE_ID    "1722437"
   ```
   (Open a **new** terminal after `setx` so the values are visible.) The
   supervisor writes the token to `%USERPROFILE%\.liquiditybot\gc-token` on
   start, matching the cloud hook.
3. **moomoo** context data: just have **moomoo OpenD** running on the PC as
   usual — it's local there, so no tailscale tunnel/forwarder is needed (that
   whole fragile bridge only existed because the bot was in the cloud).
4. **Install the autostart task**: double-click `scripts\install_autostart.bat`
   (it self-elevates the PowerShell execution policy just for that run; no
   global change).

### Use it
```
schtasks /Run  /TN LiquidityBot     REM start now, without re-logging-in
type outputs\pc_supervisor.log      REM watch the supervisor (relaunch decisions)
type outputs\runner.log             REM watch the bot (supervisor writes THIS file)
scripts\uninstall_autostart.bat     REM remove the autostart task
```
From now on the bot starts hidden at every logon and stays up. The supervisor
stays headless by design; you watch the bot on the Grafana Cloud phone
dashboard (the legacy Streamlit dashboard has been retired).

### Caveats
- Task runs **only while you're logged in** (moomoo OpenD needs your desktop
  session). If you want it to run at the lock screen too, that's a
  "run whether logged on or not" task — but OpenD won't have a GUI session then.
- The PC must be **on and awake**. Set Windows power to never sleep, or the bot
  sleeps with it.

---

## Part B — Edit it from your phone (Claude Code Remote Control)

**Important:** running Claude Code *on the web* against your own PC (a
self-hosted cloud environment) **does not exist**. The supported way to have
Claude run on your PC and drive it from your phone is **Remote Control** — a
research-preview feature. Verify the exact command against the current docs:
<https://code.claude.com/docs/en/remote-control>

### Steps (verify command names against the docs above)
1. **Install the Claude Code CLI** on the PC and sign in:
   <https://code.claude.com/docs/en/quickstart> then `claude` → `/login`
   (needs a Pro/Max/Team/Enterprise plan).
2. In the **bot's repo folder** on the PC, start a Remote Control session
   (per the docs — e.g. `claude remote-control --name "trading bot"`). It prints
   a session URL and a QR code.
3. **From the phone**: open the Claude app → **Code**, scan the QR (or pick the
   session by name); or open the session URL in a browser. You're now steering
   Claude *on your PC* — your local repo, your files.
4. Edit/chat normally from the phone. Changes land on the PC's working tree; the
   bot (Part A) keeps running independently. After a code change, redeploy the
   runner (`stop.bat` then `start.bat`, or let the supervisor pick it up after
   `stop.bat`).

### Note
Remote Control times out after an extended offline stretch (~10 min); just start
it again on the PC. It is **not** required for the bot to run — Part A stands on
its own. Remote Control is only for when you want to *change* things from your
phone.

---

## How the two fit together

```
Your PC (always on)                          Your phone
┌───────────────────────────────┐
│ Task Scheduler (at logon)      │
│   └─ pc_supervisor.py (hidden) │           Claude app ──┐
│        ├─ runner.py  (the bot) │                        │ Remote Control
│        ├─ gc_pusher.py ────────┼── Grafana ◀── dashboard│ (edit on PC)
│        └─ gc_log_pusher.py     │                        │
│   moomoo OpenD (local)         │◀───────────────────────┘
└───────────────────────────────┘
```
Bot = your PC, never pauses. Grafana = your phone dashboard. Remote Control =
editing from your phone when you want it. The cloud session becomes optional.
