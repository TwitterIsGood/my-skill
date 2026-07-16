import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ui_pipeline.config import Settings, discover_env_file, load_dotenv


class ConfigTests(unittest.TestCase):
    def test_discovers_callers_local_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env.local").write_text("UI_REPLICA_BASE_URL=https://relay.example/v1\nUI_REPLICA_API_KEY=local-only\n")
            with patch("pathlib.Path.cwd", return_value=root):
                self.assertEqual(discover_env_file(), (root / ".env.local").resolve())

    def test_loads_explicit_env_file_without_overriding_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.env"
            path.write_text("UI_REPLICA_BASE_URL=https://file.example/v1\nUI_REPLICA_API_KEY=file-key\n")
            with patch.dict(os.environ, {"UI_REPLICA_API_KEY": "exported-key"}, clear=True):
                load_dotenv(path)
                self.assertEqual(os.environ["UI_REPLICA_API_KEY"], "exported-key")
                self.assertEqual(os.environ["UI_REPLICA_BASE_URL"], "https://file.example/v1")

    def test_requires_local_base_url_and_key(self):
        with patch.dict(os.environ, {}, clear=True), patch("ui_pipeline.config.discover_env_file", return_value=None):
            with self.assertRaisesRegex(ValueError, "UI_REPLICA_API_KEY"):
                Settings.from_env()


if __name__ == "__main__":
    unittest.main()
