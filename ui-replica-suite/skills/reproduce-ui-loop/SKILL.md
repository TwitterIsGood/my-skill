---
name: reproduce-ui-loop
description: Reproduce a reference UI in static frontend code with the configured high-reasoning UI model, render it in headless Chrome, compare screenshots against the target, generate heatmaps and similarity metrics, and iteratively repair the code while using an existing sprite atlas. Use for screenshot-to-code, UI restoration, pixel-level visual convergence, sprite-integrated frontend generation, or repeated visual difference repair.
---

# Reproduce UI Loop

Generate a deterministic interactive page, render its closed initial state at the target's exact pixel dimensions, and repair the largest differences first.

## Workflow

1. Require an absolute visual target. Prefer a validated `spritesheet.json` when the target contains reusable icons.
2. Run from the configured local project. The wrapper reads the caller's environment or env file instead of bundling a key:

```bash
SKILL_DIR=/absolute/path/to/ui-replica-suite/skills/reproduce-ui-loop
"$SKILL_DIR/scripts/run.sh" \
  --visual /absolute/path/to/visual-target.png \
  --sprite-manifest /absolute/path/to/sprites/spritesheet.json \
  --output-dir /absolute/path/to/run/reproduction \
  --threshold 0.985 \
  --max-iterations 5
```

3. The model must return ordinary HTML/CSS/JS files. Require natural scrolling and meaningful behavior for visible buttons, tabs, navigation, expandable lists, forms, dialogs, and primary actions. Keep transient UI closed in the initial screenshot. Do not accept external network dependencies, whole-page SVG tracing, embedded screenshot data, or canvas screenshot copying.
4. Inspect each `iterations/<n>/screenshot.png`, `heatmap.png`, and `metrics.json`. The combined score is a gate, not a substitute for visual inspection.
5. Continue until the threshold passes or the iteration cap is reached. If capped, report the remaining largest visual differences and preserve all artifacts for a resumed run.
6. Verify that visible supplied icons use `sprite-icon sprite-<name>` rather than substitutes.

Read [references/acceptance.md](references/acceptance.md) for the output and acceptance contract.
