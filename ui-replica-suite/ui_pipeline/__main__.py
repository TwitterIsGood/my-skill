from __future__ import annotations

import argparse
import json
from pathlib import Path

from .api import OpenAICompatibleClient
from .config import Settings
from .pipeline import run_pipeline
from .reproduce import reproduce_ui
from .sprites import analyze_icons, build_sprite_atlas
from .visual import generate_visual, import_visual


def client() -> OpenAICompatibleClient:
    return OpenAICompatibleClient(Settings.from_env())


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m ui_pipeline", description="UI visual, sprite atlas, reproduction, and visual convergence pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    models = sub.add_parser("models", help="List relay models")

    visual = sub.add_parser("visual", help="Generate or import a UI visual target")
    visual_group = visual.add_mutually_exclusive_group(required=True)
    visual_group.add_argument("--prompt")
    visual_group.add_argument("--input")
    visual.add_argument("--output-dir", required=True)
    visual.add_argument("--size", default="1536x1024")

    sprites = sub.add_parser("sprites", help="Analyze a UI and build its sprite atlas")
    sprites.add_argument("--visual", required=True)
    sprites.add_argument("--output-dir", required=True)
    sprites.add_argument("--inventory", help="Existing icon inventory JSON; skips model analysis")
    sprites.add_argument("--mode", choices=("crop", "generate"), default="crop")
    sprites.add_argument("--cell-size", type=int, default=128)
    sprites.add_argument("--columns", type=int)

    reproduce = sub.add_parser("reproduce", help="Generate code and iterate with screenshot diffs")
    reproduce.add_argument("--visual", required=True)
    reproduce.add_argument("--output-dir", required=True)
    reproduce.add_argument("--sprite-manifest")
    reproduce.add_argument("--threshold", type=float, default=0.985)
    reproduce.add_argument("--max-iterations", type=int, default=5)
    reproduce.add_argument("--chrome")

    pipeline = sub.add_parser("pipeline", help="Run all stages")
    source = pipeline.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt")
    source.add_argument("--visual")
    pipeline.add_argument("--output-dir", required=True)
    pipeline.add_argument("--image-size", default="1536x1024")
    pipeline.add_argument("--sprite-mode", choices=("crop", "generate"), default="crop")
    pipeline.add_argument("--threshold", type=float, default=0.985)
    pipeline.add_argument("--max-iterations", type=int, default=5)

    args = parser.parse_args()
    if args.command == "models":
        result = client().list_models()
    elif args.command == "visual":
        result = generate_visual(client(), args.prompt, args.output_dir, size=args.size) if args.prompt else import_visual(args.input, args.output_dir)
    elif args.command == "sprites":
        api = None
        if args.inventory:
            raw = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
            icons = raw.get("icons", raw) if isinstance(raw, dict) else raw
            if args.mode == "generate":
                api = client()
        else:
            api = client()
            icons = analyze_icons(api, args.visual)
        result = build_sprite_atlas(args.visual, icons, args.output_dir, cell_size=args.cell_size, columns=args.columns, client=api, mode=args.mode)
    elif args.command == "reproduce":
        result = reproduce_ui(client(), args.visual, args.output_dir, sprite_manifest=args.sprite_manifest, threshold=args.threshold, max_iterations=args.max_iterations, chrome=args.chrome)
    else:
        result = run_pipeline(client(), args.output_dir, prompt=args.prompt, visual=args.visual, image_size=args.image_size, sprite_mode=args.sprite_mode, threshold=args.threshold, max_iterations=args.max_iterations)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
