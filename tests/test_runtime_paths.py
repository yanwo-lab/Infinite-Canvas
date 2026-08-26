import os
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class RuntimePathTests(unittest.TestCase):
    def inspect_paths(self, overrides):
        env = os.environ.copy()
        env.update(overrides)
        command = [
            sys.executable,
            "-c",
            (
                "import json; from runtime_paths import RuntimePaths; paths = RuntimePaths.from_environment(); "
                "print(json.dumps({"
                "'data': paths.data_dir, "
                "'assets': paths.assets_dir, "
                "'uploads': paths.local_upload_dir, "
                "'cache': paths.cache_dir, "
                "'previews': paths.media_preview_dir, "
                "'history': paths.history_file, "
                "'global_config': paths.global_config_file, "
                "'api_env': paths.api_env_file"
                "}))"
            ),
        ]
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        return __import__("json").loads(result.stdout.strip().splitlines()[-1])

    def test_environment_overrides_runtime_storage_roots(self):
        paths = self.inspect_paths(
            {
                "CANVAS_DATA_DIR": "/tmp/canvas-test-data",
                "CANVAS_UPLOADS_DIR": "/tmp/canvas-test-uploads",
                "CANVAS_CACHE_DIR": "/tmp/canvas-test-cache",
            }
        )

        self.assertEqual(paths["data"], "/tmp/canvas-test-data")
        self.assertEqual(paths["assets"], "/tmp/canvas-test-uploads")
        self.assertEqual(paths["uploads"], "/tmp/canvas-test-uploads/uploads")
        self.assertEqual(paths["cache"], "/tmp/canvas-test-cache")
        self.assertEqual(paths["previews"], "/tmp/canvas-test-cache/media_previews")
        self.assertEqual(paths["history"], "/tmp/canvas-test-data/history.json")
        self.assertEqual(paths["global_config"], "/tmp/canvas-test-data/global_config.json")
        self.assertEqual(paths["api_env"], "/tmp/canvas-test-data/api.env")

    def test_unconfigured_paths_keep_repository_compatible_defaults(self):
        paths = self.inspect_paths(
            {
                "CANVAS_DATA_DIR": "",
                "CANVAS_UPLOADS_DIR": "",
                "CANVAS_CACHE_DIR": "",
            }
        )

        self.assertEqual(paths["data"], str(REPO_ROOT / "data"))
        self.assertEqual(paths["assets"], str(REPO_ROOT / "assets"))
        self.assertEqual(paths["uploads"], str(REPO_ROOT / "assets" / "uploads"))
        self.assertEqual(paths["cache"], str(REPO_ROOT / "data" / "cache"))
        self.assertEqual(paths["previews"], str(REPO_ROOT / "data" / "cache" / "media_previews"))
        self.assertEqual(paths["history"], str(REPO_ROOT / "history.json"))
        self.assertEqual(paths["global_config"], str(REPO_ROOT / "global_config.json"))
        self.assertEqual(paths["api_env"], str(REPO_ROOT / "API" / ".env"))


if __name__ == "__main__":
    unittest.main()
