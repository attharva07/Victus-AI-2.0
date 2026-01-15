# Victus Local Web UI

Local FastAPI server that hosts the single-chatbox web UI and streams turn events over SSE.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r victus_local/requirements.txt
```

## Run

```bash
uvicorn victus_local.server:app --host 127.0.0.1 --port 8000
```

Open: <http://127.0.0.1:8000>

> **Security note:** keep the bind address at `127.0.0.1` so the server is local-only.

## Pipeline wiring

The local server builds a `VictusApp` instance with:
- Rule-based routing for local tasks and system status checks.
- An LLM intent planner (only when the router cannot decide).
- Policy enforcement and allowlisted tool execution.

## API

- `POST /api/turn` `{ "message": "..." }` → `text/event-stream`
- `WS /ws/logs` for live log events (fallback: `GET /api/logs/stream` for SSE)

Turn events include `status`, `token`, `tool_start`, `tool_done`, `clarify`, and `error` fields for UI rendering.
