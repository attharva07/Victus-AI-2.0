# Victus Architecture (Phase 1 Local)

## Overview
Phase 1 focuses on a local-only foundation that is deterministic-first, with an LLM as a fallback proposer only. The system is intentionally scaffolded to avoid executing real actions or Phase 2 capabilities.

## Local service layout
```
apps/local/launcher.py  -> prepares environment, starts API
apps/local/main.py      -> FastAPI app
core/                   -> config, logging, security, orchestrator, vault
adapters/               -> LLM + runtime scaffolding
```

## Request flow
```
User
  → /health (no auth)
  → /login (admin auth)
  → /me (auth)
  → /orchestrate (auth)
        → Deterministic router
        → LLM fallback proposer (no execution)
        → Policy validation
```

## Data boundaries
- Data persists under an OS-specific base directory (data/logs/vault).
- Vault access is mediated by safe path joins, allowlists, and traversal protections.

## Explicitly out of scope
Phase 2 capabilities (memory, finance, file operations, camera, utilities) are not implemented in Phase 1.
