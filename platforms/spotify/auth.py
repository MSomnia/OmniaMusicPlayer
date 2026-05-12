from __future__ import annotations
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

_ACCOUNTS_URL = "https://accounts.spotify.com/login"
_TOKEN_URL = "https://open.spotify.com/get_access_token"
_TOKEN_PARAMS = "?reason=transport&productType=web_player"


class SpotifyAuth:
    def __init__(self, repo) -> None:
        self._repo = repo
        self._cached_token: str | None = None
        self._token_expires_at: float = 0.0

    async def load_sp_dc(self) -> str | None:
        cred = await self._repo.load_credential("spotify")
        if cred:
            return cred.get("sp_dc")
        return None

    async def login(self, parent=None) -> str | None:
        from ui.components.login_dialog import LoginDialog

        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()

        dialog = LoginDialog(
            url=_ACCOUNTS_URL,
            target_cookies=["sp_dc"],
            title="Spotify — 登录",
            parent=parent,
        )

        def _on_captured(cookies: dict) -> None:
            if not future.done():
                future.set_result(cookies)

        def _on_rejected() -> None:
            if not future.done():
                future.set_result(None)

        dialog.cookies_captured.connect(_on_captured)
        dialog.rejected.connect(_on_rejected)
        dialog.show()

        cookies = await future
        if not cookies or "sp_dc" not in cookies:
            logger.debug("Spotify login cancelled — sp_dc not captured")
            return None

        sp_dc = cookies["sp_dc"]
        await self._repo.save_credential("spotify", {"sp_dc": sp_dc})
        logger.info("Spotify sp_dc saved")
        return sp_dc

    async def get_access_token(self) -> str:
        now = time.time()
        if self._cached_token and now < self._token_expires_at - 60:
            return self._cached_token

        sp_dc = await self.load_sp_dc()
        if not sp_dc:
            raise RuntimeError("Spotify not authenticated — sp_dc not found")

        import httpx
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                _TOKEN_URL + _TOKEN_PARAMS,
                headers={
                    "Cookie": f"sp_dc={sp_dc}",
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()

        self._cached_token = data["accessToken"]
        expires_ms = data.get("accessTokenExpirationTimestampMs", 0)
        self._token_expires_at = expires_ms / 1000 if expires_ms else now + 3600
        logger.info("Spotify access token refreshed (expires in %.0fs)", self._token_expires_at - now)
        return self._cached_token

    async def ensure_authenticated(self, parent=None) -> str | None:
        sp_dc = await self.load_sp_dc()
        if sp_dc:
            return sp_dc
        return await self.login(parent)
