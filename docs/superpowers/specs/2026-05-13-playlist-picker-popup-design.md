# Design: PlaylistPickerPopup — 加歌单即时反馈

**Date**: 2026-05-13  
**Branch**: feat/phase4-youtube-music  
**Scope**: 加歌单按钮点击后立即弹出加载中面板，歌单到达后填充

---

## Problem

当前 `_open_add_to_playlist_menu()` 先 `await get_addable_playlists()`（0.5–3 秒网络请求），再创建和显示 `QMenu`。用户点击"加歌单"按钮后没有任何视觉反馈，体验差。

## Solution Overview

新建 `PlaylistPickerPopup(QFrame)` 自定义下拉面板组件，点击按钮后立即弹出（loading 状态），异步获取歌单后填充内容。

---

## Component: PlaylistPickerPopup

**文件**: `ui/components/playlist_picker_popup.py`

### 状态机

```
show() → loading
  └─ set_playlists([]) → empty
  └─ set_playlists([...]) → loaded
  └─ set_error(msg) → error
```

### 布局（从上到下）

1. **标题行** — `"加入到 {platform} 歌单"`，`text_muted` 颜色，不可交互
2. **分隔线** — 1px `border` 颜色
3. **内容区**（根据状态切换）：
   - `loading`：`"加载歌单中..."` 居中，`text_muted` 颜色，禁用
   - `loaded`：QScrollArea 内的歌单列表，每项 `"{name}  {N}首"`，hover 高亮
   - `empty`：`"没有可加入的歌单"` 居中，`text_muted` 颜色，禁用
   - `error`：错误信息，`text_muted` 颜色，禁用

### 样式

复用现有 `COLORS` / `FONTS` 变量：
- 背景：`bg_elevated`
- 边框：`1px solid {border}`，`border-radius: 6px`
- 内容区最大高度：300px（超出时 QScrollArea 滚动）
- 每个歌单项：padding `6px 12px`，hover 时背景 `bg_hover`，border-radius `4px`
- 宽度：固定 220px

### 信号

```python
playlist_selected = pyqtSignal(object)  # 发出 Playlist 对象
```

用户点击某个歌单项时发出，popup 随即关闭。

### 关闭逻辑

- 选中歌单后 → 发出信号 → 关闭
- 点击面板外部 → `QApplication.instance().installEventFilter(self)` 监听 `MouseButtonPress` → 关闭
- 按 Esc 键 → `keyPressEvent` → 关闭
- 析构时自动清理 eventFilter

### 定位

接收 `pos: QPoint`（全局坐标），自动调整使面板不超出屏幕边界。

---

## Integration: app_window.py

### 修改 `_open_add_to_playlist_menu()`

**重构为两阶段**：

```python
async def _open_add_to_playlist_menu(self, track, pos) -> None:
    if not track:
        return
    if not self._is_platform_authenticated(track.platform):
        ok = await self._ensure_platform_auth(track.platform)
        if not ok:
            self._status_toast.popup("需要先登录对应平台", success=False)
            return

    # 阶段1：立即显示 popup（loading 状态）
    popup = PlaylistPickerPopup(track.platform, parent=self)
    popup.show_at(pos)

    # 阶段2：后台获取歌单
    try:
        playlists = await self._ctrl.get_addable_playlists(track.platform)
        popup.set_playlists(playlists)  # 空列表时内部自动切换 empty 状态
    except Exception:
        popup.set_error("获取歌单失败")

    # 阶段3：处理选择
    async def _on_selected(playlist):
        ok = await self._ctrl.add_track_to_playlist(track, playlist)
        if ok:
            self._status_toast.popup(f"已加入 {playlist.name}")
        else:
            msg = getattr(self._ctrl, "last_playlist_error", "") or "加入歌单失败"
            self._status_toast.popup(msg, success=False)

    popup.playlist_selected.connect(lambda p: asyncio.ensure_future(_on_selected(p)))
```

**注意**：若 popup 在 await 期间被用户手动关闭（点外部/Esc），需在调用 `set_playlists` 前判断 popup 是否还存活（`popup.isVisible()`）。

### 导入

在 `app_window.py` 顶部添加：
```python
from ui.components.playlist_picker_popup import PlaylistPickerPopup
```

---

## Files Changed

| 文件 | 变更类型 |
|------|----------|
| `ui/components/playlist_picker_popup.py` | 新建 |
| `ui/app_window.py` | 修改 `_open_add_to_playlist_menu()` + 添加 import |

---

## Out of Scope

- 预获取缓存（悬停预拉取）
- 创建新歌单入口
- 搜索歌单功能
