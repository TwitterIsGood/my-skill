# Acceptance Contract

Required output:

- `site/index.html` plus local CSS/JS
- `site/assets/spritesheet.*` when a sprite manifest is supplied
- `iterations/<n>/screenshot.png`
- `iterations/<n>/heatmap.png`
- `iterations/<n>/metrics.json`
- `run.json`

Accept only when `run.json.accepted` is true and a visual review finds no obvious layout, content, typography, color, icon, clipping, or responsive viewport errors. A configured threshold of `0.985` is intentionally strict; lower it only for exploratory runs.

Also exercise every visible control. Mobile pages must scroll, sheets/modals must close with backdrop and Escape, forms must validate, navigation must provide visible behavior, and the page must remain usable at narrow device widths.
