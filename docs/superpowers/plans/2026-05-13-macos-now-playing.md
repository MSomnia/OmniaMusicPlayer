# macOS Now Playing Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 安装 PyObjC 依赖并修复 `MacOSMediaHandler`，使 app 正确出现在 macOS Now Playing 控件中，并以高效的双路 update 减少系统调用。

**Architecture:** 在 `requirements.txt` 加 macOS 条件依赖；将 `MacOSMediaHandler.update()` 拆为 `update_full()`（track/state 变化时完整更新 + 显式 `playbackState`）和 `update_position()`（高频 tick 只更新时间戳）；`AppController` 两个 handler 分别调用对应方法。

**Tech Stack:** Python 3.11+, PyObjC (`pyobjc-framework-MediaPlayer`, `pyobjc-framework-AppKit`), pytest

---

## File Map

| 文件 | 操作 |
|------|------|
| `requirements.txt` | 添加两个 macOS 条件依赖 |
| `core/macos_media.py` | 添加 `_current_track`；新增 `update_full()`、`update_position()`、`_set_playback_state()`；删除旧 `update()` |
| `core/app_controller.py` | `_on_player_state_changed` → `update_full`；`_on_position_changed` → `update_position` |
| `tests/test_macos_media.py` | 新建：MacOSMediaHandler 单元测试 |
| `tests/test_app_controller.py` | 追加：AppController 调用路由测试 |

---

## Task 1: 添加 PyObjC 依赖

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: 追加依赖行**

打开 `requirements.txt`，在最后一个非 dev 依赖（`Pillow>=10.3.0`）后追加：

```
pyobjc-framework-MediaPlayer>=10.0; sys_platform == "darwin"
pyobjc-framework-AppKit>=10.0; sys_platform == "darwin"
```

完整文件末尾区域应如下：

```
Pillow>=10.3.0
pyobjc-framework-MediaPlayer>=10.0; sys_platform == "darwin"
pyobjc-framework-AppKit>=10.0; sys_platform == "darwin"

# Dev
pytest>=8.2.0
pytest-asyncio>=0.23.0
pytest-qt>=4.4.0
```

- [ ] **Step 2: 安装依赖**

```bash
pip3 install "pyobjc-framework-MediaPlayer>=10.0" "pyobjc-framework-AppKit>=10.0"
```

预期：安装成功，无错误。

- [ ] **Step 3: 验证导入**

```bash
python3 -c "import MediaPlayer; import AppKit; print('OK')"
```

预期输出：`OK`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat(deps): add pyobjc MediaPlayer and AppKit for macOS Now Playing"
```

---

## Task 2: 重构 MacOSMediaHandler

**Files:**
- Modify: `core/macos_media.py`
- Create: `tests/test_macos_media.py`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_macos_media.py`：

```python
import sys
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


def _make_handler(ctrl=None):
    from core.macos_media import MacOSMediaHandler
    return MacOSMediaHandler(ctrl or MagicMock())


def _track():
    from core.models import Track
    return Track(
        id="t1", platform="netease", title="Song", artist="Artist",
        artists=["Artist"], album="Album", album_cover_url="",
        duration_ms=180_000,
    )


# ── 无 PyObjC 时（_AVAILABLE=False）：全部静默 ─────────────────────────────────

def test_update_full_noop_when_unavailable():
    with patch("core.macos_media._AVAILABLE", False):
        h = _make_handler()
        h.update_full(_track(), 5000, True)   # must not raise
        assert h._current_track is None       # not set when unavailable


def test_update_position_noop_when_unavailable():
    with patch("core.macos_media._AVAILABLE", False):
        h = _make_handler()
        h.update_position(5000, True)   # must not raise


# ── _current_track 状态 ──────────────────────────────────────────────────────

def test_update_full_sets_current_track():
    t = _track()
    with patch("core.macos_media._AVAILABLE", True), \
         patch.object(_make_handler().__class__, "_update_now_playing"), \
         patch.object(_make_handler().__class__, "_set_playback_state"):
        h = _make_handler()
        with patch.object(h, "_update_now_playing"), \
             patch.object(h, "_set_playback_state"):
            h.update_full(t, 5000, True)
    # Re-test cleanly
    with patch("core.macos_media._AVAILABLE", True):
        h = _make_handler()
        with patch.object(h, "_update_now_playing"), \
             patch.object(h, "_set_playback_state"):
            h.update_full(t, 5000, True)
        assert h._current_track == t


def test_update_full_clears_current_track_on_none():
    with patch("core.macos_media._AVAILABLE", True):
        h = _make_handler()
        with patch.object(h, "_clear"):
            h.update_full(None, 0, False)
        assert h._current_track is None


def test_update_position_noop_when_no_track():
    """_current_track が None の時は位置更新しない。"""
    with patch("core.macos_media._AVAILABLE", True):
        h = _make_handler()
        # _current_track is None by default
        with patch.object(h, "_set_playback_state") as mock_state:
            h.update_position(5000, True)
            mock_state.assert_not_called()


# ── update_full が正しいメソッドを呼ぶ ───────────────────────────────────────

def test_update_full_calls_update_now_playing_and_set_state():
    t = _track()
    with patch("core.macos_media._AVAILABLE", True):
        h = _make_handler()
        with patch.object(h, "_update_now_playing") as mock_upd, \
             patch.object(h, "_set_playback_state") as mock_state:
            h.update_full(t, 3000, True)
        mock_upd.assert_called_once_with(t, 3000, True)
        mock_state.assert_called_once_with(True)


def test_update_full_calls_clear_when_track_is_none():
    with patch("core.macos_media._AVAILABLE", True):
        h = _make_handler()
        with patch.object(h, "_clear") as mock_clear:
            h.update_full(None, 0, False)
        mock_clear.assert_called_once()


# ── update_position が位置更新メソッドを呼ぶ ─────────────────────────────────

def test_update_position_calls_set_playback_state_when_track_set():
    t = _track()
    with patch("core.macos_media._AVAILABLE", True):
        h = _make_handler()
        h._current_track = t   # 直接注入 current_track
        mock_center = MagicMock()
        mock_center.nowPlayingInfo.return_value = {}
        mock_mp = MagicMock()
        mock_mp.MPNowPlayingInfoCenter.defaultCenter.return_value = mock_center
        mock_mp.MPNowPlayingInfoPropertyElapsedPlaybackTime = "elapsed"
        mock_mp.MPNowPlayingInfoPropertyPlaybackRate = "rate"
        with patch.dict("sys.modules", {"MediaPlayer": mock_mp}), \
             patch.object(h, "_set_playback_state") as mock_state:
            h.update_position(9000, False)
        mock_state.assert_called_once_with(False)
```

- [ ] **Step 2: 运行，确认失败**

```bash
python3 -m pytest tests/test_macos_media.py -v 2>&1 | head -30
```

预期：大多数测试 FAIL（`MacOSMediaHandler` 没有 `update_full`、`update_position`、`_current_track`）

- [ ] **Step 3: 重写 `core/macos_media.py`**

用以下内容**完整替换** `core/macos_media.py`：

```python
from __future__ import annotations
import asyncio
import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import Track

logger = logging.getLogger(__name__)

_AVAILABLE = False
if sys.platform == "darwin":
    try:
        import MediaPlayer  # noqa: F401
        _AVAILABLE = True
    except ImportError:
        logger.debug("PyObjC MediaPlayer framework not available — lock screen info disabled")


class MacOSMediaHandler:
    """Updates MPNowPlayingInfoCenter and registers MPRemoteCommandCenter handlers.

    Gracefully degrades when PyObjC is not installed.
    Two update paths:
      update_full()     — on track/state change: full info dict + explicit playbackState
      update_position() — on 250ms tick: only elapsed time + rate + playbackState
    """

    def __init__(self, ctrl) -> None:
        self._ctrl = ctrl
        self._cover_data: bytes | None = None
        self._current_track: "Track | None" = None
        if _AVAILABLE:
            self._register_commands()

    # ── remote command registration ───────────────────────────────────────────

    def _register_commands(self) -> None:
        try:
            from MediaPlayer import (
                MPRemoteCommandCenter,
                MPRemoteCommandHandlerStatusSuccess,
            )
            cc = MPRemoteCommandCenter.sharedCommandCenter()

            def _play(event):
                self._ctrl.toggle_play_pause()
                return MPRemoteCommandHandlerStatusSuccess

            def _pause(event):
                self._ctrl.toggle_play_pause()
                return MPRemoteCommandHandlerStatusSuccess

            def _toggle(event):
                self._ctrl.toggle_play_pause()
                return MPRemoteCommandHandlerStatusSuccess

            def _next(event):
                asyncio.ensure_future(self._ctrl.play_next())
                return MPRemoteCommandHandlerStatusSuccess

            def _prev(event):
                asyncio.ensure_future(self._ctrl.play_prev())
                return MPRemoteCommandHandlerStatusSuccess

            def _seek(event):
                pos_s = event.positionTime()
                self._ctrl.seek(int(pos_s * 1000))
                return MPRemoteCommandHandlerStatusSuccess

            cc.playCommand().addTargetWithHandler_(_play)
            cc.pauseCommand().addTargetWithHandler_(_pause)
            cc.togglePlayPauseCommand().addTargetWithHandler_(_toggle)
            cc.nextTrackCommand().addTargetWithHandler_(_next)
            cc.previousTrackCommand().addTargetWithHandler_(_prev)
            cc.changePlaybackPositionCommand().addTargetWithHandler_(_seek)
            logger.debug("macOS remote command handlers registered")
        except Exception as exc:
            logger.warning("macOS media key registration failed: %s", exc)

    # ── public API ────────────────────────────────────────────────────────────

    def set_cover_data(self, data: bytes) -> None:
        self._cover_data = data

    def update_full(self, track: "Track | None", position_ms: int, is_playing: bool) -> None:
        """Full update: call on track change, play/pause, or seek."""
        if not _AVAILABLE:
            return
        self._current_track = track
        if track is None:
            self._clear()
            return
        try:
            self._update_now_playing(track, position_ms, is_playing)
            self._set_playback_state(is_playing)
        except Exception as exc:
            logger.debug("NowPlayingInfo full update failed: %s", exc)

    def update_position(self, position_ms: int, is_playing: bool) -> None:
        """Lightweight update: call on every position tick (250ms)."""
        if not _AVAILABLE or self._current_track is None:
            return
        try:
            from MediaPlayer import (
                MPNowPlayingInfoCenter,
                MPNowPlayingInfoPropertyElapsedPlaybackTime,
                MPNowPlayingInfoPropertyPlaybackRate,
            )
            center = MPNowPlayingInfoCenter.defaultCenter()
            info = dict(center.nowPlayingInfo() or {})
            info[MPNowPlayingInfoPropertyElapsedPlaybackTime] = position_ms / 1000.0
            info[MPNowPlayingInfoPropertyPlaybackRate] = 1.0 if is_playing else 0.0
            center.setNowPlayingInfo_(info)
            self._set_playback_state(is_playing)
        except Exception as exc:
            logger.debug("NowPlayingInfo position update failed: %s", exc)

    # ── internal ─────────────────────────────────────────────────────────────

    def _set_playback_state(self, is_playing: bool) -> None:
        try:
            from MediaPlayer import (
                MPNowPlayingInfoCenter,
                MPNowPlayingPlaybackStatePlaying,
                MPNowPlayingPlaybackStatePaused,
            )
            state = (
                MPNowPlayingPlaybackStatePlaying if is_playing
                else MPNowPlayingPlaybackStatePaused
            )
            MPNowPlayingInfoCenter.defaultCenter().setPlaybackState_(state)
        except Exception as exc:
            logger.debug("playbackState update failed: %s", exc)

    def _clear(self) -> None:
        try:
            from MediaPlayer import MPNowPlayingInfoCenter
            MPNowPlayingInfoCenter.defaultCenter().setNowPlayingInfo_(None)
        except Exception:
            pass

    def _update_now_playing(
        self, track: "Track", position_ms: int, is_playing: bool
    ) -> None:
        from MediaPlayer import (
            MPNowPlayingInfoCenter,
            MPMediaItemPropertyTitle,
            MPMediaItemPropertyArtist,
            MPMediaItemPropertyAlbumTitle,
            MPMediaItemPropertyPlaybackDuration,
            MPNowPlayingInfoPropertyElapsedPlaybackTime,
            MPNowPlayingInfoPropertyPlaybackRate,
        )

        info: dict = {
            MPMediaItemPropertyTitle: track.title,
            MPMediaItemPropertyArtist: track.artist,
            MPMediaItemPropertyAlbumTitle: track.album,
            MPMediaItemPropertyPlaybackDuration: track.duration_ms / 1000.0,
            MPNowPlayingInfoPropertyElapsedPlaybackTime: position_ms / 1000.0,
            MPNowPlayingInfoPropertyPlaybackRate: 1.0 if is_playing else 0.0,
        }

        if self._cover_data:
            artwork = self._make_artwork(self._cover_data)
            if artwork is not None:
                from MediaPlayer import MPMediaItemPropertyArtwork
                info[MPMediaItemPropertyArtwork] = artwork

        MPNowPlayingInfoCenter.defaultCenter().setNowPlayingInfo_(info)

    @staticmethod
    def _make_artwork(data: bytes):
        try:
            from AppKit import NSImage
            from MediaPlayer import MPMediaItemArtwork

            ns_image = NSImage.alloc().initWithData_(data)
            if ns_image is None:
                return None

            def _handler(size):
                return ns_image

            artwork = MPMediaItemArtwork.alloc().initWithBoundsSize_requestHandler_(
                (300.0, 300.0), _handler
            )
            return artwork
        except Exception as exc:
            logger.debug("MPMediaItemArtwork creation failed: %s", exc)
            return None
```

- [ ] **Step 4: 运行，确认测试通过**

```bash
python3 -m pytest tests/test_macos_media.py -v
```

预期：所有测试 PASS

- [ ] **Step 5: Commit**

```bash
git add core/macos_media.py tests/test_macos_media.py
git commit -m "feat(macos): split update() into update_full/update_position, add explicit playbackState"
```

---

## Task 3: 更新 AppController 调用点

**Files:**
- Modify: `core/app_controller.py:646-659`
- Test: `tests/test_app_controller.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_app_controller.py` 末尾追加：

```python
def test_on_player_state_changed_calls_update_full(ctrl):
    """_on_player_state_changed 应调用 update_full，不调用 update_position。"""
    from core.models import PlayerState
    ctrl._macos_media = MagicMock()
    state = PlayerState(
        status="playing",
        current_track=_track(),
        position_ms=30_000,
        duration_ms=180_000,
    )
    ctrl._on_player_state_changed(state)
    ctrl._macos_media.update_full.assert_called_once_with(
        state.current_track, state.position_ms, True
    )
    ctrl._macos_media.update_position.assert_not_called()


def test_on_position_changed_calls_update_position(ctrl):
    """_on_position_changed 应调用 update_position，不调用 update_full。"""
    ctrl._macos_media = MagicMock()
    # 注入一个正在播放的状态，但不走 play_track（避免 prefetch 干扰）
    from core.player import UnifiedPlayer
    from core.models import PlayerState
    ctrl._player._state = PlayerState(
        status="playing",
        current_track=_track(),
        position_ms=0,
        duration_ms=180_000,
    )
    ctrl._on_position_changed(45_000)
    ctrl._macos_media.update_position.assert_called_once_with(45_000, True)
    ctrl._macos_media.update_full.assert_not_called()
```

- [ ] **Step 2: 运行，确认失败**

```bash
python3 -m pytest tests/test_app_controller.py::test_on_player_state_changed_calls_update_full tests/test_app_controller.py::test_on_position_changed_calls_update_position -v
```

预期：2 个 FAIL（`update_full` / `update_position` 方法不存在或未被调用）

- [ ] **Step 3: 修改 `_on_player_state_changed`**

找到 `core/app_controller.py` 的 `_on_player_state_changed`（约第 646 行），完整替换为：

```python
    def _on_player_state_changed(self, state) -> None:
        self._macos_media.update_full(
            state.current_track,
            state.position_ms,
            state.status == "playing",
        )
```

- [ ] **Step 4: 修改 `_on_position_changed`**

找到 `_on_position_changed` 开头的 `self._macos_media.update(...)` 调用（约第 655-659 行），替换为：

```python
    def _on_position_changed(self, position_ms: int) -> None:
        state = self._player.state
        self._macos_media.update_position(position_ms, state.status == "playing")
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

- [ ] **Step 5: 运行新增测试，确认通过**

```bash
python3 -m pytest tests/test_app_controller.py::test_on_player_state_changed_calls_update_full tests/test_app_controller.py::test_on_position_changed_calls_update_position -v
```

预期：2 个 PASS

- [ ] **Step 6: 全量测试，确认无回归**

```bash
python3 -m pytest tests/ -q 2>&1 | tail -6
```

预期：所有测试 PASS，无新失败

- [ ] **Step 7: Commit**

```bash
git add core/app_controller.py tests/test_app_controller.py
git commit -m "feat(macos): route state changes to update_full, ticks to update_position"
```

---

## 自检（Self-Review）

**Spec coverage:**
- ✅ 添加 PyObjC 依赖（macOS 条件）→ Task 1
- ✅ `_current_track` 内部状态 → Task 2 Step 3（`__init__` + `update_full`）
- ✅ `update_full` 完整更新 + `_set_playback_state` → Task 2 Step 3
- ✅ `update_position` 只更新 elapsed time，no-op when `_current_track is None` → Task 2 Step 3
- ✅ `_set_playback_state` 显式 `setPlaybackState_` → Task 2 Step 3
- ✅ 旧 `update()` 删除 → Task 2 Step 3（新文件无 `update()` 方法）
- ✅ `_on_player_state_changed` → `update_full` → Task 3 Step 3
- ✅ `_on_position_changed` → `update_position` → Task 3 Step 4
- ✅ 错误处理（`try/except`）→ Task 2 Step 3 每个方法

**Type consistency:**
- `update_full(track, position_ms, is_playing)` — Task 2 实现 ↔ Task 3 调用 ✓
- `update_position(position_ms, is_playing)` — Task 2 实现 ↔ Task 3 调用 ✓
- `_set_playback_state(is_playing)` — Task 2 内部一致 ✓

**Placeholder scan:** 无 TBD/TODO
