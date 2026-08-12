import sqlite3
import os
import json
from datetime import datetime, date

DB_PATH = "data/learning.db"


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ─── Weekly Schedule ─────────────────────────────────────

DEFAULT_WEEKLY_SCHEDULE = {
    0: ["math", "english"],            # Mon: 数学 + 英语
    1: ["chinese", "coding"],           # Tue: 语文 + 编程
    2: ["math", "oral_english"],        # Wed: 数学 + 口语
    3: ["chinese", "english"],          # Thu: 语文 + 英语
    4: ["coding", "learning"],          # Fri: 编程 + 学习科学
    5: ["oral_english", "math"],        # Sat: 口语 + 数学（轻量复习）
    6: ["learning", "english"],         # Sun: 学习科学 + 英语（收心准备）
}

def get_weekly_schedule(user_id: str) -> dict:
    """Get user's weekly schedule. Returns dict of day_index -> [course, ...]"""
    conn = get_conn()
    row = conn.execute(
        "SELECT schedule_json FROM weekly_schedules WHERE user_id=?",
        (user_id,)
    ).fetchone()
    conn.close()
    if row and row["schedule_json"]:
        return json.loads(row["schedule_json"])
    # Return defaults
    return {str(k): v for k, v in DEFAULT_WEEKLY_SCHEDULE.items()}

def save_weekly_schedule(user_id: str, schedule: dict):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO weekly_schedules (user_id, schedule_json) VALUES (?,?)",
        (user_id, json.dumps(schedule, ensure_ascii=False))
    )
    conn.commit()
    conn.close()

def get_todays_courses(user_id: str) -> list:
    """Get courses scheduled for today based on weekly schedule."""
    today = date.today()
    day_index = today.weekday()  # 0=Monday, 6=Sunday
    schedule = get_weekly_schedule(user_id)
    return schedule.get(str(day_index), [])

def generate_daily_tasks_from_schedule(user_id: str) -> list:
    """Generate today's tasks from the weekly schedule."""
    today = date.today().isoformat()
    courses = get_todays_courses(user_id)
    if not courses:
        return get_daily_tasks(user_id)  # fallback to old logic

    conn = get_conn()
    for i, course in enumerate(courses):
        # If task already exists (any status), skip; otherwise create pending
        existing = conn.execute(
            "SELECT id FROM daily_tasks WHERE user_id=? AND date=? AND course=?",
            (user_id, today, course)
        ).fetchone()
        if not existing:
            conn.execute(
                """INSERT INTO daily_tasks
                   (user_id, course, date, task_order, status, duration_seconds)
                   VALUES (?, ?, ?, ?, 'pending', 2400)""",
                (user_id, course, today, i + 1)
            )
        else:
            conn.execute(
                "UPDATE daily_tasks SET task_order=? WHERE user_id=? AND date=? AND course=?",
                (i + 1, user_id, today, course)
            )
    conn.commit()
    conn.close()
    return get_daily_tasks(user_id)


def init_storage():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS weekly_schedules (
            user_id TEXT PRIMARY KEY,
            schedule_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS learning_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            course TEXT NOT NULL,
            session_id TEXT,
            teaching_plan TEXT,
            eval_result TEXT,
            knowledge_points TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_records_user ON learning_records(user_id, course);

        CREATE TABLE IF NOT EXISTS daily_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            course TEXT NOT NULL,
            date TEXT NOT NULL,
            task_order INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            duration_seconds INTEGER DEFAULT 2400,
            elapsed_seconds INTEGER DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            session_id TEXT,
            knowledge_points TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, date, course, task_order)
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_user ON daily_tasks(user_id, date);

        CREATE TABLE IF NOT EXISTS learning_streaks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            courses_completed INTEGER DEFAULT 0,
            total_minutes INTEGER DEFAULT 0,
            total_courses INTEGER DEFAULT 2,
            UNIQUE(user_id, date)
        );
    """)
    conn.commit()
    # Migration: ensure total_courses column exists
    try:
        conn.execute("ALTER TABLE learning_streaks ADD COLUMN total_courses INTEGER DEFAULT 2")
        conn.commit()
    except Exception:
        pass  # column already exists
    conn.close()


# ─── Learning Records ─────────────────────────────────────

def save_learning_record(user_id: str, course: str, session_id: str,
                         teaching_plan: dict, eval_result: dict,
                         knowledge_points: list):
    conn = get_conn()
    conn.execute(
        """INSERT INTO learning_records (user_id, course, session_id,
           teaching_plan, eval_result, knowledge_points)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, course, session_id,
         json.dumps(teaching_plan, ensure_ascii=False) if teaching_plan else None,
         json.dumps(eval_result, ensure_ascii=False) if eval_result else None,
         json.dumps(knowledge_points, ensure_ascii=False))
    )
    conn.commit()
    conn.close()


def get_recent_records(user_id: str, course: str = None, limit: int = 10) -> list:
    conn = get_conn()
    if course:
        rows = conn.execute(
            """SELECT * FROM learning_records WHERE user_id=? AND course=?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, course, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM learning_records WHERE user_id=?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit)
        ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


# ─── Daily Tasks ──────────────────────────────────────────

def generate_daily_tasks(user_id: str, target_courses: int = 2):
    """Generate today's daily tasks if not exist. Returns list of tasks."""
    today = date.today().isoformat()

    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM daily_tasks WHERE user_id=? AND date=?",
        (user_id, today)
    ).fetchall()
    conn.close()

    if existing:
        return get_daily_tasks(user_id)

    # Pick courses based on recent activity — prefer the last studied courses,
    # then fill with available courses
    recent = get_recent_records(user_id, limit=5)
    recent_courses = list(dict.fromkeys([r['course'] for r in recent]))

    available = ['math', 'chinese', 'english', 'coding']
    chosen = []
    for c in recent_courses:
        if c in available and c not in chosen:
            chosen.append(c)
    for c in available:
        if c not in chosen and len(chosen) < target_courses:
            chosen.append(c)

    tasks = []
    for i, course in enumerate(chosen[:target_courses]):
        conn = get_conn()
        conn.execute(
            """INSERT OR IGNORE INTO daily_tasks
               (user_id, course, date, task_order, status)
               VALUES (?, ?, ?, ?, 'pending')""",
            (user_id, course, today, i + 1)
        )
        conn.commit()
        conn.close()

    return get_daily_tasks(user_id)


def get_daily_tasks(user_id: str, target_date: str = None) -> list:
    if target_date is None:
        target_date = date.today().isoformat()
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM daily_tasks WHERE user_id=? AND date=?
           ORDER BY task_order""",
        (user_id, target_date)
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def start_task(user_id: str, course: str, session_id: str) -> dict:
    today = date.today().isoformat()
    conn = get_conn()
    # If no task exists yet for this course today, auto-create one
    existing = conn.execute(
        "SELECT * FROM daily_tasks WHERE user_id=? AND date=? AND course=?",
        (user_id, today, course)
    ).fetchone()
    if not existing:
        # Auto-create
        max_order = conn.execute(
            "SELECT MAX(task_order) as m FROM daily_tasks WHERE user_id=? AND date=?",
            (user_id, today)
        ).fetchone()
        order = (max_order['m'] or 0) + 1
        conn.execute(
            """INSERT INTO daily_tasks (user_id, course, date, task_order, status, duration_seconds)
               VALUES (?, ?, ?, ?, 'in_progress', 2400)""",
            (user_id, course, today, order)
        )
        conn.commit()
        conn.close()
        return get_daily_tasks(user_id)

    conn.execute(
        """UPDATE daily_tasks SET status='in_progress', started_at=datetime('now'),
           session_id=?, elapsed_seconds=0 WHERE user_id=? AND date=? AND course=?""",
        (session_id, user_id, today, course)
    )
    conn.commit()
    conn.close()
    return get_daily_tasks(user_id)


def heartbeat_task(user_id: str, course: str) -> dict:
    """Add 10 seconds to elapsed time. Auto-complete if >= 40 min. Returns tasks + completed flag."""
    today = date.today().isoformat()
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM daily_tasks WHERE user_id=? AND date=? AND course=? AND status='in_progress'",
        (user_id, today, course)
    ).fetchone()
    if not row:
        conn.close()
        return {"tasks": get_daily_tasks(user_id), "completed": False}

    elapsed = (row['elapsed_seconds'] or 0) + 10
    duration = row['duration_seconds'] or 2400
    completed = elapsed >= duration

    if completed:
        conn.execute(
            """UPDATE daily_tasks SET status='completed', elapsed_seconds=?,
               completed_at=datetime('now')
               WHERE user_id=? AND date=? AND course=? AND status='in_progress'""",
            (duration, user_id, today, course)
        )
    else:
        conn.execute(
            "UPDATE daily_tasks SET elapsed_seconds=? WHERE user_id=? AND date=? AND course=? AND status='in_progress'",
            (elapsed, user_id, today, course)
        )
    conn.commit()
    conn.close()

    if completed:
        _update_streak(user_id, today)

    return {"tasks": get_daily_tasks(user_id), "completed": completed, "elapsed": min(elapsed, duration)}


def _update_streak(user_id: str, today: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM daily_tasks WHERE user_id=? AND date=? AND status='completed'",
        (user_id, today)
    ).fetchone()
    completed = row['cnt'] if row else 0
    total_min = completed * 40
    # Count total tasks for today
    total_row = conn.execute(
        "SELECT COUNT(*) as total FROM daily_tasks WHERE user_id=? AND date=?",
        (user_id, today)
    ).fetchone()
    total_courses = total_row['total'] if total_row else 2
    conn.execute(
        """INSERT OR REPLACE INTO learning_streaks (user_id, date, courses_completed, total_minutes, total_courses)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, today, completed, total_min, total_courses)
    )
    conn.commit()
    conn.close()


def complete_task(user_id: str, course: str):
    today = date.today().isoformat()
    conn = get_conn()
    row = conn.execute(
        "SELECT duration_seconds FROM daily_tasks WHERE user_id=? AND date=? AND course=? AND status='in_progress'",
        (user_id, today, course)
    ).fetchone()
    duration = row['duration_seconds'] if row else 2400
    conn.execute(
        """UPDATE daily_tasks SET status='completed', completed_at=datetime('now'),
           elapsed_seconds=?
           WHERE user_id=? AND date=? AND course=? AND status='in_progress'""",
        (duration, user_id, today, course)
    )
    conn.commit()
    conn.close()
    _update_streak(user_id, today)
    return get_daily_tasks(user_id)


# ─── Streaks ──────────────────────────────────────────────

def get_streak_info(user_id: str) -> dict:
    """Return current streak count and today's status."""
    today = date.today().isoformat()
    conn = get_conn()

    # Count consecutive days backward from today
    streak = 0
    check_date = date.today()
    while True:
        row = conn.execute(
            "SELECT id FROM learning_streaks WHERE user_id=? AND date=? AND courses_completed > 0",
            (user_id, check_date.isoformat())
        ).fetchone()
        if row:
            streak += 1
            check_date = check_date.replace(day=check_date.day - 1) if check_date.day > 1 else \
                         (check_date.replace(month=check_date.month - 1, day=28) if check_date.month > 1 else
                          check_date.replace(year=check_date.year - 1, month=12, day=31))
            # Simple: just go back 1 day using timedelta
            from datetime import timedelta
            check_date = date.today() - timedelta(days=streak)
        else:
            break

    # Today's status
    today_row = conn.execute(
        "SELECT * FROM learning_streaks WHERE user_id=? AND date=?",
        (user_id, today)
    ).fetchone()

    conn.close()
    return {
        "streak": streak,
        "today_courses": today_row['courses_completed'] if today_row else 0,
        "today_minutes": today_row['total_minutes'] if today_row else 0
    }


def get_calendar(user_id: str, year: int, month: int) -> list:
    """Return daily learning data for a month."""
    conn = get_conn()
    prefix = f"{year}-{month:02d}"
    rows = conn.execute(
        """SELECT date, courses_completed, total_minutes, total_courses
           FROM learning_streaks
           WHERE user_id=? AND date LIKE ?
           ORDER BY date""",
        (user_id, f"{prefix}%")
    ).fetchall()
    result = []
    for r in rows:
        d = _row_to_dict(r)
        # Count total courses for that day from schedule
        day_idx = date.fromisoformat(d['date']).weekday()
        sched = get_weekly_schedule(user_id)
        d['total_courses'] = len(sched.get(str(day_idx), []))
        result.append(d)
    conn.close()
    return result


def get_daily_detail(user_id: str, target_date: str) -> dict:
    """Get detailed learning info for a specific date."""
    tasks = get_daily_tasks(user_id, target_date)
    records = []
    for t in tasks:
        recs = get_recent_records(user_id, t['course'], limit=3)
        records.extend([r for r in recs if r.get('created_at', '').startswith(target_date)])
    return {
        "date": target_date,
        "tasks": tasks,
        "records": records
    }


# ─── Knowledge Points Extraction ──────────────────────────

def extract_knowledge_points(eval_result: dict) -> list:
    """Extract knowledge points — uses the primary ID field for each course.

    Math:     knowledge_point
    Chinese:  sub_skill (or ability_dimension)
    English:  sub_skill (or skill_area)
    Coding:   knowledge_point (or knowledge_area)
    """
    points = []
    deltas = eval_result.get('model_update_delta', [])
    for d in deltas:
        # Prefer the most specific field for each course
        kp = (d.get('knowledge_point') or      # Math, Coding
              d.get('sub_skill') or             # Chinese, English
              d.get('ability_dimension') or     # Chinese (fallback)
              d.get('skill_area') or            # English (fallback)
              d.get('knowledge_area') or '')    # Coding (fallback)
        if kp:
            points.append(kp)
    plan = eval_result.get('teaching_plan', {})
    target = plan.get('target', {})
    if target:
        kp = (target.get('knowledge_point') or
              target.get('sub_skill') or
              target.get('ability_dimension') or
              target.get('skill_area') or
              target.get('knowledge_area') or '')
        if kp and kp not in points:
            points.append(kp)
    return points


# ─── Helper ───────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}
