from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from .utils import write_json


def _rgb(path: str | Path, size: tuple[int, int] | None = None) -> np.ndarray:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
        if size and image.size != size:
            image = image.resize(size, Image.Resampling.LANCZOS)
        return np.asarray(image, dtype=np.float32)


def global_ssim(a: np.ndarray, b: np.ndarray) -> float:
    x = cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float64)
    y = cv2.cvtColor(b.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float64)
    c1, c2 = 6.5025, 58.5225
    mux, muy = x.mean(), y.mean()
    varx, vary = x.var(), y.var()
    covariance = ((x - mux) * (y - muy)).mean()
    denominator = (mux * mux + muy * muy + c1) * (varx + vary + c2)
    return float(((2 * mux * muy + c1) * (2 * covariance + c2)) / denominator) if denominator else 1.0


def compare_images(
    target: str | Path,
    actual: str | Path,
    output_dir: str | Path,
    *,
    mismatch_tolerance: int = 16,
) -> dict[str, Any]:
    target_path = Path(target).expanduser().resolve()
    with Image.open(target_path) as opened:
        size = opened.size
    a = _rgb(target_path)
    b = _rgb(actual, size=size)
    delta = np.abs(a - b)
    per_pixel = delta.mean(axis=2)
    mae = float(delta.mean() / 255.0)
    rmse = float(np.sqrt(np.mean(np.square(delta))) / 255.0)
    mismatch_ratio = float(np.mean(per_pixel > mismatch_tolerance))
    similarity = max(0.0, 1.0 - mae)
    ssim = max(-1.0, min(1.0, global_ssim(a, b)))
    score = max(0.0, min(1.0, 0.55 * ssim + 0.45 * similarity))
    heat = np.clip(per_pixel * 4, 0, 255).astype(np.uint8)
    colored = cv2.applyColorMap(heat, cv2.COLORMAP_TURBO)
    colored = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)
    overlay = (0.65 * a + 0.35 * colored).clip(0, 255).astype(np.uint8)
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    heatmap_path = root / "heatmap.png"
    Image.fromarray(overlay).save(heatmap_path)
    metrics = {
        "target": str(target_path),
        "actual": str(Path(actual).expanduser().resolve()),
        "compared_width": size[0],
        "compared_height": size[1],
        "mae": mae,
        "rmse": rmse,
        "mismatch_ratio": mismatch_ratio,
        "pixel_similarity": similarity,
        "ssim": ssim,
        "score": score,
        "heatmap": str(heatmap_path),
    }
    write_json(root / "metrics.json", metrics)
    return metrics
