"""Temporary dev harness for Phase 4 hotkey + popup UI.

Running this script starts a Qt application that listens for the
Windows global hotkey Win+Alt+V. Pressing the hotkey toggles a minimal
Victus popup window for text input/output. The popup routes all
requests through VictusApp.run_request and never bypasses policy or
executor layers.
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Dict

from PySide6.QtWidgets import QApplication

from victus.app import VictusApp
from victus.core.policy import PolicyError
from victus.core.schemas import Context, PlanStep, PrivacySettings
from victus.domains.productivity.allowlisted_plugins import (
    DocsPlugin,
    GmailPlugin,
    OpenAIPlugin,
    SpotifyPlugin,
)
from victus.domains.system.system_plugin import SystemPlugin
from victus.ui.hotkey import GlobalHotkeyManager
from victus.ui.popup_window import PopupWindow


class HotkeyPopupController:
    """Runs a popup UI that toggles via a global hotkey."""

    def __init__(self) -> None:
        self.qt_app = QApplication.instance() or QApplication(sys.argv)

        self.victus = self._build_victus_app()
        self.popup = PopupWindow(self._handle_submit)
        self.hotkey = GlobalHotkeyManager(self.toggle_popup)
        self.last_position = None

        self.qt_app.aboutToQuit.connect(self._cleanup)

    def _build_victus_app(self) -> VictusApp:
        plugins = {
            "system": SystemPlugin(),
            "gmail": GmailPlugin(),
            "docs": DocsPlugin(),
            "spotify": SpotifyPlugin(),
            "openai": OpenAIPlugin(),
        }
        return VictusApp(plugins)

    def toggle_popup(self) -> None:
        if self.popup.isVisible():
            self.hide_popup()
        else:
            self.show_popup()

    def show_popup(self) -> None:
        if self.last_position:
            self.popup.move(self.last_position)
        self.popup.show()
        self.popup.raise_()
        self.popup.activateWindow()

    def hide_popup(self) -> None:
        self.last_position = self.popup.pos()
        self.popup.hide()

    def _build_context(self) -> Context:
        return Context(
            session_id="hotkey-session",
            timestamp=datetime.utcnow(),
            mode="dev",
            foreground_app=None,
            privacy=PrivacySettings(allow_send_to_openai=True),
        )

    def _build_steps(self, user_text: str) -> list[PlanStep]:
        return [
            PlanStep(
                id="openai-1",
                tool="openai",
                action="generate_text",
                args={"prompt": user_text},
            )
        ]

    def _handle_submit(self, text: str) -> None:
        self.popup.append_user_message(text)
        self.popup.set_thinking()
        try:
            results = self.victus.run_request(
                user_input=text,
                context=self._build_context(),
                domain="productivity",
                steps=self._build_steps(text),
            )
            response_text = self._format_results(results)
            self.popup.append_victus_message(response_text)
            self.popup.set_ready()
        except PolicyError as exc:
            self.popup.append_victus_message(f"Denied: {exc}")
            self.popup.set_denied()
        except Exception as exc:  # noqa: BLE001 - display minimal error message
            self.popup.append_victus_message(f"Error: {exc}")
            self.popup.set_error()

    @staticmethod
    def _format_results(results: Dict[str, object]) -> str:
        if not results:
            return "No response"
        first = next(iter(results.values()))
        if isinstance(first, dict):
            for key in ("content", "summary"):
                if key in first:
                    return str(first[key])
            return str(first)
        return str(first)

    def _cleanup(self) -> None:
        self.hotkey.unregister()

    def exec(self) -> int:
        code = self.qt_app.exec()
        self._cleanup()
        return code


def main() -> None:
    controller = HotkeyPopupController()
    sys.exit(controller.exec())


if __name__ == "__main__":
    main()
