"""Repository-local plugin discovery for the trusted same-page plugin runtime."""

import json
from pathlib import Path, PurePosixPath


REQUIRED_MANIFEST_FIELDS = ("id", "name", "version", "apiVersion", "main")


def _safe_plugin_file(plugin_dir: Path, value: str) -> str:
    path = PurePosixPath(str(value or ""))
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe plugin path: {value!r}")
    resolved = plugin_dir.joinpath(*path.parts)
    if not resolved.is_file():
        raise ValueError(f"plugin file does not exist: {value}")
    return path.as_posix()


def discover_plugins(root) -> dict:
    root = Path(root)
    plugins = []
    errors = []
    if not root.is_dir():
        return {"plugins": plugins, "errors": errors}
    for manifest_path in sorted(root.glob("*/plugin.json")):
        directory = manifest_path.parent.name
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("manifest must be an object")
            missing = [field for field in REQUIRED_MANIFEST_FIELDS if field not in manifest]
            if missing:
                raise ValueError(f"missing manifest fields: {', '.join(missing)}")
            plugin_id = str(manifest["id"]).strip()
            if plugin_id != directory:
                raise ValueError("manifest id must match its directory")
            if int(manifest["apiVersion"]) != 1:
                raise ValueError(f"unsupported apiVersion: {manifest['apiVersion']}")
            main = _safe_plugin_file(manifest_path.parent, str(manifest["main"]))
            styles = [_safe_plugin_file(manifest_path.parent, str(item)) for item in manifest.get("styles", [])]
            plugins.append({
                **manifest,
                "id": plugin_id,
                "main": main,
                "styles": styles,
                "moduleUrl": f"/plugins/{plugin_id}/{main}",
                "styleUrls": [f"/plugins/{plugin_id}/{style}" for style in styles],
            })
        except Exception as exc:
            errors.append({"plugin": directory, "error": str(exc)})
    return {"plugins": plugins, "errors": errors}
