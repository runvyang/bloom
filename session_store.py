"""
Unified course-based session store.

Replaces the old per-session_id JSON files with a single {course}_session.log
per user per course. Uses JSON Lines format (one JSON per line) for easy append.

Also manages {course}_mem.log for compressed long-term context.
"""
import os
import json
from datetime import datetime
from storage import get_conn


def _log_path(user_id: str, course: str) -> str:
    return f"data/student/{user_id}/{course}_session.log"


def _mem_path(user_id: str, course: str) -> str:
    return f"data/student/{user_id}/{course}_mem.log"


def append_to_session(user_id: str, course: str, role: str, content: str):
    """Append one message to the unified session log."""
    path = _log_path(user_id, course)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    entry = {
        "role": role,
        "content": content,
        "time": datetime.now().isoformat()
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_recent_rounds(user_id: str, course: str, max_rounds: int = 20) -> list:
    """
    Get the most recent N rounds (a round = user message + assistant response)
    from the session log. Returns list of message dicts.
    """
    path = _log_path(user_id, course)
    if not os.path.exists(path):
        return []

    # Read all lines, keep last max_rounds*2 messages (user+assistant per round)
    all_msgs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    all_msgs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    # Keep last max_rounds * 2 messages (roughly max_rounds turns)
    max_msgs = max_rounds * 2
    if len(all_msgs) > max_msgs:
        all_msgs = all_msgs[-max_msgs:]

    return all_msgs


def get_all_messages(user_id: str, course: str) -> list:
    """Get all messages from session log (for migration/compression)."""
    path = _log_path(user_id, course)
    if not os.path.exists(path):
        return []
    all_msgs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    all_msgs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return all_msgs


def count_rounds(user_id: str, course: str) -> int:
    """Count approximate number of rounds in the session log."""
    msgs = get_all_messages(user_id, course)
    user_msgs = [m for m in msgs if m.get("role") == "user"]
    return len(user_msgs)


def needs_compression(user_id: str, course: str, threshold: int = 30) -> bool:
    """Check if the session log has more than threshold rounds."""
    return count_rounds(user_id, course) > threshold


def get_compressed_mem(user_id: str, course: str) -> str:
    """Read the compressed memory log."""
    path = _mem_path(user_id, course)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def append_compressed_mem(user_id: str, course: str, summary: str):
    """Append a compressed summary to the memory log."""
    path = _mem_path(user_id, course)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n[{ts}] Compressed Summary:\n{summary}\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)


def truncate_and_compress(user_id: str, course: str, keep_rounds: int = 20):
    """
    Keep the most recent keep_rounds in the session log,
    compress older rounds into the mem log.
    Returns True if compression happened.
    """
    path = _log_path(user_id, course)
    if not os.path.exists(path):
        return False

    all_msgs = get_all_messages(user_id, course)
    user_count = len([m for m in all_msgs if m.get("role") == "user"])
    if user_count <= keep_rounds:
        return False

    # Find the cutoff point: keep last keep_rounds user messages
    kept = []
    user_seen = 0
    for m in reversed(all_msgs):
        kept.insert(0, m)
        if m.get("role") == "user":
            user_seen += 1
            if user_seen >= keep_rounds:
                break

    old_msgs = all_msgs[:-len(kept)] if len(kept) < len(all_msgs) else []
    if not old_msgs:
        return False

    # Build summary from old messages
    summary_lines = []
    current_user_msg = None
    for m in old_msgs:
        if m.get("role") == "user":
            current_user_msg = m.get("content", "")
        elif m.get("role") == "assistant" and current_user_msg:
            summary_lines.append(f"学生：{current_user_msg[:200]}")
            summary_lines.append(f"老师：{m.get('content', '')[:200]}")
            summary_lines.append("---")

    if summary_lines:
        summary = "历史对话摘要：\n" + "\n".join(summary_lines)
        append_compressed_mem(user_id, course, summary)

    # Rewrite session log with only kept messages
    with open(path, "w", encoding="utf-8") as f:
        for m in kept:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    return True


# ─── SQLite session tracking ──────────────────────────────

def init_session_tracking():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS session_tracking (
            user_id TEXT NOT NULL,
            course TEXT NOT NULL,
            last_session_id TEXT,
            is_new_session INTEGER DEFAULT 1,
            last_active_at TEXT,
            checkin_sent_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, course)
        );
    """)
    conn.commit()
    conn.close()


def mark_session_active(user_id: str, course: str, session_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT last_session_id FROM session_tracking WHERE user_id=? AND course=?",
        (user_id, course)
    ).fetchone()

    if row and row["last_session_id"] == session_id:
        # Same session — just update timestamp
        conn.execute(
            "UPDATE session_tracking SET last_active_at=datetime('now'), is_new_session=0 WHERE user_id=? AND course=?",
            (user_id, course)
        )
    else:
        # New or changed session
        conn.execute(
            """INSERT OR REPLACE INTO session_tracking
               (user_id, course, last_session_id, is_new_session, last_active_at)
               VALUES (?, ?, ?, 1, datetime('now'))""",
            (user_id, course, session_id)
        )
    conn.commit()
    conn.close()


def is_new_session(user_id: str, course: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT is_new_session FROM session_tracking WHERE user_id=? AND course=?",
        (user_id, course)
    ).fetchone()
    conn.close()
    return row["is_new_session"] == 1 if row else True


def mark_checkin_sent(user_id: str, course: str):
    conn = get_conn()
    conn.execute(
        "UPDATE session_tracking SET is_new_session=0, checkin_sent_at=datetime('now') WHERE user_id=? AND course=?",
        (user_id, course)
    )
    conn.commit()
    conn.close()


def get_current_plan(user_id: str, course: str) -> str:
    """Extract the most recent teaching plan from session context."""
    msgs = get_recent_rounds(user_id, course, max_rounds=5)
    # Look for the last eval result or plan mention
    for m in reversed(msgs):
        c = m.get("content", "")
        if "教学计划" in c or "next_action" in c or "proposed_activity" in c:
            return c[:500]
    return ""


# ─── Migration ────────────────────────────────────────────

def migrate_old_sessions(user_id: str):
    """
    Migrate old per-session_id JSON files into unified course-based logs.
    Scans data/student/{user_id}/sessions/ for old JSON files,
    reads them, and appends messages to the appropriate {course}_session.log.
    """
    old_dir = f"data/student/{user_id}/sessions"
    if not os.path.exists(old_dir):
        return 0

    migrated = 0
    for fname in sorted(os.listdir(old_dir)):
        if not fname.endswith(".json"):
            continue
        filepath = os.path.join(old_dir, fname)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        course = data.get("course", "math")
        messages = data.get("messages", [])
        if not messages:
            continue

        # Check if already migrated (avoid duplicates)
        existing = get_all_messages(user_id, course)
        if existing:
            # Simple check: if any existing message matches first old message time
            old_first_time = messages[0].get("time", "") if messages else ""
            for em in existing:
                if em.get("time") == old_first_time:
                    break
            else:
                # Not found — append
                for m in messages:
                    append_to_session(user_id, course, m.get("role", "user"),
                                      m.get("content", ""))
                migrated += 1
        else:
            for m in messages:
                append_to_session(user_id, course, m.get("role", "user"),
                                  m.get("content", ""))
            migrated += 1

    return migrated


# Initialize on import
init_session_tracking()
