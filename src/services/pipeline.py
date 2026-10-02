from __future__ import annotations

from src.domain.models import (
    PipelineStage,
    Platform,
    ScriptRequest,
    Video,
)
from src.infrastructure.pexels_client import PexelsPhoto
from src.repositories.base import VideoRepository
from src.services.audio import AudioService
from src.services.image import ImageService
from src.services.assembly import AssemblyService
from src.services.script import ScriptService


class PipelineService:
    def __init__(
        self,
        videos: VideoRepository,
        script: ScriptService,
        audio: AudioService,
        image: ImageService,
        assembly: AssemblyService,
    ) -> None:
        self._videos = videos
        self._script = script
        self._audio = audio
        self._image = image
        self._assembly = assembly

    # ── Script ────────────────────────────────────────────────────────────────

    def generate_script(self, video_id: int, request: ScriptRequest) -> Video:
        video = self._get_or_404(video_id)
        slides = self._script.generate(request)
        updated = video.model_copy(update={"slides": slides})
        return self._videos.update(updated)

    def approve_script(self, video_id: int) -> Video:
        video = self._get_or_404(video_id)
        updated = video.model_copy(update={
            "script_approved": True,
            "stage": PipelineStage.script,
        })
        return self._videos.update(updated)

    # ── Voiceover ─────────────────────────────────────────────────────────────

    def generate_audio(self, video_id: int, voice: str | None = None) -> Video:
        video = self._get_or_404(video_id)
        slides = self._audio.generate_for_video(video.slides, video_id, voice=voice)
        updated = video.model_copy(update={"slides": slides})
        return self._videos.update(updated)

    def approve_voiceover(self, video_id: int) -> Video:
        video = self._get_or_404(video_id)
        updated = video.model_copy(update={
            "voiceover_approved": True,
            "stage": PipelineStage.voiceover,
        })
        return self._videos.update(updated)

    # ── Images ────────────────────────────────────────────────────────────────

    def search_images(self, video_id: int, slide_number: int) -> list[PexelsPhoto]:
        """Return top 5 Pexels results for a slide's search_query."""
        video = self._get_or_404(video_id)
        slide = self._get_slide_or_404(video, slide_number)
        return self._image.search(slide.search_query)

    def apply_image(self, video_id: int, slide_number: int, photo_id: int) -> Video:
        """Download and process one slide's image by Pexels photo ID."""
        video = self._get_or_404(video_id)
        slide = self._get_slide_or_404(video, slide_number)
        photo = self._image._pexels.get_photo(photo_id)
        updated_slide = self._image.process_slide(slide, video_id, photo)
        slides = [updated_slide if s.slide_number == slide_number else s for s in video.slides]
        updated = video.model_copy(update={"slides": slides})
        return self._videos.update(updated)

    def generate_images_auto(self, video_id: int) -> Video:
        """Auto-select the top Pexels result for every slide."""
        video = self._get_or_404(video_id)
        slides = video.slides
        for i, slide in enumerate(slides):
            photos = self._image.search(slide.search_query, per_page=1)
            if photos:
                slides[i] = self._image.process_slide(slide, video_id, photos[0])
        updated = video.model_copy(update={
            "slides": slides,
            "stage": PipelineStage.images,
        })
        return self._videos.update(updated)

    def advance_to_images(self, video_id: int) -> Video:
        """Advance to images stage once all slides have an image_path."""
        video = self._get_or_404(video_id)
        updated = video.model_copy(update={"stage": PipelineStage.images})
        return self._videos.update(updated)

    # ── Assembly ──────────────────────────────────────────────────────────────

    def assemble_video(self, video_id: int) -> Video:
        video = self._get_or_404(video_id)
        self._assembly.assemble(video.slides, video_id)
        updated = video.model_copy(update={"stage": PipelineStage.assembly})
        return self._videos.update(updated)

    # ── Review / Publish ──────────────────────────────────────────────────────

    def approve_final(self, video_id: int) -> Video:
        video = self._get_or_404(video_id)
        updated = video.model_copy(update={
            "final_approved": True,
            "stage": PipelineStage.review,
        })
        return self._videos.update(updated)

    def publish(self, video_id: int, platforms: list[Platform] | None = None) -> Video:
        video = self._get_or_404(video_id)
        update: dict = {"stage": PipelineStage.published}
        if platforms:
            update["platforms"] = platforms
        updated = video.model_copy(update=update)
        return self._videos.update(updated)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_or_404(self, video_id: int) -> Video:
        video = self._videos.get_by_id(video_id)
        if video is None:
            raise ValueError(f"Video {video_id} not found")
        return video

    @staticmethod
    def _get_slide_or_404(video: Video, slide_number: int):
        for slide in video.slides:
            if slide.slide_number == slide_number:
                return slide
        raise ValueError(f"Slide {slide_number} not found on video {video.id}")
