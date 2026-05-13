from __future__ import annotations
import asyncio
from PyQt6.QtWidgets import QWidget
from db.repository import AppRepository

_NETEASE_LOGIN_URL = "https://music.163.com/#/login"
_TARGET_COOKIES = ["MUSIC_U", "__csrf"]


class NeteaseAuth:
    """Manages Netease login flow and credential persistence."""

    def __init__(self, repo: AppRepository) -> None:
        self._repo = repo

    async def load_cookies(self) -> dict[str, str] | None:
        cred = await self._repo.load_credential("netease")
        return cred

    async def login(self, parent: QWidget | None = None) -> dict[str, str] | None:
        from ui.components.login_dialog import LoginDialog  # lazy: needs WebEngine
        loop = asyncio.get_event_loop()
        future: asyncio.Future[dict[str, str] | None] = loop.create_future()

        dialog = LoginDialog(
            url=_NETEASE_LOGIN_URL,
            target_cookies=_TARGET_COOKIES,
            title="网易云音乐 — 登录",
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
        if cookies:
            await self._repo.save_credential("netease", cookies)
        return cookies

    async def logout(self) -> None:
        await self._repo.delete_credential("netease")

    async def get_display_name(self) -> str | None:
        cred = await self._repo.load_credential("netease")
        if not cred:
            return None
        cookie_str = "; ".join(f"{k}={v}" for k, v in cred.items())
        try:
            import httpx
            from platforms.netease.proxy_client import DEFAULT_PROXY_URL
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{DEFAULT_PROXY_URL}/user/account",
                    params={"cookie": cookie_str},
                    timeout=5.0,
                )
                resp.raise_for_status()
                data = resp.json()
            return data.get("profile", {}).get("nickname")
        except Exception:
            return None

    async def ensure_authenticated(
        self, parent: QWidget | None = None
    ) -> dict[str, str] | None:
        existing = await self.load_cookies()
        if existing and existing.get("MUSIC_U"):
            return existing
        return await self.login(parent)
