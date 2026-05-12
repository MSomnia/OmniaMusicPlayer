import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from platforms.spotify.auth import SpotifyAuth


def _make_repo(sp_dc=None):
    repo = MagicMock()
    repo.load_credential = AsyncMock(
        return_value={"sp_dc": sp_dc} if sp_dc else None
    )
    repo.save_credential = AsyncMock()
    return repo


async def test_load_sp_dc_returns_none_when_missing():
    repo = _make_repo(sp_dc=None)
    auth = SpotifyAuth(repo)
    result = await auth.load_sp_dc()
    assert result is None


async def test_load_sp_dc_returns_value_when_present():
    repo = _make_repo(sp_dc="abc123")
    auth = SpotifyAuth(repo)
    result = await auth.load_sp_dc()
    assert result == "abc123"


async def test_get_access_token_uses_cache():
    repo = _make_repo(sp_dc="test_sp_dc")
    auth = SpotifyAuth(repo)
    auth._cached_token = "cached_token"
    auth._token_expires_at = time.time() + 3600

    token = await auth.get_access_token()
    assert token == "cached_token"


async def test_get_access_token_fetches_when_expired():
    repo = _make_repo(sp_dc="test_sp_dc")
    auth = SpotifyAuth(repo)
    auth._cached_token = "old_token"
    auth._token_expires_at = time.time() - 1  # expired

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "accessToken": "new_token",
        "accessTokenExpirationTimestampMs": int((time.time() + 3600) * 1000),
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        token = await auth.get_access_token()

    assert token == "new_token"
    assert auth._cached_token == "new_token"


async def test_get_access_token_raises_without_sp_dc():
    repo = _make_repo(sp_dc=None)
    auth = SpotifyAuth(repo)

    with pytest.raises(RuntimeError, match="not authenticated"):
        await auth.get_access_token()


async def test_ensure_authenticated_returns_existing():
    repo = _make_repo(sp_dc="existing")
    auth = SpotifyAuth(repo)
    result = await auth.ensure_authenticated()
    assert result == "existing"
