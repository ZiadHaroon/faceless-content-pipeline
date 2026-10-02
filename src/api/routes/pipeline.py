from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_pipeline_service
from src.domain.models import Platform, ScriptRequest, Video
from src.services.pipeline import PipelineService

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class GenerateScriptRequest(BaseModel):
    request: ScriptRequest


class GenerateAudioRequest(BaseModel):
    voice: Optional[str] = None


class ApplyImageRequest(BaseModel):
    photo_id: int


class PublishRequest(BaseModel):
    platforms: Optional[list[Platform]] = None


class PexelsPhotoResult(BaseModel):
    id: int
    width: int
    height: int
    photographer: str
    url_medium: str
    url_tiny: str
    alt: str


def _handle(fn):
    """Wrap service calls and convert ValueError to 404."""
    try:
        return fn()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Script ────────────────────────────────────────────────────────────────────

@router.post("/{video_id}/generate-script", response_model=Video)
def generate_script(
    video_id: int,
    body: GenerateScriptRequest,
    svc: PipelineService = Depends(get_pipeline_service),
):
    return _handle(lambda: svc.generate_script(video_id, body.request))


@router.post("/{video_id}/approve-script", response_model=Video)
def approve_script(
    video_id: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    return _handle(lambda: svc.approve_script(video_id))


# ── Voiceover ─────────────────────────────────────────────────────────────────

@router.post("/{video_id}/generate-audio", response_model=Video)
def generate_audio(
    video_id: int,
    body: GenerateAudioRequest = GenerateAudioRequest(),
    svc: PipelineService = Depends(get_pipeline_service),
):
    return _handle(lambda: svc.generate_audio(video_id, voice=body.voice))


@router.post("/{video_id}/approve-voiceover", response_model=Video)
def approve_voiceover(
    video_id: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    return _handle(lambda: svc.approve_voiceover(video_id))


# ── Images ────────────────────────────────────────────────────────────────────

@router.get("/{video_id}/slides/{slide_number}/search-images", response_model=list[PexelsPhotoResult])
def search_images(
    video_id: int,
    slide_number: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    photos = _handle(lambda: svc.search_images(video_id, slide_number))
    return [
        PexelsPhotoResult(
            id=p.id,
            width=p.width,
            height=p.height,
            photographer=p.photographer,
            url_medium=p.url_medium,
            url_tiny=p.url_tiny,
            alt=p.alt,
        )
        for p in photos
    ]


@router.post("/{video_id}/slides/{slide_number}/apply-image", response_model=Video)
def apply_image(
    video_id: int,
    slide_number: int,
    body: ApplyImageRequest,
    svc: PipelineService = Depends(get_pipeline_service),
):
    return _handle(lambda: svc.apply_image(video_id, slide_number, body.photo_id))


@router.post("/{video_id}/generate-images-auto", response_model=Video)
def generate_images_auto(
    video_id: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    return _handle(lambda: svc.generate_images_auto(video_id))


@router.post("/{video_id}/advance-to-images", response_model=Video)
def advance_to_images(
    video_id: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    return _handle(lambda: svc.advance_to_images(video_id))


# ── Assembly ──────────────────────────────────────────────────────────────────

@router.post("/{video_id}/assemble", response_model=Video)
def assemble_video(
    video_id: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    return _handle(lambda: svc.assemble_video(video_id))


# ── Review / Publish ──────────────────────────────────────────────────────────

@router.post("/{video_id}/approve-final", response_model=Video)
def approve_final(
    video_id: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    return _handle(lambda: svc.approve_final(video_id))


@router.post("/{video_id}/publish", response_model=Video)
def publish(
    video_id: int,
    body: PublishRequest = PublishRequest(),
    svc: PipelineService = Depends(get_pipeline_service),
):
    return _handle(lambda: svc.publish(video_id, platforms=body.platforms))
