import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from ui_pipeline.sprites import build_sprite_atlas, remove_border_background
from ui_pipeline.visual import import_visual


class VisualSpriteTests(unittest.TestCase):
    def fixture(self, root: Path) -> Path:
        image = Image.new("RGB", (200, 120), "#ffffff")
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, 50, 50), fill="#ff3366")
        draw.ellipse((100, 40, 135, 75), fill="#2255dd")
        path = root / "fixture.png"
        image.save(path)
        return path

    def test_import_visual_writes_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = import_visual(self.fixture(root), root / "visual")
            self.assertEqual(manifest["image"]["width"], 200)
            self.assertTrue((root / "visual" / "run.json").is_file())

    def test_remove_border_background(self):
        image = Image.new("RGB", (20, 20), "white")
        ImageDraw.Draw(image).rectangle((5, 5, 14, 14), fill="black")
        result = remove_border_background(image, 10)
        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertEqual(result.getpixel((10, 10))[3], 255)

    def test_atlas_coordinates_and_css(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.fixture(root)
            icons = [
                {"name": "heart", "bbox": {"x": 18, "y": 18, "width": 35, "height": 35}},
                {"name": "circle", "bbox": {"x": 98, "y": 38, "width": 40, "height": 40}},
            ]
            manifest = build_sprite_atlas(source, icons, root / "sprites", cell_size=64, columns=2)
            self.assertEqual(manifest["icons"][1]["atlas"]["x"], 64)
            css = (root / "sprites" / "spritesheet.css").read_text()
            self.assertIn(".sprite-heart", css)
            validation = json.loads((root / "sprites" / "validation.json").read_text())
            self.assertTrue(validation["ok"])
            self.assertAlmostEqual(validation["sprite_vs_visual"]["mean_score"], 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
