---
name: generate-ui-visual
description: Generate or register a production UI visual target and a reproducible metadata manifest. Use when Codex needs to create a UI mockup with the configured gpt-image-2 relay, import an existing screenshot or design as the pipeline target, or prepare the first stage of UI reconstruction.
---

# Generate UI Visual

Create a single straight-on UI target and store it with deterministic metadata.

## Workflow

1. Confirm the requested page, viewport orientation, visual style, and essential content from the user request. Infer ordinary details rather than blocking.
2. Run from the configured local project. The wrapper reads that project's environment or `.env` file; never store credentials in this skill directory:

```bash
SKILL_DIR=/absolute/path/to/ui-replica-suite/skills/generate-ui-visual
"$SKILL_DIR/scripts/run.sh" \
  --prompt '<UI description>' \
  --output-dir '<absolute run dir>/visual' \
  --size 1536x1024
```

3. For a supplied visual, do not regenerate it:

```bash
"$SKILL_DIR/scripts/run.sh" \
  --input /absolute/path/to/reference.png \
  --output-dir '<absolute run dir>/visual'
```

4. Inspect `visual-target.png` and `run.json`. Reject presentation boards, device mockups, perspective, clipped viewports, illegible hierarchy, and multiple variants in one image.
5. Pass the absolute `image.path` from `run.json` to the sprite stage.

Read [references/output-contract.md](references/output-contract.md) when another tool needs to consume the result.
