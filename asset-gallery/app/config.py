from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    image_dir: Path = Path(".")  # scan root; override via IMAGE_DIR env var
    thumb_dir: Path = Path("./data/thumbs")
    export_dir: Path = Path("./exports")
    # Comma-separated dirs (relative to image_dir root) to skip during scan.
    # Defaults cover the thumbs cache and the Python virtualenv.
    exclude_dirs: str = "data/thumbs,.venv"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "jina_clip_gallery"
    jina_model: str = "jinaai/jina-clip-v2"
    embedding_dim: int = 1024
    scan_batch_size: int = 256
    motif_classes: str = (
        "portrait,person,landscape,city,architecture,interior,product,food,"
        "animal,vehicle,document,artwork,other"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def motif_labels(self) -> list[str]:
        return [item.strip() for item in self.motif_classes.split(",") if item.strip()]

    @property
    def excluded_paths(self) -> list[Path]:
        """Resolved absolute paths to skip during image scanning."""
        root = self.image_dir.expanduser().resolve()
        return [
            (root / d.strip()).resolve()
            for d in self.exclude_dirs.split(",")
            if d.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.image_dir.mkdir(parents=True, exist_ok=True)
    settings.thumb_dir.mkdir(parents=True, exist_ok=True)
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    return settings
