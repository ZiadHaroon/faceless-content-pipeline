from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.domain.models import Platform, Slide, WordTiming

FPS = 30
FONT_SIZE = 60
CAPTION_Y_RATIO = 0.80          # vertical position — 80% down the frame
CAPTION_COLOR = "white"
CAPTION_BOX_COLOR = "0x000000@0.5"
CAPTION_BOX_BORDER = 10

# How many words to show at once in karaoke mode
WORDS_PER_GROUP = 3

# ── Platform export presets ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ExportPreset:
    platform: Platform
    width: int
    height: int
    video_bitrate: str   # ffmpeg -b:v value, e.g. "8M"
    codec: str           # ffmpeg -c:v value, e.g. "libx264"


EXPORT_PRESETS: dict[Platform, ExportPreset] = {
    Platform.youtube:   ExportPreset(Platform.youtube,   1080, 1920, "8M", "libx264"),
    Platform.tiktok:    ExportPreset(Platform.tiktok,    1080, 1920, "6M", "libx264"),
    Platform.instagram: ExportPreset(Platform.instagram, 1080, 1920, "6M", "libx264"),
    Platform.facebook:  ExportPreset(Platform.facebook,  1080, 1920, "6M", "libx264"),
}

DEFAULT_PRESET: ExportPreset = EXPORT_PRESETS[Platform.youtube]

# Karaoke timing weights
_PUNCTUATION_WEIGHT = 1.15      # words ending in , or . get +15% duration
_FUNCTION_WORD_WEIGHT = 0.90    # short function words get -10% duration
_FUNCTION_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be",
    "to", "of", "in", "it", "at", "as", "or", "on",
})


class AssemblyService:
    def __init__(self, output_dir: Path, fps: int = FPS) -> None:
        self._output_dir = output_dir
        self._fps = fps

    # ── Pure logic — fully unit-testable ─────────────────────────────────────

    def slide_duration(self, slide: Slide, tail: float = 0.1) -> float:
        """Display duration for one slide: audio length + tail gap."""
        return (slide.audio_duration_seconds or 0.0) + tail

    def compute_slide_offsets(self, slides: list[Slide], tail: float = 0.1) -> list[float]:
        """
        Return the global start time (seconds) for each slide in the final video.
        E.g. [0.0, 4.3, 9.1, ...].
        """
        offsets: list[float] = []
        cursor = 0.0
        for slide in slides:
            offsets.append(cursor)
            cursor += self.slide_duration(slide, tail)
        return offsets

    def build_caption_filter(
        self, slides: list[Slide], tail: float = 0.1
    ) -> str:
        """
        Build an ffmpeg drawtext filter chain for all word timings across all slides.
        Returns an empty string if no slide has word_timings (captions skipped).

        Each word is shown individually (karaoke style). Global timestamps are
        computed by adding the slide's start offset to each word's relative timing.
        """
        offsets = self.compute_slide_offsets(slides, tail)
        filters: list[str] = []

        for slide, offset in zip(slides, offsets):
            if not slide.word_timings:
                continue
            for wt in slide.word_timings:
                global_start = round(offset + wt.start_seconds, 4)
                global_end = round(offset + wt.end_seconds, 4)
                safe_word = wt.word.replace("'", "\\'").replace(":", "\\:")
                filters.append(
                    f"drawtext=text='{safe_word}'"
                    f":fontsize={FONT_SIZE}"
                    f":fontcolor={CAPTION_COLOR}"
                    f":x=(w-text_w)/2"
                    f":y=h*{CAPTION_Y_RATIO}"
                    f":box=1:boxcolor={CAPTION_BOX_COLOR}:boxborderw={CAPTION_BOX_BORDER}"
                    f":enable='between(t,{global_start},{global_end})'"
                )

        return ",".join(filters)

    def compute_word_timings(
        self, narration: str, audio_duration_seconds: float
    ) -> list[WordTiming]:
        """
        Proportional timing algorithm for karaoke captions.

        Each word gets a share of ``audio_duration_seconds`` proportional to its
        character length (punctuation stripped for the base count).  Two rhythm
        adjustments are then applied:

        - Words ending in ``,`` or ``.`` → +15 % (pause after punctuation).
        - Short function words (``a``, ``the``, ``is``, …) → −10 %.

        Returns an empty list when ``narration`` is blank or ``audio_duration_seconds``
        is non-positive.
        """
        words = narration.split()
        if not words or audio_duration_seconds <= 0:
            return []

        weights: list[float] = []
        for word in words:
            clean = word.strip(".,!?;:")
            w = float(max(len(clean), 1))
            if word and word[-1] in (",", "."):
                w *= _PUNCTUATION_WEIGHT
            if clean.lower() in _FUNCTION_WORDS:
                w *= _FUNCTION_WORD_WEIGHT
            weights.append(w)

        total = sum(weights)
        timings: list[WordTiming] = []
        cursor = 0.0
        for word, weight in zip(words, weights):
            duration = (weight / total) * audio_duration_seconds
            timings.append(WordTiming(
                word=word,
                start_seconds=round(cursor, 4),
                end_seconds=round(cursor + duration, 4),
            ))
            cursor += duration

        return timings

    # ── Assembly — MoviePy + ffmpeg, lazy imports, manual-tested ─────────────

    def assemble(
        self,
        slides: list[Slide],
        video_id: int,
        output_path: Optional[Path] = None,
        tail: float = 0.1,
        music_path: Optional[Path] = None,
        platform: Platform = Platform.youtube,
    ) -> Path:
        """
        Concatenate slide images + audio into an MP4 with the platform export preset.

        The platform preset controls resolution (1080×1920), bitrate, and codec.
        If any slide has word_timings, captions are burned in the same ffmpeg pass.
        Returns path to the final MP4.
        """
        from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips

        self._output_dir.mkdir(parents=True, exist_ok=True)

        if output_path is None:
            output_path = self._output_dir / f"video_{video_id}.mp4"

        raw_path = self._output_dir / f"video_{video_id}_raw.mp4"

        clips = []
        for slide in slides:
            duration = self.slide_duration(slide, tail)
            clip = ImageClip(str(slide.image_path)).set_duration(duration).set_fps(self._fps)
            if slide.audio_path:
                audio = AudioFileClip(str(slide.audio_path))
                clip = clip.set_audio(audio)
            clips.append(clip)

        final = concatenate_videoclips(clips, method="compose")

        if music_path and music_path.exists():
            from moviepy.editor import AudioFileClip, CompositeAudioClip
            music = AudioFileClip(str(music_path)).volumex(0.08).audio_loop(duration=final.duration)
            if final.audio:
                from moviepy.editor import CompositeAudioClip
                final = final.set_audio(CompositeAudioClip([final.audio, music]))
            else:
                final = final.set_audio(music)

        final.write_videofile(
            str(raw_path),
            codec="libx264",
            audio_codec="aac",
            fps=self._fps,
            logger=None,
        )

        preset = EXPORT_PRESETS[platform]
        caption_filter = self.build_caption_filter(slides, tail)
        self._encode_final(raw_path, output_path, preset, caption_filter)
        raw_path.unlink(missing_ok=True)

        return output_path

    @staticmethod
    def _encode_final(
        input_path: Path,
        output_path: Path,
        preset: ExportPreset,
        caption_filter: str = "",
    ) -> None:
        """
        Re-encode with ffmpeg applying the platform preset (scale, bitrate, codec).
        If ``caption_filter`` is non-empty, it is appended to the video filter chain
        so captions are burned in the same pass.
        """
        import subprocess

        vf = f"scale={preset.width}:{preset.height}"
        if caption_filter:
            vf = f"{vf},{caption_filter}"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", vf,
            "-c:v", preset.codec,
            "-b:v", preset.video_bitrate,
            "-c:a", "copy",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg encode failed:\n{result.stderr.decode()}"
            )
