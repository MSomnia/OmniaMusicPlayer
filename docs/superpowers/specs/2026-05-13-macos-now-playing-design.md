# Design: macOS Now Playing Integration

**Date**: 2026-05-13
**Branch**: feat/phase4-youtube-music
**Scope**: 激活已有 `MacOSMediaHandler`，修复 update 频率问题，显式设置 `playbackState`

---

## Problem

`core/macos_media.py` 中的 `MacOSMediaHandler` 已完整实现，但：
1. `pyobjc-framework-MediaPlayer` / `pyobjc-framework-AppKit` 未列入依赖，导致 `_AVAILABLE = False`，整个 handler 是空操作
2. `update()` 每 250ms 被调用一次，每次都重建完整 info dict（含封面 artwork），资源浪费
3. 未显式设置 `MPNowPlayingInfoCenter.playbackState`（macOS 10.13+），某些版本下 Now Playing 控件不出现

## Solution Overview

1. 在 `requirements.txt` 添加 macOS 平台条件依赖
2. 将 `MacOSMediaHandler.update()` 拆为 `update_full()`（track/state 变化时）和 `update_position()`（position tick 时）
3. 在两个方法中都显式设置 `playbackState`
4. `AppController` 相应调整调用方式

---

## Dependency Changes

**File**: `requirements.txt`

追加：
```
pyobjc-framework-MediaPlayer>=10.0; sys_platform == "darwin"
pyobjc-framework-AppKit>=10.0; sys_platform == "darwin"
```

`; sys_platform == "darwin"` 确保非 macOS 环境（CI、Linux）不安装。

---

## MacOSMediaHandler Changes

**File**: `core/macos_media.py`

### 新增内部状态

```python
self._current_track: Track | None = None
```

由 `update_full()` 维护，`update_position()` 用来判断是否有活动曲目。

### 替换 `update()` 为两个方法

#### `update_full(track, position_ms, is_playing)` — 完整更新

触发场景：track 变化、play/pause 状态变化、seek 完成。

更新内容：
- 完整 `MPNowPlayingInfo` dict（title、artist、album、duration、artwork、elapsed time、rate）
- 显式 `setPlaybackState_(...)`

```python
def update_full(self, track: "Track | None", position_ms: int, is_playing: bool) -> None:
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
```

#### `update_position(position_ms, is_playing)` — 轻量位置更新

触发场景：每 250ms position tick。

更新内容：
- 仅 `ElapsedPlaybackTime` + `PlaybackRate`
- 显式 `setPlaybackState_(...)`

```python
def update_position(self, position_ms: int, is_playing: bool) -> None:
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
```

#### `_set_playback_state(is_playing)` — 新增辅助方法

```python
def _set_playback_state(self, is_playing: bool) -> None:
    try:
        from MediaPlayer import (
            MPNowPlayingInfoCenter,
            MPNowPlayingPlaybackStatePlaying,
            MPNowPlayingPlaybackStatePaused,
        )
        state = MPNowPlayingPlaybackStatePlaying if is_playing else MPNowPlayingPlaybackStatePaused
        MPNowPlayingInfoCenter.defaultCenter().setPlaybackState_(state)
    except Exception as exc:
        logger.debug("playbackState update failed: %s", exc)
```

#### 删除旧 `update()` 方法

旧的 `update(track, position_ms, is_playing)` 方法完全删除。

---

## AppController Changes

**File**: `core/app_controller.py`

### `_on_player_state_changed` — 调用 `update_full`

```python
def _on_player_state_changed(self, state) -> None:
    self._macos_media.update_full(
        state.current_track,
        state.position_ms,
        state.status == "playing",
    )
```

### `_on_position_changed` — 调用 `update_position`

```python
def _on_position_changed(self, position_ms: int) -> None:
    state = self._player.state
    self._macos_media.update_position(position_ms, state.status == "playing")
    # ... 其余预取逻辑不变
```

---

## Error Handling

- `_AVAILABLE = False` 时两个方法直接 return（非 macOS 或 PyObjC 未安装）
- 所有 PyObjC 调用包在 `try/except Exception` 内，只 log `debug` 级别
- `MPNowPlayingPlaybackStatePlaying/Paused` 常量可能在旧版 PyObjC 不存在，`_set_playback_state` 的 `except` 静默处理

---

## Files Changed

| 文件 | 变更 |
|------|------|
| `requirements.txt` | 添加两个 macOS 平台依赖 |
| `core/macos_media.py` | 拆分 `update()` → `update_full()` + `update_position()` + `_set_playback_state()`；新增 `_current_track` 状态 |
| `core/app_controller.py` | `_on_player_state_changed` → `update_full`；`_on_position_changed` → `update_position` |

## Out of Scope

- 歌词显示在 Now Playing（macOS 不支持）
- 音量控制同步到系统媒体控制（需要额外 `MPRemoteCommandCenter` 配置，不在本次范围内）
- Windows/Linux 媒体集成
