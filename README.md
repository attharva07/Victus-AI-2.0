# Victus AI 2.0

## What Victus is
Victus is a **local, policy-gated assistant** that routes every request through a deterministic router, an intent planner, and a policy gate before any tool executes. It is designed for local-first workflows: a single input box, streaming responses, and auditable events across tools, memory, and finance.

## Architecture overview
```
User Input
  → Rule Router (fast, deterministic)
  → LLM Intent Planner (only if ambiguous)
  → Policy Engine (allowlist + privacy checks)
  → Executor (validated tools + signatures)
  → Event Stream (tokens, tool events, memory, finance)
```

Key guarantees:
- **Allowlisted tools only**: tools and actions are explicitly mapped to domains.
- **Policy signatures required**: every plan is signed before execution.
- **Local-first**: memory + finance logs are stored under `victus_data/`.

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
3. Configure an LLM provider (optional):
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
4. Run the local UI (React + Three.js):
   ```bash
   python -m uvicorn victus_local.server:app --host 127.0.0.1 --port 8000
   ```
5. Open <http://127.0.0.1:8000> to view the React dashboard with the audio-reactive Three.js sphere and dynamic module container placeholders.

## Streaming behavior
`POST /api/turn` returns `text/event-stream` and emits structured events:
- `status`: `thinking | executing | done | denied | error`
- `token`: partial LLM text
- `tool_start` / `tool_done`
- `memory_used` / `memory_written`
- `clarify` / `error`

The UI renders tokens as they arrive and logs every pipeline event in the Live Logs panel.

## UI architecture highlights
- React dashboard UI (no fallback HTML pages)
- Three.js sphere rendered in the center panel with Web Audio reactivity
- Dynamic module container swaps placeholder content for Home/Memory/Finance/Settings without routing

## Memory + finance overview
**Memory v1** is local, append-only JSONL storage with a gate that blocks sensitive data and only writes explicit or safe, important items:
- Session memory (in-memory)
- Project memory: `victus_data/memory/project.jsonl`
- User memory: `victus_data/memory/user.jsonl`

**Finance v1** provides a local SQLite logbook:
- `victus_data/finance/finance.db`
- Transactions, budgets, and paychecks
- Exportable Markdown logbook reports

## Roadmap
- ✅ Local web UI + streaming pipeline
- ✅ Memory v1 (local JSONL with gating)
- ✅ Finance Logbook v1 (SQLite)
- ⏳ Permission prompts + confirmations
- ⏳ Long-running task timelines

## Documentation
- [docs/architecture.md](docs/architecture.md)
- [docs/memory.md](docs/memory.md)
- [docs/finance.md](docs/finance.md)
- [docs/ui.md](docs/ui.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md)
- [docs/POLICY.md](docs/POLICY.md)
