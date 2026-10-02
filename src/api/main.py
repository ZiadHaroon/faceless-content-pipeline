from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.config import OUTPUT_DIR
from src.api.routes import pipeline, prompts, topics, videos, views

SRC_DIR = Path(__file__).resolve().parents[1]  # src/
STATIC_DIR = SRC_DIR / "frontend" / "static"

app = FastAPI(
    title="Faceless Content Pipeline",
    description="Local pipeline for producing faceless short-form explainer videos.",
    version="2.0.0",
)

# Static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Output files (images, videos) served for preview
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

# JSON API
app.include_router(videos.router, prefix="/api")
app.include_router(topics.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")

# HTML views (must come after API routes)
app.include_router(views.router)


@app.get("/health")
def health():
    return {"status": "ok"}
