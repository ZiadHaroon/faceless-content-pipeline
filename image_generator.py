"""
Local image generation using SDXL-Turbo (primary) with sd-turbo as fallback.

Models:
  SDXL-Turbo  (stabilityai/sdxl-turbo) — ~7 GB download, 1024×1024, excellent quality
    - SDXL-based: far better prompt following than SD 1.5/2.1
    - 1-step distilled inference (very fast)
    - Fits in 8 GB VRAM at fp16 with no quantization tricks needed

  sd-turbo fallback  (~2.5 GB, already cached, 512×512)
    - Used automatically if SDXL-Turbo fails to load

Note on FLUX.1-schnell GGUF:
  GGUF quantized FLUX was attempted but the gguf Python library has an unstable
  Rust/pyo3 memory allocator on Windows that causes segfaults. SDXL-Turbo gives
  excellent results and is fully stable.

Install GPU deps:
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    pip install -r requirements-gpu.txt
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
IMAGE_DIR = BASE_DIR / "output" / "images"

# Keep all model downloads off the C: drive.
# Must be set before torch / huggingface_hub are imported anywhere in the process.
os.environ.setdefault("HF_HOME", str(BASE_DIR / ".cache" / "huggingface"))
os.environ.setdefault("TORCH_HOME", str(BASE_DIR / ".cache" / "torch"))

SDXL_TURBO_ID = "stabilityai/sdxl-turbo"
SD_TURBO_ID   = "stabilityai/sd-turbo"

_pipeline    = None
_active_model = None   # "sdxl-turbo" | "sd-turbo"

STYLE_SUFFIX = (
    "flat design vector illustration, Kurzgesagt style, "
    "bold outlines, vibrant flat colours, white background, no text, no gradients"
)

NEGATIVE_PROMPT = (
    "photorealistic, photograph, 3d render, blurry, low quality, "
    "text, watermark, gradients, dark background, noise"
)


def is_available() -> bool:
    try:
        import torch
        from diffusers import AutoPipelineForText2Image  # noqa
        return torch.cuda.is_available()
    except ImportError:
        return False


def _load_sdxl_turbo():
    import torch
    from diffusers import AutoPipelineForText2Image

    print("Loading SDXL-Turbo (~7 GB, first run downloads)…")
    pipe = AutoPipelineForText2Image.from_pretrained(
        SDXL_TURBO_ID,
        torch_dtype=torch.float16,
        variant="fp16",
    )
    pipe = pipe.to("cuda")
    print("SDXL-Turbo ready.")
    return pipe


def _load_sd_turbo():
    import torch
    from diffusers import AutoPipelineForText2Image

    print("Loading sd-turbo fallback…")
    pipe = AutoPipelineForText2Image.from_pretrained(
        SD_TURBO_ID,
        torch_dtype=torch.float16,
        variant="fp16",
    )
    pipe = pipe.to("cuda")
    print("sd-turbo ready.")
    return pipe


def get_pipeline():
    global _pipeline, _active_model
    if _pipeline is not None:
        return _pipeline, _active_model

    try:
        _pipeline = _load_sdxl_turbo()
        _active_model = "sdxl-turbo"
    except Exception as e:
        print(f"SDXL-Turbo load failed: {e}")
        print("Falling back to sd-turbo.")
        _pipeline = _load_sd_turbo()
        _active_model = "sd-turbo"

    return _pipeline, _active_model


def build_full_prompt(image_prompt: str) -> str:
    """
    Combine scene description with style suffix.
    SDXL uses OpenCLIP which handles up to 77 tokens; longer prompts are
    truncated by the tokenizer automatically.
    """
    return f"{image_prompt.rstrip('.')}. {STYLE_SUFFIX}"


def generate_image(image_prompt: str, output_path: Path) -> str:
    """Generate one image and save as PNG. Returns str path."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    pipe, model = get_pipeline()

    full_prompt = build_full_prompt(image_prompt)

    import torch, gc
    gc.collect()
    torch.cuda.empty_cache()

    if model == "sdxl-turbo":
        # SDXL-Turbo: distilled for 1-step, no CFG needed
        # 1024×1024 at fp16 uses ~6 GB VRAM — fits cleanly on RTX 4060 8 GB
        result = pipe(
            prompt=full_prompt,
            negative_prompt=NEGATIVE_PROMPT,
            num_inference_steps=4,   # 1 works, 4 gives slightly sharper results
            guidance_scale=0.0,
            width=1024,
            height=1024,
        )
    else:
        # sd-turbo fallback: 512×512
        result = pipe(
            prompt=full_prompt,
            negative_prompt=NEGATIVE_PROMPT,
            num_inference_steps=1,
            guidance_scale=0.0,
            width=512,
            height=512,
        )

    result.images[0].save(str(output_path), "PNG")
    return str(output_path)


def generate_all_images(slides: list, video_id: int) -> list:
    """
    Generate images for every slide sequentially.
    Returns list of {slide_number, image_path} dicts.
    """
    results = []
    for slide in slides:
        sn = slide.get("slide_number", 1)
        out_path = IMAGE_DIR / f"video_{video_id}_slide{sn}.png"
        path = generate_image(
            slide.get("image_prompt", "educational flat design illustration"),
            out_path,
        )
        results.append({"slide_number": sn, "image_path": path})
    return results
