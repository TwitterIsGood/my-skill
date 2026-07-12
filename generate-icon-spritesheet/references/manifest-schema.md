# Manifest schema

```json
{
  "name": "smallweiba-categories",
  "style": "Friendly rounded clay-like pet-care app icon, soft warm palette, subtle depth, clean silhouette, consistent three-quarter front view, no border, no text",
  "cell": { "width": 128, "height": 128, "padding": 14 },
  "background": { "mode": "chroma", "color": "#FF00FF", "threshold": 72, "feather": 28 },
  "columns": 4,
  "icons": [
    { "name": "health", "prompt": "A veterinary cross combined with a small paw" },
    { "name": "grooming", "prompt": "A pet grooming brush with a tiny paw detail" },
    { "name": "cleaning", "prompt": "A clean litter scoop with one sparkle" },
    { "name": "food", "prompt": "A pet food bowl with two pieces of kibble" }
  ]
}
```

Rules:

- `name`: set identifier used in metadata.
- `style`: shared visual contract appended to every generation prompt.
- `cell.width`, `cell.height`: final atlas cell dimensions in pixels.
- `cell.padding`: transparent inset around fitted artwork.
- `columns`: optional positive integer; defaults to a near-square grid.
- `background.mode`: `transparent` or `chroma`. Use `chroma` for compatible proxies that paint a checkerboard instead of returning real alpha.
- `background.color`: chroma-key color in `#RRGGBB`; choose a color absent from the icon palette.
- `background.threshold` and `feather`: color-distance cutoff and anti-alias transition width.
- `icons`: ordered list. `name` must match `[a-z][a-z0-9-]*` and be unique.
- `icons[].prompt`: subject-specific instruction. Do not repeat the entire shared style.
- `icons[].negative_prompt`: optional extra avoidances appended to the prompt.

The generated JSON preserves manifest order and includes both pixel rectangles and normalized UV coordinates.
