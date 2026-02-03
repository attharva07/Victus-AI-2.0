# Victus Local Operations (Phase 1)

## Run locally
```
python -m apps.local.launcher
```

Defaults:
- Host: `127.0.0.1`
- Port: `8000`

Override with:
- `VICTUS_LOCAL_HOST`
- `VICTUS_LOCAL_PORT`

## Storage locations
Victus Local persists data under a stable, OS-specific base directory:
- Windows: `%LOCALAPPDATA%/VictusAI`
- macOS: `~/Library/Application Support/VictusAI`
- Linux: `$XDG_DATA_HOME/victus_ai` (or `~/.local/share/victus_ai`)

Subdirectories:
- `data/` (auth metadata)
- `logs/`
- `vault/`

## Authentication
Phase 1 uses a single local admin account. If no account exists, it is created on first run using:
- `VICTUS_LOCAL_ADMIN_USERNAME` (default: `admin`)
- `VICTUS_LOCAL_ADMIN_PASSWORD` (default: `admin`)

Tokens are signed locally and intended only for the local runtime.
