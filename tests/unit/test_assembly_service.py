from pathlib import Path

import pytest

from src.domain.models import Slide, WordTiming
from src.services.assembly import AssemblyService


# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_service(tmp_path: Path) -> AssemblyService:
    return AssemblyService(output_dir=tmp_path)


def make_slide(
    slide_number: int = 1,
    audio_duration: float | None = 4.0,
    word_timings: list[WordTiming] | None = None,
) -> Slide:
    return Slide(
        slide_number=slide_number,
        narration="Test narration.",
        search_query="test query",
        audio_path=f"/fake/slide{slide_number}.wav",
        audio_duration_seconds=audio_duration,
        word_timings=word_timings,
    )


def make_word_timing(word: str, start: float, end: float) -> WordTiming:
    return WordTiming(word=word, start_seconds=start, end_seconds=end)


# ── slide_duration tests ──────────────────────────────────────────────────────


def test_slide_duration_adds_tail(tmp_path):
    service = make_service(tmp_path)
    slide = make_slide(audio_duration=4.0)
    assert service.slide_duration(slide, tail=0.1) == pytest.approx(4.1)


def test_slide_duration_default_tail_is_0_1(tmp_path):
    service = make_service(tmp_path)
    slide = make_slide(audio_duration=5.0)
    assert service.slide_duration(slide) == pytest.approx(5.1)


def test_slide_duration_falls_back_to_tail_when_no_audio(tmp_path):
    service = make_service(tmp_path)
    slide = make_slide(audio_duration=None)
    assert service.slide_duration(slide, tail=0.1) == pytest.approx(0.1)


def test_slide_duration_custom_tail(tmp_path):
    service = make_service(tmp_path)
    slide = make_slide(audio_duration=3.0)
    assert service.slide_duration(slide, tail=0.5) == pytest.approx(3.5)


# ── compute_slide_offsets tests ───────────────────────────────────────────────


def test_first_slide_offset_is_zero(tmp_path):
    service = make_service(tmp_path)
    slides = [make_slide(1, audio_duration=4.0)]
    offsets = service.compute_slide_offsets(slides, tail=0.0)
    assert offsets[0] == pytest.approx(0.0)


def test_second_slide_offset_equals_first_duration(tmp_path):
    service = make_service(tmp_path)
    slides = [make_slide(1, audio_duration=4.0), make_slide(2, audio_duration=3.0)]
    offsets = service.compute_slide_offsets(slides, tail=0.0)
    assert offsets[1] == pytest.approx(4.0)


def test_offsets_accumulate_correctly(tmp_path):
    service = make_service(tmp_path)
    slides = [
        make_slide(1, audio_duration=4.0),
        make_slide(2, audio_duration=3.0),
        make_slide(3, audio_duration=5.0),
    ]
    offsets = service.compute_slide_offsets(slides, tail=0.0)
    assert offsets == [pytest.approx(0.0), pytest.approx(4.0), pytest.approx(7.0)]


def test_offsets_include_tail(tmp_path):
    service = make_service(tmp_path)
    slides = [make_slide(1, audio_duration=4.0), make_slide(2, audio_duration=3.0)]
    offsets = service.compute_slide_offsets(slides, tail=0.1)
    assert offsets[1] == pytest.approx(4.1)


def test_offsets_empty_slides_returns_empty(tmp_path):
    service = make_service(tmp_path)
    assert service.compute_slide_offsets([]) == []


# ── build_caption_filter tests ────────────────────────────────────────────────


def test_build_caption_filter_empty_when_no_timings(tmp_path):
    service = make_service(tmp_path)
    slides = [make_slide(1), make_slide(2)]
    assert service.build_caption_filter(slides) == ""


def test_build_caption_filter_contains_word(tmp_path):
    service = make_service(tmp_path)
    wt = make_word_timing("quantum", 0.0, 0.5)
    slides = [make_slide(1, word_timings=[wt])]
    result = service.build_caption_filter(slides, tail=0.0)
    assert "quantum" in result


def test_build_caption_filter_uses_global_offset(tmp_path):
    service = make_service(tmp_path)
    # Slide 1 is 4.0s, so slide 2's words start at 4.0
    wt = make_word_timing("fiber", 1.0, 1.5)
    slides = [
        make_slide(1, audio_duration=4.0),
        make_slide(2, audio_duration=3.0, word_timings=[wt]),
    ]
    result = service.build_caption_filter(slides, tail=0.0)
    # Word starts at 4.0 (slide offset) + 1.0 (word offset) = 5.0
    assert "between(t,5.0,5.5)" in result


def test_build_caption_filter_multiple_words(tmp_path):
    service = make_service(tmp_path)
    timings = [
        make_word_timing("your", 0.0, 0.3),
        make_word_timing("phone", 0.3, 0.7),
        make_word_timing("lies", 0.7, 1.1),
    ]
    slides = [make_slide(1, audio_duration=4.0, word_timings=timings)]
    result = service.build_caption_filter(slides, tail=0.0)
    assert "your" in result
    assert "phone" in result
    assert "lies" in result


def test_build_caption_filter_escapes_apostrophes(tmp_path):
    service = make_service(tmp_path)
    wt = make_word_timing("it's", 0.0, 0.4)
    slides = [make_slide(1, word_timings=[wt])]
    result = service.build_caption_filter(slides, tail=0.0)
    assert "it\\'s" in result


def test_build_caption_filter_skips_slides_without_timings(tmp_path):
    service = make_service(tmp_path)
    wt = make_word_timing("hello", 0.0, 0.3)
    slides = [
        make_slide(1, audio_duration=4.0),                      # no timings
        make_slide(2, audio_duration=3.0, word_timings=[wt]),    # has timings
    ]
    result = service.build_caption_filter(slides, tail=0.0)
    # Only one drawtext block — from slide 2
    assert result.count("drawtext") == 1
