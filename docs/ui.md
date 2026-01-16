# Victus UI

## Layout contract
- Fixed navbar with Victus Local logo, tabs, and status pill
- Row 1 panels: Conversation (left), Three.js sphere (center), Live Logs (right)
- Row 2 panels: Dynamic Module (left, content swaps per tab), Recent Activity (right)

## Dynamic module behavior
- Home: chat history + recent interactions summary
- Memory/Finance/Settings: placeholders only (future-ready)

## Three.js sphere
- React-owned container with Three.js canvas inside
- Web Audio amplitude drives scale and glow
- Context-aware hints activate only when `visual_hint` metadata is provided for long responses

## Data feeds
- `POST /api/turn` (SSE) for streaming tokens and turn events
- `GET /api/logs/stream` for global event logs
- Finance routes for summaries and exports (placeholders only)
