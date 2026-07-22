import sqlite3
import uuid
import os
import json
from datetime import datetime, timedelta
import bcrypt

DB_PATH = "data/auth.db"
ADMIN_PASSWORD_HASH = bcrypt.hashpw(os.getenv("ADMIN_PASSWORD", "admin123").encode(), bcrypt.gensalt()).decode()
_admin_tokens = set()  # in-memory admin session tokens


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


def admin_login(password: str) -> dict:
    """Admin login with shared password. Returns token on success."""
    if bcrypt.checkpw(password.encode(), ADMIN_PASSWORD_HASH.encode()):
        token = str(uuid.uuid4())
        _admin_tokens.add(token)
        return {"success": True, "token": token}
    return {"success": False, "error": "Invalid admin password"}


def validate_admin(token: str) -> bool:
    return token in _admin_tokens


def admin_logout(token: str):
    _admin_tokens.discard(token)


def list_users() -> list:
    """List all users who have data directories."""
    users = set()
    student_dir = "data/student"
    if os.path.exists(student_dir):
        for name in os.listdir(student_dir):
            if os.path.isdir(os.path.join(student_dir, name)):
                users.add(name)
    # Also check users table in auth.db
    conn = get_connection()
    for row in conn.execute("SELECT username FROM users ORDER BY username").fetchall():
        users.add(row["username"])
    conn.close()
    return sorted(users)


def get_user_states(username: str) -> list:
    """List course map files for a user."""
    states = []
    student_dir = f"data/student/{username}"
    if os.path.exists(student_dir):
        for f in sorted(os.listdir(student_dir)):
            if f.endswith("_map.md"):
                course = f.replace("_map.md", "")
                filepath = os.path.join(student_dir, f)
                states.append({
                    "course": course,
                    "file": f,
                    "size": os.path.getsize(filepath),
                    "modified": datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                })
    return states


def get_user_progress(username: str, course: str):
    """Read just the progress file for a user."""
    path = f"data/student/{username}/{course}_progress.md"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            return content if content.strip() else "(暂无进展记录)"
    return "(暂无进展记录)"


def get_user_state_content(username: str, course: str):
    """Read course_map + progress for a user."""
    parts = []
    map_path = f"data/student/{username}/{course}_map.md"
    prog_path = f"data/student/{username}/{course}_progress.md"
    if os.path.exists(map_path):
        with open(map_path, "r", encoding="utf-8") as f:
            parts.append(f.read())
    if os.path.exists(prog_path):
        with open(prog_path, "r", encoding="utf-8") as f:
            progress = f.read()
            if progress.strip():
                parts.append(progress)
    return "\n\n".join(parts) if parts else None


def list_user_sessions(username: str) -> list:
    """List session files for a user, sorted by modification time (newest first)."""
    sessions = []
    session_dir = f"data/student/{username}/sessions"
    if os.path.exists(session_dir):
        files = []
        for f in os.listdir(session_dir):
            if f.endswith(".json"):
                filepath = os.path.join(session_dir, f)
                files.append((filepath, f, os.path.getmtime(filepath)))
        files.sort(key=lambda x: x[2], reverse=True)
        for filepath, f, mtime in files:
            # Try to read course from session JSON
            course = ""
            try:
                with open(filepath, "r", encoding="utf-8") as sf:
                    data = json.load(sf)
                    course = data.get("course", "")
            except Exception:
                pass
            sessions.append({
                "session_id": f.replace(".json", ""),
                "course": course,
                "size": os.path.getsize(filepath),
                "modified": datetime.fromtimestamp(mtime).isoformat()
            })
    return sessions


def get_user_session_content(username: str, session_id: str):
    """Read a specific (old-style) session file for a user."""
    path = f"data/student/{username}/sessions/{session_id}.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def list_unified_sessions(username: str) -> list:
    """List unified course-based session logs ({course}_session.log)."""
    sessions = []
    student_dir = f"data/student/{username}"
    if os.path.exists(student_dir):
        for f in sorted(os.listdir(student_dir)):
            if f.endswith("_session.log"):
                course = f.replace("_session.log", "")
                filepath = os.path.join(student_dir, f)
                stat = os.stat(filepath)
                sessions.append({
                    "course": course,
                    "file": f,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
    return sessions


def get_unified_session_content(username: str, course: str) -> list:
    """Read a unified session log, return list of message dicts."""
    path = f"data/student/{username}/{course}_session.log"
    if not os.path.exists(path):
        return []
    messages = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return messages


def reset_user_password(username: str, new_password: str) -> dict:
    """Admin: reset a user's password."""
    conn = get_connection()
    user = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if not user:
        conn.close()
        return {"success": False, "error": "User not found"}
    password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, user["id"]))
    # Invalidate all sessions for this user
    conn.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Password reset for {username}"}
