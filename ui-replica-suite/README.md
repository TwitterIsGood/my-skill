# UI Replica Suite

Four project-local Agent Skills implement a complete visual UI workflow:

1. `generate-ui-visual` generates or imports the visual target.
2. `build-ui-sprite-atlas` inventories visual assets and emits a mapped PNG/WebP/CSS atlas.
3. `reproduce-ui-loop` generates an interactive local web UI, renders it in Chrome, and repairs screenshot differences.
4. `ui-replica-pipeline` orchestrates all three stages.

## Local configuration

Secrets are never stored in this repository. Exported variables take precedence. The wrapper scripts preserve the caller's working directory and otherwise discover one local configuration file in this order:

1. `UI_REPLICA_ENV_FILE=/absolute/path/to/file`
2. `<current-project>/.env.local`
3. `<current-project>/.env`
4. `<current-project>/.ui-replica.env`
Copy `.env.example` into the project where you run the suite, fill in the relay URL and key, and keep that file ignored by the project.

## Install the skills

Keep the suite directory intact because all four skills share the same runtime. Link the skill folders into either the global Codex skill directory or a project's `.agents/skills` directory:

```bash
SUITE=/absolute/path/to/ui-replica-suite
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
for skill in generate-ui-visual build-ui-sprite-atlas reproduce-ui-loop ui-replica-pipeline; do
  ln -s "$SUITE/skills/$skill" "${CODEX_HOME:-$HOME/.codex}/skills/$skill"
done
```

The launchers resolve the physical suite location even when invoked through these symlinks.

## Run

From the configured local project:

```bash
/absolute/path/to/ui-replica-suite/skills/ui-replica-pipeline/scripts/run.sh \
  --prompt "Build a warm, cute cat bookkeeping mobile UI" \
  --output-dir "$PWD/runs/cat-ledger" \
  --image-size 1024x1536 \
  --sprite-mode crop \
  --threshold 0.97 \
  --max-iterations 3
```

The generated site uses ordinary HTML/CSS/JS, mapped sprite assets, natural mobile scrolling, and meaningful behavior for visible controls. Chrome is required for screenshot verification.

## Validate

```bash
python3 -m unittest discover -s ui-replica-suite/tests -v
```
