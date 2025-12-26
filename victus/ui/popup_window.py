from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
    QTextEdit,
    QPlainTextEdit,
    QSizePolicy,
)


class PopupWindow(QWidget):
    submit = Signal(str)

    def __init__(self, on_submit: Callable[[str], None]) -> None:
        super().__init__()
        self.setWindowTitle("Victus")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(600, 480)

        self._build_ui()
        self.submit.connect(on_submit)
        self._set_status("Ready")

    def _build_ui(self) -> None:
        container = QVBoxLayout(self)
        container.setContentsMargins(12, 12, 12, 12)

        card = QWidget()
        card.setObjectName("card")
        card.setStyleSheet(
            """
            QWidget#card {
                background-color: #151515;
                border-radius: 12px;
                border: 1px solid #242424;
            }
            QLabel#status {
                padding: 4px 10px;
                border-radius: 10px;
                color: #e8e8e8;
                background-color: #2d2d2d;
                font-size: 11px;
            }
            QPushButton#closeButton {
                color: #bbbbbb;
                background: transparent;
                border: none;
                font-size: 14px;
                padding: 4px 8px;
            }
            QPushButton#closeButton:hover {
                color: #ffffff;
                background-color: #2a2a2a;
                border-radius: 6px;
            }
            QTextEdit#transcript {
                background-color: #1b1b1b;
                color: #f5f5f5;
                border: 1px solid #2a2a2a;
                border-radius: 10px;
                padding: 10px;
            }
            QPlainTextEdit#inputBox {
                background-color: #1b1b1b;
                color: #f5f5f5;
                border: 1px solid #2a2a2a;
                border-radius: 10px;
                padding: 10px;
            }
            QLabel#hint {
                color: #8a8a8a;
                font-size: 11px;
            }
            """
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Victus")
        title.setStyleSheet("color: white; font-weight: 600; font-size: 15px;")
        header.addWidget(title)

        header.addItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.status = QLabel("Ready")
        self.status.setObjectName("status")
        header.addWidget(self.status)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("closeButton")
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)

        layout.addLayout(header)

        self.transcript = QTextEdit()
        self.transcript.setObjectName("transcript")
        self.transcript.setReadOnly(True)
        self.transcript.setMinimumHeight(260)
        self.transcript.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.transcript)

        self.input_box = QPlainTextEdit()
        self.input_box.setObjectName("inputBox")
        self.input_box.setPlaceholderText("Ask Victus…")
        self.input_box.setFont(QFont("Segoe UI", 10))
        self.input_box.installEventFilter(self)
        layout.addWidget(self.input_box)

        hint = QLabel("Enter to send • Shift+Enter for newline • Esc to close")
        hint.setObjectName("hint")
        layout.addWidget(hint)

        container.addWidget(card)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.input_box.setFocus()

    def eventFilter(self, source, event):  # type: ignore[override]
        if source is self.input_box and event.type() == QEvent.KeyPress:
            if event.key() in {Qt.Key_Return, Qt.Key_Enter}:
                if event.modifiers() & Qt.ShiftModifier:
                    return False
                self._emit_submit()
                return True
            if event.key() == Qt.Key_Escape:
                self.hide()
                return True
            if event.key() == Qt.Key_L and event.modifiers() & Qt.ControlModifier:
                self.input_box.clear()
                return True
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.hide()
            return True
        return super().eventFilter(source, event)

    def _emit_submit(self) -> None:
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        self.input_box.clear()
        self.submit.emit(text)

    def append_user_message(self, text: str) -> None:
        self._append_message("You", text)

    def append_victus_message(self, text: str) -> None:
        self._append_message("Victus", text)

    def _append_message(self, speaker: str, text: str) -> None:
        existing = self.transcript.toHtml()
        message_block = f"<b style='color:#9cdcfe'>{speaker}:</b> <span style='color:#e5e5e5'>{text}</span>"
        if existing:
            updated = existing + "<br/>" + message_block
        else:
            updated = message_block
        self.transcript.setHtml(updated)
        self.transcript.verticalScrollBar().setValue(self.transcript.verticalScrollBar().maximum())

    def _set_status(self, label: str, color: str | None = None) -> None:
        palette_color = color or "#2d2d2d"
        self.status.setText(label)
        self.status.setStyleSheet(
            f"QLabel#status {{ background-color: {palette_color}; padding: 4px 10px; border-radius: 10px; color: #e8e8e8; font-size: 11px; }}"
        )

    def set_ready(self) -> None:
        self._set_status("Ready", "#2d2d2d")

    def set_thinking(self) -> None:
        self._set_status("Thinking", "#21599b")

    def set_denied(self) -> None:
        self._set_status("Denied", "#8c2f39")

    def set_error(self) -> None:
        self._set_status("Error", "#8c2f39")
