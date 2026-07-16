import unittest

from ui_pipeline.api import extract_json


class ExtractJsonTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(extract_json('{"ok": true}'), {"ok": True})

    def test_fenced_json(self):
        self.assertEqual(extract_json('```json\n{"files":{"a":"b"}}\n```')["files"], {"a": "b"})

    def test_embedded_json(self):
        self.assertEqual(extract_json('Result:\n{"icons":[{"name":"x"}]}\nDone')["icons"][0]["name"], "x")


if __name__ == "__main__":
    unittest.main()
