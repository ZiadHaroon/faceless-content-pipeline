from __future__ import annotations

from functools import lru_cache

from src.api.config import settings
from src.infrastructure.database import Database
from src.infrastructure.ollama_client import OllamaClient
from src.infrastructure.pexels_client import PexelsClient
from src.infrastructure.tts_client import TTSClient
from src.repositories.prompt import SQLitePromptRepository
from src.repositories.topic import SQLiteTopicRepository
from src.repositories.video import SQLiteVideoRepository
from src.services.assembly import AssemblyService
from src.services.audio import AudioService
from src.services.image import ImageService
from src.services.pipeline import PipelineService
from src.services.script import ScriptService


@lru_cache(maxsize=1)
def get_db() -> Database:
    db = Database(settings.db_path)
    db.migrate()
    return db


@lru_cache(maxsize=1)
def get_video_repo() -> SQLiteVideoRepository:
    return SQLiteVideoRepository(get_db())


@lru_cache(maxsize=1)
def get_topic_repo() -> SQLiteTopicRepository:
    return SQLiteTopicRepository(get_db())


@lru_cache(maxsize=1)
def get_prompt_repo() -> SQLitePromptRepository:
    return SQLitePromptRepository(get_db())


@lru_cache(maxsize=1)
def get_pipeline_service() -> PipelineService:
    ollama = OllamaClient(
        base_url=settings.ollama_base_url,
        default_model=settings.ollama_default_model,
    )
    pexels = PexelsClient(api_key=settings.pexels_api_key)
    tts = TTSClient(default_voice=settings.tts_default_voice)

    return PipelineService(
        videos=get_video_repo(),
        script=ScriptService(ollama=ollama),
        audio=AudioService(tts=tts, output_dir=settings.audio_dir),
        image=ImageService(
            pexels=pexels,
            output_dir=settings.image_dir,
            overlay_color=settings.caption_overlay_color,
        ),
        assembly=AssemblyService(output_dir=settings.video_dir),
    )
