# Next Track Prefetch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在当前曲目剩余时间低于平台阈值时，后台预取下一首流 URL 及 autoplay 推荐，消除切歌黑屏。

**Architecture:** `_on_position_changed`（已存在）中加入触发逻辑，调用新增的 `_prefetch_next()` 协程。`play_track()` 中优先使用 `track.stream_url` 缓存跳过网络请求；`play_next()` 优先使用预取的 `_prefetched_autoplay`。预取失败静默降级，不影响主流程。

**Tech Stack:** Python 3.11+, PyQt6, asyncio (qasync), pytest-asyncio

---

## File Map

| 文件 | 操作 |
|------|------|
| `core/queue.py` | 新增 `peek_next()` |
| `core/app_controller.py` | 新增常量、预取状态、`_prefetch_next()`、`_prefetch_stream_url()`；修改 `__init__`、`_on_position_changed`、`play_track()`、`play_next()` |
| `tests/test_queue.py` | 新增 `peek_next` 测试 |
| `tests/test_app_controller.py` | 新增预取逻辑测试 |

---

## Task 1: PlayQueue.peek_next()

**Files:**
- Modify: `core/queue.py`
- Test: `tests/test_queue.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_queue.py` 末尾追加：

```python
def test_peek_next_returns_next_without_advancing():
    q = PlayQueue()
    tracks = [_t("1"), _t("2"), _t("3")]
    q.set_tracks(tracks, start_index=0)
    peeked = q.peek_next()
    assert peeked == tracks[1]
    assert q.current_track == tracks[0]   # index 未推进
    assert q.current_index == 0


def test_peek_next_at_end_no_repeat_returns_none():
    q = PlayQueue()
    q.set_tracks([_t("1")], start_index=0)
    assert q.peek_next(repeat_mode="none") is None


def test_peek_next_repeat_all_returns_first():
    q = PlayQueue()
    tracks = [_t("1"), _t("2")]
    q.set_tracks(tracks, start_index=1)
    assert q.peek_next(repeat_mode="all") == tracks[0]


def test_peek_next_repeat_one_returns_current():
    q = PlayQueue()
    tracks = [_t("1"), _t("2")]
    q.set_tracks(tracks, start_index=0)
    assert q.peek_next(repeat_mode="one") == tracks[0]


def test_peek_next_empty_queue_returns_none():
    q = PlayQueue()
    assert q.peek_next() is None
```

- [ ] **Step 2: 运行，确认失败**

```bash
python3 -m pytest tests/test_queue.py::test_peek_next_returns_next_without_advancing -v
```

预期：`AttributeError: 'PlayQueue' object has no attribute 'peek_next'`

- [ ] **Step 3: 实现 `peek_next()`**

在 `core/queue.py` 的 `next()` 方法后面（第 46 行之后）插入：

```python
    def peek_next(self, repeat_mode: str = "none") -> Track | None:
        """Return the next track without advancing the index."""
        if not self._tracks:
            return None
        if repeat_mode == "one":
            return self.current_track
        nxt = self._index + 1
        if nxt >= len(self._tracks):
            if repeat_mode == "all":
                return self._tracks[0]
            return None
        return self._tracks[nxt]
```

- [ ] **Step 4: 运行，确认全部通过**

```bash
python3 -m pytest tests/test_queue.py -v
```

预期：所有测试 PASS

- [ ] **Step 5: Commit**

```bash
git add core/queue.py tests/test_queue.py
git commit -m "feat(queue): add peek_next() to inspect next track without advancing"
```

---

## Task 2: 预取常量和状态初始化

**Files:**
- Modify: `core/app_controller.py:27-29`（常量区域）、`core/app_controller.py:94-120`（`__init__`）

- [ ] **Step 1: 写失败测试**

在 `tests/test_app_controller.py` 末尾追加：

```python
def test_prefetch_state_initialized(ctrl):
    assert ctrl._prefetch_task is None
    assert ctrl._prefetch_done is False
    assert ctrl._prefetched_next_track is None
    assert ctrl._prefetched_autoplay is None
```

- [ ] **Step 2: 运行，确认失败**

```bash
python3 -m pytest tests/test_app_controller.py::test_prefetch_state_initialized -v
```

预期：`AttributeError: 'AppController' object has no attribute '_prefetch_task'`

- [ ] **Step 3: 添加常量**

在 `core/app_controller.py` 顶部常量区（`_HOME_CACHE_TTL` 等附近，约第 27 行）添加：

```python
_PREFETCH_THRESHOLD: dict[str, int] = {
    "netease": 5_000,    # 5s  — get_stream_url ≈ 200-800ms
    "ytmusic": 25_000,   # 25s — yt-dlp 解析 ≈ 8-15s
    "spotify": 20_000,   # 20s — 提前准备 autoplay；librespot 下载超出本次范围
}
_PREFETCH_FALLBACK_MS = 30_000   # 无时长时，播放满 30s 后触发
```

- [ ] **Step 4: 初始化预取状态**

在 `AppController.__init__` 的 `self.last_playlist_error = ""` 行（约第 117 行）后添加：

```python
        self._prefetch_task: asyncio.Task | None = None
        self._prefetch_done: bool = False
        self._prefetched_next_track: Track | None = None
        self._prefetched_autoplay: list[Track] | None = None
```

- [ ] **Step 5: 运行，确认通过**

```bash
python3 -m pytest tests/test_app_controller.py::test_prefetch_state_initialized -v
```

预期：PASS

- [ ] **Step 6: Commit**

```bash
git add core/app_controller.py
git commit -m "feat(prefetch): add prefetch constants and state fields to AppController"
```

---

## Task 3: `_on_position_changed` 触发预取

**Files:**
- Modify: `core/app_controller.py:625-631`（`_on_position_changed`）
- Test: `tests/test_app_controller.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_app_controller.py` 末尾追加：

```python
async def test_prefetch_triggered_near_end_of_track(ctrl):
    """_on_position_changed 在剩余时间 ≤ 阈值时启动 _prefetch_task。"""
    mock_client = MagicMock()
    mock_client.get_stream_url = AsyncMock(return_value="https://cdn.example.com/a.mp3")
    ctrl._netease_client = mock_client

    t1 = _track(id="t1", duration_ms=180_000)
    t2 = _track(id="t2", duration_ms=180_000)
    ctrl._queue.set_tracks([t1, t2], 0)
    await ctrl.play_track(t1)

    # 剩余 3s（< netease 阈值 5s），且 prefetch_done=False
    ctrl._on_position_changed(177_000)   # 180000 - 177000 = 3000ms 剩余

    assert ctrl._prefetch_task is not None


async def test_prefetch_not_triggered_when_done(ctrl):
    """_prefetch_done=True 时不重复触发。"""
    mock_client = MagicMock()
    mock_client.get_stream_url = AsyncMock(return_value="https://cdn.example.com/a.mp3")
    ctrl._netease_client = mock_client

    t1 = _track(id="t1", duration_ms=180_000)
    t2 = _track(id="t2", duration_ms=180_000)
    ctrl._queue.set_tracks([t1, t2], 0)
    await ctrl.play_track(t1)

    ctrl._prefetch_done = True
    ctrl._on_position_changed(177_000)

    assert ctrl._prefetch_task is None


async def test_prefetch_not_triggered_too_early(ctrl):
    """剩余时间 > 阈值时不触发。"""
    mock_client = MagicMock()
    mock_client.get_stream_url = AsyncMock(return_value="https://cdn.example.com/a.mp3")
    ctrl._netease_client = mock_client

    t1 = _track(id="t1", duration_ms=180_000)
    ctrl._queue.set_tracks([t1, _track(id="t2")], 0)
    await ctrl.play_track(t1)

    ctrl._on_position_changed(10_000)   # 170s 剩余，远 > 5s 阈值

    assert ctrl._prefetch_task is None
```

- [ ] **Step 2: 运行，确认失败**

```bash
python3 -m pytest tests/test_app_controller.py::test_prefetch_triggered_near_end_of_track tests/test_app_controller.py::test_prefetch_not_triggered_when_done tests/test_app_controller.py::test_prefetch_not_triggered_too_early -v
```

预期：3 个 FAIL

- [ ] **Step 3: 修改 `_on_position_changed`**

将 `core/app_controller.py` 中的 `_on_position_changed` 方法（约第 625-631 行）完整替换为：

```python
    def _on_position_changed(self, position_ms: int) -> None:
        state = self._player.state
        self._macos_media.update(
            state.current_track,
            position_ms,
            state.status == "playing",
        )
        if (
            state.status == "playing"
            and state.current_track is not None
            and not self._prefetch_done
            and self._prefetch_task is None
        ):
            platform = state.current_track.platform
            threshold = _PREFETCH_THRESHOLD.get(platform, _PREFETCH_FALLBACK_MS)
            duration = state.duration_ms
            if duration > 0:
                should = (duration - position_ms) <= threshold
            else:
                should = position_ms >= _PREFETCH_FALLBACK_MS
            if should:
                self._prefetch_done = True
                self._prefetch_task = asyncio.ensure_future(self._prefetch_next())
```

- [ ] **Step 4: 运行，确认通过**

```bash
python3 -m pytest tests/test_app_controller.py::test_prefetch_triggered_near_end_of_track tests/test_app_controller.py::test_prefetch_not_triggered_when_done tests/test_app_controller.py::test_prefetch_not_triggered_too_early -v
```

预期：3 个 PASS

- [ ] **Step 5: Commit**

```bash
git add core/app_controller.py tests/test_app_controller.py
git commit -m "feat(prefetch): trigger prefetch in _on_position_changed near track end"
```

---

## Task 4: `_prefetch_next()` 和 `_prefetch_stream_url()`

**Files:**
- Modify: `core/app_controller.py`（在 `_on_position_changed` 之后插入两个新方法）
- Test: `tests/test_app_controller.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_app_controller.py` 末尾追加：

```python
async def test_prefetch_next_caches_stream_url(ctrl):
    """_prefetch_next 把下一首的 stream_url 写入 track 对象。"""
    mock_client = MagicMock()
    mock_client.get_stream_url = AsyncMock(
        side_effect=["https://cdn.example.com/t1.mp3",
                     "https://cdn.example.com/t2.mp3"]
    )
    ctrl._netease_client = mock_client

    t1 = _track(id="t1")
    t2 = _track(id="t2")
    ctrl._queue.set_tracks([t1, t2], 0)
    await ctrl.play_track(t1)

    await ctrl._prefetch_next()

    assert t2.stream_url == "https://cdn.example.com/t2.mp3"


async def test_prefetch_next_skips_if_url_already_cached(ctrl):
    """下一首 stream_url 已有时不重复请求。"""
    mock_client = MagicMock()
    mock_client.get_stream_url = AsyncMock(return_value="https://cdn.example.com/t1.mp3")
    ctrl._netease_client = mock_client

    t1 = _track(id="t1")
    t2 = _track(id="t2", stream_url="https://cached.example.com/t2.mp3")
    ctrl._queue.set_tracks([t1, t2], 0)
    await ctrl.play_track(t1)

    await ctrl._prefetch_next()

    # get_stream_url 只被 play_track 调用了一次（t1），没有再次调用
    mock_client.get_stream_url.assert_awaited_once()


async def test_prefetch_next_fetches_autoplay_when_queue_empty(ctrl):
    """队列只剩当前曲时，预取推荐列表并缓存 stream_url。"""
    t_current = _track(id="c1")
    t_rec = _track(id="r1")

    mock_client = MagicMock()
    mock_client.get_stream_url = AsyncMock(
        side_effect=["https://cdn.example.com/c1.mp3",
                     "https://cdn.example.com/r1.mp3"]
    )
    mock_client.get_recommendations = AsyncMock(return_value=[t_rec])
    ctrl._netease_client = mock_client

    ctrl._queue.set_tracks([t_current], 0)
    await ctrl.play_track(t_current)

    await ctrl._prefetch_next()

    assert ctrl._prefetched_autoplay == [t_rec]
    assert t_rec.stream_url == "https://cdn.example.com/r1.mp3"


async def test_prefetch_next_silently_handles_error(ctrl):
    """预取失败时不抛异常。"""
    mock_client = MagicMock()
    mock_client.get_stream_url = AsyncMock(
        side_effect=["https://cdn.example.com/t1.mp3", RuntimeError("timeout")]
    )
    ctrl._netease_client = mock_client

    t1 = _track(id="t1")
    t2 = _track(id="t2")
    ctrl._queue.set_tracks([t1, t2], 0)
    await ctrl.play_track(t1)

    await ctrl._prefetch_next()   # should not raise

    assert t2.stream_url is None
    assert ctrl._prefetch_task is None
```

- [ ] **Step 2: 运行，确认失败**

```bash
python3 -m pytest tests/test_app_controller.py::test_prefetch_next_caches_stream_url tests/test_app_controller.py::test_prefetch_next_fetches_autoplay_when_queue_empty -v
```

预期：`AttributeError: 'AppController' object has no attribute '_prefetch_next'`

- [ ] **Step 3: 实现两个方法**

在 `core/app_controller.py` 中 `_on_position_changed` 方法之后插入：

```python
    async def _prefetch_next(self) -> None:
        try:
            state = self._player.state
            if state.current_track is None:
                return
            repeat_mode = state.repeat_mode
            next_track = self._queue.peek_next(repeat_mode)
            if next_track is not None:
                await self._prefetch_stream_url(next_track)
                self._prefetched_next_track = next_track
            else:
                # 队列将空 → 预取推荐
                client = self._get_platform_client(state.current_track.platform)
                if client is None:
                    return
                recs = await client.get_recommendations(state.current_track)
                # 过滤掉当前曲目，与 _autoplay 保持一致
                recs = [t for t in recs if t.id != state.current_track.id]
                if recs:
                    self._prefetched_autoplay = recs
                    await self._prefetch_stream_url(recs[0])
        except Exception:
            pass
        finally:
            self._prefetch_task = None

    async def _prefetch_stream_url(self, track: Track) -> None:
        if track.stream_url:
            return  # 已有缓存，跳过
        if track.platform == "spotify":
            return  # get_stream_url 即时返回；librespot 下载超出本次范围
        client = self._get_platform_client(track.platform)
        if client is None:
            return
        url = await client.get_stream_url(track)
        if url:
            track.stream_url = url
```

- [ ] **Step 4: 运行，确认通过**

```bash
python3 -m pytest tests/test_app_controller.py::test_prefetch_next_caches_stream_url tests/test_app_controller.py::test_prefetch_next_skips_if_url_already_cached tests/test_app_controller.py::test_prefetch_next_fetches_autoplay_when_queue_empty tests/test_app_controller.py::test_prefetch_next_silently_handles_error -v
```

预期：4 个 PASS

- [ ] **Step 5: Commit**

```bash
git add core/app_controller.py tests/test_app_controller.py
git commit -m "feat(prefetch): implement _prefetch_next and _prefetch_stream_url"
```

---

## Task 5: `play_track()` 使用缓存并重置状态

**Files:**
- Modify: `core/app_controller.py:459-488`（`play_track`）
- Test: `tests/test_app_controller.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_app_controller.py` 末尾追加：

```python
async def test_play_track_uses_cached_stream_url(ctrl, fake_vlc):
    """play_track 命中 stream_url 缓存时不调用 get_stream_url。"""
    mock_client = MagicMock()
    mock_client.get_stream_url = AsyncMock(return_value="https://cdn.example.com/fresh.mp3")
    ctrl._netease_client = mock_client

    t = _track(stream_url="https://cdn.example.com/cached.mp3")
    await ctrl.play_track(t)

    mock_client.get_stream_url.assert_not_awaited()
    assert fake_vlc._last_url == "https://cdn.example.com/cached.mp3"


async def test_play_track_resets_prefetch_state(ctrl):
    """play_track 开始时清除所有预取状态。"""
    mock_client = MagicMock()
    mock_client.get_stream_url = AsyncMock(return_value="https://cdn.example.com/a.mp3")
    ctrl._netease_client = mock_client

    # 模拟有残留预取状态
    ctrl._prefetch_done = True
    ctrl._prefetched_next_track = _track(id="stale")
    ctrl._prefetched_autoplay = [_track(id="stale2")]

    await ctrl.play_track(_track())

    assert ctrl._prefetch_done is False
    assert ctrl._prefetched_next_track is None
    assert ctrl._prefetched_autoplay is None
```

- [ ] **Step 2: 运行，确认失败**

```bash
python3 -m pytest tests/test_app_controller.py::test_play_track_uses_cached_stream_url tests/test_app_controller.py::test_play_track_resets_prefetch_state -v
```

预期：2 个 FAIL

- [ ] **Step 3: 修改 `play_track()`**

找到 `core/app_controller.py` 的 `play_track` 方法（约第 459 行），作如下两处修改：

**3a. 在 `self._player.load(track)` 之前插入状态重置：**

```python
        self._emit_queue_changed()
        # ── 重置预取状态，新曲目重新计算 ──────────────────────────────────────
        self._prefetch_done = False
        self._prefetched_next_track = None
        self._prefetched_autoplay = None
        if self._prefetch_task is not None:
            self._prefetch_task.cancel()
            self._prefetch_task = None
        # ─────────────────────────────────────────────────────────────────────
        self._player.load(track)
```

**3b. 将流 URL 获取改为优先使用缓存：**

```python
                # 修改前:
                url = await client.get_stream_url(track)
                # 修改后:
                url = track.stream_url or await client.get_stream_url(track)
```

- [ ] **Step 4: 运行，确认通过**

```bash
python3 -m pytest tests/test_app_controller.py::test_play_track_uses_cached_stream_url tests/test_app_controller.py::test_play_track_resets_prefetch_state -v
```

预期：2 个 PASS

- [ ] **Step 5: Commit**

```bash
git add core/app_controller.py tests/test_app_controller.py
git commit -m "feat(prefetch): use cached stream_url in play_track, reset state on new track"
```

---

## Task 6: `play_next()` 使用预取的 autoplay

**Files:**
- Modify: `core/app_controller.py:555-565`（`play_next`）
- Test: `tests/test_app_controller.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_app_controller.py` 末尾追加：

```python
async def test_play_next_uses_prefetched_autoplay(ctrl):
    """play_next 在队列空时使用预取的推荐列表，不重新请求。"""
    t_current = _track(id="c1")
    t_rec = _track(id="r1", stream_url="https://cdn.example.com/r1.mp3")

    mock_client = MagicMock()
    mock_client.get_stream_url = AsyncMock(return_value="https://cdn.example.com/c1.mp3")
    mock_client.get_recommendations = AsyncMock(return_value=[t_rec])
    ctrl._netease_client = mock_client

    ctrl._queue.set_tracks([t_current], 0)
    await ctrl.play_track(t_current)

    # 注入预取结果
    ctrl._prefetched_autoplay = [t_rec]

    await ctrl.play_next()

    # 不应再调用 get_recommendations
    mock_client.get_recommendations.assert_not_awaited()
    # 应该播放预取的推荐曲目
    assert ctrl._player.state.current_track == t_rec


async def test_play_next_falls_back_to_autoplay_if_no_prefetch(ctrl):
    """_prefetched_autoplay 为 None 时，走原有 _autoplay 路径。"""
    t_current = _track(id="c1")
    t_rec = _track(id="r1")

    mock_client = MagicMock()
    mock_client.get_stream_url = AsyncMock(
        side_effect=["https://cdn.example.com/c1.mp3",
                     "https://cdn.example.com/r1.mp3"]
    )
    mock_client.get_recommendations = AsyncMock(return_value=[t_rec])
    ctrl._netease_client = mock_client

    ctrl._queue.set_tracks([t_current], 0)
    await ctrl.play_track(t_current)
    # _prefetched_autoplay 是 None（未预取）

    await ctrl.play_next()

    mock_client.get_recommendations.assert_awaited_once()
```

- [ ] **Step 2: 运行，确认失败**

```bash
python3 -m pytest tests/test_app_controller.py::test_play_next_uses_prefetched_autoplay tests/test_app_controller.py::test_play_next_falls_back_to_autoplay_if_no_prefetch -v
```

预期：`test_play_next_uses_prefetched_autoplay` FAIL（当前走 `_autoplay` 路径）

- [ ] **Step 3: 修改 `play_next()`**

将 `core/app_controller.py` 的 `play_next` 方法完整替换为：

```python
    async def play_next(self) -> None:
        next_track = self._queue.next(self._player.state.repeat_mode)
        if next_track is not None:
            await self.play_track(next_track)
            return
        # 队列已空：优先使用预取的推荐列表
        if self._prefetched_autoplay:
            recs = self._prefetched_autoplay
            self._prefetched_autoplay = None
            seed = self._player.state.current_track
            self._vlc.stop()
            self._librespot.stop()
            self._player.stop()
            self._queue.set_tracks(recs, 0)
            self._emit_queue_changed()
            await self.play_track(recs[0])
        else:
            seed = self._player.state.current_track
            self._vlc.stop()
            self._librespot.stop()
            self._player.stop()
            if seed:
                asyncio.ensure_future(self._autoplay(seed))
```

- [ ] **Step 4: 运行，确认通过**

```bash
python3 -m pytest tests/test_app_controller.py::test_play_next_uses_prefetched_autoplay tests/test_app_controller.py::test_play_next_falls_back_to_autoplay_if_no_prefetch -v
```

预期：2 个 PASS

- [ ] **Step 5: 全量测试，确认无回归**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -20
```

预期：所有原有测试 PASS，无新失败

- [ ] **Step 6: Commit**

```bash
git add core/app_controller.py tests/test_app_controller.py
git commit -m "feat(prefetch): use prefetched autoplay in play_next to skip recommendations fetch"
```

---

## 自检（Self-Review）

**Spec coverage:**
- ✅ 进度触发 → Task 3 `_on_position_changed`
- ✅ 平台阈值（netease 5s / ytmusic 25s / spotify 20s）→ Task 2 `_PREFETCH_THRESHOLD`
- ✅ 退化条件（duration=0 时 30s）→ Task 3 Step 3
- ✅ peek_next 不推进 index → Task 1
- ✅ 预取队列下一首 stream_url → Task 4
- ✅ 预取 autoplay 推荐 → Task 4
- ✅ play_track 使用缓存 URL → Task 5
- ✅ play_track 重置所有预取状态 → Task 5（含 `_prefetched_autoplay`）
- ✅ play_next 使用预取推荐 → Task 6
- ✅ 失败静默降级 → Task 4（`except Exception: pass`）
- ✅ 单曲循环/全部循环 → peek_next repeat_mode 参数（Task 1 测试覆盖）
- ✅ 用户手动跳歌取消旧 task → Task 5（`_prefetch_task.cancel()`）

**Type consistency:**
- `peek_next(repeat_mode: str = "none") -> Track | None` — Task 1 定义，Task 4 调用 ✓
- `_prefetch_next() -> None` — Task 4 定义，Task 3 调用 ✓
- `_prefetch_stream_url(track: Track) -> None` — Task 4 定义，Task 4 内调用 ✓
- `_prefetched_autoplay: list[Track] | None` — Task 2 定义，Task 4/5/6 使用 ✓

**Placeholder scan:** 无 TBD/TODO
