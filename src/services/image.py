from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter

from src.domain.models import Slide
from src.infrastructure.pexels_client import PexelsClient, PexelsPhoto

# Target frame size — all platforms use 9:16 portrait
FRAME_WIDTH = 1080
FRAME_HEIGHT = 1920

# Overlay opacity: 0 = fully transparent, 255 = fully opaque
OVERLAY_ALPHA = 140


class ImageService:
    def __init__(
        self,
        pexels: PexelsClient,
        output_dir: Path,
        overlay_color: str = "#1a1a2e",
    ) -> None:
        self._pexels = pexels
        self._output_dir = output_dir
        self._overlay_color = overlay_color

    def search(self, query: str, per_page: int = 5) -> list[PexelsPhoto]:
        """Search Pexels and return up to per_page portrait photos."""
        return self._pexels.search(query, per_page=per_page, orientation="portrait")

    def process_slide(
        self, slide: Slide, video_id: int, photo: PexelsPhoto
    ) -> Slide:
        """
        Download photo, apply branded overlay, save to disk.
        Returns a copy of the slide with image_path and pexels_photo_id set.
        """
        raw_path = self._output_dir / f"video_{video_id}_slide{slide.slide_number}_raw.jpg"
        self._pexels.download(photo, raw_path, size="large")

        treated_path = self._output_dir / f"video_{video_id}_slide{slide.slide_number}.jpg"
        with Image.open(raw_path) as img:
            treated = self.apply_overlay(img)
            treated.save(str(treated_path), "JPEG", quality=92)

        raw_path.unlink(missing_ok=True)

        return slide.model_copy(update={
            "pexels_photo_id": photo.id,
            "image_path": str(treated_path),
        })

    def apply_overlay(self, image: Image.Image) -> Image.Image:
        """
        Crop to 9:16, apply gaussian blur, then apply a semi-transparent
        color overlay. Returns a new RGB image at FRAME_WIDTH x FRAME_HEIGHT.
        """
        img = self._crop_to_portrait(image)
        img = img.filter(ImageFilter.GaussianBlur(radius=2))

        overlay = Image.new("RGBA", img.size, (*self._hex_to_rgb(self._overlay_color), OVERLAY_ALPHA))
        base = img.convert("RGBA")
        blended = Image.alpha_composite(base, overlay)
        return blended.convert("RGB")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _crop_to_portrait(image: Image.Image) -> Image.Image:
        """Resize and center-crop to FRAME_WIDTH x FRAME_HEIGHT."""
        target_ratio = FRAME_WIDTH / FRAME_HEIGHT
        src_ratio = image.width / image.height

        if src_ratio > target_ratio:
            # Image is wider than target — scale by height, crop sides
            new_height = FRAME_HEIGHT
            new_width = int(image.width * (FRAME_HEIGHT / image.height))
        else:
            # Image is taller than target — scale by width, crop top/bottom
            new_width = FRAME_WIDTH
            new_height = int(image.height * (FRAME_WIDTH / image.width))

        img = image.resize((new_width, new_height), Image.LANCZOS)

        left = (new_width - FRAME_WIDTH) // 2
        top = (new_height - FRAME_HEIGHT) // 2
        return img.crop((left, top, left + FRAME_WIDTH, top + FRAME_HEIGHT))

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
