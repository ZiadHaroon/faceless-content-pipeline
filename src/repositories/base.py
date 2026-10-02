from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.domain.models import Platform, PipelineStage, Prompt, Topic, TopicTag, Video


class VideoRepository(ABC):
    @abstractmethod
    def get_all(self, stage: Optional[PipelineStage] = None) -> list[Video]:
        ...

    @abstractmethod
    def get_by_id(self, video_id: int) -> Optional[Video]:
        ...

    @abstractmethod
    def create(self, title: str, topic_id: Optional[int] = None) -> Video:
        ...

    @abstractmethod
    def update(self, video: Video) -> Video:
        ...

    @abstractmethod
    def delete(self, video_id: int) -> None:
        ...


class TopicRepository(ABC):
    @abstractmethod
    def get_all(self, unused_only: bool = False) -> list[Topic]:
        ...

    @abstractmethod
    def get_by_id(self, topic_id: int) -> Optional[Topic]:
        ...

    @abstractmethod
    def create(self, topic: str, tag: TopicTag = TopicTag.other) -> Topic:
        ...

    @abstractmethod
    def mark_used(self, topic_id: int) -> None:
        ...

    @abstractmethod
    def delete(self, topic_id: int) -> None:
        ...


class PromptRepository(ABC):
    @abstractmethod
    def get_all(self) -> list[Prompt]:
        ...

    @abstractmethod
    def get_by_id(self, prompt_id: int) -> Optional[Prompt]:
        ...

    @abstractmethod
    def create(self, name: str, template: str) -> Prompt:
        ...

    @abstractmethod
    def delete(self, prompt_id: int) -> None:
        ...
