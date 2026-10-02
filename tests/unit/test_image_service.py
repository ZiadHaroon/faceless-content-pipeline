from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.domain.models import Slide
from src.infrastructure.pexels_client import PexelsPhoto
from src.services.image import FRAME_HEIGHT, FRAME_WIDTH, ImageService


# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_service(output_dir: Path, overlay_color: str = "#1a1a2e"):
    pexels = MagicMock()
    pexels.download.side_effect = lambda photo, dest, size="large": _write_fake_image(dest)
    return ImageService(pexels=pexels, output_dir=output_dir, overlay_color=overlay_color), pexels


def make_photo(photo_id: int = 42) -> PexelsPhoto:
    return PexelsPhoto({
        "id": photo_id,
        "width": 1080,
        "height": 1920,
        "photographer": "Test Photographer",
        "src": {
            "original": "https://example.com/original.jpg",
            "large2x": "https://example.com/large.jpg",
            "medium": "https://example.com/medium.jpg",
            "tiny": "https://example.com/tiny.jpg",
        },
        "alt": "Test photo",
    })


def make_slide(slide_number: int = 1) -> Slide:
    return Slide(
        slide_number=slide_number,
        narration="Test narration.",
        search_query="test search query",
    )


def _write_fake_image(dest: Path, width: int = 1080, height: int = 1920) -> Path:
    """Write a small solid-colour JPEG to dest so PIL.Image.open works."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    img.save(str(dest), "JPEG")
    return dest


# ── search tests ──────────────────────────────────────────────────────────────


def test_search_delegates_to_pexels_client(tmp_path):
    service, pexels = make_service(tmp_path)
    service.search("smartphone battery")
    pexels.search.assert_called_once_with(
        "smartphone battery", per_page=5, orientation="portrait"
    )


def test_search_passes_per_page_override(tmp_path):
    service, pexels = make_service(tmp_path)
    service.search("fiber optic cables", per_page=3)
    pexels.search.assert_called_once_with(
        "fiber optic cables", per_page=3, orientation="portrait"
    )


# ── process_slide tests ───────────────────────────────────────────────────────


def test_process_slide_sets_image_path(tmp_path):
    service, _ = make_service(tmp_path)
    result = service.process_slide(make_slide(), video_id=1, photo=make_photo())
    assert result.image_path is not None


def test_process_slide_sets_pexels_photo_id(tmp_path):
    service, _ = make_service(tmp_path)
    result = service.process_slide(make_slide(), video_id=1, photo=make_photo(photo_id=99))
    assert result.pexels_photo_id == 99


def test_process_slide_path_follows_naming_convention(tmp_path):
    service, _ = make_service(tmp_path)
    result = service.process_slide(make_slide(slide_number=3), video_id=7, photo=make_photo())
    assert result.image_path == str(tmp_path / "video_7_slide3.jpg")


def test_process_slide_saves_file_to_disk(tmp_path):
    service, _ = make_service(tmp_path)
    result = service.process_slide(make_slide(), video_id=1, photo=make_photo())
    assert Path(result.image_path).exists()


def test_process_slide_removes_raw_download(tmp_path):
    service, _ = make_service(tmp_path)
    service.process_slide(make_slide(slide_number=1), video_id=1, photo=make_photo())
    raw = tmp_path / "video_1_slide1_raw.jpg"
    assert not raw.exists()


def test_process_slide_does_not_mutate_original(tmp_path):
    service, _ = make_service(tmp_path)
    slide = make_slide()
    result = service.process_slide(slide, video_id=1, photo=make_photo())
    assert slide.image_path is None
    assert slide.pexels_photo_id is None
    assert result.image_path is not None


# ── apply_overlay tests ───────────────────────────────────────────────────────


def test_apply_overlay_returns_rgb_image(tmp_path):
    service, _ = make_service(tmp_path)
    img = Image.new("RGB", (1080, 1920), color=(200, 200, 200))
    result = service.apply_overlay(img)
    assert result.mode == "RGB"


def test_apply_overlay_output_is_portrait_frame(tmp_path):
    service, _ = make_service(tmp_path)
    img = Image.new("RGB", (1080, 1920), color=(200, 200, 200))
    result = service.apply_overlay(img)
    assert result.size == (FRAME_WIDTH, FRAME_HEIGHT)


def test_apply_overlay_darkens_image(tmp_path):
    service, _ = make_service(tmp_path, overlay_color="#000000")
    img = Image.new("RGB", (1080, 1920), color=(255, 255, 255))
    result = service.apply_overlay(img)
    pixel = result.getpixel((540, 960))
    assert all(c < 255 for c in pixel)


def test_apply_overlay_crops_landscape_to_portrait(tmp_path):
    service, _ = make_service(tmp_path)
    landscape = Image.new("RGB", (2560, 1440), color=(100, 100, 100))
    result = service.apply_overlay(landscape)
    assert result.size == (FRAME_WIDTH, FRAME_HEIGHT)


def test_hex_to_rgb_converts_correctly(tmp_path):
    service, _ = make_service(tmp_path)
    assert service._hex_to_rgb("#1a1a2e") == (26, 26, 46)
    assert service._hex_to_rgb("#ffffff") == (255, 255, 255)
    assert service._hex_to_rgb("#000000") == (0, 0, 0)
