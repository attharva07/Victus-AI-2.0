# Victus Architecture

## System diagram
```
User
  → /api/turn (SSE stream)
     → TurnHandler
        → MemorySearch (keyword + recency)
        → VictusApp
           → Rule Router
           → Intent Planner (LLM)
           → Policy Engine
           → Execution Engine
        → MemoryGate + MemoryStore (JSONL)
```

## Event stream
Each turn emits structured events over SSE:
- `status` (thinking, executing, done, denied, error)
- `token` (streamed model output)
- `tool_start` / `tool_done`
- `memory_used` / `memory_written`

The local UI subscribes to `/api/turn` and `/api/logs/stream` for live updates.

## Local-only data
- Memory JSONL: `victus_data/memory/`
- Finance SQLite: `victus_data/finance/finance.db`
