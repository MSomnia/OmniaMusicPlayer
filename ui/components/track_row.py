from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
from core.models import Track
from ui.theme import COLORS, FONTS

ROW_HEIGHT = 38


class TrackRow(QWidget):
    """Track item widget: hover reveals an 'add to queue' button on the right."""

    queue_clicked = pyqtSignal(object)  # Track

    def __init__(self, track: Track, text: str, parent=None) -> None:
        super().__init__(parent)
        self._track = track
        self.setFixedHeight(ROW_HEIGHT)

        c, f = COLORS, FONTS

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        label = QLabel(text)
        label.setObjectName("trackRowLabel")
        layout.addWidget(label, stretch=1)

        self._btn = QPushButton("加入队列")
        self._btn.setObjectName("addToQueueBtn")
        self._btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.hide()
        self._btn.clicked.connect(self._on_btn_clicked)
        layout.addWidget(self._btn)

        self.setStyleSheet(f"""
            TrackRow {{
                background-color: transparent;
            }}
            #trackRowLabel {{
                color: {c['text_primary']};
                font-size: {f['size_sm']}px;
                background: transparent;
            }}
            #addToQueueBtn {{
                background-color: {c['bg_elevated']};
                border: 1px solid {c['border']};
                border-radius: 4px;
                color: {c['text_secondary']};
                font-size: {f['size_xs']}px;
                padding: 3px 10px;
            }}
            #addToQueueBtn:hover {{
                color: {c['text_primary']};
                border-color: {c['text_secondary']};
            }}
        """)

    def _on_btn_clicked(self) -> None:
        self.queue_clicked.emit(self._track)

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._btn.show()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._btn.hide()
