# 网易云播放流程接线 — 设计文档

> 日期：2026-05-11  
> 范围：AppController、侧边栏登录入口、SearchPage、完整播放信号链

---

## 目标

将已实现的底层模块（NeteaseClient、UnifiedPlayer、VLCBackend、NowPlayingBar）通过一个中央协调层接入可运行的 UI，实现：

- 侧边栏点击"网易云"触发登录 → 登录态指示变绿
- 搜索页输入关键词（400ms 防抖）→ 列表展示结果
- 点击曲目 → 立即播放（VLC）
- NowPlayingBar 实时更新进度、控制播放

---

## 新增 / 修改文件

| 文件 | 操作 |
|------|------|
| `core/app_controller.py` | 新建 |
| `ui/pages/search_page.py` | 新建 |
| `ui/components/track_list.py` | 新建 |
| `ui/components/sidebar.py` | 修改：平台行改为按钮 + 状态指示 |
| `ui/app_window.py` | 修改：接收 AppController，创建页面，连线 |
| `main.py` | 修改：构建 AppController，注入 MainWindow |

---

## 第一部分：AppController

**文件：** `core/app_controller.py`

**职责：** 持有全部服务对象，暴露高层异步操作，转发关键信号给 UI 层。

```python
class AppController(QObject):
    # 信号（转发给 UI 层）
    state_changed = pyqtSignal(PlayerState)
    position_changed = pyqtSignal(int)          # ms
    search_results_ready = pyqtSignal(list)     # list[Track]
    netease_auth_changed = pyqtSignal(bool)     # True=已登录

    # 持有的服务
    _repo: AppRepository
    _auth: NeteaseAuth
    _client: NeteaseClient | None               # None = 未登录
    _player: UnifiedPlayer
    _vlc: VLCBackend
    _queue: PlayQueue
```

**初始化流程（`async init()`）：**
1. `repo.init()` — 建表 + 读默认设置
2. 尝试 `auth.load_cookies()` — 若有已保存 Cookie，构建 `NeteaseClient`，发出 `netease_auth_changed(True)`
3. 连接 VLC → player → AppController 内部信号链

**公开方法：**

```python
async def ensure_netease_auth(parent) -> bool
    # 若已有 client 直接返回 True
    # 否则调用 NeteaseAuth.login(parent)，成功后构建 client，发 netease_auth_changed(True)

async def search(query: str) -> list[Track]
    # 要求已登录；调用 client.search(query)；发 search_results_ready

async def play_track(track: Track) -> None
    # 1. queue.set_tracks([track], 0)（暂只单首）
    # 2. player.load(track)
    # 3. url = await client.get_stream_url(track)
    # 4. vlc.play(url)
    # 5. player.on_load_success()
    # 出错：player.on_load_error(msg)

def toggle_play_pause() -> None
def seek(ms: int) -> None
async def play_next() -> None
    # queue.next() 返回 None（队列末尾且无循环）→ player.stop()
async def play_prev() -> None
```

**内部信号接线（在 `__init__` 完成）：**
```
vlc.position_changed  → player.update_position()
vlc.end_reached       → play_next()
vlc.error_occurred    → player.on_load_error()
player.state_changed  → self.state_changed (转发)
player.position_changed → self.position_changed (转发)
```

---

## 第二部分：侧边栏改动

**文件：** `ui/components/sidebar.py`

**改动：**

1. 新增信号：
   ```python
   platform_login_requested = pyqtSignal(str)  # "netease" | "spotify" | "ytmusic"
   ```

2. `_make_platform_row(platform_id, name)` 改为返回 `QPushButton`，点击时发出 `platform_login_requested(platform_id)`，存入 `self._platform_buttons` dict。

3. 新增公开方法：
   ```python
   def set_platform_status(platform_id: str, logged_in: bool) -> None
       # logged_in=True  → 按钮文字改为 "●  {name}"，颜色改为 accent
       # logged_in=False → 按钮文字恢复 "○  {name}"，颜色恢复 text_secondary
   ```

---

## 第三部分：TrackListWidget

**文件：** `ui/components/track_list.py`

**职责：** 纯展示组件，接收 `list[Track]`，双信号驱动。

```python
class TrackListWidget(QWidget):
    track_selected = pyqtSignal(object)   # Track

    def set_tracks(tracks: list[Track]) -> None
    def clear() -> None
    def show_loading() -> None           # 显示"搜索中…"占位
    def show_empty(msg: str) -> None     # 显示"无结果"占位
```

内部用 `QListWidget`，每行通过 `QListWidgetItem` + `setData(Qt.UserRole, track)` 存储 Track 对象。双击触发 `track_selected`。

每行显示：`{title}  —  {artist}  [{mm:ss}]`，使用现有 COLORS / FONTS 主题。

---

## 第四部分：SearchPage

**文件：** `ui/pages/search_page.py`

**布局：**
```
SearchPage (QWidget)
  QVBoxLayout
    ├── QLineEdit  (搜索框，placeholder "搜索网易云音乐…")
    └── TrackListWidget
```

**行为：**
- `QTimer` (singleShot 400ms) 实现防抖：文字变化时 reset timer，timer 触发时调用 `_do_search()`
- `_do_search()` 调用 `asyncio.ensure_future(ctrl.search(query))`
- `ctrl.search_results_ready` → `track_list.set_tracks()`
- `track_list.track_selected` → `asyncio.ensure_future(ctrl.play_track(track))`
- 未登录时 `_do_search()` 先调用 `await ctrl.ensure_netease_auth(self)`，成功后继续搜索

---

## 第五部分：MainWindow + main.py 改动

**`main.py` 改动：**
```python
async def _run(app):
    ctrl = AppController()
    await ctrl.init()
    window = MainWindow(ctrl)          # 注入
    window.now_playing.set_volume(...)
    window.show()
    ...
```

**`app_window.py` 改动：**
```python
class MainWindow(QMainWindow):
    def __init__(self, ctrl: AppController) -> None:
        ...
        self._ctrl = ctrl
        # 创建页面
        self._search_page = SearchPage(ctrl)
        self.content.addWidget(self._search_page)
        # 连线
        ctrl.state_changed.connect(self.now_playing.update_state)
        ctrl.position_changed.connect(self.now_playing.update_position)
        self.now_playing.play_pause_clicked.connect(ctrl.toggle_play_pause)
        self.now_playing.seek_requested.connect(ctrl.seek)
        self.now_playing.next_clicked.connect(lambda: asyncio.ensure_future(ctrl.play_next()))
        self.now_playing.prev_clicked.connect(lambda: asyncio.ensure_future(ctrl.play_prev()))
        self.sidebar.platform_login_requested.connect(self._on_platform_login)
        ctrl.netease_auth_changed.connect(
            lambda ok: self.sidebar.set_platform_status("netease", ok)
        )
```

---

## 数据流总览

```
用户输入关键词
  → SearchPage debounce 400ms
  → ctrl.search(query)
  → NeteaseClient.search()
  → search_results_ready → TrackListWidget.set_tracks()

用户点击曲目
  → ctrl.play_track(track)
  → player.load(track) → state_changed → NowPlayingBar.update_state()
  → client.get_stream_url()
  → vlc.play(url)
  → player.on_load_success() → state=playing → NowPlayingBar 播放图标

VLC 播放中
  → vlc.position_changed → player.update_position → position_changed → NowPlayingBar.update_position()

用户点击暂停
  → NowPlayingBar.play_pause_clicked → ctrl.toggle_play_pause()
  → vlc.pause() + player.pause() → state_changed → NowPlayingBar 图标切换

VLC 播放完毕
  → vlc.end_reached → ctrl.play_next() → (队列下一首或停止)
```

---

## 测试策略

| 测试文件 | 内容 |
|----------|------|
| `tests/test_app_controller.py` | mock NeteaseClient + VLCBackend，验证 play_track 流程、toggle_play_pause、play_next |
| `tests/test_track_list.py` | set_tracks / track_selected 信号 |
| `tests/test_search_page.py` | 防抖逻辑（mock QTimer）、未登录时触发 ensure_netease_auth |

现有 77 个测试不变。
