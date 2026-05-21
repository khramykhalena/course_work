import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "app.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'user'))
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL,
        category TEXT,
        object_group TEXT,
        object_name TEXT,
        status TEXT,
        assigned_at TEXT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        task_link TEXT,
        violation_photo TEXT,
        fix_photo TEXT,
        raw_json TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS upload_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        uploaded_at TEXT NOT NULL,
        accepted_count INTEGER NOT NULL,
        error_count INTEGER NOT NULL,
        errors_json TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()
