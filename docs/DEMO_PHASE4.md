# Victus Phase 4 Popup Demo (Legacy)

This legacy demo opens the Qt popup UI directly for text-only interactions. The web UI (victus_local) is now the primary interface, but the popup remains useful for quick desktop checks.

## Prerequisites
- Python 3.11+
- Desktop environment capable of rendering Qt windows
- Dependencies:
  ```bash
  pip install PySide6
  ```

## Run the popup
From the repo root:
```bash
python run_ui_temp.py
```
The popup window opens immediately with no tray icon or global hotkey.

## Controls
- **Enter**: send the message
- **Shift + Enter**: insert a newline
- **Window close**: exit the popup

## Request flow
1. The popup sends user text to `VictusApp.run_request_streaming` with a simple OpenAI planning step (`openai.generate_text`).
2. Privacy is configured to allow outbound LLM text so policy review succeeds.
3. The returned assistant text is rendered in the transcript. Policy denials or execution errors are surfaced with `Denied`/`Error` labels.

## Notes
- Text in/out only: no voice, vision, automation, or background listeners.
- The popup is intended for local desktop use and may not render in headless containers.
