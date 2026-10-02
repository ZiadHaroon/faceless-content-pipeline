from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_topic_repo
from src.domain.models import Topic, TopicTag
from src.repositories.topic import SQLiteTopicRepository

router = APIRouter(prefix="/topics", tags=["topics"])


class CreateTopicRequest(BaseModel):
    topic: str
    tag: TopicTag = TopicTag.other


@router.get("", response_model=list[Topic])
def list_topics(
    unused_only: bool = False,
    repo: SQLiteTopicRepository = Depends(get_topic_repo),
):
    return repo.get_all(unused_only=unused_only)


@router.post("", response_model=Topic, status_code=201)
def create_topic(
    body: CreateTopicRequest,
    repo: SQLiteTopicRepository = Depends(get_topic_repo),
):
    return repo.create(topic=body.topic, tag=body.tag)


@router.post("/{topic_id}/mark-used", response_model=Topic)
def mark_topic_used(
    topic_id: int,
    repo: SQLiteTopicRepository = Depends(get_topic_repo),
):
    topic = repo.get_by_id(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    repo.mark_used(topic_id)
    return repo.get_by_id(topic_id)


@router.delete("/{topic_id}", status_code=204)
def delete_topic(
    topic_id: int,
    repo: SQLiteTopicRepository = Depends(get_topic_repo),
):
    if repo.get_by_id(topic_id) is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    repo.delete(topic_id)
