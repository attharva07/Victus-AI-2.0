# Phase 3 Camera Recognition MVP

## Summary
Phase 3 adds **opt-in, auth-protected** camera endpoints for Victus Local. The camera is **off by default** and responds with **structured, deterministic** stub payloads (no hardware required).

## What this phase includes
- Auth-protected camera endpoints:
  - `GET /camera/status`
  - `POST /camera/capture`
  - `POST /camera/recognize`
- A backend abstraction with a **stub backend** (default, deterministic, no hardware required)
- Explicit safety gating: when disabled, endpoints return `{ ok: false, enabled: false, ... }` without touching hardware
- Audit entries per request with action, enabled flag, backend, and request ID

## Safety + permissions rationale
- The camera is **off by default** (`VICTUS_CAMERA_ENABLED=false`).
- Responses are **stubbed** (no device access, no disk writes, no cloud calls).
- Enabling the camera is an explicit, local-only opt-in; the API is auth-protected.

## What this phase does **not** include
- No UI work or UI changes
- No real webcam capture or streaming
- No face recognition models or identity matching
- No changes to Phase 1/2 memory/finance/file behavior

## How to enable locally
Camera endpoints are disabled by default. Enable them explicitly via environment variables:

```bash
export VICTUS_CAMERA_ENABLED=true
export VICTUS_CAMERA_BACKEND=stub
```

## API usage examples

### cURL
```bash
# login to get a token
TOKEN=$(curl -s http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | jq -r .access_token)

# status
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/camera/status

# capture (optional reason/format)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"manual check","format":"jpg"}' \
  http://localhost:8000/camera/capture

# recognize (optional capture_id or image_b64)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"capture_id":"stub-capture"}' \
  http://localhost:8000/camera/recognize
```

### PowerShell
```powershell
# login to get a token
$login = Invoke-RestMethod -Uri http://localhost:8000/login -Method Post -ContentType "application/json" `
  -Body '{"username":"admin","password":"admin"}'
$token = $login.access_token

# status
Invoke-RestMethod -Uri http://localhost:8000/camera/status -Headers @{Authorization = "Bearer $token"}

# capture
Invoke-RestMethod -Uri http://localhost:8000/camera/capture -Method Post -Headers @{Authorization = "Bearer $token"} `
  -ContentType "application/json" -Body '{"reason":"manual check","format":"jpg"}'

# recognize
Invoke-RestMethod -Uri http://localhost:8000/camera/recognize -Method Post -Headers @{Authorization = "Bearer $token"} `
  -ContentType "application/json" -Body '{"capture_id":"stub-capture"}'
```
