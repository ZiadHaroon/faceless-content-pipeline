from __future__ import annotations

from src.domain.models import (
    AudienceLevel,
    ExplanationDepth,
    HookStyle,
    ScriptRequest,
    Slide,
)
from src.infrastructure.ollama_client import OllamaClient


_AUDIENCE_INSTRUCTIONS: dict[AudienceLevel, str] = {
    AudienceLevel.general: (
        "Audience: general public (ELI15). Assume zero domain knowledge. "
        "Every technical term must be defined immediately using a physical analogy. "
        "Vocabulary must be simple enough for a curious 15-year-old."
    ),
    AudienceLevel.enthusiast: (
        "Audience: tech enthusiast. Some domain vocabulary is fine but briefly explain "
        "each mechanism — don't just name it, show how it works. "
        "The viewer has curiosity but not formal training."
    ),
    AudienceLevel.technical: (
        "Audience: technical professional. Assume solid domain knowledge. "
        "Use correct terminology without explanation. Include mechanism detail, "
        "nuance, and edge cases. Skip basic analogies."
    ),
}

_DEPTH_INSTRUCTIONS: dict[ExplanationDepth, str] = {
    ExplanationDepth.what: (
        "Explanation depth: WHAT. Cover surface facts — what the thing is, "
        "what it does, why people care. Do not explain the mechanism."
    ),
    ExplanationDepth.how: (
        "Explanation depth: HOW. Explain the mechanism step by step — "
        "what happens inside, what causes what. Give the viewer a working mental model."
    ),
    ExplanationDepth.why: (
        "Explanation depth: WHY. Go beyond the mechanism into analysis — "
        "why it matters, what the trade-offs are, what the implications are. "
        "Include nuance and counterarguments."
    ),
}

_HOOK_INSTRUCTIONS: dict[HookStyle, str] = {
    HookStyle.stat: (
        "Hook style: STAT. Open with a surprising, specific number or measurement "
        "that reframes how the viewer thinks about the topic. "
        "Example: 'Your phone battery loses 20% of its capacity in the first year — permanently.'"
    ),
    HookStyle.counterintuitive: (
        "Hook style: COUNTERINTUITIVE. Open by stating something that directly "
        "contradicts the viewer's assumption. Make them think 'wait, really?'. "
        "Example: 'The file you just deleted still exists — and anyone can read it.'"
    ),
    HookStyle.question: (
        "Hook style: QUESTION. Open with a question that creates an information gap "
        "the viewer immediately wants to close. "
        "Example: 'Why does your phone get hot even when you're not using it?'"
    ),
}


class ScriptService:
    def __init__(self, ollama: OllamaClient) -> None:
        self._ollama = ollama

    def build_prompt(self, request: ScriptRequest) -> str:
        audience_block = _AUDIENCE_INSTRUCTIONS[request.audience]
        depth_block = _DEPTH_INSTRUCTIONS[request.depth]
        hook_block = _HOOK_INSTRUCTIONS[request.hook_style]

        return f"""You are a world-class YouTube Shorts scriptwriter specialising in viral educational content.

Write a YouTube Shorts script about: "{request.topic}"

---

CONSTRAINTS — apply all three before writing a single word:

{audience_block}

{depth_block}

{hook_block}

---

STEP 1 — DECIDE THE FORMAT:

Choose slide count and target duration that best serve this specific topic:

• Number of slides: 3–10
  - 3–4 slides: single punchy insight or quick-hit fact
  - 5–6 slides: concept with 2-3 explanation layers (most topics)
  - 7–8 slides: multi-step process, comparison, or timeline
  - 9–10 slides: complex mechanism with several moving parts

• Target duration: 20–90 seconds
  - 20–35s: single surprising fact with immediate payoff
  - 36–55s: concept + 2 explanation beats + closer
  - 56–75s: fuller story arc, deeper analogy, more context
  - 76–90s: complex topic that earns the longer runtime

Word budget: narration is spoken at ~2.5 words/second. Match total word count to target duration.

---

STEP 2 — WRITE THE SLIDES:

Slide 1 — HOOK
Follow the hook style constraint above exactly. The first 8 words must earn the viewer's attention. Do NOT start with "Did you know".

Middle slides — CONTENT BEATS (one clear idea per slide)
Build progressively. Each beat should deepen curiosity about the next. Ground abstract concepts in physical analogies appropriate to the audience level.

Last slide — PAYOFF / CLOSER
Deliver the satisfying resolution to the hook, or open a bigger question. No weak sign-offs like "pretty cool, right?".

---

SEARCH QUERY RULES:

Each slide needs a short Pexels image search query (3-6 words) that will find a relevant, high-quality stock photo. The query should describe a concrete, photographable subject — not an abstract concept.

Good: "smartphone battery close up", "fiber optic cables glowing", "server room data center"
Bad: "technology concept", "digital innovation", "abstract data"

---

OUTPUT FORMAT — return ONLY this JSON, nothing else, no markdown fences:

{{
  "title": "Punchy 4-7 word title (title case)",
  "target_duration_seconds": <integer>,
  "slides": [
    {{
      "slide_number": 1,
      "narration": "...",
      "search_query": "3-6 word pexels search phrase"
    }}
  ]
}}

SELF-CHECK before outputting:
- Does slide 1 match the hook style constraint exactly?
- Is the vocabulary appropriate for the audience level throughout?
- Does the explanation depth match the constraint — not shallower, not deeper?
- Is total narration word count within 10% of target_duration_seconds × 2.5?
- Is every search_query a concrete, photographable subject (3-6 words)?"""

    def generate(self, request: ScriptRequest, model: str | None = None) -> list[Slide]:
        """
        Generate a script for the given request.
        Returns a list of Slide objects with narration and search_query populated.
        Raises json.JSONDecodeError if the model returns unparseable output.
        """
        prompt = self.build_prompt(request)
        parsed, _ = self._ollama.chat(prompt, model=model)
        return [
            Slide(
                slide_number=s["slide_number"],
                narration=s["narration"],
                search_query=s["search_query"],
            )
            for s in parsed["slides"]
        ]
