from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image

from .api import OpenAICompatibleClient, extract_json
from .diff import compare_images
from .render import render_html
from .utils import ensure_within, utc_now, write_json


ALLOWED_SUFFIXES = {".html", ".css", ".js", ".mjs", ".json", ".svg", ".txt"}


def prepare_model_image(source: str | Path, output: str | Path, max_dimension: int = 1200) -> Path:
    source_path = Path(source).expanduser().resolve()
    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as opened:
        image = opened.convert("RGB")
        scale = min(1.0, max_dimension / max(image.size))
        if scale < 1.0:
            image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
        image.save(output_path, format="JPEG", quality=86, optimize=True)
    return output_path


def apply_files(root: str | Path, files: dict[str, Any]) -> list[str]:
    written = []
    for relative, content in files.items():
        if not isinstance(relative, str) or not isinstance(content, str):
            raise ValueError("model files must map string paths to string contents")
        output = ensure_within(root, relative)
        if output.suffix.lower() not in ALLOWED_SUFFIXES:
            raise ValueError(f"unsupported generated file type: {relative}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        written.append(str(output))
    return written


def read_code_files(root: str | Path, max_chars: int = 100_000) -> dict[str, str]:
    base = Path(root).resolve()
    result: dict[str, str] = {}
    used = 0
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        remaining = max_chars - used
        if remaining <= 0:
            break
        result[str(path.relative_to(base))] = content[:remaining]
        used += len(result[str(path.relative_to(base))])
    return result


def _sprite_context(sprite_manifest: str | Path | None) -> tuple[str, Path | None]:
    if not sprite_manifest:
        return "No sprite atlas was supplied.", None
    path = Path(sprite_manifest).expanduser().resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    compact = {
        "grid": data.get("grid"),
        "icons": [{"name": i["name"], "description": i.get("description", ""), "atlas": i["atlas"]} for i in data.get("icons", [])],
    }
    return json.dumps(compact, ensure_ascii=False), path


def reproduce_ui(
    client: OpenAICompatibleClient,
    visual: str | Path,
    output_dir: str | Path,
    *,
    sprite_manifest: str | Path | None = None,
    threshold: float = 0.985,
    max_iterations: int = 5,
    chrome: str | None = None,
) -> dict[str, Any]:
    visual_path = Path(visual).expanduser().resolve()
    root = Path(output_dir).expanduser().resolve()
    site = root / "site"
    iterations = root / "iterations"
    site.mkdir(parents=True, exist_ok=True)
    sprite_context, manifest_path = _sprite_context(sprite_manifest)
    if manifest_path:
        sprite_root = manifest_path.parent
        assets = site / "assets"
        assets.mkdir(exist_ok=True)
        for name in ("spritesheet.webp", "spritesheet.png", "spritesheet.css", "spritesheet.json"):
            source = sprite_root / name
            if source.is_file():
                shutil.copy2(source, assets / name)
    with Image.open(visual_path) as image:
        width, height = image.size
    model_visual = prepare_model_image(visual_path, root / "model-input" / "target.jpg")
    analysis_prompt = f"""Analyze the attached {width}x{height} UI target for exact frontend reconstruction.
Return JSON only. Capture: canvas/background, sidebar/header geometry, every major rectangle with approximate pixel x/y/width/height, spacing system, typography sizes/weights/colors, borders/radii/shadows, gradients, charts, table columns/rows, all visible text and numbers, and where each named sprite icon appears with approximate rendered size.
Do not write code. Be concise but complete enough for another model to build the page without seeing the image.

Available sprite contract:
{sprite_context}"""
    analysis_response = client.chat(analysis_prompt, images=[model_visual], max_tokens=6000, reasoning_effort="low")
    (root / "visual-spec-response.txt").write_text(analysis_response, encoding="utf-8")
    visual_spec = extract_json(analysis_response)
    write_json(root / "visual-spec.json", visual_spec)
    base_prompt = f"""Reproduce a UI as an interactive, production-quality local web page whose initial visual state is exactly {width}x{height} CSS pixels using the structured visual specification below.
Return JSON only in this shape: {{"files":{{"index.html":"...","styles.css":"...","app.js":"..."}},"notes":"short summary"}}.
Use semantic HTML and deterministic local CSS/JS only. Do not use network resources, external fonts, inline base64 images, canvas screenshot tracing, or an SVG that redraws the whole visual. The page must render directly from site/index.html. Implement meaningful interactions for every visible button, category, navigation item, expandable list, and primary action. Mobile pages must scroll naturally when their content exceeds the viewport. Keep dialogs, drawers, menus, and expanded states closed initially so screenshot comparison still measures the supplied visual state.
Match layout, typography, colors, borders, radii, shadows, spacing, and content as precisely as possible.

Structured visual specification:
{json.dumps(visual_spec, ensure_ascii=False)}

Sprite atlas contract:
{sprite_context}

When a supplied icon is visible, use a span with classes `sprite-icon sprite-<name>` and load `assets/spritesheet.css`. The CSS file points to its own adjacent spritesheet. Scale icons with wrapper transforms only when required; never guess or rewrite atlas coordinates."""
    response = client.chat(base_prompt, max_tokens=12000)
    (root / "initial-response.txt").write_text(response, encoding="utf-8")
    data = extract_json(response)
    apply_files(site, data.get("files", {}))
    if not (site / "index.html").is_file():
        raise ValueError("model response did not create index.html")
    history = []
    for iteration in range(max_iterations + 1):
        iteration_dir = iterations / f"{iteration:02d}"
        screenshot = render_html(site / "index.html", iteration_dir / "screenshot.png", width=width, height=height, chrome=chrome)
        metrics = compare_images(visual_path, screenshot, iteration_dir)
        metrics["iteration"] = iteration
        history.append(metrics)
        if metrics["score"] >= threshold or iteration == max_iterations:
            break
        current_files = read_code_files(site)
        model_current = prepare_model_image(screenshot, iteration_dir / "model-current.jpg")
        model_heatmap = prepare_model_image(metrics["heatmap"], iteration_dir / "model-heatmap.jpg")
        diagnosis_prompt = f"""Compare the attached target UI, current screenshot, and difference heatmap.
Return JSON only with `largest_differences` in priority order and `repair_instructions` containing concrete pixel/layout/color/type/icon changes. Do not write code.
Metrics: {json.dumps(metrics)}"""
        diagnosis_response = client.chat(
            diagnosis_prompt,
            images=[model_visual, model_current, model_heatmap],
            max_tokens=4000,
            reasoning_effort="low",
        )
        (iteration_dir / "diagnosis-response.txt").write_text(diagnosis_response, encoding="utf-8")
        diagnosis = extract_json(diagnosis_response)
        write_json(iteration_dir / "diagnosis.json", diagnosis)
        repair_prompt = f"""Repair the current static UI implementation according to the visual diagnosis so its next screenshot matches the target specification more closely.
Return JSON only: {{"files":{{"path":"complete replacement content"}},"notes":"what changed"}}.
Only include files that need replacement. Preserve correct areas and existing working interactions. Continue using the supplied sprite atlas classes for matching icons. Do not add network resources, screenshot tracing, or a whole-page SVG.

Current metrics:
{json.dumps(metrics, indent=2)}

Visual diagnosis:
{json.dumps(diagnosis, ensure_ascii=False)}

Original structured visual specification:
{json.dumps(visual_spec, ensure_ascii=False)}

Current files:
{json.dumps(current_files, ensure_ascii=False)}

Prioritize the largest visible differences and return complete replacement contents for changed files."""
        repair = client.chat(repair_prompt, max_tokens=10000)
        (iteration_dir / "repair-response.txt").write_text(repair, encoding="utf-8")
        repair_data = extract_json(repair)
        apply_files(site, repair_data.get("files", {}))
    result = {
        "version": 1,
        "created_at": utc_now(),
        "target": str(visual_path),
        "site": str(site),
        "threshold": threshold,
        "max_iterations": max_iterations,
        "accepted": bool(history and history[-1]["score"] >= threshold),
        "best_score": max(item["score"] for item in history),
        "final_score": history[-1]["score"],
        "iterations": history,
    }
    write_json(root / "run.json", result)
    return result
