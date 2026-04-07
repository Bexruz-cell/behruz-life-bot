import sqlite3
import json
import logging
from datetime import datetime
from bot.config import DB_PATH

logger = logging.getLogger(__name__)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            photo_url TEXT,
            message_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            topic TEXT,
            mood TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS day_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS custom_phrases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phrase TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            photo_url TEXT,
            scheduled_at TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    defaults = {
        "active": "1",
        "interval_min": "120",
        "interval_max": "240",
        "school_mode": "1",
        "news_mode": "0",
        "photo_mode": "1",
        "only_photo_mode": "0",
        "continue_story_mode": "0",
        "mood": "нейтральное",
        "photo_keywords": "street night city alone music teen",
        "daily_report": "1",
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()
    logger.info("Database initialized")


def get_setting(key: str, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def save_post(text: str, photo_url: str = None, message_id: int = None,
              topic: str = None, mood: str = None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO posts (text, photo_url, message_id, topic, mood) VALUES (?, ?, ?, ?, ?)",
        (text, photo_url, message_id, topic, mood)
    )
    conn.commit()
    conn.close()


def get_last_posts(n: int = 10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM posts ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_posts():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_posts_count():
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM posts").fetchone()
    conn.close()
    return row["cnt"]


def get_today_posts_count():
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM posts WHERE date(created_at)=date('now','localtime')"
    ).fetchone()
    conn.close()
    return row["cnt"]


def get_last_post():
    conn = get_conn()
    row = conn.execute("SELECT * FROM posts ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def delete_last_post():
    conn = get_conn()
    row = conn.execute("SELECT id, message_id FROM posts ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        conn.execute("DELETE FROM posts WHERE id=?", (row["id"],))
        conn.commit()
        conn.close()
        return row["message_id"]
    conn.close()
    return None


def clear_history():
    conn = get_conn()
    conn.execute("DELETE FROM posts")
    conn.commit()
    conn.close()


def add_day_event(event: str):
    conn = get_conn()
    conn.execute("INSERT INTO day_events (event) VALUES (?)", (event,))
    conn.commit()
    conn.close()


def get_today_events():
    conn = get_conn()
    rows = conn.execute(
        "SELECT event FROM day_events WHERE date(created_at)=date('now','localtime') ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [r["event"] for r in rows]


def add_custom_phrase(phrase: str):
    conn = get_conn()
    conn.execute("INSERT INTO custom_phrases (phrase) VALUES (?)", (phrase,))
    conn.commit()
    conn.close()


def get_custom_phrases():
    conn = get_conn()
    rows = conn.execute("SELECT phrase FROM custom_phrases ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    return [r["phrase"] for r in rows]


def add_scheduled_post(text: str, photo_url: str, scheduled_at: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO scheduled_posts (text, photo_url, scheduled_at) VALUES (?, ?, ?)",
        (text, photo_url, scheduled_at)
    )
    conn.commit()
    conn.close()


def get_pending_scheduled_posts():
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = conn.execute(
        "SELECT * FROM scheduled_posts WHERE done=0 AND scheduled_at<=?", (now,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_scheduled_done(post_id: int):
    conn = get_conn()
    conn.execute("UPDATE scheduled_posts SET done=1 WHERE id=?", (post_id,))
    conn.commit()
    conn.close()


def add_log(action: str, detail: str = None):
    conn = get_conn()
    conn.execute("INSERT INTO logs (action, detail) VALUES (?, ?)", (action, detail))
    conn.commit()
    conn.close()


def get_last_logs(n: int = 20):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def export_to_json():
    data = {
        "posts": get_all_posts(),
        "settings": {},
        "day_events": [],
        "custom_phrases": get_custom_phrases(),
        "logs": get_last_logs(100),
        "exported_at": datetime.now().isoformat(),
    }
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    data["settings"] = {r["key"]: r["value"] for r in rows}
    rows2 = conn.execute("SELECT event, created_at FROM day_events ORDER BY id DESC LIMIT 50").fetchall()
    data["day_events"] = [dict(r) for r in rows2]
    conn.close()
    return json.dumps(data, ensure_ascii=False, indent=2)


def get_avg_post_length():
    conn = get_conn()
    rows = conn.execute("SELECT text FROM posts").fetchall()
    conn.close()
    if not rows:
        return 0
    lengths = [len(r["text"]) for r in rows]
    return round(sum(lengths) / len(lengths))
