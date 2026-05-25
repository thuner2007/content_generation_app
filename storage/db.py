"""SQLite database initialization and connection management."""
import sqlite3
import threading
from pathlib import Path

_DB_PATH: Path = Path.home() / ".ai_ads_studio" / "studio.db"
_lock = threading.Lock()


def get_db_path() -> Path:
    return _DB_PATH


def get_connection() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables if they don't exist."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slogan TEXT DEFAULT '',
                brand_colors TEXT DEFAULT '',
                fonts TEXT DEFAULT '',
                logo_path TEXT DEFAULT '',
                legal_info TEXT DEFAULT '',
                description TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                title TEXT DEFAULT 'New Chat',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                provider TEXT DEFAULT '',
                model TEXT DEFAULT '',
                tokens_used INTEGER DEFAULT 0,
                cost REAL DEFAULT 0.0,
                pinned INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS assets (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                type TEXT NOT NULL,
                title TEXT DEFAULT '',
                content TEXT NOT NULL,
                tags TEXT DEFAULT '',
                provider TEXT DEFAULT '',
                model TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                provider TEXT PRIMARY KEY,
                api_key TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS usage_logs (
                id TEXT PRIMARY KEY,
                project_id TEXT DEFAULT '',
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                tokens_input INTEGER DEFAULT 0,
                tokens_output INTEGER DEFAULT 0,
                cost REAL DEFAULT 0.0,
                generation_type TEXT DEFAULT 'chat',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS project_files (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT DEFAULT '',
                extracted_text TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'draft',
                strategy TEXT DEFAULT '',
                objective TEXT DEFAULT '',
                platforms TEXT DEFAULT '[]',
                daily_budget REAL DEFAULT 0.0,
                total_budget REAL DEFAULT 0.0,
                start_date TEXT DEFAULT '',
                end_date TEXT DEFAULT '',
                target_audience TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                price TEXT DEFAULT '',
                url TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
        """)
        conn.commit()

        # Migrations — safe to run on every startup
        _migrate(conn)
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    migrations = [
        "ALTER TABLE projects ADD COLUMN marketing_brief TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN image_style TEXT DEFAULT ''",
        "ALTER TABLE campaigns ADD COLUMN product_name TEXT DEFAULT ''",
        "ALTER TABLE campaigns ADD COLUMN product_description TEXT DEFAULT ''",
        "ALTER TABLE campaigns ADD COLUMN video_ideas TEXT DEFAULT '[]'",
        "ALTER TABLE campaigns ADD COLUMN product_ids TEXT DEFAULT '[]'",
        "ALTER TABLE projects ADD COLUMN tone_of_voice TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN brand_values TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN voiceover_voice TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN music_mood TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN video_style TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN target_audience TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN content_pillars TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN hashtags TEXT DEFAULT ''",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            pass  # column already exists
