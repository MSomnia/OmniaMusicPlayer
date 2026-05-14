import asyncio
import pytest
from unittest.mock import AsyncMock
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication
from core.models import Track, PlayerState


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


class _MockCtrl(QObject):
    state_changed = pyqtSignal(PlayerState)
    position_changed = pyqtSignal(int)
    search_results_ready = pyqtSignal(list)
    netease_auth_changed = pyqtSignal(bool)
    ytmusic_auth_changed = pyqtSignal(bool)
    spotify_auth_changed = pyqtSignal(bool)
    album_search_ready = pyqtSignal(str, list)

    def __init__(self):
        super().__init__()
        self.is_netease_authenticated = True
        self.is_ytmusic_authenticated = False
        self.is_spotify_authenticated = False
        self.search = AsyncMock(return_value=[])
        self.search_albums = AsyncMock()
        self.get_album_tracks = AsyncMock(return_value=[])
        self.play_track = AsyncMock()
        self.ensure_netease_auth = AsyncMock(return_value=True)
        self.ensure_ytmusic_auth = AsyncMock(return_value=True)
        self.ensure_spotify_auth = AsyncMock(return_value=True)

    def add_to_queue(self, track):
        pass


def _track(tid="1") -> Track:
    return Track(id=tid, platform="netease", title=f"Song {tid}",
                 artist="A", artists=["A"], album="Alb",
                 album_cover_url="", duration_ms=180_000)


def test_search_page_creates(qapp, qtbot):
    from ui.pages.search_page import SearchPage
    ctrl = _MockCtrl()
    w = SearchPage(ctrl)
    qtbot.addWidget(w)


def test_search_page_has_search_input(qapp, qtbot):
    from ui.pages.search_page import SearchPage
    ctrl = _MockCtrl()
    w = SearchPage(ctrl)
    qtbot.addWidget(w)
    assert w._search_input is not None


def test_search_platform_tabs_have_uniform_larger_size(qapp, qtbot):
    from ui.pages.search_page import SearchPage
    ctrl = _MockCtrl()
    w = SearchPage(ctrl)
    qtbot.addWidget(w)

    sizes = {btn.size() for btn in w._tab_btns.values()}
    assert len(sizes) == 1
    size = sizes.pop()
    assert size.width() == 132
    assert size.height() == 36


def test_search_results_signal_populates_list(qapp, qtbot):
    from ui.pages.search_page import SearchPage
    ctrl = _MockCtrl()
    w = SearchPage(ctrl)
    qtbot.addWidget(w)
    tracks = [_track("1"), _track("2")]
    ctrl.search_results_ready.emit(tracks)
    assert w._track_list._list.count() == 2


async def test_track_selected_calls_play_track(qapp, qtbot):
    from ui.pages.search_page import SearchPage
    ctrl = _MockCtrl()
    w = SearchPage(ctrl)
    qtbot.addWidget(w)
    t = _track("42")
    w._track_list.track_selected.emit(t)
    await asyncio.sleep(0)
    ctrl.play_track.assert_awaited_once_with(t)


async def test_do_search_calls_ctrl_search(qapp, qtbot):
    from ui.pages.search_page import SearchPage
    ctrl = _MockCtrl()
    w = SearchPage(ctrl)
    qtbot.addWidget(w)
    await w._do_search("hello")
    await asyncio.sleep(0)
    ctrl.search.assert_awaited_once_with("hello", platform="netease")
    ctrl.search_albums.assert_awaited_once_with("hello", platform="netease")


async def test_do_search_skips_empty_query(qapp, qtbot):
    from ui.pages.search_page import SearchPage
    ctrl = _MockCtrl()
    w = SearchPage(ctrl)
    qtbot.addWidget(w)
    await w._do_search("  ")
    ctrl.search.assert_not_awaited()


async def test_do_search_triggers_login_when_not_authenticated(qapp, qtbot):
    from ui.pages.search_page import SearchPage
    ctrl = _MockCtrl()
    ctrl.is_netease_authenticated = False
    w = SearchPage(ctrl)
    qtbot.addWidget(w)
    await w._do_search("hello")
    ctrl.ensure_netease_auth.assert_awaited_once()
