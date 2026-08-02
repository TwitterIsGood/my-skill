---
name: maestro-runner
description: Create, run, debug, and maintain Maestro YAML UI/E2E tests with the project-local maestro-runner CLI. Use when Android, iOS, React Native, Flutter, Expo, or mobile-app testing is requested or would materially validate a change; also use for device UI automation, regression flows, smoke tests, selector discovery, screenshots, parallel device runs, Appium/cloud-device execution, and compatible web UI flows.
---

# Maestro Runner

Use the project-local pinned binary. Do not install or invoke a global `maestro-runner` when this skill is available.

```bash
SKILL_DIR=".agents/skills/maestro-runner"
"$SKILL_DIR/scripts/run.sh" --version
```

## Workflow

1. Read the nearest `AGENTS.md` files and identify the app, target platform, build artifact, and existing test conventions.
2. Search for existing Maestro flows before creating new ones:

   ```bash
   rg --files -g '*.yaml' -g '*.yml' | rg '(^|/)(\.maestro|maestro|e2e|flows|tests)(/|$)'
   ```

3. Run the platform-specific environment check:

   ```bash
   "$SKILL_DIR/scripts/doctor.sh" android
   "$SKILL_DIR/scripts/doctor.sh" ios
   "$SKILL_DIR/scripts/doctor.sh" web
   ```

4. Reuse existing flow locations and naming. If none exist, place mobile flows under `.maestro/`.
5. Prefer stable accessibility IDs/test IDs. Use visible text only when it is stable and intentional.
6. Inspect the live hierarchy when selectors are uncertain:

   ```bash
   "$SKILL_DIR/scripts/run.sh" --platform android --device <id> hierarchy --compact
   "$SKILL_DIR/scripts/run.sh" --platform ios --device <udid> hierarchy --compact --find login
   ```

7. Run the narrowest relevant flow first, then the related suite. Preserve reports and failure artifacts.
8. Report the platform, device, app artifact, exact flow paths, command, result, and any untested constraints.

## Platform Rules

- Android: require `adb`; use an attached device/emulator or `--auto-start-emulator`. Pass `--app-file <apk>` when installation is required.
- iOS: require `xcrun` and an available simulator/device. Follow repository instructions for building/signing; this repository requires iOS compilation and packaging through its configured cloud build service. Test the resulting `.app` or `.ipa` artifact locally only when available.
- React Native, Flutter, and Expo: treat them as Android/iOS targets and prefer declared test IDs or semantics.
- Web: require Chrome/Chromium and pass `--platform web`; use browser-oriented selectors only for actual web flows.
- Appium/cloud devices: use `--driver appium --appium-url <url> --caps <file>`. Keep provider credentials in ignored environment files or the existing secret manager, never in flow YAML or committed capability files.

## Commands

```bash
# Android
"$SKILL_DIR/scripts/run.sh" --platform android test .maestro/login.yaml

# Install an APK and test
"$SKILL_DIR/scripts/run.sh" --platform android --app-file build/app.apk test .maestro/

# iOS simulator/device
"$SKILL_DIR/scripts/run.sh" --platform ios --device <udid> test .maestro/login.yaml

# Web
"$SKILL_DIR/scripts/run.sh" --platform web test .maestro/web-login.yaml

# Parallel devices and deterministic report location
"$SKILL_DIR/scripts/run.sh" --platform android test --parallel 2 --output reports/maestro --flatten .maestro/
```

Read [references/cli-and-flows.md](references/cli-and-flows.md) when authoring flows, selecting flags, debugging selectors, configuring reports, or using visual regression/Appium.

## Safety

- Do not claim mobile validation when no compatible device/simulator and app artifact were exercised.
- Do not start, reset, uninstall from, or mutate an explicitly selected physical device without confirming the target.
- Do not commit credentials, signing material, `.env` files, cloud capability secrets, or generated reports unless the repository already tracks them intentionally.
- Treat screenshot baseline updates as an intentional reviewable change; use `--update-screenshots` only when the expected UI changed.
- Keep `MAESTRO_RUNNER_HOME` project-local by invoking `scripts/run.sh`.
