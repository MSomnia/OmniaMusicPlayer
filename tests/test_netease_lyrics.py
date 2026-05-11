import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from platforms.netease.lyrics import NeteaseLyrics
from core.models import LyricLine, Track


@pytest.fixture
def lyrics_client():
    return NeteaseLyrics(cookies={"MUSIC_U": "fake", "__csrf": "fake"})


def _make_track(tid="123"):
    return Track(
        id=tid, platform="netease", title="T", artist="A",
        artists=["A"], album="Alb", album_cover_url="", duration_ms=180000,
    )


LRC_BODY = "[00:01.00]Hello\n[00:03.00]World\n"
LYRICS_RESPONSE = {
    "lrc": {"lyric": LRC_BODY},
    "klyric": {"lyric": ""},
    "code": 200,
}


async def test_get_lyrics_returns_lyric_lines(lyrics_client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = LYRICS_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        lines = await lyrics_client.get_lyrics(_make_track())

    assert len(lines) == 2
    assert lines[0].text == "Hello"
    assert lines[1].text == "World"


async def test_get_lyrics_no_lrc_returns_empty(lyrics_client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"lrc": {"lyric": ""}, "code": 200}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        lines = await lyrics_client.get_lyrics(_make_track())

    assert lines == []


async def test_get_lyrics_timestamps_correct(lyrics_client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = LYRICS_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        lines = await lyrics_client.get_lyrics(_make_track())

    assert lines[0].start_ms == 1000
    assert lines[1].start_ms == 3000
