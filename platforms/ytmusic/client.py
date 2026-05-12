from __future__ import annotations
import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from core.models import Track, Playlist, LyricLine
from platforms.base import AbstractPlatform

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ytmusic")

# User-Agent that matches what yt-dlp sends; returned alongside the stream URL
# so VLC can use it for the CDN request.
_YT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class YTMusicClient(AbstractPlatform):
    """Async wrapper around synchronous ytmusicapi + yt-dlp."""

    platform_id = "ytmusic"

    def __init__(self, headers: dict[str, str]) -> None:
        from ytmusicapi import YTMusic  # type: ignore[import]
        # Pass dict directly — ytmusicapi 1.12+ accepts str | dict | None for auth.
        # Passing json.dumps() makes ytmusicapi detect it as OAuth JSON; a dict
        # preserves the Authorization: SAPISIDHASH header needed for BROWSER detection.
        self._ytm = YTMusic(auth=headers)

    async def is_authenticated(self) -> bool:
        return bool(self._ytm)

    async def search(self, query: str, limit: int = 30) -> list[Track]:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            _executor, lambda: self._ytm.search(query, filter="songs", limit=limit)
        )
        tracks = [self._to_track(r) for r in (results or []) if r.get("videoId")]
        return tracks

    async def get_stream_url(self, track: Track) -> str:
        if not track.id:
            raise ValueError(f"Track has no video ID: {track.title!r}")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._extract_stream_url, track.id)

    async def get_lyrics(self, track: Track) -> list[LyricLine]:
        from platforms.ytmusic.lyrics import LRCLibClient
        return await LRCLibClient().get_lyrics(track)

    async def get_library_playlists(self) -> list[Playlist]:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(
            _executor, self._ytm.get_library_playlists
        )
        return [self._to_playlist(p) for p in (raw or [])]

    def _extract_stream_url(self, video_id: str) -> str:
        import yt_dlp  # type: ignore[import]

        if not video_id:
            raise ValueError("Empty video_id passed to _extract_stream_url")

        opts = {
            # Prefer opus/webm (best quality audio-only); fall back to m4a, then any
            "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            # Do NOT skip DASH — audio-only DASH streams are direct HTTP URLs
            # (not manifests) and are the highest-quality option on YouTube.
        }

        yt_url = f"https://music.youtube.com/watch?v={video_id}"
        logger.debug("Extracting stream URL for video %s", video_id)

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(yt_url, download=False)

        if not info:
            raise RuntimeError(f"yt-dlp returned no info for video {video_id!r}")

        # yt-dlp already applied the format selector; info["url"] is the winner.
        stream_url = info.get("url")

        # When video+audio are merged into separate tracks, URLs live here:
        if not stream_url:
            for fmt in info.get("requested_formats", []):
                u = fmt.get("url")
                if u and fmt.get("acodec") not in (None, "none"):
                    stream_url = u
                    break

        # Last resort: scan formats manually
        if not stream_url:
            fmts = [
                f for f in info.get("formats", [])
                if f.get("url") and f.get("acodec") not in (None, "none")
            ]
            if fmts:
                stream_url = max(fmts, key=lambda f: f.get("abr") or f.get("tbr") or 0)["url"]

        if not stream_url:
            raise RuntimeError(f"No playable stream URL found for video {video_id!r}")

        logger.debug("Stream URL extracted: %s…", stream_url[:60])
        return stream_url

    @staticmethod
    def _to_track(r: dict) -> Track:
        artists = [a["name"] for a in r.get("artists") or []]
        album_obj = r.get("album") or {}
        thumbs = r.get("thumbnails") or []
        cover = thumbs[-1]["url"] if thumbs else ""
        return Track(
            id=r.get("videoId") or "",   # guard: videoId can be None in some results
            platform="ytmusic",
            title=r.get("title", ""),
            artist=artists[0] if artists else "",
            artists=artists,
            album=album_obj.get("name", "") if isinstance(album_obj, dict) else "",
            album_cover_url=cover,
            duration_ms=(r.get("duration_seconds") or 0) * 1000,
        )

    @staticmethod
    def _to_playlist(p: dict) -> Playlist:
        thumbs = p.get("thumbnails") or []
        cover = thumbs[-1]["url"] if thumbs else ""
        return Playlist(
            id=p.get("playlistId", ""),
            platform="ytmusic",
            name=p.get("title", ""),
            cover_url=cover,
            track_count=p.get("count") or 0,
        )
