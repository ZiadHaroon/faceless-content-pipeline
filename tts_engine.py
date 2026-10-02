"""
Local Text-to-Speech using Kokoro (kokoro-82m).
Model downloads ~300MB on first run.
Install: pip install kokoro soundfile
"""
import os
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "output" / "audio"

# Keep model downloads off the C: drive — must be set before huggingface_hub
# gets imported anywhere in the process (it reads this at import time).
os.environ.setdefault("HF_HOME", str(BASE_DIR / ".cache" / "huggingface"))

VOICES = {
    "American Female — Heart": "af_heart",
    "American Female — Bella": "af_bella",
    "American Female — Nicole": "af_nicole",
    "American Male — Adam": "am_adam",
    "American Male — Michael": "am_michael",
    "British Female — Emma": "bf_emma",
    "British Male — George": "bm_george",
}

_pipeline = None


def is_available() -> bool:
    try:
        import kokoro  # noqa
        import soundfile  # noqa
        return True
    except ImportError:
        return False


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        from kokoro import KPipeline
        _pipeline = KPipeline(lang_code="a")  # 'a' = American English
    return _pipeline


def generate_voiceover(text: str, output_path: Path, voice: str = "af_heart", speed: float = 0.95) -> str:
    """Generate voiceover audio from text. Returns path to saved WAV file."""
    import soundfile as sf
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    pipeline = get_pipeline()
    chunks = []
    for _, _, audio in pipeline(text, voice=voice, speed=speed):
        chunks.append(audio)

    full_audio = np.concatenate(chunks)
    sf.write(str(output_path), full_audio, 24000)
    return str(output_path)
