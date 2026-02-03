# Phase 1 Assumptions & Boundaries

## Locked roadmap (non-negotiable)
- Phase 1 only. Do **not** implement Phase 2 features (memory, finance, file ops, camera, utilities) beyond interfaces/stubs.
- No refactors unrelated to Phase 1.
- CI must remain green (Python 3.11 + 3.12).
- Local must bind to `127.0.0.1` by default.
- Data must persist in a stable OS-specific directory (do not overwrite user data).

## Phase 1 scope
- Local FastAPI app + launcher.
- Auth + token/session scaffolding for a single local admin.
- Logging + audit hooks.
- Vault sandbox (safe path join, allowlist, traversal + symlink escape protection).
- Updater scaffolding (stubs only).
- 3-layer orchestrator skeleton (deterministic-first, LLM fallback proposer only).
- Docs for architecture, operations, decisions.

## Explicitly out of scope (Phase 2)
- Memory system.
- Finance system.
- File operations or OS control.
- Camera/media utilities.
- External updater behavior or network update checks.
