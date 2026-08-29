import asyncio
import importlib
import json
import os
import tempfile
import unittest
import urllib.parse
import warnings
from pathlib import Path
from unittest.mock import patch

import httpx
import plugin_discovery


class PluginCanvasIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("static/js/smart-canvas.js").read_text(encoding="utf-8")

    def test_unknown_plugin_nodes_skip_builtin_media_normalization(self):
        self.assertIn("if(pluginHost?.isPluginNode(node)) return;", self.source)
        self.assertIn("!pluginHost?.isPluginNode(n) && n.jimengPending", self.source)
        self.assertIn("!pluginHost?.isPluginNode(node) && smartPendingTasks(node).length", self.source)

    def test_dragged_plugin_connections_keep_named_ports(self):
        self.assertIn("fromPortId", self.source)
        self.assertIn("toPortId", self.source)
        self.assertIn("data-port-id", self.source)


class PluginAssetHttpIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime_tmp = tempfile.TemporaryDirectory()
        external_plugins = str(Path(cls.runtime_tmp.name) / "configured-plugins")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with patch.dict(os.environ, {"CANVAS_EXTERNAL_PLUGINS_DIR": external_plugins}):
                cls.main = importlib.import_module("main")
        cls.loop = asyncio.new_event_loop()

    @classmethod
    def tearDownClass(cls):
        cls.loop.close()
        cls.runtime_tmp.cleanup()

    def _get(self, url, *, headers=None, with_chunks=False):
        async def request():
            parsed = urllib.parse.urlsplit(url)
            request_headers = [(b"host", b"testserver")]
            request_headers.extend(
                (
                    str(name).lower().encode("latin-1"),
                    str(value).encode("latin-1"),
                )
                for name, value in (headers or {}).items()
            )
            scope = {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.4"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": urllib.parse.unquote(parsed.path),
                "raw_path": parsed.path.encode("ascii"),
                "query_string": parsed.query.encode("ascii"),
                "root_path": "",
                "headers": request_headers,
                "client": ("127.0.0.1", 12345),
                "server": ("testserver", 80),
            }
            messages = []
            request_sent = False

            async def receive():
                nonlocal request_sent
                if not request_sent:
                    request_sent = True
                    return {"type": "http.request", "body": b"", "more_body": False}
                await asyncio.Event().wait()

            async def send(message):
                messages.append(message)

            app_task = self.loop.create_task(self.main.app(scope, receive, send))
            while not app_task.done():
                await asyncio.sleep(0.01)
            await app_task
            start = next(message for message in messages if message["type"] == "http.response.start")
            body = b"".join(
                message.get("body", b"")
                for message in messages
                if message["type"] == "http.response.body"
            )
            response = httpx.Response(
                start["status"],
                headers=start.get("headers", []),
                content=body,
                request=httpx.Request("GET", f"http://testserver{url}"),
            )
            if with_chunks:
                chunks = [
                    message.get("body", b"")
                    for message in messages
                    if message["type"] == "http.response.body" and message.get("body")
                ]
                return response, chunks
            return response

        return self.loop.run_until_complete(request())

    def _write_plugin(self, root, plugin_id, *, main_path="index.js", styles=None, name=None):
        plugin = root / plugin_id
        plugin.mkdir(parents=True)
        styles = ["style.css"] if styles is None else styles
        manifest = {
            "id": plugin_id,
            "name": name or plugin_id,
            "version": "1.0.0",
            "apiVersion": 1,
            "main": main_path,
            "styles": styles,
        }
        for relative_path, content in [(main_path, "main"), *[(style, "style") for style in styles]]:
            path = plugin / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        (plugin / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
        return plugin

    def _roots(self, root):
        builtin = root / "builtin"
        external = root / "external"
        builtin.mkdir()
        external.mkdir()
        return builtin, external

    def _configured_roots(self, builtin, external):
        return (
            patch.object(self.main, "PLUGINS_DIR", str(builtin)),
            patch.object(self.main, "EXTERNAL_PLUGINS_DIR", str(external)),
        )

    def test_external_plugin_directory_uses_runtime_paths_and_exists(self):
        self.assertEqual(
            self.main.EXTERNAL_PLUGINS_DIR,
            self.main.RUNTIME_PATHS.external_plugins_dir,
        )
        self.assertTrue(Path(self.main.EXTERNAL_PLUGINS_DIR).is_dir())

    def test_api_plugins_discovers_both_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            builtin, external = self._roots(Path(tmp))
            self._write_plugin(builtin, "builtin-one")
            self._write_plugin(external, "external-one")

            builtin_patch, external_patch = self._configured_roots(builtin, external)
            with builtin_patch, external_patch:
                response = self._get("/api/plugins")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                [(plugin["id"], plugin["source"]) for plugin in response.json()["plugins"]],
                [("builtin-one", "builtin"), ("external-one", "external")],
            )

    def test_http_serves_entry_style_nested_and_encoded_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            builtin, external = self._roots(Path(tmp))
            builtin_plugin = self._write_plugin(builtin, "builtin-one")
            (builtin_plugin / "assets").mkdir()
            (builtin_plugin / "assets" / "icon.svg").write_text("icon", encoding="utf-8")
            special_main = "nested dir/entry#query?percent%2f雪.js"
            self._write_plugin(external, "external-one", main_path=special_main)

            builtin_patch, external_patch = self._configured_roots(builtin, external)
            with builtin_patch, external_patch:
                discovery = self._get("/api/plugins").json()
                special_url = next(
                    plugin["moduleUrl"]
                    for plugin in discovery["plugins"]
                    if plugin["id"] == "external-one"
                )
                responses = {
                    "main": self._get("/plugins/builtin-one/index.js"),
                    "style": self._get("/plugins/builtin-one/style.css"),
                    "nested": self._get("/plugins/builtin-one/assets/icon.svg"),
                    "encoded": self._get(special_url),
                }

            self.assertEqual(
                {name: (response.status_code, response.text) for name, response in responses.items()},
                {
                    "main": (200, "main"),
                    "style": (200, "style"),
                    "nested": (200, "icon"),
                    "encoded": (200, "main"),
                },
            )

    def test_http_serves_only_the_authoritative_builtin_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            builtin, external = self._roots(Path(tmp))
            builtin_plugin = self._write_plugin(builtin, "shared", name="Built In")
            external_plugin = self._write_plugin(external, "shared", name="External")
            (builtin_plugin / "winner.txt").write_text("builtin", encoding="utf-8")
            (external_plugin / "winner.txt").write_text("external", encoding="utf-8")

            builtin_patch, external_patch = self._configured_roots(builtin, external)
            with builtin_patch, external_patch:
                response = self._get("/plugins/shared/winner.txt")

            self.assertEqual((response.status_code, response.text), (200, "builtin"))

    def test_http_rejects_unsafe_or_unavailable_assets_with_path_free_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin, external = self._roots(root)
            plugin = self._write_plugin(builtin, "safe-plugin")
            malformed = self._write_plugin(builtin, "malformed")
            (malformed / "plugin.json").write_text("{broken", encoding="utf-8")
            (plugin / "directory").mkdir()
            outside_file = root / "outside.txt"
            outside_file.write_text("outside", encoding="utf-8")
            (plugin / "linked-file").symlink_to(outside_file)
            outside_dir = root / "outside-dir"
            outside_dir.mkdir()
            (outside_dir / "secret.txt").write_text("secret", encoding="utf-8")
            (plugin / "linked-dir").symlink_to(outside_dir, target_is_directory=True)

            urls = (
                "/plugins/safe-plugin/",
                "/plugins/Bad/index.js",
                "/plugins/safe-plugin/%2e%2e/outside.txt",
                "/plugins/safe-plugin/%252e%252e/outside.txt",
                "/plugins/safe-plugin/%2Fetc/passwd",
                "/plugins/safe-plugin/nested%5Cindex.js",
                "/plugins/safe-plugin/.git/config",
                "/plugins/safe-plugin/nested/.hidden",
                "/plugins/safe-plugin/directory",
                "/plugins/safe-plugin/linked-file",
                "/plugins/safe-plugin/linked-dir/secret.txt",
                "/plugins/malformed/index.js",
                "/plugins/safe-plugin/missing.txt",
            )
            builtin_patch, external_patch = self._configured_roots(builtin, external)
            with builtin_patch, external_patch:
                responses = [
                    (url, self._get(url))
                    for url in urls
                ]

            for url, response in responses:
                with self.subTest(url=url):
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn(str(root), response.text)

    def test_http_reads_the_open_descriptor_without_reopening_the_swapped_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin, external = self._roots(root)
            plugin = self._write_plugin(builtin, "safe-plugin")
            asset = plugin / "message.txt"
            asset.write_text("plugin descriptor", encoding="utf-8")
            outside = root / "outside.txt"
            outside.write_text("outside content", encoding="utf-8")
            opened_descriptors = []

            def open_then_swap(*args):
                descriptor = plugin_discovery.open_plugin_asset(*args)
                self.assertIsNotNone(descriptor)
                opened_descriptors.append(descriptor)
                asset.unlink()
                asset.symlink_to(outside)
                return descriptor

            builtin_patch, external_patch = self._configured_roots(builtin, external)
            with builtin_patch, external_patch:
                with patch.object(
                    self.main,
                    "open_plugin_asset",
                    side_effect=open_then_swap,
                    create=True,
                ):
                    with patch.object(
                        self.main,
                        "FileResponse",
                        side_effect=AssertionError("plugin route reopened a pathname"),
                    ):
                        response = self._get("/plugins/safe-plugin/message.txt")

            self.assertEqual((response.status_code, response.text), (200, "plugin descriptor"))
            self.assertNotIn("outside content", response.text)
            with self.assertRaises(OSError):
                os.fstat(opened_descriptors[0])

    def test_http_rejects_a_directory_component_swapped_after_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin, external = self._roots(root)
            plugin = self._write_plugin(builtin, "safe-plugin")
            nested = plugin / "assets"
            nested.mkdir()
            (nested / "message.txt").write_text("plugin", encoding="utf-8")
            moved = plugin / "moved-assets"
            outside = root / "outside-assets"
            outside.mkdir()
            (outside / "message.txt").write_text("outside content", encoding="utf-8")
            real_resolve = plugin_discovery.resolve_plugin_asset
            swapped = False

            def resolve_then_swap(*args):
                nonlocal swapped
                resolved = real_resolve(*args)
                if resolved is not None and not swapped:
                    nested.rename(moved)
                    nested.symlink_to(outside, target_is_directory=True)
                    swapped = True
                return resolved

            builtin_patch, external_patch = self._configured_roots(builtin, external)
            with builtin_patch, external_patch:
                with patch("plugin_discovery.resolve_plugin_asset", side_effect=resolve_then_swap):
                    with patch.object(
                        self.main,
                        "resolve_plugin_asset",
                        side_effect=resolve_then_swap,
                        create=True,
                    ):
                        response = self._get("/plugins/safe-plugin/assets/message.txt")

            self.assertEqual(response.status_code, 404)
            self.assertNotIn("outside content", response.text)
            self.assertNotIn(str(root), response.text)

    def test_http_streams_large_assets_in_bounded_chunks_with_static_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin, external = self._roots(root)
            plugin = self._write_plugin(builtin, "safe-plugin")
            payload = (b"0123456789abcdef" * 8193) + b"tail"
            asset = plugin / "bundle.png"
            asset.write_bytes(payload)
            opened_descriptors = []

            def capture_open(*args):
                descriptor = plugin_discovery.open_plugin_asset(*args)
                opened_descriptors.append(descriptor)
                return descriptor

            builtin_patch, external_patch = self._configured_roots(builtin, external)
            with builtin_patch, external_patch:
                with patch.object(self.main, "open_plugin_asset", side_effect=capture_open):
                    response, chunks = self._get(
                        "/plugins/safe-plugin/bundle.png",
                        with_chunks=True,
                    )

            self.assertEqual((response.status_code, response.content), (200, payload))
            self.assertEqual(response.headers["content-type"], "image/png")
            self.assertEqual(response.headers["content-length"], str(len(payload)))
            self.assertEqual(response.headers["accept-ranges"], "bytes")
            self.assertGreater(len(chunks), 1)
            self.assertLessEqual(max(map(len, chunks)), 64 * 1024)
            with self.assertRaises(OSError):
                os.fstat(opened_descriptors[0])

    def test_http_supports_single_closed_suffix_and_open_ended_byte_ranges(self):
        cases = (
            ("bytes=2-5", b"2345", "bytes 2-5/10"),
            ("bytes=-3", b"789", "bytes 7-9/10"),
            ("bytes=6-", b"6789", "bytes 6-9/10"),
            ("bytes=7-99", b"789", "bytes 7-9/10"),
        )
        for range_header, expected_body, expected_content_range in cases:
            with self.subTest(range_header=range_header), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                builtin, external = self._roots(root)
                plugin = self._write_plugin(builtin, "safe-plugin")
                (plugin / "numbers.txt").write_bytes(b"0123456789")

                builtin_patch, external_patch = self._configured_roots(builtin, external)
                with builtin_patch, external_patch:
                    response = self._get(
                        "/plugins/safe-plugin/numbers.txt",
                        headers={"range": range_header},
                    )

                self.assertEqual((response.status_code, response.content), (206, expected_body))
                self.assertEqual(response.headers["content-range"], expected_content_range)
                self.assertEqual(response.headers["content-length"], str(len(expected_body)))
                self.assertEqual(response.headers["accept-ranges"], "bytes")

    def test_http_rejects_invalid_or_unsatisfiable_ranges_and_closes_descriptors(self):
        for range_header in (
            "bytes=99-",
            "bytes=5-2",
            "bytes=0-1,4-5",
            "bytes=bad",
            "items=0-1",
        ):
            with self.subTest(range_header=range_header), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                builtin, external = self._roots(root)
                plugin = self._write_plugin(builtin, "safe-plugin")
                (plugin / "numbers.txt").write_bytes(b"0123456789")
                opened_descriptors = []

                def capture_open(*args):
                    descriptor = plugin_discovery.open_plugin_asset(*args)
                    opened_descriptors.append(descriptor)
                    return descriptor

                builtin_patch, external_patch = self._configured_roots(builtin, external)
                with builtin_patch, external_patch:
                    with patch.object(self.main, "open_plugin_asset", side_effect=capture_open):
                        response = self._get(
                            "/plugins/safe-plugin/numbers.txt",
                            headers={"range": range_header},
                        )

                self.assertEqual((response.status_code, response.content), (416, b""))
                self.assertEqual(response.headers["content-range"], "bytes */10")
                self.assertEqual(response.headers["content-length"], "0")
                self.assertEqual(response.headers["accept-ranges"], "bytes")
                with self.assertRaises(OSError):
                    os.fstat(opened_descriptors[0])


if __name__ == "__main__":
    unittest.main()
