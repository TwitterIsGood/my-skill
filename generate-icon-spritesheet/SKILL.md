---
name: generate-icon-spritesheet
description: Generate a visually consistent set of transparent UI icons with an OpenAI-compatible image model, then deterministically normalize, pack, validate, and export a spritesheet plus JSON and Swift metadata. Use when Codex needs icon families, tab-bar artwork, category icons, game/UI sprites, atlas data, CSS-style frame data, or iOS UIImage cropping metadata from a base URL, API token, and image model such as gpt-image-2.
---

# Generate Icon Spritesheet

Separate creative generation from deterministic packaging. Generate one transparent source PNG per icon, then use the bundled script to trim, normalize, pack, and export metadata.

The script requires Python 3.9+ and Pillow. In the Codex desktop app, call `load_workspace_dependencies` and run it with the returned bundled Python executable. Outside Codex, install Pillow into the selected Python environment.

## Security

On first use, run the interactive configuration command. It asks for Base URL, API key, and model name, hides the key while typing, and saves the settings to `${XDG_CONFIG_HOME:-~/.config}/generate-icon-spritesheet/config.json` with mode `0600`:

```bash
python3 <skill-dir>/scripts/icon_spritesheet.py configure
```

Never write credentials into manifests, repositories, generated metadata, or logs. Environment variables `ICON_IMAGE_BASE_URL`, `ICON_IMAGE_MODEL`, and `ICON_IMAGE_API_TOKEN` override saved settings for CI or temporary use. A normal `generate` command automatically starts first-use configuration when required and attached to a terminal.

## Workflow

1. Create a compact manifest using `references/manifest-schema.md`.
2. Define one shared `style` for the whole family. Each icon prompt describes only its subject and distinctive pose/symbol.
3. Run a dry run and review the resolved prompts:

```bash
python3 <skill-dir>/scripts/icon_spritesheet.py generate \
  --manifest path/to/icons.json --output-dir path/to/run --dry-run
```

4. Generate source icons. API calls are one icon at a time so failed icons can be retried without regenerating the set:

```bash
python3 <skill-dir>/scripts/icon_spritesheet.py generate \
  --manifest path/to/icons.json --output-dir path/to/run
```

5. Pack existing source icons into final assets:

```bash
python3 <skill-dir>/scripts/icon_spritesheet.py pack \
  --manifest path/to/icons.json --source-dir path/to/run/source \
  --output-dir path/to/run/output
```

6. Inspect `contact-sheet.png` visually. Regenerate only icons with inconsistent silhouette, palette, line weight, padding, or transparency, then pack again.
7. Copy approved outputs into the app asset location. Keep the manifest with the assets so the atlas is reproducible.

## Prompt rules

- Request one centered icon per image with transparent background and no text.
- Prefer manifest `background.mode: chroma` when a proxy ignores transparent output or paints a checkerboard. The script removes the declared flat key color deterministically.
- Keep palette, material, viewpoint, lighting, outline, corner language, and visual weight identical across the family.
- Prefer simple silhouettes readable at the requested cell size.
- Avoid baked-in drop shadows unless the manifest explicitly requests them.
- For SmallWeiBa, favor warm, friendly pet-care imagery and distinguish categories through subject shape before color.

## Output contract

The pack command writes:

- `spritesheet.png`: transparent fixed-grid atlas.
- `spritesheet.json`: pixel and normalized UV frames.
- `IconSprites.swift`: typed iOS frame metadata and a UIImage crop helper.
- `contact-sheet.png`: labeled QA preview; do not ship it in the app.

Fail packaging when an icon is missing, empty, fully opaque at all four corners, duplicated by name, or exceeds the declared cell geometry.

Use `--api-path` when the compatible service does not expose `/v1/images/generations`. Use `--minimal-payload` when a proxy rejects optional image parameters.

For CLI Proxy API (CPA), verify that the server actually exposes `POST /v1/images/generations`. A model can appear in `/v1/models` while the image route or support plugin remains disabled; in that state Chat Completions rejects the image model and the Images endpoint returns 404.
