from __future__ import annotations

from pathlib import Path
from typing import Any

from .api import OpenAICompatibleClient
from .sprites import analyze_icons, build_sprite_atlas
from .utils import utc_now, write_json
from .visual import generate_visual, import_visual
from .reproduce import reproduce_ui


def run_pipeline(
    client: OpenAICompatibleClient,
    output_dir: str | Path,
    *,
    prompt: str | None = None,
    visual: str | Path | None = None,
    image_size: str = "1536x1024",
    sprite_mode: str = "crop",
    threshold: float = 0.985,
    max_iterations: int = 5,
) -> dict[str, Any]:
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {"version": 1, "created_at": utc_now(), "stages": {}}
    write_json(root / "run.json", state)
    visual_dir = root / "visual"
    if visual:
        visual_result = import_visual(visual, visual_dir)
    elif prompt:
        visual_result = generate_visual(client, prompt, visual_dir, size=image_size)
    else:
        raise ValueError("either prompt or visual is required")
    target = visual_result["image"]["path"]
    state["stages"]["visual"] = {"status": "complete", "result": visual_result}
    write_json(root / "run.json", state)
    icons = analyze_icons(client, target)
    sprite_result = build_sprite_atlas(target, icons, root / "sprites", client=client, mode=sprite_mode)
    state["stages"]["sprites"] = {"status": "complete", "manifest": str(root / "sprites" / "spritesheet.json"), "icon_count": len(sprite_result["icons"])}
    write_json(root / "run.json", state)
    reproduction = reproduce_ui(
        client,
        target,
        root / "reproduction",
        sprite_manifest=root / "sprites" / "spritesheet.json",
        threshold=threshold,
        max_iterations=max_iterations,
    )
    state["stages"]["reproduction"] = {"status": "complete", "result": reproduction}
    state["accepted"] = reproduction["accepted"]
    state["final_score"] = reproduction["final_score"]
    write_json(root / "run.json", state)
    return state
