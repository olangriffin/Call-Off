from functools import lru_cache
from pathlib import Path

from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.backend.core.csrf import csrf_token

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = BASE_DIR / "frontend" / "templates"
STATIC_ASSET_DIR = BASE_DIR / "frontend" / "static" / "assets"


@lru_cache(maxsize=32)
def inline_svg_asset(filename: str) -> Markup:
    if "/" in filename or "\\" in filename or not filename.endswith(".svg"):
        raise ValueError(
            "Only SVG filenames from the static assets directory are allowed.",
        )

    return Markup((STATIC_ASSET_DIR / filename).read_text(encoding="utf-8"))


def build_frontend_templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    templates.env.globals["inline_svg_asset"] = inline_svg_asset
    templates.env.globals["csrf_token"] = csrf_token

    return templates
