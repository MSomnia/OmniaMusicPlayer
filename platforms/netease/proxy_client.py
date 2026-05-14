from __future__ import annotations
import asyncio
import logging
import httpx
from core.models import Track, Playlist, Album, LyricLine, Artist
from platforms.base import AbstractPlatform
from utils.lrc_parser import parse_lrc

logger = logging.getLogger(__name__)

# Default URL for a locally-running NeteaseCloudMusicApi instance.
# Start it with: npx @binaryify/netease-cloud-music-api
DEFAULT_PROXY_URL = "http://localhost:3000"
_LIBRARY_RETRY_DELAY = 0.35
_LIBRARY_REQUEST_TIMEOUT = 15.0


def _playlist_add_succeeded(data: dict) -> bool:
    body = data.get("body")
    if isinstance(body, dict) and "code" in body:
        try:
            return int(body.get("code", 0)) == 200
        except (TypeError, ValueError):
            return False
    if "code" in data:
        try:
            return int(data.get("code", 0)) == 200
        except (TypeError, ValueError):
            return False
    try:
        return int(data.get("status", 0)) == 200
    except (TypeError, ValueError):
        return False


class NeteaseProxyClient(AbstractPlatform):
    """Calls a local NeteaseCloudMusicApi proxy instead of Netease directly.

    Avoids geo-blocking by delegating all requests to the local proxy server,
    which handles weapi encryption and routing internally.
    """

    platform_id = "netease"

    def __init__(
        self,
        cookies: dict[str, str],
        proxy_url: str = DEFAULT_PROXY_URL,
    ) -> None:
        self._cookies = cookies
        self._base = proxy_url.rstrip("/")
        self._uid: str | None = None

    def _cookie_str(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self._cookies.items())

    async def is_authenticated(self) -> bool:
        return bool(self._cookies.get("MUSIC_U"))

    async def search(self, query: str, limit: int = 30) -> list[Track]:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base}/cloudsearch",
                params={"keywords": query, "type": 1, "limit": limit, "cookie": self._cookie_str()},
            )
            resp.raise_for_status()
            data = resp.json()
        songs = data.get("result", {}).get("songs", [])
        return [self._song_to_track(s) for s in songs]

    async def get_stream_url(self, track: Track) -> str:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base}/song/url/v1",
                params={"id": track.id, "level": "exhigh", "cookie": self._cookie_str()},
            )
            resp.raise_for_status()
            data = resp.json()
        items = data.get("data", [])
        if not items or not items[0].get("url"):
            raise RuntimeError(f"No stream URL for track {track.id}")
        return items[0]["url"]

    async def get_lyrics(self, track: Track) -> list[LyricLine]:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base}/lyric",
                params={"id": track.id, "cookie": self._cookie_str()},
            )
            resp.raise_for_status()
            data = resp.json()
        lrc_text = data.get("lrc", {}).get("lyric", "")
        if not lrc_text:
            return []
        return parse_lrc(lrc_text)

    async def get_library_playlists(self) -> list[Playlist]:
        uid = await self._get_uid()
        data = await self._get_json_with_retry(
            "/user/playlist",
            {"uid": uid, "limit": 50, "cookie": self._cookie_str()},
        )
        playlists = data.get("playlist", [])
        return [
            Playlist(
                id=str(p["id"]),
                platform="netease",
                name=p["name"],
                cover_url=p.get("coverImgUrl", ""),
                track_count=p.get("trackCount", 0),
            )
            for p in playlists
        ]

    async def get_addable_playlists(self) -> list[Playlist]:
        uid = await self._get_uid()
        data = await self._get_json_with_retry(
            "/user/playlist",
            {"uid": uid, "limit": 100, "cookie": self._cookie_str()},
        )
        playlists = data.get("playlist", [])
        return [
            Playlist(
                id=str(p["id"]),
                platform="netease",
                name=p["name"],
                cover_url=p.get("coverImgUrl", ""),
                track_count=p.get("trackCount", 0),
            )
            for p in playlists
            if not p.get("subscribed")
        ]

    async def get_home(self) -> list[tuple[str, list[Track]]]:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base}/recommend/songs",
                params={"cookie": self._cookie_str()},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
        songs = data.get("data", {}).get("dailySongs", [])
        tracks = [self._song_to_track(s) for s in songs]
        return [("每日推荐", tracks)] if tracks else []

    async def search_albums(self, query: str, limit: int = 5) -> list[Album]:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{self._base}/cloudsearch",
                    params={"keywords": query, "type": 10, "limit": limit,
                            "cookie": self._cookie_str()},
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Netease search_albums failed: %s", exc)
            return []
        albums = []
        for a in data.get("result", {}).get("albums", []):
            albums.append(Album(
                id=str(a["id"]),
                platform="netease",
                name=a.get("name", ""),
                artist=a.get("artist", {}).get("name", ""),
                cover_url=a.get("picUrl", ""),
                track_count=a.get("size", 0),
                year=str(a.get("publishTime", ""))[:4],
            ))
        return albums

    async def get_album_tracks(self, album_id: str) -> list[Track]:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{self._base}/album",
                    params={"id": album_id, "cookie": self._cookie_str()},
                    timeout=12.0,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Netease get_album_tracks failed: %s", exc)
            return []
        return [self._song_to_track(s) for s in data.get("songs", [])]

    async def search_artist(self, name: str) -> "Artist | None":
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{self._base}/cloudsearch",
                    params={"keywords": name, "type": 100, "limit": 1,
                            "cookie": self._cookie_str()},
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Netease proxy search_artist failed: %s", exc)
            return None
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
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{self._base}/artists",
                    params={"id": artist_id, "cookie": self._cookie_str()},
                    timeout=12.0,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Netease proxy get_artist_top_tracks failed: %s", exc)
            return []
        songs = data.get("hotSongs", [])
        return [self._song_to_track(s) for s in songs[:limit]]

    async def get_recommendations(self, track: Track) -> list[Track]:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{self._base}/simi/song",
                    params={"id": track.id, "limit": 12, "cookie": self._cookie_str()},
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Netease simi/song failed: %s", exc)
            return []
        return [self._song_to_track(s) for s in data.get("songs", [])]

    async def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base}/playlist/track/all",
                params={"id": playlist_id, "limit": 200, "cookie": self._cookie_str()},
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
        songs = data.get("songs", [])
        return [self._song_to_track(s) for s in songs]

    async def add_track_to_playlist(self, playlist_id: str, track: Track) -> bool:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base}/playlist/tracks",
                params={
                    "op": "add",
                    "pid": playlist_id,
                    "tracks": track.id,
                    "cookie": self._cookie_str(),
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
        return _playlist_add_succeeded(data)

    async def remove_track_from_playlist(self, playlist_id: str, track: Track) -> bool:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base}/playlist/tracks",
                params={
                    "op": "del",
                    "pid": playlist_id,
                    "tracks": track.id,
                    "cookie": self._cookie_str(),
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
        result = _playlist_add_succeeded(data)
        if not result:
            logger.warning("Netease proxy remove_track_from_playlist rejected: %s", data)
        return result

    async def _get_uid(self) -> str:
        if self._uid:
            return self._uid
        data = await self._get_json_with_retry(
            "/user/account",
            {"cookie": self._cookie_str()},
        )
        self._uid = str(data.get("account", {}).get("id", ""))
        return self._uid

    async def _get_json_with_retry(self, path: str, params: dict) -> dict:
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient() as http:
                    resp = await http.get(
                        f"{self._base}{path}",
                        params=params,
                        timeout=_LIBRARY_REQUEST_TIMEOUT,
                    )
                    resp.raise_for_status()
                    return resp.json()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt == 0:
                    logger.info(
                        "Netease proxy %s not ready yet, retrying: %r",
                        path,
                        exc,
                    )
                    await asyncio.sleep(_LIBRARY_RETRY_DELAY)
                    continue
                raise
        raise RuntimeError(f"Netease proxy request failed: {path}") from last_exc

    @staticmethod
    def _song_to_track(song: dict) -> Track:
        artists = [a["name"] for a in song.get("ar", [])]
        album = song.get("al", {})
        return Track(
            id=str(song["id"]),
            platform="netease",
            title=song["name"],
            artist=artists[0] if artists else "",
            artists=artists,
            album=album.get("name", ""),
            album_cover_url=album.get("picUrl", ""),
            duration_ms=song.get("dt", 0),
        )
