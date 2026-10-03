from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.api.dependencies import (
    get_pipeline_service,
    get_prompt_repo,
    get_topic_repo,
    get_video_repo,
)
from src.api.templating import templates
from src.domain.models import (
    AudienceLevel,
    ExplanationDepth,
    HookStyle,
    Platform,
    PipelineStage,
    PlatformMetrics,
    ScriptRequest,
    TopicTag,
)
from src.infrastructure.tts_client import VOICES
from src.repositories.prompt import SQLitePromptRepository
from src.repositories.topic import SQLiteTopicRepository
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
    return templates.TemplateResponse(request, "pipeline.html", {
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
    return templates.TemplateResponse(request, "partials/video_list.html", {
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
    return templates.TemplateResponse(request, "partials/video_row.html", _video_ctx(request, video))


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
        request,
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
        request,
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
        request,
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
        request,
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
        request,
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
    return templates.TemplateResponse(request, "partials/photo_results.html", {
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
        request,
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
        request,
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
        request,
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
        request,
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
        request,
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
        request,
        "partials/video_row.html",
        _video_ctx(request, video, expanded_panel=_panel_template(video)),
    )


@router.post("/pipeline/{video_id}/set-post-url", response_class=HTMLResponse)
def set_post_url_html(
    request: Request,
    video_id: int,
    platform: str = Form(...),
    url: str = Form(...),
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    video = repo.get_by_id(video_id)
    if video is None:
        return HTMLResponse("")
    p = Platform(platform)
    updated_urls = dict(video.post_urls)
    updated_urls[p] = url.strip()
    video = video.model_copy(update={"post_urls": updated_urls})
    repo.update(video)
    url_val = updated_urls[p]
    return templates.TemplateResponse(request, "partials/post_url_entry.html", {
        "video_id": video_id,
        "platform": p,
        "url": url_val,
    })


@router.post("/pipeline/{video_id}/update-metrics", response_class=HTMLResponse)
def update_metrics_html(
    request: Request,
    video_id: int,
    platform: str = Form(...),
    views: int = Form(0),
    likes: int = Form(0),
    comments: int = Form(0),
    shares: int = Form(0),
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    video = repo.get_by_id(video_id)
    if video is None:
        return HTMLResponse("")
    p = Platform(platform)
    updated_perf = dict(video.performance)
    updated_perf[p] = PlatformMetrics(views=views, likes=likes, comments=comments, shares=shares)
    video = video.model_copy(update={"performance": updated_perf})
    repo.update(video)
    m = updated_perf[p]
    return templates.TemplateResponse(request, "partials/metrics_row.html", {
        "video_id": video_id,
        "platform": p,
        "m": m,
    })


# ── Topics ────────────────────────────────────────────────────────────────


@router.get("/topics", response_class=HTMLResponse)
def topics_page(
    request: Request,
    repo: SQLiteTopicRepository = Depends(get_topic_repo),
):
    topics = repo.get_all()
    return templates.TemplateResponse(request, "topics.html", {
        "active_nav": "topics",
        "topics": topics,
        "tags": list(TopicTag),
    })


@router.get("/topics/list", response_class=HTMLResponse)
def topic_list_partial(
    request: Request,
    unused_only: bool = False,
    repo: SQLiteTopicRepository = Depends(get_topic_repo),
):
    topics = repo.get_all(unused_only=unused_only)
    return templates.TemplateResponse(request, "partials/topic_list.html", {
        "topics": topics,
    })


@router.post("/topics", response_class=HTMLResponse)
def create_topic_html(
    request: Request,
    topic: str = Form(...),
    tag: str = Form("other"),
    repo: SQLiteTopicRepository = Depends(get_topic_repo),
):
    new_topic = repo.create(topic=topic, tag=TopicTag(tag))
    return templates.TemplateResponse(request, "partials/topic_row.html", {
        "topic": new_topic,
    })


@router.post("/topics/{topic_id}/mark-used", response_class=HTMLResponse)
def mark_topic_used_html(
    request: Request,
    topic_id: int,
    repo: SQLiteTopicRepository = Depends(get_topic_repo),
):
    repo.mark_used(topic_id)
    topic = repo.get_by_id(topic_id)
    return templates.TemplateResponse(request, "partials/topic_row.html", {
        "topic": topic,
    })


@router.delete("/topics/{topic_id}", response_class=HTMLResponse)
def delete_topic_html(
    topic_id: int,
    repo: SQLiteTopicRepository = Depends(get_topic_repo),
):
    repo.delete(topic_id)
    return HTMLResponse("")


# ── Prompts ───────────────────────────────────────────────────────────────


@router.get("/prompts", response_class=HTMLResponse)
def prompts_page(
    request: Request,
    repo: SQLitePromptRepository = Depends(get_prompt_repo),
):
    prompts = repo.get_all()
    return templates.TemplateResponse(request, "prompts.html", {
        "active_nav": "prompts",
        "prompts": prompts,
    })


@router.get("/prompts/list", response_class=HTMLResponse)
def prompt_list_partial(
    request: Request,
    repo: SQLitePromptRepository = Depends(get_prompt_repo),
):
    prompts = repo.get_all()
    return templates.TemplateResponse(request, "partials/prompt_list.html", {
        "prompts": prompts,
    })


@router.post("/prompts", response_class=HTMLResponse)
def create_prompt_html(
    request: Request,
    name: str = Form(...),
    template: str = Form(...),
    repo: SQLitePromptRepository = Depends(get_prompt_repo),
):
    prompt = repo.create(name=name, template=template)
    return templates.TemplateResponse(request, "partials/prompt_row.html", {
        "prompt": prompt,
    })


@router.delete("/prompts/{prompt_id}", response_class=HTMLResponse)
def delete_prompt_html(
    prompt_id: int,
    repo: SQLitePromptRepository = Depends(get_prompt_repo),
):
    repo.delete(prompt_id)
    return HTMLResponse("")


# ── Batch / Calendar / Performance ───────────────────────────────────────


@router.get("/batch", response_class=HTMLResponse)
def batch_page(
    request: Request,
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    videos = repo.get_all()
    active_stages = [s for s in PipelineStage if s != PipelineStage.published]
    videos_by_stage: dict[str, list] = {s.value: [] for s in active_stages}
    for v in videos:
        if v.stage != PipelineStage.published:
            videos_by_stage[v.stage.value].append(v)
    stage_counts = {s: len(videos_by_stage[s.value]) for s in active_stages}
    total = sum(stage_counts.values())
    return templates.TemplateResponse(request, "batch.html", {
        "active_nav": "batch",
        "videos_by_stage": videos_by_stage,
        "active_stages": [s.value for s in active_stages],
        "stage_counts": {s.value: c for s, c in stage_counts.items()},
        "total": total,
    })


@router.get("/calendar", response_class=HTMLResponse)
def calendar_page(
    request: Request,
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    videos = repo.get_all(stage=PipelineStage.published)
    return templates.TemplateResponse(request, "calendar.html", {
        "active_nav": "calendar",
        "videos": videos,
    })


@router.get("/performance", response_class=HTMLResponse)
def performance_page(
    request: Request,
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    videos = repo.get_all(stage=PipelineStage.published)
    return templates.TemplateResponse(request, "performance.html", {
        "active_nav": "performance",
        "videos": videos,
    })
