import json
import tempfile
import unittest
from pathlib import Path

from plugin_discovery import discover_plugins


class PluginDiscoveryTests(unittest.TestCase):
    def test_discovers_valid_manifests_without_a_hardcoded_plugin_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "example-text"
            plugin.mkdir()
            (plugin / "index.js").write_text("export function activate() {}", encoding="utf-8")
            (plugin / "style.css").write_text(".example {}", encoding="utf-8")
            (plugin / "plugin.json").write_text(json.dumps({
                "id": "example-text",
                "name": "Example Text",
                "version": "0.1.0",
                "apiVersion": 1,
                "main": "index.js",
                "styles": ["style.css"],
            }), encoding="utf-8")

            result = discover_plugins(root)

            self.assertEqual([item["id"] for item in result["plugins"]], ["example-text"])
            self.assertEqual(result["plugins"][0]["moduleUrl"], "/plugins/example-text/index.js")
            self.assertEqual(result["plugins"][0]["styleUrls"], ["/plugins/example-text/style.css"])
            self.assertEqual(result["errors"], [])

    def test_isolates_invalid_manifest_and_keeps_other_plugins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            broken = root / "broken"
            broken.mkdir()
            (broken / "plugin.json").write_text("{broken", encoding="utf-8")
            valid = root / "valid"
            valid.mkdir()
            (valid / "index.js").write_text("", encoding="utf-8")
            (valid / "plugin.json").write_text(json.dumps({
                "id": "valid", "name": "Valid", "version": "1", "apiVersion": 1, "main": "index.js"
            }), encoding="utf-8")

            result = discover_plugins(root)

            self.assertEqual([item["id"] for item in result["plugins"]], ["valid"])
            self.assertEqual(result["errors"][0]["plugin"], "broken")

    def test_rejects_manifest_paths_that_escape_the_plugin_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "unsafe"
            plugin.mkdir()
            (plugin / "plugin.json").write_text(json.dumps({
                "id": "unsafe", "name": "Unsafe", "version": "1", "apiVersion": 1, "main": "../outside.js"
            }), encoding="utf-8")

            result = discover_plugins(root)

            self.assertEqual(result["plugins"], [])
            self.assertEqual(result["errors"][0]["plugin"], "unsafe")


if __name__ == "__main__":
    unittest.main()
