from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: str | Path, value: Any) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def slugify(value: str, fallback: str = "item") -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or fallback


def unique_slugs(values: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    result = []
    for value in values:
        base = slugify(value)
        counts[base] = counts.get(base, 0) + 1
        result.append(base if counts[base] == 1 else f"{base}-{counts[base]}")
    return result


def ensure_within(root: str | Path, relative: str | Path) -> Path:
    root_path = Path(root).resolve()
    candidate = (root_path / relative).resolve()
    if candidate != root_path and root_path not in candidate.parents:
        raise ValueError(f"path escapes output root: {relative}")
    return candidate
