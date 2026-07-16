# Spritesheet Contract

The stage emits:

- `spritesheet.png` and lossless `spritesheet.webp`
- `spritesheet.json`: atlas dimensions, grid, semantic icon names, source bounding boxes, and atlas rectangles
- `spritesheet.css`: `.sprite-icon` plus `.sprite-<name>` classes
- `icons/<name>-source.png`: QA crop from the target visual
- `icons/<name>-reference.png`: normalized source-visual reference used for sprite difference scoring
- `icons/<name>.png`: normalized transparent atlas cell
- `contact-sheet.png`: labeled human/model QA surface
- `validation.json`: deterministic empty-cell checks plus per-icon `sprite_vs_visual` alpha-IoU/RGB similarity scores

CSS coordinates are unscaled source pixels. If the UI needs a smaller icon, place it inside a sized wrapper and scale the sprite element without changing the manifest coordinates.
