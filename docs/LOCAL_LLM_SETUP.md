# Local-LLM companion — operator setup (Windows / PowerShell)

Design: `docs/superpowers/specs/2026-07-26-local-llm-companion-design.md`
§1–§2. This wires a Claude Code MCP server on your PC to a local Ollama
model, so Claude Code sessions on your desk can ask it free-form
questions or have it summarize a bot report file — **outside** the
trading decision loop (§0.3: touches zero invariants, imports zero
engine code, invisible to cloud sessions). Everything below runs in
PowerShell on the operator's PC, not in the bot's frozen `.venv`.

---

## 1. Install Ollama + pull the model

```powershell
winget install Ollama.Ollama
# or, if winget is unavailable: download/run the installer from
# https://ollama.com/download/windows

ollama pull qwen2.5:7b-instruct
```

This is the default model the bridge talks to (`LOCAL_LLM_MODEL` below).
Q4_K_M quantization, ~4.7 GB — fits the 3070 Ti FE's 8 GB VRAM with
headroom.

---

## 2. Coexistence env vars (so Ollama shares the box with the always-on bot)

Set these **user-level** (`setx`, not `$env:`, so they survive reboots)
then restart the Ollama service so it picks them up:

```powershell
setx OLLAMA_KEEP_ALIVE 5m
setx OLLAMA_MAX_LOADED_MODELS 1
setx OLLAMA_NUM_PARALLEL 1

# Restart Ollama so the new env vars take effect:
Restart-Service Ollama
# or, if it's not registered as a service: quit Ollama from the tray
# icon and relaunch it.
```

`OLLAMA_KEEP_ALIVE=5m` unloads the model after 5 minutes idle so VRAM
comes back for gaming; `OLLAMA_MAX_LOADED_MODELS=1` and
`OLLAMA_NUM_PARALLEL=1` keep it to one model, one request at a time —
this is a companion tool, not a serving cluster. `setx` only affects
*new* processes/terminals — open a fresh terminal to confirm with
`$env:OLLAMA_KEEP_ALIVE`.

---

## 3. Bridge venv (separate from the bot's frozen `.venv`)

The bridge's `fastmcp` dependency must **never** enter the bot's frozen
venv (design law, §2). Give it its own:

```powershell
py -m venv %USERPROFILE%\.venvs\llm-bridge
%USERPROFILE%\.venvs\llm-bridge\Scripts\pip install fastmcp
```

---

## 4. Register the MCP server (user-scope, never project-scope)

User-scope only — the project's `.mcp.json` must never reference this,
because cloud Claude Code sessions have no local Ollama endpoint to
reach (§2). Absolute paths, one line:

```powershell
claude mcp add --scope user local-llm -- %USERPROFILE%\.venvs\llm-bridge\Scripts\python.exe C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\scripts\local_llm_mcp.py
```

Point it at the bot's `outputs/` directory so `summarize_bot_report`
can find report files — either as part of the registration via
`--env`:

```powershell
claude mcp add --scope user --env LOCAL_LLM_OUTPUTS_DIR=C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs local-llm -- %USERPROFILE%\.venvs\llm-bridge\Scripts\python.exe C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\scripts\local_llm_mcp.py
```

or as a standalone user env var:

```powershell
setx LOCAL_LLM_OUTPUTS_DIR "C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs"
```

`LOCAL_LLM_BASE_URL` (default `http://127.0.0.1:11434/v1`) and
`LOCAL_LLM_MODEL` (default `qwen2.5:7b-instruct`) follow the same
pattern if you ever swap the serving stack — every consumer speaks
"OpenAI-compatible base URL" (§1), so pointing at vLLM/LM Studio/
llama.cpp later needs no code change, just a different
`LOCAL_LLM_BASE_URL`.

---

## 5. Verify

1. Restart Claude Code (fully quit, relaunch) so it picks up the new
   user-scope server.
2. Run `/mcp` — `local-llm` should show as **connected**.
3. Ask Claude in a session: *"call ask_local_model with prompt 'say
   ok'"* (or just "use the local model to say ok"). A short reply
   routed through your Ollama instance confirms the whole chain —
   Ollama running, bridge venv correct, registration correct.

---

## 6. Troubleshooting

- **`/mcp` shows local-llm failed / not connecting**: run the exact
  registered command directly in a shell — this is the official
  diagnostic, since Claude Code just launches that same command:
  ```powershell
  %USERPROFILE%\.venvs\llm-bridge\Scripts\python.exe C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\scripts\local_llm_mcp.py
  ```
  Whatever it prints (import error, traceback, etc.) is the real
  failure — fix that first, then retry `/mcp`.
- **Connects, then times out on first tool call**: Claude Code allows
  ~30 s for an MCP server to start responding. If Ollama just cold-
  loaded the model (post-`OLLAMA_KEEP_ALIVE` unload) the first
  request can be slow — retry once the model is warm.
- **Tool call fails with `local model endpoint failed (...) - is the
  server running at ...?`**: this is `call_endpoint`'s own error
  wrapper — it means the bridge reached out to `LOCAL_LLM_BASE_URL`
  and got nothing back (connection refused, DNS failure, timeout).
  Check Ollama is actually running (`ollama list`) and that
  `LOCAL_LLM_BASE_URL` matches where it's listening
  (`http://127.0.0.1:11434/v1` by default).
