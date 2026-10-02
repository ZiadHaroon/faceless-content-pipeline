# Faceless Content Pipeline — v2 Specification

> **Purpose:** Single source of truth for all v2 decisions. Every architectural and feature choice recorded here was agreed in the planning session before implementation began. Do not change this file without revisiting the decision — add a note explaining the revision instead.

---

## 1. Goals for v2

| Goal | Detail |
|---|---|
| Instant startup | Replace Streamlit — no full-script re-run on every interaction |
| Upload-ready video | MP4 with burned-in captions, no CapCut step required |
| Better images | Replace local GPU generation with Pexels stock photos + branded overlay |
| Precise audio timing | Per-slide audio files drive slide display duration automatically |
| Audience-aware scripts | Complexity = vocabulary + explanation depth, not slide count |
| Maintainable codebase | Clean layered architecture, dependency injection, unit tests on all services |

---

## 2. What is out of scope for v2

- Kanban drag-and-drop — scrapped, list view with detail panels is sufficient
- Arabic / second channel — future phase, not planned
- Hosted deployment — local-only, single user
- FLUX / GPU image generation — fully replaced by Pexels
- Auto-publishing to platforms — manual upload remains the final step

---

## 3. Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | FastAPI | Async, typed, pairs well with Pydantic; replaces Streamlit server |
| Frontend | HTMX + Jinja2 | No build step, stays Python ecosystem, partial page updates feel fast; kanban removal made React unnecessary |
| Domain models | Pydantic v2 | Free validation + JSON serialization; FastAPI already depends on it |
| Database | SQLite (unchanged) | Right size for a local single-user tool; no migration needed at this scale |
| Script generation | Ollama (unchanged) | `llama3.1:8b` default, `qwen2.5:7b` alternative |
| Voiceover | Kokoro TTS (unchanged) | Per-slide output instead of one long file |
| Images | Pexels API | Free, no attribution required for most uses; video clips available too |
| Image treatment | PIL (Pillow) | Branded color overlay applied to every Pexels result |
| Video assembly | MoviePy + ffmpeg | MoviePy for slide concatenation, ffmpeg for caption burn-in |
| Testing | pytest + pytest-asyncio | Unit tests for services, integration tests for repositories |

---

## 4. Architecture

### 4.1 Layer diagram

```
┌─────────────────────────────────────────────┐
│  Frontend  (HTMX + Jinja2 templates)        │
├─────────────────────────────────────────────┤
│  API  (FastAPI routes — thin, no logic)     │
├─────────────────────────────────────────────┤
│  Services  (all business logic)             │
│  ScriptService │ AudioService │ ImageService │
│  AssemblyService │ PipelineService          │
├─────────────────────────────────────────────┤
│  Repositories  (data access abstractions)   │
│  VideoRepository │ TopicRepository          │
│  PromptRepository                           │
├─────────────────────────────────────────────┤
│  Infrastructure  (external system wrappers) │
│  SQLiteDB │ OllamaClient │ PexelsClient     │
│  TTSClient                                  │
├─────────────────────────────────────────────┤
│  Domain  (pure Pydantic models, no deps)    │
│  Video │ Slide │ Topic │ Prompt             │
└─────────────────────────────────────────────┘
```

### 4.2 Project structure

```
src/
  domain/
    models.py             # Video, Slide, Topic, Prompt, PipelineStage
  repositories/
    base.py               # Abstract interfaces (ABCs)
    video.py
    topic.py
    prompt.py
  services/
    script.py             # Prompt building + Ollama call
    audio.py              # Per-slide Kokoro TTS
    image.py              # Pexels search + PIL overlay
    assembly.py           # Slide concat + ffmpeg caption burn-in
    pipeline.py           # Orchestrates stage transitions
  infrastructure/
    database.py           # SQLite connection + migrations
    ollama_client.py      # Ollama /api/chat wrapper
    pexels_client.py      # Pexels REST API wrapper
    tts_client.py         # Kokoro TTS wrapper
  api/
    routes/
      videos.py
      topics.py
      prompts.py
      pipeline.py
    main.py               # FastAPI app factory
  frontend/
    templates/            # Jinja2 HTML (base + per-view)
    static/
      css/
      js/                 # HTMX + minimal custom JS
tests/
  unit/
    test_script_service.py
    test_audio_service.py
    test_image_service.py
    test_assembly_service.py
  integration/
    test_video_repo.py
    test_topic_repo.py
```

### 4.3 Dependency injection rule

Services receive all external dependencies as constructor arguments. Nothing inside `services/` imports directly from `infrastructure/`. This is the line that makes unit testing work — in tests, pass a mock client; in production, pass the real one.

```python
# Correct
class ScriptService:
    def __init__(self, ollama: OllamaClient) -> None:
        self._ollama = ollama

# Wrong — untestable
class ScriptService:
    def generate(self, topic: str):
        client = OllamaClient()   # hard dependency, can't mock
        ...
```

---

## 5. Domain Models (Pydantic v2)

### Video
```
id: int
title: str
stage: PipelineStage          # enum: idea|script|voiceover|images|assembly|review|published
slides: list[Slide]           # embedded, serialised as JSON in DB
script_approved: bool
voiceover_approved: bool
final_approved: bool
platforms: list[Platform]     # enum: youtube|tiktok|instagram|facebook
publish_date: date | None
post_urls: dict[Platform, str]
performance: dict[Platform, PlatformMetrics]
created_at: datetime
updated_at: datetime
```

### Slide
```
slide_number: int
narration: str
search_query: str             # replaces image_prompt — short phrase for Pexels
pexels_photo_id: int | None   # selected Pexels asset
image_path: str | None        # local path after overlay applied
audio_path: str | None        # per-slide WAV from Kokoro
audio_duration_seconds: float | None   # drives display timing
word_timings: list[WordTiming] | None  # for karaoke captions
```

### WordTiming
```
word: str
start_seconds: float
end_seconds: float
```

### Topic
```
id: int
topic: str
tag: TopicTag                 # enum: AI|device|security|internet|other
used: bool
created_at: datetime
```

---

## 6. Pipeline Stages

Seven stages, same as v1. Nothing auto-advances without an explicit approval action.

```
idea → script → voiceover → images → assembly → review → published
```

Stage transitions are handled exclusively by `PipelineService`. Routes call `PipelineService.advance(video_id, approval)` — they do not update stage directly.

---

## 7. Feature Specs

### 7.1 Script generation — complexity model

Complexity is **not** slide count. It is two independent axes injected into the LLM prompt as behavioral constraints:

**Audience level**
- `general` — ELI15, pure analogy, no assumed knowledge, every term defined
- `enthusiast` — some domain vocabulary, terms briefly explained, mechanism shown
- `technical` — baseline domain knowledge assumed, full mechanism, nuance and edge cases included

**Explanation depth**
- `what` — surface facts, what the thing is
- `how` — the mechanism, how it works
- `why` — analysis, why it matters, nuance, trade-offs

These two values are passed as prompt constraints. The LLM determines appropriate slide count for the topic. The human does not set slide count.

**Hook style** (third pre-generation control)
- `stat` — opens with a surprising number or measurement
- `counterintuitive` — states something that contradicts common assumption
- `question` — opens with a question that creates an information gap

Hook style is also injected into the prompt. Default: `counterintuitive`.

**Prompt output schema** — same JSON structure as v1 but `image_prompt` is replaced by `search_query`:
```json
{
  "title": "string",
  "target_duration_seconds": 55,
  "slides": [
    {
      "slide_number": 1,
      "narration": "string",
      "search_query": "smartphone battery lithium ion degrading"
    }
  ]
}
```

### 7.2 Image pipeline — Pexels + overlay

1. For each slide, call Pexels `/v1/search` with `search_query`
2. Return top 5 results as thumbnail previews in the UI — user picks one (or auto-select top result)
3. Download full-resolution image (or video still)
4. PIL applies branded treatment:
   - Semi-transparent color overlay (channel palette — color TBD by user)
   - Slight gaussian blur on background image to reduce visual noise
5. Save treated image to `output/images/video_{id}_slide{n}.jpg`
6. Store `pexels_photo_id` on the slide record

**Pexels API key:** stored in `.env` as `PEXELS_API_KEY`. Free tier, no rate limit issues at batch production scale.

### 7.3 Audio pipeline — per-slide

Each slide gets its own WAV file from Kokoro TTS. This replaces the single long voiceover file from v1.

Benefits:
- Slide display duration derived directly from audio duration — no manual timing
- Single slide can be regenerated without redoing the whole video
- Natural pauses configurable as a gap (default: 0.3s) inserted between slides at assembly

`audio_duration_seconds` is written to the slide record after generation.

### 7.4 Karaoke captions

**Implementation: proportional timing (v2.0), WhisperX upgrade path (v2.x)**

Proportional timing algorithm:
1. Split narration into words
2. Assign each word a duration proportional to its character length relative to total characters
3. Scale total to match `audio_duration_seconds`
4. Apply a basic rhythm weight: punctuated words (ending in `,`, `.`) get +15% duration, short function words (`a`, `the`, `is`) get -10%

This produces `word_timings` on the slide. Assembly burns these into the video using ffmpeg `drawtext` filter with timestamp-triggered visibility.

**Caption style** (configurable per video or global default):
- Font: bold sans-serif (Inter or system default)
- Position: lower third (centered, 20% from bottom)
- Color: white text, semi-transparent black pill background
- Max words visible at once: 3

WhisperX can be dropped in later by replacing the proportional timing function with a forced-alignment call on the generated WAV — the `WordTiming` model stays the same.

### 7.5 Video assembly

Assembly order per slide:
1. Treated Pexels image (full 9:16 frame)
2. Display duration = `audio_duration_seconds` + configurable tail (default 0.1s)
3. Audio segment overlaid
4. Per-word caption via ffmpeg `drawtext`

After all slides are concatenated:
- Optional: background music bed at low volume (user uploads an MP3, stored in `output/music/`)
- ffmpeg encodes final MP4 with platform presets

**Platform export presets:**
| Platform | Resolution | Bitrate | Codec |
|---|---|---|---|
| YouTube Shorts | 1080×1920 | 8 Mbps | H.264 |
| TikTok | 1080×1920 | 6 Mbps | H.264 |
| Instagram Reels | 1080×1920 | 6 Mbps | H.264 |
| Facebook Reels | 1080×1920 | 6 Mbps | H.264 |

Default: YouTube Shorts preset. User selects at assembly time.

### 7.6 Batch operations

- **Batch script generation:** select multiple ideas from Topic Bank → generate all scripts in one Ollama call queue, one after another (not parallel — Ollama is single-threaded on local GPU)
- **Single slide regeneration:** regenerate audio or image for one slide without touching the rest of the video; resets assembly stage if video was already assembled

---

## 8. Frontend (HTMX + Jinja2)

No kanban. Pipeline is a filtered list with inline detail panels.

**Views:**
1. **Pipeline** — list of all videos, filterable by stage; click to expand stage panel inline (HTMX swap)
2. **Topic Bank** — add/remove/tag topics, mark used
3. **Prompt Library** — stored script prompt templates, one-click copy with topic slotted in
4. **Weekly Batch** — stage counts with progress bars, list of active videos
5. **Publishing Calendar** — table of published videos with dates and post URLs
6. **Performance** — per-video, per-platform metrics entry and summary table

Stage panels are rendered server-side via Jinja2 partials and swapped in by HTMX `hx-get` — no full page reload per interaction.

Long-running operations (script generation, audio generation, image generation, assembly) use **HTMX SSE or polling** to show progress without blocking the UI.

---

## 9. Testing Strategy

### Unit tests (services)
- All service methods have unit tests
- External clients (Ollama, Pexels, Kokoro) are mocked via `unittest.mock`
- Tests live alongside the feature — written before or during implementation, not after
- Target: 100% coverage of `services/` and `domain/`

### Integration tests (repositories)
- Repository tests run against an in-memory SQLite DB (`:memory:`)
- Test DB is created fresh per test via a pytest fixture
- No mocking — these tests verify real SQL queries

### What is not tested
- `infrastructure/` client wrappers (Ollama, Pexels, TTS) — tested manually against live services
- Frontend templates — visual review only

### Conventions
- Test file mirrors source file: `services/script.py` → `tests/unit/test_script_service.py`
- Each test function name states what it verifies: `test_build_prompt_injects_audience_level`
- No test should touch the filesystem or network — use `tmp_path` fixture for file operations

---

## 10. Environment Variables

```
PEXELS_API_KEY=your_key_here
OLLAMA_BASE_URL=http://localhost:11434      # default
OLLAMA_DEFAULT_MODEL=llama3.1:8b           # default
TTS_DEFAULT_VOICE=af_heart                 # Kokoro voice id
CAPTION_OVERLAY_COLOR=#1a1a2e             # channel brand color for image overlay
```

---

## 11. Build Order

Execute in this sequence. Do not start a phase until the previous phase has passing tests.

| Phase | Deliverable | Tests |
|---|---|---|
| 1 | Domain models + repository abstract interfaces | n/a (interfaces) |
| 2 | Infrastructure layer: DB, Ollama client, Pexels client, TTS client | manual |
| 3 | Repository implementations + integration tests | integration |
| 4 | ScriptService + unit tests | unit |
| 5 | AudioService (per-slide) + unit tests | unit |
| 6 | ImageService (Pexels + overlay) + unit tests | unit |
| 7 | AssemblyService (concat + captions) + unit tests | unit |
| 8 | FastAPI routes (thin wiring) | manual via `/docs` |
| 9 | HTMX frontend — pipeline list + stage panels | visual |
| 10 | HTMX frontend — remaining views | visual |
| 11 | Karaoke caption timing (proportional) | unit |
| 12 | Platform export presets | manual |

---

## 12. Known Technical Risks

| Risk | Mitigation |
|---|---|
| Kokoro TTS does not output word-level timestamps | Use proportional timing algorithm; WhisperX forced alignment is a documented upgrade path |
| Pexels search quality for abstract tech concepts | Allow user to pick from top 5 results rather than auto-selecting; user can also re-run search with a custom query |
| ffmpeg `drawtext` caption timing is frame-accurate but syntax is verbose | Encapsulate entirely in `AssemblyService` — routes never touch ffmpeg directly |
| Ollama single-threaded on local GPU | Batch generation queues sequentially; progress shown per video in UI |
| MoviePy 1.0.3 is unmaintained | Upgrade path to MoviePy 2.x or direct ffmpeg subprocess is isolated to `AssemblyService` |
