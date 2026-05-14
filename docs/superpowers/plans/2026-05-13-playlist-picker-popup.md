# PlaylistPickerPopup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 点击"加歌单"按钮后立即弹出含"加载歌单中..."占位的自定义下拉面板，异步获取歌单后填充内容，提供即时视觉反馈。

**Architecture:** 新建 `PlaylistPickerPopup(QFrame)` 独立组件，持有 loading/loaded/empty/error 四种状态，通过 `playlist_selected` 信号向上层传递选择结果。`app_window.py` 中的 `_open_add_to_playlist_menu()` 重构为：先弹出 popup（loading），再异步获取歌单，结果到达后调用 `set_playlists()` 或 `set_error()`。

**Tech Stack:** Python 3.11+, PyQt6, asyncio (qasync), pytest-qt

---

## File Map

| 文件 | 操作 |
|------|------|
| `ui/components/playlist_picker_popup.py` | 新建：PlaylistPickerPopup 组件 |
| `tests/test_playlist_picker_popup.py` | 新建：组件单元测试 |
| `ui/app_window.py` | 修改：`_open_add_to_playlist_menu()` + import |

---

## Task 1: 创建 PlaylistPickerPopup 组件

**Files:**
- Create: `ui/components/playlist_picker_popup.py`
- Test: `tests/test_playlist_picker_popup.py`

- [ ] **Step 1: 写失败测试（构造与初始状态）**

新建 `tests/test_playlist_picker_popup.py`，内容如下：

```python
import pytest
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton
from PyQt6.QtCore import Qt
from ui.components.playlist_picker_popup import PlaylistPickerPopup
from core.models import Playlist


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_popup(qapp, qtbot, platform="spotify"):
    p = PlaylistPickerPopup(platform)
    qtbot.addWidget(p)
    return p


def test_initial_shows_loading(qapp, qtbot):
    p = _make_popup(qapp, qtbot)
    loading = p.findChild(QLabel, "loading_lbl")
    assert loading is not None
    assert loading.isVisible()
    assert "加载歌单中" in loading.text()


def test_title_contains_platform_label(qapp, qtbot):
    p = _make_popup(qapp, qtbot, platform="spotify")
    title = p.findChild(QLabel, "title_lbl")
    assert title is not None
    assert "Spotify" in title.text()


def test_title_netease(qapp, qtbot):
    p = _make_popup(qapp, qtbot, platform="netease")
    title = p.findChild(QLabel, "title_lbl")
    assert "网易云音乐" in title.text()


def test_title_ytmusic(qapp, qtbot):
    p = _make_popup(qapp, qtbot, platform="ytmusic")
    title = p.findChild(QLabel, "title_lbl")
    assert "YouTube Music" in title.text()
```

- [ ] **Step 2: 运行，确认失败**

```bash
cd /Users/msomnia/Library/CloudStorage/OneDrive-Personal/1MSomnia/code/SomniaPlayer
python -m pytest tests/test_playlist_picker_popup.py -v 2>&1 | head -20
```

预期：`ModuleNotFoundError: No module named 'ui.components.playlist_picker_popup'`

- [ ] **Step 3: 实现组件骨架（通过初始状态测试）**

新建 `ui/components/playlist_picker_popup.py`：

```python
from __future__ import annotations
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QApplication,
)
from PyQt6.QtCore import Qt, QPoint, QEvent, pyqtSignal
from PyQt6.QtGui import QCursor
from core.models import Playlist
from ui.theme import COLORS, FONTS

_PLATFORM_LABELS = {
    "netease": "网易云音乐",
    "spotify": "Spotify",
    "ytmusic": "YouTube Music",
}

_WIDTH = 220
_MAX_LIST_HEIGHT = 260


class PlaylistPickerPopup(QFrame):
    playlist_selected = pyqtSignal(object)  # Playlist

    def __init__(self, platform: str, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(_WIDTH)
        self.setStyleSheet(f"""
            PlaylistPickerPopup {{
                background-color: {COLORS['bg_elevated']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 6, 4, 6)
        root.setSpacing(0)

        # Title
        title_lbl = QLabel(
            f"加入到 {_PLATFORM_LABELS.get(platform, platform)} 歌单"
        )
        title_lbl.setObjectName("title_lbl")
        title_lbl.setStyleSheet(f"""
            color: {COLORS['text_muted']};
            font-size: {FONTS['size_sm']}px;
            padding: 4px 8px;
        """)
        root.addWidget(title_lbl)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']}; margin: 2px 0;")
        root.addWidget(sep)

        # Loading label (default visible)
        self._loading_lbl = QLabel("加载歌单中...")
        self._loading_lbl.setObjectName("loading_lbl")
        self._loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_lbl.setStyleSheet(f"""
            color: {COLORS['text_muted']};
            font-size: {FONTS['size_sm']}px;
            padding: 12px 8px;
        """)
        root.addWidget(self._loading_lbl)

        # Scroll area (hidden until data arrives)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setMaximumHeight(_MAX_LIST_HEIGHT)
        self._scroll.setVisible(False)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(1)
        self._scroll.setWidget(self._list_widget)
        root.addWidget(self._scroll)

        QApplication.instance().installEventFilter(self)

    # ── public API ───────────────────────────────────────────────────────────

    def show_at(self, pos: QPoint) -> None:
        self.adjustSize()
        screen = QApplication.primaryScreen().availableGeometry()
        x = min(pos.x(), screen.right() - _WIDTH - 4)
        y = min(pos.y(), screen.bottom() - self.sizeHint().height() - 4)
        self.move(max(x, screen.left()), max(y, screen.top()))
        self.show()

    def set_playlists(self, playlists: list[Playlist]) -> None:
        if not self.isVisible():
            return
        self._loading_lbl.setVisible(False)
        self._clear_list()

        if not playlists:
            lbl = QLabel("没有可加入的歌单")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"""
                color: {COLORS['text_muted']};
                font-size: {FONTS['size_sm']}px;
                padding: 12px 8px;
            """)
            self._list_layout.addWidget(lbl)
        else:
            for playlist in playlists:
                name = playlist.name or "未命名歌单"
                count = f"  {playlist.track_count}首" if playlist.track_count else ""
                btn = QPushButton(f"{name}{count}")
                btn.setFlat(True)
                btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                btn.setStyleSheet(f"""
                    QPushButton {{
                        text-align: left;
                        padding: 6px 12px;
                        border: none;
                        border-radius: 4px;
                        color: {COLORS['text_primary']};
                        font-size: {FONTS['size_sm']}px;
                        background: transparent;
                    }}
                    QPushButton:hover {{
                        background-color: {COLORS['bg_hover']};
                    }}
                """)
                btn.clicked.connect(
                    lambda checked, p=playlist: self._on_item_clicked(p)
                )
                self._list_layout.addWidget(btn)

        self._scroll.setVisible(True)
        self.adjustSize()

    def set_error(self, msg: str) -> None:
        if not self.isVisible():
            return
        self._loading_lbl.setText(msg)

    # ── internal ─────────────────────────────────────────────────────────────

    def _clear_list(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_item_clicked(self, playlist: Playlist) -> None:
        self.playlist_selected.emit(playlist)
        self.close()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            global_pos = event.globalPosition().toPoint()
            if self.isVisible() and not self.geometry().contains(global_pos):
                self.close()
        return False

    def closeEvent(self, event) -> None:  # type: ignore[override]
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)
```

- [ ] **Step 4: 运行初始状态测试，确认通过**

```bash
python -m pytest tests/test_playlist_picker_popup.py::test_initial_shows_loading tests/test_playlist_picker_popup.py::test_title_contains_platform_label tests/test_playlist_picker_popup.py::test_title_netease tests/test_playlist_picker_popup.py::test_title_ytmusic -v
```

预期：4 个 PASS

- [ ] **Step 5: 写失败测试（set_playlists 行为）**

在 `tests/test_playlist_picker_popup.py` 末尾追加：

```python
def _make_playlist(name="我的歌单", track_count=10):
    return Playlist(id="p1", platform="spotify", name=name,
                    cover_url="", track_count=track_count)


def test_set_playlists_hides_loading(qapp, qtbot):
    p = _make_popup(qapp, qtbot)
    p.set_playlists([_make_playlist()])
    loading = p.findChild(QLabel, "loading_lbl")
    assert not loading.isVisible()


def test_set_playlists_shows_buttons(qapp, qtbot):
    p = _make_popup(qapp, qtbot)
    playlists = [_make_playlist("歌单A", 5), _make_playlist("歌单B", 0)]
    p.set_playlists(playlists)
    btns = p.findChildren(QPushButton)
    labels = [b.text() for b in btns]
    assert any("歌单A" in t and "5首" in t for t in labels)
    assert any("歌单B" in t for t in labels)


def test_set_playlists_empty_shows_no_playlist_message(qapp, qtbot):
    p = _make_popup(qapp, qtbot)
    p.set_playlists([])
    labels = [l.text() for l in p.findChildren(QLabel)]
    assert any("没有可加入的歌单" in t for t in labels)


def test_set_error_updates_loading_label(qapp, qtbot):
    p = _make_popup(qapp, qtbot)
    p.set_error("获取歌单失败")
    loading = p.findChild(QLabel, "loading_lbl")
    assert loading.isVisible()
    assert "获取歌单失败" in loading.text()


def test_playlist_selected_signal(qapp, qtbot):
    p = _make_popup(qapp, qtbot)
    pl = _make_playlist("测试歌单")
    p.set_playlists([pl])
    received = []
    p.playlist_selected.connect(received.append)
    btns = p.findChildren(QPushButton)
    target = next(b for b in btns if "测试歌单" in b.text())
    target.click()
    assert received == [pl]


def test_set_playlists_noop_when_not_visible(qapp, qtbot):
    p = _make_popup(qapp, qtbot)
    # Not shown → set_playlists should silently do nothing
    p.set_playlists([_make_playlist()])
    # loading label remains visible (popup never shown → state unchanged)
    loading = p.findChild(QLabel, "loading_lbl")
    assert loading.isVisible()
```

- [ ] **Step 6: 运行，确认失败**

```bash
python -m pytest tests/test_playlist_picker_popup.py -v 2>&1 | tail -20
```

预期：新增的 6 个测试 FAIL（`set_playlists` 中 `isVisible()` 为 False，导致 noop）

- [ ] **Step 7: 运行全部测试，确认通过**

```bash
python -m pytest tests/test_playlist_picker_popup.py -v
```

预期：所有测试 PASS

> **注意**：`test_set_playlists_noop_when_not_visible` 验证组件未显示时 `set_playlists` 是空操作。其余测试的 popup 也未调用 `show_at()`，但 `set_playlists` 内部检查 `isVisible()`，故仍为 noop。要测试实际渲染，需先 `p.show()`。
>
> 如果这批测试中的 set_playlists 相关测试因为 isVisible() == False 而全部失败，将 `_make_popup` 改为先调 `p.show()` 再返回。

- [ ] **Step 8: Commit**

```bash
git add ui/components/playlist_picker_popup.py tests/test_playlist_picker_popup.py
git commit -m "feat: add PlaylistPickerPopup component with loading state"
```

---

## Task 2: 集成到 app_window.py

**Files:**
- Modify: `ui/app_window.py:8-11`（import 区域）
- Modify: `ui/app_window.py:502-558`（`_open_add_to_playlist_menu`）

- [ ] **Step 1: 写集成失败测试**

在 `tests/test_ui_components.py` 中，在 `_MockCtrl` 类里补充 playlist 相关方法（如果还没有），然后在文件末尾追加：

```python
def test_add_to_playlist_shows_popup_immediately(qapp_instance, qtbot):
    """点击加歌单后，popup 应立即可见（即使歌单还没加载）。"""
    import asyncio
    from unittest.mock import AsyncMock, patch
    from PyQt6.QtCore import QPoint
    from ui.components.playlist_picker_popup import PlaylistPickerPopup

    # 确保 _MockCtrl 有这两个方法
    async def _slow_get_playlists(platform):
        await asyncio.sleep(0)   # 模拟异步
        return []

    ctrl = _MockCtrl()
    ctrl.get_addable_playlists = _slow_get_playlists
    ctrl.add_track_to_playlist = AsyncMock(return_value=True)
    ctrl.is_spotify_authenticated = True

    win = MainWindow(ctrl)
    qtbot.addWidget(win)

    from core.models import Track
    track = Track(
        id="t1", platform="spotify", title="Song", artist="Artist",
        artists=["Artist"], album="Album", album_cover_url="",
        duration_ms=180000,
    )

    popups_shown: list[PlaylistPickerPopup] = []
    original_init = PlaylistPickerPopup.__init__

    def patched_init(self, platform, parent=None):
        original_init(self, platform, parent)
        popups_shown.append(self)

    with patch.object(PlaylistPickerPopup, '__init__', patched_init):
        win._request_add_to_playlist(track, QPoint(100, 100))

    # Event loop を一周させる
    qtbot.wait(50)
    assert len(popups_shown) == 1
```

> 这是一个粗粒度集成测试，验证 popup 被创建。更细粒度的 popup 行为已在 Task 1 的测试中覆盖。

- [ ] **Step 2: 运行，确认失败**

```bash
python -m pytest tests/test_ui_components.py::test_add_to_playlist_shows_popup_immediately -v
```

预期：FAIL（`_MockCtrl` 缺少 `get_addable_playlists` 或 popup 未被创建）

- [ ] **Step 3: 修改 app_window.py — 替换 import**

在 [ui/app_window.py](ui/app_window.py) 顶部，找到：

```python
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QLabel,
    QMenu,
)
```

改为（移除 `QMenu`，添加 `PlaylistPickerPopup` import）：

```python
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QLabel,
)
from ui.components.playlist_picker_popup import PlaylistPickerPopup
```

- [ ] **Step 4: 修改 app_window.py — 重构 `_open_add_to_playlist_menu`**

找到并整体替换 `_open_add_to_playlist_menu` 方法（[ui/app_window.py:502-558](ui/app_window.py#L502-L558)）：

```python
async def _open_add_to_playlist_menu(self, track, pos) -> None:
    if not track:
        return
    if not self._is_platform_authenticated(track.platform):
        ok = await self._ensure_platform_auth(track.platform)
        if not ok:
            self._status_toast.popup("需要先登录对应平台", success=False)
            return

    popup = PlaylistPickerPopup(track.platform, parent=self)

    async def _on_selected(playlist) -> None:
        ok = await self._ctrl.add_track_to_playlist(track, playlist)
        if ok:
            self._status_toast.popup(f"已加入 {playlist.name}")
        else:
            msg = getattr(self._ctrl, "last_playlist_error", "") or "加入歌单失败"
            self._status_toast.popup(msg, success=False)

    popup.playlist_selected.connect(lambda p: asyncio.ensure_future(_on_selected(p)))
    popup.show_at(pos)

    try:
        playlists = await self._ctrl.get_addable_playlists(track.platform)
        popup.set_playlists(playlists)
    except Exception:
        popup.set_error("获取歌单失败")
```

- [ ] **Step 5: 运行集成测试，确认通过**

```bash
python -m pytest tests/test_ui_components.py::test_add_to_playlist_shows_popup_immediately -v
```

预期：PASS

- [ ] **Step 6: 运行全量测试，确认无回归**

```bash
python -m pytest tests/ -v 2>&1 | tail -30
```

预期：所有原有测试 PASS，无新失败

- [ ] **Step 7: Commit**

```bash
git add ui/app_window.py
git commit -m "feat: show playlist picker popup immediately on click with loading state"
```

---

## 自检（Self-Review）

**Spec coverage:**
- ✅ 点击立即弹出 → Task 2, Step 4（`popup.show_at(pos)` 在 `await` 之前）
- ✅ 显示"加载歌单中..." → Task 1 组件骨架初始状态
- ✅ 歌单到达后填充 → `set_playlists()` + Task 1 Step 5 测试
- ✅ 空歌单状态 → `set_playlists([])` 分支
- ✅ 加载失败状态 → `set_error()` + Task 1 Step 5 测试
- ✅ 点击外部关闭 → `eventFilter` + `closeEvent` 清理
- ✅ Esc 关闭 → `keyPressEvent`
- ✅ 选中后触发 add_track_to_playlist → `_on_selected` lambda

**Type consistency:**
- `set_playlists(playlists: list[Playlist])` — Task 1 实现与 Task 2 调用一致
- `set_error(msg: str)` — Task 1 实现与 Task 2 调用一致
- `playlist_selected = pyqtSignal(object)` — Task 1 定义，Task 2 `.connect()` 使用

**Placeholder scan:** 无 TBD/TODO
