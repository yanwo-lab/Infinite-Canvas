import os
from dataclasses import dataclass
from pathlib import Path


def _configured_path(name: str, default: Path) -> str:
    value = os.getenv(name, "").strip()
    return str(Path(value).expanduser().resolve()) if value else str(default.resolve())


@dataclass(frozen=True)
class RuntimePaths:
    base_dir: str
    data_dir: str
    assets_dir: str
    cache_dir: str
    output_dir: str
    data_dir_configured: bool

    @classmethod
    def from_environment(cls, base_dir: str | None = None) -> "RuntimePaths":
        base = Path(base_dir or Path(__file__).resolve().parent)
        data = Path(_configured_path("CANVAS_DATA_DIR", base / "data"))
        assets = Path(_configured_path("CANVAS_UPLOADS_DIR", base / "assets"))
        cache = Path(_configured_path("CANVAS_CACHE_DIR", data / "cache"))
        output = Path(_configured_path("CANVAS_OUTPUT_DIR", base / "output"))
        return cls(
            base_dir=str(base.resolve()),
            data_dir=str(data),
            assets_dir=str(assets),
            cache_dir=str(cache),
            output_dir=str(output),
            data_dir_configured=bool(os.getenv("CANVAS_DATA_DIR", "").strip()),
        )

    @property
    def local_upload_dir(self) -> str:
        return str(Path(self.assets_dir) / "uploads")

    @property
    def media_preview_dir(self) -> str:
        return str(Path(self.cache_dir) / "media_previews")

    @property
    def history_file(self) -> str:
        root = Path(self.data_dir) if self.data_dir_configured else Path(self.base_dir)
        return str(root / "history.json")

    @property
    def global_config_file(self) -> str:
        root = Path(self.data_dir) if self.data_dir_configured else Path(self.base_dir)
        return str(root / "global_config.json")

    @property
    def api_env_file(self) -> str:
        if self.data_dir_configured:
            return str(Path(self.data_dir) / "api.env")
        return str(Path(self.base_dir) / "API" / ".env")
