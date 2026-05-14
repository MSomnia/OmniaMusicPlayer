import sys
import pytest
from unittest.mock import MagicMock, patch


def _make_handler(ctrl=None):
    from core.macos_media import MacOSMediaHandler
    return MacOSMediaHandler(ctrl or MagicMock())


def _track():
    from core.models import Track
    return Track(
        id="t1", platform="netease", title="Song", artist="Artist",
        artists=["Artist"], album="Album", album_cover_url="",
        duration_ms=180_000,
    )


# ── 无 PyObjC 时（_AVAILABLE=False）：全部静默 ─────────────────────────────────

def test_update_full_noop_when_unavailable():
    with patch("core.macos_media._AVAILABLE", False):
        h = _make_handler()
        h.update_full(_track(), 5000, True)   # must not raise
        assert h._current_track is None       # not set when unavailable


def test_update_position_noop_when_unavailable():
    with patch("core.macos_media._AVAILABLE", False):
        h = _make_handler()
        h.update_position(5000, True)   # must not raise


# ── _current_track 状态 ──────────────────────────────────────────────────────

def test_update_full_sets_current_track():
    t = _track()
    with patch("core.macos_media._AVAILABLE", True):
        h = _make_handler()
        with patch.object(h, "_update_now_playing"), \
             patch.object(h, "_set_playback_state"):
            h.update_full(t, 5000, True)
        assert h._current_track == t


def test_update_full_clears_current_track_on_none():
    with patch("core.macos_media._AVAILABLE", True):
        h = _make_handler()
        with patch.object(h, "_clear"):
            h.update_full(None, 0, False)
        assert h._current_track is None


def test_update_position_noop_when_no_track():
    with patch("core.macos_media._AVAILABLE", True):
        h = _make_handler()
        # _current_track is None by default
        with patch.object(h, "_set_playback_state") as mock_state:
            h.update_position(5000, True)
            mock_state.assert_not_called()


# ── update_full が正しいメソッドを呼ぶ ───────────────────────────────────────

def test_update_full_calls_update_now_playing_and_set_state():
    t = _track()
    with patch("core.macos_media._AVAILABLE", True):
        h = _make_handler()
        with patch.object(h, "_update_now_playing") as mock_upd, \
             patch.object(h, "_set_playback_state") as mock_state:
            h.update_full(t, 3000, True)
        mock_upd.assert_called_once_with(t, 3000, True)
        mock_state.assert_called_once_with(True)


def test_update_full_calls_clear_when_track_is_none():
    with patch("core.macos_media._AVAILABLE", True):
        h = _make_handler()
        with patch.object(h, "_clear") as mock_clear:
            h.update_full(None, 0, False)
        mock_clear.assert_called_once()


# ── update_position が位置更新メソッドを呼ぶ ─────────────────────────────────

def test_update_position_calls_set_playback_state_when_track_set():
    t = _track()
    with patch("core.macos_media._AVAILABLE", True):
        h = _make_handler()
        h._current_track = t
        mock_center = MagicMock()
        mock_center.nowPlayingInfo.return_value = {}
        mock_mp = MagicMock()
        mock_mp.MPNowPlayingInfoCenter.defaultCenter.return_value = mock_center
        mock_mp.MPNowPlayingInfoPropertyElapsedPlaybackTime = "elapsed"
        mock_mp.MPNowPlayingInfoPropertyPlaybackRate = "rate"
        with patch.dict("sys.modules", {"MediaPlayer": mock_mp}), \
             patch.object(h, "_set_playback_state") as mock_state:
            h.update_position(9000, False)
        mock_state.assert_called_once_with(False)


# ── macOS menu bar status item ───────────────────────────────────────────────

def test_format_status_title_playing():
    h = _make_handler()
    assert h._format_status_title(_track(), True) == "♪ Song - Artist"


def test_format_status_title_paused():
    h = _make_handler()
    assert h._format_status_title(_track(), False) == "Ⅱ Song - Artist"


def test_format_status_title_scrolls_long_song_in_short_window():
    from core.models import Track
    t = Track(
        id="t2", platform="netease",
        title="This Song Title Is Far Longer Than The Menu Bar Should Carry",
        artist="A Very Long Artist", artists=["A Very Long Artist"],
        album="Album", album_cover_url="", duration_ms=180_000,
    )
    h = _make_handler()
    first = h._format_status_title(t, True, offset=0)
    second = h._format_status_title(t, True, offset=5)
    assert first.startswith("♪ This Song Title")
    assert second.startswith("♪ Song Title")
    assert "…" not in first
    assert len(first) <= 25
    assert len(second) <= 25


def test_status_text_should_scroll_only_for_long_titles():
    from core.models import Track
    long_track = Track(
        id="t2", platform="netease",
        title="This Song Title Is Far Longer Than The Menu Bar Should Carry",
        artist="A Very Long Artist", artists=["A Very Long Artist"],
        album="Album", album_cover_url="", duration_ms=180_000,
    )
    h = _make_handler()
    assert not h._status_text_should_scroll(_track())
    assert h._status_text_should_scroll(long_track)


def test_update_full_updates_status_item_even_when_media_unavailable():
    t = _track()
    status_item = MagicMock()
    button = MagicMock()
    status_item.button.return_value = button
    with patch("core.macos_media._AVAILABLE", False):
        h = _make_handler()
        h._status_item = status_item
        with patch.object(h, "_set_status_visible") as mock_visible:
            h.update_full(t, 5000, True)
    button.setTitle_.assert_called_once_with("♪ Song - Artist")
    button.setToolTip_.assert_called_once_with("Song\nArtist\nAlbum")
    mock_visible.assert_called_once_with(True)
    assert h._current_track is None


def test_update_full_hides_status_item_when_track_is_none_and_media_unavailable():
    status_item = MagicMock()
    with patch("core.macos_media._AVAILABLE", False):
        h = _make_handler()
        h._status_item = status_item
        with patch.object(h, "_set_status_visible") as mock_visible:
            h.update_full(None, 0, False)
    mock_visible.assert_called_once_with(False)
