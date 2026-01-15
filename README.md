# Victus AI 2.0

## What Victus is
Victus is a local-first assistant pipeline that routes every user request through a policy gate before any tool executes. It combines an LLM response path with a guarded task executor so you can type a single message and let Victus decide whether to chat, run a local action, or ask for clarification.

## Architecture overview
```
Input
  → Rule Router (fast, deterministic)
  → LLM Intent Planner (only if ambiguous)
  → Policy Engine (allowlist + privacy checks)
  → Executor (validated tools only)
  → Output (streamed events)
```

Key guarantees:
- Tools are allowlisted and arguments are validated before execution.
- LLMs can propose actions but never execute tools directly.
- Policy approvals and signatures are required before any task runs.

## Local setup (Windows-first)
1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
   _macOS/Linux:_ `source .venv/bin/activate`
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure an LLM provider (optional but recommended):
   - **Ollama (local):**
     ```bash
     set LLM_PROVIDER=ollama
     set OLLAMA_BASE_URL=http://localhost:11434
     set OLLAMA_MODEL=llama3
     ```
   - **OpenAI:**
     ```bash
     set LLM_PROVIDER=openai
     set OPENAI_API_KEY=your_key_here
     ```
4. Run the local UI:
   ```bash
   python -m uvicorn victus_local.server:app --host 127.0.0.1 --port 8000
   ```
5. Open <http://127.0.0.1:8000> and use the single chatbox.

## Streaming behavior
`POST /api/turn` returns `text/event-stream` and emits structured events:
- `status`: `thinking | executing | done | denied | error`
- `token`: partial LLM text
- `tool_start` / `tool_done`
- `clarify` / `error`

If the underlying LLM client does not support native streaming, Victus sends chunked fallback output so the UI still updates incrementally.

## Task gating
Local actions are routed through policy and only the allowlisted tools below can execute:
- `local.open_app` (open a local app by name or path)
- `local.open_youtube` (open a YouTube search or URL)

Every plan still flows through the policy engine, which enforces allowlists and privacy settings before execution.

## Current limitations
- Text-only (no voice input yet)
- Local-only server (no auth or multi-user support)
- LLM intent planner is best-effort JSON; ambiguous prompts may trigger clarification
- No long-running task state or background scheduling

## Roadmap timeline
- ✅ Popup UI phase (completed)
- ✅ Local web UI phase (current)
- ✅ Unified pipeline + streaming (this update)
- ⏳ Voice input + permission prompts (future)
- ⏳ Long-running state and task history (future)

## Documentation links
- [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md)
- [docs/POLICY.md](docs/POLICY.md)
- [docs/LLM_PROVIDERS.md](docs/LLM_PROVIDERS.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
