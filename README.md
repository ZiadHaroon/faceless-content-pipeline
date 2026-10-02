# Faceless Content Pipeline

A local tool for producing faceless short-form explainer videos (YouTube Shorts, TikTok, Instagram Reels, Facebook Reels). The human reviews and approves at each stage — AI handles script, voiceover, and images.

**Human time target: ~8–10 minutes per video, done in weekly batches.**

> **Status:** v1 (Streamlit) is functional. v2 migration is in progress — see [v2-spec.md](v2-spec.md) for the full plan.

---

## What it does

Each video moves through a fixed pipeline:

`Idea → Script → Voiceover → Images → Assembly → Review → Published`

Nothing advances without an explicit approval click. The app tracks every video as a record, stores your topic bank and prompt templates, and assembles the final MP4 locally.

---

## v2 Migration Progress

v2 replaces Streamlit with FastAPI + HTMX, GPU image generation with Pexels stock photos, and adds per-slide audio, karaoke captions, and a clean layered architecture.

| Phase | Deliverable | Status |
|---|---|---|
| 1 | Domain models + repository interfaces | ✅ Done |
| 2 | Infrastructure layer (DB, Ollama, Pexels, TTS clients) | ✅ Done |
| 3 | Repository implementations + integration tests | ✅ Done |
| 4 | ScriptService + unit tests | ✅ Done |
| 5 | AudioService (per-slide) + unit tests | ✅ Done |
| 6 | ImageService (Pexels + overlay) + unit tests | ✅ Done |
| 7 | AssemblyService (concat + captions) + unit tests | ✅ Done |
| 8 | FastAPI routes | ✅ Done |
| 9 | HTMX frontend — pipeline list + stage panels | ✅ Done |
| 10 | HTMX frontend — remaining views | ✅ Done |
| 11 | Karaoke caption timing | Pending |
| 12 | Platform export presets | Pending |

---

## Stack

### v1 (current, running)

| Layer | Tool |
|---|---|
| UI | Streamlit |
| Database | SQLite (local, zero config) |
| Script generation | Ollama (local LLM — `llama3.1:8b` default) |
| Voiceover | Kokoro TTS (local) |
| Image generation | FLUX Q4 GGUF via GPU |
| Video assembly | MoviePy |

### v2 (in progress)

| Layer | Tool |
|---|---|
| UI | FastAPI + HTMX + Jinja2 |
| Database | SQLite (unchanged) |
| Script generation | Ollama (unchanged) |
| Voiceover | Kokoro TTS — per-slide WAV output |
| Images | Pexels API + PIL branded overlay |
| Video assembly | MoviePy + ffmpeg (caption burn-in) |

---

## Setup (v1)

**1. Clone and create a virtual environment**

```bash
git clone https://github.com/your-username/faceless-content-pipeline.git
cd faceless-content-pipeline
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Set up Ollama**

Install [Ollama](https://ollama.com), then pull a model:

```bash
ollama pull llama3.1:8b       # recommended (~4.7 GB VRAM)
# or
ollama pull qwen2.5:7b        # stricter JSON output
```

**4. Run**

```bash
ollama serve                  # separate terminal
streamlit run app.py
```

Opens at `http://localhost:8501`. The database and output folders are created automatically on first run.

---

## Fallbacks

Everything has a manual fallback if local AI isn't available:

- **No Ollama** — copy the prompt from the app, paste into Claude.ai or ChatGPT, paste the JSON back.
- **No Kokoro TTS** — upload an MP3/WAV from ElevenLabs via the file uploader.
- **No GPU** — generate images via Pexels (v2) or Gemini and upload per slide.

---

## Environment variables

```bash
# v1 — no keys required for core functionality

# v2 additions
PEXELS_API_KEY=your_key_here
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3.1:8b
TTS_DEFAULT_VOICE=af_heart
CAPTION_OVERLAY_COLOR=#1a1a2e
```

---

## Project structure

```
# v1 (active)
app.py               # Streamlit UI — all tabs and stage panels
db.py                # SQLite layer — schema, seed data, CRUD
script_generator.py  # Ollama integration — prompt, generation, JSON parsing
tts_engine.py        # Kokoro TTS — voice selection, WAV output
image_generator.py   # FLUX GPU image generation
video_builder.py     # MoviePy assembly — images + audio → MP4
cli.py               # Headless CLI entry point

# v2 (in progress)
src/
  domain/models.py         # Pydantic v2 domain models
  repositories/base.py     # Abstract repository interfaces
  services/                # Business logic (phases 4–7)
  infrastructure/          # External system wrappers (phase 2)
  api/                     # FastAPI routes (phase 8)
  frontend/                # HTMX + Jinja2 templates (phases 9–10)
tests/
  unit/                    # Service unit tests
  integration/             # Repository integration tests

# Specs
v2-spec.md                 # Full v2 architecture and feature decisions
content-pipeline-spec.md   # Original v1 build spec
```

---

## Content rules

- No copyrighted footage — AI-generated or stock visuals only.
- Tech/AI niche, English, evergreen topics.
- Format: 45–90 seconds, hook in the first 8 words.
