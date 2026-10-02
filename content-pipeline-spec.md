# Faceless Content Pipeline — Process & Dashboard Spec

## 1. Goal

Run a solo, low-effort, high-output content operation producing short-form
faceless explainer videos (tech/AI niche, English, to start) for YouTube
Shorts, TikTok, Instagram Reels, and Facebook Reels. The creator's role is
**reviewer, not producer** — AI tools handle script, voice, visuals, and
assembly; the human approves/edits at checkpoints and publishes.

This document describes the process end-to-end, then specifies a dashboard
web app to run it from. Use this as a build spec.

---

## 2. Content Pipeline (per video)

Each video moves through fixed stages. A dashboard should track every video
as a record moving through these stages, like a kanban board.

1. **Idea** — topic pulled from the topic bank or added ad hoc
2. **Script** — generated via LLM from a saved prompt template, human
   reviews/edits (~2 min)
3. **Voiceover** — script sent to ElevenLabs (or similar TTS), audio file
   produced, human spot-checks for glitches (~1 min)
4. **Visuals** — AI-generated images/stock B-roll matched to script beats
   (CapCut AI / InVideo AI), human skims for mismatches (~2 min)
5. **Assembly** — voiceover + visuals + captions combined into a 9:16 video
   (CapCut), human watches full video once (~2–3 min)
6. **Review/Approve** — final go/no-go checkpoint before publishing
7. **Published** — posted natively per platform, with per-platform post IDs
   and publish timestamps logged
8. **Performance** — views/likes/comments/shares tracked post-publish
   (manual entry initially; platform APIs later)

Total human time target: **~8–10 minutes per video**, done in batches.

---

## 3. Operating Cadence

- **Batch production**: once a week, generate 5–7 scripts in one sitting,
  then all voiceovers, then all assemblies, then review all, then schedule
  the week's posts.
- **Publishing frequency**: daily once past the first 1–2 batches.
- **Review checkpoint**: nothing auto-publishes without explicit human
  approval in the dashboard (matches "reviewer only" role).

---

## 4. Tool Stack (current)

| Stage | Tool | Notes |
|---|---|---|
| Script | ChatGPT / Claude | Uses saved prompt template (Section 6) |
| Voiceover | ElevenLabs | Pick one consistent voice for brand recognition |
| Visuals | CapCut AI tools / InVideo AI | Auto-matches B-roll/images to script |
| Assembly + captions | CapCut | Auto-captions, auto-resize to 9:16 |
| Publish | Native upload per platform | YouTube Shorts, TikTok, IG Reels, FB Reels |

None of these currently expose a unified API the dashboard can call directly
for generation — treat the dashboard initially as a **tracking and workflow
tool**, not a generation engine. (See Section 8, Phase 2, for optional API
wiring later, e.g. ElevenLabs does have a public API for voiceover.)

---

## 5. Content Rules

- **No copyrighted footage** (no movie/TV clips) — AI-generated or generic
  stock visuals only, to avoid Content ID strikes and takedowns.
- **Niche for now**: tech/AI explainers only. Evergreen, curiosity-driven,
  copyright-safe. (Movies/pop-culture and a second Arabic-language channel
  are later phases — see Section 8.)
- **Format**: 45–60 seconds, hook in first 8 words, 3 concise points, punchy
  closer or open question, plain spoken English.

---

## 6. Saved Script Prompt Template

Store this in the dashboard so it's one click to reuse, with a field to
swap in the topic:

```
You are writing a 45-60 second YouTube Shorts script about [TOPIC].
Structure: (1) a hook in the first 8 words that creates curiosity or
states something surprising, (2) 3 concise points building on each
other, (3) a punchy closer or open question. Plain, spoken English,
no jargon unless explained. ~150 words total.
```

---

## 7. Seed Topic Bank

Starter list to load into the dashboard's topic queue:

1. How does Face ID actually work
2. Why does your phone battery degrade over time
3. What is a VPN actually doing
4. How AI image generators actually "draw"
5. Why 5G isn't as big a deal as advertised
6. How does end-to-end encryption work
7. What happens when you delete a file
8. Why does your phone get hot when charging
9. How do noise-cancelling headphones work
10. What is quantum computing actually trying to solve

---

## 8. Dashboard / Webapp Spec

### Purpose
A single "base of operations" screen to run the whole pipeline without
losing track of what stage each video is in, without re-explaining prompts
from scratch, and without juggling five separate tools' tabs.

### Phase 1 — Core tracker (build first)

**Data model — `Video` record:**
```
id
title / working topic
stage: idea | script | voiceover | visuals | assembly | review | published
script_text
script_approved: bool
voiceover_file_ref (path or link)
voiceover_approved: bool
visuals_notes
assembly_file_ref (path or link)
final_approved: bool
platforms: [youtube, tiktok, instagram, facebook]
publish_date (per platform, can differ)
post_urls: { youtube: url, tiktok: url, instagram: url, facebook: url }
performance: { views, likes, comments, shares } per platform, per date pulled
created_at / updated_at
```

**Views/screens:**
1. **Kanban board** — columns = pipeline stages, cards = videos, drag between
   stages, click card to expand and see/edit script, mark approvals.
2. **Topic bank** — running list of ideas, add/remove/mark used, tag by
   sub-topic (device, security, AI, internet, etc.) to avoid repeating angles.
3. **Prompt library** — stores the script prompt template (Section 6) and
   any variants; one-click copy with topic slotted in.
4. **Weekly batch view** — a checklist for the weekly batching session:
   scripts written → voiceovers done → visuals done → assembled →
   reviewed → scheduled. Shows counts per stage so you know where the
   week's batch is stuck.
5. **Publishing calendar** — week/month calendar view showing what's
   scheduled to post where and when.
6. **Performance log** — simple table to manually log views/likes/comments
   per video per platform on a schedule (e.g. weekly), so you can see
   which topics/hooks perform best over time.

**Not required for Phase 1:** actual video generation, AI API calls,
auto-posting. This phase is pure workflow/tracking — it replaces a messy
spreadsheet with a proper interface, and enforces the "nothing publishes
without approval" rule via the `approved` flags.

### Phase 2 — Optional automation hooks (build once Phase 1 is in daily use)

- **ElevenLabs API integration**: send approved script text, receive
  voiceover audio file back into the record automatically.
- **LLM API integration** (Anthropic/OpenAI): generate a script draft from
  a topic bank entry directly inside the dashboard.
- **Analytics API pulls**: YouTube Data API and TikTok/Meta APIs (where
  available) to auto-populate the performance log instead of manual entry.
- **Notification/reminder**: flag if the weekly batch hasn't moved a video
  past "script" stage by a certain day.

### Phase 3 — Scaling hooks (later, once format is validated)

- Second channel/workspace for Egyptian Arabic content, same data model,
  separate topic bank and prompt variants (dialect-specific prompt tuning).
- Movie/pop-culture niche as a second content lane, with a content rule
  flag to enforce "no copyrighted footage" visually (AI-generated posters/
  art only).

---

## 9. Suggested Build Order for Claude Code

1. Scaffold a simple web app (e.g. React + local storage or lightweight
   backend/DB — SQLite is enough at this scale) with the `Video` data model
   above.
2. Build the kanban board view first — it's the daily-use screen.
3. Add topic bank + prompt library (static content, fastest to build,
   immediately useful).
4. Add the publishing calendar view.
5. Add the performance log table.
6. Only after Phase 1 is being used for a couple of real weekly batches,
   revisit Phase 2 API integrations — premature automation here just adds
   maintenance burden before the workflow itself is proven.

---

## 10. Open Decisions to Confirm Before/During Build

- Local-only tool (single user, runs on your machine) vs. hosted app you
  can check from your phone? Affects whether Claude Code should build a
  local SQLite app or something deployable.
- Do you want file storage (voiceover/video files) to live inside the app,
  or should the app just hold links/paths to files stored elsewhere
  (Google Drive, local folder)? Simpler to start with links.
