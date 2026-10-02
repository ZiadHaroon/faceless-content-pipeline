from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.domain.models import Slide
from src.services.audio import AudioService


# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_service(output_dir: Path, duration: float = 4.2):
    tts = MagicMock()
    tts.generate.side_effect = lambda text, dest, voice=None: (dest, duration)
    return AudioService(tts=tts, output_dir=output_dir), tts


def make_slide(slide_number: int = 1, narration: str = "Test narration.") -> Slide:
    return Slide(
        slide_number=slide_number,
        narration=narration,
        search_query="test query",
    )


# ── generate_for_slide tests ──────────────────────────────────────────────────


def test_generate_for_slide_sets_audio_path(tmp_path):
    service, _ = make_service(tmp_path)
    result = service.generate_for_slide(make_slide(), video_id=1)
    assert result.audio_path is not None


def test_generate_for_slide_sets_duration(tmp_path):
    service, _ = make_service(tmp_path, duration=6.5)
    result = service.generate_for_slide(make_slide(), video_id=1)
    assert result.audio_duration_seconds == 6.5


def test_generate_for_slide_path_follows_naming_convention(tmp_path):
    service, _ = make_service(tmp_path)
    result = service.generate_for_slide(make_slide(slide_number=3), video_id=7)
    assert result.audio_path == str(tmp_path / "video_7_slide3.wav")


def test_generate_for_slide_passes_narration_to_tts(tmp_path):
    service, tts = make_service(tmp_path)
    slide = make_slide(narration="Quantum bits exist in superposition.")
    service.generate_for_slide(slide, video_id=1)
    text_arg = tts.generate.call_args[0][0]
    assert text_arg == "Quantum bits exist in superposition."


def test_generate_for_slide_passes_voice_override_to_tts(tmp_path):
    service, tts = make_service(tmp_path)
    service.generate_for_slide(make_slide(), video_id=1, voice="bm_george")
    _, kwargs = tts.generate.call_args
    assert kwargs.get("voice") == "bm_george"


def test_generate_for_slide_does_not_mutate_original(tmp_path):
    service, _ = make_service(tmp_path)
    slide = make_slide()
    result = service.generate_for_slide(slide, video_id=1)
    assert slide.audio_path is None
    assert slide.audio_duration_seconds is None
    assert result.audio_path is not None


# ── generate_for_video tests ──────────────────────────────────────────────────


def test_generate_for_video_processes_all_slides(tmp_path):
    service, tts = make_service(tmp_path)
    slides = [make_slide(i) for i in range(1, 5)]
    results = service.generate_for_video(slides, video_id=2)
    assert len(results) == 4
    assert tts.generate.call_count == 4


def test_generate_for_video_each_slide_has_audio(tmp_path):
    service, _ = make_service(tmp_path)
    slides = [make_slide(i) for i in range(1, 4)]
    results = service.generate_for_video(slides, video_id=1)
    for result in results:
        assert result.audio_path is not None
        assert result.audio_duration_seconds is not None


def test_generate_for_video_paths_are_unique(tmp_path):
    service, _ = make_service(tmp_path)
    slides = [make_slide(i) for i in range(1, 4)]
    results = service.generate_for_video(slides, video_id=1)
    paths = [r.audio_path for r in results]
    assert len(paths) == len(set(paths))


def test_generate_for_video_empty_slides_returns_empty(tmp_path):
    service, tts = make_service(tmp_path)
    results = service.generate_for_video([], video_id=1)
    assert results == []
    tts.generate.assert_not_called()
