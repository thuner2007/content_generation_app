"""Bootstrap: initialise DB and configure app data directory."""
from pathlib import Path


def bootstrap() -> None:
    """Run all startup initialization tasks."""
    _ensure_data_dir()
    _init_database()


def _ensure_data_dir() -> None:
    data_dir = Path.home() / ".ai_ads_studio"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "files").mkdir(exist_ok=True)   # uploaded project files
    (data_dir / "exports").mkdir(exist_ok=True)  # exported assets


def _init_database() -> None:
    from storage.db import init_db
    init_db()
