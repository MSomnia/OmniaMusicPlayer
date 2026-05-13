# Standby Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增"待机页"全屏覆盖视图——点击侧边栏用户名进入，左半显示封面/歌名/艺术家/滚动歌词，右半文字占位，保留底部 NowPlayingBar。

**Architecture:** `StandbyPage(QWidget)` 作为 `_AppRoot` 的直接子 widget，绝对定位覆盖 body 区域（sidebar + content），底部 NowPlayingBar 天然不被遮盖。`SidebarWidget` 新增 `standby_requested` 信号，`MainWindow` 连接信号并管理进入/退出动画。

**Tech Stack:** PyQt6 — `QPropertyAnimation`, `QGraphicsOpacityEffect`, `QRadialGradient`, `LyricsEngine`（内部复用）

---

## 文件地图

| 操作 | 路径 | 职责 |
|---|---|---|
| **新建** | `ui/pages/standby_page.py` | StandbyPage 完整实现 |
| **修改** | `ui/components/sidebar.py` | 添加 `_ClickableLabel`、`standby_requested` 信号 |
| **修改** | `ui/app_window.py` | 创建 StandbyPage、接线、resizeEvent、_toggle_standby |
| **修改** | `tests/test_ui_components.py` | 新增 sidebar 信号测试和 StandbyPage 状态测试 |

---

## Task 1: SidebarWidget — standby_requested 信号

**Files:**
- Modify: `ui/components/sidebar.py:1-10` (imports), `sidebar.py:12-15` (class header), `sidebar.py:28-37` (_setup_ui title block)
- Test: `tests/test_ui_components.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_ui_components.py` 的 `_MockCtrl` 类定义**之后**添加：

```python
def test_sidebar_standby_signal(qapp_instance, qtbot):
    w = SidebarWidget()
    qtbot.addWidget(w)
    received: list[int] = []
    w.standby_requested.connect(lambda: received.append(1))
    w._title.mousePressEvent(
        type("E", (), {"button": lambda self: Qt.MouseButton.LeftButton})()
    )
    assert received == [1]
```

同时在文件顶部 import 行补充：

```python
from PyQt6.QtCore import Qt
```

（如果已有则跳过）

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/msomnia/Library/CloudStorage/OneDrive-Personal/1MSomnia/code/SomniaPlayer
pytest tests/test_ui_components.py::test_sidebar_standby_signal -v
```

期望：`FAILED` — `AttributeError: 'SidebarWidget' object has no attribute 'standby_requested'`

- [ ] **Step 3: 实现 SidebarWidget 修改**

在 `ui/components/sidebar.py` 顶部添加 `_ClickableLabel`，并修改类定义：

```python
from __future__ import annotations
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QCursor
from ui.frosted import paint_frosted_panel
from ui.theme import COLORS, FONTS


class _ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class SidebarWidget(QWidget):
    nav_changed = pyqtSignal(str)
    platform_login_requested = pyqtSignal(str)
    standby_requested = pyqtSignal()           # ← 新增
```

在 `_setup_ui` 方法中，将 `self._title = QLabel()` 改为：

```python
        self._title = _ClickableLabel()
        self._title.setObjectName("appName")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.clicked.connect(self.standby_requested)   # ← 新增
        layout.addWidget(self._title)
        self._refresh_title()
        layout.addSpacing(16)
```

（删除原来的 `self._title = QLabel()` 和紧跟着的 `setObjectName`/`setAlignment`/`addWidget`/`_refresh_title`/`addSpacing` 行，用上面的块替换）

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_ui_components.py::test_sidebar_standby_signal -v
```

期望：`PASSED`

- [ ] **Step 5: 运行全量 UI 测试确认无回归**

```bash
pytest tests/test_ui_components.py -v
```

期望：全部 PASSED（包含原有 `test_sidebar_title_uses_greeting_and_display_name`）

- [ ] **Step 6: Commit**

```bash
git add ui/components/sidebar.py tests/test_ui_components.py
git commit -m "feat(sidebar): add standby_requested signal via clickable username label"
```

---

## Task 2: StandbyPage — 骨架、布局、关闭按钮

**Files:**
- Create: `ui/pages/standby_page.py`
- Test: `tests/test_ui_components.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_ui_components.py` 末尾添加：

```python
from ui.pages.standby_page import StandbyPage


def test_standby_page_creates_hidden(qapp_instance, qtbot):
    ctrl = _MockCtrl()
    # StandbyPage 需要一个有 background_pixmap() 方法的父 widget
    from PyQt6.QtWidgets import QWidget
    from PyQt6.QtGui import QPixmap
    parent_mock = QWidget()
    parent_mock.background_pixmap = lambda: QPixmap()
    qtbot.addWidget(parent_mock)
    page = StandbyPage(ctrl, parent_mock)
    qtbot.addWidget(page)
    assert page.isHidden()
    assert page._close_btn is not None


def test_standby_page_has_left_right_panels(qapp_instance, qtbot):
    ctrl = _MockCtrl()
    from PyQt6.QtWidgets import QWidget
    from PyQt6.QtGui import QPixmap
    parent_mock = QWidget()
    parent_mock.background_pixmap = lambda: QPixmap()
    qtbot.addWidget(parent_mock)
    page = StandbyPage(ctrl, parent_mock)
    qtbot.addWidget(page)
    assert page._title_label is not None
    assert page._artist_label is not None
    assert page._cover_label is not None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_ui_components.py::test_standby_page_creates_hidden -v
```

期望：`FAILED` — `ModuleNotFoundError` 或 `ImportError`

- [ ] **Step 3: 创建 StandbyPage 骨架**

新建 `ui/pages/standby_page.py`：

```python
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QTimer, pyqtSignal,
)
from PyQt6.QtGui import (
    QPainter, QPixmap, QPainterPath, QColor, QRadialGradient, QCursor,
)
from core.lyrics_engine import LyricsEngine
from core.models import LyricLine, PlayerState
from ui.theme import COLORS, FONTS


class _StandbyLyricLine(QLabel):
    def __init__(self, line: LyricLine, parent=None) -> None:
        super().__init__(parent)
        self._line = line
        self._is_current = False
        self._word_idx = -1
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setContentsMargins(0, 4, 0, 4)
        self._render()

    def set_state(self, is_current: bool, word_idx: int = -1) -> None:
        if self._is_current == is_current and self._word_idx == word_idx:
            return
        self._is_current = is_current
        self._word_idx = word_idx
        self._render()

    @staticmethod
    def _esc(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _render(self) -> None:
        if self._is_current:
            self.setStyleSheet(
                f"font-size: {FONTS['size_lyrics']}px; font-weight: bold;"
                " background: transparent;"
            )
            if self._line.words:
                parts: list[str] = []
                for i, word in enumerate(self._line.words):
                    if i < self._word_idx:
                        color = COLORS["lyrics_past"]
                    elif i == self._word_idx:
                        color = COLORS["accent"]
                    else:
                        color = COLORS["lyrics_future"]
                    parts.append(
                        f'<span style="color:{color};">{self._esc(word.text)}</span>'
                    )
                self.setText("".join(parts))
            else:
                color = COLORS["lyrics_active"]
                self.setText(
                    f'<span style="color:{color};">{self._esc(self._line.text)}</span>'
                )
        else:
            self.setStyleSheet(
                f"font-size: {FONTS['size_lg']}px; font-weight: normal;"
                " background: transparent;"
            )
            color = COLORS["lyrics_future"]
            self.setText(
                f'<span style="color:{color};">{self._esc(self._line.text)}</span>'
            )


class StandbyPage(QWidget):
    def __init__(self, ctrl, parent=None) -> None:
        super().__init__(parent)
        self._ctrl = ctrl
        self._engine = LyricsEngine()
        self._gradient_rgb: tuple[int, int, int] = (80, 60, 120)
        self._line_widgets: list[_StandbyLyricLine] = []
        self._current_line: int = -1
        self._last_position_ms: int = 0
        self._scroll_anim: QPropertyAnimation | None = None
        self._fade_anim: QPropertyAnimation | None = None
        self._pending_scroll: int | None = None
        self.setAutoFillBackground(False)
        self._setup_ui()
        self._apply_styles()
        self.hide()

    def _setup_ui(self) -> None:
        # ── Main horizontal split ─────────────────────────────────────────────
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left panel ────────────────────────────────────────────────────────
        left = QWidget()
        left.setObjectName("standbyLeft")
        left.setAutoFillBackground(False)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(40, 72, 40, 40)
        left_layout.setSpacing(0)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        # Cover image
        self._cover_label = QLabel()
        self._cover_label.setObjectName("standbyCover")
        self._cover_label.setFixedSize(130, 130)
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self._cover_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        left_layout.addSpacing(12)

        # Song title
        self._title_label = QLabel("暂无播放")
        self._title_label.setObjectName("standbyTitle")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setWordWrap(True)
        left_layout.addWidget(self._title_label)
        left_layout.addSpacing(4)

        # Artist
        self._artist_label = QLabel("—")
        self._artist_label.setObjectName("standbyArtist")
        self._artist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self._artist_label)
        left_layout.addSpacing(16)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("standbyDivider")
        left_layout.addWidget(divider)
        left_layout.addSpacing(16)

        # "No lyrics" placeholder
        self._no_lyrics_label = QLabel("暂无歌词")
        self._no_lyrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_lyrics_label.setStyleSheet(
            f"color: {COLORS['text_muted']};"
            f" font-size: {FONTS['size_lg']}px;"
            " background: transparent;"
        )

        # Lyrics scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background: transparent; border: none;")
        self._scroll.viewport().setStyleSheet("background: transparent;")

        self._lyric_container = QWidget()
        self._lyric_container.setStyleSheet("background: transparent;")
        self._lyric_layout = QVBoxLayout(self._lyric_container)
        self._lyric_layout.setContentsMargins(0, 40, 0, 80)
        self._lyric_layout.setSpacing(12)
        self._lyric_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._lyric_container)

        left_layout.addWidget(self._scroll, stretch=1)
        left_layout.addWidget(self._no_lyrics_label, stretch=1)
        self._set_mode_no_lyrics()

        # ── Right panel ───────────────────────────────────────────────────────
        right = QWidget()
        right.setObjectName("standbyRight")
        right.setAutoFillBackground(False)
        right_layout = QVBoxLayout(right)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        placeholder = QLabel("✦\n更多内容\n即将到来")
        placeholder.setObjectName("standbyPlaceholder")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(placeholder)

        root.addWidget(left, stretch=1)
        root.addWidget(right, stretch=1)

        # ── Close button (absolute overlay) ───────────────────────────────────
        self._close_btn = QPushButton("✕  退出待机", self)
        self._close_btn.setObjectName("standbyCloseBtn")
        self._close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._close_btn.setFixedSize(116, 32)
        self._close_btn.clicked.connect(self.leave)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._close_btn.move(12, 12)

    def _apply_styles(self) -> None:
        c, f = COLORS, FONTS
        self.setStyleSheet(f"""
            #standbyLeft, #standbyRight {{
                background: transparent;
            }}
            #standbyTitle {{
                color: {c['text_primary']};
                font-size: {f['size_xl']}px;
                font-weight: bold;
            }}
            #standbyArtist {{
                color: rgba(255,255,255,0.55);
                font-size: {f['size_sm']}px;
            }}
            #standbyDivider {{
                color: rgba(255,255,255,0.08);
                max-height: 1px;
                margin: 0 15%;
            }}
            #standbyPlaceholder {{
                color: rgba(255,255,255,0.18);
                font-size: {f['size_md']}px;
                line-height: 2;
            }}
            #standbyCloseBtn {{
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 16px;
                color: rgba(255,255,255,0.70);
                font-size: {f['size_xs']}px;
                padding: 0 14px;
            }}
            #standbyCloseBtn:hover {{
                background: rgba(255,255,255,0.18);
                color: {c['text_primary']};
            }}
        """)

    def _set_mode_lyrics(self) -> None:
        self._scroll.show()
        self._no_lyrics_label.hide()

    def _set_mode_no_lyrics(self) -> None:
        self._scroll.hide()
        self._no_lyrics_label.show()

    # ── Public API stubs (implemented in later tasks) ─────────────────────────

    def on_state_changed(self, state: PlayerState) -> None:
        pass

    def set_cover_art_bytes(self, data: bytes) -> None:
        pass

    def set_cover_color(self, r: int, g: int, b: int) -> None:
        pass

    def set_lyrics(self, lines: list[LyricLine]) -> None:
        pass

    def update_position(self, position_ms: int) -> None:
        pass

    def enter(self) -> None:
        self.show()
        self.raise_()

    def leave(self) -> None:
        self.hide()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_ui_components.py::test_standby_page_creates_hidden tests/test_ui_components.py::test_standby_page_has_left_right_panels -v
```

期望：`PASSED`

- [ ] **Step 5: Commit**

```bash
git add ui/pages/standby_page.py tests/test_ui_components.py
git commit -m "feat(standby): scaffold StandbyPage skeleton with layout and close button"
```

---

## Task 3: StandbyPage — 曲目信息显示（封面、歌名、艺术家、占位状态）

**Files:**
- Modify: `ui/pages/standby_page.py` — 实现 `on_state_changed`、`set_cover_art_bytes`、`_draw_cover`、`_set_placeholder_cover`、`_set_loading_cover`
- Test: `tests/test_ui_components.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_ui_components.py` 末尾添加：

```python
def _make_standby(qapp_instance, qtbot) -> "StandbyPage":
    ctrl = _MockCtrl()
    from PyQt6.QtWidgets import QWidget
    from PyQt6.QtGui import QPixmap
    parent_mock = QWidget()
    parent_mock.background_pixmap = lambda: QPixmap()
    qtbot.addWidget(parent_mock)
    page = StandbyPage(ctrl, parent_mock)
    qtbot.addWidget(page)
    return page


def test_standby_track_shows_title_and_artist(qapp_instance, qtbot):
    from core.models import Track
    page = _make_standby(qapp_instance, qtbot)
    track = Track(
        id="1", platform="netease", title="远走高飞", artist="金志文",
        artists=["金志文"], album="", album_cover_url="", duration_ms=240000,
    )
    page.on_state_changed(PlayerState(status="playing", current_track=track))
    assert page._title_label.text() == "远走高飞"
    assert page._artist_label.text() == "金志文"


def test_standby_clearing_track_restores_placeholder(qapp_instance, qtbot):
    from core.models import Track
    page = _make_standby(qapp_instance, qtbot)
    track = Track(
        id="1", platform="netease", title="远走高飞", artist="金志文",
        artists=["金志文"], album="", album_cover_url="", duration_ms=240000,
    )
    page.on_state_changed(PlayerState(status="playing", current_track=track))
    page.on_state_changed(PlayerState())   # clear
    assert page._title_label.text() == "暂无播放"
    assert page._artist_label.text() == "—"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_ui_components.py::test_standby_track_shows_title_and_artist -v
```

期望：`FAILED` — `assert "暂无播放" == "远走高飞"`（桩实现未修改标签文本）

- [ ] **Step 3: 实现 on_state_changed 和封面显示**

在 `ui/pages/standby_page.py` 中，替换以下三个方法的桩实现：

```python
    def on_state_changed(self, state: PlayerState) -> None:
        track = state.current_track
        if track is None:
            self._title_label.setText("暂无播放")
            self._artist_label.setText("—")
            self._set_placeholder_cover()
        else:
            self._title_label.setText(track.title)
            self._artist_label.setText(track.artist)
            if state.status == "loading":
                self._set_loading_cover()

    def set_cover_art_bytes(self, data: bytes) -> None:
        pixmap = QPixmap()
        if data and pixmap.loadFromData(data):
            self._draw_cover(pixmap)
        else:
            self._set_placeholder_cover()

    def _draw_cover(self, pixmap: QPixmap) -> None:
        size = 130
        scaled = pixmap.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        rounded = QPixmap(size, size)
        rounded.fill(Qt.GlobalColor.transparent)
        p = QPainter(rounded)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, size, size, 10, 10)
        p.setClipPath(path)
        x = (size - scaled.width()) // 2
        y = (size - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)
        p.end()
        self._cover_label.setPixmap(rounded)
        self._cover_label.setText("")
        self._cover_label.setStyleSheet("")

    def _set_placeholder_cover(self) -> None:
        self._cover_label.setPixmap(QPixmap())
        self._cover_label.setText("🎵")
        self._cover_label.setStyleSheet(
            "font-size: 48px;"
            " background: rgba(255,255,255,0.08);"
            " border-radius: 10px;"
        )

    def _set_loading_cover(self) -> None:
        self._cover_label.setPixmap(QPixmap())
        self._cover_label.setText("")
        self._cover_label.setStyleSheet(
            "background: rgba(255,255,255,0.08);"
            " border-radius: 10px;"
        )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_ui_components.py::test_standby_track_shows_title_and_artist tests/test_ui_components.py::test_standby_clearing_track_restores_placeholder -v
```

期望：`PASSED`

- [ ] **Step 5: Commit**

```bash
git add ui/pages/standby_page.py tests/test_ui_components.py
git commit -m "feat(standby): implement track info display with cover art and placeholder states"
```

---

## Task 4: StandbyPage — 歌词显示（LyricsEngine + 滚动）

**Files:**
- Modify: `ui/pages/standby_page.py` — 实现 `set_lyrics`、`update_position`、`_rebuild_line_widgets`、`_scroll_to_line`、`_do_pending_scroll`
- Test: `tests/test_ui_components.py`

- [ ] **Step 1: 写失败测试**

```python
def test_standby_set_lyrics_switches_to_lyrics_mode(qapp_instance, qtbot):
    from core.models import LyricLine
    page = _make_standby(qapp_instance, qtbot)
    lines = [
        LyricLine(start_ms=0, end_ms=3000, text="第一行"),
        LyricLine(start_ms=3000, end_ms=6000, text="第二行"),
    ]
    page.set_lyrics(lines)
    assert page._scroll.isVisible()
    assert not page._no_lyrics_label.isVisible()
    assert len(page._line_widgets) == 2


def test_standby_update_position_hidden_no_crash(qapp_instance, qtbot):
    from core.models import LyricLine
    page = _make_standby(qapp_instance, qtbot)
    page.set_lyrics([LyricLine(start_ms=0, end_ms=3000, text="行")])
    # widget is hidden — update_position should silently skip processing
    page.update_position(1500)
    # No exception = pass
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_ui_components.py::test_standby_set_lyrics_switches_to_lyrics_mode tests/test_ui_components.py::test_standby_update_position_hidden_no_crash -v
```

期望：`FAILED`

- [ ] **Step 3: 实现歌词方法**

在 `ui/pages/standby_page.py` 中替换 `set_lyrics`、`update_position` 的桩，并添加私有方法：

```python
    def set_lyrics(self, lines: list[LyricLine]) -> None:
        self._engine.load(lines)
        self._current_line = -1
        self._rebuild_line_widgets()
        if lines:
            self._set_mode_lyrics()
            if self._last_position_ms > 0:
                QTimer.singleShot(0, lambda: self.update_position(self._last_position_ms))
        else:
            self._set_mode_no_lyrics()

    def update_position(self, position_ms: int) -> None:
        self._last_position_ms = position_ms
        if not self.isVisible() or not self._line_widgets:
            return
        line_idx, word_idx = self._engine.update(position_ms)
        line_changed = line_idx != self._current_line
        for i, widget in enumerate(self._line_widgets):
            widget.set_state(i == line_idx, word_idx if i == line_idx else -1)
        if line_changed:
            self._current_line = line_idx
            if line_idx >= 0:
                self._pending_scroll = line_idx
                QTimer.singleShot(0, self._do_pending_scroll)

    def _rebuild_line_widgets(self) -> None:
        for w in self._line_widgets:
            self._lyric_layout.removeWidget(w)
            w.deleteLater()
        self._line_widgets.clear()
        for line in self._engine.lines:
            label = _StandbyLyricLine(line)
            label.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            self._lyric_layout.addWidget(label)
            self._line_widgets.append(label)

    def _do_pending_scroll(self) -> None:
        if self._pending_scroll is None:
            return
        line_idx = self._pending_scroll
        self._pending_scroll = None
        self._scroll_to_line(line_idx)

    def _scroll_to_line(self, line_idx: int) -> None:
        if line_idx < 0 or line_idx >= len(self._line_widgets):
            return
        target_widget = self._line_widgets[line_idx]
        widget_center = target_widget.y() + target_widget.height() // 2
        viewport_center = self._scroll.viewport().height() // 2
        target_value = widget_center - viewport_center
        sb = self._scroll.verticalScrollBar()
        target_value = max(0, min(target_value, sb.maximum()))
        if self._scroll_anim and self._scroll_anim.state() == QPropertyAnimation.State.Running:
            self._scroll_anim.stop()
        self._scroll_anim = QPropertyAnimation(sb, b"value", self)
        self._scroll_anim.setDuration(450)
        self._scroll_anim.setStartValue(sb.value())
        self._scroll_anim.setEndValue(target_value)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_anim.start()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_ui_components.py::test_standby_set_lyrics_switches_to_lyrics_mode tests/test_ui_components.py::test_standby_update_position_hidden_no_crash -v
```

期望：`PASSED`

- [ ] **Step 5: Commit**

```bash
git add ui/pages/standby_page.py tests/test_ui_components.py
git commit -m "feat(standby): implement lyrics display with LyricsEngine and smooth scroll"
```

---

## Task 5: StandbyPage — paintEvent（背景图 + 发光遮罩）

**Files:**
- Modify: `ui/pages/standby_page.py` — 实现 `paintEvent`、`set_cover_color`
- Test: `tests/test_ui_components.py`

- [ ] **Step 1: 写失败测试**

```python
def test_standby_set_cover_color_updates_gradient(qapp_instance, qtbot):
    page = _make_standby(qapp_instance, qtbot)
    page.set_cover_color(100, 150, 200)
    assert page._gradient_rgb == (100, 150, 200)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_ui_components.py::test_standby_set_cover_color_updates_gradient -v
```

期望：`FAILED`

- [ ] **Step 3: 实现 set_cover_color 和 paintEvent**

在 `ui/pages/standby_page.py` 中，替换 `set_cover_color` 的桩，并添加 `paintEvent`：

```python
    def set_cover_color(self, r: int, g: int, b: int) -> None:
        self._gradient_rgb = (r, g, b)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Black base
        painter.fillRect(self.rect(), Qt.GlobalColor.black)

        # Background image (from _AppRoot parent)
        parent = self.parent()
        if parent is not None and hasattr(parent, "background_pixmap"):
            bg: QPixmap = parent.background_pixmap()
            if not bg.isNull():
                scaled = bg.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (self.width() - scaled.width()) // 2
                y = (self.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)

        # Ambient overlay: rgba(0,0,0,0.25) → alpha ≈ 64
        painter.fillRect(self.rect(), QColor(0, 0, 0, 64))

        # Cover glow: radial gradient centred on the left half
        r, g, b = self._gradient_rgb
        cx = self.width() // 4
        cy = int(self.height() * 0.42)
        radius = int(self.width() * 0.35)
        grad = QRadialGradient(cx, cy, radius)
        grad.setColorAt(0.0, QColor(r, g, b, 77))   # opacity ≈ 0.30
        grad.setColorAt(1.0, QColor(r, g, b, 0))
        painter.fillRect(self.rect(), grad)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_ui_components.py::test_standby_set_cover_color_updates_gradient -v
```

期望：`PASSED`

- [ ] **Step 5: Commit**

```bash
git add ui/pages/standby_page.py tests/test_ui_components.py
git commit -m "feat(standby): implement paintEvent with background image and cover glow"
```

---

## Task 6: StandbyPage — 进入/退出动画

**Files:**
- Modify: `ui/pages/standby_page.py` — 替换 `enter()` 和 `leave()` 的桩实现
- Test: `tests/test_ui_components.py`

- [ ] **Step 1: 写失败测试**

```python
def test_standby_enter_uses_opacity_effect(qapp_instance, qtbot):
    from PyQt6.QtWidgets import QGraphicsOpacityEffect
    page = _make_standby(qapp_instance, qtbot)
    page.enter()
    assert isinstance(page.graphicsEffect(), QGraphicsOpacityEffect)


def test_standby_leave_creates_fade_animation(qapp_instance, qtbot):
    page = _make_standby(qapp_instance, qtbot)
    page.enter()
    page.leave()
    assert page._fade_anim is not None
    qtbot.waitUntil(lambda: page.isHidden(), timeout=1000)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_ui_components.py::test_standby_enter_uses_opacity_effect tests/test_ui_components.py::test_standby_leave_creates_fade_animation -v
```

期望：两个均 `FAILED` — 桩实现未设置 `QGraphicsOpacityEffect`，`_fade_anim` 始终为 `None`

- [ ] **Step 3: 实现带动画的 enter/leave**

在 `ui/pages/standby_page.py` 顶部补充导入：

```python
from PyQt6.QtWidgets import QGraphicsOpacityEffect
```

替换 `enter` 和 `leave` 方法：

```python
    def enter(self) -> None:
        if self._fade_anim is not None and self._fade_anim.state() == QPropertyAnimation.State.Running:
            self._fade_anim.stop()

        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        effect.setOpacity(0.0)

        self.show()
        self.raise_()

        self._fade_anim = QPropertyAnimation(effect, b"opacity", self)
        self._fade_anim.setDuration(300)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()

    def leave(self) -> None:
        if self._fade_anim is not None and self._fade_anim.state() == QPropertyAnimation.State.Running:
            self._fade_anim.stop()

        effect = self.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)

        start_opacity = effect.opacity() if isinstance(effect, QGraphicsOpacityEffect) else 1.0

        self._fade_anim = QPropertyAnimation(effect, b"opacity", self)
        self._fade_anim.setDuration(200)
        self._fade_anim.setStartValue(start_opacity)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_anim.finished.connect(self.hide)
        self._fade_anim.start()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_ui_components.py::test_standby_enter_uses_opacity_effect tests/test_ui_components.py::test_standby_leave_creates_fade_animation -v
```

期望：`PASSED`

- [ ] **Step 5: Commit**

```bash
git add ui/pages/standby_page.py tests/test_ui_components.py
git commit -m "feat(standby): implement fade-in/fade-out animation for enter/leave"
```

---

## Task 7: MainWindow — 集成（创建、接线、尺寸同步、切换）

**Files:**
- Modify: `ui/app_window.py` — import StandbyPage, create in `_setup_ui`, wire in `_wire_signals`, add `resizeEvent`, add `_toggle_standby`
- Test: `tests/test_ui_components.py`

- [ ] **Step 1: 写失败测试**

```python
def test_main_window_has_standby_page(qapp_instance, qtbot):
    ctrl = _MockCtrl()
    win = MainWindow(ctrl)
    qtbot.addWidget(win)
    assert hasattr(win, "_standby_page")
    from ui.pages.standby_page import StandbyPage
    assert isinstance(win._standby_page, StandbyPage)
    assert win._standby_page.isHidden()


def test_main_window_toggle_standby_shows_and_hides(qapp_instance, qtbot):
    ctrl = _MockCtrl()
    win = MainWindow(ctrl)
    qtbot.addWidget(win)
    win.show()
    win._toggle_standby()
    assert win._standby_page.isVisible()
    win._toggle_standby()
    qtbot.waitUntil(lambda: win._standby_page.isHidden(), timeout=1000)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_ui_components.py::test_main_window_has_standby_page tests/test_ui_components.py::test_main_window_toggle_standby_shows_and_hides -v
```

期望：`FAILED` — `AttributeError: 'MainWindow' object has no attribute '_standby_page'`

- [ ] **Step 3: 修改 ui/app_window.py**

**3a.** 在 `app_window.py` 顶部 import 区添加：

```python
from ui.pages.standby_page import StandbyPage
```

**3b.** 在 `_setup_ui` 方法中，在 `self._error_toast = _ErrorToast(central)` **之后**添加：

```python
        # Standby page — full-body overlay, hidden by default
        self._standby_page = StandbyPage(self._ctrl, central)
        central_h = central.height()
        np_h = self.now_playing.height() if self.now_playing.height() > 0 else 90
        self._standby_page.setGeometry(0, 0, central.width() or 900, central_h - np_h or 510)
```

**3c.** 在 `_wire_signals` 方法中，在 `ctrl.background_changed.connect(...)` 行**之后**添加：

```python
        # Sidebar standby toggle
        self.sidebar.standby_requested.connect(self._toggle_standby)

        # Standby page data feeds
        ctrl.state_changed.connect(self._standby_page.on_state_changed)
        ctrl.cover_art_bytes.connect(self._standby_page.set_cover_art_bytes)
        ctrl.cover_color_ready.connect(self._standby_page.set_cover_color)
        ctrl.lyrics_ready.connect(self._standby_page.set_lyrics)
        ctrl.position_changed.connect(self._standby_page.update_position)
```

**3d.** 在 `MainWindow` 类中添加 `resizeEvent` 方法（在 `showEvent` **之后**）：

```python
    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if hasattr(self, "_standby_page") and hasattr(self, "_app_root"):
            central = self._app_root
            np_h = self.now_playing.height()
            self._standby_page.setGeometry(0, 0, central.width(), central.height() - np_h)
```

**3e.** 在 `MainWindow` 类中添加 `_toggle_standby` 方法（在 `_on_platform_login` **之后**）：

```python
    def _toggle_standby(self) -> None:
        if self._standby_page.isVisible():
            self._standby_page.leave()
        else:
            self._standby_page.enter()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_ui_components.py::test_main_window_has_standby_page tests/test_ui_components.py::test_main_window_toggle_standby_shows_and_hides -v
```

期望：`PASSED`

- [ ] **Step 5: 运行全量测试确认无回归**

```bash
pytest tests/test_ui_components.py -v
```

期望：全部 `PASSED`

- [ ] **Step 6: Commit**

```bash
git add ui/app_window.py tests/test_ui_components.py
git commit -m "feat(standby): integrate StandbyPage into MainWindow with signal wiring and resize sync"
```

---

## 完成标志

- 点击侧边栏用户名 → 待机页 fade-in 出现，覆盖 sidebar + content，NowPlayingBar 正常显示
- 点击"✕ 退出待机" → fade-out 后消失，回到原来的页面
- 正在播放时：封面图（圆角 130px）+ 歌名 + 艺术家 + 滚动歌词高亮
- 无歌曲时：🎵 占位封面 + "暂无播放"
- 背景图存在时透出背景 + 封面颜色发光；无背景图时纯黑
- `pytest tests/test_ui_components.py` 全绿
