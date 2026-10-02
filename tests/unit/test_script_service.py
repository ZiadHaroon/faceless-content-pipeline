import json
from unittest.mock import MagicMock

import pytest

from src.domain.models import AudienceLevel, ExplanationDepth, HookStyle, ScriptRequest
from src.services.script import ScriptService


# ── Fixtures ─────────────────────────────────────────────────────────────────


def make_service(chat_return=None):
    """Return a ScriptService with a mocked OllamaClient."""
    ollama = MagicMock()
    if chat_return is not None:
        ollama.chat.return_value = chat_return
    return ScriptService(ollama=ollama), ollama


def make_request(**kwargs):
    defaults = dict(
        topic="How does Face ID work",
        audience=AudienceLevel.general,
        depth=ExplanationDepth.how,
        hook_style=HookStyle.counterintuitive,
    )
    return ScriptRequest(**{**defaults, **kwargs})


SAMPLE_RESPONSE = {
    "title": "How Face ID Actually Works",
    "target_duration_seconds": 55,
    "slides": [
        {
            "slide_number": 1,
            "narration": "Your face is a password that took Apple three years to crack.",
            "search_query": "face recognition smartphone unlock",
        },
        {
            "slide_number": 2,
            "narration": "A dot projector fires 30,000 invisible infrared dots onto your face.",
            "search_query": "infrared dot projector sensor",
        },
        {
            "slide_number": 3,
            "narration": "A flood illuminator then lights your face in infrared so a camera can map the dots.",
            "search_query": "infrared camera night vision",
        },
    ],
}


# ── build_prompt tests ────────────────────────────────────────────────────────


def test_build_prompt_contains_topic():
    service, _ = make_service()
    prompt = service.build_prompt(make_request(topic="Battery degradation"))
    assert "Battery degradation" in prompt


def test_build_prompt_injects_general_audience():
    service, _ = make_service()
    prompt = service.build_prompt(make_request(audience=AudienceLevel.general))
    assert "ELI15" in prompt
    assert "zero domain knowledge" in prompt


def test_build_prompt_injects_enthusiast_audience():
    service, _ = make_service()
    prompt = service.build_prompt(make_request(audience=AudienceLevel.enthusiast))
    assert "tech enthusiast" in prompt


def test_build_prompt_injects_technical_audience():
    service, _ = make_service()
    prompt = service.build_prompt(make_request(audience=AudienceLevel.technical))
    assert "technical professional" in prompt


def test_build_prompt_injects_what_depth():
    service, _ = make_service()
    prompt = service.build_prompt(make_request(depth=ExplanationDepth.what))
    assert "WHAT" in prompt
    assert "surface facts" in prompt


def test_build_prompt_injects_how_depth():
    service, _ = make_service()
    prompt = service.build_prompt(make_request(depth=ExplanationDepth.how))
    assert "HOW" in prompt
    assert "mechanism" in prompt


def test_build_prompt_injects_why_depth():
    service, _ = make_service()
    prompt = service.build_prompt(make_request(depth=ExplanationDepth.why))
    assert "WHY" in prompt
    assert "trade-offs" in prompt


def test_build_prompt_injects_stat_hook():
    service, _ = make_service()
    prompt = service.build_prompt(make_request(hook_style=HookStyle.stat))
    assert "STAT" in prompt
    assert "number or measurement" in prompt


def test_build_prompt_injects_counterintuitive_hook():
    service, _ = make_service()
    prompt = service.build_prompt(make_request(hook_style=HookStyle.counterintuitive))
    assert "COUNTERINTUITIVE" in prompt


def test_build_prompt_injects_question_hook():
    service, _ = make_service()
    prompt = service.build_prompt(make_request(hook_style=HookStyle.question))
    assert "QUESTION" in prompt
    assert "information gap" in prompt


def test_build_prompt_requests_search_query_not_image_prompt():
    service, _ = make_service()
    prompt = service.build_prompt(make_request())
    assert "search_query" in prompt
    assert "image_prompt" not in prompt


# ── generate tests ────────────────────────────────────────────────────────────


def test_generate_returns_slides(monkeypatch):
    service, ollama = make_service(chat_return=(SAMPLE_RESPONSE, "raw"))
    slides = service.generate(make_request())
    assert len(slides) == 3


def test_generate_slide_fields_are_populated():
    service, ollama = make_service(chat_return=(SAMPLE_RESPONSE, "raw"))
    slides = service.generate(make_request())
    assert slides[0].slide_number == 1
    assert slides[0].narration == "Your face is a password that took Apple three years to crack."
    assert slides[0].search_query == "face recognition smartphone unlock"


def test_generate_passes_prompt_to_ollama():
    service, ollama = make_service(chat_return=(SAMPLE_RESPONSE, "raw"))
    request = make_request(topic="VPN explained")
    service.generate(request)
    call_args = ollama.chat.call_args
    prompt_used = call_args[0][0]
    assert "VPN explained" in prompt_used


def test_generate_passes_model_override_to_ollama():
    service, ollama = make_service(chat_return=(SAMPLE_RESPONSE, "raw"))
    service.generate(make_request(), model="qwen2.5:7b")
    _, kwargs = ollama.chat.call_args
    assert kwargs.get("model") == "qwen2.5:7b"


def test_generate_raises_on_missing_slides_key():
    bad_response = {"title": "Something", "target_duration_seconds": 30}
    service, _ = make_service(chat_return=(bad_response, "raw"))
    with pytest.raises(KeyError):
        service.generate(make_request())


def test_generate_slides_have_no_image_path_yet():
    service, _ = make_service(chat_return=(SAMPLE_RESPONSE, "raw"))
    slides = service.generate(make_request())
    for slide in slides:
        assert slide.image_path is None
        assert slide.audio_path is None
        assert slide.pexels_photo_id is None
