import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plugin_discovery import (
    discover_plugins,
    open_plugin_asset,
    resolve_plugin_asset,
    validate_plugin_directory,
)


class PluginDiscoveryTests(unittest.TestCase):
    def _write_plugin(self, root, plugin_id, **overrides):
        plugin = root / plugin_id
        plugin.mkdir(parents=True)
        manifest = {
            "id": plugin_id,
            "name": plugin_id.replace("-", " ").title(),
            "version": "1.0.0",
            "apiVersion": 1,
            "main": "index.js",
            "styles": ["style.css"],
        }
        manifest.update(overrides)
        (plugin / "index.js").write_text("export function activate() {}", encoding="utf-8")
        (plugin / "style.css").write_text(".plugin {}", encoding="utf-8")
        (plugin / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
        return plugin

    def test_validates_a_plugin_directory_for_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = self._write_plugin(Path(tmp), "example-text", description="Example")

            validated = validate_plugin_directory(plugin, "external")

            self.assertEqual(validated["id"], "example-text")
            self.assertEqual(validated["source"], "external")
            self.assertEqual(validated["description"], "Example")
            self.assertEqual(validated["moduleUrl"], "/plugins/example-text/index.js")
            self.assertEqual(validated["styleUrls"], ["/plugins/example-text/style.css"])
            self.assertFalse(any(key in validated for key in ("path", "pluginDir", "plugin_dir")))

    def test_percent_encodes_reserved_space_and_non_ascii_characters_in_module_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            main = "nested dir/entry#query?percent%2f雪.js"
            plugin = self._write_plugin(root, "encoded-main", main=main)
            (plugin / "nested dir").mkdir()
            (plugin / main).write_text("export function activate() {}", encoding="utf-8")

            validated = validate_plugin_directory(plugin, "builtin")

            self.assertEqual(validated["main"], main)
            self.assertEqual(
                validated["moduleUrl"],
                "/plugins/encoded-main/nested%20dir/entry%23query%3Fpercent%252f%E9%9B%AA.js",
            )

    def test_percent_encodes_reserved_space_and_non_ascii_characters_in_style_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            style = "styles dir/theme#query?percent%2f雪.css"
            plugin = self._write_plugin(root, "encoded-style", styles=[style])
            (plugin / "styles dir").mkdir()
            (plugin / style).write_text(".encoded {}", encoding="utf-8")

            validated = validate_plugin_directory(plugin, "external")

            self.assertEqual(validated["styles"], [style])
            self.assertEqual(
                validated["styleUrls"],
                ["/plugins/encoded-style/styles%20dir/theme%23query%3Fpercent%252f%E9%9B%AA.css"],
            )

    def test_discovers_builtin_plugins_with_backward_compatible_one_argument_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_plugin(root, "example-text")

            result = discover_plugins(root)

            self.assertEqual([item["id"] for item in result["plugins"]], ["example-text"])
            self.assertEqual(result["plugins"][0]["source"], "builtin")
            self.assertEqual(result["errors"], [])

    def test_discovers_external_plugins_when_builtin_root_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            external = root / "external"
            external.mkdir()
            self._write_plugin(external, "external-only")

            result = discover_plugins(builtin, external)

            self.assertEqual([item["id"] for item in result["plugins"]], ["external-only"])
            self.assertEqual(result["plugins"][0]["source"], "external")
            self.assertEqual(result["errors"], [])

    def test_scans_builtin_then_external_with_each_source_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            external = root / "external"
            builtin.mkdir()
            external.mkdir()
            for plugin_id in ("zulu", "alpha"):
                self._write_plugin(builtin, plugin_id)
            for plugin_id in ("yankee", "bravo"):
                self._write_plugin(external, plugin_id)

            result = discover_plugins(builtin, external)

            self.assertEqual(
                [(item["id"], item["source"]) for item in result["plugins"]],
                [
                    ("alpha", "builtin"),
                    ("zulu", "builtin"),
                    ("bravo", "external"),
                    ("yankee", "external"),
                ],
            )

    def test_valid_builtin_wins_duplicate_external_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            external = root / "external"
            builtin.mkdir()
            external.mkdir()
            self._write_plugin(builtin, "shared", name="Built In")
            self._write_plugin(external, "shared", name="External")

            result = discover_plugins(builtin, external)

            self.assertEqual([(item["id"], item["name"]) for item in result["plugins"]], [("shared", "Built In")])
            self.assertEqual(result["errors"], [{
                "plugin": "shared",
                "source": "external",
                "error": "duplicate plugin id conflicts with builtin",
            }])

    def test_invalid_builtin_does_not_reserve_id_from_valid_external(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            external = root / "external"
            builtin.mkdir()
            external.mkdir()
            self._write_plugin(builtin, "shared", apiVersion=True)
            self._write_plugin(external, "shared", name="External")

            result = discover_plugins(builtin, external)

            self.assertEqual([(item["id"], item["source"]) for item in result["plugins"]], [("shared", "external")])
            self.assertEqual([(error["plugin"], error["source"]) for error in result["errors"]], [("shared", "builtin")])

    def test_isolates_malformed_and_missing_required_manifests_without_host_path_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            malformed = root / "malformed"
            malformed.mkdir()
            (malformed / "plugin.json").write_text("{broken", encoding="utf-8")
            missing = root / "missing"
            missing.mkdir()
            (missing / "plugin.json").write_text(json.dumps({"id": "missing"}), encoding="utf-8")
            self._write_plugin(root, "valid")

            result = discover_plugins(root)

            self.assertEqual([item["id"] for item in result["plugins"]], ["valid"])
            self.assertEqual(
                [(error["plugin"], error["source"]) for error in result["errors"]],
                [("malformed", "builtin"), ("missing", "builtin")],
            )
            self.assertTrue(all(str(root) not in error["error"] for error in result["errors"]))

    def test_rejects_boolean_non_integer_and_unsupported_api_versions(self):
        for api_version in (True, False, "1", 2, 0, 1.0):
            with self.subTest(api_version=api_version), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._write_plugin(root, "bad-api", apiVersion=api_version)

                result = discover_plugins(root)

                self.assertEqual(result["plugins"], [])
                self.assertEqual(result["errors"][0]["plugin"], "bad-api")
                self.assertEqual(result["errors"][0]["source"], "builtin")

    def test_rejects_ids_outside_the_public_plugin_id_grammar(self):
        bad_ids = ("Bad", "-bad", "bad-", "bad_name", "a" * 65)
        for plugin_id in bad_ids:
            with self.subTest(plugin_id=plugin_id), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._write_plugin(root, plugin_id)

                result = discover_plugins(root)

                self.assertEqual(result["plugins"], [])
                self.assertEqual(result["errors"][0]["plugin"], plugin_id)

    def test_rejects_manifest_id_that_does_not_equal_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_plugin(root, "directory-id", id="manifest-id")

            result = discover_plugins(root)

            self.assertEqual(result["plugins"], [])
            self.assertEqual(result["errors"][0]["plugin"], "directory-id")

    def test_rejects_unsafe_main_paths(self):
        unsafe_paths = (
            "", "{outside}", ".", "..", "../outside.js", ".hidden.js",
            "nested/.hidden.js", "windows\\index.js", "bad\x00name.js", "bad\nname.js",
            "nested/", "nested//index.js",
        )
        for unsafe_path in unsafe_paths:
            with self.subTest(path=repr(unsafe_path)), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                outside = root / "outside.js"
                outside.write_text("outside", encoding="utf-8")
                if unsafe_path == "{outside}":
                    unsafe_path = str(outside)
                self._write_plugin(root, "unsafe-main", main=unsafe_path)
                plugin = root / "unsafe-main"
                (plugin / ".hidden.js").write_text("hidden", encoding="utf-8")
                (plugin / "windows\\index.js").write_text("windows", encoding="utf-8")
                (plugin / "bad\nname.js").write_text("control", encoding="utf-8")
                nested = plugin / "nested"
                nested.mkdir()
                (nested / ".hidden.js").write_text("hidden", encoding="utf-8")
                (nested / "index.js").write_text("nested", encoding="utf-8")

                result = discover_plugins(root)

                self.assertEqual(result["plugins"], [])
                self.assertEqual(result["errors"][0]["plugin"], "unsafe-main")

    def test_rejects_unsafe_style_paths_and_non_list_styles(self):
        unsafe_styles = (
            ["../style.css"], [".hidden.css"], ["nested\\style.css"], [""],
            ["bad\x00name.css"], "x", [1],
        )
        for styles in unsafe_styles:
            with self.subTest(styles=repr(styles)), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._write_plugin(root, "unsafe-style", styles=styles)
                plugin = root / "unsafe-style"
                (root / "style.css").write_text("outside", encoding="utf-8")
                (plugin / ".hidden.css").write_text("hidden", encoding="utf-8")
                (plugin / "nested\\style.css").write_text("windows", encoding="utf-8")
                (plugin / "x").write_text("string", encoding="utf-8")
                (plugin / "1").write_text("number", encoding="utf-8")

                result = discover_plugins(root)

                self.assertEqual(result["plugins"], [])
                self.assertEqual(result["errors"][0]["plugin"], "unsafe-style")

    def test_rejects_symlink_file_and_symlink_parent_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            builtin.mkdir()
            outside_file = root / "outside.js"
            outside_file.write_text("outside", encoding="utf-8")
            symlink_file = self._write_plugin(builtin, "symlink-file", main="linked.js")
            (symlink_file / "linked.js").symlink_to(outside_file)

            outside_dir = root / "outside-dir"
            outside_dir.mkdir()
            (outside_dir / "index.js").write_text("outside", encoding="utf-8")
            symlink_parent = self._write_plugin(builtin, "symlink-parent", main="assets/index.js")
            (symlink_parent / "assets").symlink_to(outside_dir, target_is_directory=True)

            result = discover_plugins(builtin)

            self.assertEqual(result["plugins"], [])
            self.assertEqual([error["plugin"] for error in result["errors"]], ["symlink-file", "symlink-parent"])
            self.assertTrue(all(str(root) not in error["error"] for error in result["errors"]))

    def test_rejects_non_file_entry_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = self._write_plugin(root, "directory-main", main="assets")
            (plugin / "assets").mkdir()

            result = discover_plugins(root)

            self.assertEqual(result["plugins"], [])
            self.assertEqual(result["errors"][0]["plugin"], "directory-main")

    def test_missing_external_root_is_empty_without_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            builtin.mkdir()
            self._write_plugin(builtin, "built-in")

            result = discover_plugins(builtin, root / "does-not-exist")

            self.assertEqual([item["id"] for item in result["plugins"]], ["built-in"])
            self.assertEqual(result["errors"], [])

    def test_resolves_entry_style_nested_and_percent_encoded_name_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            external = root / "external"
            builtin.mkdir()
            external.mkdir()
            plugin = self._write_plugin(builtin, "asset-plugin")
            nested = plugin / "nested dir"
            nested.mkdir()
            special_name = "asset#query?percent%2f雪.js"
            special_asset = nested / special_name
            special_asset.write_text("special", encoding="utf-8")

            expected = {
                "index.js": plugin / "index.js",
                "style.css": plugin / "style.css",
                f"nested dir/{special_name}": special_asset,
            }
            for asset_path, expected_path in expected.items():
                with self.subTest(asset_path=asset_path):
                    self.assertEqual(
                        resolve_plugin_asset(builtin, external, "asset-plugin", asset_path),
                        expected_path,
                    )

    def test_resolver_uses_the_same_valid_builtin_first_selection_as_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            external = root / "external"
            builtin.mkdir()
            external.mkdir()
            builtin_plugin = self._write_plugin(builtin, "shared")
            external_plugin = self._write_plugin(external, "shared")
            (builtin_plugin / "winner.txt").write_text("builtin", encoding="utf-8")
            (external_plugin / "winner.txt").write_text("external", encoding="utf-8")

            self.assertEqual(
                resolve_plugin_asset(builtin, external, "shared", "winner.txt"),
                builtin_plugin / "winner.txt",
            )

            (builtin_plugin / "plugin.json").write_text("{malformed", encoding="utf-8")
            self.assertEqual(
                resolve_plugin_asset(builtin, external, "shared", "winner.txt"),
                external_plugin / "winner.txt",
            )

    def test_resolver_rejects_invalid_ids_and_unsafe_asset_paths(self):
        unsafe_paths = (
            "", "/index.js", "\\index.js", "nested\\index.js", ".", "..",
            "nested/./index.js", "nested/../index.js", ".git/config",
            "nested/.hidden", "bad\x00name", "bad\nname", "nested/", "nested//index.js",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            external = root / "external"
            builtin.mkdir()
            external.mkdir()
            self._write_plugin(builtin, "safe-plugin")

            for plugin_id in ("", "Bad", "-bad", "bad-", "bad_name", "a" * 65):
                with self.subTest(plugin_id=plugin_id):
                    self.assertIsNone(
                        resolve_plugin_asset(builtin, external, plugin_id, "index.js")
                    )
            for asset_path in unsafe_paths:
                with self.subTest(asset_path=repr(asset_path)):
                    self.assertIsNone(
                        resolve_plugin_asset(builtin, external, "safe-plugin", asset_path)
                    )

    def test_resolver_rejects_symlinks_directories_and_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            external = root / "external"
            builtin.mkdir()
            external.mkdir()
            plugin = self._write_plugin(builtin, "safe-plugin")
            directory = plugin / "directory"
            directory.mkdir()
            outside_file = root / "outside.txt"
            outside_file.write_text("outside", encoding="utf-8")
            (plugin / "linked-file").symlink_to(outside_file)
            outside_dir = root / "outside-dir"
            outside_dir.mkdir()
            (outside_dir / "secret.txt").write_text("secret", encoding="utf-8")
            (plugin / "linked-dir").symlink_to(outside_dir, target_is_directory=True)

            for asset_path in (
                "missing.txt", "directory", "linked-file", "linked-dir/secret.txt"
            ):
                with self.subTest(asset_path=asset_path):
                    self.assertIsNone(
                        resolve_plugin_asset(builtin, external, "safe-plugin", asset_path)
                    )

    def test_resolver_requires_a_currently_valid_plugin_and_tolerates_missing_external_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            builtin.mkdir()
            malformed = self._write_plugin(builtin, "malformed")
            (malformed / "plugin.json").write_text("{broken", encoding="utf-8")

            self.assertIsNone(
                resolve_plugin_asset(builtin, root / "missing-external", "malformed", "index.js")
            )
            self.assertIsNone(
                resolve_plugin_asset(builtin, root / "missing-external", "unknown", "index.js")
            )

    def test_opens_a_valid_nested_asset_descriptor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            external = root / "external"
            builtin.mkdir()
            external.mkdir()
            plugin = self._write_plugin(builtin, "safe-plugin")
            nested = plugin / "assets"
            nested.mkdir()
            asset = nested / "message.txt"
            asset.write_bytes(b"descriptor content")

            descriptor = open_plugin_asset(
                builtin, external, "safe-plugin", "assets/message.txt"
            )

            self.assertIsNotNone(descriptor)
            try:
                self.assertEqual(os.read(descriptor, 1024), b"descriptor content")
            finally:
                os.close(descriptor)

    def test_open_rejects_a_final_file_swapped_to_a_symlink_after_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            external = root / "external"
            builtin.mkdir()
            external.mkdir()
            plugin = self._write_plugin(builtin, "safe-plugin")
            asset = plugin / "message.txt"
            asset.write_text("plugin", encoding="utf-8")
            outside = root / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            real_resolve = resolve_plugin_asset

            def resolve_then_swap(*args):
                resolved = real_resolve(*args)
                asset.unlink()
                asset.symlink_to(outside)
                return resolved

            with patch("plugin_discovery.resolve_plugin_asset", side_effect=resolve_then_swap):
                descriptor = open_plugin_asset(
                    builtin, external, "safe-plugin", "message.txt"
                )

            self.assertIsNone(descriptor)

    def test_open_rejects_a_directory_component_swapped_to_a_symlink_after_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            external = root / "external"
            builtin.mkdir()
            external.mkdir()
            plugin = self._write_plugin(builtin, "safe-plugin")
            nested = plugin / "assets"
            nested.mkdir()
            (nested / "message.txt").write_text("plugin", encoding="utf-8")
            outside = root / "outside"
            outside.mkdir()
            (outside / "message.txt").write_text("outside", encoding="utf-8")
            moved = plugin / "moved-assets"
            real_resolve = resolve_plugin_asset

            def resolve_then_swap(*args):
                resolved = real_resolve(*args)
                nested.rename(moved)
                nested.symlink_to(outside, target_is_directory=True)
                return resolved

            with patch("plugin_discovery.resolve_plugin_asset", side_effect=resolve_then_swap):
                descriptor = open_plugin_asset(
                    builtin, external, "safe-plugin", "assets/message.txt"
                )

            self.assertIsNone(descriptor)


if __name__ == "__main__":
    unittest.main()
