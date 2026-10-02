from __future__ import annotations

from pathlib import Path

from src.domain.models import Slide
from src.infrastructure.tts_client import TTSClient


class AudioService:
    def __init__(self, tts: TTSClient, output_dir: Path) -> None:
        self._tts = tts
        self._output_dir = output_dir

    def generate_for_slide(
        self, slide: Slide, video_id: int, voice: str | None = None
    ) -> Slide:
        """
        Generate a WAV file for one slide.
        Returns a copy of the slide with audio_path and audio_duration_seconds set.
        """
        dest = self._output_dir / f"video_{video_id}_slide{slide.slide_number}.wav"
        path, duration = self._tts.generate(slide.narration, dest, voice=voice)
        return slide.model_copy(update={
            "audio_path": str(path),
            "audio_duration_seconds": duration,
        })

    def generate_for_video(
        self, slides: list[Slide], video_id: int, voice: str | None = None
    ) -> list[Slide]:
        """
        Generate WAV files for every slide in order.
        Returns updated slides with audio_path and audio_duration_seconds populated.
        """
        return [self.generate_for_slide(slide, video_id, voice=voice) for slide in slides]
