# Phase 4 Temporary Popup Demo (Legacy)

A lightweight developer harness that launches the Victus popup UI directly. The web UI is now the primary interface, but the popup remains available for quick checks.

## Install dependencies
```bash
pip install PySide6
```

## Run
```bash
python run_ui_temp.py
```

## Controls
- **Enter**: submit text
- **Shift + Enter**: insert newline
- **Window close**: exit the popup

## Notes
- UI opens immediately; there is no tray icon or global hotkey.
- Requests flow through `VictusApp.run_request_streaming` (no direct plugin calls).
- Text in/out only (no voice, TTS, screenshots, or vision).
- The popup is intended for local desktop use and may not render in headless containers.
