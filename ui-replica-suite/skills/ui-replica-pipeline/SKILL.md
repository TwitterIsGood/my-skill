---
name: ui-replica-pipeline
description: "Orchestrate the complete UI production pipeline: generate or import a visual target, create a mapped UI icon spritesheet, ask the configured high-reasoning UI model to reproduce the UI with that atlas, render and compare screenshots, and iterate toward the configured similarity threshold. Use when the user wants the full visual-to-sprites-to-code-to-validation loop rather than an individual stage."
---

# UI Replica Pipeline

Run the three project-local abilities in order and keep every stage resumable through saved artifacts.

## Full Run

From a text brief:

```bash
SKILL_DIR=/absolute/path/to/ui-replica-suite/skills/ui-replica-pipeline
"$SKILL_DIR/scripts/run.sh" \
  --prompt '<complete UI brief>' \
  --output-dir /absolute/path/to/runs/<name> \
  --sprite-mode crop \
  --threshold 0.985 \
  --max-iterations 5
```

From an existing target:

```bash
"$SKILL_DIR/scripts/run.sh" \
  --visual /absolute/path/to/reference.png \
  --output-dir /absolute/path/to/runs/<name>
```

## Control Rules

- Prefer `crop` for first-pass icon fidelity; regenerate only failed icons.
- Read relay configuration only from the caller's exported environment, `.env.local`, `.env`, `.ui-replica.env`, or `UI_REPLICA_ENV_FILE`. Never write a key into this skill bundle.
- Read the top-level `run.json` after every stage.
- On failure, rerun the smallest stage with its individual skill rather than restarting image generation.
- Do not declare completion unless the sprite validation passes, the final screenshot exists, and the reproduction acceptance gate passes.
- Preserve failed runs for diagnosis.

Read [references/pipeline-layout.md](references/pipeline-layout.md) for artifact locations.
