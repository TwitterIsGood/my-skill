---
name: build-ui-sprite-atlas
description: Analyze a UI visual, inventory reusable icons and small visual assets, extract or regenerate them, and package a validated CSS spritesheet with JSON coordinates, CSS classes, source bounding boxes, contact-sheet QA, and per-icon files. Use for UI icon extraction, sprite atlas creation, sprite coordinate mapping, CSS background-position generation, or validating that a sprite atlas matches a visual design.
---

# Build UI Sprite Atlas

Convert every reusable non-text UI asset into an explicit atlas contract. Never make the UI implementation guess coordinates.

## Workflow

1. Use the canonical visual target from `generate-ui-visual` or an absolute image supplied by the user.
   Automatic icon inventory uses the configured UI model at low reasoning effort; atlas generation does not spend `xhigh` reasoning on coordinate extraction.
2. Run automatic inventory and exact crop extraction first from the configured local project. Keep relay credentials only in that project:

```bash
SKILL_DIR=/absolute/path/to/ui-replica-suite/skills/build-ui-sprite-atlas
"$SKILL_DIR/scripts/run.sh" \
  --visual /absolute/path/to/visual-target.png \
  --output-dir /absolute/path/to/run/sprites \
  --mode crop \
  --cell-size 128
```

3. Inspect `contact-sheet.png`, `validation.json`, and the labeled source crops under `icons/`.
4. Fix incorrect bounding boxes through an inventory JSON and rerun with `--inventory`. Use this shape:

```json
{"icons":[{"name":"search","description":"nav search icon","bbox":{"x":20,"y":30,"width":24,"height":24},"padding":8,"priority":"required"}]}
```

5. Use `--mode generate` only when source cropping cannot produce a clean reusable asset. This calls `gpt-image-2` once per icon; review identity, color, stroke weight, transparency, and silhouette afterward.
6. Treat `spritesheet.json` as authoritative. Use `.sprite-icon.sprite-<name>` from `spritesheet.css`; do not hand-author `background-position` values.

Read [references/spritesheet-contract.md](references/spritesheet-contract.md) before integrating the atlas. Fail the stage if a required icon is missing, empty, clipped, mislabeled, or visually inconsistent.
