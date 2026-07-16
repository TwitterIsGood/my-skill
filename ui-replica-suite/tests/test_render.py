import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ui_pipeline.render import find_chrome, render_html


class RenderTests(unittest.TestCase):
    def test_headless_chrome_renders_static_html(self):
        chrome = find_chrome()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text("<style>html,body{margin:0;background:#123456}</style>", encoding="utf-8")
            output = render_html(root / "index.html", root / "shot.png", width=80, height=60, chrome=chrome)
            with Image.open(output) as image:
                self.assertEqual(image.size, (80, 60))


if __name__ == "__main__":
    unittest.main()
