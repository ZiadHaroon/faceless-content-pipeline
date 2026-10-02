from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.api.dependencies import get_pipeline_service, get_video_repo
from src.api.templating import templates
from src.domain.models import (
    AudienceLevel,
    ExplanationDepth,
    HookStyle,
    Platform,
    PipelineStage,
    ScriptRequest,
)
from src.infrastructure.tts_client import VOICES
from src.repositories.video import SQLiteVideoRepository
from src.services.pipeline import PipelineService

router = APIRouter()

_STAGES = [s.value for s in PipelineStage]


def _video_ctx(request: Request, video, expanded_panel: str | None = None) -> dict:
    """Build common template context for a video row."""
    all_audio_done = (
        bool(video.slides) and
        all(s.audio_duration_seconds is not None for s in video.slides)
    )
    all_images_done = (
        bool(video.slides) and
        all(s.image_path is not None for s in video.slides)
    )
    return {
        "request": request,
        "video": video,
        "expanded_panel": expanded_panel,
        "voices": VOICES,
        "platforms": list(Platform),
        "all_audio_done": all_audio_done,
        "all_images_done": all_images_done,
    }


def _panel_template(video) -> str:
    return f"partials/stage_panel/{video.stage.value}.html"


# ── Pages ──────────────────────────────────────────────────────────────────


@router.get("/", response_class=RedirectResponse)
def index():
    return RedirectResponse(url="/pipeline")


@router.get("/pipeline", response_class=HTMLResponse)
def pipeline_page(
    request: Request,
    stage: Optional[str] = None,
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    stage_filter = PipelineStage(stage) if stage else None
    videos = repo.get_all(stage=stage_filter)
    return templates.TemplateResponse("pipeline.html", {
        "request": request,
        "active_nav": "pipeline",
        "videos": videos,
        "stages": _STAGES,
        "current_stage": stage,
    })


# ── Video List Partial (HTMX filter swap) ─────────────────────────────────


@router.get("/pipeline/videos", response_class=HTMLResponse)
def video_list_partial(
    request: Request,
    stage: Optional[str] = None,
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    stage_filter = PipelineStage(stage) if stage else None
    videos = repo.get_all(stage=stage_filter)
    return templates.TemplateResponse("partials/video_list.html", {
        "request": request,
        "videos": videos,
        "current_stage": stage,
    })


@router.post("/pipeline/videos", response_class=HTMLResponse)
def create_video_html(
    request: Request,
    title: str = Form(...),
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    video = repo.create(title=title)
    return templates.TemplateResponse("partials/video_row.html", _video_ctx(request, video))


@router.delete("/pipeline/videos/{video_id}", response_class=HTMLResponse)
def delete_video_html(
    video_id: int,
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    repo.delete(video_id)
    return HTMLResponse("")


# ── Stage Panel Partial ───────────────────────────────────────────────────


@router.get("/pipeline/{video_id}/panel", response_class=HTMLResponse)
def stage_panel(
    request: Request,
    video_id: int,
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    video = repo.get_by_id(video_id)
    if video is None:
        return HTMLResponse("<p class='text-muted text-sm'>Video not found.</p>")
    return templates.TemplateResponse(
        _panel_template(video),
        _video_ctx(request, video),
    )


# ── Pipeline Actions ──────────────────────────────────────────────────────


@router.post("/pipeline/{video_id}/generate-script", response_class=HTMLResponse)
def generate_script_html(
    request: Request,
    video_id: int,
    audience: str = Form("general"),
    depth: str = Form("how"),
    hook_style: str = Form("counterintuitive"),
    svc: PipelineService = Depends(get_pipeline_service),
):
    script_req = ScriptRequest(
        topic=svc._videos.get_by_id(video_id).title,
        audience=AudienceLevel(audience),
        depth=ExplanationDepth(depth),
        hook_style=HookStyle(hook_style),
    )
    video = svc.generate_script(video_id, script_req)
    return templates.TemplateResponse(
        "partials/video_row.html",
        _video_ctx(request, video, expanded_panel=_panel_template(video)),
    )


@router.post("/pipeline/{video_id}/approve-script", response_class=HTMLResponse)
def approve_script_html(
    request: Request,
    video_id: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    video = svc.approve_script(video_id)
    return templates.TemplateResponse(
        "partials/video_row.html",
        _video_ctx(request, video, expanded_panel=_panel_template(video)),
    )


@router.post("/pipeline/{video_id}/generate-audio", response_class=HTMLResponse)
def generate_audio_html(
    request: Request,
    video_id: int,
    voice: Optional[str] = Form(None),
    svc: PipelineService = Depends(get_pipeline_service),
):
    video = svc.generate_audio(video_id, voice=voice or None)
    return templates.TemplateResponse(
        "partials/video_row.html",
        _video_ctx(request, video, expanded_panel=_panel_template(video)),
    )


@router.post("/pipeline/{video_id}/approve-voiceover", response_class=HTMLResponse)
def approve_voiceover_html(
    request: Request,
    video_id: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    video = svc.approve_voiceover(video_id)
    return templates.TemplateResponse(
        "partials/video_row.html",
        _video_ctx(request, video, expanded_panel=_panel_template(video)),
    )


@router.get("/pipeline/{video_id}/slides/{slide_number}/search-images-html", response_class=HTMLResponse)
def search_images_html(
    request: Request,
    video_id: int,
    slide_number: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    photos = svc.search_images(video_id, slide_number)
    video = svc._videos.get_by_id(video_id)
    slide = svc._get_slide_or_404(video, slide_number)
    return templates.TemplateResponse("partials/photo_results.html", {
        "request": request,
        "photos": photos,
        "video_id": video_id,
        "slide_number": slide_number,
        "query": slide.search_query,
    })


@router.post("/pipeline/{video_id}/slides/{slide_number}/apply-image-html", response_class=HTMLResponse)
def apply_image_html(
    request: Request,
    video_id: int,
    slide_number: int,
    photo_id: int = Form(...),
    svc: PipelineService = Depends(get_pipeline_service),
):
    video = svc.apply_image(video_id, slide_number, photo_id)
    return templates.TemplateResponse(
        "partials/video_row.html",
        _video_ctx(request, video, expanded_panel=_panel_template(video)),
    )


@router.post("/pipeline/{video_id}/generate-images-auto", response_class=HTMLResponse)
def generate_images_auto_html(
    request: Request,
    video_id: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    video = svc.generate_images_auto(video_id)
    return templates.TemplateResponse(
        "partials/video_row.html",
        _video_ctx(request, video, expanded_panel=_panel_template(video)),
    )


@router.post("/pipeline/{video_id}/advance-to-images", response_class=HTMLResponse)
def advance_to_images_html(
    request: Request,
    video_id: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    video = svc.advance_to_images(video_id)
    return templates.TemplateResponse(
        "partials/video_row.html",
        _video_ctx(request, video, expanded_panel=_panel_template(video)),
    )


@router.post("/pipeline/{video_id}/assemble", response_class=HTMLResponse)
def assemble_html(
    request: Request,
    video_id: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    video = svc.assemble_video(video_id)
    return templates.TemplateResponse(
        "partials/video_row.html",
        _video_ctx(request, video, expanded_panel=_panel_template(video)),
    )


@router.post("/pipeline/{video_id}/approve-final", response_class=HTMLResponse)
def approve_final_html(
    request: Request,
    video_id: int,
    svc: PipelineService = Depends(get_pipeline_service),
):
    video = svc.approve_final(video_id)
    return templates.TemplateResponse(
        "partials/video_row.html",
        _video_ctx(request, video, expanded_panel=_panel_template(video)),
    )


@router.post("/pipeline/{video_id}/publish", response_class=HTMLResponse)
def publish_html(
    request: Request,
    video_id: int,
    platforms: list[str] = Form(default=[]),
    svc: PipelineService = Depends(get_pipeline_service),
):
    platform_enums = [Platform(p) for p in platforms] if platforms else None
    video = svc.publish(video_id, platforms=platform_enums)
    return templates.TemplateResponse(
        "partials/video_row.html",
        _video_ctx(request, video, expanded_panel=_panel_template(video)),
    )
