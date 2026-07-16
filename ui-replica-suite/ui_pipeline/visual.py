from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

from .api import OpenAICompatibleClient
from .utils import utc_now, write_json


VISUAL_SUFFIX = """
Create one production-quality UI visual, shown straight-on with no device mockup and no perspective.
Use crisp readable hierarchy, consistent spacing, complete viewport edges, and realistic final content.
Do not show annotations, measurements, grid overlays, multiple variants, or surrounding presentation boards.
Any icons must share one coherent visual language and remain clearly separable from their backgrounds.
""".strip()


def generate_visual(
    client: OpenAICompatibleClient,
    prompt: str,
    output_dir: str | Path,
    *,
    size: str = "1536x1024",
    name: str = "visual-target.png",
) -> dict:
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    output = root / name
    final_prompt = f"{prompt.strip()}\n\n{VISUAL_SUFFIX}"
    client.generate_image(final_prompt, output, size=size)
    return _write_visual_manifest(root, output, prompt, final_prompt, "generated", size, client.settings.image_model)


def import_visual(source: str | Path, output_dir: str | Path, *, name: str = "visual-target.png") -> dict:
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    output = root / name
    if source_path != output:
        shutil.copy2(source_path, output)
    return _write_visual_manifest(root, output, "", "", "imported", None, None)


def _write_visual_manifest(root: Path, image_path: Path, prompt: str, final_prompt: str, source: str, requested_size: str | None, model: str | None) -> dict:
    with Image.open(image_path) as image:
        width, height = image.size
        mode = image.mode
    manifest = {
        "version": 1,
        "created_at": utc_now(),
        "source": source,
        "model": model,
        "prompt": prompt,
        "effective_prompt": final_prompt,
        "requested_size": requested_size,
        "image": {"path": str(image_path), "width": width, "height": height, "mode": mode},
    }
    write_json(root / "run.json", manifest)
    return manifest
