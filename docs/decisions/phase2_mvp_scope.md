# Phase 2 MVP Scope (Victus Local)

## Overview
Phase 2 adds:
- Memories MVP (SQLite-backed add/search/list/delete).
- Finance MVP (SQLite-backed add/list/summary with deterministic parsing).
- File sandbox MVP (single-folder read/write/list with safe extensions).

All data is stored in the OS-stable data directory resolved by `core/config.py`.

## Explicitly Not Included
- Camera recognition (Phase 3) is **not** implemented.
- Utilities such as alarms, timers, clocks, sticky notes, or calendars are **not** implemented.

## How to Run Locally
1. Set any required environment variables (optional):
   - `VICTUS_DATA_DIR` to override the data directory.
   - `VICTUS_FILE_SANDBOX_DIR` to override the sandbox folder.
2. Start the local app (example):
   - `uvicorn apps.local.main:app --host 127.0.0.1 --port 8000`

## How to Test Locally
- Run the full test suite:
  - `pytest`

## Locked Scope Confirmation
Phase 2 work is limited to memories, finance, and single-folder file sandbox features only.
