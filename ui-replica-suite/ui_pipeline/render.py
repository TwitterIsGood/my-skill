from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def find_chrome(explicit: str | None = None) -> str:
    if explicit and Path(explicit).is_file():
        return explicit
    env = os.getenv("UI_REPLICA_CHROME")
    if env and Path(env).is_file():
        return env
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    for name in ("google-chrome", "chromium", "chromium-browser"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    raise FileNotFoundError("headless Chrome was not found; set UI_REPLICA_CHROME")


def render_html(
    html: str | Path,
    output: str | Path,
    *,
    width: int,
    height: int,
    chrome: str | None = None,
    timeout: int = 60,
) -> Path:
    html_path = Path(html).expanduser().resolve()
    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        find_chrome(chrome),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--force-device-scale-factor=1",
        f"--window-size={width},{height}",
        f"--screenshot={output_path}",
        html_path.as_uri(),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0 or not output_path.is_file():
        raise RuntimeError(f"Chrome screenshot failed ({result.returncode}): {result.stderr[-2000:]}")
    return output_path
