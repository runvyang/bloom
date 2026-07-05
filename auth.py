import sqlite3
import uuid
import os
from datetime import datetime, timedelta
import bcrypt

DB_PATH = "data/auth.db"


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

        CREATE TABLE IF NOT EXISTS sessions (
            token       TEXT PRIMARY KEY,
            user_id     INTEGER NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at  TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
    """)
    conn.commit()
    conn.close()


def register_user(username: str, password: str) -> dict:
    if not username or len(username) < 2:
        return {"success": False, "error": "Username must be at least 2 characters"}
    if not password or len(password) < 4:
        return {"success": False, "error": "Password must be at least 4 characters"}

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            conn.close()
            return {"success": False, "error": "Username already taken"}

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        token = create_session(user_id)
        return {"success": True, "token": token, "user": {"id": user_id, "username": username}}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def authenticate_user(username: str, password: str) -> dict:
    conn = get_connection()
    user = conn.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    conn.close()

    if not user:
        return {"success": False, "error": "Invalid username or password"}

    if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return {"success": False, "error": "Invalid username or password"}

    token = create_session(user["id"])
    return {
        "success": True,
        "token": token,
        "user": {"id": user["id"], "username": user["username"]}
    }


def create_session(user_id: int) -> str:
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=7)
    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at.isoformat())
    )
    conn.commit()
    conn.close()
    return token


def validate_session(token: str):
    conn = get_connection()
    row = conn.execute(
        """SELECT s.token, s.user_id, s.expires_at, u.username
           FROM sessions s JOIN users u ON s.user_id = u.id
           WHERE s.token = ?""",
        (token,)
    ).fetchone()

    if not row:
        conn.close()
        return None

    expires_at = datetime.fromisoformat(row["expires_at"])
    if datetime.utcnow() > expires_at:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return None

    conn.close()
    return {"id": row["user_id"], "username": row["username"]}


def invalidate_session(token: str):
    conn = get_connection()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def cleanup_expired_sessions() -> int:
    conn = get_connection()
    cursor = conn.execute(
        "DELETE FROM sessions WHERE expires_at < datetime('now')"
    )
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count
