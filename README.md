# Faceless Content Pipeline

A local Streamlit dashboard for producing faceless short-form explainer videos (YouTube Shorts, TikTok, Instagram Reels, Facebook Reels). The human reviews and approves at each stage — AI handles script, voiceover, and images.

**Human time target: ~8–10 minutes per video, done in weekly batches.**

---

## What it does

Each video moves through a fixed pipeline:

`Idea → Script → Voiceover → Images → Assembly → Review → Published`

Nothing advances without an explicit approval click. The app tracks every video as a record, stores your topic bank and prompt templates, and assembles the final MP4 locally.

---

## Stack

| Layer | Tool |
|---|---|
| UI | Streamlit |
| Database | SQLite (local, zero config) |
| Script generation | Ollama (local LLM — `llama3.1:8b` default) |
| Voiceover | Kokoro TTS (local) |
| Image generation | FLUX Q4 GGUF via GPU |
| Video assembly | MoviePy |

All AI runs locally — no API keys required for core functionality.

---

## Setup

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

For GPU image generation (requires NVIDIA GPU):

```bash
pip install -r requirements-gpu.txt
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
- **No GPU** — generate images in Gemini and upload per slide.

---

## Environment variables

Copy `.env.example` to `.env` and fill in any keys you want to use:

```bash
cp .env.example .env
```

---

## Project structure

```
app.py               # Streamlit UI — all tabs and stage panels
db.py                # SQLite layer — schema, seed data, CRUD
script_generator.py  # Ollama integration — prompt, generation, JSON parsing
tts_engine.py        # Kokoro TTS — voice selection, WAV output
image_generator.py   # FLUX GPU image generation
video_builder.py     # MoviePy assembly — images + audio → MP4
cli.py               # Headless CLI entry point
content-pipeline-spec.md  # Original build spec
```

---

## Content rules

- No copyrighted footage — AI-generated or stock visuals only.
- Tech/AI niche, English, evergreen topics.
- Format: 45–90 seconds, hook in the first 8 words.
