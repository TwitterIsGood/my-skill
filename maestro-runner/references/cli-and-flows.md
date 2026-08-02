# CLI And Flow Reference

This project pins maestro-runner `1.1.22`. Use the wrapper in `../scripts/run.sh` so the binary and driver home remain project-local.

## Flow Skeleton

```yaml
appId: com.example.app
name: Login smoke test
tags:
  - smoke
---
- launchApp:
    clearState: true
- tapOn:
    id: email-input
- inputText: user@example.com
- tapOn:
    id: password-input
- inputText: ${PASSWORD}
- tapOn:
    id: login-button
- assertVisible:
    text: Welcome
```

Pass secrets without placing them in YAML:

```bash
.agents/skills/maestro-runner/scripts/run.sh \
  --platform android test -e PASSWORD="$TEST_PASSWORD" .maestro/login.yaml
```

Prefer an existing ignored env file when the suite already uses one:

```bash
.agents/skills/maestro-runner/scripts/run.sh \
  --platform android test --env-file .env.maestro .maestro/
```

## Selection And Debugging

- Prefer `id:` backed by accessibility identifiers, Android resource IDs, React Native `testID`, or Flutter semantics.
- Use `text:` for stable user-facing labels; it supports regex semantics, so escape metacharacters when a literal match is required.
- Use relative selectors such as `below`, `above`, `leftOf`, `rightOf`, and `childOf` only when a stable ID is unavailable.
- Dump the hierarchy before guessing selectors:

  ```bash
  .agents/skills/maestro-runner/scripts/run.sh \
    --platform android --device emulator-5554 hierarchy --compact --find login
  ```

## Useful Execution Options

```bash
# Tags
... test --include-tags smoke .maestro/
... test --exclude-tags destructive .maestro/

# Multiple devices
... --device emulator-5554,emulator-5556 test --parallel 2 .maestro/

# Start an available emulator/simulator automatically
... --platform android --auto-start-emulator test .maestro/
... --platform ios --auto-start-emulator test .maestro/

# Failure artifacts and stable report directory
... test --artifacts always --output reports/maestro --flatten .maestro/

# Continuous single-flow development
... --platform android test --continuous .maestro/login.yaml
```

Reports support HTML, JUnit XML, and Allure-compatible output. Default reports are written under `reports/<timestamp>/`.

## Visual Regression

```yaml
- assertScreenshot:
    path: screenshots/login
    thresholdPercentage: 95
    cropOn:
      id: login-form
```

The first run seeds a missing baseline. Update an existing baseline only after confirming the UI change:

```bash
... test --update-screenshots .maestro/visual.yaml
```

Pin the device model, OS, resolution, locale, and font settings for meaningful comparisons.

## Platform Notes

- Android requires `adb` and Android SDK Platform-Tools. The default driver is UIAutomator2; `--driver devicelab` is an optional alternative.
- iOS requires Xcode command-line tools. Use `--team-id` for signed real-device WDA execution when required.
- Web requires Chrome/Chromium and `--platform web`; add `--headed` when visual browser inspection is needed.
- Appium requires a reachable Appium 2.x/3.x endpoint and a capabilities JSON file:

  ```bash
  ... --driver appium --appium-url "$APPIUM_URL" --caps caps.json test .maestro/
  ```

Keep cloud-provider usernames, access keys, and signing values outside committed files.
