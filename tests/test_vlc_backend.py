import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_backend():
    mock_instance = MagicMock()
    mock_player = MagicMock()
    mock_instance.media_player_new.return_value = mock_player
    mock_player.event_manager.return_value = MagicMock()

    with patch("core.vlc_backend.vlc") as mock_vlc:
        mock_vlc.Instance.return_value = mock_instance
        mock_vlc.EventType = MagicMock()

        from core.vlc_backend import VLCBackend
        backend = VLCBackend()

    return backend, mock_instance, mock_player


def test_vlc_backend_play_calls_vlc(qapp):
    backend, mock_instance, mock_player = _make_backend()
    backend.play("https://example.com/audio.mp3")
    mock_instance.media_new.assert_called_once_with("https://example.com/audio.mp3")
    mock_player.play.assert_called_once()


def test_vlc_backend_pause_calls_vlc(qapp):
    backend, _, mock_player = _make_backend()
    backend.pause()
    mock_player.pause.assert_called_once()


def test_vlc_backend_stop_calls_vlc(qapp):
    backend, _, mock_player = _make_backend()
    backend.stop()
    mock_player.stop.assert_called_once()


def test_vlc_backend_set_volume(qapp):
    backend, _, mock_player = _make_backend()
    backend.set_volume(80)
    mock_player.audio_set_volume.assert_called_once_with(80)


def test_vlc_backend_seek(qapp):
    backend, _, mock_player = _make_backend()
    backend.seek(30000)
    mock_player.set_time.assert_called_once_with(30000)
