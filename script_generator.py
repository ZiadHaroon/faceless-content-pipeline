"""
Local script generation via Ollama.

Install Ollama: https://ollama.com
Pull a model:   ollama pull llama3.1:8b   (recommended — ~4.7 GB VRAM)
Alternative:    ollama pull qwen2.5:7b    (stricter JSON output)
"""
import json
import re

import requests

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:8b"
TIMEOUT = 180  # seconds — 8B on RTX 4060 generates ~200 tokens in ~15-30s


def build_script_prompt(topic: str) -> str:
    return f"""You are a world-class YouTube Shorts scriptwriter specialising in viral educational content. Your scripts consistently achieve 70%+ watch-through rates because they respect the viewer's intelligence while making complex ideas feel effortless.

Write a YouTube Shorts script about: "{topic}"

---

STEP 1 — DECIDE THE FORMAT (before writing anything):

Choose the number of slides and target duration that best serve this specific topic:

• Number of slides: 3–10
  - 3–4 slides: single punchy insight, quick-hit fact
  - 5–6 slides: concept with 2-3 explanation layers (most topics)
  - 7–8 slides: multi-step process, comparison, or timeline
  - 9–10 slides: complex mechanism with several moving parts

• Target duration: 20–90 seconds
  - 20–35s: single surprising fact with immediate payoff
  - 36–55s: concept + 2 explanation beats + closer
  - 56–75s: fuller story arc, deeper analogy, more context
  - 76–90s: complex topic that earns the longer runtime

Word budget: narration is spoken at ~2.5 words/second. Match your total word count to your target duration (e.g. 60s → ~150 words across all slides).

---

STEP 2 — WRITE THE SLIDES:

Slide 1 — HOOK
Open with a counterintuitive fact, shocking statistic, or question that creates an immediate information gap. The first 8 words must make the viewer think "wait, really?" Do NOT start with "Did you know". Strong examples: "Your phone is slowly poisoning itself every time you charge it." / "The file you just deleted still exists — and anyone can read it."

Middle slides — CONTENT BEATS (one clear idea per slide, ~20-35 words each)
Build progressively. Use plain, conversational language as if explaining to a smart friend over coffee. Each beat should make the viewer more curious about the next. Use concrete analogies when the concept is abstract — ground it in something the viewer has physically experienced.

Last slide — PAYOFF / CLOSER (~15-25 words)
Either deliver the fully satisfying "aha" that resolves the hook, OR open a bigger question. No weak sign-offs like "pretty cool, right?" — end with conviction or genuine curiosity.

---

IMAGE PROMPT RULES:

Each slide needs a detailed image prompt for a flat-design educational illustration (Kurzgesagt / TED-Ed / Vox style). Each prompt must specify:
1. The main subject or object in the scene — described precisely (size, position, state)
2. Any human figures — what they look like, what they are doing, their expression/posture
3. A visual metaphor or diagram element that makes the concept tangible (arrows, cross-sections, scale comparisons, before/after split)
4. The colour mood — bold, flat colours appropriate to the topic (warm tones for energy/heat, cool blues for tech/data, greens for biology)
5. Composition — where things are placed in the frame, what the viewer's eye is drawn to first
6. Style keywords: flat design vector illustration, clean bold outlines, no gradients, no photorealism, white background, no text or labels in the image

---

OUTPUT FORMAT — return ONLY this JSON, nothing else, no markdown fences:

{{
  "title": "Punchy 4-7 word title (title case)",
  "target_duration_seconds": <integer — your chosen ideal duration>,
  "slides": [
    {{
      "slide_number": 1,
      "narration": "[Hook narration]",
      "image_prompt": "[Full detailed image prompt — minimum 60 words, specifying subject, figures, visual metaphor, colours, composition, and flat-design style keywords]"
    }}
    ... (as many slides as the topic deserves — minimum 3, maximum 10)
  ]
}}

SELF-CHECK before outputting:
- Does slide 1 open a genuine information gap in the first 8 words?
- Is the slide count genuinely the right fit for this topic — not just defaulting to 5?
- Does total narration word count match target_duration_seconds × 2.5?
- Does each image prompt describe a SPECIFIC, visualisable scene — not an abstract concept?
- Would a 16-year-old understand every sentence without pausing?
- Are the image prompts detailed enough that two different artists would draw roughly the same scene?"""


def is_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list:
    """Return names of models currently pulled in Ollama."""
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def generate_script(prompt: str, model: str = DEFAULT_MODEL) -> tuple:
    """
    Send the script prompt to Ollama via the chat endpoint.
    Returns (parsed_dict, raw_text).
    raw_text is always populated so callers can show it on failure.
    Raises on network/HTTP errors; lets JSON errors surface with raw_text available.
    """
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a JSON API. Output ONLY valid JSON — no markdown fences, "
                    "no preamble, no explanation, no trailing text. "
                    "Your entire response must start with { and end with }."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": "json",   # Ollama grammar-constrained JSON mode
        "think": False,     # reasoning models (qwen3.5, gemma4, ...) otherwise burn
                             # num_predict on <thinking> and emit empty content
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_predict": 3000,
        },
    }
    r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    raw = r.json()["message"]["content"]

    # Unload model from GPU immediately so VRAM is free for image generation
    try:
        requests.post(
            f"{OLLAMA_BASE}/api/chat",
            json={"model": model, "messages": [], "keep_alive": 0},
            timeout=10,
        )
    except Exception:
        pass  # non-critical — generation already succeeded

    return parse_script_response(raw), raw


def parse_script_response(raw: str) -> dict:
    """
    Strip markdown fences, find the outermost JSON object, and parse.
    Tries increasingly lenient extraction so minor model slippage doesn't fail hard.
    """
    text = raw.strip()

    # Remove markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fall back: extract outermost {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    # Nothing worked — re-raise with the original text so caller can show it
    raise json.JSONDecodeError("No valid JSON object found in model output", text, 0)
