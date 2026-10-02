from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_video_repo
from src.domain.models import PipelineStage, Video
from src.repositories.video import SQLiteVideoRepository

router = APIRouter(prefix="/videos", tags=["videos"])


class CreateVideoRequest(BaseModel):
    title: str
    topic_id: Optional[int] = None


@router.get("", response_model=list[Video])
def list_videos(
    stage: Optional[PipelineStage] = None,
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    return repo.get_all(stage=stage)


@router.post("", response_model=Video, status_code=201)
def create_video(
    body: CreateVideoRequest,
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    return repo.create(title=body.title, topic_id=body.topic_id)


@router.get("/{video_id}", response_model=Video)
def get_video(
    video_id: int,
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    video = repo.get_by_id(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.delete("/{video_id}", status_code=204)
def delete_video(
    video_id: int,
    repo: SQLiteVideoRepository = Depends(get_video_repo),
):
    if repo.get_by_id(video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found")
    repo.delete(video_id)
