#!/usr/bin/env python3
"""
Content Pipeline CLI
Usage: python cli.py <command> [options]
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

import db
import script_generator

STAGES = ["idea", "script", "voiceover", "images", "assembly", "review", "published"]
STAGE_EMOJI = {
    "idea": "[idea]", "script": "[script]", "voiceover": "[voice]",
    "images": "[imgs]", "assembly": "[assem]", "review": "[review]", "published": "[pub]",
}

# Use UTF-8 output on Windows if the terminal supports it
import io
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ── Formatting helpers ────────────────────────────────────────────────────────

def fmt_stage(stage):
    return f"{STAGE_EMOJI.get(stage, '')} {stage}"

def print_table(rows, cols):
    """Print a simple fixed-width table."""
    widths = [max(len(str(r[c])) for r in ([{c: c}] + rows)) for c in cols]
    sep = "  ".join("-" * w for w in widths)
    header = "  ".join(str(c).ljust(w) for c, w in zip(cols, widths))
    print(header)
    print(sep)
    for row in rows:
        print("  ".join(str(row[c]).ljust(w) for c, w in zip(cols, widths)))

def die(msg):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)

def require_video(video_id):
    v = db.get_video(video_id)
    if not v:
        die(f"Video {video_id} not found.")
    return v


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_status(args):
    """Show pipeline status summary."""
    videos = db.get_videos()
    total = len(videos)
    counts = {s: 0 for s in STAGES}
    for v in videos:
        s = v.get("stage", "idea")
        if s in counts:
            counts[s] += 1

    print(f"\nContent Pipeline — {total} video{'s' if total != 1 else ''} total\n")
    for stage in STAGES:
        bar_len = counts[stage] * 3
        bar = "█" * bar_len
        print(f"  {STAGE_EMOJI[stage]} {stage:<12} {counts[stage]:>3}  {bar}")
    print()

    ollama_ok = script_generator.is_available()
    models = script_generator.list_models() if ollama_ok else []
    if ollama_ok:
        print(f"  Ollama: ready ({len(models)} model{'s' if len(models) != 1 else ''}: {', '.join(models[:3])}{'...' if len(models) > 3 else ''})")
    else:
        print("  Ollama: not running  (start with: ollama serve)")
    print()


def cmd_video_list(args):
    stage = args.stage if args.stage != "all" else None
    videos = db.get_videos(stage=stage)
    if not videos:
        print("No videos found.")
        return
    rows = [
        {
            "ID": v["id"],
            "Stage": fmt_stage(v.get("stage", "idea")),
            "Title": v["title"][:60],
            "Updated": v.get("updated_at", "")[:16],
        }
        for v in videos
    ]
    print()
    print_table(rows, ["ID", "Stage", "Title", "Updated"])
    print()


def cmd_video_create(args):
    topic = args.topic
    video_id = db.create_video(topic)
    print(f"Created video #{video_id}: {topic}")


def cmd_video_show(args):
    v = require_video(args.id)
    print(f"\n{'─'*60}")
    print(f"  ID:      {v['id']}")
    print(f"  Title:   {v['title']}")
    print(f"  Stage:   {fmt_stage(v.get('stage','idea'))}")
    print(f"  Created: {v.get('created_at','')[:16]}")
    print(f"  Updated: {v.get('updated_at','')[:16]}")

    if v.get("voiceover_path"):
        print(f"  Audio:   {v['voiceover_path']}")
    if v.get("assembly_path"):
        print(f"  Video:   {v['assembly_path']}")

    if v.get("script_json"):
        script = json.loads(v["script_json"])
        slides = script.get("slides", [])
        dur = script.get("target_duration_seconds")
        print(f"\n  Script: '{script.get('title','')}' — {len(slides)} slides" + (f", {dur}s target" if dur else ""))
        for s in slides:
            sn = s.get("slide_number", "?")
            narr = s.get("narration", "").strip()[:80]
            has_img = "🖼️" if s.get("image_path") and os.path.exists(s["image_path"]) else "  "
            print(f"    {has_img} Slide {sn}: {narr}")

    if v.get("post_urls"):
        post_urls = json.loads(v["post_urls"])
        links = {k: u for k, u in post_urls.items() if u}
        if links:
            print("\n  Post URLs:")
            for platform, url in links.items():
                print(f"    {platform}: {url}")

    print(f"{'─'*60}\n")


def cmd_video_delete(args):
    v = require_video(args.id)
    if not args.yes:
        confirm = input(f"Delete '{v['title']}' (#{v['id']})? [y/N] ")
        if confirm.lower() != "y":
            print("Aborted.")
            return
    db.delete_video(args.id)
    print(f"Deleted video #{args.id}.")


def cmd_video_set_stage(args):
    if args.stage not in STAGES:
        die(f"Invalid stage. Choose from: {', '.join(STAGES)}")
    v = require_video(args.id)
    db.update_video(args.id, stage=args.stage)
    print(f"Video #{args.id} '{v['title']}' → {fmt_stage(args.stage)}")


def cmd_video_generate_script(args):
    v = require_video(args.id)
    if v.get("stage") != "idea":
        print(f"Warning: video is at stage '{v['stage']}', not 'idea'. Continuing anyway.")

    if not script_generator.is_available():
        die("Ollama is not running. Start it with: ollama serve")

    models = script_generator.list_models()
    if not models:
        die("No models pulled. Run: ollama pull llama3.1:8b")

    model = args.model or next(
        (m for m in models if "llama3.1" in m or "llama3" in m or "qwen" in m),
        models[0],
    )
    print(f"Generating script for '{v['title']}' using {model}…")

    prompt = script_generator.build_script_prompt(v["title"])

    try:
        result, _ = script_generator.generate_script(prompt, model=model)
        db.update_video(args.id, script_json=json.dumps(result), stage="script")
        slides = result.get("slides", [])
        dur = result.get("target_duration_seconds")
        print(f"Done — {len(slides)} slides" + (f", {dur}s target" if dur else ""))
        for s in slides:
            print(f"  Slide {s.get('slide_number','?')}: {s.get('narration','')[:70]}")
    except Exception as e:
        die(f"Generation failed: {e}")


def cmd_video_approve_script(args):
    v = require_video(args.id)
    if not v.get("script_json"):
        die("No script found. Generate one first.")
    db.update_video(args.id, script_approved=1, stage="voiceover")
    print(f"Script approved. Video #{args.id} moved to voiceover stage.")


def cmd_video_approve_voiceover(args):
    audio_path = args.path
    if not os.path.exists(audio_path):
        die(f"Audio file not found: {audio_path}")
    v = require_video(args.id)
    db.update_video(args.id, voiceover_path=str(Path(audio_path).resolve()),
                    voiceover_approved=1, stage="images")
    print(f"Voiceover set. Video #{args.id} moved to images stage.")


def cmd_video_generate_images(args):
    v = require_video(args.id)
    if not v.get("script_json"):
        die("No script found. Run generate-script first.")

    try:
        import image_generator
    except ImportError:
        die("image_generator module not found.")

    if not image_generator.is_available():
        die("GPU image generation not available. Check requirements-gpu.txt.")

    script = json.loads(v["script_json"])
    slides = script.get("slides", [])
    if not slides:
        die("No slides in script.")

    print(f"Generating {len(slides)} image(s) for video #{args.id} (FLUX Q4_K_S GGUF on GPU)")
    print("First run downloads ~6.8 GB GGUF file; subsequent runs load from cache.\n")

    try:
        results = image_generator.generate_all_images(slides, args.id)
        path_map = {r["slide_number"]: r["image_path"] for r in results}
        for s in slides:
            if s.get("slide_number") in path_map:
                s["image_path"] = path_map[s["slide_number"]]
                print(f"  Slide {s['slide_number']}: {path_map[s['slide_number']]}")
        updated_script = dict(script)
        updated_script["slides"] = slides
        db.update_video(args.id, script_json=json.dumps(updated_script))
        print(f"\nAll {len(results)} images saved.")
    except Exception as e:
        die(f"Image generation failed: {e}")


def cmd_video_approve_images(args):
    v = require_video(args.id)
    if not v.get("script_json"):
        die("No script found.")
    script = json.loads(v["script_json"])
    slides = script.get("slides", [])
    missing = [s for s in slides if not s.get("image_path") or not os.path.exists(s["image_path"])]
    if missing and not args.force:
        die(f"{len(missing)} slide(s) are missing images. Use --force to skip this check.")
    db.update_video(args.id, stage="assembly")
    print(f"Images approved. Video #{args.id} moved to assembly stage.")


def cmd_video_assemble(args):
    v = require_video(args.id)
    if v.get("stage") != "assembly":
        print(f"Warning: video is at stage '{v['stage']}', expected 'assembly'.")

    import video_builder
    voiceover_path = v.get("voiceover_path", "")
    if not voiceover_path or not os.path.exists(voiceover_path):
        die("Voiceover file not found. Set one first with: video approve-voiceover")

    script = json.loads(v.get("script_json") or "{}")
    slides = script.get("slides", [])
    if not slides:
        die("No slides found in script.")

    print(f"Assembling video #{args.id}…")
    try:
        fname = f"video_{args.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        out_path = video_builder.build_video(args.id, slides, voiceover_path, fname)
        db.update_video(args.id, assembly_path=out_path, stage="review")
        print(f"Done! Video saved to: {out_path}")
    except Exception as e:
        die(f"Assembly failed: {e}")


def cmd_video_approve(args):
    v = require_video(args.id)
    assembly_path = v.get("assembly_path", "")
    if not assembly_path or not os.path.exists(assembly_path):
        print("Warning: no assembled video file found.")
    db.update_video(args.id, final_approved=1, stage="published")
    print(f"Video #{args.id} approved and marked as published.")


def cmd_topic_list(args):
    topics = db.get_topics(unused_only=not args.all)
    if not topics:
        print("No topics found.")
        return
    rows = [
        {
            "ID": t["id"],
            "Topic": t["topic"][:60],
            "Tag": t.get("tag", ""),
            "Used": "yes" if t.get("used") else "no",
        }
        for t in topics
    ]
    print()
    print_table(rows, ["ID", "Topic", "Tag", "Used"])
    print()


def cmd_topic_add(args):
    db.add_topic(args.topic, args.tag or "")
    print(f"Added topic: {args.topic}" + (f" [{args.tag}]" if args.tag else ""))


def cmd_topic_mark_used(args):
    db.mark_topic_used(args.id)
    print(f"Topic #{args.id} marked as used.")


def cmd_topic_delete(args):
    db.delete_topic(args.id)
    print(f"Topic #{args.id} deleted.")


def cmd_prompt_list(args):
    prompts = db.get_prompts()
    if not prompts:
        print("No prompts found.")
        return
    for p in prompts:
        print(f"\n[{p['id']}] {p['name']}")
        print(f"  {p['template'][:120]}{'…' if len(p['template']) > 120 else ''}")
    print()


def cmd_prompt_delete(args):
    db.delete_prompt(args.id)
    print(f"Prompt #{args.id} deleted.")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="cli",
        description="Content Pipeline CLI",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # status
    p_status = sub.add_parser("status", help="Show pipeline status")
    p_status.set_defaults(func=cmd_status)

    # video
    p_video = sub.add_parser("video", help="Manage videos")
    vs = p_video.add_subparsers(dest="video_cmd", metavar="<subcommand>")
    vs.required = True

    p_vl = vs.add_parser("list", help="List videos")
    p_vl.add_argument("--stage", default="all",
                      choices=["all"] + STAGES, help="Filter by stage")
    p_vl.set_defaults(func=cmd_video_list)

    p_vc = vs.add_parser("create", help="Create a new video")
    p_vc.add_argument("topic", help="Video topic")
    p_vc.set_defaults(func=cmd_video_create)

    p_vs = vs.add_parser("show", help="Show video details")
    p_vs.add_argument("id", type=int, help="Video ID")
    p_vs.set_defaults(func=cmd_video_show)

    p_vd = vs.add_parser("delete", help="Delete a video")
    p_vd.add_argument("id", type=int, help="Video ID")
    p_vd.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    p_vd.set_defaults(func=cmd_video_delete)

    p_vss = vs.add_parser("set-stage", help="Manually set a video's stage")
    p_vss.add_argument("id", type=int, help="Video ID")
    p_vss.add_argument("stage", choices=STAGES, help="Target stage")
    p_vss.set_defaults(func=cmd_video_set_stage)

    p_vg = vs.add_parser("generate-script", help="Generate script via Ollama")
    p_vg.add_argument("id", type=int, help="Video ID")
    p_vg.add_argument("--model", help="Ollama model name (default: auto-select)")
    p_vg.set_defaults(func=cmd_video_generate_script)

    p_vas = vs.add_parser("approve-script", help="Approve script → voiceover stage")
    p_vas.add_argument("id", type=int, help="Video ID")
    p_vas.set_defaults(func=cmd_video_approve_script)

    p_vav = vs.add_parser("approve-voiceover", help="Set voiceover file → images stage")
    p_vav.add_argument("id", type=int, help="Video ID")
    p_vav.add_argument("path", help="Path to audio file (.wav/.mp3)")
    p_vav.set_defaults(func=cmd_video_approve_voiceover)

    p_vgi = vs.add_parser("generate-images", help="Generate images via FLUX.1-schnell (GPU)")
    p_vgi.add_argument("id", type=int, help="Video ID")
    p_vgi.set_defaults(func=cmd_video_generate_images)

    p_vai = vs.add_parser("approve-images", help="Approve images → assembly stage")
    p_vai.add_argument("id", type=int, help="Video ID")
    p_vai.add_argument("--force", action="store_true", help="Skip missing-image check")
    p_vai.set_defaults(func=cmd_video_approve_images)

    p_vasm = vs.add_parser("assemble", help="Assemble the video")
    p_vasm.add_argument("id", type=int, help="Video ID")
    p_vasm.set_defaults(func=cmd_video_assemble)

    p_vap = vs.add_parser("approve", help="Approve assembled video → published")
    p_vap.add_argument("id", type=int, help="Video ID")
    p_vap.set_defaults(func=cmd_video_approve)

    # topic
    p_topic = sub.add_parser("topic", help="Manage topic bank")
    ts = p_topic.add_subparsers(dest="topic_cmd", metavar="<subcommand>")
    ts.required = True

    p_tl = ts.add_parser("list", help="List topics")
    p_tl.add_argument("--all", action="store_true", help="Include used topics")
    p_tl.set_defaults(func=cmd_topic_list)

    p_ta = ts.add_parser("add", help="Add a topic")
    p_ta.add_argument("topic", help="Topic text")
    p_ta.add_argument("--tag", choices=["AI", "device", "security", "internet", "other"],
                      help="Tag")
    p_ta.set_defaults(func=cmd_topic_add)

    p_tmu = ts.add_parser("mark-used", help="Mark topic as used")
    p_tmu.add_argument("id", type=int, help="Topic ID")
    p_tmu.set_defaults(func=cmd_topic_mark_used)

    p_td = ts.add_parser("delete", help="Delete a topic")
    p_td.add_argument("id", type=int, help="Topic ID")
    p_td.set_defaults(func=cmd_topic_delete)

    # prompt
    p_prompt = sub.add_parser("prompt", help="Manage prompt templates")
    ps = p_prompt.add_subparsers(dest="prompt_cmd", metavar="<subcommand>")
    ps.required = True

    p_pl = ps.add_parser("list", help="List prompts")
    p_pl.set_defaults(func=cmd_prompt_list)

    p_pd = ps.add_parser("delete", help="Delete a prompt")
    p_pd.add_argument("id", type=int, help="Prompt ID")
    p_pd.set_defaults(func=cmd_prompt_delete)

    return parser


def main():
    db.init_db()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
