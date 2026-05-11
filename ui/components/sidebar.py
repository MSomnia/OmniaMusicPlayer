from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.theme import COLORS, FONTS


class SidebarWidget(QWidget):
    nav_changed = pyqtSignal(str)               # "home"|"search"|"library"|"settings"
    platform_login_requested = pyqtSignal(str)  # "netease"|"spotify"|"ytmusic"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(200)
        self._nav_buttons: dict[str, QPushButton] = {}
        self._platform_buttons: dict[str, QPushButton] = {}
        self._platform_names: dict[str, str] = {}
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(2)

        title = QLabel("Somnia")
        title.setObjectName("appName")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(16)

        for page_id, label in [
            ("search",  "🔍  搜索"),
            ("home",    "🏠  首页"),
            ("library", "📚  我的库"),
        ]:
            layout.addWidget(self._make_nav_btn(page_id, label))

        layout.addWidget(self._make_divider())
        layout.addSpacing(4)

        section = QLabel("平台账号")
        section.setObjectName("sectionLabel")
        layout.addWidget(section)

        for platform_id, name in [
            ("spotify",  "Spotify"),
            ("ytmusic",  "YouTube Music"),
            ("netease",  "网易云"),
        ]:
            layout.addWidget(self._make_platform_btn(platform_id, name))

        layout.addWidget(self._make_divider())
        layout.addStretch()

        layout.addWidget(self._make_nav_btn("settings", "⚙️  设置"))
        layout.addSpacing(8)

    def _make_nav_btn(self, page_id: str, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("navButton")
        btn.setCheckable(True)
        btn.clicked.connect(lambda _checked, p=page_id: self.nav_changed.emit(p))
        self._nav_buttons[page_id] = btn
        return btn

    def _make_platform_btn(self, platform_id: str, name: str) -> QPushButton:
        btn = QPushButton(f"○  {name}")
        btn.setObjectName("platformButton")
        btn.clicked.connect(
            lambda: self.platform_login_requested.emit(platform_id)
        )
        self._platform_buttons[platform_id] = btn
        self._platform_names[platform_id] = name
        return btn

    def _make_divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("divider")
        return line

    def _apply_styles(self) -> None:
        c, f = COLORS, FONTS
        self.setStyleSheet(f"""
            SidebarWidget {{
                background-color: {c['bg_surface']};
                border-right: 1px solid {c['border']};
            }}
            #appName {{
                color: {c['text_primary']};
                font-size: {f['size_md']}px;
                font-weight: bold;
                padding: 0 12px;
            }}
            #navButton {{
                text-align: left;
                padding: 8px 16px;
                background: transparent;
                border: none;
                border-left: 3px solid transparent;
                color: {c['text_secondary']};
                font-size: {f['size_sm']}px;
                border-radius: 0;
            }}
            #navButton:hover {{
                background-color: {c['bg_hover']};
                color: {c['text_primary']};
                border-left-color: {c['accent']};
            }}
            #navButton:checked {{
                background-color: {c['bg_hover']};
                color: {c['text_primary']};
                border-left-color: {c['accent']};
            }}
            #platformButton {{
                text-align: left;
                padding: 6px 16px;
                background: transparent;
                border: none;
                color: {c['text_secondary']};
                font-size: {f['size_sm']}px;
                border-radius: 0;
            }}
            #platformButton:hover {{
                background-color: {c['bg_hover']};
                color: {c['text_primary']};
            }}
            #divider {{
                color: {c['divider']};
                margin: 4px 12px;
                max-height: 1px;
            }}
            #sectionLabel {{
                color: {c['text_muted']};
                font-size: {f['size_xs']}px;
                padding: 4px 16px;
            }}
        """)

    def set_active_page(self, page_id: str) -> None:
        for pid, btn in self._nav_buttons.items():
            btn.setChecked(pid == page_id)

    def set_platform_status(self, platform_id: str, logged_in: bool) -> None:
        btn = self._platform_buttons.get(platform_id)
        if not btn:
            return
        name = self._platform_names[platform_id]
        if logged_in:
            btn.setText(f"●  {name}")
            btn.setStyleSheet(f"color: {COLORS['accent']};")
        else:
            btn.setText(f"○  {name}")
            btn.setStyleSheet("")
