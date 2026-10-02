from pathlib import Path
from fastapi.templating import Jinja2Templates

SRC_DIR = Path(__file__).resolve().parents[1]  # src/
templates = Jinja2Templates(directory=str(SRC_DIR / "frontend" / "templates"))
