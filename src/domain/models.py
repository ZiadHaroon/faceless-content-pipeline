from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────


class PipelineStage(str, Enum):
    idea = "idea"
    script = "script"
    voiceover = "voiceover"
    images = "images"
    assembly = "assembly"
    review = "review"
    published = "published"


class Platform(str, Enum):
    youtube = "youtube"
    tiktok = "tiktok"
    instagram = "instagram"
    facebook = "facebook"


class TopicTag(str, Enum):
    AI = "AI"
    device = "device"
    security = "security"
    internet = "internet"
    other = "other"


class AudienceLevel(str, Enum):
    general = "general"
    enthusiast = "enthusiast"
    technical = "technical"


class ExplanationDepth(str, Enum):
    what = "what"
    how = "how"
    why = "why"


class HookStyle(str, Enum):
    stat = "stat"
    counterintuitive = "counterintuitive"
    question = "question"


# ── Sub-models ────────────────────────────────────────────────────────────────


class WordTiming(BaseModel):
    word: str
    start_seconds: float
    end_seconds: float


class PlatformMetrics(BaseModel):
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0


class Slide(BaseModel):
    slide_number: int
    narration: str
    search_query: str
    pexels_photo_id: Optional[int] = None
    image_path: Optional[str] = None
    audio_path: Optional[str] = None
    audio_duration_seconds: Optional[float] = None
    word_timings: Optional[list[WordTiming]] = None


# ── Root models ───────────────────────────────────────────────────────────────


class Video(BaseModel):
    id: int
    title: str
    stage: PipelineStage = PipelineStage.idea
    slides: list[Slide] = Field(default_factory=list)
    script_approved: bool = False
    voiceover_approved: bool = False
    final_approved: bool = False
    platforms: list[Platform] = Field(default_factory=list)
    publish_date: Optional[date] = None
    post_urls: dict[Platform, str] = Field(default_factory=dict)
    performance: dict[Platform, PlatformMetrics] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class Topic(BaseModel):
    id: int
    topic: str
    tag: TopicTag = TopicTag.other
    used: bool = False
    created_at: datetime


class Prompt(BaseModel):
    id: int
    name: str
    template: str
    created_at: datetime


# ── Script generation inputs ──────────────────────────────────────────────────


class ScriptRequest(BaseModel):
    topic: str
    audience: AudienceLevel = AudienceLevel.general
    depth: ExplanationDepth = ExplanationDepth.how
    hook_style: HookStyle = HookStyle.counterintuitive
