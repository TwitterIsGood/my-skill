import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ui_pipeline.diff import compare_images
from ui_pipeline.reproduce import apply_files, prepare_model_image, reproduce_ui


class FakeClient:
    def chat(self, prompt, **kwargs):
        return '{"files":{"index.html":"<style>html,body{margin:0;width:100%;height:100%;background:#123456}</style>"},"notes":"fixture"}'


class DiffReproduceTests(unittest.TestCase):
    def test_identical_images_score_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = Image.new("RGB", (30, 20), "#336699")
            a, b = root / "a.png", root / "b.png"
            image.save(a); image.save(b)
            metrics = compare_images(a, b, root / "diff")
            self.assertAlmostEqual(metrics["score"], 1.0, places=6)
            self.assertEqual(metrics["mismatch_ratio"], 0.0)

    def test_different_images_lower_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (30, 20), "black").save(root / "a.png")
            Image.new("RGB", (30, 20), "white").save(root / "b.png")
            metrics = compare_images(root / "a.png", root / "b.png", root / "diff")
            self.assertLess(metrics["score"], 0.5)

    def test_apply_files_blocks_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                apply_files(tmp, {"../outside.html": "bad"})

    def test_apply_files_writes_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            apply_files(tmp, {"index.html": "<h1>ok</h1>", "styles.css": "body{}"})
            self.assertTrue((Path(tmp) / "index.html").is_file())

    def test_reproduce_offline_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.png"
            Image.new("RGB", (80, 60), "#123456").save(target)
            result = reproduce_ui(FakeClient(), target, root / "run", threshold=0.99, max_iterations=0)
            self.assertTrue(result["accepted"])
            self.assertTrue((root / "run" / "iterations" / "00" / "heatmap.png").is_file())

    def test_prepare_model_image_downscales(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "large.png"
            Image.new("RGB", (1600, 800), "white").save(source)
            output = prepare_model_image(source, root / "model.jpg", max_dimension=1000)
            with Image.open(output) as image:
                self.assertEqual(image.size, (1000, 500))


if __name__ == "__main__":
    unittest.main()
