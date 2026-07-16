from __future__ import annotations

import math
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .api import OpenAICompatibleClient, extract_json
from .utils import unique_slugs, utc_now, write_json


def analyze_icons(client: OpenAICompatibleClient, visual: str | Path) -> list[dict[str, Any]]:
    with Image.open(visual) as image:
        width, height = image.size
    prompt = f"""Analyze this {width}x{height} UI visual and inventory every reusable non-text visual element suitable for a CSS spritesheet.
Include interface icons, logos/marks when visually required, badges, avatars that function as UI assets, small illustrations, and decorative symbols. Exclude plain text, photos, gradients, backgrounds, dividers, shadows, and entire UI components.
Return JSON only:
{{"icons":[{{"name":"semantic-kebab-name","description":"appearance and role","bbox":{{"x":0,"y":0,"width":24,"height":24}},"padding":2,"priority":"required"}}]}}
Coordinates must be integer source-image pixels, tightly enclose one element, and remain inside the image. Use stable semantic English names. Do not merge separate icons into one box."""
    data = extract_json(client.chat(prompt, images=[visual], max_tokens=4096, reasoning_effort="low"))
    icons = data.get("icons", []) if isinstance(data, dict) else []
    if not isinstance(icons, list):
        raise ValueError("icon inventory must contain an icons array")
    return icons


def _clamp_bbox(bbox: dict[str, Any], width: int, height: int) -> tuple[int, int, int, int]:
    x = max(0, min(width - 1, int(bbox.get("x", 0))))
    y = max(0, min(height - 1, int(bbox.get("y", 0))))
    w = max(1, int(bbox.get("width", 1)))
    h = max(1, int(bbox.get("height", 1)))
    return x, y, min(width, x + w), min(height, y + h)


def remove_border_background(image: Image.Image, threshold: float = 24.0) -> Image.Image:
    """Remove border-connected pixels similar to the crop's corner colors."""
    rgba = np.array(image.convert("RGBA"), dtype=np.uint8)
    height, width = rgba.shape[:2]
    corner = max(1, min(width, height, 4))
    samples = np.concatenate(
        [
            rgba[:corner, :corner, :3].reshape(-1, 3),
            rgba[:corner, -corner:, :3].reshape(-1, 3),
            rgba[-corner:, :corner, :3].reshape(-1, 3),
            rgba[-corner:, -corner:, :3].reshape(-1, 3),
        ]
    ).astype(np.float32)
    background = np.median(samples, axis=0)
    distance = np.linalg.norm(rgba[:, :, :3].astype(np.float32) - background, axis=2)
    candidate = distance <= threshold
    visited = np.zeros((height, width), dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        if candidate[0, x]: queue.append((0, x))
        if candidate[height - 1, x]: queue.append((height - 1, x))
    for y in range(height):
        if candidate[y, 0]: queue.append((y, 0))
        if candidate[y, width - 1]: queue.append((y, width - 1))
    while queue:
        y, x = queue.popleft()
        if visited[y, x] or not candidate[y, x]:
            continue
        visited[y, x] = True
        if y: queue.append((y - 1, x))
        if y + 1 < height: queue.append((y + 1, x))
        if x: queue.append((y, x - 1))
        if x + 1 < width: queue.append((y, x + 1))
    rgba[visited, 3] = 0
    rgba[visited, :3] = 0
    return Image.fromarray(rgba, "RGBA")


def trim_transparent(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    return image.crop(bbox) if bbox else Image.new("RGBA", (1, 1), (0, 0, 0, 0))


def normalize_icon(image: Image.Image, cell_size: int, padding: int) -> Image.Image:
    icon = trim_transparent(image.convert("RGBA"))
    available = max(1, cell_size - 2 * padding)
    scale = min(available / icon.width, available / icon.height, 1.0 if max(icon.size) <= available else 10.0)
    size = (max(1, round(icon.width * scale)), max(1, round(icon.height * scale)))
    icon = icon.resize(size, Image.Resampling.LANCZOS)
    result = Image.new("RGBA", (cell_size, cell_size), (0, 0, 0, 0))
    result.alpha_composite(icon, ((cell_size - icon.width) // 2, (cell_size - icon.height) // 2))
    return result


def compare_icon_reference(reference: Image.Image, actual: Image.Image) -> dict[str, float]:
    a = np.asarray(reference.convert("RGBA"), dtype=np.float32)
    b = np.asarray(actual.convert("RGBA"), dtype=np.float32)
    alpha_a = a[:, :, 3] > 8
    alpha_b = b[:, :, 3] > 8
    union = np.logical_or(alpha_a, alpha_b).sum()
    intersection = np.logical_and(alpha_a, alpha_b).sum()
    alpha_iou = float(intersection / union) if union else 1.0
    rgb_mae = float(np.abs(a[:, :, :3] - b[:, :, :3]).mean() / 255.0)
    score = max(0.0, min(1.0, 0.7 * alpha_iou + 0.3 * (1.0 - rgb_mae)))
    return {"alpha_iou": alpha_iou, "rgb_mae": rgb_mae, "score": score}


def build_sprite_atlas(
    visual: str | Path,
    icons: list[dict[str, Any]],
    output_dir: str | Path,
    *,
    cell_size: int = 128,
    columns: int | None = None,
    background_threshold: float = 24.0,
    client: OpenAICompatibleClient | None = None,
    mode: str = "crop",
) -> dict[str, Any]:
    visual_path = Path(visual).expanduser().resolve()
    root = Path(output_dir).expanduser().resolve()
    assets_dir = root / "icons"
    assets_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(visual_path) as opened:
        source = opened.convert("RGBA")
    names = unique_slugs([str(icon.get("name") or f"icon-{i + 1}") for i, icon in enumerate(icons)])
    count = len(icons)
    if count == 0:
        raise ValueError("no icons were supplied or detected")
    columns = columns or math.ceil(math.sqrt(count))
    rows = math.ceil(count / columns)
    atlas = Image.new("RGBA", (columns * cell_size, rows * cell_size), (0, 0, 0, 0))
    entries: list[dict[str, Any]] = []
    for index, (name, spec) in enumerate(zip(names, icons)):
        box = _clamp_bbox(spec.get("bbox") or {}, source.width, source.height)
        crop = source.crop(box)
        raw_path = assets_dir / f"{name}-source.png"
        crop.save(raw_path)
        padding = max(0, min(cell_size // 3, int(spec.get("padding", 8))))
        source_reference = normalize_icon(remove_border_background(crop, background_threshold), cell_size, padding)
        reference_path = assets_dir / f"{name}-reference.png"
        source_reference.save(reference_path)
        if mode == "generate":
            if client is None:
                raise ValueError("generate mode requires an API client")
            generated = assets_dir / f"{name}-generated.png"
            client.generate_image(
                "Create one isolated UI icon centered on a perfectly flat solid #FF00FF magenta chroma-key background. "
                f"Icon: {spec.get('description') or name}. Match the source UI's visual language exactly. "
                "No transparency checkerboard, no shadow, no text, no border frame, no mockup, no extra objects, crisp edges.",
                generated,
                size="1024x1024",
            )
            with Image.open(generated) as generated_image:
                prepared = remove_border_background(generated_image, max(background_threshold, 36.0))
        else:
            prepared = remove_border_background(crop, background_threshold)
        normalized = normalize_icon(prepared, cell_size, padding)
        icon_path = assets_dir / f"{name}.png"
        normalized.save(icon_path)
        column = index % columns
        row = index // columns
        x, y = column * cell_size, row * cell_size
        atlas.alpha_composite(normalized, (x, y))
        entries.append(
            {
                "name": name,
                "description": str(spec.get("description", "")),
                "priority": str(spec.get("priority", "required")),
                "source_bbox": {"x": box[0], "y": box[1], "width": box[2] - box[0], "height": box[3] - box[1]},
                "atlas": {"x": x, "y": y, "width": cell_size, "height": cell_size},
                "source_crop": str(raw_path),
                "source_reference": str(reference_path),
                "asset": str(icon_path),
                "visual_match": compare_icon_reference(source_reference, normalized),
            }
        )
    root.mkdir(parents=True, exist_ok=True)
    png_path = root / "spritesheet.png"
    webp_path = root / "spritesheet.webp"
    atlas.save(png_path)
    atlas.save(webp_path, format="WEBP", lossless=True)
    manifest = {
        "version": 1,
        "created_at": utc_now(),
        "source_visual": str(visual_path),
        "mode": mode,
        "image": {"png": str(png_path), "webp": str(webp_path), "width": atlas.width, "height": atlas.height},
        "grid": {"columns": columns, "rows": rows, "cell_width": cell_size, "cell_height": cell_size},
        "icons": entries,
    }
    write_json(root / "spritesheet.json", manifest)
    (root / "spritesheet.css").write_text(render_css(manifest), encoding="utf-8")
    make_contact_sheet(atlas, entries, root / "contact-sheet.png", cell_size)
    validation = validate_atlas(atlas, entries)
    write_json(root / "validation.json", validation)
    return manifest


def render_css(manifest: dict[str, Any]) -> str:
    width = manifest["image"]["width"]
    height = manifest["image"]["height"]
    lines = [
        ".sprite-icon {",
        "  display: inline-block;",
        "  background-image: url('./spritesheet.webp');",
        "  background-repeat: no-repeat;",
        f"  background-size: {width}px {height}px;",
        "}",
        "",
    ]
    for icon in manifest["icons"]:
        atlas = icon["atlas"]
        lines.extend(
            [
                f".sprite-{icon['name']} {{",
                f"  width: {atlas['width']}px;",
                f"  height: {atlas['height']}px;",
                f"  background-position: -{atlas['x']}px -{atlas['y']}px;",
                "}",
                "",
            ]
        )
    return "\n".join(lines)


def validate_atlas(atlas: Image.Image, entries: list[dict[str, Any]]) -> dict[str, Any]:
    errors = []
    for entry in entries:
        a = entry["atlas"]
        cell = atlas.crop((a["x"], a["y"], a["x"] + a["width"], a["y"] + a["height"]))
        if cell.getchannel("A").getbbox() is None:
            errors.append(f"{entry['name']} is empty")
    visual_scores = [entry["visual_match"]["score"] for entry in entries]
    return {
        "ok": not errors,
        "icon_count": len(entries),
        "errors": errors,
        "sprite_vs_visual": {
            "mean_score": float(sum(visual_scores) / len(visual_scores)) if visual_scores else 0.0,
            "minimum_score": float(min(visual_scores)) if visual_scores else 0.0,
            "icons": {entry["name"]: entry["visual_match"] for entry in entries},
        },
    }


def make_contact_sheet(atlas: Image.Image, entries: list[dict[str, Any]], output: Path, cell_size: int) -> None:
    label_height = 24
    columns = max(1, min(4, len(entries)))
    rows = math.ceil(len(entries) / columns)
    sheet = Image.new("RGB", (columns * cell_size, rows * (cell_size + label_height)), "#f2f2f2")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, entry in enumerate(entries):
        col, row = index % columns, index // columns
        x, y = col * cell_size, row * (cell_size + label_height)
        a = entry["atlas"]
        icon = atlas.crop((a["x"], a["y"], a["x"] + cell_size, a["y"] + cell_size))
        checker = Image.new("RGB", (cell_size, cell_size), "white")
        checker.paste(icon, mask=icon.getchannel("A"))
        sheet.paste(checker, (x, y))
        draw.rectangle((x, y, x + cell_size - 1, y + cell_size - 1), outline="#bbbbbb")
        draw.rectangle((x, y + cell_size, x + cell_size - 1, y + cell_size + label_height - 1), fill="#111111")
        draw.text((x + 5, y + cell_size + 6), entry["name"][:24], fill="white", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
