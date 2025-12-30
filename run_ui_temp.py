"""Temporary Phase 4 popup runner for text-only UI checks.

Launch this script locally to open the Victus popup immediately. No
hotkeys, tray icons, or background listeners are used. All requests flow
through ``VictusApp.run_request`` to preserve policy and executor
coverage.
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import QThread, Signal
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
from victus.ui.popup_window import PopupWindow
from victus.ui.renderers import render_system_result


class GenerationWorker(QThread):
    chunk = Signal(str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        victus: VictusApp,
        user_text: str,
        context: Context,
        steps: List[PlanStep],
    ) -> None:
        super().__init__()
        self.victus = victus
        self.user_text = user_text
        self.context = context
        self.steps = steps
        self._stop_requested = False
        self._saw_chunk = False

    def stop(self) -> None:
        self._stop_requested = True

    def _should_stop(self) -> bool:
        return self._stop_requested

    def _emit_chunk(self, text: str) -> None:
        self._saw_chunk = True
        self.chunk.emit(text)

    def run(self) -> None:  # type: ignore[override]
        try:
            results = self.victus.run_request_streaming(
                user_input=self.user_text,
                context=self.context,
                domain="productivity",
                steps=self.steps,
                stream_callbacks={self.steps[0].id: self._emit_chunk},
                stop_requests={self.steps[0].id: self._should_stop},
            )
            final_text = PopupController._format_results(results)
            if final_text and not self._saw_chunk:
                self.chunk.emit(final_text)
            self.finished.emit(final_text)
        except PolicyError as exc:
            self.failed.emit(f"Denied: {exc}")
        except Exception as exc:  # noqa: BLE001 - minimal surface message
            self.failed.emit(f"Error: {exc}")


class PopupController:
    """Runs the popup window directly for local testing."""

    def __init__(self) -> None:
        self.qt_app = QApplication.instance() or QApplication(sys.argv)

        self.victus = self._build_victus_app()
        self.popup = PopupWindow(self._handle_submit)
        self.popup.stop_requested.connect(self._handle_stop_request)
        self.worker: Optional[GenerationWorker] = None
        self._show_popup()

    def _show_popup(self) -> None:
        self.popup.show()
        self.popup.raise_()
        self.popup.activateWindow()

    def _build_victus_app(self) -> VictusApp:
        plugins = {
            "system": SystemPlugin(),
            "gmail": GmailPlugin(),
            "docs": DocsPlugin(),
            "spotify": SpotifyPlugin(),
            "openai": OpenAIPlugin(),
        }
        return VictusApp(plugins)

    def _build_context(self) -> Context:
        return Context(
            session_id="ui-temp-session",
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
        self._cancel_worker()
        self.popup.append_user_message(text)
        self.popup.set_thinking()
        steps = self._build_steps(text)
        context = self._build_context()
        self.popup.begin_stream_message("Victus")
        worker = GenerationWorker(self.victus, text, context, steps)
        worker.chunk.connect(self.popup.append_stream_chunk)
        worker.finished.connect(self._handle_worker_finished)
        worker.failed.connect(self._handle_worker_failed)
        worker.finished.connect(self._clear_worker)
        worker.failed.connect(self._clear_worker)
        self.worker = worker
        worker.start()

    def _handle_worker_finished(self, final_text: str) -> None:
        self.popup.end_stream_message()
        if not final_text:
            self.popup.append_victus_message("No response")
        self.popup.set_ready()

    def _handle_worker_failed(self, message: str) -> None:
        self.popup.end_stream_message()
        self.popup.append_victus_message(message)
        if message.startswith("Denied:"):
            self.popup.set_denied()
        else:
            self.popup.set_error()

    def _handle_stop_request(self) -> None:
        if self.worker:
            self.worker.stop()

    def _cancel_worker(self) -> None:
        if self.worker:
            self.worker.stop()
            self.worker.wait(2000)
            self.worker = None

    def _clear_worker(self, *_args) -> None:
        self.worker = None

    @staticmethod
    def _format_results(results: Dict[str, object]) -> str:
        if not results:
            return "No response"
        first = next(iter(results.values()))
        if isinstance(first, dict):
            system_rendered = render_system_result(first)
            if system_rendered:
                return system_rendered
            for key in ("content", "summary"):
                if key in first:
                    return str(first[key])
            return str(first)
        return str(first)

    def exec(self) -> int:
        return self.qt_app.exec()


def main() -> None:
    controller = PopupController()
    sys.exit(controller.exec())


if __name__ == "__main__":
    main()
