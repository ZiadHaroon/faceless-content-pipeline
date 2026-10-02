from __future__ import annotations

from fastapi import FastAPI

from src.api.routes import pipeline, prompts, topics, videos

app = FastAPI(
    title="Faceless Content Pipeline",
    description="Local pipeline for producing faceless short-form explainer videos.",
    version="2.0.0",
)

app.include_router(videos.router, prefix="/api")
app.include_router(topics.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
