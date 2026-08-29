"""Repository-local plugin discovery for the trusted same-page plugin runtime."""

import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from urllib.parse import quote


REQUIRED_MANIFEST_FIELDS = ("id", "name", "version", "apiVersion", "main")
PLUGIN_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
PLUGIN_SOURCES = frozenset({"builtin", "external"})


class PluginValidationError(ValueError):
    """A validation failure whose message is safe to expose through the API."""


def _safe_plugin_file(plugin_dir: Path, value: object) -> str:
    if type(value) is not str or not value:
        raise PluginValidationError("plugin path must be a non-empty string")
    if "\\" in value or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise PluginValidationError("plugin path contains an unsafe character")

    path = PurePosixPath(value)
    parts = value.split("/")
    if path.is_absolute() or any(
        not component or component in {".", ".."} or component.startswith(".")
        for component in parts
    ):
        raise PluginValidationError("plugin path must use visible relative POSIX components")

    try:
        plugin_stat = plugin_dir.lstat()
        plugin_root = plugin_dir.resolve(strict=True)
    except OSError as exc:
        raise PluginValidationError("plugin directory is unavailable") from exc
    if stat.S_ISLNK(plugin_stat.st_mode) or not stat.S_ISDIR(plugin_stat.st_mode):
        raise PluginValidationError("plugin directory must be a real directory")

    candidate = plugin_dir
    for index, component in enumerate(parts):
        candidate = candidate / component
        try:
            component_stat = candidate.lstat()
        except OSError as exc:
            raise PluginValidationError("plugin file does not exist") from exc
        if stat.S_ISLNK(component_stat.st_mode):
            raise PluginValidationError("plugin path must not contain symlinks")
        if index < len(parts) - 1 and not stat.S_ISDIR(component_stat.st_mode):
            raise PluginValidationError("plugin path parent must be a directory")
        if index == len(parts) - 1 and not stat.S_ISREG(component_stat.st_mode):
            raise PluginValidationError("plugin path target must be a regular file")

    try:
        resolved = candidate.resolve(strict=True)
        if os.path.commonpath((str(plugin_root), str(resolved))) != str(plugin_root):
            raise PluginValidationError("plugin path escapes its directory")
    except OSError as exc:
        raise PluginValidationError("plugin file is unavailable") from exc
    return path.as_posix()


def validate_plugin_directory(plugin_dir: Path, source: str) -> dict:
    """Validate one plugin directory and return its path-free API record."""

    plugin_dir = Path(plugin_dir)
    if source not in PLUGIN_SOURCES:
        raise PluginValidationError("plugin source must be builtin or external")

    try:
        plugin_stat = plugin_dir.lstat()
    except OSError as exc:
        raise PluginValidationError("plugin directory is unavailable") from exc
    if stat.S_ISLNK(plugin_stat.st_mode) or not stat.S_ISDIR(plugin_stat.st_mode):
        raise PluginValidationError("plugin directory must be a real directory")

    manifest_path = plugin_dir / "plugin.json"
    try:
        manifest_stat = manifest_path.lstat()
        if stat.S_ISLNK(manifest_stat.st_mode) or not stat.S_ISREG(manifest_stat.st_mode):
            raise PluginValidationError("plugin manifest must be a regular non-symlink file")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PluginValidationError("plugin manifest is not valid JSON") from exc
    except UnicodeError as exc:
        raise PluginValidationError("plugin manifest is not valid UTF-8") from exc
    except OSError as exc:
        raise PluginValidationError("plugin manifest is unavailable") from exc

    if not isinstance(manifest, dict):
        raise PluginValidationError("manifest must be an object")
    missing = [field for field in REQUIRED_MANIFEST_FIELDS if field not in manifest]
    if missing:
        raise PluginValidationError(f"missing manifest fields: {', '.join(missing)}")

    plugin_id = manifest["id"]
    if type(plugin_id) is not str or not PLUGIN_ID_PATTERN.fullmatch(plugin_id):
        raise PluginValidationError("manifest id is invalid")
    if plugin_id != plugin_dir.name:
        raise PluginValidationError("manifest id must match its directory")

    api_version = manifest["apiVersion"]
    if type(api_version) is not int or api_version != 1:
        raise PluginValidationError("unsupported apiVersion")

    main = _safe_plugin_file(plugin_dir, manifest["main"])
    styles_value = manifest.get("styles", [])
    if not isinstance(styles_value, list):
        raise PluginValidationError("manifest styles must be a list")
    styles = [_safe_plugin_file(plugin_dir, value) for value in styles_value]

    return {
        **manifest,
        "id": plugin_id,
        "main": main,
        "styles": styles,
        "source": source,
        "moduleUrl": f"/plugins/{plugin_id}/{quote(main, safe='/')}",
        "styleUrls": [f"/plugins/{plugin_id}/{quote(style, safe='/')}" for style in styles],
    }


def discover_plugins(builtin_root, external_root=None) -> dict:
    """Discover valid built-in plugins, followed by valid external plugins."""

    plugins = []
    errors = []
    selected_sources = {}

    for source, configured_root in (("builtin", builtin_root), ("external", external_root)):
        if configured_root is None:
            continue
        root = Path(configured_root)
        if not root.is_dir():
            continue
        try:
            plugin_dirs = sorted(
                (
                    entry
                    for entry in root.iterdir()
                    if not entry.name.startswith(".") and entry.is_dir()
                ),
                key=lambda entry: entry.name,
            )
        except OSError:
            continue

        for plugin_dir in plugin_dirs:
            try:
                plugin = validate_plugin_directory(plugin_dir, source)
                plugin_id = plugin["id"]
                if plugin_id in selected_sources:
                    errors.append({
                        "plugin": plugin_dir.name,
                        "source": source,
                        "error": f"duplicate plugin id conflicts with {selected_sources[plugin_id]}",
                    })
                    continue
                selected_sources[plugin_id] = source
                plugins.append(plugin)
            except PluginValidationError as exc:
                errors.append({
                    "plugin": plugin_dir.name,
                    "source": source,
                    "error": str(exc),
                })
            except Exception:
                errors.append({
                    "plugin": plugin_dir.name,
                    "source": source,
                    "error": "plugin validation failed",
                })

    return {"plugins": plugins, "errors": errors}


def resolve_plugin_asset(builtin_root, external_root, plugin_id, asset_path) -> Path | None:
    """Resolve one safe file from the authoritative valid plugin selection.

    ``asset_path`` is treated as the router-decoded path. It is intentionally
    not URL-decoded again, so a literal percent sequence in a validated file
    name cannot become a separator or traversal component here.
    """

    if type(plugin_id) is not str or not PLUGIN_ID_PATTERN.fullmatch(plugin_id):
        return None
    if type(asset_path) is not str:
        return None

    selected = next(
        (
            plugin
            for plugin in discover_plugins(builtin_root, external_root)["plugins"]
            if plugin["id"] == plugin_id
        ),
        None,
    )
    if selected is None:
        return None

    configured_root = builtin_root if selected["source"] == "builtin" else external_root
    if configured_root is None:
        return None
    plugin_dir = Path(configured_root) / plugin_id
    try:
        safe_asset_path = _safe_plugin_file(plugin_dir, asset_path)
    except (PluginValidationError, OSError, ValueError):
        return None
    return plugin_dir.joinpath(*PurePosixPath(safe_asset_path).parts)


def open_plugin_asset(builtin_root, external_root, plugin_id, asset_path) -> int | None:
    """Open a selected plugin asset without following mutable path components.

    The caller owns the returned descriptor and must close it. ``None`` is
    returned for invalid plugins, unsafe paths, races, and non-regular files.
    """

    resolved = resolve_plugin_asset(builtin_root, external_root, plugin_id, asset_path)
    if resolved is None:
        return None

    components = asset_path.split("/")
    plugin_dir = resolved
    for _ in components:
        plugin_dir = plugin_dir.parent

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    directory_fd = None
    asset_fd = None
    try:
        directory_fd = os.open(plugin_dir, directory_flags)
        for component in components[:-1]:
            next_directory_fd = os.open(
                component,
                directory_flags,
                dir_fd=directory_fd,
            )
            os.close(directory_fd)
            directory_fd = next_directory_fd

        asset_fd = os.open(components[-1], file_flags, dir_fd=directory_fd)
        if not stat.S_ISREG(os.fstat(asset_fd).st_mode):
            os.close(asset_fd)
            asset_fd = None
            return None
        return asset_fd
    except (OSError, TypeError, ValueError):
        if asset_fd is not None:
            os.close(asset_fd)
        return None
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
