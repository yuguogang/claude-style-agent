import os
import sqlite3
import json
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src/.. = project root
DB_PATH = os.path.join(BASE_DIR, "agent_state.db")
def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state_json TEXT NOT NULL
        )
        """)
        conn.execute("INSERT OR IGNORE INTO state (id, state_json) VALUES (1, '{}')")

def load_state() -> Optional[dict]:
    with get_conn() as conn:
        cur = conn.execute("SELECT state_json FROM state WHERE id = 1")
        row = cur.fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        return data if data else None

def save_state(state: dict):
    with get_conn() as conn:
        conn.execute(
            "UPDATE state SET state_json = ? WHERE id = 1",
            (json.dumps(state),)
        )

def clear_state():
    with get_conn() as conn:
        conn.execute("UPDATE state SET state_json = '{}' WHERE id = 1")
