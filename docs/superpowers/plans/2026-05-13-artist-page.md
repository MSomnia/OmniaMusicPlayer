# Artist Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现歌手详情页，显示歌手名称、头像和热门歌曲，支持从控制栏歌手名称和歌曲列表行中的歌手名称跳转进入。

**Architecture:** 新增 `ArtistPage`（`ui/pages/artist_page.py`）并将其加入 `MainWindow` 的 QStackedWidget 中；在 `NowPlayingBar` 与 `TrackRow` 上将歌手标签改为可点击控件并发出信号；三个平台客户端实现 `search_artist` / `get_artist_top_tracks`，`AppController` 协调异步加载并通过信号通知 UI。

**Tech Stack:** PyQt6, Python asyncio/qasync, httpx, ytmusicapi

---

## File Map

| 状态 | 文件 | 说明 |
|------|------|------|
| 修改 | `core/models.py` | 新增 `Artist` dataclass |
| 修改 | `platforms/base.py` | 新增 `search_artist` / `get_artist_top_tracks` 可选方法 |
| 修改 | `platforms/netease/client.py` | 实现歌手搜索 + 热门歌曲 |
| 修改 | `platforms/spotify/client.py` | 实现歌手搜索 + 热门歌曲（Web API） |
| 修改 | `platforms/ytmusic/client.py` | 实现歌手搜索 + 热门歌曲（ytmusicapi） |
| 修改 | `core/app_controller.py` | 新增 `artist_ready` / `artist_tracks_ready` 信号 + `load_artist` |
| 新建 | `ui/pages/artist_page.py` | 歌手详情页 |
| 修改 | `ui/components/now_playing_bar.py` | 歌手标签改为可点击，新增 `artist_clicked` 信号 |
| 修改 | `ui/components/track_row.py` | 歌手标签改为可点击，新增 `artist_clicked(Track)` 信号 |
| 修改 | `ui/app_window.py` | 注册 ArtistPage、接线导航信号 |
| 修改 | `tests/test_models.py` | 测试 Artist 模型 |
| 修改 | `tests/test_netease_client.py` | 测试 NeteaseClient 歌手方法 |
| 修改 | `tests/test_spotify_client.py` | 测试 SpotifyClient 歌手方法 |
| 修改 | `tests/test_ytmusic_client.py` | 测试 YTMusicClient 歌手方法 |

---

## Task 1: Artist 数据模型 + 基类方法

**Files:**
- Modify: `core/models.py`
- Modify: `platforms/base.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_models.py` 末尾追加：

```python
from core.models import Artist

def test_artist_fields():
    a = Artist(id="123", platform="netease", name="歌手A", image_url="https://example.com/pic.jpg")
    assert a.id == "123"
    assert a.platform == "netease"
    assert a.name == "歌手A"
    assert a.image_url == "https://example.com/pic.jpg"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/msomnia/Library/CloudStorage/OneDrive-Personal/1MSomnia/code/SomniaPlayer
python -m pytest tests/test_models.py::test_artist_fields -v
```

期望: `FAILED — ImportError: cannot import name 'Artist'`

- [ ] **Step 3: 在 `core/models.py` 的 `Album` dataclass 之后添加 `Artist`**

```python
@dataclass
class Artist:
    id: str
    platform: str
    name: str
    image_url: str
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_models.py::test_artist_fields -v
```

期望: `PASSED`

- [ ] **Step 5: 在 `platforms/base.py` 添加可选方法**

在 `get_album_tracks` 之后追加：

```python
from core.models import Track, Playlist, Album, LyricLine, Artist

async def search_artist(self, name: str) -> "Artist | None":
    """Return best matching Artist for name, or None if unsupported."""
    return None

async def get_artist_top_tracks(self, artist_id: str, limit: int = 30) -> list[Track]:
    """Return top tracks for artist_id."""
    return []
```

注意：`base.py` 第 3 行的 import 需要加入 `Artist`：
```python
from core.models import Track, Playlist, Album, LyricLine, Artist
```

- [ ] **Step 6: 提交**

```bash
git add core/models.py platforms/base.py tests/test_models.py
git commit -m "feat(artist): add Artist model and base platform stubs"
```

---

## Task 2: NeteaseClient 歌手方法

**Files:**
- Modify: `platforms/netease/client.py`
- Modify: `tests/test_netease_client.py`

网易云音乐 API：
- 搜索歌手：POST `/weapi/cloudsearch/pc`，`type=100`
- 热门歌曲：POST `/weapi/v1/artist/{artist_id}`，返回 `hotSongs`

- [ ] **Step 1: 写失败测试**

在 `tests/test_netease_client.py` 末尾追加：

```python
from core.models import Artist

ARTIST_SEARCH_RESPONSE = {
    "result": {
        "artists": [
            {"id": 6452, "name": "周杰伦", "picUrl": "https://example.com/jay.jpg"}
        ]
    },
    "code": 200,
}

ARTIST_SONGS_RESPONSE = {
    "hotSongs": [
        {
            "id": 186001,
            "name": "青花瓷",
            "ar": [{"name": "周杰伦"}],
            "al": {"name": "我很忙", "picUrl": "https://example.com/album.jpg"},
            "dt": 237000,
        }
    ]
}


async def test_search_artist_returns_artist(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = ARTIST_SEARCH_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_resp.content = b"ok"

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        artist = await client.search_artist("周杰伦")

    assert artist is not None
    assert isinstance(artist, Artist)
    assert artist.id == "6452"
    assert artist.name == "周杰伦"
    assert artist.image_url == "https://example.com/jay.jpg"
    assert artist.platform == "netease"


async def test_search_artist_returns_none_on_empty(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": {"artists": []}, "code": 200}
    mock_resp.raise_for_status = MagicMock()
    mock_resp.content = b"ok"

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        artist = await client.search_artist("nonexistent")

    assert artist is None


async def test_get_artist_top_tracks(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = ARTIST_SONGS_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_resp.content = b"ok"

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        tracks = await client.get_artist_top_tracks("6452")

    assert len(tracks) == 1
    assert tracks[0].title == "青花瓷"
    assert tracks[0].platform == "netease"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_netease_client.py::test_search_artist_returns_artist tests/test_netease_client.py::test_get_artist_top_tracks -v
```

期望: `FAILED — AttributeError: 'NeteaseClient' object has no attribute 'search_artist'`

- [ ] **Step 3: 在 `platforms/netease/client.py` 添加方法**

在 `NeteaseClient` 类的 `_song_to_track` 方法之前添加：

```python
async def search_artist(self, name: str) -> "Artist | None":
    from core.models import Artist
    payload = weapi_encrypt({"s": name, "type": 100, "limit": 1, "offset": 0})
    async with httpx.AsyncClient(headers=_HEADERS, cookies=self._cookies) as http:
        resp = await http.post(f"{_BASE_URL}/weapi/cloudsearch/pc", data=payload)
        resp.raise_for_status()
        if not resp.content:
            return None
        data = resp.json()
    artists = data.get("result", {}).get("artists", [])
    if not artists:
        return None
    a = artists[0]
    return Artist(
        id=str(a["id"]),
        platform="netease",
        name=a.get("name", ""),
        image_url=a.get("picUrl", ""),
    )

async def get_artist_top_tracks(self, artist_id: str, limit: int = 30) -> list[Track]:
    payload = weapi_encrypt({"csrf_token": self._cookies.get("__csrf", "")})
    async with httpx.AsyncClient(headers=_HEADERS, cookies=self._cookies) as http:
        resp = await http.post(
            f"{_BASE_URL}/weapi/v1/artist/{artist_id}", data=payload
        )
        resp.raise_for_status()
        if not resp.content:
            return []
        data = resp.json()
    songs = data.get("hotSongs", [])
    return [self._song_to_track(s) for s in songs[:limit]]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_netease_client.py::test_search_artist_returns_artist tests/test_netease_client.py::test_search_artist_returns_none_on_empty tests/test_netease_client.py::test_get_artist_top_tracks -v
```

期望: 3 × `PASSED`

- [ ] **Step 5: 提交**

```bash
git add platforms/netease/client.py tests/test_netease_client.py
git commit -m "feat(artist): implement NeteaseClient.search_artist + get_artist_top_tracks"
```

---

## Task 3: SpotifyClient 歌手方法

**Files:**
- Modify: `platforms/spotify/client.py`
- Modify: `tests/test_spotify_client.py`

使用标准 Spotify Web API（与 `get_recommendations` 相同的 Bearer token + `_WEB_API_URL`）：
- 搜索歌手：`GET /v1/search?q={name}&type=artist&limit=1`
- 热门歌曲：`GET /v1/artists/{id}/top-tracks?market=US`（返回格式与 `_to_webapi_track` 兼容）

- [ ] **Step 1: 写失败测试**

在 `tests/test_spotify_client.py` 末尾追加（先查看该文件的 fixture 模式，确保 `client` fixture 可用）：

```python
from core.models import Artist

ARTIST_SEARCH_RESPONSE = {
    "artists": {
        "items": [
            {
                "id": "3TVXtAsR1Inumwj472S9r4",
                "name": "Drake",
                "images": [{"url": "https://example.com/drake.jpg", "height": 640, "width": 640}],
            }
        ]
    }
}

ARTIST_TOP_TRACKS_RESPONSE = {
    "tracks": [
        {
            "id": "track_001",
            "name": "God's Plan",
            "artists": [{"name": "Drake"}],
            "album": {"name": "Scorpion", "images": [{"url": "https://example.com/alb.jpg"}]},
            "duration_ms": 198973,
            "explicit": True,
        }
    ]
}


async def test_spotify_search_artist(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = ARTIST_SEARCH_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        artist = await client.search_artist("Drake")

    assert artist is not None
    assert isinstance(artist, Artist)
    assert artist.id == "3TVXtAsR1Inumwj472S9r4"
    assert artist.name == "Drake"
    assert artist.image_url == "https://example.com/drake.jpg"
    assert artist.platform == "spotify"


async def test_spotify_search_artist_returns_none_on_empty(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"artists": {"items": []}}
    mock_resp.raise_for_status = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        artist = await client.search_artist("nonexistent_xyz")

    assert artist is None


async def test_spotify_get_artist_top_tracks(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = ARTIST_TOP_TRACKS_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        tracks = await client.get_artist_top_tracks("3TVXtAsR1Inumwj472S9r4")

    assert len(tracks) == 1
    assert tracks[0].title == "God's Plan"
    assert tracks[0].platform == "spotify"
    assert tracks[0].is_explicit is True
```

注意：`tests/test_spotify_client.py` 中的 `client` fixture 通常 mock 了 `auth.get_access_token`；若无，需在测试中 patch `client._auth.get_access_token`。先运行一次查看报错信息再调整。

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_spotify_client.py::test_spotify_search_artist tests/test_spotify_client.py::test_spotify_get_artist_top_tracks -v
```

期望: `FAILED — AttributeError: 'SpotifyClient' object has no attribute 'search_artist'`

- [ ] **Step 3: 在 `platforms/spotify/client.py` 的 `get_recommendations` 方法之前添加**

```python
async def search_artist(self, name: str) -> "Artist | None":
    from core.models import Artist
    try:
        token = await self._auth.get_access_token()
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{_WEB_API_URL}/search",
                params={"q": name, "type": "artist", "limit": 1},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "User-Agent": _WEB_UA,
                    **_APP_HEADERS,
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            items = resp.json().get("artists", {}).get("items", [])
    except Exception as exc:
        logger.warning("Spotify search_artist failed: %s", exc)
        return None
    if not items:
        return None
    a = items[0]
    images = a.get("images") or []
    image_url = images[0].get("url", "") if images else ""
    return Artist(
        id=a.get("id", ""),
        platform="spotify",
        name=a.get("name", ""),
        image_url=image_url,
    )

async def get_artist_top_tracks(self, artist_id: str, limit: int = 30) -> list[Track]:
    try:
        token = await self._auth.get_access_token()
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{_WEB_API_URL}/artists/{artist_id}/top-tracks",
                params={"market": "US"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "User-Agent": _WEB_UA,
                    **_APP_HEADERS,
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            tracks_raw = resp.json().get("tracks", [])
    except Exception as exc:
        logger.warning("Spotify get_artist_top_tracks failed: %s", exc)
        return []
    return [self._to_webapi_track(t) for t in tracks_raw[:limit] if t.get("id")]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_spotify_client.py::test_spotify_search_artist tests/test_spotify_client.py::test_spotify_search_artist_returns_none_on_empty tests/test_spotify_client.py::test_spotify_get_artist_top_tracks -v
```

期望: 3 × `PASSED`

- [ ] **Step 5: 提交**

```bash
git add platforms/spotify/client.py tests/test_spotify_client.py
git commit -m "feat(artist): implement SpotifyClient.search_artist + get_artist_top_tracks"
```

---

## Task 4: YTMusicClient 歌手方法

**Files:**
- Modify: `platforms/ytmusic/client.py`
- Modify: `tests/test_ytmusic_client.py`

ytmusicapi：
- `self._ytm.search(name, filter="artists", limit=1)` → 返回列表，每项有 `browseId`、`artist`（名称）、`thumbnails`
- `self._ytm.get_artist(browseId)` → 返回 dict，有 `songs.results`（歌曲列表）

- [ ] **Step 1: 写失败测试**

在 `tests/test_ytmusic_client.py` 末尾追加：

```python
from core.models import Artist

ARTIST_SEARCH_RESULT = [
    {
        "browseId": "UCVnWg1HM4tKcBbFAFpGfqCg",
        "artist": "Taylor Swift",
        "thumbnails": [
            {"url": "https://example.com/ts_small.jpg", "width": 100, "height": 100},
            {"url": "https://example.com/ts_large.jpg", "width": 576, "height": 576},
        ],
        "resultType": "artist",
    }
]

ARTIST_DATA = {
    "name": "Taylor Swift",
    "thumbnails": [
        {"url": "https://example.com/ts_large.jpg", "width": 576, "height": 576},
    ],
    "songs": {
        "results": [
            {
                "videoId": "abc123",
                "title": "Anti-Hero",
                "artists": [{"name": "Taylor Swift", "id": "UCVnWg1HM4tKcBbFAFpGfqCg"}],
                "album": {"name": "Midnights", "id": "alb001"},
                "thumbnails": [{"url": "https://example.com/midnights.jpg"}],
                "duration_seconds": 200,
            }
        ]
    },
}


async def test_ytmusic_search_artist(client):
    with patch.object(client._ytm, "search", return_value=ARTIST_SEARCH_RESULT):
        artist = await client.search_artist("Taylor Swift")

    assert artist is not None
    assert isinstance(artist, Artist)
    assert artist.id == "UCVnWg1HM4tKcBbFAFpGfqCg"
    assert artist.name == "Taylor Swift"
    assert artist.image_url == "https://example.com/ts_large.jpg"
    assert artist.platform == "ytmusic"


async def test_ytmusic_search_artist_returns_none_on_empty(client):
    with patch.object(client._ytm, "search", return_value=[]):
        artist = await client.search_artist("nonexistent_xyz")

    assert artist is None


async def test_ytmusic_get_artist_top_tracks(client):
    with patch.object(client._ytm, "get_artist", return_value=ARTIST_DATA):
        tracks = await client.get_artist_top_tracks("UCVnWg1HM4tKcBbFAFpGfqCg")

    assert len(tracks) == 1
    assert tracks[0].title == "Anti-Hero"
    assert tracks[0].platform == "ytmusic"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_ytmusic_client.py::test_ytmusic_search_artist tests/test_ytmusic_client.py::test_ytmusic_get_artist_top_tracks -v
```

期望: `FAILED — AttributeError: 'YTMusicClient' object has no attribute 'search_artist'`

- [ ] **Step 3: 在 `platforms/ytmusic/client.py` 的 `get_recommendations` 方法之前添加**

```python
async def search_artist(self, name: str) -> "Artist | None":
    from core.models import Artist
    loop = asyncio.get_event_loop()
    try:
        results = await asyncio.wait_for(
            loop.run_in_executor(
                _executor,
                lambda: self._ytm.search(name, filter="artists", limit=1),
            ),
            timeout=10.0,
        )
    except Exception as exc:
        logger.warning("YTMusic search_artist failed: %s", exc)
        return None
    if not results:
        return None
    a = results[0]
    thumbs = a.get("thumbnails") or []
    image_url = thumbs[-1]["url"] if thumbs else ""
    artist_name = a.get("artist") or a.get("name") or name
    browse_id = a.get("browseId", "")
    return Artist(
        id=browse_id,
        platform="ytmusic",
        name=artist_name,
        image_url=image_url,
    )

async def get_artist_top_tracks(self, artist_id: str, limit: int = 30) -> list[Track]:
    loop = asyncio.get_event_loop()
    try:
        data = await asyncio.wait_for(
            loop.run_in_executor(
                _executor, lambda: self._ytm.get_artist(artist_id)
            ),
            timeout=12.0,
        )
    except Exception as exc:
        logger.warning("YTMusic get_artist_top_tracks failed: %s", exc)
        return []
    songs = (data or {}).get("songs", {}).get("results", [])
    return [self._to_track(s) for s in songs[:limit] if s.get("videoId")]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_ytmusic_client.py::test_ytmusic_search_artist tests/test_ytmusic_client.py::test_ytmusic_search_artist_returns_none_on_empty tests/test_ytmusic_client.py::test_ytmusic_get_artist_top_tracks -v
```

期望: 3 × `PASSED`

- [ ] **Step 5: 提交**

```bash
git add platforms/ytmusic/client.py tests/test_ytmusic_client.py
git commit -m "feat(artist): implement YTMusicClient.search_artist + get_artist_top_tracks"
```

---

## Task 5: AppController 新增信号与 load_artist 方法

**Files:**
- Modify: `core/app_controller.py`

- [ ] **Step 1: 在 `core/app_controller.py` 顶部 signals 区添加两个新信号**

在 `background_changed = pyqtSignal(str)` 这行之后添加：

```python
artist_ready = pyqtSignal(object)         # Artist
artist_tracks_ready = pyqtSignal(list)    # list[Track]
```

- [ ] **Step 2: 在 `AppController` 末尾添加 `load_artist` 方法**

在文件末尾（或现有异步方法之后）添加：

```python
async def load_artist(self, artist_name: str, platform: str) -> None:
    client = self._get_platform_client(platform)
    if client is None:
        logger.warning("load_artist: no client for platform %r", platform)
        return
    try:
        artist = await client.search_artist(artist_name)
    except Exception as exc:
        logger.warning("load_artist search_artist failed: %s", exc)
        return
    if artist is None:
        return
    self.artist_ready.emit(artist)
    try:
        tracks = await client.get_artist_top_tracks(artist.id)
    except Exception as exc:
        logger.warning("load_artist get_artist_top_tracks failed: %s", exc)
        tracks = []
    self.artist_tracks_ready.emit(tracks)
```

- [ ] **Step 3: 运行全量测试确认无回归**

```bash
python -m pytest tests/ -v --tb=short -q
```

期望：所有之前通过的测试仍通过，无新失败。

- [ ] **Step 4: 提交**

```bash
git add core/app_controller.py
git commit -m "feat(artist): add artist_ready/artist_tracks_ready signals and load_artist to AppController"
```

---

## Task 6: ArtistPage UI

**Files:**
- Create: `ui/pages/artist_page.py`

页面布局：
```
┌──────────────────────────────────────────────────────────────┐
│  ← 返回    [头像 80×80]   歌手名称（pageTitle 样式）          │
│                          平台标签（小字，subdued 颜色）         │
├──────────────────────────────────────────────────────────────┤
│  热门歌曲                                                      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ TrackRow × N（可滚动）                                 │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

- [ ] **Step 1: 新建 `ui/pages/artist_page.py`**

```python
from __future__ import annotations
import asyncio
import httpx
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QListWidget, QListWidgetItem, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QCursor
from ui.theme import COLORS, FONTS, scrollbar_qss
from ui.components.track_row import TrackRow, ROW_HEIGHT
from core.models import Artist, Track


class ArtistPage(QWidget):
    back_requested = pyqtSignal()
    play_track = pyqtSignal(object)         # Track
    queue_track = pyqtSignal(object)        # Track
    artist_clicked = pyqtSignal(object)     # Track (for nested artist navigation)

    def __init__(self, ctrl, parent=None) -> None:
        super().__init__(parent)
        self._ctrl = ctrl
        self._artist: Artist | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 0)
        layout.setSpacing(12)

        # ── Header ────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(16)

        back_btn = QPushButton("← 返回")
        back_btn.setObjectName("backBtn")
        back_btn.setFixedWidth(80)
        back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back_btn.clicked.connect(self.back_requested)
        header.addWidget(back_btn)

        self._cover_lbl = QLabel()
        self._cover_lbl.setFixedSize(80, 80)
        self._cover_lbl.setObjectName("artistCover")
        self._cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self._cover_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        self._name_lbl = QLabel("—")
        self._name_lbl.setObjectName("pageTitle")
        title_col.addWidget(self._name_lbl)
        self._platform_lbl = QLabel("")
        self._platform_lbl.setObjectName("artistPlatform")
        title_col.addWidget(self._platform_lbl)
        title_col.addStretch()
        header.addLayout(title_col, stretch=1)

        layout.addLayout(header)

        # ── Section label ─────────────────────────────────────────────────────
        section_lbl = QLabel("热门歌曲")
        section_lbl.setObjectName("sectionLabel")
        layout.addWidget(section_lbl)

        # ── Track list ────────────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setObjectName("artistTrackList")
        self._list.setSpacing(0)
        self._list.setFrameShape(self._list.Shape.NoFrame)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setVerticalScrollMode(self._list.ScrollMode.ScrollPerPixel)
        self._list.setStyleSheet(scrollbar_qss() + """
            QListWidget { background: transparent; border: none; outline: none; }
            QListWidget::item { padding: 0; border: none; }
            QListWidget::item:selected { background: transparent; }
        """)
        layout.addWidget(self._list, stretch=1)

        self._apply_styles()

    def _apply_styles(self) -> None:
        c, f = COLORS, FONTS
        self.setStyleSheet(f"""
            #backBtn {{
                background: transparent;
                color: {c['text_secondary']};
                font-size: {f['size_sm']}px;
                border: none;
                text-align: left;
                padding: 0;
            }}
            #backBtn:hover {{ color: {c['text_primary']}; }}
            #artistCover {{
                background-color: {c['bg_elevated']};
                border-radius: 40px;
            }}
            #pageTitle {{
                color: {c['text_primary']};
                font-size: {f['size_lg']}px;
                font-weight: bold;
            }}
            #artistPlatform {{
                color: {c['text_secondary']};
                font-size: {f['size_sm']}px;
            }}
            #sectionLabel {{
                color: {c['text_primary']};
                font-size: {f['size_md']}px;
                font-weight: bold;
            }}
        """)

    # ── public API ────────────────────────────────────────────────────────────

    def load_artist(self, artist: Artist) -> None:
        self._artist = artist
        self._name_lbl.setText(artist.name)
        _PLATFORM_NAMES = {"netease": "网易云音乐", "spotify": "Spotify", "ytmusic": "YouTube Music"}
        self._platform_lbl.setText(_PLATFORM_NAMES.get(artist.platform, artist.platform))
        self._cover_lbl.setText("")
        self._list.clear()
        if artist.image_url:
            asyncio.ensure_future(self._load_cover(artist.image_url))

    def load_tracks(self, tracks: list[Track]) -> None:
        self._list.clear()
        for track in tracks:
            row = TrackRow(track)
            row.queue_clicked.connect(self.queue_track)
            row.artist_clicked.connect(self.artist_clicked)
            item = QListWidgetItem(self._list)
            item.setSizeHint(row.sizeHint())
            self._list.setItemWidget(item, row)
            # Double-click on item plays track
            item.setData(Qt.ItemDataRole.UserRole, track)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)

    # ── internal ──────────────────────────────────────────────────────────────

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        track = item.data(Qt.ItemDataRole.UserRole)
        if track:
            self.play_track.emit(track)

    async def _load_cover(self, url: str) -> None:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(url, timeout=8.0)
                data = resp.content
            px = QPixmap()
            px.loadFromData(data)
            if not px.isNull():
                px = px.scaled(
                    80, 80,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                # Circular clip
                out = QPixmap(80, 80)
                out.fill(Qt.GlobalColor.transparent)
                painter = QPainter(out)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                path = QPainterPath()
                path.addEllipse(0, 0, 80, 80)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, px)
                painter.end()
                self._cover_lbl.setPixmap(out)
        except Exception:
            pass
```

- [ ] **Step 2: 确认文件无语法错误**

```bash
python -c "from ui.pages.artist_page import ArtistPage; print('OK')"
```

期望: `OK`

- [ ] **Step 3: 提交**

```bash
git add ui/pages/artist_page.py
git commit -m "feat(artist): create ArtistPage UI"
```

---

## Task 7: 控制栏与歌曲行的歌手标签可点击化

**Files:**
- Modify: `ui/components/now_playing_bar.py`
- Modify: `ui/components/track_row.py`

### now_playing_bar.py

当前 `self._artist = QLabel("—")`，改为 `_ClickableLabel`（该类已在同文件中定义）并新增 `artist_clicked` 信号。

- [ ] **Step 1: 在 `NowPlayingBar` 类的信号声明区新增 `artist_clicked` 信号**

在 `track_info_clicked = pyqtSignal()` 这行之后添加：

```python
artist_clicked = pyqtSignal()
```

- [ ] **Step 2: 在 `_build_left` 中将 `QLabel` 改为 `_ClickableLabel` 并连接信号**

将：
```python
self._artist = QLabel("—")
self._artist.setObjectName("trackArtist")
```

改为：
```python
self._artist = _ClickableLabel("—")
self._artist.setObjectName("trackArtist")
self._artist.clicked.connect(self.artist_clicked)
```

### track_row.py

`TrackRow._artist_lbl` 当前是 `QLabel`，需要改为可点击标签并发出 `artist_clicked(Track)` 信号。

- [ ] **Step 3: 在 `track_row.py` 文件顶部（`ROW_HEIGHT = 38` 之前）添加 `_ClickableLabel`**

```python
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QCursor

class _ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
```

注意：`track_row.py` 已经有 `from PyQt6.QtCore import Qt, QRectF, pyqtSignal` 这行，需要在其中补充 `QCursor`。

- [ ] **Step 4: 在 `TrackRow` 类的信号声明区新增 `artist_clicked` 信号**

在 `queue_clicked = pyqtSignal(object)` 之后添加：

```python
artist_clicked = pyqtSignal(object)  # Track
```

- [ ] **Step 5: 在 `TrackRow.__init__` 中将歌手列改为 `_ClickableLabel` 并连接信号**

将：
```python
self._artist_lbl = QLabel(track.artist)
self._artist_lbl.setObjectName("colArtist")
self._artist_lbl.setFixedWidth(ARTIST_WIDTH)
layout.addWidget(self._artist_lbl)
```

改为：
```python
self._artist_lbl = _ClickableLabel(track.artist)
self._artist_lbl.setObjectName("colArtist")
self._artist_lbl.setFixedWidth(ARTIST_WIDTH)
self._artist_lbl.clicked.connect(lambda: self.artist_clicked.emit(self._track))
layout.addWidget(self._artist_lbl)
```

- [ ] **Step 6: 确认无语法错误**

```bash
python -c "from ui.components.now_playing_bar import NowPlayingBar; from ui.components.track_row import TrackRow; print('OK')"
```

期望: `OK`（Qt 环境需要在有 QApplication 时才能实例化，这里只检查导入）

- [ ] **Step 7: 运行现有 UI 组件测试**

```bash
python -m pytest tests/test_ui_components.py tests/test_track_list.py -v --tb=short
```

期望：全部通过，无回归。

- [ ] **Step 8: 提交**

```bash
git add ui/components/now_playing_bar.py ui/components/track_row.py
git commit -m "feat(artist): make artist labels clickable in NowPlayingBar and TrackRow"
```

---

## Task 8: MainWindow 接线

**Files:**
- Modify: `ui/app_window.py`

需要：
1. 导入并注册 `ArtistPage` 到 QStackedWidget
2. 将 `ctrl.artist_ready` / `ctrl.artist_tracks_ready` 连接到 `ArtistPage`
3. 将 `now_playing.artist_clicked` 连接到 `_navigate_to_artist`
4. 将各页面中 `TrackRow.artist_clicked` 信号一路冒泡到 `MainWindow`（通过页面自身转发）
5. 实现 `_navigate_to_artist(artist_name, platform)` 与 `_on_artist_back`

### 页面信号转发（先处理现有页面）

`HomePage`、`SearchPage`、`LibraryPage` 中都使用了 `TrackRow`（通过 `TrackList` 或直接创建）。需要将 `TrackRow.artist_clicked` 信号转发到页面级。先查看这些文件，确认是否有统一入口。

- [ ] **Step 1: 在 `HomePage` / `SearchPage` / `LibraryPage` 中为 `TrackRow.artist_clicked` 信号添加转发**

检查每个页面创建 `TrackRow` 的位置（通常在 `_make_row` 或直接 `TrackRow(track)` 处），在每个地方连接：

```python
row.artist_clicked.connect(self.artist_clicked)
```

同时在每个页面类开头声明：

```python
artist_clicked = pyqtSignal(object)  # Track
```

（搜索文件中 `TrackRow(track)` 出现的位置，逐一添加。）

- [ ] **Step 2: 在 `ArtistPage` 中，`load_tracks` 创建的 `TrackRow` 已经连接了 `row.artist_clicked.connect(self.artist_clicked)`（Task 6 已实现）。**

确认 `ui/pages/artist_page.py` 的 `load_tracks` 中有这一行。若没有，在 `row.queue_clicked.connect(self.queue_track)` 之后添加：

```python
row.artist_clicked.connect(self.artist_clicked)
```

- [ ] **Step 3: 在 `ui/app_window.py` 顶部 import 区添加 `ArtistPage`**

在现有 `from ui.pages.settings_page import SettingsPage` 之后添加：

```python
from ui.pages.artist_page import ArtistPage
```

- [ ] **Step 4: 在 `MainWindow._build_ui` 中注册 `ArtistPage`**

在 `self._settings_page = SettingsPage(self._ctrl)` 之后添加：

```python
self._artist_page = ArtistPage(self._ctrl)
```

在 `self._page_map` dict 中添加：

```python
"artist": self.content.addWidget(self._artist_page),
```

- [ ] **Step 5: 在 `MainWindow._wire_signals` 中接线**

在 `self.now_playing.queue_requested.connect(self._show_queue)` 之后添加：

```python
# Artist page
self.now_playing.artist_clicked.connect(self._on_nowplaying_artist_clicked)
ctrl.artist_ready.connect(self._artist_page.load_artist)
ctrl.artist_tracks_ready.connect(self._artist_page.load_tracks)
self._artist_page.back_requested.connect(self._on_artist_back)
self._artist_page.play_track.connect(
    lambda t: asyncio.ensure_future(ctrl.play_track(t))
)
self._artist_page.queue_track.connect(ctrl.add_to_queue)
self._artist_page.artist_clicked.connect(
    lambda t: self._navigate_to_artist(t.artist, t.platform)
)

# Forward artist_clicked from content pages
self._home_page.artist_clicked.connect(
    lambda t: self._navigate_to_artist(t.artist, t.platform)
)
self._search_page.artist_clicked.connect(
    lambda t: self._navigate_to_artist(t.artist, t.platform)
)
self._library_page.artist_clicked.connect(
    lambda t: self._navigate_to_artist(t.artist, t.platform)
)
```

注意：若 `ctrl.play_track` 方法名不一致，检查 `AppController` 中播放单首曲目的实际方法名（可能是 `play_track` 或 `play_now`）并修正。同样检查 `ctrl.add_to_queue` 是否存在。

- [ ] **Step 6: 在 `MainWindow` 中添加导航方法**

在 `_save_prev_page` 方法之后添加：

```python
def _on_nowplaying_artist_clicked(self) -> None:
    state = self._ctrl._player._state   # 访问当前播放状态
    if state.current_track is None:
        return
    t = state.current_track
    self._navigate_to_artist(t.artist, t.platform)

def _navigate_to_artist(self, artist_name: str, platform: str) -> None:
    if not artist_name:
        return
    self._save_prev_page()
    self.content.setCurrentIndex(self._page_map["artist"])
    self.now_playing.set_lyrics_active(False)
    asyncio.ensure_future(self._ctrl.load_artist(artist_name, platform))

def _on_artist_back(self) -> None:
    idx = self._page_map.get(self._prev_page, self._page_map["home"])
    self.content.setCurrentIndex(idx)
```

注意：`self._ctrl._player._state` 是内部访问；若 `AppController` 有公开的 `current_state` property 或类似接口，优先使用。检查 `app_controller.py` 中是否有 `current_state` 或 `state` 属性；若没有，添加一个：

```python
@property
def current_state(self) -> PlayerState:
    return self._player._state
```

然后在 `_on_nowplaying_artist_clicked` 中使用：
```python
state = self._ctrl.current_state
```

- [ ] **Step 7: 运行全量测试确认无回归**

```bash
python -m pytest tests/ -v --tb=short -q
```

期望：全部通过（UI 实例化测试可能被 skip，属正常）。

- [ ] **Step 8: 提交**

```bash
git add ui/app_window.py ui/pages/home_page.py ui/pages/search_page.py ui/pages/library_page.py core/app_controller.py
git commit -m "feat(artist): wire ArtistPage into MainWindow, connect all artist navigation signals"
```

---

## Self-Review

### 规格覆盖检查

| 需求 | 对应 Task |
|------|-----------|
| 歌手详情页显示歌手歌曲 | Task 6 ArtistPage |
| 从控制栏歌手名称进入 | Task 7 NowPlayingBar + Task 8 |
| 从页内歌曲词条歌手名进入 | Task 7 TrackRow + Task 8 |
| 根据当前歌曲平台获取歌手信息 | Task 2/3/4 平台实现 + Task 5 AppController |
| 三个平台均支持 | Task 2 (Netease) + Task 3 (Spotify) + Task 4 (YTMusic) |

### Placeholder 扫描

- Task 8 Step 5 注意项：`ctrl.play_track` 和 `ctrl.add_to_queue` 名称需在实施时确认。
- `_on_nowplaying_artist_clicked` 中的 state 访问路径需在实施时确认并可能添加 `current_state` property。

### 类型一致性

- `Artist` dataclass 在 Task 1 定义，Task 2/3/4/5/6 均使用相同字段（`id`, `platform`, `name`, `image_url`）。
- `artist_clicked` 信号在 `TrackRow`/`ArtistPage`/各内容页统一为 `pyqtSignal(object)` 传递 `Track`。
- `NowPlayingBar.artist_clicked` 为 `pyqtSignal()` 无参数（由 MainWindow 从 state 取 track）。
