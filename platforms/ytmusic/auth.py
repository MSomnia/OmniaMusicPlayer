from __future__ import annotations
import asyncio
import logging
from PyQt6.QtWidgets import QWidget
from db.repository import AppRepository

logger = logging.getLogger(__name__)

_LOGIN_URL = "https://music.youtube.com"
# SAPISID is the primary Google auth cookie. It's also present under the
# __Secure-3PAPISID prefix on some clients, so we check for either.
_AUTH_COOKIES = {"SAPISID", "__Secure-3PAPISID", "__Secure-1PAPISID"}
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class YTMusicAuth:
    """Manages YouTube Music login via WebView cookie capture."""

    def __init__(self, repo: AppRepository) -> None:
        self._repo = repo

    async def load_auth(self) -> dict[str, str] | None:
        return await self._repo.load_credential("ytmusic")

    async def login(self, parent: QWidget | None = None) -> dict[str, str] | None:
        from ui.components.login_dialog import LoginDialog  # lazy: needs WebEngine

        loop = asyncio.get_event_loop()
        future: asyncio.Future[dict[str, str] | None] = loop.create_future()

        # target_cookies is empty so auto-close is driven ONLY by loadAllCookies
        # detecting an existing session or by the user clicking "我已登录".
        # capture_all_cookies=True accumulates every cookie for the Cookie header.
        dialog = LoginDialog(
            url=_LOGIN_URL,
            target_cookies=list(_AUTH_COOKIES),   # auto-close when any auth cookie seen
            title="YouTube Music — 登录",
            capture_all_cookies=True,
            show_done_button=True,
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
        if not cookies:
            logger.debug("YTMusic login cancelled — no cookies captured")
            return None

        has_auth = bool(_AUTH_COOKIES & cookies.keys())
        if not has_auth:
            logger.warning(
                "YTMusic login: no auth cookie found. Captured keys: %s",
                list(cookies.keys())[:10],
            )
            # Still proceed — user explicitly clicked Done; maybe cookies are named
            # differently on their account. ytmusicapi will fail gracefully if auth is invalid.

        headers = self._build_headers(cookies)
        await self._repo.save_credential("ytmusic", headers)
        logger.info("YTMusic credentials saved (%d cookies)", len(cookies))
        return headers

    async def ensure_authenticated(
        self, parent: QWidget | None = None
    ) -> dict[str, str] | None:
        existing = await self.load_auth()
        if existing and existing.get("Cookie"):
            return existing
        return await self.login(parent)

    @staticmethod
    def _build_headers(cookies: dict[str, str]) -> dict[str, str]:
        """Build a ytmusicapi-compatible headers dict from captured cookies."""
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        return {
            "User-Agent": _USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/json",
            "X-Goog-AuthUser": "0",
            "x-origin": "https://music.youtube.com",
            "Cookie": cookie_str,
        }
