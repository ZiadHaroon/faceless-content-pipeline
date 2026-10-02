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


# ── compute_word_timings tests ────────────────────────────────────────────────


def test_word_timings_empty_narration_returns_empty(tmp_path):
    service = make_service(tmp_path)
    assert service.compute_word_timings("", 5.0) == []


def test_word_timings_zero_duration_returns_empty(tmp_path):
    service = make_service(tmp_path)
    assert service.compute_word_timings("hello world", 0.0) == []


def test_word_timings_negative_duration_returns_empty(tmp_path):
    service = make_service(tmp_path)
    assert service.compute_word_timings("hello world", -1.0) == []


def test_word_timings_count_matches_word_count(tmp_path):
    service = make_service(tmp_path)
    timings = service.compute_word_timings("your phone lies to you", 5.0)
    assert len(timings) == 5


def test_word_timings_first_word_starts_at_zero(tmp_path):
    service = make_service(tmp_path)
    timings = service.compute_word_timings("hello world", 4.0)
    assert timings[0].start_seconds == pytest.approx(0.0)


def test_word_timings_total_duration_matches_audio(tmp_path):
    service = make_service(tmp_path)
    audio_duration = 7.3
    timings = service.compute_word_timings("quantum computing changes everything now", audio_duration)
    total = timings[-1].end_seconds - timings[0].start_seconds
    assert total == pytest.approx(audio_duration, rel=1e-4)


def test_word_timings_contiguous(tmp_path):
    """Each word's start_seconds equals the previous word's end_seconds."""
    service = make_service(tmp_path)
    timings = service.compute_word_timings("your phone lies to you daily", 6.0)
    for i in range(1, len(timings)):
        assert timings[i].start_seconds == pytest.approx(timings[i - 1].end_seconds, rel=1e-4)


def test_word_timings_single_word_spans_full_duration(tmp_path):
    service = make_service(tmp_path)
    timings = service.compute_word_timings("quantum", 3.5)
    assert timings[0].start_seconds == pytest.approx(0.0)
    assert timings[0].end_seconds == pytest.approx(3.5)


def test_word_timings_longer_word_gets_more_time(tmp_path):
    """'quantum' (7 chars) should get more time than 'a' (1 char)."""
    service = make_service(tmp_path)
    timings = service.compute_word_timings("quantum a", 4.0)
    quantum_dur = timings[0].end_seconds - timings[0].start_seconds
    a_dur = timings[1].end_seconds - timings[1].start_seconds
    assert quantum_dur > a_dur


def test_word_timings_punctuated_word_gets_more_time_than_plain(tmp_path):
    """'battery.' should be longer than 'battery' given equal char lengths."""
    service = make_service(tmp_path)
    # Two identical words side by side — the punctuated one should be longer
    timings_plain = service.compute_word_timings("battery battery", 4.0)
    timings_punct = service.compute_word_timings("battery. battery", 4.0)
    plain_first = timings_plain[0].end_seconds - timings_plain[0].start_seconds
    punct_first = timings_punct[0].end_seconds - timings_punct[0].start_seconds
    assert punct_first > plain_first


def test_word_timings_function_word_gets_less_time(tmp_path):
    """'the' (function word) should get less time than 'cat' (same char count, non-function)."""
    service = make_service(tmp_path)
    timings = service.compute_word_timings("the cat", 4.0)
    the_dur = timings[0].end_seconds - timings[0].start_seconds
    cat_dur = timings[1].end_seconds - timings[1].start_seconds
    assert the_dur < cat_dur


def test_word_timings_preserves_original_words_including_punctuation(tmp_path):
    """WordTiming.word must be the original token, not the stripped version."""
    service = make_service(tmp_path)
    timings = service.compute_word_timings("battery, depletes.", 3.0)
    assert timings[0].word == "battery,"
    assert timings[1].word == "depletes."


def test_word_timings_words_stored_correctly(tmp_path):
    service = make_service(tmp_path)
    timings = service.compute_word_timings("hello world", 2.0)
    assert timings[0].word == "hello"
    assert timings[1].word == "world"
