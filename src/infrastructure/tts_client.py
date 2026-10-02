from __future__ import annotations

import os
from pathlib import Path

import numpy as np


VOICES = {
    "American Female — Heart": "af_heart",
    "American Female — Bella": "af_bella",
    "American Female — Nicole": "af_nicole",
    "American Male — Adam": "am_adam",
    "American Male — Michael": "am_michael",
    "British Female — Emma": "bf_emma",
    "British Male — George": "bm_george",
}

SAMPLE_RATE = 24000


class TTSClient:
    def __init__(self, default_voice: str = "af_heart", speed: float = 0.95) -> None:
        self.default_voice = default_voice
        self.speed = speed
        self._pipeline = None

    @staticmethod
    def is_available() -> bool:
        try:
            import kokoro  # noqa
            import soundfile  # noqa
            return True
        except ImportError:
            return False

    def _get_pipeline(self):
        if self._pipeline is None:
            from kokoro import KPipeline
            self._pipeline = KPipeline(lang_code="a")
        return self._pipeline

    def generate(self, text: str, dest: Path, voice: str | None = None) -> tuple[Path, float]:
        """
        Synthesize text to a WAV file at dest.
        Returns (path, duration_seconds).
        """
        import soundfile as sf

        voice = voice or self.default_voice
        dest.parent.mkdir(parents=True, exist_ok=True)

        pipeline = self._get_pipeline()
        chunks = []
        for _, _, audio in pipeline(text, voice=voice, speed=self.speed):
            chunks.append(audio)

        full_audio = np.concatenate(chunks)
        sf.write(str(dest), full_audio, SAMPLE_RATE)

        duration = len(full_audio) / SAMPLE_RATE
        return dest, duration
