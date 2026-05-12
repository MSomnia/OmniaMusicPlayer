from __future__ import annotations
import io
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    import soundfile as sf
except ImportError:
    sf = None  # type: ignore[assignment]
    logger.warning("soundfile not installed — Spotify audio decode unavailable")

try:
    from librespot.core import Session
    from librespot.metadata import TrackId
    from librespot.audio.decoders import AudioQuality, VorbisOnlyAudioQuality
    _LIBRESPOT_AVAILABLE = True
except Exception as _err:
    _LIBRESPOT_AVAILABLE = False
    logger.warning("librespot-python unavailable: %s", _err)


class LibrespotBridge:
    """Manages a librespot-python Session and decodes Spotify tracks to PCM."""

    _CHUNK = 16384

    def __init__(self, creds_path: str) -> None:
        self._creds_path = creds_path
        self._session: "Session | None" = None

    def has_session(self) -> bool:
        return self._session is not None

    def create_session(
        self,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Create or restore a librespot Session.

        If creds_path exists: load stored credentials.
        Otherwise: username + password required for first-time auth.
        """
        if not _LIBRESPOT_AVAILABLE:
            raise RuntimeError("librespot-python is not installed")

        conf = (
            Session.Configuration.Builder()
            .set_stored_credential_file(self._creds_path)
            .build()
        )
        builder = Session.Builder(conf=conf)

        if Path(self._creds_path).exists():
            logger.info("Librespot: loading stored credentials from %s", self._creds_path)
            self._session = builder.stored_file().create()
        elif username and password:
            logger.info("Librespot: authenticating with username/password")
            self._session = builder.user_pass(username, password).create()
        else:
            raise RuntimeError(
                "No librespot credentials found. Login with username and password first."
            )

    def load_track(self, track_id_str: str) -> tuple[np.ndarray, int]:
        """Decrypt and decode a Spotify track → (float32 array, samplerate).

        Downloads the full track before returning (download-then-play model).
        Raises RuntimeError if no session or decode fails.
        """
        if self._session is None:
            raise RuntimeError("No session — call create_session() first")
        if not _LIBRESPOT_AVAILABLE:
            raise RuntimeError("librespot-python not installed")
        if sf is None:
            raise RuntimeError("soundfile not installed — cannot decode Ogg Vorbis")

        tid = TrackId.from_uri(f"spotify:track:{track_id_str}")
        loaded = self._session.content_feeder().load(
            tid,
            VorbisOnlyAudioQuality(AudioQuality.HIGH),
            False,
            None,
        )

        buf = io.BytesIO()
        audio_stream = loaded.input_stream.stream()
        while True:
            chunk = audio_stream.read(self._CHUNK)
            if not chunk:
                break
            buf.write(chunk)
        buf.seek(0)

        with sf.SoundFile(buf) as f:
            samplerate = f.samplerate
            audio_data = f.read(dtype="float32")

        # Ensure 2D (frames, channels)
        if audio_data.ndim == 1:
            audio_data = audio_data.reshape(-1, 1)

        logger.debug(
            "Loaded track %s: %d frames @ %dHz, %d ch",
            track_id_str, len(audio_data), samplerate, audio_data.shape[1],
        )
        return audio_data, samplerate

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None
