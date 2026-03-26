import os
import sys
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'history.db')


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            page_type TEXT,
            accessed_at TEXT NOT NULL,
            space_key TEXT,
            UNIQUE(url)
        )
    ''')
    conn.commit()
    conn.close()


def save_url(url, title="", page_type="confluence", space_key=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO history (url, title, page_type, accessed_at, space_key)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title=excluded.title,
            accessed_at=excluded.accessed_at
    ''', (url, title, page_type, datetime.now().isoformat(), space_key))
    conn.commit()
    conn.close()


def get_history(limit=20):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT url, title, page_type, accessed_at, space_key
        FROM history
        ORDER BY accessed_at DESC
        LIMIT ?
    ''', (limit,))
    rows = c.fetchall()
    conn.close()
    return [
        {"url": r[0], "title": r[1], "page_type": r[2], "accessed_at": r[3], "space_key": r[4]}
        for r in rows
    ]


def clear_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM history')
    conn.commit()
    conn.close()


init_db()