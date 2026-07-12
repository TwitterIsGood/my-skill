#!/usr/bin/env python3
"""Generate transparent icons with an OpenAI-compatible API and pack an atlas."""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Pillow is required. In Codex, load workspace dependencies and use its bundled Python; "
        "otherwise install Pillow in the active Python environment."
    ) from exc

NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
IMAGE_SUFFIXES = (".png", ".webp", ".jpg", ".jpeg")


def config_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "generate-icon-spritesheet" / "config.json"


def load_user_config() -> dict[str, str]:
    path = config_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"could not read config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"config must be a JSON object: {path}")
    return {key: value for key, value in data.items() if isinstance(value, str)}


def save_user_config(data: dict[str, str]) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def configure(args: argparse.Namespace) -> None:
    current = load_user_config()
    base_url = args.base_url or input(f"Base URL [{current.get('base_url', 'https://api.openai.com')}]: ").strip() or current.get("base_url", "https://api.openai.com")
    model = args.model or input(f"Image model [{current.get('model', 'gpt-image-2')}]: ").strip() or current.get("model", "gpt-image-2")
    api_key = args.api_key or getpass.getpass("API key (hidden; leave blank to keep the saved key): ").strip() or current.get("api_key", "")
    if not api_key:
        raise SystemExit("API key is required")
    path = save_user_config({"base_url": base_url.rstrip("/"), "model": model, "api_key": api_key})
    print(json.dumps({"ok": True, "config": str(path), "base_url": base_url.rstrip("/"), "model": model}, indent=2))


def connection_settings(args: argparse.Namespace) -> tuple[str, str, str]:
    saved = load_user_config()
    base_url = args.base_url or os.environ.get("ICON_IMAGE_BASE_URL") or saved.get("base_url", "")
    model = args.model or os.environ.get("ICON_IMAGE_MODEL") or saved.get("model", "")
    token = os.environ.get("ICON_IMAGE_API_TOKEN") or saved.get("api_key", "")
    if not (base_url and model and token):
        if not sys.stdin.isatty():
            raise SystemExit(
                f"image API is not configured. Run this script with the configure command; settings are saved to {config_path()}"
            )
        print("First-time image API setup. Credentials stay in your user config directory.")
        configure(argparse.Namespace(base_url=base_url or None, model=model or None, api_key=None))
        saved = load_user_config()
        base_url, model, token = saved["base_url"], saved["model"], saved["api_key"]
    return base_url, model, token


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("manifest must be a JSON object")
    icons = data.get("icons")
    if not isinstance(icons, list) or not icons:
        raise SystemExit("manifest.icons must be a non-empty array")
    names: list[str] = []
    for index, icon in enumerate(icons):
        if not isinstance(icon, dict):
            raise SystemExit(f"icons[{index}] must be an object")
        name = icon.get("name")
        prompt = icon.get("prompt")
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            raise SystemExit(f"invalid icon name at index {index}: {name!r}")
        if not isinstance(prompt, str) or not prompt.strip():
            raise SystemExit(f"icon {name} needs a prompt")
        names.append(name)
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise SystemExit(f"duplicate icon names: {', '.join(duplicates)}")
    cell = data.setdefault("cell", {})
    for key, default in (("width", 128), ("height", 128), ("padding", 12)):
        value = cell.setdefault(key, default)
        if not isinstance(value, int) or value < (0 if key == "padding" else 1):
            raise SystemExit(f"cell.{key} must be a valid integer")
    if cell["padding"] * 2 >= min(cell["width"], cell["height"]):
        raise SystemExit("cell.padding leaves no drawable area")
    return data


def resolved_prompt(manifest: dict[str, Any], icon: dict[str, Any]) -> str:
    style = str(manifest.get("style", "")).strip()
    negative = str(icon.get("negative_prompt", "")).strip()
    background = manifest.get("background", {})
    if isinstance(background, dict) and background.get("mode") == "chroma":
        color = str(background.get("color", "#FF00FF"))
        background_instruction = (
            f"Use a perfectly flat solid {color} background filling every pixel outside the icon. "
            "Do not draw checkerboards, gradients, texture, shadows, or lighting on the background."
        )
    else:
        background_instruction = "Use a genuinely transparent background; do not draw a checkerboard."
    parts = [
        "Create exactly one standalone UI icon.",
        str(icon["prompt"]).strip(),
        style,
        background_instruction,
        "Centered composition, no text, no letters, no watermark, no frame, no mockup.",
        "Keep generous empty padding around the subject and make the silhouette readable at small size.",
    ]
    if negative:
        parts.append(f"Avoid: {negative}.")
    return " ".join(part for part in parts if part)


def api_endpoint(base_url: str, api_path: str) -> str:
    base = base_url.rstrip("/")
    path = api_path if api_path.startswith("/") else f"/{api_path}"
    if path.startswith("/v1/") and base.endswith("/v1"):
        path = path[3:]
    return base + path


def post_json(url: str, token: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:2000]
        if exc.code == 404 and url.rstrip("/").endswith("/v1/images/generations"):
            raise RuntimeError(
                "image API route /v1/images/generations returned HTTP 404. "
                "For CLI Proxy API (CPA), this means the model may appear in /v1/models while "
                "the image-generation route/plugin is not enabled on the server. Upgrade or "
                "enable the CPA image support plugin, then retry."
            ) from exc
        raise RuntimeError(f"image API returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"image API request failed: {exc.reason}") from exc


def download(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": "image/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def image_bytes(response: dict[str, Any], timeout: int) -> bytes:
    data = response.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise RuntimeError("image API response has no data[0]")
    item = data[0]
    encoded = item.get("b64_json") or item.get("b64")
    if isinstance(encoded, str):
        return base64.b64decode(encoded)
    url = item.get("url")
    if isinstance(url, str):
        return download(url, timeout)
    raise RuntimeError("image API response has neither b64_json nor url")


def generate(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = load_manifest(manifest_path)
    output_dir = Path(args.output_dir).expanduser().resolve()
    source_dir = output_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        saved = load_user_config()
        base_url = args.base_url or os.environ.get("ICON_IMAGE_BASE_URL") or saved.get("base_url", "https://api.openai.com")
        model = args.model or os.environ.get("ICON_IMAGE_MODEL") or saved.get("model", "gpt-image-2")
        token = ""
    else:
        base_url, model, token = connection_settings(args)
    endpoint = api_endpoint(base_url, args.api_path)
    jobs = []
    for icon in manifest["icons"]:
        prompt = resolved_prompt(manifest, icon)
        target = source_dir / f"{icon['name']}.png"
        job = {"name": icon["name"], "output": str(target), "prompt": prompt}
        jobs.append(job)
        if args.dry_run:
            continue
        if target.exists() and not args.force:
            print(f"skip existing {target.name}")
            continue
        payload: dict[str, Any] = {"model": model, "prompt": prompt, "size": args.size}
        if not args.minimal_payload:
            payload.update({"quality": args.quality, "output_format": "png"})
            background = manifest.get("background", {})
            if not isinstance(background, dict) or background.get("mode", "transparent") == "transparent":
                payload["background"] = "transparent"
        print(f"generating {icon['name']}...", flush=True)
        response = post_json(endpoint, token, payload, args.timeout)
        raw = image_bytes(response, args.timeout)
        with Image.open(BytesIO(raw)) as opened:
            opened.convert("RGBA").save(target, format="PNG")
    (output_dir / "generation-jobs.json").write_text(
        json.dumps({"endpoint": endpoint, "model": model, "jobs": jobs}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "dry_run": args.dry_run, "jobs": len(jobs), "source_dir": str(source_dir)}, indent=2))


def find_source(source_dir: Path, name: str) -> Path:
    for suffix in IMAGE_SUFFIXES:
        candidate = source_dir / f"{name}{suffix}"
        if candidate.is_file():
            return candidate
    raise SystemExit(f"missing source icon: {name}")


def parse_hex_color(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise SystemExit(f"invalid chroma color: {value}")
    return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))


def remove_chroma(image: Image.Image, background: dict[str, Any]) -> Image.Image:
    key = parse_hex_color(str(background.get("color", "#FF00FF")))
    threshold = float(background.get("threshold", 72))
    feather = max(1.0, float(background.get("feather", 28)))
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = pixels[x, y]
            distance = math.sqrt((red - key[0]) ** 2 + (green - key[1]) ** 2 + (blue - key[2]) ** 2)
            if distance <= threshold:
                pixels[x, y] = (0, 0, 0, 0)
            elif distance < threshold + feather:
                new_alpha = round(alpha * (distance - threshold) / feather)
                pixels[x, y] = (red, green, blue, new_alpha)
    return rgba


def normalize_icon(path: Path, width: int, height: int, padding: int, background: dict[str, Any]) -> Image.Image:
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
    if background.get("mode") == "chroma":
        image = remove_chroma(image, background)
    corners = [image.getpixel((0, 0))[3], image.getpixel((image.width - 1, 0))[3], image.getpixel((0, image.height - 1))[3], image.getpixel((image.width - 1, image.height - 1))[3]]
    if all(alpha > 250 for alpha in corners):
        raise SystemExit(f"{path.name} appears to have an opaque background")
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise SystemExit(f"{path.name} is fully transparent")
    art = image.crop(bbox)
    max_w, max_h = width - 2 * padding, height - 2 * padding
    scale = min(max_w / art.width, max_h / art.height)
    art = art.resize((max(1, round(art.width * scale)), max(1, round(art.height * scale))), Image.Resampling.LANCZOS)
    cell = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cell.alpha_composite(art, ((width - art.width) // 2, (height - art.height) // 2))
    return cell


def swift_identifier(name: str) -> str:
    parts = name.split("-")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def swift_file(set_name: str, frames: list[dict[str, Any]], atlas_w: int, atlas_h: int) -> str:
    cases = "\n".join(f"        case {swift_identifier(frame['name'])} = \"{frame['name']}\"" for frame in frames)
    rects = "\n".join(
        f"        .{swift_identifier(frame['name'])}: CGRect(x: {frame['frame']['x']}, y: {frame['frame']['y']}, width: {frame['frame']['w']}, height: {frame['frame']['h']}),"
        for frame in frames
    )
    return f'''// Generated by generate-icon-spritesheet. Do not edit manually.
import CoreGraphics
import UIKit

enum IconSprites {{
    static let setName = "{set_name}"
    static let atlasPixelSize = CGSize(width: {atlas_w}, height: {atlas_h})

    enum Name: String, CaseIterable {{
{cases}
    }}

    static let frames: [Name: CGRect] = [
{rects}
    ]

    static func image(_ name: Name, from atlas: UIImage) -> UIImage? {{
        guard let frame = frames[name], let cgImage = atlas.cgImage else {{ return nil }}
        let scaleX = CGFloat(cgImage.width) / atlasPixelSize.width
        let scaleY = CGFloat(cgImage.height) / atlasPixelSize.height
        let crop = CGRect(x: frame.minX * scaleX, y: frame.minY * scaleY, width: frame.width * scaleX, height: frame.height * scaleY).integral
        guard let cropped = cgImage.cropping(to: crop) else {{ return nil }}
        return UIImage(cgImage: cropped, scale: atlas.scale, orientation: .up)
    }}
}}
'''


def pack(args: argparse.Namespace) -> None:
    manifest = load_manifest(Path(args.manifest).expanduser().resolve())
    source_dir = Path(args.source_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cell = manifest["cell"]
    width, height, padding = cell["width"], cell["height"], cell["padding"]
    count = len(manifest["icons"])
    columns = manifest.get("columns") or math.ceil(math.sqrt(count))
    if not isinstance(columns, int) or columns < 1:
        raise SystemExit("columns must be a positive integer")
    rows = math.ceil(count / columns)
    atlas_w, atlas_h = columns * width, rows * height
    atlas = Image.new("RGBA", (atlas_w, atlas_h), (0, 0, 0, 0))
    frames: list[dict[str, Any]] = []
    normalized: list[tuple[str, Image.Image]] = []
    for index, icon in enumerate(manifest["icons"]):
        name = icon["name"]
        background = manifest.get("background", {})
        if not isinstance(background, dict):
            raise SystemExit("background must be an object")
        image = normalize_icon(find_source(source_dir, name), width, height, padding, background)
        column, row = index % columns, index // columns
        x, y = column * width, row * height
        atlas.alpha_composite(image, (x, y))
        normalized.append((name, image))
        frames.append({
            "name": name,
            "frame": {"x": x, "y": y, "w": width, "h": height},
            "uv": {"x": x / atlas_w, "y": y / atlas_h, "w": width / atlas_w, "h": height / atlas_h},
        })
    atlas.save(output_dir / "spritesheet.png")
    metadata = {
        "name": manifest.get("name", "icon-sprites"),
        "image": "spritesheet.png",
        "size": {"width": atlas_w, "height": atlas_h},
        "cell": cell,
        "grid": {"columns": columns, "rows": rows},
        "frames": frames,
    }
    (output_dir / "spritesheet.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "IconSprites.swift").write_text(swift_file(metadata["name"], frames, atlas_w, atlas_h), encoding="utf-8")
    label_h = 22
    contact = Image.new("RGBA", (atlas_w, rows * (height + label_h)), (245, 245, 245, 255))
    draw = ImageDraw.Draw(contact)
    font = ImageFont.load_default()
    for index, (name, image) in enumerate(normalized):
        column, row = index % columns, index // columns
        x, y = column * width, row * (height + label_h)
        checker = Image.new("RGBA", (width, height), (225, 225, 225, 255))
        checker.alpha_composite(image)
        contact.alpha_composite(checker, (x, y))
        draw.text((x + 4, y + height + 5), name, fill=(25, 25, 25, 255), font=font)
    contact.convert("RGB").save(output_dir / "contact-sheet.png")
    print(json.dumps({"ok": True, "icons": count, "atlas": str(output_dir / 'spritesheet.png'), "metadata": str(output_dir / 'spritesheet.json')}, indent=2))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("configure", help="Save first-use API settings in the user config directory")
    setup.add_argument("--base-url")
    setup.add_argument("--model")
    setup.add_argument("--api-key", help=argparse.SUPPRESS)
    setup.set_defaults(func=configure)
    gen = commands.add_parser("generate", help="Generate one transparent source PNG per manifest icon")
    gen.add_argument("--manifest", required=True)
    gen.add_argument("--output-dir", required=True)
    gen.add_argument("--base-url")
    gen.add_argument("--model")
    gen.add_argument("--api-path", default="/v1/images/generations")
    gen.add_argument("--size", default="1024x1024")
    gen.add_argument("--quality", default="high")
    gen.add_argument("--timeout", type=int, default=180)
    gen.add_argument("--minimal-payload", action="store_true")
    gen.add_argument("--dry-run", action="store_true")
    gen.add_argument("--force", action="store_true")
    gen.set_defaults(func=generate)
    packing = commands.add_parser("pack", help="Normalize source icons and create atlas metadata")
    packing.add_argument("--manifest", required=True)
    packing.add_argument("--source-dir", required=True)
    packing.add_argument("--output-dir", required=True)
    packing.set_defaults(func=pack)
    return root


def main() -> None:
    args = parser().parse_args()
    try:
        args.func(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
