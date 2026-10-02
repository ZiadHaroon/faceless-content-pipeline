from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]  # project root
OUTPUT_DIR = BASE_DIR / "output"


class Settings:
    pexels_api_key: str = os.getenv("PEXELS_API_KEY", "")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_default_model: str = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.1:8b")
    tts_default_voice: str = os.getenv("TTS_DEFAULT_VOICE", "af_heart")
    caption_overlay_color: str = os.getenv("CAPTION_OVERLAY_COLOR", "#1a1a2e")
    db_path: Path = BASE_DIR / "data" / "pipeline.db"
    audio_dir: Path = OUTPUT_DIR / "audio"
    image_dir: Path = OUTPUT_DIR / "images"
    video_dir: Path = OUTPUT_DIR / "videos"


settings = Settings()
