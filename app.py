import streamlit as st
import json, os
from pathlib import Path
from datetime import datetime
import pandas as pd
import requests

import db
import video_builder
import script_generator

try:
    import image_generator
    _GPU_AVAILABLE = image_generator.is_available()
except ImportError:
    _GPU_AVAILABLE = False

try:
    import tts_engine
    _TTS_AVAILABLE = tts_engine.is_available()
except ImportError:
    _TTS_AVAILABLE = False

_OLLAMA_AVAILABLE = script_generator.is_available()
_OLLAMA_MODELS = script_generator.list_models() if _OLLAMA_AVAILABLE else []

st.set_page_config(page_title="Content Pipeline", page_icon="🎬", layout="wide")
db.init_db()

BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "output" / "audio"
IMAGE_DIR = BASE_DIR / "output" / "images"
for d in [AUDIO_DIR, IMAGE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

STAGES = ["idea", "script", "voiceover", "images", "assembly", "review", "published"]
STAGE_EMOJI = {
    "idea": "💡",
    "script": "📝",
    "voiceover": "🎙️",
    "images": "🖼️",
    "assembly": "🎬",
    "review": "✅",
    "published": "🚀",
}
GEMINI_URL = "https://gemini.google.com"
ELEVENLABS_URL = "https://elevenlabs.io/app/speech-synthesis"


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Settings")
    if _OLLAMA_AVAILABLE:
        model_count = len(_OLLAMA_MODELS)
        st.success(f"Ollama ready — {model_count} model{'s' if model_count != 1 else ''} available")
    else:
        st.warning("Ollama not running. Start it with: `ollama serve`")
    if _GPU_AVAILABLE:
        st.success("RTX 4060 ready — GPU image gen enabled")
    else:
        st.warning("GPU image gen not available. See requirements-gpu.txt.")
    if _TTS_AVAILABLE:
        st.success("Kokoro TTS ready — local voiceover enabled")
    else:
        st.warning("Local TTS not available. Run: pip install kokoro soundfile")
    st.divider()
    st.markdown("**External Tools**")
    st.markdown(f"[🎙️ ElevenLabs]({ELEVENLABS_URL})")
    st.markdown(f"[🖼️ Gemini]({GEMINI_URL})")
    st.markdown("[✍️ Claude.ai](https://claude.ai)")

api_key = None  # no longer used; kept to avoid NameError in render_stage_panel call


# ── Helpers ──────────────────────────────────────────────────────────────────

def build_script_prompt(topic: str) -> str:
    return script_generator.build_script_prompt(topic)


def parse_script_response(raw: str) -> dict:
    return script_generator.parse_script_response(raw)


# ── Stage Panel ───────────────────────────────────────────────────────────────

def render_stage_panel(v, api_key):
    stage = v["stage"]
    vid_id = v["id"]

    # ── IDEA ──
    if stage == "idea":
        st.write(f"**Topic:** {v['title']}")

        # ── Local Ollama generation (primary path) ──
        if _OLLAMA_AVAILABLE and _OLLAMA_MODELS:
            st.markdown("#### Generate Script Locally")
            default_idx = next(
                (i for i, m in enumerate(_OLLAMA_MODELS) if "llama3.1" in m or "llama3" in m or "qwen" in m),
                0,
            )
            selected_model = st.selectbox(
                "Model",
                _OLLAMA_MODELS,
                index=default_idx,
                key=f"ollama_model_{vid_id}",
            )
            if st.button("🤖 Generate Script (Ollama)", key=f"ollama_gen_{vid_id}", type="primary"):
                with st.spinner(f"Generating with {selected_model}… (~15–30 seconds)"):
                    try:
                        result, _ = script_generator.generate_script(
                            build_script_prompt(v["title"]), model=selected_model
                        )
                        db.update_video(vid_id, script_json=json.dumps(result), stage="script")
                        st.rerun()
                    except requests.exceptions.Timeout:
                        st.error("Timed out — model took too long. Try a smaller/faster model.")
                    except requests.exceptions.ConnectionError:
                        st.error("Cannot reach Ollama. Is it running? Try: `ollama serve`")
                    except json.JSONDecodeError as e:
                        raw_output = getattr(e, "doc", "") or ""
                        st.error(f"Model output was not valid JSON: {e}")
                        if raw_output.strip():
                            with st.expander("Raw model output (debug)"):
                                st.text(raw_output)
                        else:
                            st.warning("Model returned an empty response. The model may not be pulled yet — run: `ollama pull llama3.1:8b`")
                    except Exception as e:
                        st.error(f"Generation failed: {e}")
            st.divider()
        elif _OLLAMA_AVAILABLE and not _OLLAMA_MODELS:
            st.warning("Ollama is running but no models are pulled. Run: `ollama pull llama3.1:8b`")
            st.divider()
        else:
            st.info("Ollama not running — using manual paste fallback. Start with: `ollama serve`")

        # ── Manual fallback ──
        with st.expander("Paste script JSON manually (fallback)", expanded=not _OLLAMA_AVAILABLE):
            st.markdown("**Step 1 — Copy this prompt into Claude.ai or ChatGPT:**")
            st.code(build_script_prompt(v["title"]), language=None)
            st.link_button("✍️ Open Claude.ai", "https://claude.ai")
            st.markdown("**Step 2 — Paste the JSON response here:**")
            pasted = st.text_area(
                "Response",
                height=180,
                key=f"paste_{vid_id}",
                placeholder='{"title": "...", "slides": [...]}',
                label_visibility="collapsed",
            )
            if st.button("▶ Parse & Save Script", key=f"parse_{vid_id}", type="primary"):
                if pasted.strip():
                    try:
                        result = parse_script_response(pasted)
                        db.update_video(vid_id, script_json=json.dumps(result), stage="script")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not parse JSON: {e}")
                else:
                    st.warning("Paste the response first.")

        manual_slide_count = st.number_input(
            "Number of slides (manual entry)",
            min_value=3, max_value=10, value=5, step=1,
            key=f"manual_slide_count_{vid_id}",
        )
        if st.button("✏️ Enter manually", key=f"manual_{vid_id}"):
            empty_script = {
                "title": v["title"],
                "target_duration_seconds": None,
                "slides": [
                    {"slide_number": i, "narration": "", "image_prompt": "", "image_path": ""}
                    for i in range(1, int(manual_slide_count) + 1)
                ],
            }
            db.update_video(vid_id, script_json=json.dumps(empty_script), stage="script")
            st.rerun()

    # ── SCRIPT ──
    elif stage == "script":
        script = json.loads(v.get("script_json") or "{}")
        slides = script.get("slides", [])
        target_dur = script.get("target_duration_seconds")
        st.write(f"**Title:** {script.get('title', v['title'])}")
        st.caption(f"**{len(slides)} slides** · Target duration: **{target_dur}s** (~{round(target_dur / 60, 1)} min)" if target_dur else f"**{len(slides)} slides**")

        updated_slides = []
        for slide in slides:
            sn = slide.get("slide_number", "?")
            st.markdown(f"**Slide {sn}**")
            col1, col2 = st.columns(2)
            with col1:
                narr = st.text_area(
                    "Narration",
                    value=slide.get("narration", ""),
                    height=100,
                    key=f"narr_{vid_id}_{sn}",
                )
            with col2:
                img_p = st.text_area(
                    "Image Prompt",
                    value=slide.get("image_prompt", ""),
                    height=100,
                    key=f"imgp_{vid_id}_{sn}",
                )
            updated_slides.append({
                "slide_number": sn,
                "narration": narr,
                "image_prompt": img_p,
                "image_path": slide.get("image_path", ""),
            })

        col_save, col_approve = st.columns(2)
        with col_save:
            if st.button("💾 Save Edits", key=f"save_script_{vid_id}"):
                new_script = dict(script)
                new_script["slides"] = updated_slides
                db.update_video(vid_id, script_json=json.dumps(new_script))
                st.success("Saved.")
        with col_approve:
            if st.button("✅ Approve & Next →", key=f"approve_script_{vid_id}"):
                new_script = dict(script)
                new_script["slides"] = updated_slides
                db.update_video(
                    vid_id,
                    script_json=json.dumps(new_script),
                    script_approved=1,
                    stage="voiceover",
                )
                st.rerun()

    # ── VOICEOVER ──
    elif stage == "voiceover":
        script = json.loads(v.get("script_json") or "{}")
        slides = script.get("slides", [])
        full_narration = " ".join(s.get("narration", "") for s in slides)

        st.text_area("Full narration", value=full_narration, height=150,
                     disabled=True, key=f"narr_ro_{vid_id}")

        existing_path = v.get("voiceover_path", "")
        if existing_path and os.path.exists(existing_path):
            st.markdown("**Current voiceover:**")
            st.audio(existing_path)
            if st.button("✅ Approve & Next →", key=f"vo_already_{vid_id}", type="primary"):
                db.update_video(vid_id, voiceover_approved=1, stage="images")
                st.rerun()
            st.divider()

        # ── Local TTS ──
        if _TTS_AVAILABLE:
            voice_label = st.selectbox(
                "Voice",
                list(tts_engine.VOICES.keys()),
                key=f"vo_voice_{vid_id}",
            )
            speed = st.slider("Speed", 0.7, 1.3, 0.95, 0.05, key=f"vo_speed_{vid_id}")
            if st.button("🎙️ Generate Voiceover (Local)", key=f"vo_gen_{vid_id}", type="primary"):
                with st.spinner("Generating voiceover... (first run downloads ~300MB model)"):
                    try:
                        voice_id = tts_engine.VOICES[voice_label]
                        out_path = AUDIO_DIR / f"video_{vid_id}_vo.wav"
                        tts_engine.generate_voiceover(full_narration, out_path, voice_id, speed)
                        db.update_video(vid_id, voiceover_path=str(out_path),
                                        voiceover_approved=1, stage="images")
                        st.rerun()
                    except Exception as e:
                        st.error(f"TTS failed: {e}")
        else:
            st.info("Install Kokoro for local voiceover: `pip install kokoro soundfile`")
            st.link_button("🎙️ Open ElevenLabs instead", ELEVENLABS_URL)
            uploaded = st.file_uploader("Or upload audio file",
                                        type=["mp3", "wav", "m4a", "ogg"],
                                        key=f"vo_upload_{vid_id}")
            if uploaded:
                save_path = AUDIO_DIR / f"video_{vid_id}_{uploaded.name}"
                with open(str(save_path), "wb") as f:
                    f.write(uploaded.read())
                st.audio(str(save_path))
                if st.button("✅ Approve & Next →", key=f"vo_approve_{vid_id}"):
                    db.update_video(vid_id, voiceover_path=str(save_path),
                                    voiceover_approved=1, stage="images")
                    st.rerun()

    # ── IMAGES ──
    elif stage == "images":
        script = json.loads(v.get("script_json") or "{}")
        slides_for_gen = script.get("slides", [])

        if _GPU_AVAILABLE:
            if st.button("🎨 Generate All Images — FLUX Q4 GGUF / GPU", key=f"gpu_gen_{vid_id}", type="primary"):
                with st.spinner("Generating images on GPU... first run downloads ~2GB model"):
                    try:
                        results = image_generator.generate_all_images(slides_for_gen, vid_id)
                        # Merge new image paths into slides
                        path_map = {r["slide_number"]: r["image_path"] for r in results}
                        for s in slides_for_gen:
                            if s.get("slide_number") in path_map:
                                s["image_path"] = path_map[s["slide_number"]]
                        updated_script = dict(script)
                        updated_script["slides"] = slides_for_gen
                        db.update_video(vid_id, script_json=json.dumps(updated_script))
                        st.success("All images generated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"GPU generation failed: {e}")
            st.caption("Or generate manually in Gemini and upload below.")
        else:
            st.link_button("🖼️ Open Gemini", GEMINI_URL)
            st.caption("Generate each image in Gemini, save it, upload below.")
            st.info("Install requirements-gpu.txt to enable one-click GPU image generation.")
        slides = script.get("slides", [])
        updated_slides = []

        for i, slide in enumerate(slides):
            sn = slide.get("slide_number", i + 1)
            st.markdown(f"**Slide {sn}**")
            st.code(slide.get("image_prompt", "(no prompt)"), language=None)

            existing_img = slide.get("image_path", "")
            if existing_img and os.path.exists(existing_img):
                st.image(existing_img, width=200)

            img_file = st.file_uploader(
                f"Upload image for slide {sn}",
                type=["png", "jpg", "jpeg", "webp"],
                key=f"img_{vid_id}_{i}",
            )
            new_image_path = existing_img
            if img_file:
                save_path = IMAGE_DIR / f"video_{vid_id}_slide{sn}_{img_file.name}"
                with open(str(save_path), "wb") as f:
                    f.write(img_file.read())
                st.image(str(save_path), width=200)
                new_image_path = str(save_path)

            updated_slides.append({
                "slide_number": sn,
                "narration": slide.get("narration", ""),
                "image_prompt": slide.get("image_prompt", ""),
                "image_path": new_image_path,
            })

        all_have_images = all(
            s.get("image_path") and os.path.exists(s["image_path"])
            for s in updated_slides
        )

        col_save, col_assemble = st.columns(2)
        with col_save:
            if st.button("💾 Save", key=f"save_imgs_{vid_id}"):
                new_script = dict(script)
                new_script["slides"] = updated_slides
                db.update_video(vid_id, script_json=json.dumps(new_script))
                st.success("Saved.")
        with col_assemble:
            if st.button(
                "✅ All Done → Assemble",
                key=f"assemble_btn_{vid_id}",
                disabled=not all_have_images,
            ):
                new_script = dict(script)
                new_script["slides"] = updated_slides
                db.update_video(
                    vid_id,
                    script_json=json.dumps(new_script),
                    stage="assembly",
                )
                st.rerun()

        if not all_have_images:
            st.info("Upload images for all slides to enable assembly.")

    # ── ASSEMBLY ──
    elif stage == "assembly":
        voiceover_path = v.get("voiceover_path", "")
        script = json.loads(v.get("script_json") or "{}")
        slides = script.get("slides", [])

        audio_ok = bool(voiceover_path) and os.path.exists(voiceover_path)
        images_with_path = [
            s for s in slides if s.get("image_path") and os.path.exists(s["image_path"])
        ]

        st.markdown("**Assembly Checklist:**")
        st.write(f"Audio file: {'✅' if audio_ok else '❌'}")
        st.write(f"Images: {'✅' if len(images_with_path) == len(slides) else '❌'} ({len(images_with_path)}/{len(slides)} slides have images)")

        all_ready = audio_ok and len(images_with_path) == len(slides)
        if all_ready:
            if st.button("🎬 Assemble Video", key=f"assemble_{vid_id}", type="primary"):
                with st.spinner("Assembling video..."):
                    try:
                        fname = f"video_{vid_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                        out_path = video_builder.build_video(vid_id, slides, voiceover_path, fname)
                        db.update_video(vid_id, assembly_path=out_path, stage="review")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Assembly failed: {e}")
        else:
            st.warning("Complete audio and images stages before assembling.")

    # ── REVIEW ──
    elif stage == "review":
        assembly_path = v.get("assembly_path", "")
        if assembly_path and os.path.exists(assembly_path):
            st.video(assembly_path)
        else:
            st.warning("Video file not found. Try reassembling.")

        col_approve, col_redo = st.columns(2)
        with col_approve:
            if st.button("✅ Approve & Publish", key=f"final_approve_{vid_id}", type="primary"):
                db.update_video(vid_id, final_approved=1, stage="published")
                st.rerun()
        with col_redo:
            if st.button("🔄 Redo Assembly", key=f"redo_assembly_{vid_id}"):
                db.update_video(vid_id, stage="assembly")
                st.rerun()

    # ── PUBLISHED ──
    elif stage == "published":
        post_urls = json.loads(v.get("post_urls") or "{}")
        st.markdown("**Post URLs**")
        col1, col2 = st.columns(2)
        with col1:
            yt = st.text_input("YouTube URL", value=post_urls.get("youtube", ""), key=f"yt_{vid_id}")
            tt = st.text_input("TikTok URL", value=post_urls.get("tiktok", ""), key=f"tt_{vid_id}")
        with col2:
            ig = st.text_input("Instagram URL", value=post_urls.get("instagram", ""), key=f"ig_{vid_id}")
            fb = st.text_input("Facebook URL", value=post_urls.get("facebook", ""), key=f"fb_{vid_id}")

        existing_date = v.get("publish_date")
        date_val = datetime.fromisoformat(existing_date).date() if existing_date else datetime.today().date()
        pub_date = st.date_input("Publish Date", value=date_val, key=f"pubdate_{vid_id}")

        if st.button("💾 Save", key=f"save_pub_{vid_id}"):
            new_urls = {"youtube": yt, "tiktok": tt, "instagram": ig, "facebook": fb}
            db.update_video(
                vid_id,
                post_urls=json.dumps(new_urls),
                publish_date=str(pub_date),
            )
            st.success("Saved.")

        assembly_path = v.get("assembly_path", "")
        if assembly_path and os.path.exists(assembly_path):
            st.markdown(f"**Video file:** `{assembly_path}`")

    # ── Delete button (all stages) ──
    st.divider()
    if st.button("🗑️ Delete this video", key=f"delete_{vid_id}", type="secondary"):
        db.delete_video(vid_id)
        st.rerun()


# ── Tabs ──────────────────────────────────────────────────────────────────────

tabs = st.tabs(["🎬 Pipeline", "💡 Topic Bank", "📋 Prompts", "📦 Weekly Batch", "📅 Calendar", "📊 Performance"])


# ── Pipeline Tab ──────────────────────────────────────────────────────────────

with tabs[0]:
    st.header("Content Pipeline")

    with st.expander("➕ New Video"):
        col1, col2 = st.columns(2)
        with col1:
            manual_topic = st.text_input("Enter topic manually", key="new_topic_manual")
        with col2:
            unused_topics = db.get_topics(unused_only=True)
            topic_options = ["— pick —"] + [t["topic"] for t in unused_topics]
            selected_topic_label = st.selectbox("Or pick from Topic Bank", topic_options, key="new_topic_bank")

        if st.button("Create", key="create_video_btn", type="primary"):
            if manual_topic.strip():
                db.create_video(manual_topic.strip())
                st.rerun()
            elif selected_topic_label != "— pick —":
                # Find matching topic
                matched = next((t for t in unused_topics if t["topic"] == selected_topic_label), None)
                if matched:
                    db.create_video(matched["topic"], topic_id=matched["id"])
                    st.rerun()
            else:
                st.warning("Enter a topic or pick one from the bank.")

    # Stage summary metrics
    all_videos = db.get_videos()
    stage_counts = {s: 0 for s in STAGES}
    for v in all_videos:
        s = v.get("stage", "idea")
        if s in stage_counts:
            stage_counts[s] += 1

    metric_cols = st.columns(len(STAGES))
    for col, stage in zip(metric_cols, STAGES):
        with col:
            st.metric(f"{STAGE_EMOJI[stage]} {stage.capitalize()}", stage_counts[stage])

    st.divider()

    filter_stage = st.selectbox("Filter by stage", ["All"] + STAGES, key="pipeline_filter")

    filtered_videos = db.get_videos(stage=filter_stage if filter_stage != "All" else None)

    if not filtered_videos:
        st.info("No videos found. Create one above.")
    else:
        for v in filtered_videos:
            stage = v.get("stage", "idea")
            label = f"{STAGE_EMOJI.get(stage, '')} {v['title']}"
            with st.expander(label):
                render_stage_panel(v, api_key)


# ── Topic Bank Tab ────────────────────────────────────────────────────────────

with tabs[1]:
    st.header("💡 Topic Bank")

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        new_topic_text = st.text_input("New topic", key="tb_new_topic")
    with col2:
        new_topic_tag = st.selectbox("Tag", ["", "AI", "device", "security", "internet", "other"], key="tb_tag")
    with col3:
        st.write("")
        st.write("")
        if st.button("➕ Add", key="tb_add_btn"):
            if new_topic_text.strip():
                db.add_topic(new_topic_text.strip(), new_topic_tag)
                st.rerun()
            else:
                st.warning("Enter a topic first.")

    show_used = st.checkbox("Show used topics too", key="tb_show_used")
    topics = db.get_topics(unused_only=not show_used)

    if not topics:
        st.info("No topics found.")
    else:
        for t in topics:
            c1, c2, c3 = st.columns([5, 1, 1])
            with c1:
                tag_badge = f" `{t['tag']}`" if t.get("tag") else ""
                if t.get("used"):
                    st.markdown(f"~~{t['topic']}~~{tag_badge}")
                else:
                    st.markdown(f"{t['topic']}{tag_badge}")
            with c2:
                if not t.get("used"):
                    if st.button("✓ Mark Used", key=f"tb_used_{t['id']}"):
                        db.mark_topic_used(t["id"])
                        st.rerun()
            with c3:
                if st.button("🗑️", key=f"tb_del_{t['id']}"):
                    db.delete_topic(t["id"])
                    st.rerun()


# ── Prompts Tab ───────────────────────────────────────────────────────────────

with tabs[2]:
    st.header("📋 Prompt Templates")

    prompts = db.get_prompts()
    for p in prompts:
        with st.expander(p["name"], expanded=True):
            st.text_area(
                "Template",
                value=p["template"],
                height=150,
                key=f"prompt_ta_{p['id']}",
                disabled=True,
            )
            st.caption("Copy and replace [TOPIC]")
            if st.button("🗑️ Delete", key=f"prompt_del_{p['id']}"):
                db.delete_prompt(p["id"])
                st.rerun()

    st.divider()
    with st.expander("➕ Add Template"):
        new_prompt_name = st.text_input("Name", key="new_prompt_name")
        new_prompt_template = st.text_area("Template", height=150, key="new_prompt_template")
        if st.button("💾 Save Template", key="save_new_prompt"):
            if new_prompt_name.strip() and new_prompt_template.strip():
                db.add_prompt(new_prompt_name.strip(), new_prompt_template.strip())
                st.rerun()
            else:
                st.warning("Both name and template are required.")


# ── Weekly Batch Tab ──────────────────────────────────────────────────────────

with tabs[3]:
    st.header("📦 Weekly Batch Overview")

    all_vids = db.get_videos()
    total = len(all_vids)

    stage_counts_wb = {s: 0 for s in STAGES}
    for v in all_vids:
        s = v.get("stage", "idea")
        if s in stage_counts_wb:
            stage_counts_wb[s] += 1

    for stage in STAGES:
        count = stage_counts_wb[stage]
        st.write(f"{STAGE_EMOJI[stage]} **{stage.capitalize()}**: {count}")
        st.progress(count / max(total, 1))

    st.divider()
    st.subheader("All Active Videos")
    non_published = [v for v in all_vids if v.get("stage") != "published"]
    if not non_published:
        st.info("No active videos in the pipeline.")
    else:
        for v in non_published:
            stage = v.get("stage", "idea")
            st.write(f"{STAGE_EMOJI.get(stage, '')} **{v['title']}** — {stage}")


# ── Calendar Tab ─────────────────────────────────────────────────────────────

with tabs[4]:
    st.header("📅 Publishing Calendar")

    published = db.get_videos(stage="published")
    if not published:
        st.info("No published videos yet.")
    else:
        rows = []
        for v in published:
            post_urls = json.loads(v.get("post_urls") or "{}")
            rows.append({
                "Title": v["title"],
                "Publish Date": v.get("publish_date", ""),
                "YouTube": post_urls.get("youtube", ""),
                "TikTok": post_urls.get("tiktok", ""),
                "Instagram": post_urls.get("instagram", ""),
                "Facebook": post_urls.get("facebook", ""),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)


# ── Performance Tab ───────────────────────────────────────────────────────────

with tabs[5]:
    st.header("📊 Performance Tracker")

    published_vids = db.get_videos(stage="published")
    if not published_vids:
        st.info("No published videos yet.")
    else:
        vid_titles = {v["id"]: v["title"] for v in published_vids}
        selected_vid_id = st.selectbox(
            "Select video",
            options=list(vid_titles.keys()),
            format_func=lambda vid_id: vid_titles[vid_id],
            key="perf_select",
        )

        selected_vid = db.get_video(selected_vid_id)
        perf = json.loads(selected_vid.get("performance") or "{}")

        platforms = ["YouTube", "TikTok", "Instagram", "Facebook"]
        metrics = ["views", "likes", "comments", "shares"]

        perf_cols = st.columns(len(platforms))
        new_perf = {}
        for col, platform in zip(perf_cols, platforms):
            with col:
                st.subheader(platform)
                plat_data = perf.get(platform, {})
                new_perf[platform] = {}
                for metric in metrics:
                    new_perf[platform][metric] = st.number_input(
                        metric.capitalize(),
                        value=int(plat_data.get(metric, 0)),
                        min_value=0,
                        key=f"perf_{selected_vid_id}_{platform}_{metric}",
                    )

        if st.button("💾 Save Metrics", key="save_metrics_btn", type="primary"):
            db.update_video(selected_vid_id, performance=json.dumps(new_perf))
            st.success("Metrics saved.")

        st.divider()
        st.subheader("All Published Videos — Summary")

        summary_rows = []
        for v in published_vids:
            vperf = json.loads(v.get("performance") or "{}")
            total_views = sum(
                vperf.get(p, {}).get("views", 0) for p in platforms
            )
            summary_rows.append({"Title": v["title"], "Total Views": total_views})

        summary_df = pd.DataFrame(summary_rows).sort_values("Total Views", ascending=False)
        st.dataframe(summary_df, use_container_width=True)
