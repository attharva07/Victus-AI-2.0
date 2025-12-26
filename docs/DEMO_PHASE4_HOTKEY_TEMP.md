# Phase 4 Temporary Hotkey Dev Harness

A minimal Windows-only developer harness that starts a global hotkey listener and toggles the Victus popup UI. This harness is text-only and intended for local dev testing.

## Install dependencies
```bash
pip install PySide6 pywin32
```

## Run
```bash
python run_hotkey_ui_temp.py
```

## Hotkey
- **Win + Alt + V**: toggle the popup window

## Controls
- **Enter**: submit text
- **Shift + Enter**: insert newline
- **Esc**: hide popup (if visible)

## Limitations
- Temporary dev harness: no installer, no tray icon
- Text in/out only (no voice, TTS, screenshots, or vision)
- No OAuth or connector changes
- Uses `VictusApp.run_request` only; respects policy/executor
