from pathlib import Path
import os, json, textwrap
from PIL import Image, ImageDraw, ImageFont, ImageOps
import numpy as np
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

BASE_DIR = Path(__file__).parent
VIDEO_DIR = BASE_DIR / "output" / "videos"
TEMP_DIR = BASE_DIR / "output" / "temp"
VIDEO_W, VIDEO_H = 1080, 1920
FPS = 30


def get_font(size):
    font_paths = [
        "C:/Windows/Fonts/arial.ttf",                                      # Windows
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",                 # Linux
        "/System/Library/Fonts/Helvetica.ttc",                             # Mac
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def fit_image_to_frame(image_path):
    canvas = Image.new("RGB", (VIDEO_W, VIDEO_H), (255, 255, 255))
    try:
        img = Image.open(image_path).convert("RGB")
    except Exception:
        return canvas

    # Resize maintaining aspect ratio to fit within canvas
    img_w, img_h = img.size
    scale = min(VIDEO_W / img_w, VIDEO_H / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Paste centered
    x_off = (VIDEO_W - new_w) // 2
    y_off = (VIDEO_H - new_h) // 2
    canvas.paste(img, (x_off, y_off))
    return canvas


def add_caption(pil_img, text):
    img = pil_img.copy()
    draw = ImageDraw.Draw(img)
    font = get_font(52)

    bottom_margin = 80
    max_chars = 30
    lines = textwrap.wrap(text, width=max_chars)

    line_height = 62
    text_block_h = len(lines) * line_height
    padding = 20

    rect_top = VIDEO_H - bottom_margin - text_block_h - padding * 2
    rect_bottom = VIDEO_H - bottom_margin

    # Semi-transparent black rectangle
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle(
        [(0, rect_top), (VIDEO_W, rect_bottom)],
        fill=(0, 0, 0, 160),
    )
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Draw each line of text
    for i, line in enumerate(lines):
        # Measure text width for centering
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
        except AttributeError:
            text_w, _ = draw.textsize(line, font=font)

        x = (VIDEO_W - text_w) // 2
        y = rect_top + padding + i * line_height

        # Black outline (2px in each direction)
        outline_color = (0, 0, 0)
        for dx in [-2, -1, 0, 1, 2]:
            for dy in [-2, -1, 0, 1, 2]:
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), line, font=font, fill=outline_color)

        # White text
        draw.text((x, y), line, font=font, fill=(255, 255, 255))

    return img


def build_video(vid_id, slides, voiceover_path, filename):
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    audio = AudioFileClip(voiceover_path)
    total_duration = audio.duration

    # Calculate word counts for proportional durations
    word_counts = []
    for slide in slides:
        narration = slide.get("narration", "")
        word_counts.append(max(1, len(narration.split())))

    total_words = sum(word_counts)
    durations = [(wc / total_words) * total_duration for wc in word_counts]

    clips = []
    temp_files = []

    for i, (slide, duration) in enumerate(zip(slides, durations)):
        narration = slide.get("narration", "")
        image_path = slide.get("image_path", "")

        # Build frame image
        if image_path and os.path.exists(image_path):
            frame = fit_image_to_frame(image_path)
        else:
            # Dark blue placeholder
            frame = Image.new("RGB", (VIDEO_W, VIDEO_H), (20, 20, 50))

        frame = add_caption(frame, narration)

        # Save temp frame
        temp_path = TEMP_DIR / f"vid_{vid_id}_slide_{i:03d}.jpg"
        frame.save(str(temp_path), "JPEG", quality=95)
        temp_files.append(temp_path)

        clip = (
            ImageClip(str(temp_path))
            .set_duration(duration)
            .set_fps(FPS)
        )
        clips.append(clip)

    # Concatenate and add audio
    final = concatenate_videoclips(clips, method="compose")
    final = final.set_audio(audio)

    output_path = VIDEO_DIR / filename

    # Try GPU encoding (NVENC) first, fall back to CPU (libx264)
    try:
        final.write_videofile(
            str(output_path),
            codec="h264_nvenc",
            audio_codec="aac",
            fps=FPS,
            logger=None,
        )
    except Exception:
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=FPS,
            logger=None,
        )

    # Cleanup temp files
    for tp in temp_files:
        try:
            os.remove(str(tp))
        except Exception:
            pass

    return str(output_path)
