# Local-LLM Companion — design (2026-07-26)

Status: operator-approved direction (Approach A chosen 2026-07-26; GPU
confirmed RTX 3070 Ti FE, 8GB). Research corpus: session workspace
local-llm/ (research_bridge.raw, research_serving.raw) + the bot-side
seam map. Governing law: the learnaccel spec's §6 rejected-forever LLM
clause (unqualified, in-loop) and §5 Phase-4 news-sentiment entry
conditions.

## §0 Three-tier boundary (binding)

1. **In the trading decision loop: never.** "LLM decision layers /
   multi-persona debate / online LLM APIs in the loop" — rejected
   forever, no phase unlocks it.
2. **Bot-adjacent (news-sentiment feature): paper now, code at the
   gate.** Entry conditions verbatim: "after T3 pruning + OF-1 pass +
   flow resumed + sent_fear certified alive." §3 below is the design
   addendum; zero code before the gate.
3. **Outside the loop: build now.** An MCP tool server for Claude Code
   sessions on the operator's PC + offline summarization of
   already-rendered report artifacts. Touches zero invariants, imports
   zero engine code, and is invisible to cloud sessions.

## §1 Serving stack (operator's PC)

- **Ollama, native Windows** — one installer, CUDA auto-detect (3070 Ti
  = compute 8.6, fully supported). Model: `qwen2.5:7b-instruct`
  (Q4_K_M, ~4.7GB — fits 8GB VRAM with context headroom; ~55-70 tok/s
  expected; a 200-token reply in ~3-4s).
- **Swappable-endpoint principle (design law for this project):** every
  consumer speaks only "OpenAI-compatible base URL" (default
  `http://127.0.0.1:11434/v1`). Ollama today; vLLM-in-WSL, LM Studio,
  or llama.cpp tomorrow — no consumer changes.
- **Coexistence with the always-on bot:** `OLLAMA_KEEP_ALIVE=5m`
  (model auto-unloads, VRAM returns for gaming),
  `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`; Ollama service
  runs at default priority (its idle footprint is a parked process; the
  bot is CPU-light and RAM-light — no affinity partitioning needed
  unless observed contention says otherwise).

## §2 The bridge — `scripts/local_llm_mcp.py` (build now)

One small file, in-repo (versioned, reviewed, ships via normal merges),
run only on the PC:

- **Structure:** pure logic functions importable with ZERO third-party
  deps (whitelist resolution, prompt shaping, HTTP payload build via
  stdlib `urllib.request`) + a `main()` that lazily imports `fastmcp`
  and registers two tools. `fastmcp` lives in its OWN venv on the PC
  (never the bot's frozen venv). scripts/ is outside the
  import-integrity sweep and the pyright shipped scope; tests cover the
  pure functions with the HTTP call mocked, and skip the fastmcp layer
  when the dep is absent.
- **Tool 1:** `ask_local_model(prompt: str, system: str = "",
  max_tokens: int = 400) -> str` — temperature 0, single request, POST
  to `<base_url>/chat/completions`. max_tokens capped at 2000 (MCP
  output limits).
- **Tool 2:** `summarize_bot_report(filename: str) -> str` — whitelist:
  basename must resolve inside `<repo>/outputs/` and end in
  `.md|.csv|.json`; path traversal rejected; file content truncated to
  24,000 characters before prompting; fixed summarization system prompt.
- **Config:** env vars only — `LOCAL_LLM_BASE_URL` (default the Ollama
  URL), `LOCAL_LLM_MODEL` (default `qwen2.5:7b-instruct`). No bot
  config.json keys — this tool is not part of the bot.
- **Registration: user-scope on the PC** (`claude mcp add --scope user
  local-llm -- <abs path to bridge venv python> <abs path to script>`),
  NOT the project `.mcp.json` — cloud sessions must never reference an
  endpoint that only exists on the operator's desk. Tools surface as
  `mcp__local-llm__ask_local_model` etc.
- **Trust boundary note (mirrors the coinpaprika `_doc` convention):**
  local-model output is untrusted text — treated as data, never as
  instructions; nothing the engine reads is ever written by this tool.

## §3 Bot-side seam — Phase-4 addendum (paper only)

When (and only when) the §0.2 gate opens, the news-sentiment scorer is
built to this shape:

- **Model-agnostic scorer interface:** `score_headline(text) -> float
  [-1, 1]` behind the same OpenAI-compatible-endpoint abstraction —
  candidates: FinBERT-class encoder (110M, CPU, strong on tone) vs the
  local 7B instruct (better on impact judgment). The A/B is adjudicated
  inside OF-3's CSCV like every schema experiment — never chosen by
  preference.
- **PIT discipline (context-engine pattern):** each headline scored
  ONCE at ingestion; `{ts, source, text_hash, score, model_tag}`
  appended to an append-only JSONL PIT file; never re-scored, never
  re-fetched. This freezes the audit trail and dissolves the
  LLM-determinism caveat (temp-0 is same-machine reproducible but not
  bit-perfect across builds — irrelevant once scores are frozen at
  ingestion).
- **Feature entry:** the existing 6-step schema procedure (FEATURE_NAMES
  + contracts bounds + compute w/ neutral default + FEATURE_SCHEMA_VERSION
  bump + migrate_history entry + bak/bundle recovery exercised), PBO
  space consciously re-baselined per T3.5's rule.
- **Failure posture:** scorer unavailable → feature emits its neutral;
  known/available booleans with grace windows; errors log-and-continue.
  Sentiment shades, never creates/vetoes/flips (fear_filter law).

## §4 Explicitly out of scope

Gaudi/enterprise accelerators (closed: OAM/server-only, ~$15k/card,
product line winding down); vLLM on this machine (Linux/WSL-only,
single-user mismatch) — the §1 endpoint principle keeps it available
later without design changes; any LLM touch to lessons_digest.py or any
engine-imported path (its no-LLM header law stands — summarization
happens OUTSIDE, reading its rendered output).

## §5 Acceptance

Bridge file + tests green in the normal battery (pure functions only);
operator completes the PC install checklist (Ollama + model pull +
bridge venv + user-scope registration); first successful
`mcp__local-llm__ask_local_model` call in a PC Claude Code session;
`summarize_bot_report` demonstrated on outputs/lessons_digest.md.
Phase-4 addendum (§3) referenced from the learnaccel program ledger.
