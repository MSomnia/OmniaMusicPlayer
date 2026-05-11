import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from platforms.netease.client import NeteaseClient
from core.models import Track


@pytest.fixture
def client():
    return NeteaseClient(cookies={"MUSIC_U": "fake", "__csrf": "fake"})


SEARCH_RESPONSE = {
    "result": {
        "songs": [
            {
                "id": 123456,
                "name": "Test Song",
                "ar": [{"name": "Artist A"}, {"name": "Artist B"}],
                "al": {"name": "Test Album", "picUrl": "https://example.com/cover.jpg"},
                "dt": 240000,
            }
        ]
    },
    "code": 200,
}


async def test_search_returns_tracks(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = SEARCH_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        tracks = await client.search("Test Song")

    assert len(tracks) == 1
    t = tracks[0]
    assert isinstance(t, Track)
    assert t.id == "123456"
    assert t.title == "Test Song"
    assert t.platform == "netease"
    assert t.artist == "Artist A"
    assert t.artists == ["Artist A", "Artist B"]
    assert t.duration_ms == 240000


STREAM_RESPONSE = {
    "data": [{"url": "https://cdn.example.com/audio.mp3", "code": 200}],
    "code": 200,
}


async def test_get_stream_url(client):
    track = Track(
        id="123456", platform="netease", title="T", artist="A",
        artists=["A"], album="Alb", album_cover_url="", duration_ms=1000,
    )
    mock_resp = MagicMock()
    mock_resp.json.return_value = STREAM_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        url = await client.get_stream_url(track)

    assert url == "https://cdn.example.com/audio.mp3"


async def test_search_empty_result(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": {"songs": []}, "code": 200}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        tracks = await client.search("nonexistent")
    assert tracks == []


async def test_is_authenticated_false_when_no_music_u(client):
    empty_client = NeteaseClient(cookies={})
    result = await empty_client.is_authenticated()
    assert result is False


async def test_is_authenticated_true_when_cookie_present(client):
    result = await client.is_authenticated()
    assert result is True
