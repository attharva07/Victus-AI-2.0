# Phase 3 Camera Recognition MVP

## Summary
Phase 3 adds **opt-in, auth-protected** camera endpoints for Victus Local. The camera is **off by default** and only captures a single frame per request. There is no background recording and no cloud calls.

## What this phase includes
- Auth-protected camera endpoints:
  - `GET /camera/status`
  - `POST /camera/capture`
  - `POST /camera/recognize`
- A backend abstraction with:
  - **Stub backend** (default, deterministic, no hardware required)
  - **OpenCV backend** (optional, only when explicitly enabled)
- Face detection only (no identity recognition)
- Strict size limits and no disk writes by default

## What this phase does **not** include
- No UI work or UI changes
- No always-on or background camera recording
- No identity recognition or cloud processing
- No changes to Phase 1/2 memory/finance/file behavior

## How to enable locally
Camera endpoints are disabled by default. Enable them explicitly via environment variables:

```bash
export VICTUS_CAMERA_ENABLED=true
export VICTUS_CAMERA_BACKEND=stub   # or "opencv" if OpenCV is installed
export VICTUS_CAMERA_DEVICE_INDEX=0
export VICTUS_CAMERA_MAX_IMAGE_BYTES=2000000
export VICTUS_CAMERA_MAX_DIM=1280
```

To use the OpenCV backend, install it locally (optional dependency):

```bash
pip install opencv-python
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

# capture
curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/camera/capture

# recognize (face detection)
curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/camera/recognize
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
Invoke-RestMethod -Uri http://localhost:8000/camera/capture -Method Post -Headers @{Authorization = "Bearer $token"}

# recognize
Invoke-RestMethod -Uri http://localhost:8000/camera/recognize -Method Post -Headers @{Authorization = "Bearer $token"}
```
