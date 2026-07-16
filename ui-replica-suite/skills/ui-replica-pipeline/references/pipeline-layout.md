# Pipeline Layout

```text
<run>/
  run.json
  visual/
    visual-target.png
    run.json
  sprites/
    spritesheet.png
    spritesheet.webp
    spritesheet.json
    spritesheet.css
    contact-sheet.png
    validation.json
    icons/
  reproduction/
    run.json
    site/
    iterations/
```

The top-level `run.json` records stage completion and final acceptance. Each stage can be invoked separately against these artifacts.
